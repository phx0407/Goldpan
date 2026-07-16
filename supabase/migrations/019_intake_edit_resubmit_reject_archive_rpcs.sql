-- ═══════════════════════════════════════════════════════════════════════════
-- 019_intake_edit_resubmit_reject_archive_rpcs.sql
--
-- Task #45 — implements the four remaining DEC000001 Intake Packet commands
-- as single-transaction RPCs, following the exact pattern established in
-- 017_intake_review_decision_rpcs.sql (task #44) and
-- 018_intake_claim_release_rpcs.sql (task #43): FOR UPDATE row lock,
-- authorization resolved by a direct operations.users lookup inside the
-- function (RPC is authoritative, not a client-supplied flag), a single
-- UPDATE plus a single INSERT into the relevant append-only table, RETURN
-- the row — one statement, one transaction, atomic by construction.
--
-- Commands implemented here, in the order Brad specified:
--   1. operations.edit_intake_packet_payload  (intake.packet.edit_payload, CMD000033)
--   2. operations.resubmit_intake_packet      (intake.packet.resubmit,     CMD000034)
--   3. operations.reject_intake_packet        (intake.packet.reject,       CMD000009)
--   4. operations.archive_intake_packet       (intake.packet.archive,      CMD000011)
--
-- Explicitly out of scope: intake.packet.commit_ingest (Task #46) and
-- intake.packet.reopen (CMD000010, reserved/undefined per DEC000001 §5.1 —
-- not to be built as a routine command).
--
-- Do not execute this migration against any database without review.
-- ═══════════════════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════════════════════
-- Governance judgment calls made in this migration (flagged for review, not
-- silently decided):
--
--   1. edit_payload / resubmit role scope: restricted to DB role 'canvasser'
--      (Intake Specialist) only — explicitly NOT 'admin'. The Founder/CEO
--      override clarification (DEC000001 §5.5, 2026-07-16) is scoped in its
--      own heading to "intake.review.return and intake.review.approve" —
--      it does not mention edit_payload or resubmit, and DEC000001 §4/§5.2/
--      §7 item 5 state the Intake Specialist restriction on payload
--      mutation as absolute ("Governance Reviewers ... may not mutate
--      packet_data under any circumstance"). No override path is
--      implemented for either command. A new authority_basis value,
--      'intake_specialist', is introduced for these two commands' audit
--      metadata (actor_role will always be 'canvasser' here — there is no
--      override branch to distinguish it from).
--
--   2. edit_payload's events-table entry: 'edit_payload' is not a valid
--      event_type in operations.intake_packet_events' CHECK-constrained
--      enum ('claim','release','return','resubmit','approve','reject',
--      'ingest','archive','supersede','annotate' — migration 016), and
--      DEC000001 §5.8 only explicitly requires the intake_packet_revisions
--      row for edit_payload, not an events-table row. Per Brad's explicit
--      step 6 ("Insert an annotate or precisely governed payload-edit event
--      ... consistent with DEC000001 and the existing event enum"), this
--      migration writes event_type='annotate' with
--      metadata.annotation_type='payload_edit' and metadata.revision_id
--      pointing at the intake_packet_revisions row just inserted, so the
--      two append-only records are cross-referenced.
--
--   3. [SUPERSEDED 2026-07-16 — Founder/CEO governance correction, see block
--      below] reject originally shipped claimant-only with no override.
--      Brad has since explicitly authorized a narrow Founder/CEO override
--      through the current 'admin' DB-role adapter. See the correction
--      block immediately following this list for the exact rule now
--      implemented.
--
--   4. [SUPERSEDED 2026-07-16 — Founder/CEO governance correction, see block
--      below] archive originally shipped with no role-specific gate at all
--      ("any active actor may archive"). Brad has since explicitly
--      restricted this to Governance Reviewer (rejected-only) and
--      Founder/CEO-via-admin-adapter (rejected or ingested). See the
--      correction block immediately following this list for the exact rule
--      now implemented.
--
--   5. Duplicate archival is explicitly prevented at the RPC level
--      (archived_at IS NOT NULL -> GP409). Migration 016's CHECK
--      constraints (archival eligibility, archival-actor-requires-
--      timestamp) do not by themselves prevent re-archiving an
--      already-archived packet, and no governing rule explicitly permits
--      duplicate archival, so this migration treats it as a conflict.
--
--   6. resubmit clears operations.intake_packets.return_reason (the one
--      column migration 015 adds that is specific to a `returned` packet)
--      and nothing else. reviewer_notes is left untouched — it is not
--      return-specific (approve also writes it) and Brad's instruction
--      ("Clears return-only fields where appropriate") is naturally read as
--      the field(s) that exist only in service of the returned state,
--      which is return_reason alone.
--
-- Still not executed against any database; still requires review before
-- migration or commit.
-- ═══════════════════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════════════════════
-- Founder/CEO governance correction (2026-07-16) — supersedes judgment calls
-- #3 and #4 above. This is a correction to already-drafted, never-executed
-- code; it is applied in place (CREATE OR REPLACE) rather than as a new
-- migration file, consistent with how 017/018 themselves accumulated
-- multiple clarification passes before ever being run.
--
-- IMPORTANT — scope of the 'admin' role going forward: the 'admin' DB role
-- is documented here, narrowly, as the CURRENT TECHNICAL IMPLEMENTATION
-- ADAPTER through which Founder/CEO authority is exercised, because Brad is
-- presently performing the company's operational roles himself. This is NOT
-- a standing grant of override/archive authority to every future System
-- Administrator. If and when Founder/CEO authority is separated from the
-- 'admin' DB role (e.g. a dedicated role or claim is introduced), these two
-- functions' role checks must be revisited — the authority described below
-- attaches to the Founder/CEO, not to the 'admin' role as such.
--
-- 1. reject (operations.reject_intake_packet):
--    - Ordinary rejection remains claimant-only, exactly as before.
--    - A NEW exceptional path is added: if the acting actor resolves to the
--      'admin' role AND is not the current claimant, the function now
--      permits the rejection as a Founder/CEO override instead of raising
--      GP403 — provided p_reason is non-blank (already required of every
--      caller; per the same precedent as return_intake_packet, no separate
--      override_reason parameter is added — p_reason doubles as the
--      override justification).
--    - Metadata now ALWAYS includes override (bool) and claimant_user_id
--      (the prior claimant's ID), regardless of whether this was an
--      ordinary or override rejection — mirroring release_intake_packet's
--      established pattern of never omitting these fields.
--    - authority_basis: 'governance_reviewer' + override=false for ordinary
--      claimant rejection; 'founder_ceo_override' + override=true for the
--      admin-adapter override path. actor_role is always the actor's real
--      DB role ('reviewer' or 'admin').
--    - A non-admin, non-claimant actor is still refused with GP403 — the
--      override path is admin-only, not open to any non-claimant reviewer.
--
-- 2. archive (operations.archive_intake_packet):
--    - The prior "any active actor may archive" gate is removed entirely.
--    - New rule: 'admin' (Founder/CEO adapter) may archive an eligible
--      'rejected' OR 'ingested' packet. 'reviewer' (Governance Reviewer) may
--      archive an eligible 'rejected' packet only — attempting to archive
--      an 'ingested' packet as a non-admin reviewer is refused with GP403.
--      Every other role (canvasser/Intake Specialist, coordinator, or no
--      active operations.users row at all) is refused with GP403 outright,
--      regardless of packet status.
--    - Because Governance Reviewer eligibility is itself status-dependent,
--      the role check is applied AFTER the generic
--      packet_status IN ('rejected','ingested') eligibility check (already
--      present), not before it.
--    - Metadata now records actor_role, authority_basis
--      ('governance_reviewer' or 'founder_ceo_override'), and the eligible
--      source packet_status at the moment of archival, alongside the
--      existing reason — per Brad's explicit "Preserve: actual actor_role,
--      authority_basis, eligible source status, archive reason."
--    - Duplicate-archival prevention (judgment call #5) and the
--      packet_status-untouched behavior are unchanged.
--    - Automated/policy-driven archival remains explicitly out of scope of
--      this RPC, unchanged.
-- ═══════════════════════════════════════════════════════════════════════════


-- ── operations.edit_intake_packet_payload ────────────────────────────────
--
-- Implements intake.packet.edit_payload (CMD000033) per DEC000001 §4, §5.2,
-- §7 item 5, §8:
--   1. Lock the packet row.
--   2. Verify the packet exists and is 'returned'.
--   3. Verify actor authority (Intake Specialist / 'canvasser' only — see
--      judgment call #1 above; Governance Reviewers are rejected here, not
--      merely un-granted).
--   4. Insert the CURRENT packet_data into intake_packet_revisions.
--      prior_payload before it is overwritten — this is the append-only
--      snapshot of what the payload was, keyed to the human actor making
--      the edit (intake_packet_revisions.actor_user_id is NOT NULL,
--      migration 016 — this table has no system-actor path).
--   5. Update intake_packets.packet_data to the new payload. packet_status
--      is never referenced in this UPDATE (DEC000001 §6: edit_payload is
--      not a state transition).
--   6. Insert an 'annotate' event cross-referencing the revision (judgment
--      call #2 above).
--   7. Return the updated packet.
--   8. Any RAISE aborts the whole function — the revision insert, the
--      packet_data UPDATE, and the event insert either all commit or none
--      do; a prior revision is never overwritten or deleted because this
--      function only ever INSERTs into intake_packet_revisions, and that
--      table's own append-only trigger (migration 016) would reject an
--      UPDATE/DELETE regardless.
CREATE OR REPLACE FUNCTION operations.edit_intake_packet_payload(
    p_packet_id     uuid,
    p_actor_user_id uuid,
    p_packet_data   jsonb,
    p_reason        text
)
RETURNS operations.intake_packets
LANGUAGE plpgsql
AS $$
DECLARE
    v_row         operations.intake_packets%ROWTYPE;
    v_actor_role  text;
    v_revision_id uuid;
BEGIN
    IF p_actor_user_id IS NULL THEN
        RAISE EXCEPTION 'p_actor_user_id is required'
            USING ERRCODE = 'GP422';
    END IF;

    IF p_packet_data IS NULL THEN
        RAISE EXCEPTION 'p_packet_data (replacement payload) is required'
            USING ERRCODE = 'GP422';
    END IF;

    IF p_reason IS NULL OR btrim(p_reason) = '' THEN
        RAISE EXCEPTION 'A non-blank reason is required to edit packet payload'
            USING ERRCODE = 'GP422';
    END IF;

    -- 3 (authorization gate, resolved before the packet lock so an
    -- unauthorized caller never even acquires FOR UPDATE on the row).
    -- Role-check duplication (same flagged technical debt as 017/018):
    -- queries operations.users.role directly rather than trusting a
    -- client-supplied flag. Update in lockstep with api/role_adapter.py's
    -- interim mapping if it ever changes.
    SELECT role INTO v_actor_role
    FROM operations.users
    WHERE user_id = p_actor_user_id
      AND is_active = true;

    IF v_actor_role IS DISTINCT FROM 'canvasser' THEN
        RAISE EXCEPTION 'Only an Intake Specialist may edit packet payload'
            USING ERRCODE = 'GP403';
    END IF;

    -- 1. Lock the row for the duration of this transaction.
    SELECT * INTO v_row
    FROM operations.intake_packets
    WHERE packet_id = p_packet_id
    FOR UPDATE;

    -- 2.
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Packet % not found', p_packet_id
            USING ERRCODE = 'GP404';
    END IF;

    IF v_row.packet_status <> 'returned' THEN
        RAISE EXCEPTION 'Packet % must be returned before its payload can be edited', p_packet_id
            USING ERRCODE = 'GP409';
    END IF;

    -- 4. Append-only snapshot of the payload as it stood before this edit.
    -- Never overwritten or deleted: this function only ever INSERTs here,
    -- and intake_packet_revisions carries its own append-only trigger
    -- (migration 016) as a second line of defense.
    INSERT INTO operations.intake_packet_revisions (
        packet_id, prior_payload, actor_user_id, reason
    ) VALUES (
        p_packet_id, v_row.packet_data, p_actor_user_id, p_reason
    )
    RETURNING revision_id INTO v_revision_id;

    -- 5. Replace the payload. packet_status is deliberately absent from
    -- this SET list — edit_payload never changes status (DEC000001 §6).
    UPDATE operations.intake_packets
    SET packet_data = p_packet_data
    WHERE packet_id = p_packet_id
    RETURNING * INTO v_row;

    -- 6. Payload-edit annotation event, cross-referencing the revision row
    -- above so the two append-only stores are linkable (judgment call #2).
    -- If this INSERT fails, the revision insert and the packet_data UPDATE
    -- above are rolled back with it.
    INSERT INTO operations.intake_packet_events (
        packet_id, event_type, actor_type, actor_id, reason, metadata
    ) VALUES (
        p_packet_id,
        'annotate',
        'user',
        p_actor_user_id::text,
        p_reason,
        jsonb_build_object(
            'actor_role', v_actor_role,
            'authority_basis', 'intake_specialist',
            'annotation_type', 'payload_edit',
            'revision_id', v_revision_id
        )
    );

    -- 7.
    RETURN v_row;
END;
$$;

COMMENT ON FUNCTION operations.edit_intake_packet_payload(uuid, uuid, jsonb, text) IS
    'Task #45. Single-transaction intake.packet.edit_payload (CMD000033): '
    'requires Intake Specialist (''canvasser'') authority, validates '
    'returned-only state, snapshots the prior payload into '
    'intake_packet_revisions (append-only, never overwritten), replaces '
    'packet_data, and writes a cross-referenced ''annotate'' event '
    '(annotation_type=payload_edit) atomically. Never changes packet_status. '
    'DEC000001 §4, §5.2, §5.8, §7 item 5, §8.';


-- ── operations.resubmit_intake_packet ────────────────────────────────────
--
-- Implements intake.packet.resubmit (CMD000034) per DEC000001 §5.1, §6:
--   1. Lock the packet row.
--   2. Verify the packet exists and is 'returned'.
--   3. Verify actor authority (Intake Specialist only, same gate as
--      edit_payload above; no override).
--   4. Transition returned -> pending_review. packet_data is never
--      referenced or written. return_reason is cleared (judgment call #6
--      above) since it is specific to the state being left.
--   5. Insert the resubmit event. reason is optional here (CMD000034:
--      reason_required: false) — the reason-required CHECK constraint on
--      intake_packet_events (migration 016) only applies to
--      event_type IN ('return','reject'), so a NULL reason on a 'resubmit'
--      row is valid.
--   6. Return the updated packet.
--   7. Any RAISE aborts the whole function; the status transition and the
--      event insert commit together or not at all.
CREATE OR REPLACE FUNCTION operations.resubmit_intake_packet(
    p_packet_id     uuid,
    p_actor_user_id uuid,
    p_reason        text DEFAULT NULL
)
RETURNS operations.intake_packets
LANGUAGE plpgsql
AS $$
DECLARE
    v_row        operations.intake_packets%ROWTYPE;
    v_actor_role text;
BEGIN
    IF p_actor_user_id IS NULL THEN
        RAISE EXCEPTION 'p_actor_user_id is required'
            USING ERRCODE = 'GP422';
    END IF;

    -- 3.
    SELECT role INTO v_actor_role
    FROM operations.users
    WHERE user_id = p_actor_user_id
      AND is_active = true;

    IF v_actor_role IS DISTINCT FROM 'canvasser' THEN
        RAISE EXCEPTION 'Only an Intake Specialist may resubmit a packet'
            USING ERRCODE = 'GP403';
    END IF;

    -- 1.
    SELECT * INTO v_row
    FROM operations.intake_packets
    WHERE packet_id = p_packet_id
    FOR UPDATE;

    -- 2.
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Packet % not found', p_packet_id
            USING ERRCODE = 'GP404';
    END IF;

    IF v_row.packet_status <> 'returned' THEN
        RAISE EXCEPTION 'Packet % must be returned before it can be resubmitted', p_packet_id
            USING ERRCODE = 'GP409';
    END IF;

    -- 4. packet_data intentionally absent from this SET list.
    UPDATE operations.intake_packets
    SET packet_status = 'pending_review',
        return_reason = NULL
    WHERE packet_id = p_packet_id
    RETURNING * INTO v_row;

    -- 5.
    INSERT INTO operations.intake_packet_events (
        packet_id, event_type, actor_type, actor_id, reason, metadata
    ) VALUES (
        p_packet_id,
        'resubmit',
        'user',
        p_actor_user_id::text,
        p_reason,
        jsonb_build_object('actor_role', v_actor_role, 'authority_basis', 'intake_specialist')
    );

    -- 6.
    RETURN v_row;
END;
$$;

COMMENT ON FUNCTION operations.resubmit_intake_packet(uuid, uuid, text) IS
    'Task #45. Single-transaction intake.packet.resubmit (CMD000034): '
    'requires Intake Specialist (''canvasser'') authority, validates '
    'returned-only state, transitions returned -> pending_review, clears '
    'return_reason, never touches packet_data, and writes the resubmit '
    'event (reason optional) atomically. DEC000001 §5.1, §6.';


-- ── operations.reject_intake_packet ──────────────────────────────────────
--
-- Implements intake.packet.reject (CMD000009) per DEC000001 §5.10, as
-- corrected 2026-07-16 (Founder/CEO governance correction, see block above):
--   1. Lock the packet row.
--   2. Verify the packet exists, is 'in_review', and is claimed.
--   3. Verify actor authority: current claimant (ordinary rejection), OR
--      the 'admin' role acting as a non-claimant (Founder/CEO override).
--      Any other non-claimant actor is refused with GP403.
--   4. Transition in_review -> rejected, clear claim fields. packet_data is
--      never referenced (rejected is a read-only state, DEC000001 §5.2 —
--      "makes payload immutable through status" is satisfied simply by
--      never writing packet_data here or in any other rejected-state
--      command).
--   5. Insert the mandatory-reason reject event (intake_packet_events'
--      reason-required CHECK, migration 016, enforces this a second time
--      at the DB layer regardless of the p_reason guard below). Metadata
--      always includes override and claimant_user_id.
--   6. Return the updated packet.
--   7. Any RAISE aborts the whole function.
CREATE OR REPLACE FUNCTION operations.reject_intake_packet(
    p_packet_id     uuid,
    p_actor_user_id uuid,
    p_reason        text
)
RETURNS operations.intake_packets
LANGUAGE plpgsql
AS $$
DECLARE
    v_row             operations.intake_packets%ROWTYPE;
    v_claimant        uuid;
    v_actor_role      text;
    v_authority_basis text;
    v_is_override     boolean;
BEGIN
    IF p_actor_user_id IS NULL THEN
        RAISE EXCEPTION 'p_actor_user_id is required'
            USING ERRCODE = 'GP422';
    END IF;

    IF p_reason IS NULL OR btrim(p_reason) = '' THEN
        RAISE EXCEPTION 'A non-blank reason is required to reject a packet'
            USING ERRCODE = 'GP422';
    END IF;

    -- 1.
    SELECT * INTO v_row
    FROM operations.intake_packets
    WHERE packet_id = p_packet_id
    FOR UPDATE;

    -- 2.
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Packet % not found', p_packet_id
            USING ERRCODE = 'GP404';
    END IF;

    v_claimant := v_row.claimed_by_user_id;
    IF v_row.packet_status <> 'in_review' OR v_claimant IS NULL THEN
        RAISE EXCEPTION 'Packet % must be in_review and claimed before it can be rejected', p_packet_id
            USING ERRCODE = 'GP409';
    END IF;

    SELECT role INTO v_actor_role
    FROM operations.users
    WHERE user_id = p_actor_user_id
      AND is_active = true;

    v_is_override := p_actor_user_id IS DISTINCT FROM v_claimant;

    -- 3. Ordinary rejection is claimant-only. A non-claimant may reject
    -- only through the 'admin' adapter (Founder/CEO override,
    -- 2026-07-16 governance correction) — every other non-claimant actor
    -- is refused.
    IF v_is_override AND v_actor_role IS DISTINCT FROM 'admin' THEN
        RAISE EXCEPTION 'Only the current claimant may reject packet %', p_packet_id
            USING ERRCODE = 'GP403';
    END IF;

    v_authority_basis := CASE WHEN v_is_override
                               THEN 'founder_ceo_override'
                               ELSE 'governance_reviewer'
                          END;

    -- 4. packet_data intentionally absent from this SET list.
    UPDATE operations.intake_packets
    SET packet_status      = 'rejected',
        reviewed_at        = now(),
        reviewed_by        = p_actor_user_id::text,
        claimed_by_user_id = NULL,
        claimed_at         = NULL
    WHERE packet_id = p_packet_id
    RETURNING * INTO v_row;

    -- 5. override and claimant_user_id are always present in metadata
    -- (never omitted), mirroring release_intake_packet's established
    -- pattern — this is a 2026-07-16 governance-correction requirement.
    INSERT INTO operations.intake_packet_events (
        packet_id, event_type, actor_type, actor_id, reason, metadata
    ) VALUES (
        p_packet_id,
        'reject',
        'user',
        p_actor_user_id::text,
        p_reason,
        jsonb_build_object(
            'actor_role', v_actor_role,
            'authority_basis', v_authority_basis,
            'override', v_is_override,
            'claimant_user_id', v_claimant
        )
    );

    -- 6.
    RETURN v_row;
END;
$$;

COMMENT ON FUNCTION operations.reject_intake_packet(uuid, uuid, text) IS
    'Task #45, corrected 2026-07-16 (Founder/CEO governance correction). '
    'Single-transaction intake.packet.reject (CMD000009): ordinary '
    'rejection is claimant-only (authority_basis=governance_reviewer, '
    'override=false); a non-claimant may reject only via the ''admin'' '
    'adapter (authority_basis=founder_ceo_override, override=true) — the '
    '''admin'' role here is the current technical adapter for Founder/CEO '
    'authority, not a standing grant to every future Administrator. '
    'Validates in_review+claimed state, requires a non-blank reason, '
    'transitions to rejected, clears claim fields, never touches '
    'packet_data, and writes the reject event (always recording override '
    'and claimant_user_id) atomically. DEC000001 §5.10.';


-- ── operations.archive_intake_packet ─────────────────────────────────────
--
-- Implements intake.packet.archive (CMD000011) per DEC000001 §5.11, §8, as
-- corrected 2026-07-16 (Founder/CEO governance correction, see block above):
--   1. Lock the packet row.
--   2. Verify the packet exists and is 'rejected' or 'ingested'.
--   3. Prevent duplicate archival (judgment call #5, unchanged).
--   4. Verify actor authority: 'admin' (Founder/CEO adapter) may archive
--      either eligible status; 'reviewer' (Governance Reviewer) may archive
--      'rejected' only (GP403 if attempting 'ingested'); every other role
--      (or no active operations.users row) is refused with GP403 outright.
--      This check runs after the status-eligibility check above because
--      Governance Reviewer eligibility is itself status-dependent.
--   5. Set archived_at / archived_by_user_id. packet_status is
--      DELIBERATELY absent from this SET list (Brad: "Does not change
--      packet_status").
--   6. Insert the archive event, preserving actor_role, authority_basis,
--      the eligible source status, and the reason.
--   7. Return the updated packet.
--   8. Any RAISE aborts the whole function.
CREATE OR REPLACE FUNCTION operations.archive_intake_packet(
    p_packet_id     uuid,
    p_actor_user_id uuid,
    p_reason        text
)
RETURNS operations.intake_packets
LANGUAGE plpgsql
AS $$
DECLARE
    v_row             operations.intake_packets%ROWTYPE;
    v_actor_role      text;
    v_authority_basis text;
    v_source_status   text;
BEGIN
    IF p_actor_user_id IS NULL THEN
        RAISE EXCEPTION 'p_actor_user_id is required'
            USING ERRCODE = 'GP422';
    END IF;

    IF p_reason IS NULL OR btrim(p_reason) = '' THEN
        RAISE EXCEPTION 'A non-blank reason is required to archive a packet'
            USING ERRCODE = 'GP422';
    END IF;

    -- 1.
    SELECT * INTO v_row
    FROM operations.intake_packets
    WHERE packet_id = p_packet_id
    FOR UPDATE;

    -- 2.
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Packet % not found', p_packet_id
            USING ERRCODE = 'GP404';
    END IF;

    IF v_row.packet_status NOT IN ('rejected', 'ingested') THEN
        RAISE EXCEPTION 'Packet % must be rejected or ingested before it can be archived', p_packet_id
            USING ERRCODE = 'GP409';
    END IF;

    v_source_status := v_row.packet_status;

    -- 3. Duplicate-archival guard (judgment call #5 — the migration-016
    -- CHECK constraints do not by themselves prevent this).
    IF v_row.archived_at IS NOT NULL THEN
        RAISE EXCEPTION 'Packet % is already archived', p_packet_id
            USING ERRCODE = 'GP409';
    END IF;

    -- 4. Role + status-dependent authorization (2026-07-16 governance
    -- correction, supersedes the prior "any active actor" gate). Applied
    -- after the status-eligibility check above since Governance Reviewer
    -- eligibility is itself status-dependent.
    SELECT role INTO v_actor_role
    FROM operations.users
    WHERE user_id = p_actor_user_id
      AND is_active = true;

    IF v_actor_role = 'admin' THEN
        -- Founder/CEO adapter: eligible for either rejected or ingested
        -- (already validated above).
        v_authority_basis := 'founder_ceo_override';
    ELSIF v_actor_role = 'reviewer' THEN
        IF v_source_status <> 'rejected' THEN
            RAISE EXCEPTION 'Only the Founder/CEO (admin adapter) may archive an ingested packet; a Governance Reviewer may only archive a rejected packet (%)', p_packet_id
                USING ERRCODE = 'GP403';
        END IF;
        v_authority_basis := 'governance_reviewer';
    ELSE
        RAISE EXCEPTION 'Actor % is not authorized to archive packets (Governance Reviewer or Founder/CEO admin adapter only)', p_actor_user_id
            USING ERRCODE = 'GP403';
    END IF;

    -- 5. packet_status intentionally absent from this SET list.
    UPDATE operations.intake_packets
    SET archived_at         = now(),
        archived_by_user_id = p_actor_user_id
    WHERE packet_id = p_packet_id
    RETURNING * INTO v_row;

    -- 6. actor_role, authority_basis, the eligible source status, and the
    -- reason are all preserved per Brad's explicit instruction.
    INSERT INTO operations.intake_packet_events (
        packet_id, event_type, actor_type, actor_id, reason, metadata
    ) VALUES (
        p_packet_id,
        'archive',
        'user',
        p_actor_user_id::text,
        p_reason,
        jsonb_build_object(
            'actor_role', v_actor_role,
            'authority_basis', v_authority_basis,
            'source_status', v_source_status
        )
    );

    -- 7.
    RETURN v_row;
END;
$$;

COMMENT ON FUNCTION operations.archive_intake_packet(uuid, uuid, text) IS
    'Task #45, corrected 2026-07-16 (Founder/CEO governance correction). '
    'Single-transaction intake.packet.archive (CMD000011): a Governance '
    'Reviewer (''reviewer'') may archive an eligible rejected packet only; '
    'the Founder/CEO via the ''admin'' adapter may archive an eligible '
    'rejected or ingested packet — the ''admin'' role here is the current '
    'technical adapter for Founder/CEO authority, not a standing grant to '
    'every future Administrator. Intake Specialists and all other actors '
    'are refused. Requires a non-blank reason, validates rejected/'
    'ingested-only state, prevents duplicate archival, sets archived_at/'
    'archived_by_user_id without changing packet_status, and writes the '
    'archive event (preserving actor_role, authority_basis, and source '
    'status) atomically. Automated/policy-driven archival remains out of '
    'scope. DEC000001 §5.11, §8.';


-- ── Grants ────────────────────────────────────────────────────────────────
GRANT EXECUTE ON FUNCTION operations.edit_intake_packet_payload(uuid, uuid, jsonb, text)
    TO service_role, authenticated;
GRANT EXECUTE ON FUNCTION operations.resubmit_intake_packet(uuid, uuid, text)
    TO service_role, authenticated;
GRANT EXECUTE ON FUNCTION operations.reject_intake_packet(uuid, uuid, text)
    TO service_role, authenticated;
GRANT EXECUTE ON FUNCTION operations.archive_intake_packet(uuid, uuid, text)
    TO service_role, authenticated;
