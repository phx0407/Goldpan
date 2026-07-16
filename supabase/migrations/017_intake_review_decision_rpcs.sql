-- ═══════════════════════════════════════════════════════════════════════════
-- 017_intake_review_decision_rpcs.sql
--
-- Task #44 correction — transactional-integrity fix.
--
-- Context: the first pass at task #44 (intake.review.approve / .return)
-- implemented the DEC000001 §5.5 "one operation" requirement as two
-- separate PostgREST statements from the API layer — a conditional UPDATE
-- on operations.intake_packets, then a separate INSERT into
-- operations.intake_packet_events — with the gap between them explicitly
-- flagged rather than hidden. That was rejected: a packet can end up
-- approved/returned with no corresponding audit event if the INSERT fails
-- after the UPDATE commits, and reporting that as HTTP 500 does not
-- satisfy DEC000001's governed-operation requirement or the Master OS
-- audit requirement — an unaudited decision is a real integrity defect,
-- not a cosmetic one.
--
-- Fix: move the entire decision — validation, authorization, status
-- transition, claim-clearing, and event insert — into a single Postgres
-- function per command, invoked by the API as one RPC call
-- (`sb.rpc("approve_intake_packet", {...}).execute()` /
-- `sb.rpc("return_intake_packet", {...}).execute()`). Everything a
-- function does runs inside the one implicit transaction PostgREST opens
-- for that single statement; if any step raises, Postgres rolls back the
-- entire function's work — the UPDATE and the INSERT either both commit
-- or neither does. This is genuine ACID atomicity, not a documented gap.
--
-- Scope: this migration touches only the two decision commands named in
-- the correction (intake.review.approve, intake.review.return). It does
-- NOT touch intake.review.claim or intake.review.release (task #43) —
-- those still use the two-statement UPDATE+INSERT pattern. That pattern
-- has the same theoretical gap (a claim/release event could fail to
-- record after its UPDATE commits), but Brad's correction was scoped
-- explicitly to "each decision" (approve/return); claim/release were not
-- named and are not touched here. Flagged in the task #44 scope report
-- for a separate decision, not silently carried into this change.
--
-- Do not execute this migration against any database without review.
-- ═══════════════════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════════════════════
-- Governance clarification (Founder/CEO authority) — 2026-07-16
--
-- Brad's instruction: the Founder/CEO must not be artificially restricted
-- from performing ordinary Governance Reviewer operations (claim, release,
-- approve, return) during GoldPan's early operating stage, while
-- auditability must still show exactly who acted and under what authority.
--
-- There is no distinct 'founder'/'ceo' value in operations.users.role (the
-- CHECK constraint is still canvasser|reviewer|coordinator|admin, migration
-- 004) and no separate Founder/CEO authority tier exists anywhere in this
-- schema or in api/role_adapter.py's interim mapping. Per that mapping,
-- 'admin' already IS the Administrator/override-authority tier this system
-- has, so the Founder/CEO acts through the existing 'admin' role — no
-- schema change was made here to introduce a new role value. If GoldPan
-- later wants a role model that distinguishes "the Founder personally"
-- from "any Administrator," that requires an actual schema change (a new
-- role value or a boolean flag) and is out of scope for this clarification.
--
-- Two concrete changes made in this pass:
--
--   1. operations.return_intake_packet's claimant-only rule (no override,
--      per DEC000001 §3 as originally read) is superseded: an Administrator
--      may now also return a packet they did not claim, mirroring the
--      claimant-or-admin pattern operations.approve_intake_packet and (in
--      migration 018) operations.release_intake_packet already use. This
--      was the one operation of the four (claim/release/approve/return)
--      where the CEO, acting as an ordinary Administrator and not the
--      claimant, would previously have been blocked outright rather than
--      merely needing to supply a reason — the artificial restriction Brad
--      flagged. return already requires a non-blank reason from every
--      caller (self or override), so no new "override reason" parameter
--      was added; the existing p_reason now also doubles as the override
--      justification when the actor is not the claimant, and that fact is
--      recorded in the event's metadata (override:true, claimant_user_id)
--      exactly as approve/release do.
--
--   2. Every event these functions write (approve, return here; claim,
--      release in migration 018) now always includes the acting user's DB
--      role in its metadata as 'actor_role', not only when an override
--      occurred. Previously the role was looked up (and so was knowable)
--      only on the override branch of approve; ordinary claimant-self
--      actions recorded no role at all. "The audit trail must always
--      record the actual acting user and their role/authority" is Brad's
--      explicit requirement — actor_id already recorded the acting user;
--      actor_role now closes the "and their role/authority" half of that
--      sentence for every event, self-action or override alike. Since no
--      separate Founder/CEO identity exists (see above), recording
--      actor_role is also the concrete fulfillment of Brad's fallback
--      instruction — "or record the actor role if that is already
--      available" — for events performed by the CEO acting as 'admin'.
--
-- Still not executed against any database; still requires review before
-- migration or commit.
-- ═══════════════════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════════════════════
-- Governance-alignment correction — authority_basis metadata (2026-07-16,
-- second pass)
--
-- The direction of the governance clarification above is accepted, but
-- Brad flagged one narrow documentation defect it left behind: DEC000001
-- and the Command Registry must not be read as describing
-- intake.review.return as claimant-only with no exception, now that an
-- Administrator override exists for it. The corresponding narrow doc edits
-- are in docs/decisions/DEC000001_CANONICAL_INTAKE_PACKET_STATE_MACHINE.md
-- §5.5 and docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md's CMD000006 §18 note
-- (both dated 2026-07-16), not in this migration file.
--
-- The functional correction made here: this pass restates, explicitly,
-- that the Founder/CEO's use of the 'admin' DB role is the CURRENT
-- IMPLEMENTATION ADAPTER through which their authority is exercised — not
-- a general grant of override authority to every future holder of an
-- administrator-tier database role. To keep that distinction legible in
-- the audit trail itself (not just in prose doc commentary that could
-- drift from the code), every event these four functions write (approve
-- and return here; claim and release in migration 018) now also records a
-- new `authority_basis` metadata key, alongside the existing `actor_role`:
--
--   * `actor_role`      — the actor's literal operations.users.role value
--                          at the time of the action (e.g. 'reviewer',
--                          'admin'). Unchanged from the first governance
--                          clarification pass above — this is the
--                          technical/database role, nothing more.
--   * `authority_basis` — the organizational authority basis the action
--                          was taken under: 'governance_reviewer' for an
--                          actor holding the 'reviewer' role, or
--                          'founder_ceo_override' for an actor holding the
--                          'admin' role — since 'admin' is, today, only
--                          ever held by the Founder/CEO exercising that
--                          authority through the current adapter (no
--                          other administrator population exists in this
--                          system yet). authority_basis is deliberately a
--                          distinct field from actor_role, not a renaming
--                          of it: actor_role will keep meaning "the DB
--                          role" even after a real role model replaces
--                          'admin' as the Founder/CEO's adapter, while
--                          authority_basis's 'founder_ceo_override' value
--                          is what should be re-evaluated at that time —
--                          it is not a promise that every future 'admin'
--                          row automatically continues to mean
--                          Founder/CEO.
--
-- Only 'reviewer' and 'admin' actors ever reach the point in any of these
-- four functions where authority_basis is computed — every other role is
-- already rejected with GP403 before that point (claim's reviewer-or-admin
-- gate; approve/return/release's claimant-or-admin-override checks) — so
-- the two-way mapping above is exhaustive for every event actually
-- written, not a partial mapping with silent gaps.
--
-- Still not executed against any database; still requires review before
-- migration or commit. Not a new task — a correction requested on top of
-- the still-pending Task #43/#44 review, per Brad's standing instruction
-- not to begin Task #45 or any other new work.
-- ═══════════════════════════════════════════════════════════════════════════


-- ── operations.approve_intake_packet ─────────────────────────────────────
--
-- Implements intake.review.approve (CMD000005) per DEC000001 §3, §5.5, §5.9:
--   1. Packet must exist and be in_review (with a claimant).
--   2. Ordinary approval is claimant-only. An actor who is not the claimant
--      may still approve iff they hold the 'admin' DB role (DEC000001 §3:
--      "claimant-or-admin only") AND supply a non-blank override_reason.
--   3-5. Transition to approved, clear the claim, stamp reviewed_at/by,
--      clear return_reason, apply reviewer_notes if provided.
--      packet_data is never referenced or written (DEC000001 §5.2).
--   6. Insert the append-only decision event, with override metadata when
--      applicable — this is the permanent record of the deciding reviewer
--      (DEC000001 §5.5), not the legacy reviewed_by column.
--   7. Return the resulting row.
--   8. Any RAISE aborts the whole function; nothing above is left applied.
--
-- Role-check duplication (explicitly flagged technical debt): the
-- claimant-or-admin check below queries operations.users.role directly
-- rather than trusting a client-supplied flag, per "make the RPC the
-- authoritative atomic mutation." This duplicates api/role_adapter.py's
-- interim DB-role → Blueprint-role mapping (reviewer/canvasser/admin/
-- coordinator) at the SQL layer. That module's docstring already commits
-- to being replaced wholesale when a real role model lands; this function
-- must be updated in lockstep if that mapping ever changes. Kept as a
-- literal 'admin' string comparison (not a lookup table) to keep the
-- duplication minimal and easy to grep for.
CREATE OR REPLACE FUNCTION operations.approve_intake_packet(
    p_packet_id       uuid,
    p_actor_user_id   uuid,
    p_override_reason text DEFAULT NULL,
    p_reviewer_notes  text DEFAULT NULL
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
    -- Defensive guard: the RPC is the authoritative check (task #44
    -- correction), so it must not assume a well-formed caller. A NULL
    -- actor should never reach here from the FastAPI layer (get_acting_user
    -- requires a resolved X-User-Id), but the function does not trust that
    -- invariant blindly.
    IF p_actor_user_id IS NULL THEN
        RAISE EXCEPTION 'p_actor_user_id is required'
            USING ERRCODE = 'GP422';
    END IF;

    -- 1. Lock the row for the duration of this transaction so a concurrent
    -- claim/release/decision cannot interleave between the validation
    -- below and the UPDATE further down (replaces the API-layer
    -- conditional-UPDATE-with-zero-rows-check pattern with a real lock).
    SELECT * INTO v_row
    FROM operations.intake_packets
    WHERE packet_id = p_packet_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Packet % not found', p_packet_id
            USING ERRCODE = 'GP404';
    END IF;

    IF v_row.packet_status <> 'in_review' OR v_row.claimed_by_user_id IS NULL THEN
        RAISE EXCEPTION 'Packet % must be in_review and claimed before it can be approved', p_packet_id
            USING ERRCODE = 'GP409';
    END IF;

    v_claimant    := v_row.claimed_by_user_id;
    v_is_override := (p_actor_user_id IS DISTINCT FROM v_claimant);

    -- 2. Authorization. Role is always resolved now (not only for the
    -- override branch) so every event this function writes can carry the
    -- acting user's role/authority in its metadata (Founder/CEO governance
    -- clarification, see migration header) — auditability must not depend
    -- on which branch of this IF ran.
    SELECT role INTO v_actor_role
    FROM operations.users
    WHERE user_id = p_actor_user_id
      AND is_active = true;

    IF v_is_override THEN
        IF v_actor_role IS DISTINCT FROM 'admin' THEN
            RAISE EXCEPTION 'Only the current claimant or an Administrator may approve packet %', p_packet_id
                USING ERRCODE = 'GP403';
        END IF;

        IF p_override_reason IS NULL OR btrim(p_override_reason) = '' THEN
            RAISE EXCEPTION 'An Administrator override approval requires a non-blank reason'
                USING ERRCODE = 'GP422';
        END IF;
    END IF;

    -- Organizational authority basis for the audit trail, distinct from
    -- v_actor_role's raw DB-role value — governance-alignment correction,
    -- see migration header. Only 'reviewer' or 'admin' ever reach this
    -- point (every other role was already rejected above).
    v_authority_basis := CASE WHEN v_actor_role = 'admin'
                               THEN 'founder_ceo_override'
                               ELSE 'governance_reviewer'
                          END;

    -- 3-5. Transition + clear claim + apply fields. packet_data untouched.
    UPDATE operations.intake_packets
    SET packet_status      = 'approved',
        reviewed_at        = now(),
        reviewed_by        = p_actor_user_id::text,
        return_reason      = NULL,
        claimed_by_user_id = NULL,
        claimed_at         = NULL,
        reviewer_notes     = COALESCE(p_reviewer_notes, reviewer_notes)
    WHERE packet_id = p_packet_id
    RETURNING * INTO v_row;

    -- 6. Permanent decision-event record (DEC000001 §5.5, §5.8). If this
    -- INSERT fails (append-only trigger, actor-validation trigger, or any
    -- other reason), the RAISE it produces propagates out of this
    -- function and Postgres rolls back the UPDATE above along with it —
    -- the packet is never left approved without its event.
    INSERT INTO operations.intake_packet_events (
        packet_id, event_type, actor_type, actor_id, reason, metadata
    ) VALUES (
        p_packet_id,
        'approve',
        'user',
        p_actor_user_id::text,
        CASE WHEN v_is_override THEN p_override_reason ELSE NULL END,
        jsonb_build_object('actor_role', v_actor_role, 'authority_basis', v_authority_basis) ||
        CASE WHEN v_is_override
             THEN jsonb_build_object('override', true, 'claimant_user_id', v_claimant)
             ELSE '{}'::jsonb
        END
    );

    -- 7.
    RETURN v_row;
END;
$$;

COMMENT ON FUNCTION operations.approve_intake_packet(uuid, uuid, text, text) IS
    'Task #44 (corrected); Founder/CEO governance clarification 2026-07-16; '
    'authority_basis correction 2026-07-16. Single-transaction '
    'intake.review.approve (CMD000005): validates in_review+claimant state, '
    'enforces claimant-or-admin authorization with mandatory override reason, '
    'transitions status, clears claim fields, and writes the append-only '
    'decision event (with actor_role and authority_basis always recorded in '
    'metadata — the raw DB role vs. the organizational authority basis it '
    'stands for) atomically. DEC000001 §3, §5.5, §5.9.';


-- ── operations.return_intake_packet ──────────────────────────────────────
--
-- Implements intake.review.return (CMD000006) per DEC000001 §3, §5.5, §5.9,
-- as superseded by the Founder/CEO governance clarification (see migration
-- header):
--   1. Packet must exist and be in_review (with a claimant).
--   2. Ordinary return is claimant-only. An actor who is not the claimant
--      may still return iff they hold the 'admin' DB role, mirroring
--      approve_intake_packet's claimant-or-admin pattern — this is the
--      change made by the governance clarification; DEC000001 §3's return
--      row originally stated the in_review-only source-state restriction
--      with no claimant-or-admin language, and api/role_adapter.py's
--      deliberate absence of a can_override_return function documented
--      that original no-override reading. Both are now superseded here;
--      see the migration header for why.
--   3-5. Transition to returned, clear the claim, stamp reviewed_at/by,
--      store the mandatory reason. packet_data is never referenced (§5.2).
--   6. Insert the append-only decision event with the full reason, override
--      metadata when applicable, and the acting user's role always.
--   7. Return the resulting row.
--   8. Any RAISE aborts the whole function.
CREATE OR REPLACE FUNCTION operations.return_intake_packet(
    p_packet_id      uuid,
    p_actor_user_id  uuid,
    p_reason         text,
    p_reviewer_notes text DEFAULT NULL
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

    IF p_reason IS NULL OR btrim(p_reason) = '' THEN
        RAISE EXCEPTION 'A non-blank reason is required to return a packet'
            USING ERRCODE = 'GP422';
    END IF;

    -- 1. Lock the row for the duration of this transaction (see comment in
    -- approve_intake_packet above).
    SELECT * INTO v_row
    FROM operations.intake_packets
    WHERE packet_id = p_packet_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Packet % not found', p_packet_id
            USING ERRCODE = 'GP404';
    END IF;

    IF v_row.packet_status <> 'in_review' OR v_row.claimed_by_user_id IS NULL THEN
        RAISE EXCEPTION 'Packet % must be in_review and claimed before it can be returned', p_packet_id
            USING ERRCODE = 'GP409';
    END IF;

    v_claimant    := v_row.claimed_by_user_id;
    v_is_override := (p_actor_user_id IS DISTINCT FROM v_claimant);

    -- 2. Authorization. Claimant-or-admin (governance clarification — see
    -- function and migration header comments; this was claimant-only prior
    -- to the clarification). Role is always resolved, not only for the
    -- override branch, so every event this function writes can carry the
    -- acting user's role/authority in its metadata.
    SELECT role INTO v_actor_role
    FROM operations.users
    WHERE user_id = p_actor_user_id
      AND is_active = true;

    IF v_is_override AND v_actor_role IS DISTINCT FROM 'admin' THEN
        RAISE EXCEPTION 'Only the current claimant or an Administrator may return packet %', p_packet_id
            USING ERRCODE = 'GP403';
    END IF;

    -- Organizational authority basis for the audit trail, distinct from
    -- v_actor_role's raw DB-role value — governance-alignment correction,
    -- see migration header. Only 'reviewer' or 'admin' ever reach this
    -- point (every other role was already rejected above).
    v_authority_basis := CASE WHEN v_actor_role = 'admin'
                               THEN 'founder_ceo_override'
                               ELSE 'governance_reviewer'
                          END;

    -- 3-5. Transition + clear claim + apply fields. packet_data untouched.
    UPDATE operations.intake_packets
    SET packet_status      = 'returned',
        return_reason      = p_reason,
        reviewed_at        = now(),
        reviewed_by        = p_actor_user_id::text,
        claimed_by_user_id = NULL,
        claimed_at         = NULL,
        reviewer_notes     = COALESCE(p_reviewer_notes, reviewer_notes)
    WHERE packet_id = p_packet_id
    RETURNING * INTO v_row;

    -- 6. Permanent decision-event record, full reason preserved, override
    -- metadata recorded distinctly (mirrors approve_intake_packet), acting
    -- user's role always recorded. Same rollback-on-failure guarantee as
    -- approve_intake_packet above.
    INSERT INTO operations.intake_packet_events (
        packet_id, event_type, actor_type, actor_id, reason, metadata
    ) VALUES (
        p_packet_id,
        'return',
        'user',
        p_actor_user_id::text,
        p_reason,
        jsonb_build_object('actor_role', v_actor_role, 'authority_basis', v_authority_basis) ||
        CASE WHEN v_is_override
             THEN jsonb_build_object('override', true, 'claimant_user_id', v_claimant)
             ELSE '{}'::jsonb
        END
    );

    -- 7.
    RETURN v_row;
END;
$$;

COMMENT ON FUNCTION operations.return_intake_packet(uuid, uuid, text, text) IS
    'Task #44 (corrected); Founder/CEO governance clarification 2026-07-16; '
    'authority_basis correction 2026-07-16. Single-transaction '
    'intake.review.return (CMD000006): ordinary return remains claimant-only; '
    'an Administrator override is permitted (added by the governance '
    'clarification — superseding the original claimant-only-no-override '
    'reading of DEC000001 §3) and requires a non-blank reason, logged '
    'distinctly. Validates in_review+claimant state, transitions status, '
    'clears claim fields, and writes the append-only decision event (with '
    'override metadata when applicable, and actor_role/authority_basis '
    'always — the raw DB role vs. the organizational authority basis it '
    'stands for) atomically. DEC000001 §3, §5.5, §5.9.';


-- ── Grants ────────────────────────────────────────────────────────────────
-- Matches the table-level GRANT convention used elsewhere for the
-- operations schema (e.g. 009_ai_usage_tracking.sql, 010_business_development.sql,
-- 011_submission_tables.sql): explicit, function-level grants to
-- service_role and authenticated rather than relying on default privileges.
GRANT EXECUTE ON FUNCTION operations.approve_intake_packet(uuid, uuid, text, text)
    TO service_role, authenticated;
GRANT EXECUTE ON FUNCTION operations.return_intake_packet(uuid, uuid, text, text)
    TO service_role, authenticated;
