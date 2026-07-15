-- ============================================================
-- 016_intake_packet_state_machine.sql
-- Intake OS — implements the DEC000001 canonical Intake Packet
-- state machine (Founder-approved 2026-07-13, v4.1) against the
-- live schema introduced in 015_intake_packets.sql.
--
-- Scope of this migration (schema only — see
-- docs/decisions/DEC000001_IMPLEMENTATION_GAP_MAP.md §1-§2):
--   1. Expand packet_status to the six canonical values
--      (adds in_review, rejected), gated by a fail-loud precondition.
--   2. Add claim fields (§5.3-§5.5), DB-enforced claim/status
--      consistency.
--   3. Add supersession fields + single-hop enforcement (§5.6).
--   4. Add archival fields (§5.11), DB-enforced eligibility.
--   5. Create operations.intake_packet_revisions (§5.8), with a
--      trigger validating the revision actor is an active user.
--   6. Create operations.intake_packet_events (§5.8), with a
--      trigger validating user actor IDs against operations.users.
--
-- What is DB-enforced vs. API-enforced (per Brad's correction passes):
--   DB-enforced:   packet_status value set (only after verifying the live
--                  legacy constraint matches expectations — see §1 below);
--                  claim fields both-null or both-set depending on status;
--                  archival eligibility (status allow-list, actor requires
--                  archived_at); supersession single-hop + no self-reference;
--                  return/reject reason non-null and non-blank;
--                  edit_payload revision reason non-null and non-blank;
--                  user actor_id/actor_user_id resolves to an active
--                  operations.users row, on both intake_packet_events and
--                  intake_packet_revisions.
--   API-enforced:  who may call which command (role boundaries, §4);
--                  the atomic claim UPDATE...WHERE...RETURNING pattern (§5.4);
--                  archival confirmation step and *which* actor may archive;
--                  admin-override-release reason requirement (§5.5) — not
--                  structurally distinguishable from an ordinary self-release
--                  without a dedicated override flag, so this one stays an
--                  API-layer guardrail, not a CHECK.
--
-- Explicitly OUT of scope for this migration (per Brad's instruction —
-- belongs to the subsequent API/service pass, and this migration is NOT
-- to be run yet):
--   - X-User-Id / X-Admin-Key request-handling logic.
--   - intake.packet.commit_ingest integration with ingest_packet.py.
--   - Any application-layer role/permission enforcement.
--
-- Identity source (resolved, not invented — gap map §0):
--   *_user_id columns below reference operations.users(user_id),
--   the existing Supabase-Auth-mirrored identity table (migration
--   004). No new identity model is introduced by this migration.
-- ============================================================

-- ── 1. packet_status: expand to six canonical values (§6) ─────────────────────
-- Fail-loud precondition, not a silent best-effort drop. This block:
--   (a) finds the CHECK constraint(s) actually attached to
--       operations.intake_packets.packet_status in the live schema — located
--       via an exact single-column conkey match (con.conkey = ARRAY[att.attnum]),
--       not by guessing a name and not by a loose ANY() membership test that
--       could also match a multi-column constraint referencing packet_status
--       incidentally;
--   (b) aborts with a clear exception if there isn't exactly one such
--       constraint (zero found, or more than one — ambiguous, refuses to
--       guess which one is the legacy constraint to drop);
--   (c) aborts with a clear exception if that one constraint's definition
--       doesn't contain the expected legacy 4-state tokens and does contain
--       either new v6-state token — see the explicit scope statement below;
--   (d) only then drops that exact, now-verified constraint by its real name
--       and installs the 6-state constraint.
-- It never falls through to installing the 6-state constraint alongside an
-- unidentified stale constraint.
--
-- ⚠ BLOCKED — scope of verification, stated explicitly rather than overclaimed:
-- Step (c) above is STRUCTURAL validation (exactly one CHECK constraint,
-- located via an exact conkey match on the packet_status attribute) plus
-- STATE-TOKEN validation (the constraint's text contains the four legacy
-- state literals and neither of the two new ones). It is NOT a comparison
-- against the exact normalized pg_get_constraintdef() output of the live
-- 015_intake_packets.sql constraint, because that exact live-database output
-- has not been obtained or compared from this sandbox (no live Postgres/
-- Supabase connection is available here). This migration must not be
-- executed until the exact live pg_get_constraintdef() output for the
-- packet_status constraint has been inspected and confirmed to match
-- 015_intake_packets.sql's inline CHECK before this block is allowed to run
-- against production. Running this migration blind is itself not the
-- verification step.

DO $$
DECLARE
    v_conname  name;
    v_condef   text;
    v_matches  int;
BEGIN
    SELECT count(DISTINCT con.oid) INTO v_matches
    FROM pg_constraint con
    JOIN pg_class rel      ON rel.oid = con.conrelid
    JOIN pg_namespace nsp  ON nsp.oid = rel.relnamespace
    JOIN pg_attribute att  ON att.attrelid = rel.oid
    WHERE nsp.nspname = 'operations'
      AND rel.relname = 'intake_packets'
      AND con.contype = 'c'
      AND att.attname = 'packet_status'
      AND con.conkey = ARRAY[att.attnum]::smallint[];

    IF v_matches = 0 THEN
        RAISE EXCEPTION
            'Migration precondition failed: no single-column CHECK constraint found '
            'on operations.intake_packets.packet_status. Expected exactly one '
            '(the legacy 4-state constraint from 015_intake_packets.sql). '
            'Aborting rather than guessing — verify the live schema before retrying.';
    ELSIF v_matches > 1 THEN
        RAISE EXCEPTION
            'Migration precondition failed: % single-column CHECK constraints found '
            'on operations.intake_packets.packet_status, expected exactly one. '
            'Aborting rather than guessing which one is the legacy constraint to '
            'drop — resolve the ambiguity in the live schema before retrying.',
            v_matches;
    END IF;

    SELECT con.conname, pg_get_constraintdef(con.oid)
    INTO v_conname, v_condef
    FROM pg_constraint con
    JOIN pg_class rel      ON rel.oid = con.conrelid
    JOIN pg_namespace nsp  ON nsp.oid = rel.relnamespace
    JOIN pg_attribute att  ON att.attrelid = rel.oid
    WHERE nsp.nspname = 'operations'
      AND rel.relname = 'intake_packets'
      AND con.contype = 'c'
      AND att.attname = 'packet_status'
      AND con.conkey = ARRAY[att.attnum]::smallint[];

    -- Structural + state-token validation only (see the BLOCKED statement
    -- above) — NOT an exact pg_get_constraintdef() comparison. Checks that
    -- the definition contains the four legacy state tokens and neither new
    -- v6-state token, so an already-migrated 6-state constraint (e.g. from a
    -- prior partial run) is not mistaken for the legacy one and silently
    -- dropped/replaced. This does not by itself prove the definition is
    -- exactly 015_intake_packets.sql's CHECK — that comparison is still
    -- outstanding per the BLOCKED note above.
    IF NOT (
        v_condef ~ 'pending_review'
        AND v_condef ~ 'returned'
        AND v_condef ~ 'approved'
        AND v_condef ~ 'ingested'
        AND v_condef !~ 'in_review'
        AND v_condef !~ 'rejected'
    ) THEN
        RAISE EXCEPTION
            'Migration precondition failed: constraint "%" on '
            'operations.intake_packets.packet_status does not contain the expected '
            'legacy 4-state tokens (pending_review, returned, approved, ingested) '
            'or contains an unexpected v6-state token. Actual definition: %. '
            'Aborting — this may mean the six-state constraint is already '
            'installed (this migration already ran), or the schema has drifted '
            'from what 015_intake_packets.sql defines. Resolve manually before '
            'retrying.', v_conname, v_condef;
    END IF;

    EXECUTE format('ALTER TABLE operations.intake_packets DROP CONSTRAINT %I', v_conname);
END $$;

ALTER TABLE operations.intake_packets
    ADD CONSTRAINT intake_packets_packet_status_check
    CHECK (packet_status IN (
        'pending_review', 'in_review', 'returned', 'approved', 'rejected', 'ingested'
    ));

COMMENT ON COLUMN operations.intake_packets.packet_status IS
    'Six canonical statuses per DEC000001 §6: pending_review, in_review, returned, '
    'approved, rejected, ingested. draft is intentionally excluded (§6).';

-- ── 2. Claim fields (§5.3-§5.5) + DB-enforced claim/status consistency ────────
-- Stable user ID only — no display-name snapshot (§5.3). The atomic claim
-- UPDATE ... WHERE ... RETURNING pattern (§5.4) is an API-layer concern, not
-- expressible as a schema constraint, and remains out of scope here. What IS
-- DB-enforced below: claim fields are both-set if and only if packet_status
-- is in_review — never one without the other, and never present outside
-- in_review.

ALTER TABLE operations.intake_packets
    ADD COLUMN IF NOT EXISTS claimed_by_user_id  uuid REFERENCES operations.users(user_id),
    ADD COLUMN IF NOT EXISTS claimed_at           timestamptz;

COMMENT ON COLUMN operations.intake_packets.claimed_by_user_id IS
    'Governance Reviewer who currently holds this packet in_review (DEC000001 §5.3-§5.4). '
    'Cleared atomically by release/return/approve/reject (§5.5) — describes who currently '
    'has the packet checked out, not who last decided it (that lives permanently in '
    'operations.intake_packet_events). DB-enforced: set if and only if packet_status = '
    'in_review (see intake_packets_claim_consistency below); the atomic claim UPDATE '
    'pattern itself (§5.4) is an API responsibility.';
COMMENT ON COLUMN operations.intake_packets.claimed_at IS
    'Set atomically with claimed_by_user_id by intake.review.claim (§5.4). DB-enforced '
    'alongside claimed_by_user_id — see intake_packets_claim_consistency.';

ALTER TABLE operations.intake_packets
    DROP CONSTRAINT IF EXISTS intake_packets_claim_consistency;
ALTER TABLE operations.intake_packets
    ADD CONSTRAINT intake_packets_claim_consistency
    CHECK (
        (packet_status = 'in_review'
            AND claimed_by_user_id IS NOT NULL
            AND claimed_at IS NOT NULL)
        OR
        (packet_status != 'in_review'
            AND claimed_by_user_id IS NULL
            AND claimed_at IS NULL)
    );

COMMENT ON CONSTRAINT intake_packets_claim_consistency ON operations.intake_packets IS
    'DEC000001 §5.4-§5.5: in_review requires both claim fields set; every other status '
    'requires both null. Decision commands (return/approve/reject) must clear both claim '
    'fields in the same transaction that moves packet_status out of in_review, or this '
    'constraint rejects the write.';

-- ── 3. Supersession (§5.6) — system-derived, single-hop chain ─────────────────

ALTER TABLE operations.intake_packets
    ADD COLUMN IF NOT EXISTS superseded_by_packet_id uuid
        REFERENCES operations.intake_packets(packet_id);

-- Self-reference is structurally excluded (§5.6).
ALTER TABLE operations.intake_packets
    DROP CONSTRAINT IF EXISTS intake_packets_no_self_supersede;
ALTER TABLE operations.intake_packets
    ADD CONSTRAINT intake_packets_no_self_supersede
    CHECK (superseded_by_packet_id != packet_id);

-- Each packet may be referenced as the successor of at most one
-- immediate predecessor (§5.6's single-hop enforcement mechanism).
CREATE UNIQUE INDEX IF NOT EXISTS idx_intake_packets_superseded_by_unique
    ON operations.intake_packets(superseded_by_packet_id)
    WHERE superseded_by_packet_id IS NOT NULL;

COMMENT ON COLUMN operations.intake_packets.superseded_by_packet_id IS
    'System-derived only (§5.6) — no routine human-facing command sets this. Points to '
    'the immediate chronological successor (later canvass_date, same restaurant '
    'identity) among ingested packets. Referential validity (target must be ingested, '
    'same restaurant identity, strictly later canvass_date) cannot be expressed as a '
    'CHECK constraint per §5.6 and must be enforced by the recomputation logic that '
    'sets this column — an API/service responsibility, not DB-enforced here.';

-- ── 4. Archival (§5.11) — non-status attribute, DB-enforced eligibility ───────
-- Status eligibility (rejected/ingested only) and the actor-requires-timestamp
-- rule are now DB-enforced via CHECK constraints below. Still API-enforced:
-- *who* may archive, the confirmation step, and the reason requirement (§8
-- guardrail language about "must refuse to run" describes the combination of
-- these DB constraints plus the API's own authorization/confirmation logic).

ALTER TABLE operations.intake_packets
    ADD COLUMN IF NOT EXISTS archived_at          timestamptz,
    ADD COLUMN IF NOT EXISTS archived_by_user_id   uuid REFERENCES operations.users(user_id);

COMMENT ON COLUMN operations.intake_packets.archived_at IS
    'Non-status attribute (§5.11). DB-enforced eligibility: archived_at may only be set '
    'while packet_status is rejected or ingested (see intake_packets_archival_eligibility '
    'below) — no path exists directly from approved to archived; approved must reach '
    'ingested via commit_ingest first. Who may archive and the confirmation step remain '
    'API responsibilities.';
COMMENT ON COLUMN operations.intake_packets.archived_by_user_id IS
    'Set only for manual archival (§5.11); null when/if a future policy-driven automatic '
    'archival schedule is adopted (none is approved by DEC000001). DB-enforced: an actor '
    'cannot be recorded without archived_at also being set (see '
    'intake_packets_archival_actor_requires_timestamp below) — this still permits future '
    'system archival with archived_at populated and no human actor.';

ALTER TABLE operations.intake_packets
    DROP CONSTRAINT IF EXISTS intake_packets_archival_eligibility;
ALTER TABLE operations.intake_packets
    ADD CONSTRAINT intake_packets_archival_eligibility
    CHECK (archived_at IS NULL OR packet_status IN ('rejected', 'ingested'));

ALTER TABLE operations.intake_packets
    DROP CONSTRAINT IF EXISTS intake_packets_archival_actor_requires_timestamp;
ALTER TABLE operations.intake_packets
    ADD CONSTRAINT intake_packets_archival_actor_requires_timestamp
    CHECK (archived_by_user_id IS NULL OR archived_at IS NOT NULL);

COMMENT ON CONSTRAINT intake_packets_archival_eligibility ON operations.intake_packets IS
    'DEC000001 §5.11 explicit allow-list, DB-enforced: archived_at is only settable while '
    'packet_status ∈ {rejected, ingested}.';
COMMENT ON CONSTRAINT intake_packets_archival_actor_requires_timestamp ON operations.intake_packets IS
    'DEC000001 §5.11: an archival actor implies archival happened. Deliberately one-way — '
    'archived_at with no archived_by_user_id remains valid, covering a future '
    'system-initiated archival (§5.11, not itself approved by this decision).';

-- ── 5. reviewed_by — retained temporarily, not converted (see gap-map note) ───
-- Inspected: no current code path writes this column. api/routers/intake.py's
-- approve_packet() and return_packet() update every other reviewed_* field but
-- never set reviewed_by; no seed/fixture data sets it either. It is read-only
-- dead weight today — present in the API response models and the Intake UI
-- detail view (conditionally rendered), but always null in practice.
-- Per instruction: not converted to uuid and not dropped in this migration.
-- Retained as-is (text, nullable) for API/UI read-path compatibility until the
-- API and UI are updated to read the reviewer-of-record from
-- operations.intake_packet_events instead (§5.5, §5.8 — the event log is the
-- permanent reviewer-of-record). Recommend removing this column in a follow-up
-- migration once that cutover happens.

COMMENT ON COLUMN operations.intake_packets.reviewed_by IS
    'DEPRECATED — unused by any current write path (verified 2026-07 during '
    'DEC000001 implementation). Retained temporarily for read-path compatibility. '
    'The reviewer-of-record now lives permanently in operations.intake_packet_events '
    '(§5.5, §5.8). Slated for removal once API/UI are cut over to the event log.';

-- ── 6. Indexes supporting the new lifecycle ────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_intake_packets_claimed_by
    ON operations.intake_packets(claimed_by_user_id)
    WHERE claimed_by_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_intake_packets_archived_at
    ON operations.intake_packets(archived_at)
    WHERE archived_at IS NOT NULL;

-- ── Generic append-only enforcement, reusable across both new tables ──────────
-- 006_triggers.sql's existing append-only functions (prevent_lifecycle_events_
-- mutation, prevent_audit_log_mutation) hardcode their table name into the
-- exception message, so they can't be reused as-is for a different table
-- without producing a misleading error. This is a generic equivalent, keyed
-- off TG_TABLE_SCHEMA/TG_TABLE_NAME, applied to both tables below.

CREATE OR REPLACE FUNCTION operations.prevent_append_only_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        '%.% is append-only. UPDATE and DELETE are prohibited. Operation: %',
        TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP;
END;
$$;

-- ============================================================
-- ── operations.intake_packet_revisions (§5.8) ──────────────────────────────
-- Payload snapshots only. One row per intake.packet.edit_payload call —
-- always human-initiated by an Intake Specialist, never system-generated.
-- Distinct from intake_packet_events (lifecycle/claim/annotation log, below).
-- reason is NOT NULL + non-blank: edit_payload requires a reason (§5.1, §5.8).
-- ============================================================

CREATE TABLE IF NOT EXISTS operations.intake_packet_revisions (
    revision_id      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    packet_id        uuid        NOT NULL REFERENCES operations.intake_packets(packet_id),
    prior_payload    jsonb       NOT NULL,
    actor_user_id    uuid        NOT NULL REFERENCES operations.users(user_id),
    reason           text        NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT intake_packet_revisions_reason_nonblank
        CHECK (reason ~ '\S')
);

COMMENT ON TABLE operations.intake_packet_revisions IS
    'Append-only payload snapshots (DEC000001 §5.8). One row per edit_payload call. '
    'actor_user_id, not actor_type/actor_id — payload edits are always human '
    '(Intake Specialist role only, §4, §5.2), never system-generated. reason is '
    'DB-enforced NOT NULL and non-blank (edit_payload requires a reason, §5.1, §5.8). '
    'actor_user_id is DB-enforced (via trigger) to reference an active operations.users '
    'row at insert time — the FK alone only proves the row exists, not that it was '
    'active when the edit happened.';
COMMENT ON COLUMN operations.intake_packet_revisions.prior_payload IS
    'packet_data as it existed immediately before this edit (the new payload lives '
    'on the intake_packets row itself).';

CREATE INDEX IF NOT EXISTS idx_intake_packet_revisions_packet
    ON operations.intake_packet_revisions(packet_id, created_at DESC);

-- Append-only: same pattern as operations.audit_log / evidence.lifecycle_events
-- (006_triggers.sql), via the generic function defined above. Dropped before
-- recreation so this migration is safe to re-run after a partial failure.
DROP TRIGGER IF EXISTS trg_intake_packet_revisions_append_only
    ON operations.intake_packet_revisions;
CREATE TRIGGER trg_intake_packet_revisions_append_only
    BEFORE UPDATE OR DELETE ON operations.intake_packet_revisions
    FOR EACH ROW EXECUTE FUNCTION operations.prevent_append_only_mutation();

-- Validate the revision actor: actor_user_id's FK already proves the row
-- exists in operations.users, but not that it was active at insert time.
-- Table is append-only (UPDATE already blocked above), so INSERT is the only
-- path that needs validation.

CREATE OR REPLACE FUNCTION operations.validate_intake_packet_revision_actor()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_is_active boolean;
BEGIN
    SELECT is_active INTO v_is_active
    FROM operations.users
    WHERE user_id = NEW.actor_user_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'intake_packet_revisions.actor_user_id (%) does not reference an existing '
            'operations.users row.', NEW.actor_user_id;
    END IF;

    IF NOT v_is_active THEN
        RAISE EXCEPTION
            'intake_packet_revisions.actor_user_id (%) references an inactive '
            'operations.users row.', NEW.actor_user_id;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_intake_packet_revisions_validate_actor
    ON operations.intake_packet_revisions;
CREATE TRIGGER trg_intake_packet_revisions_validate_actor
    BEFORE INSERT ON operations.intake_packet_revisions
    FOR EACH ROW EXECUTE FUNCTION operations.validate_intake_packet_revision_actor();

ALTER TABLE operations.intake_packet_revisions ENABLE ROW LEVEL SECURITY;
-- Service role bypasses RLS — API uses service role. No anon/authenticated
-- policies, matching operations.intake_packets (015).

-- ============================================================
-- ── operations.intake_packet_events (§5.8) ─────────────────────────────────
-- Full lifecycle/claim/annotation audit trail. One row per state-changing,
-- claim-changing, or annotation event: claim, release, return, resubmit,
-- approve, reject, ingest, archive, supersede, annotate.
--
-- actor_type/actor_id (not a single actor_user_id) so system- and
-- pipeline-derived events (ingest, supersede) can be recorded without a
-- human user ID (§5.8, corrected in v4.1). actor_id is intentionally text,
-- not a uuid FK to operations.users — it must also hold service-account
-- identifiers and pipeline-run identifiers when actor_type != 'user'. When
-- actor_type = 'user', a trigger below (not a CHECK, since it requires a
-- lookup) validates actor_id is a UUID referencing an active
-- operations.users row.
-- ============================================================

CREATE TABLE IF NOT EXISTS operations.intake_packet_events (
    event_id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    packet_id        uuid        NOT NULL REFERENCES operations.intake_packets(packet_id),
    event_type       text        NOT NULL,
    actor_type       text        NOT NULL,
    actor_id         text        NOT NULL,
    reason           text,
    metadata         jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at       timestamptz NOT NULL DEFAULT now(),

    -- Explicitly named (rather than left as inline/auto-named column CHECKs)
    -- for consistency with every other constraint in this migration, and so
    -- a future migration can reference them by a stable name rather than
    -- guessing an auto-generated one (see §1's packet_status precondition
    -- block above for why that matters).
    CONSTRAINT intake_packet_events_event_type_check
        CHECK (event_type IN (
            'claim', 'release', 'return', 'resubmit',
            'approve', 'reject', 'ingest', 'archive',
            'supersede', 'annotate'
        )),
    CONSTRAINT intake_packet_events_actor_type_check
        CHECK (actor_type IN ('user', 'system', 'pipeline')),

    -- actor_id non-blank check applies to all three actor types (user,
    -- system, pipeline) — a system or pipeline identifier consisting solely
    -- of whitespace is just as invalid as a blank one.
    CONSTRAINT intake_packet_events_actor_id_nonblank
        CHECK (actor_id ~ '\S'),

    -- §5.10: reason is mandatory and non-blank for reject. §5.9/carried
    -- behavior: mandatory and non-blank for return. (Release-override's
    -- reason requirement, §5.5, is conditional on "admin override" vs.
    -- "ordinary self-release" — not a structural distinction this table can
    -- express without a dedicated override flag — so that specific case
    -- remains an API-layer guardrail, not a CHECK here.)
    CONSTRAINT intake_packet_events_reason_required
        CHECK (event_type NOT IN ('return', 'reject')
               OR (reason IS NOT NULL AND reason ~ '\S'))
);

COMMENT ON TABLE operations.intake_packet_events IS
    'Append-only lifecycle/claim/annotation audit trail (DEC000001 §5.8, corrected '
    'v4.1). actor_type distinguishes user/system/pipeline actors so ingest and '
    'supersede events (system-derived, §5.6-§5.7) do not require a human actor_id. '
    'This is the permanent reviewer-of-record — see §5.5. return/reject reasons are '
    'DB-enforced NOT NULL and non-blank; user actor_id is DB-enforced (via trigger) '
    'to reference an active operations.users row.';
COMMENT ON COLUMN operations.intake_packet_events.actor_id IS
    'Stable user ID (actor_type=user) | service-account/system actor identifier '
    '(actor_type=system) | pipeline name or pipeline-run identifier '
    '(actor_type=pipeline). Not FK-constrained to operations.users because this '
    'column is polymorphic across the three actor types — instead, DB-enforced by '
    'trg_intake_packet_events_validate_actor below when actor_type = user only.';

CREATE INDEX IF NOT EXISTS idx_intake_packet_events_packet
    ON operations.intake_packet_events(packet_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_intake_packet_events_type
    ON operations.intake_packet_events(event_type, created_at DESC);

-- Append-only: same pattern as operations.audit_log (006_triggers.sql), via
-- the generic function defined above. Dropped before recreation so this
-- migration is safe to re-run after a partial failure.
DROP TRIGGER IF EXISTS trg_intake_packet_events_append_only
    ON operations.intake_packet_events;
CREATE TRIGGER trg_intake_packet_events_append_only
    BEFORE UPDATE OR DELETE ON operations.intake_packet_events
    FOR EACH ROW EXECUTE FUNCTION operations.prevent_append_only_mutation();

-- Validate user actor IDs: when actor_type = 'user', actor_id must cast to a
-- uuid and must reference an active operations.users row. system/pipeline
-- actor IDs remain free-form text identifiers, untouched by this check. A
-- CHECK constraint can't perform this lookup, so this is a BEFORE INSERT
-- trigger — the table is append-only (UPDATE is already blocked above), so
-- INSERT is the only path that needs validation.

CREATE OR REPLACE FUNCTION operations.validate_intake_packet_event_actor()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_actor_user_id uuid;
    v_is_active     boolean;
BEGIN
    IF NEW.actor_type = 'user' THEN
        BEGIN
            v_actor_user_id := NEW.actor_id::uuid;
        EXCEPTION WHEN invalid_text_representation THEN
            RAISE EXCEPTION
                'intake_packet_events.actor_id must be a valid UUID when actor_type = ''user''. '
                'Got: %', NEW.actor_id;
        END;

        SELECT is_active INTO v_is_active
        FROM operations.users
        WHERE user_id = v_actor_user_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION
                'intake_packet_events.actor_id (%) does not reference an existing '
                'operations.users row.', NEW.actor_id;
        END IF;

        IF NOT v_is_active THEN
            RAISE EXCEPTION
                'intake_packet_events.actor_id (%) references an inactive '
                'operations.users row.', NEW.actor_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_intake_packet_events_validate_actor
    ON operations.intake_packet_events;
CREATE TRIGGER trg_intake_packet_events_validate_actor
    BEFORE INSERT ON operations.intake_packet_events
    FOR EACH ROW EXECUTE FUNCTION operations.validate_intake_packet_event_actor();

ALTER TABLE operations.intake_packet_events ENABLE ROW LEVEL SECURITY;
-- Service role bypasses RLS — API uses service role. No anon/authenticated
-- policies, matching operations.intake_packets (015).

-- ============================================================
-- End of 016_intake_packet_state_machine.sql
--
-- Explicitly NOT done here (next steps, per DEC000001 gap map §3 and
-- Brad's implementation order items 3-6):
--   - intake.review.claim / intake.review.release endpoints
--   - Tightening intake.review.approve / intake.review.return to require
--     in_review + claimant-or-admin
--   - intake.packet.reject / edit_payload / resubmit / archive endpoints
--   - intake.packet.commit_ingest as the sole ordinary path to ingested
--   - X-Admin-Key + X-User-Id dual-header request validation
--
-- Do not run this migration until it has been reviewed against the live
-- schema — §1's precondition block will abort loudly rather than corrupt
-- state if the live packet_status constraint doesn't match expectations,
-- but that self-check has not yet been exercised against an actual
-- Supabase instance from this sandbox.
-- ============================================================
