-- ═══════════════════════════════════════════════════════════════════════════
-- 018_intake_claim_release_rpcs.sql
--
-- Task #43 correction — extends the task #44 transactional-integrity fix
-- (supabase/migrations/017_intake_review_decision_rpcs.sql) to
-- intake.review.claim (CMD000003) and intake.review.release (CMD000004).
--
-- Context: 017's own scope note explicitly flagged that claim/release kept
-- the original two-statement pattern (conditional UPDATE on
-- operations.intake_packets, then a separate INSERT into
-- operations.intake_packet_events) because task #44's correction was
-- scoped to "each decision" (approve/return) and claim/release weren't
-- named. Brad has now asked for the same fix here, narrowly: same defect
-- class (a claim/release event could fail to record after its UPDATE
-- commits), same fix (move the whole operation into one Postgres function
-- so the UPDATE and the INSERT commit or roll back together).
--
-- operations.claim_intake_packet(p_packet_id, p_actor_user_id) and
-- operations.release_intake_packet(p_packet_id, p_actor_user_id, p_reason)
-- follow the identical pattern established in 017: FOR UPDATE row lock,
-- authorization resolved by direct operations.users lookup (RPC as
-- authoritative, not a client-supplied flag), single UPDATE, single INSERT,
-- RETURN the row — one statement, one transaction, no separate rollback
-- code required because that's what a single plpgsql function body inside
-- PostgREST's one-statement transaction already gives for free.
--
-- Do not execute this migration against any database without review.
-- ═══════════════════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════════════════════
-- Governance clarification (Founder/CEO authority) — 2026-07-16
--
-- See the matching header note in supabase/migrations/017_intake_review_
-- decision_rpcs.sql for full context (Brad's instruction: the Founder/CEO
-- must not be artificially restricted from ordinary Governance Reviewer
-- operations — claim, release, approve, return; the audit trail must
-- always show the acting user and their role/authority).
--
-- claim_intake_packet's authorization gate already admitted 'admin' (task
-- #43's deliberate reviewer-or-admin widening, unchanged here) and
-- release_intake_packet's admin-override path already existed — neither
-- function's authorization logic needed to change for this clarification;
-- claim/release were never the "artificial restriction" Brad flagged
-- (that was return, corrected in migration 017).
--
-- What did change here: both functions' event metadata now always includes
-- the acting user's role as 'actor_role'. claim already looked up the role
-- unconditionally for its gate, so this is a metadata-only addition there;
-- release previously looked the role up only on the override branch — that
-- lookup is now unconditional here too, so a self-release's event also
-- carries actor_role, not just an override release's.
--
-- Still not executed against any database; still requires review before
-- migration or commit.
-- ═══════════════════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════════════════════
-- Governance-alignment correction — authority_basis metadata (2026-07-16,
-- second pass)
--
-- See the matching header note in supabase/migrations/017_intake_review_
-- decision_rpcs.sql for full context. Brad's follow-up correction requires
-- that 'admin' be documented, in the audit trail itself and not only in
-- prose, as the current implementation adapter through which Founder/CEO
-- authority is exercised — not a general grant of override authority to
-- every future holder of an administrator-tier database role.
--
-- Both functions below now also record a new `authority_basis` metadata
-- key alongside the existing `actor_role`: 'governance_reviewer' for an
-- actor holding the 'reviewer' role, or 'founder_ceo_override' for an
-- actor holding the 'admin' role (the only two roles that ever reach the
-- point in either function where this is computed — every other role is
-- already rejected with GP403 before that point). actor_role remains the
-- literal DB role; authority_basis is the organizational authority basis
-- it stands for today, kept as a distinct field precisely so it can be
-- re-evaluated independently of actor_role if a real Founder/CEO identity
-- is ever added to the schema.
--
-- Still not executed against any database; still requires review before
-- migration or commit.
-- ═══════════════════════════════════════════════════════════════════════════


-- ── operations.claim_intake_packet ───────────────────────────────────────
--
-- Implements intake.review.claim (CMD000003) per DEC000001 §5.3-§5.4:
--   1. Actor must hold Governance Reviewer or Administrator authority
--      under the approved interim role mapping (operations.users.role IN
--      ('reviewer','admin')) — checked before the packet is even looked
--      up, matching the original endpoint's order (role gate is
--      unconditional, not packet-state-dependent).
--   2. Packet must exist and be pending_review with no existing claimant.
--   3. Transition to in_review, set both claim fields.
--   4. Insert the claim event.
--   5. Return the resulting row.
--   6. Any RAISE aborts the whole function — no packet is ever left
--      in_review without its claim event.
--
-- Role-check duplication (same flagged technical debt as 017's admin-
-- override check): this queries operations.users.role directly, duplicating
-- api/role_adapter.py's can_claim_review() at the SQL layer. Update both
-- together if the interim mapping changes.
--
-- Note: this authorizes 'reviewer' OR 'admin' to claim. The original task
-- #43 Python implementation (can_claim_review -> is_governance_reviewer
-- only) authorized 'reviewer' alone; Brad's task #43 correction request
-- explicitly widened this to "Governance Reviewer or administrator
-- authority per the approved interim mapping" for the RPC. This is a
-- deliberate behavioral change made at his explicit instruction, not a
-- bug — flagged here and in the scope report so it isn't mistaken for
-- silent scope creep.
CREATE OR REPLACE FUNCTION operations.claim_intake_packet(
    p_packet_id     uuid,
    p_actor_user_id uuid
)
RETURNS operations.intake_packets
LANGUAGE plpgsql
AS $$
DECLARE
    v_row             operations.intake_packets%ROWTYPE;
    v_actor_role      text;
    v_authority_basis text;
BEGIN
    IF p_actor_user_id IS NULL THEN
        RAISE EXCEPTION 'p_actor_user_id is required'
            USING ERRCODE = 'GP422';
    END IF;

    -- 1. Authorization gate, independent of packet state (matches the
    -- original endpoint's order: role checked before any packet lookup).
    SELECT role INTO v_actor_role
    FROM operations.users
    WHERE user_id = p_actor_user_id
      AND is_active = true;

    IF v_actor_role IS DISTINCT FROM 'reviewer' AND v_actor_role IS DISTINCT FROM 'admin' THEN
        RAISE EXCEPTION 'Only Governance Reviewers or Administrators may claim a packet for review'
            USING ERRCODE = 'GP403';
    END IF;

    -- Organizational authority basis for the audit trail, distinct from
    -- v_actor_role's raw DB-role value — governance-alignment correction,
    -- see migration header.
    v_authority_basis := CASE WHEN v_actor_role = 'admin'
                               THEN 'founder_ceo_override'
                               ELSE 'governance_reviewer'
                          END;

    -- 2. Lock the row for the duration of this transaction — a real lock
    -- in place of the API-layer conditional-UPDATE-with-zero-rows-check
    -- pattern, so a concurrent claim cannot interleave with this check.
    SELECT * INTO v_row
    FROM operations.intake_packets
    WHERE packet_id = p_packet_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Packet % not found', p_packet_id
            USING ERRCODE = 'GP404';
    END IF;

    IF v_row.packet_status <> 'pending_review' OR v_row.claimed_by_user_id IS NOT NULL THEN
        RAISE EXCEPTION 'Packet % is not available to claim (already claimed, or not pending_review)', p_packet_id
            USING ERRCODE = 'GP409';
    END IF;

    -- 3. Transition + set claim fields.
    UPDATE operations.intake_packets
    SET packet_status      = 'in_review',
        claimed_by_user_id = p_actor_user_id,
        claimed_at         = now()
    WHERE packet_id = p_packet_id
    RETURNING * INTO v_row;

    -- 4. Permanent claim-event record. Rolls back the UPDATE above with it
    -- if this INSERT fails, same guarantee as 017's decision RPCs.
    INSERT INTO operations.intake_packet_events (
        packet_id, event_type, actor_type, actor_id, reason, metadata
    ) VALUES (
        p_packet_id, 'claim', 'user', p_actor_user_id::text, NULL,
        jsonb_build_object('actor_role', v_actor_role, 'authority_basis', v_authority_basis)
    );

    -- 5.
    RETURN v_row;
END;
$$;

COMMENT ON FUNCTION operations.claim_intake_packet(uuid, uuid) IS
    'Task #43 (corrected); Founder/CEO governance clarification 2026-07-16; '
    'authority_basis correction 2026-07-16. Single-transaction '
    'intake.review.claim (CMD000003): requires Governance Reviewer or '
    'Administrator authority (interim role mapping), validates '
    'pending_review+unclaimed state, transitions status, sets claim fields, '
    'and writes the claim event (with actor_role and authority_basis always '
    'recorded in metadata — the raw DB role vs. the organizational authority '
    'basis it stands for) atomically. DEC000001 §5.3-§5.4.';


-- ── operations.release_intake_packet ─────────────────────────────────────
--
-- Implements intake.review.release (CMD000004) per DEC000001 §5.5:
--   1. Packet must exist and be in_review (with a claimant).
--   2. Current claimant may self-release without a reason. Anyone else
--      must hold Administrator authority AND supply a non-blank reason
--      (override release).
--   3. Transition to pending_review, clear both claim fields.
--   4. Insert the release event — reason and override metadata recorded
--      distinctly (self-release: reason NULL, override:false; override
--      release: reason preserved, override:true, former claimant_user_id
--      recorded).
--   5. Return the resulting row.
--   6. Any RAISE aborts the whole function.
CREATE OR REPLACE FUNCTION operations.release_intake_packet(
    p_packet_id     uuid,
    p_actor_user_id uuid,
    p_reason        text DEFAULT NULL
)
RETURNS operations.intake_packets
LANGUAGE plpgsql
AS $$
DECLARE
    v_row             operations.intake_packets%ROWTYPE;
    v_claimant        uuid;
    v_is_override     boolean;
    v_actor_role      text;
    v_authority_basis text;
BEGIN
    IF p_actor_user_id IS NULL THEN
        RAISE EXCEPTION 'p_actor_user_id is required'
            USING ERRCODE = 'GP422';
    END IF;

    -- 1. Lock the row for the duration of this transaction.
    SELECT * INTO v_row
    FROM operations.intake_packets
    WHERE packet_id = p_packet_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Packet % not found', p_packet_id
            USING ERRCODE = 'GP404';
    END IF;

    IF v_row.packet_status <> 'in_review' OR v_row.claimed_by_user_id IS NULL THEN
        RAISE EXCEPTION 'Packet % is not currently claimed / in_review', p_packet_id
            USING ERRCODE = 'GP409';
    END IF;

    v_claimant    := v_row.claimed_by_user_id;
    v_is_override := (p_actor_user_id IS DISTINCT FROM v_claimant);

    -- 2. Authorization. Self-release needs nothing further. Override
    -- release requires Administrator authority (direct operations.users
    -- lookup — RPC is authoritative, same duplication caveat as 017 and
    -- claim_intake_packet above) and a non-blank reason. Role is always
    -- resolved now (not only for the override branch) so every event this
    -- function writes carries the acting user's role in its metadata
    -- (Founder/CEO governance clarification, see migration header).
    SELECT role INTO v_actor_role
    FROM operations.users
    WHERE user_id = p_actor_user_id
      AND is_active = true;

    IF v_is_override THEN
        IF v_actor_role IS DISTINCT FROM 'admin' THEN
            RAISE EXCEPTION 'Only the current claimant or an Administrator may release packet %', p_packet_id
                USING ERRCODE = 'GP403';
        END IF;

        IF p_reason IS NULL OR btrim(p_reason) = '' THEN
            RAISE EXCEPTION 'An Administrator override release requires a non-blank reason'
                USING ERRCODE = 'GP422';
        END IF;
    END IF;

    -- Organizational authority basis for the audit trail, distinct from
    -- v_actor_role's raw DB-role value — governance-alignment correction,
    -- see migration header. Only 'reviewer' or 'admin' ever reach this
    -- point (every other role was already rejected above, or was never
    -- eligible to become claimant/actor here).
    v_authority_basis := CASE WHEN v_actor_role = 'admin'
                               THEN 'founder_ceo_override'
                               ELSE 'governance_reviewer'
                          END;

    -- 3. Transition + clear claim fields.
    UPDATE operations.intake_packets
    SET packet_status      = 'pending_review',
        claimed_by_user_id = NULL,
        claimed_at          = NULL
    WHERE packet_id = p_packet_id
    RETURNING * INTO v_row;

    -- 4. Permanent release-event record, override metadata recorded
    -- distinctly from an ordinary self-release. Rolls back the UPDATE
    -- above with it if this INSERT fails.
    INSERT INTO operations.intake_packet_events (
        packet_id, event_type, actor_type, actor_id, reason, metadata
    ) VALUES (
        p_packet_id,
        'release',
        'user',
        p_actor_user_id::text,
        CASE WHEN v_is_override THEN p_reason ELSE NULL END,
        jsonb_build_object(
            'actor_role', v_actor_role,
            'authority_basis', v_authority_basis,
            'override', v_is_override,
            'claimant_user_id', v_claimant
        )
    );

    -- 5.
    RETURN v_row;
END;
$$;

COMMENT ON FUNCTION operations.release_intake_packet(uuid, uuid, text) IS
    'Task #43 (corrected); Founder/CEO governance clarification 2026-07-16; '
    'authority_basis correction 2026-07-16. Single-transaction '
    'intake.review.release (CMD000004): validates in_review+claimed state, '
    'allows claimant self-release or an Administrator override release with '
    'a mandatory reason, transitions status, clears claim fields, and writes '
    'the release event (with distinct override metadata, and actor_role/'
    'authority_basis always — the raw DB role vs. the organizational '
    'authority basis it stands for) atomically. DEC000001 §5.5.';


-- ── Grants ────────────────────────────────────────────────────────────────
GRANT EXECUTE ON FUNCTION operations.claim_intake_packet(uuid, uuid)
    TO service_role, authenticated;
GRANT EXECUTE ON FUNCTION operations.release_intake_packet(uuid, uuid, text)
    TO service_role, authenticated;
