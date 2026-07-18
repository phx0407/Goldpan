-- ============================================================
-- 021_submission_state_machine.sql
-- Restaurant Operations OS — implements the DEC000002 canonical
-- Restaurant Update Submission state machine (v4.2 narrow
-- consistency correction, final draft — ready for Founder approval)
-- against the live schema introduced in 011_submission_tables.sql.
--
-- Scope of this migration (schema only — see
-- docs/decisions/DEC000002_IMPLEMENTATION_GAP_MAP.md §1-§2):
--   1. Add claim fields (§5.6), DB-enforced claim/status consistency.
--   2. Add resubmission-chain fields (§5.7-§5.8): immutable parent/
--      child linkage, single-hop enforcement both directions,
--      self-reference exclusion, DB-enforced post-creation
--      immutability (stronger than the DEC000001 precedent — §5.8
--      names this as a structural guarantee, not merely "system-
--      derived only").
--   3. Add archival fields (§5.9), DB-enforced eligibility that
--      depends on status AND disposition_status/supersession state
--      (more conditional than DEC000001's archival, which only
--      depended on packet_status).
--   4. Add resolution_summary (§5.4, §5.11), DB-enforced mandatory
--      when disposition_type = no_action.
--   5. Add the disposition model — disposition_type, disposition_
--      status, failure_stage (§5.3, §5.4, §6) — with DB-enforced
--      enum membership and type/status/failure_stage consistency.
--   6. Resolve downstream linkage (§5.11): rename the legacy free-
--      text resulting_intake_session placeholder to
--      resulting_intake_session_id (non-canonical, no FK, no
--      confirmed target); add resulting_intake_packet_id (canonical
--      FK -> operations.intake_packets, ON DELETE RESTRICT per the
--      same provenance principle applied to migration 020's
--      source_packet_id — packets are permanent audit records,
--      hard-deleting one referenced by a submission must fail, not
--      silently sever the link); add identity_review_item_id and
--      exception_request_id as unconstrained nullable placeholders
--      (no target table exists for either yet — see judgment call 2
--      below and the gap map §3).
--   7. Create operations.restaurant_update_submission_events (§5.10),
--      append-only, with actor_type/actor_id AND initiating_actor_
--      type/initiating_actor_id (executing vs. requesting actor),
--      downstream_caller_id, and prior/resulting status +
--      disposition_status columns.
--
-- Explicitly OUT of scope for this migration (belongs to the
-- subsequent RPC/API/service pass, or is blocked on architecture
-- that doesn't exist yet — see 022_submission_review_rpcs.sql and
-- the gap map §3, §5):
--   - submission.route_to_identity_review / submission.
--     escalate_exception RPCs — blocked; no Identity Review Queue or
--     Governance exception-request table exists anywhere in this
--     schema to route to (DEC000002 §5.11 confirms this itself).
--   - Any application-layer role/permission enforcement, request
--     handling, or UI.
--
-- Identity source (resolved, not invented — same resolution as
-- DEC000001_IMPLEMENTATION_GAP_MAP.md §0, carried over per gap map
-- §0 here): *_user_id columns below reference operations.users
-- (user_id), the existing Supabase-Auth-mirrored identity table
-- (migration 004). No new identity model is introduced.
--
-- Governance judgment calls made in this migration (flagged for
-- review, not silently decided — per Brad's explicit direction on
-- the two items below, plus one newly discovered item found while
-- drafting this migration that the original gap map did not catch):
--
--   1. Downstream entity reference on the events table (§5.10's
--      "downstream entity reference, where applicable" line) is
--      stored in metadata jsonb, NOT as four more mirrored nullable
--      FK-shaped columns on the events table — per Brad's explicit
--      instruction. Structured shape, applied consistently by every
--      RPC that writes it (022_submission_review_rpcs.sql):
--        {
--          "downstream_entity_type": "intake_packet" |
--                                     "identity_review_item" |
--                                     "exception_request",
--          "downstream_entity_id":   "<uuid as text>",
--          "routing_command":        "submission.convert_to_intake" |
--                                     "submission.route_to_identity_review" |
--                                     "submission.escalate_exception"
--        }
--      merged with whatever other event-specific keys that RPC
--      already writes (actor_role, authority_basis, etc.). This
--      keeps referential integrity where it belongs (the submission
--      row's own real FK columns, added in this migration) while
--      keeping the audit log's shape simple and migratable — if a
--      canonical downstream-link table is ever introduced, this
--      metadata shape maps onto it directly (entity_type, entity_id,
--      command) with no lossy translation.
--
--   2. identity_review_item_id and exception_request_id are added as
--      plain nullable uuid columns with NO foreign-key constraint,
--      per Brad's explicit instruction not to invent missing target
--      tables. Neither table exists anywhere in migrations 001-020.
--      submission.route_to_identity_review and submission.
--      escalate_exception are correspondingly NOT implemented as
--      RPCs in 022_submission_review_rpcs.sql — marked blocked
--      pending that downstream architecture, per the gap map §3.
--
--   3. NEWLY DISCOVERED while drafting (not caught by the original
--      gap map — flagging now rather than silently working around
--      it): DEC000002 §5.8's same-restaurant-identity rule for
--      resubmission ("same restaurant_id, or same
--      restaurant_external_id if restaurant_id is null on either")
--      cannot be fully implemented as written. operations.
--      restaurant_update_submissions (migration 011) has no
--      restaurant_external_id column at all — only restaurant_id.
--      There is nothing on this table to fall back to. This
--      migration implements the restaurant_id-only half of the
--      rule via a trigger (below) and requires restaurant_id to be
--      non-null and equal on both parent and child — stricter than
--      DEC000002's OR-fallback (fails loud instead of silently
--      allowing an unverifiable identity match). If a submission's
--      restaurant_id is ever null, resubmission against it is
--      refused by this trigger rather than falling through to an
--      identity check this table has no column to perform. Adding a
--      restaurant_external_id column to this table, if the fallback
--      is actually needed operationally, is a follow-up decision,
--      not made here.
-- ============================================================


-- ── 1. Claim fields (§5.6) + DB-enforced claim/status consistency ─────────
-- Stable user ID only, no display-name snapshot (§5.1). The atomic claim
-- UPDATE ... WHERE ... RETURNING pattern is an RPC-layer concern (see
-- 022_submission_review_rpcs.sql), not expressible as a schema constraint.
-- DB-enforced here: claim fields are both-set if and only if status is
-- in_review — never one without the other, never present outside in_review.

ALTER TABLE operations.restaurant_update_submissions
    ADD COLUMN IF NOT EXISTS claimed_by_user_id  uuid REFERENCES operations.users(user_id),
    ADD COLUMN IF NOT EXISTS claimed_at           timestamptz;

COMMENT ON COLUMN operations.restaurant_update_submissions.claimed_by_user_id IS
    'Restaurant Operations coordinator who currently holds this submission in_review '
    '(DEC000002 §5.6). Cleared atomically by release/return/approve/reject — describes '
    'who currently has the submission checked out, not who last decided it (that lives '
    'permanently in operations.restaurant_update_submission_events). DB-enforced: set if '
    'and only if status = in_review (see rusub_claim_consistency below); the atomic claim '
    'UPDATE pattern itself is an RPC-layer responsibility.';
COMMENT ON COLUMN operations.restaurant_update_submissions.claimed_at IS
    'Set atomically with claimed_by_user_id by claim_restaurant_update_submission. '
    'DB-enforced alongside claimed_by_user_id — see rusub_claim_consistency.';

ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_claim_consistency;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_claim_consistency
    CHECK (
        (status = 'in_review'
            AND claimed_by_user_id IS NOT NULL
            AND claimed_at IS NOT NULL)
        OR
        (status != 'in_review'
            AND claimed_by_user_id IS NULL
            AND claimed_at IS NULL)
    );

COMMENT ON CONSTRAINT rusub_claim_consistency ON operations.restaurant_update_submissions IS
    'DEC000002 §5.6: in_review requires both claim fields set; every other status requires '
    'both null. Decision commands (return/approve/reject) must clear both claim fields in '
    'the same transaction that moves status out of in_review, or this constraint rejects '
    'the write.';


-- ── 2. Resubmission chain (§5.7-§5.8) — immutable, single-hop, cycle-free ──
-- by construction. Same restaurant_id or restaurant_external_id: implemented
-- restaurant_id-only via trigger (below) — see judgment call 3 above.

ALTER TABLE operations.restaurant_update_submissions
    ADD COLUMN IF NOT EXISTS resubmission_of_submission_id uuid
        REFERENCES operations.restaurant_update_submissions(submission_id),
    ADD COLUMN IF NOT EXISTS superseded_by_submission_id   uuid
        REFERENCES operations.restaurant_update_submissions(submission_id);

ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_no_self_resubmission;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_no_self_resubmission
    CHECK (resubmission_of_submission_id IS NULL OR resubmission_of_submission_id != submission_id);

ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_no_self_supersede;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_no_self_supersede
    CHECK (superseded_by_submission_id IS NULL OR superseded_by_submission_id != submission_id);

-- Each parent has at most one direct child (§5.7-§5.8) — unique on the
-- child-side column that names the parent.
CREATE UNIQUE INDEX IF NOT EXISTS idx_rusub_resubmission_of_unique
    ON operations.restaurant_update_submissions(resubmission_of_submission_id)
    WHERE resubmission_of_submission_id IS NOT NULL;

-- Each child is claimed as a successor by at most one parent — defensive
-- symmetry, preventing a stray manual UPDATE from pointing two parents'
-- superseded_by_submission_id at the same child (not itself named in
-- §5.8's bullet list, but implied by "each child has at most one parent"
-- read the other direction; cheap to enforce, so enforced).
CREATE UNIQUE INDEX IF NOT EXISTS idx_rusub_superseded_by_unique
    ON operations.restaurant_update_submissions(superseded_by_submission_id)
    WHERE superseded_by_submission_id IS NOT NULL;

COMMENT ON COLUMN operations.restaurant_update_submissions.resubmission_of_submission_id IS
    'Set once, atomically, by resubmit_restaurant_update_submission (§5.7) — the parent '
    'this row corrects. Immutable after the child-creation transaction (§5.8 rule 2), '
    'enforced by trg_rusub_prevent_chain_rewrite below, not merely by convention.';
COMMENT ON COLUMN operations.restaurant_update_submissions.superseded_by_submission_id IS
    'Set once, atomically, by resubmit_restaurant_update_submission (§5.7) — the child that '
    'replaces this row. Immutable after that transaction (§5.8 rule 2), enforced by '
    'trg_rusub_prevent_chain_rewrite below. A returned row with this set is a permanently '
    'closed leaf (§5.7 — "parent remains returned, it never moves again"); §5.9 archival '
    'eligibility keys off this column being non-null.';

-- §5.8 rule 2: "resubmission_of_submission_id (on the child) and
-- superseded_by_submission_id (on the parent) are immutable once written by
-- the child-creation transaction — no command, routine or administrative,
-- may later change either value on an existing row." This is DB-enforced
-- here via a trigger, not left as an unenforced structural claim (stronger
-- than the DEC000001 precedent for superseded_by_packet_id, which relies on
-- "no routine command sets this" rather than a trigger — DEC000002 §5.8
-- names immutability itself, not just "system-derived only," as the
-- guarantee, so it is enforced structurally here).
CREATE OR REPLACE FUNCTION operations.prevent_rusub_chain_rewrite()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.resubmission_of_submission_id IS NOT NULL
       AND NEW.resubmission_of_submission_id IS DISTINCT FROM OLD.resubmission_of_submission_id THEN
        RAISE EXCEPTION
            'operations.restaurant_update_submissions.resubmission_of_submission_id is '
            'immutable once set (DEC000002 §5.8 rule 2). Row %.', OLD.submission_id;
    END IF;

    IF OLD.superseded_by_submission_id IS NOT NULL
       AND NEW.superseded_by_submission_id IS DISTINCT FROM OLD.superseded_by_submission_id THEN
        RAISE EXCEPTION
            'operations.restaurant_update_submissions.superseded_by_submission_id is '
            'immutable once set (DEC000002 §5.8 rule 2). Row %.', OLD.submission_id;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_rusub_prevent_chain_rewrite ON operations.restaurant_update_submissions;
CREATE TRIGGER trg_rusub_prevent_chain_rewrite
    BEFORE UPDATE ON operations.restaurant_update_submissions
    FOR EACH ROW EXECUTE FUNCTION operations.prevent_rusub_chain_rewrite();

-- Same-restaurant-identity rule (§5.8), restaurant_id-only per judgment
-- call 3 above. Fires only when a row is being inserted as a resubmission
-- child (resubmission_of_submission_id IS NOT NULL) — an ordinary top-level
-- submission is untouched by this check.
CREATE OR REPLACE FUNCTION operations.validate_rusub_resubmission_identity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_parent_restaurant_id uuid;
BEGIN
    IF NEW.resubmission_of_submission_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT restaurant_id INTO v_parent_restaurant_id
    FROM operations.restaurant_update_submissions
    WHERE submission_id = NEW.resubmission_of_submission_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'resubmission_of_submission_id (%) does not reference an existing submission.',
            NEW.resubmission_of_submission_id;
    END IF;

    IF NEW.restaurant_id IS NULL OR v_parent_restaurant_id IS NULL THEN
        RAISE EXCEPTION
            'Cannot verify same-restaurant identity for a resubmission (DEC000002 §5.8): '
            'both parent and child restaurant_id must be set. This table has no '
            'restaurant_external_id fallback column (see migration 021 header, judgment '
            'call 3) — resolve the missing restaurant_id before resubmitting.';
    END IF;

    IF NEW.restaurant_id != v_parent_restaurant_id THEN
        RAISE EXCEPTION
            'Resubmission child restaurant_id (%) does not match parent restaurant_id (%) '
            '— DEC000002 §5.8 requires the same canonical restaurant identity.',
            NEW.restaurant_id, v_parent_restaurant_id;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_rusub_validate_resubmission_identity ON operations.restaurant_update_submissions;
CREATE TRIGGER trg_rusub_validate_resubmission_identity
    BEFORE INSERT ON operations.restaurant_update_submissions
    FOR EACH ROW EXECUTE FUNCTION operations.validate_rusub_resubmission_identity();


-- ── 3. Archival (§5.9) — eligibility depends on status AND disposition/ ───
-- supersession state, unlike DEC000001's status-only eligibility. Still
-- single-row, still a plain CHECK (no cross-row lookup needed — every input
-- to the eligibility rule lives on the row itself).

ALTER TABLE operations.restaurant_update_submissions
    ADD COLUMN IF NOT EXISTS archived_at          timestamptz,
    ADD COLUMN IF NOT EXISTS archived_by_user_id   uuid REFERENCES operations.users(user_id),
    ADD COLUMN IF NOT EXISTS archive_reason        text;

ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_archival_eligibility;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_archival_eligibility
    CHECK (
        archived_at IS NULL
        OR status = 'rejected'
        OR (status = 'approved' AND disposition_status = 'completed')
        OR (status = 'returned' AND superseded_by_submission_id IS NOT NULL)
    );

ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_archival_actor_requires_timestamp;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_archival_actor_requires_timestamp
    CHECK (archived_by_user_id IS NULL OR archived_at IS NOT NULL);

-- §5.9: "Requires an actor ... and archive_reason for any manual archival."
-- No automatic archival schedule is approved by this decision, so every
-- archival today is manual — but this is phrased as "an actor implies a
-- reason," the same one-way pattern as DEC000001's archival-actor-requires-
-- timestamp, so a hypothetical future system-initiated archival (archived_at
-- set, no actor, no reason) is not structurally foreclosed by this migration
-- even though none is approved today.
ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_archival_actor_requires_reason;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_archival_actor_requires_reason
    CHECK (archived_by_user_id IS NULL OR (archive_reason IS NOT NULL AND archive_reason ~ '\S'));

COMMENT ON COLUMN operations.restaurant_update_submissions.archived_at IS
    'Non-status attribute (§5.9). DB-enforced eligibility (rusub_archival_eligibility): '
    'rejected; approved with disposition_status = completed; or returned with a linked '
    'child (superseded_by_submission_id IS NOT NULL). Never removes the record, only '
    'removes it from default operational views (§5.9).';
COMMENT ON COLUMN operations.restaurant_update_submissions.archived_by_user_id IS
    'Set for manual archival (the only kind currently approved, §5.9). DB-enforced: an '
    'actor cannot be recorded without archived_at and archive_reason also being set.';
COMMENT ON COLUMN operations.restaurant_update_submissions.archive_reason IS
    'Mandatory for any manual archival (§5.9) — DB-enforced via '
    'rusub_archival_actor_requires_reason whenever archived_by_user_id is set.';


-- ── 4. Disposition model (§5.3, §5.4, §6) ──────────────────────────────────

ALTER TABLE operations.restaurant_update_submissions
    ADD COLUMN IF NOT EXISTS disposition_type   text,
    ADD COLUMN IF NOT EXISTS disposition_status text NOT NULL DEFAULT 'unassessed',
    ADD COLUMN IF NOT EXISTS failure_stage      text,
    ADD COLUMN IF NOT EXISTS resolution_summary text;

ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_disposition_type_check;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_disposition_type_check
    CHECK (disposition_type IS NULL OR disposition_type IN (
        'intake_required', 'identity_review', 'no_action', 'exception_escalation'
    ));

ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_disposition_status_check;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_disposition_status_check
    CHECK (disposition_status IN ('unassessed', 'pending', 'in_progress', 'completed', 'failed'));

ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_failure_stage_check;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_failure_stage_check
    CHECK (failure_stage IS NULL OR failure_stage IN ('handoff_call', 'local_write', 'downstream_terminal'));

-- §5.3: failure_stage is "a sub-classification of failed" — never set
-- unless disposition_status = failed.
ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_failure_stage_requires_failed;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_failure_stage_requires_failed
    CHECK (failure_stage IS NULL OR disposition_status = 'failed');

-- §5.4: "No approved submission may remain disposition_status = unassessed
-- — the atomicity of step 4 with steps 1-3 guarantees this structurally,
-- not just by convention." DB-enforced here as the structural half of that
-- guarantee: disposition_type and disposition_status = unassessed are set
-- or cleared together, never independently.
ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_disposition_type_status_consistency;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_disposition_type_status_consistency
    CHECK (
        (disposition_type IS NULL AND disposition_status = 'unassessed')
        OR
        (disposition_type IS NOT NULL AND disposition_status != 'unassessed')
    );

-- §5.4: "no_action requires resolution_summary as a mandatory, not merely
-- recommended, parameter" — the one case where this decision makes the
-- field decision-blocking. DB-enforced as defense-in-depth alongside the
-- RPC-layer check in 022_submission_review_rpcs.sql.
ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_no_action_requires_resolution_summary;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_no_action_requires_resolution_summary
    CHECK (
        disposition_type IS DISTINCT FROM 'no_action'
        OR (resolution_summary IS NOT NULL AND resolution_summary ~ '\S')
    );

COMMENT ON COLUMN operations.restaurant_update_submissions.disposition_type IS
    'Set once, atomically, by approve_restaurant_update_submission (§5.4). One of '
    'intake_required, identity_review, no_action, exception_escalation. Null only while '
    'disposition_status = unassessed (rusub_disposition_type_status_consistency).';
COMMENT ON COLUMN operations.restaurant_update_submissions.disposition_status IS
    'unassessed (pre-approval default) -> pending (disposition selected, no handoff yet) '
    '-> in_progress (downstream record created, owning OS has not yet reported a terminal '
    'outcome) -> completed | failed. §5.3: a submission does not reach completed merely '
    'because a downstream record was created — only the owning OS''s own terminal signal, '
    'or no_action''s immediate completion at approval, may set completed.';
COMMENT ON COLUMN operations.restaurant_update_submissions.failure_stage IS
    'Sub-classification of disposition_status = failed (§5.3): handoff_call (the routing '
    'command''s call to the downstream owning OS never succeeded — safely retryable), '
    'local_write (downstream call succeeded, this row''s own linkage write failed — a '
    'downstream object may already exist), or downstream_terminal (the downstream owning '
    'OS itself later reported a terminal failure). DB-enforced: never set unless '
    'disposition_status = failed.';
COMMENT ON COLUMN operations.restaurant_update_submissions.resolution_summary IS
    'Structured/human-readable disposition note (§5.11), populated regardless of which '
    'downstream link field is used. Mandatory and DB-enforced non-blank when '
    'disposition_type = no_action (§5.4) — the only record that disposition will ever '
    'produce, since no_action reaches disposition_status = completed immediately with no '
    'downstream workflow to later explain why.';


-- ── 5. Downstream linkage (§5.11) — resolved canonical target, explicit ───
-- nullable FKs, conditional cardinality.

-- 5a. Rename the legacy free-text placeholder to its DEC000002 name and
-- retype it as an unconstrained uuid — non-canonical, no confirmed target
-- (§5.11), excluded from the cardinality rule below. Fail-loud precondition
-- (matching migration 016's convention): abort rather than silently drop
-- data if any existing value isn't UUID-shaped.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'operations'
          AND table_name = 'restaurant_update_submissions'
          AND column_name = 'resulting_intake_session'
    ) THEN
        ALTER TABLE operations.restaurant_update_submissions
            RENAME COLUMN resulting_intake_session TO resulting_intake_session_id;
    END IF;
END $$;

DO $$
DECLARE
    v_bad_count int;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'operations'
          AND table_name = 'restaurant_update_submissions'
          AND column_name = 'resulting_intake_session_id'
          AND data_type = 'text'
    ) THEN
        SELECT count(*) INTO v_bad_count
        FROM operations.restaurant_update_submissions
        WHERE resulting_intake_session_id IS NOT NULL
          AND resulting_intake_session_id !~
              '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$';

        IF v_bad_count > 0 THEN
            RAISE EXCEPTION
                'Migration precondition failed: % row(s) in operations.'
                'restaurant_update_submissions.resulting_intake_session_id contain '
                'non-UUID-shaped legacy text values that cannot be cast to uuid. Resolve '
                'manually before retrying — this migration will not silently truncate or '
                'null out existing data.', v_bad_count;
        END IF;

        ALTER TABLE operations.restaurant_update_submissions
            ALTER COLUMN resulting_intake_session_id TYPE uuid
            USING resulting_intake_session_id::uuid;
    END IF;
END $$;

COMMENT ON COLUMN operations.restaurant_update_submissions.resulting_intake_session_id IS
    'Non-canonical, optional secondary technical reference (§5.11) — the packet-vs-session '
    'handoff-target question is resolved in favor of resulting_intake_packet_id below; this '
    'column has no confirmed target entity, carries no FK constraint, is left null unless a '
    'future decision defines a real intake-session entity, and is explicitly excluded from '
    'the downstream-FK-cardinality rule (rusub_downstream_fk_cardinality below).';

-- 5b. resulting_intake_packet_id — canonical, ready to build (§5.11).
-- ON DELETE RESTRICT: same provenance principle applied to migration 020's
-- source_packet_id — Intake Packets are permanent audit records and should
-- be archived rather than hard-deleted; a submission's canonical evidence
-- of what it was routed to must remain traceable. If a packet referenced
-- here is hard-deleted, that must fail loudly, not silently sever the link.
ALTER TABLE operations.restaurant_update_submissions
    ADD COLUMN IF NOT EXISTS resulting_intake_packet_id uuid
        REFERENCES operations.intake_packets(packet_id) ON DELETE RESTRICT;

COMMENT ON COLUMN operations.restaurant_update_submissions.resulting_intake_packet_id IS
    'Canonical downstream FK for disposition_type = intake_required (§5.11). '
    'ON DELETE RESTRICT: Intake Packets are permanent audit records; hard-deleting a '
    'referenced packet must fail, not silently sever this submission''s provenance link — '
    'same principle as evidence.restaurant_source_inventory.source_packet_id (migration '
    '020). Set only by submission_convert_to_intake, once, per '
    '022_submission_review_rpcs.sql.';

-- 5c. identity_review_item_id, exception_request_id — placeholders only,
-- no FK (judgment call 2 above). Neither target table exists yet.
ALTER TABLE operations.restaurant_update_submissions
    ADD COLUMN IF NOT EXISTS identity_review_item_id uuid,
    ADD COLUMN IF NOT EXISTS exception_request_id    uuid;

COMMENT ON COLUMN operations.restaurant_update_submissions.identity_review_item_id IS
    'Canonical nullable reference for disposition_type = identity_review (§5.11). '
    'Deliberately UNCONSTRAINED — no Identity Review Queue table exists anywhere in this '
    'schema yet (Blueprint-defined, not yet implemented). submission.route_to_identity_'
    'review is correspondingly NOT built in 022_submission_review_rpcs.sql; this column is '
    'a placeholder only, per DEC000002 §5.11 and the implementation gap map §3.';
COMMENT ON COLUMN operations.restaurant_update_submissions.exception_request_id IS
    'Canonical nullable reference for disposition_type = exception_escalation (§5.11). '
    'Deliberately UNCONSTRAINED — no Governance OS exception-request table exists anywhere '
    'in this schema yet. submission.escalate_exception is correspondingly NOT built in '
    '022_submission_review_rpcs.sql; this column is a placeholder only, per DEC000002 §5.11 '
    'and the implementation gap map §3.';

-- 5d. Cardinality (§5.11): at most one canonical downstream FK populated at
-- once; resulting_intake_session_id is non-canonical and excluded.
ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_downstream_fk_cardinality;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_downstream_fk_cardinality
    CHECK (
        (CASE WHEN resulting_intake_packet_id IS NOT NULL THEN 1 ELSE 0 END
         + CASE WHEN identity_review_item_id IS NOT NULL THEN 1 ELSE 0 END
         + CASE WHEN exception_request_id    IS NOT NULL THEN 1 ELSE 0 END) <= 1
    );

-- Each canonical FK may only be populated when it matches the row's own
-- selected disposition_type — a same-row structural guardrail, distinct
-- from (and narrower than) the timing rule (which FK, if any, is populated
-- at a given disposition_status) that 022's RPCs enforce.
ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_intake_packet_fk_requires_type;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_intake_packet_fk_requires_type
    CHECK (resulting_intake_packet_id IS NULL OR disposition_type = 'intake_required');

ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_identity_review_fk_requires_type;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_identity_review_fk_requires_type
    CHECK (identity_review_item_id IS NULL OR disposition_type = 'identity_review');

ALTER TABLE operations.restaurant_update_submissions
    DROP CONSTRAINT IF EXISTS rusub_exception_request_fk_requires_type;
ALTER TABLE operations.restaurant_update_submissions
    ADD CONSTRAINT rusub_exception_request_fk_requires_type
    CHECK (exception_request_id IS NULL OR disposition_type = 'exception_escalation');


-- ── 6. Indexes supporting the new lifecycle ────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_rusub_claimed_by
    ON operations.restaurant_update_submissions(claimed_by_user_id)
    WHERE claimed_by_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_rusub_archived_at
    ON operations.restaurant_update_submissions(archived_at)
    WHERE archived_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_rusub_disposition_status
    ON operations.restaurant_update_submissions(disposition_status, status);

CREATE INDEX IF NOT EXISTS idx_rusub_resulting_intake_packet
    ON operations.restaurant_update_submissions(resulting_intake_packet_id)
    WHERE resulting_intake_packet_id IS NOT NULL;


-- ============================================================
-- ── operations.restaurant_update_submission_events (§5.10) ────────────────
-- Append-only lifecycle/claim/disposition/handoff audit trail. Reuses
-- operations.prevent_append_only_mutation() (defined generically in
-- 016_intake_packet_state_machine.sql, keyed off TG_TABLE_SCHEMA/
-- TG_TABLE_NAME — no redefinition needed here).
--
-- actor_type/actor_id (executing actor) plus initiating_actor_type/
-- initiating_actor_id (requesting actor, when distinct) plus
-- downstream_caller_id (the downstream owning OS's own callback identity,
-- downstream_completion_received only) — corrected in DEC000002 v4.2 §5.10
-- to distinguish "who requested this" from "what executed it," rather than
-- collapsing a human-initiated handoff into actor_type = system alone.
-- ============================================================

CREATE TABLE IF NOT EXISTS operations.restaurant_update_submission_events (
    event_id                      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id                 uuid        NOT NULL
                                   REFERENCES operations.restaurant_update_submissions(submission_id),
    event_type                    text        NOT NULL,
    actor_type                    text        NOT NULL,
    actor_id                      text        NOT NULL,
    initiating_actor_type         text,
    initiating_actor_id           text,
    downstream_caller_id          text,
    prior_status                  text,
    resulting_status               text,
    prior_disposition_status      text,
    resulting_disposition_status  text,
    failure_stage                 text,
    reason                        text,
    metadata                      jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at                    timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT rusub_events_event_type_check
        CHECK (event_type IN (
            'claim', 'release', 'return', 'resubmit', 'approve', 'reject',
            'disposition_selected', 'disposition_handoff_attempted',
            'disposition_handoff_succeeded', 'disposition_handoff_failed',
            'downstream_completion_received', 'archive'
        )),
    CONSTRAINT rusub_events_actor_type_check
        CHECK (actor_type IN ('user', 'system', 'pipeline')),
    CONSTRAINT rusub_events_initiating_actor_type_check
        CHECK (initiating_actor_type IS NULL OR initiating_actor_type IN ('user', 'system', 'pipeline')),
    CONSTRAINT rusub_events_actor_id_nonblank
        CHECK (actor_id ~ '\S'),
    CONSTRAINT rusub_events_initiating_actor_id_nonblank
        CHECK (initiating_actor_id IS NULL OR initiating_actor_id ~ '\S'),

    -- §5.10: reason mandatory+non-blank for return, reject, and manual
    -- archive. (Administrative release-override reason requirement is not
    -- structurally distinguishable here without a dedicated override flag —
    -- same caveat as DEC000001's intake_packet_events — so it stays an
    -- RPC-layer guardrail, not a CHECK.)
    CONSTRAINT rusub_events_reason_required
        CHECK (event_type NOT IN ('return', 'reject', 'archive')
               OR (reason IS NOT NULL AND reason ~ '\S')),

    CONSTRAINT rusub_events_failure_stage_check
        CHECK (failure_stage IS NULL OR failure_stage IN ('handoff_call', 'local_write', 'downstream_terminal')),
    -- §5.3: failure_stage is set only on disposition_handoff_failed or a
    -- failure-carrying downstream_completion_received.
    CONSTRAINT rusub_events_failure_stage_scope
        CHECK (failure_stage IS NULL
               OR event_type IN ('disposition_handoff_failed', 'downstream_completion_received'))
);

COMMENT ON TABLE operations.restaurant_update_submission_events IS
    'Append-only lifecycle/claim/disposition/handoff audit trail (DEC000002 §5.10). '
    'actor_type/actor_id record the executing actor; initiating_actor_type/'
    'initiating_actor_id record the requesting actor when distinct (e.g. a human-invoked '
    'routing handoff executed by actor_type=system); downstream_caller_id records the '
    'downstream owning OS''s own callback identity on downstream_completion_received. '
    'Downstream entity references (per §5.11) live in metadata jsonb, not as separate FK '
    'columns on this table — see migration 021 header, judgment call 1. return/reject/'
    'archive reasons are DB-enforced NOT NULL and non-blank; user actor_id and '
    'initiating_actor_id are DB-enforced (via trigger) to reference active operations.users '
    'rows when their corresponding *_type = user.';
COMMENT ON COLUMN operations.restaurant_update_submission_events.actor_id IS
    'Stable user ID (actor_type=user) | service-account/system actor identifier '
    '(actor_type=system) | pipeline name or pipeline-run identifier (actor_type=pipeline). '
    'Not FK-constrained (polymorphic across actor types) — validated by '
    'trg_rusub_events_validate_actor below when actor_type = user.';
COMMENT ON COLUMN operations.restaurant_update_submission_events.metadata IS
    'Event-specific detail. For disposition_handoff_succeeded / disposition_handoff_failed '
    '/ downstream_completion_received, carries the downstream entity reference per §5.11 '
    '(judgment call 1, migration header): {"downstream_entity_type", "downstream_entity_id", '
    '"routing_command"}, merged with actor_role/authority_basis and any other event-specific '
    'keys the writing RPC adds.';

CREATE INDEX IF NOT EXISTS idx_rusub_events_submission
    ON operations.restaurant_update_submission_events(submission_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_rusub_events_type
    ON operations.restaurant_update_submission_events(event_type, created_at DESC);

-- Append-only, reusing the generic trigger function from migration 016.
DROP TRIGGER IF EXISTS trg_rusub_events_append_only
    ON operations.restaurant_update_submission_events;
CREATE TRIGGER trg_rusub_events_append_only
    BEFORE UPDATE OR DELETE ON operations.restaurant_update_submission_events
    FOR EACH ROW EXECUTE FUNCTION operations.prevent_append_only_mutation();

-- Validate user actor IDs: when actor_type/initiating_actor_type = 'user',
-- the corresponding *_id must cast to a uuid referencing an active
-- operations.users row. system/pipeline actor IDs remain free-form text,
-- untouched by this check. Table is append-only (INSERT is the only path
-- that needs validation).
CREATE OR REPLACE FUNCTION operations.validate_rusub_event_actor()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id   uuid;
    v_is_active boolean;
BEGIN
    IF NEW.actor_type = 'user' THEN
        BEGIN
            v_user_id := NEW.actor_id::uuid;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION
                'restaurant_update_submission_events.actor_id must be a valid UUID when '
                'actor_type = ''user''. Got: %', NEW.actor_id;
        END;

        SELECT is_active INTO v_is_active FROM operations.users WHERE user_id = v_user_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION
                'restaurant_update_submission_events.actor_id (%) does not reference an '
                'existing operations.users row.', NEW.actor_id;
        ELSIF NOT v_is_active THEN
            RAISE EXCEPTION
                'restaurant_update_submission_events.actor_id (%) references an inactive '
                'operations.users row.', NEW.actor_id;
        END IF;
    END IF;

    IF NEW.initiating_actor_type = 'user' THEN
        BEGIN
            v_user_id := NEW.initiating_actor_id::uuid;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION
                'restaurant_update_submission_events.initiating_actor_id must be a valid '
                'UUID when initiating_actor_type = ''user''. Got: %', NEW.initiating_actor_id;
        END;

        SELECT is_active INTO v_is_active FROM operations.users WHERE user_id = v_user_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION
                'restaurant_update_submission_events.initiating_actor_id (%) does not '
                'reference an existing operations.users row.', NEW.initiating_actor_id;
        ELSIF NOT v_is_active THEN
            RAISE EXCEPTION
                'restaurant_update_submission_events.initiating_actor_id (%) references an '
                'inactive operations.users row.', NEW.initiating_actor_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_rusub_events_validate_actor
    ON operations.restaurant_update_submission_events;
CREATE TRIGGER trg_rusub_events_validate_actor
    BEFORE INSERT ON operations.restaurant_update_submission_events
    FOR EACH ROW EXECUTE FUNCTION operations.validate_rusub_event_actor();

ALTER TABLE operations.restaurant_update_submission_events ENABLE ROW LEVEL SECURITY;
-- Service role bypasses RLS — RPCs/API use service role. No anon/
-- authenticated SELECT/INSERT *policies* are added — RLS enabled with
-- zero policies denies all row access to every non-bypassing role by
-- default, matching the effective row-level protection on operations.
-- intake_packet_events and operations.intake_packet_revisions (migration
-- 016) exactly. Note the table-level GRANT below is not identical to
-- 016's: 016 issued no GRANT at all for either of those tables, whereas
-- this migration explicitly grants SELECT/INSERT to service_role and
-- authenticated — inert in practice for the authenticated role since RLS
-- with no policies still denies every row, but stated explicitly here
-- rather than left implicit. Interim mapping, not a permanent grant —
-- same disclaimer as migration 020: long-term authorization for
-- Restaurant Operations OS is capability-based and API/RPC-governed, per
-- DEC000001's precedent extended here by DEC000002.

GRANT SELECT, INSERT ON operations.restaurant_update_submission_events
    TO service_role, authenticated;

-- ============================================================
-- End of 021_submission_state_machine.sql
--
-- Explicitly NOT done here (next step: 022_submission_review_rpcs.sql):
--   - claim / release / return / approve / reject RPCs
--   - resubmit RPC (built, but per Brad's instruction NOT granted to
--     `authenticated` and NOT wired to any API endpoint — invocation
--     authority remains undefined, DEC000002 §5.7, §7 item 5)
--   - submission.convert_to_intake RPC (link-only — see 022's own header
--     for why "create a new intake_packets row from a submission" is out
--     of scope)
--   - submission.route_to_identity_review / submission.escalate_exception
--     — NOT built; blocked on downstream architecture that doesn't exist
--     yet (judgment call 2 above)
--   - archive RPC
--   - Any FastAPI router / X-User-Id request handling / UI
--
-- Do not run this migration until it has been reviewed. Not executed
-- against any database.
-- ============================================================
