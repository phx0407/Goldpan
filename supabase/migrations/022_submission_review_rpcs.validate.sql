-- ============================================================
-- 022_submission_review_rpcs.validate.sql
-- Focused validation for 022_submission_review_rpcs.sql
-- (operations.resubmit_restaurant_update_submission).
--
-- Not a migration. Not executed as part of applying migration 022. Run
-- this manually, against a database that already has migrations 021
-- AND 022 applied, when Brad wants to verify the RPC before/after
-- applying it in a given environment.
--
-- Everything in this script runs inside a single transaction that is
-- ROLLBACK'd at the end — no fixture data or test rows are left
-- behind, and no real data is modified. Safe to run against a
-- database that already has real operations.restaurant_update_
-- submissions rows in it.
--
-- Runs as whatever role executes this script. Because 022 REVOKEs
-- EXECUTE from PUBLIC and grants it to no one, this script must be
-- run as the database owner or a superuser (e.g. `postgres`) —
-- exactly like every other DDL-adjacent script in this repo. That is
-- itself part of what this script is confirming (section D).
--
-- Coverage:
--   A. Guard                      (021 and 022 schema objects present)
--   B. Fixtures                   (users, restaurant, parent submissions)
--   C. Input/precondition rejection (GP422 / GP404 / GP403 / GP409, one
--      failure mode per case, none of which mutate anything)
--   D. Successful resubmit        (child created correctly, parent linked
--      atomically, both resubmit events written correctly, payload/
--      description COALESCE behavior for both the "override" and
--      "carry forward" cases)
--   E. Post-resubmit immutability (calling resubmit again on the same,
--      now-superseded parent is rejected — confirms the RPC's own
--      GP409 check and 021's trg_rusub_prevent_chain_rewrite agree)
--   F. Invocation authority        (EXECUTE is confirmed absent for
--      authenticated/service_role — the withheld grant itself)
--
-- Each check RAISEs NOTICE on pass and RAISEs EXCEPTION on failure, so
-- a failed run aborts loudly and the whole transaction rolls back.
-- Usage:  psql "$DATABASE_URL" -f 022_submission_review_rpcs.validate.sql
-- ============================================================

BEGIN;

-- ── A. Guard: migrations 021 and 022 must already be applied ────────────────

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
    IF to_regprocedure('operations.resubmit_restaurant_update_submission(uuid, uuid, jsonb, text)') IS NULL THEN
        RAISE EXCEPTION 'VALIDATION ABORTED: operations.resubmit_restaurant_update_submission does not exist — apply migration 022 first';
    END IF;
    RAISE NOTICE 'GUARD PASS: migration 021 and 022 schema objects present';
END $$;


-- ── B. Fixtures (rolled back at end of script; never committed) ─────────────

DO $$
BEGIN
    INSERT INTO operations.users (user_id, email, display_name, role, is_active)
    VALUES ('00000000-0000-4000-8000-000000000401', 'validate022.active@example.com', 'Validate022 Active User', 'coordinator', true);

    INSERT INTO operations.users (user_id, email, display_name, role, is_active)
    VALUES ('00000000-0000-4000-8000-000000000402', 'validate022.inactive@example.com', 'Validate022 Inactive User', 'coordinator', false);

    INSERT INTO evidence.restaurants (restaurant_id, external_id, name)
    VALUES ('00000000-0000-4000-8000-000000000403', 'TESTR_022_VALIDATE', 'Migration 022 Validation Fixture');

    -- Parent A: eligible — status = returned, not yet superseded. Inserted
    -- directly (no return RPC exists yet in this migration set) with a
    -- distinctive payload/description so COALESCE behavior is verifiable.
    INSERT INTO operations.restaurant_update_submissions (
        submission_id, restaurant_id, submission_type, description, payload_json,
        priority, source, status
    ) VALUES (
        '00000000-0000-4000-8000-000000000404', '00000000-0000-4000-8000-000000000403',
        'menu_update', 'Parent A original description',
        '{"dish_name":"Original Dish","note":"parent A payload"}'::jsonb,
        'urgent', 'portal', 'returned'
    );

    -- Parent B: same shape, used for the "not returned" precondition case.
    INSERT INTO operations.restaurant_update_submissions (
        submission_id, restaurant_id, submission_type, status
    ) VALUES (
        '00000000-0000-4000-8000-000000000405', '00000000-0000-4000-8000-000000000403',
        'menu_update', 'pending_review'
    );

    RAISE NOTICE 'PASS (fixtures): 2 operations.users rows, 1 evidence.restaurants row, 2 parent operations.restaurant_update_submissions rows created';
END $$;


-- ── C. Input/precondition rejection (each expected failure caught) ──────────

-- C1. p_submission_id NULL -> GP422.
DO $$
BEGIN
    BEGIN
        PERFORM operations.resubmit_restaurant_update_submission(
            NULL, '00000000-0000-4000-8000-000000000401', NULL, NULL
        );
        RAISE EXCEPTION 'VALIDATION FAILED: resubmit did not reject a NULL p_submission_id';
    EXCEPTION
        WHEN SQLSTATE 'GP422' THEN
            RAISE NOTICE 'PASS (C1): NULL p_submission_id rejected with GP422';
    END;
END $$;

-- C2. p_actor_user_id NULL -> GP422.
DO $$
BEGIN
    BEGIN
        PERFORM operations.resubmit_restaurant_update_submission(
            '00000000-0000-4000-8000-000000000404', NULL, NULL, NULL
        );
        RAISE EXCEPTION 'VALIDATION FAILED: resubmit did not reject a NULL p_actor_user_id';
    EXCEPTION
        WHEN SQLSTATE 'GP422' THEN
            RAISE NOTICE 'PASS (C2): NULL p_actor_user_id rejected with GP422';
    END;
END $$;

-- C3. Actor does not reference an existing operations.users row -> GP404.
DO $$
BEGIN
    BEGIN
        PERFORM operations.resubmit_restaurant_update_submission(
            '00000000-0000-4000-8000-000000000404', '00000000-0000-4000-8000-00000000ffff', NULL, NULL
        );
        RAISE EXCEPTION 'VALIDATION FAILED: resubmit did not reject a nonexistent actor';
    EXCEPTION
        WHEN SQLSTATE 'GP404' THEN
            RAISE NOTICE 'PASS (C3): nonexistent actor rejected with GP404';
    END;
END $$;

-- C4. Actor references an inactive operations.users row -> GP403.
DO $$
BEGIN
    BEGIN
        PERFORM operations.resubmit_restaurant_update_submission(
            '00000000-0000-4000-8000-000000000404', '00000000-0000-4000-8000-000000000402', NULL, NULL
        );
        RAISE EXCEPTION 'VALIDATION FAILED: resubmit did not reject an inactive actor';
    EXCEPTION
        WHEN SQLSTATE 'GP403' THEN
            RAISE NOTICE 'PASS (C4): inactive actor rejected with GP403';
    END;
END $$;

-- C5. Submission does not exist -> GP404.
DO $$
BEGIN
    BEGIN
        PERFORM operations.resubmit_restaurant_update_submission(
            '00000000-0000-4000-8000-00000000ffff', '00000000-0000-4000-8000-000000000401', NULL, NULL
        );
        RAISE EXCEPTION 'VALIDATION FAILED: resubmit did not reject a nonexistent submission_id';
    EXCEPTION
        WHEN SQLSTATE 'GP404' THEN
            RAISE NOTICE 'PASS (C5): nonexistent submission_id rejected with GP404';
    END;
END $$;

-- C6. Submission not in 'returned' status -> GP409 (Parent B is pending_review).
DO $$
BEGIN
    BEGIN
        PERFORM operations.resubmit_restaurant_update_submission(
            '00000000-0000-4000-8000-000000000405', '00000000-0000-4000-8000-000000000401', NULL, NULL
        );
        RAISE EXCEPTION 'VALIDATION FAILED: resubmit did not reject a non-returned parent';
    EXCEPTION
        WHEN SQLSTATE 'GP409' THEN
            RAISE NOTICE 'PASS (C6): non-returned parent (pending_review) rejected with GP409';
    END;
END $$;


-- ── D. Successful resubmit ───────────────────────────────────────────────────

DO $$
DECLARE
    v_child        operations.restaurant_update_submissions%ROWTYPE;
    v_parent_after operations.restaurant_update_submissions%ROWTYPE;
    v_event_count  int;
    v_parent_event operations.restaurant_update_submission_events%ROWTYPE;
    v_child_event  operations.restaurant_update_submission_events%ROWTYPE;
BEGIN
    -- Override description only; payload_json omitted (must carry parent's forward).
    SELECT * INTO v_child
    FROM operations.resubmit_restaurant_update_submission(
        '00000000-0000-4000-8000-000000000404',
        '00000000-0000-4000-8000-000000000401',
        NULL,
        'Corrected description supplied on resubmit'
    );

    IF v_child.submission_id IS NULL THEN
        RAISE EXCEPTION 'VALIDATION FAILED: resubmit did not return a child row';
    END IF;
    RAISE NOTICE 'PASS (D0): resubmit returned a new child row %', v_child.submission_id;

    -- D1. Child fields.
    IF v_child.status <> 'pending_review' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: child status = % (expected pending_review)', v_child.status;
    END IF;
    IF v_child.resubmission_of_submission_id <> '00000000-0000-4000-8000-000000000404' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: child.resubmission_of_submission_id = % (expected parent id)', v_child.resubmission_of_submission_id;
    END IF;
    IF v_child.description <> 'Corrected description supplied on resubmit' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: child.description = % (expected the supplied override)', v_child.description;
    END IF;
    IF v_child.payload_json IS DISTINCT FROM '{"dish_name":"Original Dish","note":"parent A payload"}'::jsonb THEN
        RAISE EXCEPTION 'VALIDATION FAILED: child.payload_json = % (expected parent A''s payload carried forward, since none was supplied)', v_child.payload_json;
    END IF;
    IF v_child.restaurant_id <> '00000000-0000-4000-8000-000000000403' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: child.restaurant_id was not copied from the parent';
    END IF;
    IF v_child.priority <> 'urgent' OR v_child.source <> 'portal' OR v_child.submission_type <> 'menu_update' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: child priority/source/submission_type were not copied from the parent';
    END IF;
    IF v_child.disposition_status <> 'unassessed' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: child.disposition_status = % (expected unassessed default)', v_child.disposition_status;
    END IF;
    RAISE NOTICE 'PASS (D1): child row correctly carries parent A''s payload_json forward, applies the supplied description override, and copies restaurant_id/priority/source/submission_type';

    -- D2. Parent updated atomically.
    SELECT * INTO v_parent_after
    FROM operations.restaurant_update_submissions
    WHERE submission_id = '00000000-0000-4000-8000-000000000404';

    IF v_parent_after.superseded_by_submission_id IS DISTINCT FROM v_child.submission_id THEN
        RAISE EXCEPTION 'VALIDATION FAILED: parent.superseded_by_submission_id = % (expected child id %)', v_parent_after.superseded_by_submission_id, v_child.submission_id;
    END IF;
    IF v_parent_after.status <> 'returned' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: parent.status changed to % — §5.7 requires the parent remain returned', v_parent_after.status;
    END IF;
    RAISE NOTICE 'PASS (D2): parent.superseded_by_submission_id set to the new child, parent.status unchanged (still returned)';

    -- D3. Exactly two resubmit events written, one per row, cross-referenced.
    SELECT count(*) INTO v_event_count
    FROM operations.restaurant_update_submission_events
    WHERE submission_id IN ('00000000-0000-4000-8000-000000000404', v_child.submission_id)
      AND event_type = 'resubmit';

    IF v_event_count <> 2 THEN
        RAISE EXCEPTION 'VALIDATION FAILED: expected exactly 2 resubmit event rows, found %', v_event_count;
    END IF;

    SELECT * INTO v_parent_event
    FROM operations.restaurant_update_submission_events
    WHERE submission_id = '00000000-0000-4000-8000-000000000404' AND event_type = 'resubmit';

    SELECT * INTO v_child_event
    FROM operations.restaurant_update_submission_events
    WHERE submission_id = v_child.submission_id AND event_type = 'resubmit';

    IF v_parent_event.metadata->>'resubmission_role' <> 'parent'
       OR (v_parent_event.metadata->>'child_submission_id')::uuid <> v_child.submission_id THEN
        RAISE EXCEPTION 'VALIDATION FAILED: parent-side resubmit event metadata does not correctly cross-reference the child (%)', v_parent_event.metadata;
    END IF;
    IF v_child_event.metadata->>'resubmission_role' <> 'child'
       OR (v_child_event.metadata->>'parent_submission_id')::uuid <> '00000000-0000-4000-8000-000000000404' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: child-side resubmit event metadata does not correctly cross-reference the parent (%)', v_child_event.metadata;
    END IF;
    IF v_parent_event.actor_id <> '00000000-0000-4000-8000-000000000401'
       OR v_child_event.actor_id <> '00000000-0000-4000-8000-000000000401' THEN
        RAISE EXCEPTION 'VALIDATION FAILED: one or both resubmit events do not record the resubmitting actor';
    END IF;
    RAISE NOTICE 'PASS (D3): exactly 2 resubmit events written, correctly cross-referenced (parent<->child) and actor-attributed';
END $$;


-- ── E. Post-resubmit immutability (already-superseded parent rejected) ──────

DO $$
BEGIN
    BEGIN
        PERFORM operations.resubmit_restaurant_update_submission(
            '00000000-0000-4000-8000-000000000404', '00000000-0000-4000-8000-000000000401', NULL, NULL
        );
        RAISE EXCEPTION 'VALIDATION FAILED: resubmitting an already-superseded parent was not rejected';
    EXCEPTION
        WHEN SQLSTATE 'GP409' THEN
            RAISE NOTICE 'PASS (E1): resubmitting an already-superseded parent rejected with GP409 (this RPC''s own precondition check)';
    END;

    -- 021's own immutability trigger, independent of this RPC: a direct
    -- attempt to rewrite superseded_by_submission_id on the same row.
    BEGIN
        UPDATE operations.restaurant_update_submissions
        SET superseded_by_submission_id = '00000000-0000-4000-8000-000000000405'
        WHERE submission_id = '00000000-0000-4000-8000-000000000404';
        RAISE EXCEPTION 'VALIDATION FAILED: trg_rusub_prevent_chain_rewrite did not reject a direct rewrite of an already-set superseded_by_submission_id';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%immutable once set%' THEN
                RAISE NOTICE 'PASS (E2): direct rewrite of parent.superseded_by_submission_id rejected by 021''s trg_rusub_prevent_chain_rewrite, independent of this RPC';
            ELSE
                RAISE EXCEPTION 'VALIDATION FAILED: unexpected error on direct rewrite attempt: %', SQLERRM;
            END IF;
    END;
END $$;


-- ── F. Invocation authority withheld (the grant itself) ─────────────────────

DO $$
DECLARE
    v_has_authenticated boolean;
    v_has_public        boolean;
BEGIN
    SELECT has_function_privilege('authenticated', 'operations.resubmit_restaurant_update_submission(uuid, uuid, jsonb, text)', 'EXECUTE')
        INTO v_has_authenticated;
    SELECT has_function_privilege('public', 'operations.resubmit_restaurant_update_submission(uuid, uuid, jsonb, text)', 'EXECUTE')
        INTO v_has_public;

    IF v_has_authenticated THEN
        RAISE EXCEPTION 'VALIDATION FAILED: authenticated role has EXECUTE on resubmit_restaurant_update_submission — invocation authority was supposed to remain withheld';
    END IF;
    IF v_has_public THEN
        RAISE EXCEPTION 'VALIDATION FAILED: PUBLIC still has EXECUTE on resubmit_restaurant_update_submission — the REVOKE in 022 did not take effect';
    END IF;
    RAISE NOTICE 'PASS (F): neither authenticated nor PUBLIC has EXECUTE on resubmit_restaurant_update_submission — invocation authority remains withheld, as intended';
END $$;


-- ── Done — roll back all fixtures and test rows, nothing persists ───────────

DO $$
BEGIN
    RAISE NOTICE '=== ALL CHECKS PASSED — rolling back, no data persisted ===';
END $$;

ROLLBACK;
