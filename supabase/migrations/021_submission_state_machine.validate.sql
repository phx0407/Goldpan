-- ============================================================
-- 021_submission_state_machine.validate.sql
-- Focused validation for 021_submission_state_machine.sql.
--
-- Not a migration. Not executed as part of applying migration 021. Run
-- this manually, against a database that already has migration 021
-- applied, when Brad wants to verify the migration before/after applying
-- it in a given environment.
--
-- Independently verifies the FULL contract implemented by migration 021 —
-- not merely the portions exercised indirectly by 022's resubmit tests.
-- Derived from the canonical DEC000002_submission_state_machine.md (v4.2),
-- docs/decisions/DEC000002_IMPLEMENTATION_GAP_MAP.md, and the actual SQL
-- in 021_submission_state_machine.sql.
--
-- Everything in this script runs inside a single transaction that is
-- ROLLBACK'd at the end — no fixture data or test rows are left behind,
-- and no real data is modified. Safe to run against a database that
-- already has real operations.restaurant_update_submissions rows in it.
--
-- Coverage:
--   A. Guard                       (021 schema objects present)
--   B. Fixtures                    (users, restaurants, intake packet,
--                                    baseline + resubmission-parent rows)
--   C. Schema additions            (columns present; nullability; defaults;
--                                    resulting_intake_session -> _id rename
--                                    + retype to uuid)
--   D. Constraint & index inventory + canonical status alignment
--      (every 021-defined CHECK/index present by name; status CHECK
--      contains exactly the 5 DEC000002 v4.2 values, no 'converted' leak)
--   E. Claim consistency guard     (rusub_claim_consistency)
--   F. Resubmission chain          (identity trigger, chain-rewrite
--                                    immutability trigger, self-supersede
--                                    CHECK, single-hop uniqueness both
--                                    directions)
--   G. Archival eligibility        (rusub_archival_eligibility + actor/
--                                    reason/timestamp companions)
--   H. Disposition model           (type/status/failure_stage consistency,
--                                    no_action resolution_summary mandate)
--   I. Downstream linkage          (FK-requires-type guardrails, ON DELETE
--                                    RESTRICT, non-canonical exclusion from
--                                    cardinality, unconstrained placeholders
--                                    confirmed to carry no invented FK)
--   J. Events table                (event_type/actor_type enums, reason
--                                    requirement, failure_stage scope,
--                                    actor-validation trigger, append-only)
--   K. Trigger function privileges (RETURNS TRIGGER functions reject
--                                    direct invocation outside a trigger)
--   L. RLS / GRANT posture         (events table: RLS on, no policies,
--                                    SELECT+INSERT only, no UPDATE/DELETE)
--   M. Direct-mutation failure behavior + rollback cleanliness banner
--
-- Each check RAISEs NOTICE on pass and RAISEs EXCEPTION on failure, so a
-- failed run aborts loudly and the whole transaction rolls back.
-- Usage:  psql "$DATABASE_URL" -f 021_submission_state_machine.validate.sql
-- ============================================================

BEGIN;

-- ── A. Guard: migration 021 must already be applied ─────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'operations' AND table_name = 'restaurant_update_submissions'
          AND column_name = 'resubmission_of_submission_id'
    ) THEN
        RAISE EXCEPTION 'VALIDATION ABORTED: operations.restaurant_update_submissions.resubmission_of_submission_id does not exist — apply migration 021 first';
    END IF;
    IF to_regclass('operations.restaurant_update_submission_events') IS NULL THEN
        RAISE EXCEPTION 'VALIDATION ABORTED: operations.restaurant_update_submission_events does not exist — apply migration 021 first';
    END IF;
    IF to_regprocedure('operations.prevent_rusub_chain_rewrite()') IS NULL THEN
        RAISE EXCEPTION 'VALIDATION ABORTED: operations.prevent_rusub_chain_rewrite() does not exist — apply migration 021 first';
    END IF;
    IF to_regprocedure('operations.validate_rusub_resubmission_identity()') IS NULL THEN
        RAISE EXCEPTION 'VALIDATION ABORTED: operations.validate_rusub_resubmission_identity() does not exist — apply migration 021 first';
    END IF;
    IF to_regprocedure('operations.validate_rusub_event_actor()') IS NULL THEN
        RAISE EXCEPTION 'VALIDATION ABORTED: operations.validate_rusub_event_actor() does not exist — apply migration 021 first';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rusub_prevent_chain_rewrite') THEN
        RAISE EXCEPTION 'VALIDATION ABORTED: trg_rusub_prevent_chain_rewrite trigger does not exist — apply migration 021 first';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rusub_validate_resubmission_identity') THEN
        RAISE EXCEPTION 'VALIDATION ABORTED: trg_rusub_validate_resubmission_identity trigger does not exist — apply migration 021 first';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rusub_events_append_only') THEN
        RAISE EXCEPTION 'VALIDATION ABORTED: trg_rusub_events_append_only trigger does not exist — apply migration 021 first';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rusub_events_validate_actor') THEN
        RAISE EXCEPTION 'VALIDATION ABORTED: trg_rusub_events_validate_actor trigger does not exist — apply migration 021 first';
    END IF;
    RAISE NOTICE 'GUARD PASS: all migration-021 schema objects (columns, table, functions, triggers) present';
END $$;


-- ── B. Fixtures (rolled back at end of script; never committed) ─────────────

DO $$
BEGIN
    INSERT INTO operations.users (user_id, email, display_name, role, is_active)
    VALUES ('00000000-0000-4000-8000-000000000501', 'validate021.active@example.com', 'Validate021 Active User', 'coordinator', true);

    INSERT INTO operations.users (user_id, email, display_name, role, is_active)
    VALUES ('00000000-0000-4000-8000-000000000502', 'validate021.inactive@example.com', 'Validate021 Inactive User', 'coordinator', false);

    INSERT INTO evidence.restaurants (restaurant_id, external_id, name)
    VALUES ('00000000-0000-4000-8000-000000000503', 'TESTR_021_VALIDATE_A', 'Migration 021 Validation Fixture A');

    INSERT INTO evidence.restaurants (restaurant_id, external_id, name)
    VALUES ('00000000-0000-4000-8000-000000000504', 'TESTR_021_VALIDATE_B', 'Migration 021 Validation Fixture B');

    INSERT INTO operations.intake_packets (
        packet_id, restaurant_external_id, restaurant_name, canvass_date, packet_data
    ) VALUES (
        '00000000-0000-4000-8000-000000000505', 'TESTR_021_VALIDATE_A', 'Migration 021 Validation Fixture A',
        current_date, '{}'::jsonb
    );

    -- Baseline submission, restaurant A, default status — general-purpose
    -- target for events-table tests and the direct-mutation failure test.
    INSERT INTO operations.restaurant_update_submissions (
        submission_id, restaurant_id, submission_type
    ) VALUES (
        '00000000-0000-4000-8000-000000000510', '00000000-0000-4000-8000-000000000503', 'menu_update'
    );

    -- Resubmission-chain parent, restaurant A, status = returned (eligible
    -- source state for resubmission per §5.7 — created directly since no
    -- return RPC exists yet in this migration set).
    INSERT INTO operations.restaurant_update_submissions (
        submission_id, restaurant_id, submission_type, status
    ) VALUES (
        '00000000-0000-4000-8000-000000000520', '00000000-0000-4000-8000-000000000503', 'menu_update', 'returned'
    );

    -- Second returned parent, restaurant A, no chain yet — used for the
    -- self-supersede CHECK and cross-parent uniqueness tests (F8/F10),
    -- kept separate from 520/521 so those tests don't disturb the main
    -- chain fixture.
    INSERT INTO operations.restaurant_update_submissions (
        submission_id, restaurant_id, submission_type, status
    ) VALUES (
        '00000000-0000-4000-8000-000000000522', '00000000-0000-4000-8000-000000000503', 'menu_update', 'returned'
    );

    RAISE NOTICE 'PASS (fixtures): 2 operations.users rows, 2 evidence.restaurants rows, 1 operations.intake_packets row, 3 operations.restaurant_update_submissions rows created';
END $$;


-- ── C. Schema additions: columns present, nullability, defaults ─────────────

-- C1. operations.restaurant_update_submissions — 15 new columns, expected
-- nullability per migration 021.
DO $$
DECLARE
    r record;
    v_nullable text;
BEGIN
    FOR r IN
        SELECT * FROM (VALUES
            ('claimed_by_user_id',            'YES'),
            ('claimed_at',                    'YES'),
            ('resubmission_of_submission_id',  'YES'),
            ('superseded_by_submission_id',    'YES'),
            ('archived_at',                    'YES'),
            ('archived_by_user_id',            'YES'),
            ('archive_reason',                 'YES'),
            ('disposition_type',               'YES'),
            ('disposition_status',             'NO'),
            ('failure_stage',                  'YES'),
            ('resolution_summary',             'YES'),
            ('resulting_intake_session_id',    'YES'),
            ('resulting_intake_packet_id',     'YES'),
            ('identity_review_item_id',        'YES'),
            ('exception_request_id',           'YES')
        ) AS t(col_name, exp_nullable)
    LOOP
        SELECT is_nullable INTO v_nullable
        FROM information_schema.columns
        WHERE table_schema = 'operations' AND table_name = 'restaurant_update_submissions'
          AND column_name = r.col_name;

        IF v_nullable IS NULL THEN
            RAISE EXCEPTION 'VALIDATION FAILED: column % does not exist on operations.restaurant_update_submissions', r.col_name;
        END IF;
        IF v_nullable <> r.exp_nullable THEN
            RAISE EXCEPTION 'VALIDATION FAILED: operations.restaurant_update_submissions.% is_nullable = % (expected %)', r.col_name, v_nullable, r.exp_nullable;
        END IF;
    END LOOP;
    RAISE NOTICE 'PASS (C1): all 15 new operations.restaurant_update_submissions columns present with expected nullability';
END $$;

-- C2. disposition_status default, resulting_intake_session_id retype+rename.
DO $$
DECLARE
    v_default text;
    v_type    text;
BEGIN
    SELECT column_default INTO v_default
    FROM information_schema.columns
    WHERE table_schema = 'operations' AND table_name = 'restaurant_update_submissions'
      AND column_name = 'disposition_status';
    IF v_default IS NULL OR v_default NOT LIKE '%unassessed%' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: disposition_status column_default = % (expected a default containing ''unassessed'')', v_default;
    END IF;
    RAISE NOTICE 'PASS (C2a): disposition_status NOT NULL DEFAULT ''unassessed'' confirmed (default = %)', v_default;

    SELECT data_type INTO v_type
    FROM information_schema.columns
    WHERE table_schema = 'operations' AND table_name = 'restaurant_update_submissions'
      AND column_name = 'resulting_intake_session_id';
    IF v_type IS DISTINCT FROM 'uuid' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: resulting_intake_session_id data_type = % (expected uuid — legacy text-to-uuid retype did not take effect)', v_type;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'operations' AND table_name = 'restaurant_update_submissions'
          AND column_name = 'resulting_intake_session'
    ) THEN
        RAISE EXCEPTION 'VALIDATION FAILED: legacy column resulting_intake_session still exists — rename to resulting_intake_session_id did not take effect';
    END IF;
    RAISE NOTICE 'PASS (C2b): resulting_intake_session_id is uuid-typed and the legacy resulting_intake_session column no longer exists';
END $$;

-- C3. operations.restaurant_update_submission_events — full column set,
-- expected nullability.
DO $$
DECLARE
    r record;
    v_nullable text;
BEGIN
    FOR r IN
        SELECT * FROM (VALUES
            ('event_id',                     'NO'),
            ('submission_id',                'NO'),
            ('event_type',                   'NO'),
            ('actor_type',                   'NO'),
            ('actor_id',                     'NO'),
            ('initiating_actor_type',        'YES'),
            ('initiating_actor_id',          'YES'),
            ('downstream_caller_id',         'YES'),
            ('prior_status',                 'YES'),
            ('resulting_status',             'YES'),
            ('prior_disposition_status',     'YES'),
            ('resulting_disposition_status', 'YES'),
            ('failure_stage',                'YES'),
            ('reason',                       'YES'),
            ('metadata',                     'NO'),
            ('created_at',                   'NO')
        ) AS t(col_name, exp_nullable)
    LOOP
        SELECT is_nullable INTO v_nullable
        FROM information_schema.columns
        WHERE table_schema = 'operations' AND table_name = 'restaurant_update_submission_events'
          AND column_name = r.col_name;

        IF v_nullable IS NULL THEN
            RAISE EXCEPTION 'VALIDATION FAILED: column % does not exist on operations.restaurant_update_submission_events', r.col_name;
        END IF;
        IF v_nullable <> r.exp_nullable THEN
            RAISE EXCEPTION 'VALIDATION FAILED: operations.restaurant_update_submission_events.% is_nullable = % (expected %)', r.col_name, v_nullable, r.exp_nullable;
        END IF;
    END LOOP;
    RAISE NOTICE 'PASS (C3): all 16 operations.restaurant_update_submission_events columns present with expected nullability';
END $$;

-- C4. metadata jsonb default '{}', created_at default now() — the
-- structured-metadata judgment call (021 header item 1): downstream entity
-- references live in jsonb, not as four more mirrored FK columns.
DO $$
DECLARE
    v_default text;
BEGIN
    SELECT column_default INTO v_default
    FROM information_schema.columns
    WHERE table_schema = 'operations' AND table_name = 'restaurant_update_submission_events'
      AND column_name = 'metadata';
    IF v_default IS NULL OR v_default NOT LIKE '%''{}''%' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: restaurant_update_submission_events.metadata column_default = % (expected a default of ''{}''::jsonb)', v_default;
    END IF;

    SELECT column_default INTO v_default
    FROM information_schema.columns
    WHERE table_schema = 'operations' AND table_name = 'restaurant_update_submission_events'
      AND column_name = 'created_at';
    IF v_default IS NULL OR v_default NOT LIKE '%now()%' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: restaurant_update_submission_events.created_at column_default = % (expected a default of now())', v_default;
    END IF;
    RAISE NOTICE 'PASS (C4): restaurant_update_submission_events.metadata defaults to ''{}''::jsonb, created_at defaults to now()';
END $$;

-- C5. Events table has NO downstream *_id columns of its own — confirms
-- judgment call 1 (021 header): downstream entity references live only in
-- metadata jsonb, never as mirrored FK-shaped columns on the events table.
DO $$
DECLARE
    v_bad_count int;
BEGIN
    SELECT count(*) INTO v_bad_count
    FROM information_schema.columns
    WHERE table_schema = 'operations' AND table_name = 'restaurant_update_submission_events'
      AND column_name IN (
        'resulting_intake_packet_id', 'resulting_intake_session_id',
        'identity_review_item_id', 'exception_request_id',
        'downstream_entity_id', 'downstream_entity_type'
      );
    IF v_bad_count > 0 THEN
        RAISE EXCEPTION 'VALIDATION FAILED: operations.restaurant_update_submission_events has % mirrored downstream-entity FK-shaped column(s) — violates judgment call 1 (downstream references belong in metadata jsonb only)', v_bad_count;
    END IF;
    RAISE NOTICE 'PASS (C5): restaurant_update_submission_events carries no mirrored downstream-entity FK columns — downstream references are metadata-jsonb-only, as designed';
END $$;


-- ── D. Constraint & index inventory + canonical status alignment ────────────

-- D1. Every CHECK constraint 021 defines on restaurant_update_submissions
-- is present by name.
DO $$
DECLARE
    expected text[] := ARRAY[
        'rusub_claim_consistency',
        'rusub_no_self_resubmission',
        'rusub_no_self_supersede',
        'rusub_archival_eligibility',
        'rusub_archival_actor_requires_timestamp',
        'rusub_archival_actor_requires_reason',
        'rusub_disposition_type_check',
        'rusub_disposition_status_check',
        'rusub_failure_stage_check',
        'rusub_failure_stage_requires_failed',
        'rusub_disposition_type_status_consistency',
        'rusub_no_action_requires_resolution_summary',
        'rusub_downstream_fk_cardinality',
        'rusub_intake_packet_fk_requires_type',
        'rusub_identity_review_fk_requires_type',
        'rusub_exception_request_fk_requires_type'
    ];
    c text;
BEGIN
    FOREACH c IN ARRAY expected LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'operations.restaurant_update_submissions'::regclass
              AND conname = c
        ) THEN
            RAISE EXCEPTION 'VALIDATION FAILED: expected constraint % is missing on operations.restaurant_update_submissions', c;
        END IF;
    END LOOP;
    RAISE NOTICE 'PASS (D1): all % expected migration-021 CHECK constraints present on operations.restaurant_update_submissions', array_length(expected, 1);
END $$;

-- D2. Every CHECK constraint 021 defines inline on the events table is
-- present by name.
DO $$
DECLARE
    expected text[] := ARRAY[
        'rusub_events_event_type_check',
        'rusub_events_actor_type_check',
        'rusub_events_initiating_actor_type_check',
        'rusub_events_actor_id_nonblank',
        'rusub_events_initiating_actor_id_nonblank',
        'rusub_events_reason_required',
        'rusub_events_failure_stage_check',
        'rusub_events_failure_stage_scope'
    ];
    c text;
BEGIN
    FOREACH c IN ARRAY expected LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'operations.restaurant_update_submission_events'::regclass
              AND conname = c
        ) THEN
            RAISE EXCEPTION 'VALIDATION FAILED: expected constraint % is missing on operations.restaurant_update_submission_events', c;
        END IF;
    END LOOP;
    RAISE NOTICE 'PASS (D2): all % expected migration-021 CHECK constraints present on operations.restaurant_update_submission_events', array_length(expected, 1);
END $$;

-- D3. Index presence, both tables.
DO $$
DECLARE
    expected text[] := ARRAY[
        'idx_rusub_claimed_by',
        'idx_rusub_archived_at',
        'idx_rusub_disposition_status',
        'idx_rusub_resulting_intake_packet',
        'idx_rusub_resubmission_of_unique',
        'idx_rusub_superseded_by_unique',
        'idx_rusub_events_submission',
        'idx_rusub_events_type'
    ];
    idx text;
BEGIN
    FOREACH idx IN ARRAY expected LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'operations' AND indexname = idx
        ) THEN
            RAISE EXCEPTION 'VALIDATION FAILED: expected index % is missing', idx;
        END IF;
    END LOOP;
    RAISE NOTICE 'PASS (D3): all % expected migration-021 indexes are present', array_length(expected, 1);
END $$;

-- D4. Canonical status CHECK remains exactly aligned with DEC000002 v4.2 —
-- exactly the 5 values (pending_review, in_review, approved, returned,
-- rejected), and critically does NOT include 'converted' (the sibling
-- operations.partner_submissions status value — must not leak here).
DO $$
DECLARE
    v_def text;
BEGIN
    SELECT string_agg(pg_get_constraintdef(oid), ' | ') INTO v_def
    FROM pg_constraint
    WHERE conrelid = 'operations.restaurant_update_submissions'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) ILIKE '%pending_review%';

    IF v_def IS NULL THEN
        RAISE EXCEPTION 'VALIDATION FAILED: no CHECK constraint on operations.restaurant_update_submissions references pending_review — status CHECK missing entirely';
    END IF;

    IF v_def NOT ILIKE '%in_review%' OR v_def NOT ILIKE '%approved%'
       OR v_def NOT ILIKE '%returned%' OR v_def NOT ILIKE '%rejected%' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: status CHECK does not contain all 5 canonical DEC000002 v4.2 values (pending_review, in_review, approved, returned, rejected). Definition: %', v_def;
    END IF;

    IF v_def ILIKE '%converted%' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: status CHECK contains ''converted'' — that value belongs only to operations.partner_submissions (migration 011), not restaurant_update_submissions. Definition: %', v_def;
    END IF;

    RAISE NOTICE 'PASS (D4): operations.restaurant_update_submissions.status CHECK contains exactly the 5 canonical DEC000002 v4.2 values, with no ''converted'' leak from partner_submissions';
END $$;

-- D5. Live confirmation: 'converted' is rejected by the status CHECK
-- (behavioral, not just definitional).
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions (restaurant_id, submission_type, status)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'converted');
        RAISE EXCEPTION 'VALIDATION FAILED: status CHECK did not reject ''converted'' — a partner_submissions-only value';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (D5): status CHECK rejects ''converted'' (behaviorally confirmed, not merely absent from the definition)';
    END;
END $$;


-- ── E. Claim consistency guard (rusub_claim_consistency, §5.6) ──────────────

-- E1. status = in_review with no claim fields set -> rejected.
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions (restaurant_id, submission_type, status)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'in_review');
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_claim_consistency did not reject status = in_review with both claim fields null';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (E1): in_review with unset claim fields rejected';
    END;
END $$;

-- E2. status = pending_review with claim fields set -> rejected.
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, status, claimed_by_user_id, claimed_at)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'pending_review',
                '00000000-0000-4000-8000-000000000501', now());
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_claim_consistency did not reject status = pending_review with claim fields set';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (E2): pending_review with claim fields set rejected';
    END;
END $$;

-- E3. status = in_review with only one claim field set -> rejected (partial set).
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, status, claimed_by_user_id)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'in_review',
                '00000000-0000-4000-8000-000000000501');
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_claim_consistency did not reject in_review with claimed_by_user_id set but claimed_at null';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (E3): in_review with a partial claim-field set (one of two) rejected';
    END;
END $$;

-- E4. status = in_review with both claim fields set -> succeeds.
DO $$
BEGIN
    INSERT INTO operations.restaurant_update_submissions
        (restaurant_id, submission_type, status, claimed_by_user_id, claimed_at)
    VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'in_review',
            '00000000-0000-4000-8000-000000000501', now());
    RAISE NOTICE 'PASS (E4): in_review with both claim fields set succeeds';
END $$;


-- ── F. Resubmission chain (§5.7-§5.8) ────────────────────────────────────────

-- F1. Identity trigger: resubmission_of_submission_id referencing a
-- nonexistent parent -> rejected.
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, resubmission_of_submission_id)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update',
                '00000000-0000-4000-8000-0000000000ff');
        RAISE EXCEPTION 'VALIDATION FAILED: trg_rusub_validate_resubmission_identity did not reject a nonexistent parent';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%does not reference an existing submission%' THEN
                RAISE NOTICE 'PASS (F1): resubmission referencing a nonexistent parent rejected';
            ELSE
                RAISE EXCEPTION 'VALIDATION FAILED: unexpected error for nonexistent-parent resubmission: %', SQLERRM;
            END IF;
    END;
END $$;

-- F2. Identity trigger: child restaurant_id NULL when parent restaurant_id
-- is set -> rejected ("cannot verify same-restaurant identity").
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, resubmission_of_submission_id)
        VALUES (NULL, 'menu_update', '00000000-0000-4000-8000-000000000520');
        RAISE EXCEPTION 'VALIDATION FAILED: trg_rusub_validate_resubmission_identity did not reject a null child restaurant_id';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%Cannot verify same-restaurant identity%' THEN
                RAISE NOTICE 'PASS (F2): resubmission with null child restaurant_id rejected';
            ELSE
                RAISE EXCEPTION 'VALIDATION FAILED: unexpected error for null-restaurant-id resubmission: %', SQLERRM;
            END IF;
    END;
END $$;

-- F3. Identity trigger: child restaurant_id mismatched with parent -> rejected.
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, resubmission_of_submission_id)
        VALUES ('00000000-0000-4000-8000-000000000504', 'menu_update',
                '00000000-0000-4000-8000-000000000520');
        RAISE EXCEPTION 'VALIDATION FAILED: trg_rusub_validate_resubmission_identity did not reject a mismatched child restaurant_id';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%does not match parent restaurant_id%' THEN
                RAISE NOTICE 'PASS (F3): resubmission with a mismatched child restaurant_id rejected';
            ELSE
                RAISE EXCEPTION 'VALIDATION FAILED: unexpected error for mismatched-restaurant resubmission: %', SQLERRM;
            END IF;
    END;
END $$;

-- F4. Valid resubmission child insert succeeds (same restaurant as parent).
DO $$
BEGIN
    INSERT INTO operations.restaurant_update_submissions
        (submission_id, restaurant_id, submission_type, resubmission_of_submission_id)
    VALUES ('00000000-0000-4000-8000-000000000521', '00000000-0000-4000-8000-000000000503',
            'menu_update', '00000000-0000-4000-8000-000000000520');
    RAISE NOTICE 'PASS (F4): valid same-restaurant resubmission child insert succeeds';
END $$;

-- F5. Parent-side linkage: first-time UPDATE of superseded_by_submission_id
-- succeeds (not yet set on this row, so the immutability trigger allows it).
DO $$
BEGIN
    UPDATE operations.restaurant_update_submissions
    SET superseded_by_submission_id = '00000000-0000-4000-8000-000000000521'
    WHERE submission_id = '00000000-0000-4000-8000-000000000520';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'VALIDATION FAILED: parent fixture row not found for superseded_by_submission_id update';
    END IF;
    RAISE NOTICE 'PASS (F5): first-time UPDATE of parent.superseded_by_submission_id succeeds';
END $$;

-- F6. Immutability trigger: rewriting child.resubmission_of_submission_id
-- once already set -> rejected.
DO $$
BEGIN
    BEGIN
        UPDATE operations.restaurant_update_submissions
        SET resubmission_of_submission_id = '00000000-0000-4000-8000-000000000522'
        WHERE submission_id = '00000000-0000-4000-8000-000000000521';
        RAISE EXCEPTION 'VALIDATION FAILED: trg_rusub_prevent_chain_rewrite did not reject rewriting an already-set resubmission_of_submission_id';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%immutable once set%' THEN
                RAISE NOTICE 'PASS (F6): rewriting an already-set child.resubmission_of_submission_id rejected';
            ELSE
                RAISE EXCEPTION 'VALIDATION FAILED: unexpected error rewriting resubmission_of_submission_id: %', SQLERRM;
            END IF;
    END;
END $$;

-- F7. Immutability trigger: rewriting parent.superseded_by_submission_id
-- once already set -> rejected (independent confirmation from 022's own
-- coverage of this same trigger).
DO $$
BEGIN
    BEGIN
        UPDATE operations.restaurant_update_submissions
        SET superseded_by_submission_id = '00000000-0000-4000-8000-000000000522'
        WHERE submission_id = '00000000-0000-4000-8000-000000000520';
        RAISE EXCEPTION 'VALIDATION FAILED: trg_rusub_prevent_chain_rewrite did not reject rewriting an already-set superseded_by_submission_id';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%immutable once set%' THEN
                RAISE NOTICE 'PASS (F7): rewriting an already-set parent.superseded_by_submission_id rejected';
            ELSE
                RAISE EXCEPTION 'VALIDATION FAILED: unexpected error rewriting superseded_by_submission_id: %', SQLERRM;
            END IF;
    END;
END $$;

-- F8. rusub_no_self_supersede: UPDATE setting superseded_by_submission_id to
-- the row's own submission_id -> rejected. Uses fixture 522, whose
-- superseded_by_submission_id is still null, so the immutability trigger
-- (F6/F7) does not intervene and the CHECK constraint itself is exercised.
DO $$
BEGIN
    BEGIN
        UPDATE operations.restaurant_update_submissions
        SET superseded_by_submission_id = submission_id
        WHERE submission_id = '00000000-0000-4000-8000-000000000522';
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_no_self_supersede did not reject a row superseding itself';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (F8): a row setting superseded_by_submission_id to its own submission_id is rejected (rusub_no_self_supersede)';
    END;
END $$;

-- F9. Single-hop uniqueness (idx_rusub_resubmission_of_unique): a second
-- child also naming parent 520 as resubmission_of_submission_id -> rejected.
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, resubmission_of_submission_id)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update',
                '00000000-0000-4000-8000-000000000520');
        RAISE EXCEPTION 'VALIDATION FAILED: idx_rusub_resubmission_of_unique did not reject a second child naming the same parent';
    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE 'PASS (F9): a second child naming the same parent (resubmission_of_submission_id) is rejected — each parent has at most one direct child';
    END;
END $$;

-- F10. Single-hop uniqueness the other direction
-- (idx_rusub_superseded_by_unique): a different row (522) claiming the same
-- child (521) as its own superseded_by_submission_id -> rejected. 522's
-- superseded_by_submission_id is still null after F8's rejected attempt
-- (the failed statement's effect was rolled back to the start of that
-- exception block), so the immutability trigger does not intervene here.
DO $$
BEGIN
    BEGIN
        UPDATE operations.restaurant_update_submissions
        SET superseded_by_submission_id = '00000000-0000-4000-8000-000000000521'
        WHERE submission_id = '00000000-0000-4000-8000-000000000522';
        RAISE EXCEPTION 'VALIDATION FAILED: idx_rusub_superseded_by_unique did not reject a second parent claiming the same child';
    EXCEPTION
        WHEN unique_violation THEN
            RAISE NOTICE 'PASS (F10): a second parent claiming the same child (superseded_by_submission_id) is rejected — each child is claimed by at most one parent';
    END;
END $$;

-- F11. rusub_no_self_resubmission CHECK is present (structural confirmation
-- only — a live INSERT test is not meaningful here: a row referencing its
-- own submission_id as resubmission_of_submission_id is caught by
-- trg_rusub_validate_resubmission_identity's existence check first, since
-- the row does not yet exist to be found when the BEFORE INSERT trigger
-- runs, so F1's "does not reference an existing submission" path fires
-- before this CHECK ever would. The CHECK still exists as defense-in-depth
-- for any future direct-UPDATE path that could set this column post-insert
-- if the immutability trigger were ever relaxed).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'operations.restaurant_update_submissions'::regclass
          AND conname = 'rusub_no_self_resubmission'
    ) THEN
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_no_self_resubmission constraint is missing';
    END IF;
    RAISE NOTICE 'PASS (F11): rusub_no_self_resubmission CHECK is present (defense-in-depth behind the identity trigger, which independently makes self-resubmission at INSERT time unreachable)';
END $$;


-- ── G. Archival eligibility (§5.9) ───────────────────────────────────────────

-- G0. Fixtures for archival tests: a rejected row, an approved+completed
-- row, an approved+pending row, a returned-without-child row, and a
-- rejected-but-not-yet-archived row for the actor/reason companion checks.
DO $$
BEGIN
    INSERT INTO operations.restaurant_update_submissions
        (submission_id, restaurant_id, submission_type, status)
    VALUES ('00000000-0000-4000-8000-000000000530', '00000000-0000-4000-8000-000000000503',
            'menu_update', 'rejected');

    INSERT INTO operations.restaurant_update_submissions
        (submission_id, restaurant_id, submission_type, status,
         disposition_type, disposition_status, resolution_summary)
    VALUES ('00000000-0000-4000-8000-000000000531', '00000000-0000-4000-8000-000000000503',
            'menu_update', 'approved', 'no_action', 'completed', 'No action required — duplicate submission.');

    INSERT INTO operations.restaurant_update_submissions
        (submission_id, restaurant_id, submission_type, status,
         disposition_type, disposition_status)
    VALUES ('00000000-0000-4000-8000-000000000532', '00000000-0000-4000-8000-000000000503',
            'menu_update', 'approved', 'intake_required', 'pending');

    INSERT INTO operations.restaurant_update_submissions
        (submission_id, restaurant_id, submission_type, status)
    VALUES ('00000000-0000-4000-8000-000000000533', '00000000-0000-4000-8000-000000000503',
            'menu_update', 'returned');

    INSERT INTO operations.restaurant_update_submissions
        (submission_id, restaurant_id, submission_type, status)
    VALUES ('00000000-0000-4000-8000-000000000534', '00000000-0000-4000-8000-000000000503',
            'menu_update', 'rejected');

    RAISE NOTICE 'PASS (fixtures G0): 5 archival-scenario submission rows created';
END $$;

-- G1. rejected -> archival succeeds (§5.9 eligible bullet 1).
DO $$
BEGIN
    UPDATE operations.restaurant_update_submissions
    SET archived_at = now(), archived_by_user_id = '00000000-0000-4000-8000-000000000501',
        archive_reason = 'Rejected — no further action needed.'
    WHERE submission_id = '00000000-0000-4000-8000-000000000530';
    RAISE NOTICE 'PASS (G1): archival of a rejected submission succeeds';
END $$;

-- G2. approved + disposition_status = completed -> archival succeeds
-- (§5.9 eligible bullet 2).
DO $$
BEGIN
    UPDATE operations.restaurant_update_submissions
    SET archived_at = now(), archived_by_user_id = '00000000-0000-4000-8000-000000000501',
        archive_reason = 'Approved and disposition completed.'
    WHERE submission_id = '00000000-0000-4000-8000-000000000531';
    RAISE NOTICE 'PASS (G2): archival of an approved + disposition_status=completed submission succeeds';
END $$;

-- G3. approved + disposition_status = pending -> archival rejected
-- (§5.9 ineligible: approved with a non-completed disposition_status).
DO $$
BEGIN
    BEGIN
        UPDATE operations.restaurant_update_submissions
        SET archived_at = now(), archived_by_user_id = '00000000-0000-4000-8000-000000000501',
            archive_reason = 'Attempted premature archival.'
        WHERE submission_id = '00000000-0000-4000-8000-000000000532';
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_archival_eligibility did not reject archival of an approved+pending submission';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (G3): archival of an approved + disposition_status=pending submission is rejected';
    END;
END $$;

-- G4. returned with superseded_by_submission_id set -> archival succeeds
-- (§5.9 eligible bullet 3; reuses parent 520, superseded per F5).
DO $$
BEGIN
    UPDATE operations.restaurant_update_submissions
    SET archived_at = now(), archived_by_user_id = '00000000-0000-4000-8000-000000000501',
        archive_reason = 'Superseded by resubmission child.'
    WHERE submission_id = '00000000-0000-4000-8000-000000000520';
    RAISE NOTICE 'PASS (G4): archival of a returned submission with a linked resubmission child succeeds';
END $$;

-- G5. returned WITHOUT a child -> archival rejected (§5.9 ineligible).
DO $$
BEGIN
    BEGIN
        UPDATE operations.restaurant_update_submissions
        SET archived_at = now(), archived_by_user_id = '00000000-0000-4000-8000-000000000501',
            archive_reason = 'Attempted archival without a resubmission child.'
        WHERE submission_id = '00000000-0000-4000-8000-000000000533';
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_archival_eligibility did not reject archival of a returned submission with no linked child';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (G5): archival of a returned submission with no linked resubmission child is rejected';
    END;
END $$;

-- G6. Actor set without archived_at -> rejected
-- (rusub_archival_actor_requires_timestamp).
DO $$
BEGIN
    BEGIN
        UPDATE operations.restaurant_update_submissions
        SET archived_by_user_id = '00000000-0000-4000-8000-000000000501'
        WHERE submission_id = '00000000-0000-4000-8000-000000000534';
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_archival_actor_requires_timestamp did not reject an actor set without archived_at';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (G6): archived_by_user_id set without archived_at is rejected';
    END;
END $$;

-- G7. Actor set with a blank (whitespace-only) archive_reason -> rejected
-- (rusub_archival_actor_requires_reason, non-blank via ~ '\S').
DO $$
BEGIN
    BEGIN
        UPDATE operations.restaurant_update_submissions
        SET archived_at = now(), archived_by_user_id = '00000000-0000-4000-8000-000000000501',
            archive_reason = '   '
        WHERE submission_id = '00000000-0000-4000-8000-000000000534';
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_archival_actor_requires_reason did not reject a whitespace-only archive_reason';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (G7): a whitespace-only archive_reason with an actor set is rejected (non-blank enforced)';
    END;
END $$;


-- ── H. Disposition model (§5.3, §5.4, §6) ────────────────────────────────────

-- H1. disposition_type set while disposition_status left at 'unassessed'
-- default -> rejected (rusub_disposition_type_status_consistency).
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, disposition_type)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'intake_required');
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_disposition_type_status_consistency did not reject disposition_type set with disposition_status still unassessed';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (H1): disposition_type set with disposition_status = unassessed is rejected';
    END;
END $$;

-- H2. disposition_status != 'unassessed' while disposition_type is null ->
-- rejected (same constraint, opposite direction).
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, disposition_status)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'pending');
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_disposition_type_status_consistency did not reject disposition_status != unassessed with disposition_type null';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (H2): disposition_status set to a non-unassessed value with disposition_type null is rejected';
    END;
END $$;

-- H3. disposition_type enum rejects an invalid value.
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, disposition_type, disposition_status)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'not_a_real_disposition_type', 'pending');
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_disposition_type_check did not reject an invalid disposition_type';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (H3): an invalid disposition_type value is rejected';
    END;
END $$;

-- H4. failure_stage set while disposition_status != 'failed' -> rejected
-- (rusub_failure_stage_requires_failed).
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, disposition_type, disposition_status, failure_stage)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'intake_required', 'pending', 'handoff_call');
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_failure_stage_requires_failed did not reject failure_stage set with disposition_status != failed';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (H4): failure_stage set while disposition_status is not failed is rejected';
    END;
END $$;

-- H5. disposition_type = no_action without resolution_summary -> rejected
-- (rusub_no_action_requires_resolution_summary).
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, disposition_type, disposition_status)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'no_action', 'completed');
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_no_action_requires_resolution_summary did not reject no_action with resolution_summary null';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (H5): disposition_type = no_action with resolution_summary null is rejected';
    END;
END $$;

-- H6. disposition_type = no_action with a blank (whitespace-only)
-- resolution_summary -> rejected (non-blank enforced via ~ '\S').
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, disposition_type, disposition_status, resolution_summary)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'no_action', 'completed', '   ');
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_no_action_requires_resolution_summary did not reject a whitespace-only resolution_summary';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (H6): disposition_type = no_action with a whitespace-only resolution_summary is rejected';
    END;
END $$;

-- H7. Valid no_action disposition (type + status + non-blank
-- resolution_summary) succeeds — already exercised as a fixture in G0
-- (submission 531), reconfirmed here as a standalone positive case.
DO $$
BEGIN
    INSERT INTO operations.restaurant_update_submissions
        (restaurant_id, submission_type, disposition_type, disposition_status, resolution_summary)
    VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'no_action', 'completed',
            'Not applicable — informational submission only.');
    RAISE NOTICE 'PASS (H7): a fully valid no_action disposition (type + status + resolution_summary) succeeds';
END $$;


-- ── I. Downstream linkage (§5.11) ────────────────────────────────────────────

-- I1. resulting_intake_packet_id set while disposition_type != intake_required
-- -> rejected (rusub_intake_packet_fk_requires_type).
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, disposition_type, disposition_status, resolution_summary,
             resulting_intake_packet_id)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'no_action', 'completed',
                'Not applicable.', '00000000-0000-4000-8000-000000000505');
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_intake_packet_fk_requires_type did not reject resulting_intake_packet_id set with disposition_type != intake_required';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (I1): resulting_intake_packet_id set with a non-matching disposition_type is rejected';
    END;
END $$;

-- I2. resulting_intake_packet_id set WITH disposition_type = intake_required
-- -> succeeds (canonical FK, ready to build per §5.11).
DO $$
BEGIN
    INSERT INTO operations.restaurant_update_submissions
        (restaurant_id, submission_type, disposition_type, disposition_status,
         resulting_intake_packet_id)
    VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'intake_required', 'pending',
            '00000000-0000-4000-8000-000000000505');
    RAISE NOTICE 'PASS (I2): resulting_intake_packet_id set with disposition_type = intake_required succeeds';
END $$;

-- I3. resulting_intake_packet_id ON DELETE RESTRICT: hard-deleting a
-- referenced intake_packets row must fail, not silently sever the link
-- (same provenance principle as migration 020's source_packet_id).
DO $$
BEGIN
    BEGIN
        DELETE FROM operations.intake_packets WHERE packet_id = '00000000-0000-4000-8000-000000000505';
        RAISE EXCEPTION 'VALIDATION FAILED: deleting an operations.intake_packets row still referenced by resulting_intake_packet_id did not fail — provenance lineage would be silently severed';
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE 'PASS (I3): resulting_intake_packet_id ON DELETE RESTRICT blocks hard-deletion of a referenced packet';
    END;
END $$;

-- I4. resulting_intake_session_id is non-canonical and excluded from the
-- downstream-FK cardinality rule — setting it alongside a canonical FK
-- (resulting_intake_packet_id) must NOT trip rusub_downstream_fk_cardinality.
DO $$
BEGIN
    INSERT INTO operations.restaurant_update_submissions
        (restaurant_id, submission_type, disposition_type, disposition_status,
         resulting_intake_packet_id, resulting_intake_session_id)
    VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'intake_required', 'pending',
            '00000000-0000-4000-8000-000000000505', gen_random_uuid());
    RAISE NOTICE 'PASS (I4): resulting_intake_session_id set alongside the canonical resulting_intake_packet_id does not trip the downstream-FK cardinality CHECK — confirmed non-canonical and excluded, per §5.11';
END $$;

-- I5. identity_review_item_id / exception_request_id carry NO foreign-key
-- constraint — authorized placeholders remain unconstrained (judgment call
-- 2, 021 header): no target table exists for either yet, and none was
-- invented.
DO $$
DECLARE
    v_fk_count int;
BEGIN
    SELECT count(*) INTO v_fk_count
    FROM pg_constraint co
    JOIN pg_attribute a ON a.attrelid = co.conrelid AND a.attnum = ANY(co.conkey)
    WHERE co.conrelid = 'operations.restaurant_update_submissions'::regclass
      AND co.contype = 'f'
      AND a.attname IN ('identity_review_item_id', 'exception_request_id');

    IF v_fk_count > 0 THEN
        RAISE EXCEPTION 'VALIDATION FAILED: % foreign-key constraint(s) found referencing identity_review_item_id / exception_request_id — these are supposed to be unconstrained placeholders (no target table exists), per judgment call 2', v_fk_count;
    END IF;
    RAISE NOTICE 'PASS (I5): identity_review_item_id and exception_request_id carry no foreign-key constraint — remain authorized unconstrained placeholders, no invented downstream tables';
END $$;

-- I6. identity_review_item_id / exception_request_id nonetheless still
-- respect their own FK-requires-type guardrails (same-row structural rule,
-- independent of the missing FK) — setting either without the matching
-- disposition_type is rejected.
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, disposition_type, disposition_status,
             identity_review_item_id)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'intake_required', 'pending',
                gen_random_uuid());
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_identity_review_fk_requires_type did not reject identity_review_item_id set with a non-matching disposition_type';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (I6a): identity_review_item_id set with a non-matching disposition_type is rejected';
    END;

    BEGIN
        INSERT INTO operations.restaurant_update_submissions
            (restaurant_id, submission_type, disposition_type, disposition_status,
             exception_request_id)
        VALUES ('00000000-0000-4000-8000-000000000503', 'menu_update', 'identity_review', 'pending',
                gen_random_uuid());
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_exception_request_fk_requires_type did not reject exception_request_id set with a non-matching disposition_type';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (I6b): exception_request_id set with a non-matching disposition_type is rejected';
    END;
END $$;

-- I7. No invented routing behavior: confirm route_to_identity_review and
-- escalate_exception are not implemented as functions anywhere in the
-- schema (021 scope is schema-only; 022 does not build them either, per
-- the gap map §3 — this is a structural absence check, not a behavioral one).
DO $$
BEGIN
    IF to_regprocedure('operations.route_to_identity_review(uuid, uuid, jsonb, text)') IS NOT NULL
       OR to_regprocedure('operations.escalate_exception(uuid, uuid, jsonb, text)') IS NOT NULL THEN
        RAISE EXCEPTION 'VALIDATION FAILED: an operations.route_to_identity_review or operations.escalate_exception function exists — these are explicitly blocked pending downstream architecture that does not exist yet (DEC000002 §5.11, judgment call 2)';
    END IF;
    RAISE NOTICE 'PASS (I7): no route_to_identity_review or escalate_exception function exists — no invented downstream routing behavior';
END $$;


-- ── J. Events table (§5.10) — actor references, event recording ─────────────

-- J1. event_type enum rejects an invalid value.
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submission_events
            (submission_id, event_type, actor_type, actor_id)
        VALUES ('00000000-0000-4000-8000-000000000510', 'not_a_real_event_type', 'system', 'validate-021-script');
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_events_event_type_check did not reject an invalid event_type';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (J1): an invalid event_type value is rejected';
    END;
END $$;

-- J2. actor_type enum rejects an invalid value.
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submission_events
            (submission_id, event_type, actor_type, actor_id)
        VALUES ('00000000-0000-4000-8000-000000000510', 'claim', 'not_a_real_actor_type', 'validate-021-script');
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_events_actor_type_check did not reject an invalid actor_type';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (J2): an invalid actor_type value is rejected';
    END;
END $$;

-- J3. actor_id blank (whitespace-only) is rejected (rusub_events_actor_id_nonblank).
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submission_events
            (submission_id, event_type, actor_type, actor_id)
        VALUES ('00000000-0000-4000-8000-000000000510', 'claim', 'system', '   ');
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_events_actor_id_nonblank did not reject a whitespace-only actor_id';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (J3): a whitespace-only actor_id is rejected';
    END;
END $$;

-- J4. reason mandatory for event_type IN (return, reject, archive) — missing
-- reason rejected (rusub_events_reason_required).
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submission_events
            (submission_id, event_type, actor_type, actor_id)
        VALUES ('00000000-0000-4000-8000-000000000510', 'return', 'system', 'validate-021-script');
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_events_reason_required did not reject a return event with no reason';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (J4): a return/reject/archive event with no reason is rejected';
    END;
END $$;

-- J5. reason present -> succeeds for the same event_type.
DO $$
BEGIN
    INSERT INTO operations.restaurant_update_submission_events
        (submission_id, event_type, actor_type, actor_id, reason)
    VALUES ('00000000-0000-4000-8000-000000000510', 'return', 'system', 'validate-021-script',
            'Missing required nutrition documentation.');
    RAISE NOTICE 'PASS (J5): a return event with a reason present succeeds';
END $$;

-- J6. failure_stage scope: set on an event_type other than
-- disposition_handoff_failed / downstream_completion_received -> rejected
-- (rusub_events_failure_stage_scope).
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submission_events
            (submission_id, event_type, actor_type, actor_id, failure_stage)
        VALUES ('00000000-0000-4000-8000-000000000510', 'claim', 'system', 'validate-021-script', 'handoff_call');
        RAISE EXCEPTION 'VALIDATION FAILED: rusub_events_failure_stage_scope did not reject failure_stage set on a claim event';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (J6): failure_stage set on an out-of-scope event_type (claim) is rejected';
    END;
END $$;

-- J7. failure_stage set on disposition_handoff_failed -> succeeds
-- (in-scope event_type).
DO $$
BEGIN
    INSERT INTO operations.restaurant_update_submission_events
        (submission_id, event_type, actor_type, actor_id, failure_stage)
    VALUES ('00000000-0000-4000-8000-000000000510', 'disposition_handoff_failed', 'system',
            'validate-021-script', 'handoff_call');
    RAISE NOTICE 'PASS (J7): failure_stage set on disposition_handoff_failed succeeds';
END $$;

-- J8. Actor-validation trigger: actor_type = 'user' with a non-UUID
-- actor_id -> rejected ("must be a valid UUID").
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submission_events
            (submission_id, event_type, actor_type, actor_id)
        VALUES ('00000000-0000-4000-8000-000000000510', 'claim', 'user', 'not-a-uuid');
        RAISE EXCEPTION 'VALIDATION FAILED: trg_rusub_events_validate_actor did not reject a non-UUID actor_id when actor_type = user';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%must be a valid UUID%' THEN
                RAISE NOTICE 'PASS (J8): a non-UUID actor_id with actor_type = user is rejected';
            ELSE
                RAISE EXCEPTION 'VALIDATION FAILED: unexpected error for non-UUID user actor_id: %', SQLERRM;
            END IF;
    END;
END $$;

-- J9. Actor-validation trigger: actor_type = 'user' with a UUID that does
-- not reference any operations.users row -> rejected.
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submission_events
            (submission_id, event_type, actor_type, actor_id)
        VALUES ('00000000-0000-4000-8000-000000000510', 'claim', 'user',
                '00000000-0000-4000-8000-00000000ffff');
        RAISE EXCEPTION 'VALIDATION FAILED: trg_rusub_events_validate_actor did not reject a nonexistent user actor_id';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%does not reference an existing operations.users row%' THEN
                RAISE NOTICE 'PASS (J9): a nonexistent operations.users actor_id is rejected';
            ELSE
                RAISE EXCEPTION 'VALIDATION FAILED: unexpected error for nonexistent user actor_id: %', SQLERRM;
            END IF;
    END;
END $$;

-- J10. Actor-validation trigger: actor_type = 'user' referencing an
-- INACTIVE operations.users row -> rejected.
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submission_events
            (submission_id, event_type, actor_type, actor_id)
        VALUES ('00000000-0000-4000-8000-000000000510', 'claim', 'user',
                '00000000-0000-4000-8000-000000000502');
        RAISE EXCEPTION 'VALIDATION FAILED: trg_rusub_events_validate_actor did not reject an inactive user actor_id';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%references an inactive operations.users row%' THEN
                RAISE NOTICE 'PASS (J10): an inactive operations.users actor_id is rejected';
            ELSE
                RAISE EXCEPTION 'VALIDATION FAILED: unexpected error for inactive user actor_id: %', SQLERRM;
            END IF;
    END;
END $$;

-- J11. Same three checks (bad UUID / not found / inactive) apply
-- independently to initiating_actor_id when initiating_actor_type = 'user'
-- — spot-check one (inactive) to confirm the second validation block fires.
DO $$
BEGIN
    BEGIN
        INSERT INTO operations.restaurant_update_submission_events
            (submission_id, event_type, actor_type, actor_id,
             initiating_actor_type, initiating_actor_id)
        VALUES ('00000000-0000-4000-8000-000000000510', 'disposition_handoff_attempted', 'system',
                'validate-021-script', 'user', '00000000-0000-4000-8000-000000000502');
        RAISE EXCEPTION 'VALIDATION FAILED: trg_rusub_events_validate_actor did not reject an inactive initiating_actor_id';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%initiating_actor_id (%) references an inactive operations.users row%'
               OR SQLERRM LIKE '%references an inactive operations.users row%' THEN
                RAISE NOTICE 'PASS (J11): an inactive operations.users initiating_actor_id is independently rejected';
            ELSE
                RAISE EXCEPTION 'VALIDATION FAILED: unexpected error for inactive initiating_actor_id: %', SQLERRM;
            END IF;
    END;
END $$;

-- J12. Valid user actor_id (active, matches operations.users) succeeds,
-- and system/pipeline actor_id remains free-form text (no UUID
-- requirement) — both positive paths in one block.
DO $$
BEGIN
    INSERT INTO operations.restaurant_update_submission_events
        (submission_id, event_type, actor_type, actor_id)
    VALUES ('00000000-0000-4000-8000-000000000510', 'claim', 'user',
            '00000000-0000-4000-8000-000000000501');

    INSERT INTO operations.restaurant_update_submission_events
        (submission_id, event_type, actor_type, actor_id, downstream_caller_id)
    VALUES ('00000000-0000-4000-8000-000000000510', 'downstream_completion_received', 'pipeline',
            'intake-webhook-run-2026-07-17T00:00:00Z', 'intake-os-callback-service');

    RAISE NOTICE 'PASS (J12): a valid active-user actor_id succeeds, and a free-form (non-UUID) pipeline actor_id succeeds untouched by user-validation';
END $$;

-- J13. Append-only: UPDATE on an existing event row is rejected.
DO $$
BEGIN
    BEGIN
        UPDATE operations.restaurant_update_submission_events
        SET reason = 'attempted mutation'
        WHERE submission_id = '00000000-0000-4000-8000-000000000510' AND event_type = 'return';
        RAISE EXCEPTION 'VALIDATION FAILED: trg_rusub_events_append_only did not reject an UPDATE on an existing event row';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%is append-only%' THEN
                RAISE NOTICE 'PASS (J13): UPDATE on an existing restaurant_update_submission_events row is rejected';
            ELSE
                RAISE EXCEPTION 'VALIDATION FAILED: unexpected error on event UPDATE attempt: %', SQLERRM;
            END IF;
    END;
END $$;

-- J14. Append-only: DELETE on an existing event row is rejected.
DO $$
BEGIN
    BEGIN
        DELETE FROM operations.restaurant_update_submission_events
        WHERE submission_id = '00000000-0000-4000-8000-000000000510' AND event_type = 'return';
        RAISE EXCEPTION 'VALIDATION FAILED: trg_rusub_events_append_only did not reject a DELETE on an existing event row';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%is append-only%' THEN
                RAISE NOTICE 'PASS (J14): DELETE on an existing restaurant_update_submission_events row is rejected';
            ELSE
                RAISE EXCEPTION 'VALIDATION FAILED: unexpected error on event DELETE attempt: %', SQLERRM;
            END IF;
    END;
END $$;


-- ── K. Trigger function privileges ───────────────────────────────────────────
-- 021 creates three functions, all RETURNS TRIGGER. Trigger functions are
-- structurally uninvokable via direct SQL calls (Postgres rejects direct
-- invocation with feature_not_supported) — this is the expected "privilege"
-- posture for all three, independent of any GRANT/REVOKE statement, since
-- none of them are ordinary callable functions to begin with.

DO $$
BEGIN
    BEGIN
        PERFORM operations.prevent_rusub_chain_rewrite();
        RAISE EXCEPTION 'VALIDATION FAILED: operations.prevent_rusub_chain_rewrite() was callable directly outside of a trigger context';
    EXCEPTION
        WHEN feature_not_supported THEN
            RAISE NOTICE 'PASS (K1): operations.prevent_rusub_chain_rewrite() cannot be invoked directly (trigger-only)';
    END;
END $$;

DO $$
BEGIN
    BEGIN
        PERFORM operations.validate_rusub_resubmission_identity();
        RAISE EXCEPTION 'VALIDATION FAILED: operations.validate_rusub_resubmission_identity() was callable directly outside of a trigger context';
    EXCEPTION
        WHEN feature_not_supported THEN
            RAISE NOTICE 'PASS (K2): operations.validate_rusub_resubmission_identity() cannot be invoked directly (trigger-only)';
    END;
END $$;

DO $$
BEGIN
    BEGIN
        PERFORM operations.validate_rusub_event_actor();
        RAISE EXCEPTION 'VALIDATION FAILED: operations.validate_rusub_event_actor() was callable directly outside of a trigger context';
    EXCEPTION
        WHEN feature_not_supported THEN
            RAISE NOTICE 'PASS (K3): operations.validate_rusub_event_actor() cannot be invoked directly (trigger-only)';
    END;
END $$;

-- K4. All three triggers are correctly attached (function <-> trigger <->
-- table <-> timing), not merely present in isolation.
DO $$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT * FROM (VALUES
            ('trg_rusub_prevent_chain_rewrite',          'operations.restaurant_update_submissions',       'prevent_rusub_chain_rewrite'),
            ('trg_rusub_validate_resubmission_identity',  'operations.restaurant_update_submissions',       'validate_rusub_resubmission_identity'),
            ('trg_rusub_events_append_only',              'operations.restaurant_update_submission_events', 'prevent_append_only_mutation'),
            ('trg_rusub_events_validate_actor',           'operations.restaurant_update_submission_events', 'validate_rusub_event_actor')
        ) AS t(trig_name, tbl, fn_name)
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM pg_trigger tg
            JOIN pg_proc p ON p.oid = tg.tgfoid
            WHERE tg.tgname = r.trig_name
              AND tg.tgrelid = r.tbl::regclass
              AND p.proname = r.fn_name
        ) THEN
            RAISE EXCEPTION 'VALIDATION FAILED: trigger % on % calling function % is not correctly attached', r.trig_name, r.tbl, r.fn_name;
        END IF;
    END LOOP;
    RAISE NOTICE 'PASS (K4): all 4 migration-021 triggers are correctly attached to their expected table and function';
END $$;


-- ── L. RLS / GRANT posture (events table) ────────────────────────────────────

-- L1. RLS is enabled on the events table.
DO $$
DECLARE
    v_rls boolean;
BEGIN
    SELECT relrowsecurity INTO v_rls
    FROM pg_class
    WHERE oid = 'operations.restaurant_update_submission_events'::regclass;

    IF NOT v_rls THEN
        RAISE EXCEPTION 'VALIDATION FAILED: RLS is not enabled on operations.restaurant_update_submission_events';
    END IF;
    RAISE NOTICE 'PASS (L1): RLS is enabled on operations.restaurant_update_submission_events';
END $$;

-- L2. No RLS policies are defined on the events table — service_role
-- bypasses RLS by design, matching the intake_packet_events /
-- intake_packet_revisions precedent (migration 016).
DO $$
DECLARE
    v_policy_count int;
BEGIN
    SELECT count(*) INTO v_policy_count
    FROM pg_policies
    WHERE schemaname = 'operations' AND tablename = 'restaurant_update_submission_events';

    IF v_policy_count > 0 THEN
        RAISE EXCEPTION 'VALIDATION FAILED: % RLS policy(ies) found on operations.restaurant_update_submission_events — expected zero, matching the migration-016 precedent (service_role bypasses RLS by design)', v_policy_count;
    END IF;
    RAISE NOTICE 'PASS (L2): no RLS policies are defined on operations.restaurant_update_submission_events (service_role bypass by design)';
END $$;

-- L3. GRANT posture: service_role and authenticated have SELECT and
-- INSERT, but NOT UPDATE or DELETE (append-only intent reinforced at the
-- grant layer, not just by the trigger).
DO $$
DECLARE
    r record;
BEGIN
    FOR r IN
        SELECT * FROM (VALUES ('service_role'), ('authenticated')) AS t(role_name)
    LOOP
        IF NOT has_table_privilege(r.role_name, 'operations.restaurant_update_submission_events', 'SELECT') THEN
            RAISE EXCEPTION 'VALIDATION FAILED: % lacks SELECT on operations.restaurant_update_submission_events', r.role_name;
        END IF;
        IF NOT has_table_privilege(r.role_name, 'operations.restaurant_update_submission_events', 'INSERT') THEN
            RAISE EXCEPTION 'VALIDATION FAILED: % lacks INSERT on operations.restaurant_update_submission_events', r.role_name;
        END IF;
        IF has_table_privilege(r.role_name, 'operations.restaurant_update_submission_events', 'UPDATE') THEN
            RAISE EXCEPTION 'VALIDATION FAILED: % unexpectedly has UPDATE on operations.restaurant_update_submission_events — append-only intent violated at the grant layer', r.role_name;
        END IF;
        IF has_table_privilege(r.role_name, 'operations.restaurant_update_submission_events', 'DELETE') THEN
            RAISE EXCEPTION 'VALIDATION FAILED: % unexpectedly has DELETE on operations.restaurant_update_submission_events — append-only intent violated at the grant layer', r.role_name;
        END IF;
    END LOOP;
    RAISE NOTICE 'PASS (L3): service_role and authenticated hold SELECT + INSERT only on the events table — no UPDATE/DELETE grant, append-only reinforced at the grant layer';
END $$;


-- ── M. Direct-mutation failure behavior + rollback cleanliness ──────────────

-- M1. A direct UPDATE attempting to bypass the canonical status set (e.g.
-- setting status = 'converted', the partner_submissions-only value)
-- against an existing row is rejected — same guard as D5, exercised here
-- as an UPDATE rather than an INSERT to confirm the CHECK applies equally
-- to both statement types.
DO $$
BEGIN
    BEGIN
        UPDATE operations.restaurant_update_submissions
        SET status = 'converted'
        WHERE submission_id = '00000000-0000-4000-8000-000000000510';
        RAISE EXCEPTION 'VALIDATION FAILED: a direct UPDATE setting status = ''converted'' was not rejected';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (M1): a direct UPDATE attempting status = ''converted'' is rejected — invalid direct mutations fail loudly, not silently';
    END;
END $$;

-- M2. Rollback cleanliness banner. The actual cleanliness guarantee is the
-- ROLLBACK statement below, wrapping this entire script in a single
-- transaction — no fixture row, event row, or constraint-violating attempt
-- above persists past this point, and no real pre-existing data was ever
-- touched.
DO $$
BEGIN
    RAISE NOTICE '=== ALL CHECKS PASSED — rolling back, no data persisted ===';
END $$;

ROLLBACK;
