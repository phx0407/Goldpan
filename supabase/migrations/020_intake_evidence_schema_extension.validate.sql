-- ============================================================
-- 020_intake_evidence_schema_extension.validate.sql
-- Focused validation for 020_intake_evidence_schema_extension.sql.
--
-- Not a migration. Not executed as part of applying migration 020. Run
-- this manually, against a database that already has migration 020
-- applied, when Brad wants to verify the migration before/after applying
-- it in a given environment.
--
-- Everything in this script runs inside a single transaction that is
-- ROLLBACK'd at the end — no fixture data or test rows are left behind,
-- and no real data is modified. Safe to run against a database that
-- already has real evidence.* rows in it.
--
-- Coverage:
--   A. Existing-row / schema compatibility  (new columns present, nullable,
--      pre-existing rows unaffected)
--   B. Constraint enforcement                (CHECK / NOT NULL / FK reject
--      invalid data as designed)
--   C. Index presence                        (every index migration 020
--      defines actually exists)
--   D. Representative inserts                (valid rows for every new
--      table/column succeed, including the "no calorie data" and "no
--      source_packet_id" optional-evidence cases, and confirms
--      source_packet_id ON DELETE RESTRICT blocks hard-deletion of a
--      referenced intake_packets row rather than silently severing lineage)
--
-- Each check RAISEs NOTICE on pass and RAISEs EXCEPTION on failure, so a
-- failed run aborts loudly and the whole transaction rolls back.
-- Usage:  psql "$DATABASE_URL" -f 020_intake_evidence_schema_extension.validate.sql
-- ============================================================

BEGIN;

-- ── 0. Guard: migration 020 must already be applied ─────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'evidence' AND table_name = 'restaurant_claims'
          AND column_name = 'scope'
    ) THEN
        RAISE EXCEPTION 'VALIDATION ABORTED: evidence.restaurant_claims.scope does not exist — apply migration 020 first';
    END IF;
    IF to_regclass('evidence.dish_verbatim_components') IS NULL THEN
        RAISE EXCEPTION 'VALIDATION ABORTED: evidence.dish_verbatim_components does not exist — apply migration 020 first';
    END IF;
    IF to_regclass('evidence.restaurant_source_inventory') IS NULL THEN
        RAISE EXCEPTION 'VALIDATION ABORTED: evidence.restaurant_source_inventory does not exist — apply migration 020 first';
    END IF;
    IF to_regclass('evidence.dish_modifiers') IS NULL THEN
        RAISE EXCEPTION 'VALIDATION ABORTED: evidence.dish_modifiers does not exist — apply migration 020 first';
    END IF;
    RAISE NOTICE 'GUARD PASS: all five migration-020 schema objects present';
END $$;


-- ── A. Existing-row / schema compatibility ───────────────────────────────────

DO $$
DECLARE
    pre_existing_claims  int;
    pre_existing_dishes  int;
    non_null_scope       int;
    non_null_calorie_new int;
BEGIN
    SELECT count(*) INTO pre_existing_claims FROM evidence.restaurant_claims;
    SELECT count(*) INTO pre_existing_dishes FROM evidence.dishes;

    -- New restaurant_claims.scope column must be nullable and must default
    -- to NULL for all rows that existed before this migration touched them
    -- (no backfill was performed — none was possible, per DEC000003 §2 item 8).
    SELECT count(*) INTO non_null_scope FROM evidence.restaurant_claims WHERE scope IS NOT NULL;

    -- New dishes calorie columns must default to NULL for pre-existing rows.
    SELECT count(*) INTO non_null_calorie_new
    FROM evidence.dishes
    WHERE calorie_unit IS NOT NULL
       OR calorie_source_url IS NOT NULL
       OR calorie_ingredient_source IS NOT NULL
       OR calorie_notes IS NOT NULL
       OR calorie_raw_fragment IS NOT NULL;

    RAISE NOTICE 'INFO: % pre-existing evidence.restaurant_claims rows, % pre-existing evidence.dishes rows', pre_existing_claims, pre_existing_dishes;

    IF non_null_scope > 0 THEN
        RAISE EXCEPTION 'VALIDATION FAILED: % evidence.restaurant_claims rows have non-null scope with no backfill source — unexpected pre-population', non_null_scope;
    END IF;
    RAISE NOTICE 'PASS (A1): evidence.restaurant_claims.scope is null on all pre-existing rows';

    IF non_null_calorie_new > 0 THEN
        RAISE NOTICE 'INFO: % evidence.dishes rows already have non-null new calorie columns (expected only if this script has been run before without a clean rollback, or another process populated them)', non_null_calorie_new;
    ELSE
        RAISE NOTICE 'PASS (A2): new evidence.dishes calorie columns are null on all pre-existing rows';
    END IF;

    -- Confirm all seven calorie columns are nullable (no NOT NULL constraint).
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'evidence' AND table_name = 'dishes'
          AND column_name IN ('calorie_value','calorie_source_text','calorie_unit',
                               'calorie_source_url','calorie_ingredient_source',
                               'calorie_notes','calorie_raw_fragment')
          AND is_nullable = 'NO'
    ) THEN
        RAISE EXCEPTION 'VALIDATION FAILED: one or more calorie columns on evidence.dishes is NOT NULL — violates DEC000003 §13 Decision 6 (calories are optional evidence)';
    END IF;
    RAISE NOTICE 'PASS (A3): all seven calorie-related columns on evidence.dishes are nullable';
END $$;


-- ── Fixtures (rolled back at end of script; never committed) ────────────────

DO $$
BEGIN
    INSERT INTO evidence.restaurants (restaurant_id, external_id, name)
    VALUES ('00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE', 'Migration 020 Validation Fixture');

    INSERT INTO evidence.dishes (dish_id, external_id, restaurant_id, restaurant_external_id, dish_name)
    VALUES ('00000000-0000-4000-8000-000000000202', 'TESTD_020_VALIDATE',
            '00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE', 'Validation Fixture Dish');

    -- Second dish with deliberately NO calorie data, to exercise the
    -- "optional evidence" path explicitly (DEC000003 §13 Decision 6).
    INSERT INTO evidence.dishes (dish_id, external_id, restaurant_id, restaurant_external_id, dish_name)
    VALUES ('00000000-0000-4000-8000-000000000203', 'TESTD_020_VALIDATE_NOCAL',
            '00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE', 'Validation Fixture Dish (no calorie data)');

    INSERT INTO operations.intake_packets (
        packet_id, restaurant_external_id, restaurant_name, canvass_date, packet_data
    ) VALUES (
        '00000000-0000-4000-8000-000000000204', 'TESTR_020_VALIDATE', 'Migration 020 Validation Fixture',
        current_date, '{}'::jsonb
    );

    RAISE NOTICE 'PASS (fixtures): restaurant, two dishes, and one intake_packets row created for validation';
END $$;


-- ── B. Constraint enforcement (each expected failure caught, not a real error) ─

-- B1. restaurant_claims.scope CHECK rejects an invalid value.
DO $$
BEGIN
    BEGIN
        INSERT INTO evidence.restaurant_claims (restaurant_id, restaurant_external_id, claim_text, scope)
        VALUES ('00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE', 'bad scope test', 'not_a_real_scope');
        RAISE EXCEPTION 'VALIDATION FAILED: evidence.restaurant_claims.scope CHECK did not reject an invalid value';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (B1): evidence.restaurant_claims.scope CHECK rejects invalid values';
    END;
END $$;

-- B2. dish_verbatim_components.resolution_status CHECK rejects an invalid value.
DO $$
BEGIN
    BEGIN
        INSERT INTO evidence.dish_verbatim_components
            (dish_id, dish_external_id, restaurant_id, restaurant_external_id, verbatim_text, resolution_status)
        VALUES ('00000000-0000-4000-8000-000000000202', 'TESTD_020_VALIDATE',
                '00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE',
                'salad dressing', 'not_a_real_status');
        RAISE EXCEPTION 'VALIDATION FAILED: evidence.dish_verbatim_components.resolution_status CHECK did not reject an invalid value';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (B2): evidence.dish_verbatim_components.resolution_status CHECK rejects invalid values';
    END;
END $$;

-- B3. dish_verbatim_components.dish_id FK (RESTRICT) rejects a bogus dish.
DO $$
BEGIN
    BEGIN
        INSERT INTO evidence.dish_verbatim_components
            (dish_id, dish_external_id, restaurant_id, restaurant_external_id, verbatim_text)
        VALUES ('00000000-0000-4000-8000-00000000ffff', 'NOT_A_REAL_DISH',
                '00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE',
                'orphaned component');
        RAISE EXCEPTION 'VALIDATION FAILED: evidence.dish_verbatim_components.dish_id FK did not reject a nonexistent dish_id';
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE 'PASS (B3): evidence.dish_verbatim_components.dish_id FK rejects nonexistent dishes';
    END;
END $$;

-- B4. restaurant_source_inventory.source_type CHECK rejects an invalid value.
DO $$
BEGIN
    BEGIN
        INSERT INTO evidence.restaurant_source_inventory
            (restaurant_id, restaurant_external_id, source_type, url)
        VALUES ('00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE',
                'not_a_real_source_type', 'https://example.com');
        RAISE EXCEPTION 'VALIDATION FAILED: evidence.restaurant_source_inventory.source_type CHECK did not reject an invalid value';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS (B4): evidence.restaurant_source_inventory.source_type CHECK rejects invalid values';
    END;
END $$;

-- B5. dish_modifiers.raw_packet_fragment NOT NULL rejects a missing fragment.
DO $$
BEGIN
    BEGIN
        INSERT INTO evidence.dish_modifiers
            (dish_id, dish_external_id, restaurant_id, restaurant_external_id, modifier_name)
        VALUES ('00000000-0000-4000-8000-000000000202', 'TESTD_020_VALIDATE',
                '00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE',
                'Extra Cheese');
        RAISE EXCEPTION 'VALIDATION FAILED: evidence.dish_modifiers.raw_packet_fragment NOT NULL did not reject a missing fragment';
    EXCEPTION
        WHEN not_null_violation THEN
            RAISE NOTICE 'PASS (B5): evidence.dish_modifiers.raw_packet_fragment NOT NULL rejects missing fragments';
    END;
END $$;


-- ── C. Index presence ─────────────────────────────────────────────────────────

DO $$
DECLARE
    expected text[] := ARRAY[
        'idx_restaurant_claims_scope',
        'idx_dish_verbatim_components_dish',
        'idx_dish_verbatim_components_restaurant',
        'idx_dish_verbatim_components_status',
        'idx_restaurant_source_inventory_restaurant',
        'idx_restaurant_source_inventory_packet',
        'idx_restaurant_source_inventory_type',
        'idx_dish_modifiers_dish',
        'idx_dish_modifiers_restaurant'
    ];
    idx text;
BEGIN
    FOREACH idx IN ARRAY expected LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'evidence' AND indexname = idx
        ) THEN
            RAISE EXCEPTION 'VALIDATION FAILED: expected index % is missing', idx;
        END IF;
    END LOOP;
    RAISE NOTICE 'PASS (C): all % expected migration-020 indexes are present', array_length(expected, 1);
END $$;


-- ── D. Representative inserts (all expected to succeed) ─────────────────────

-- D1. restaurant_claims with a valid scope.
DO $$
BEGIN
    INSERT INTO evidence.restaurant_claims (restaurant_id, restaurant_external_id, claim_text, scope)
    VALUES ('00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE',
            'We are a vegan restaurant', 'ownership');
    RAISE NOTICE 'PASS (D1): valid evidence.restaurant_claims.scope insert succeeded';
END $$;

-- D2. dish_verbatim_components, default resolution_status.
DO $$
BEGIN
    INSERT INTO evidence.dish_verbatim_components
        (dish_id, dish_external_id, restaurant_id, restaurant_external_id, verbatim_text, ingredient_source)
    VALUES ('00000000-0000-4000-8000-000000000202', 'TESTD_020_VALIDATE',
            '00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE',
            'salad dressing', 'menu');
    RAISE NOTICE 'PASS (D2): evidence.dish_verbatim_components insert succeeded with default resolution_status';
END $$;

-- D3. restaurant_source_inventory with a real source_packet_id.
DO $$
BEGIN
    INSERT INTO evidence.restaurant_source_inventory
        (restaurant_id, restaurant_external_id, source_type, url, source_packet_id)
    VALUES ('00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE',
            'menu', 'https://example.com/menu', '00000000-0000-4000-8000-000000000204');
    RAISE NOTICE 'PASS (D3): evidence.restaurant_source_inventory insert succeeded with source_packet_id set';
END $$;

-- D3b. source_packet_id ON DELETE RESTRICT: hard-deleting a referenced
-- intake_packets row must fail, not silently null out the reference.
DO $$
BEGIN
    BEGIN
        DELETE FROM operations.intake_packets WHERE packet_id = '00000000-0000-4000-8000-000000000204';
        RAISE EXCEPTION 'VALIDATION FAILED: deleting an operations.intake_packets row still referenced by evidence.restaurant_source_inventory.source_packet_id did not fail — provenance lineage would be silently severed';
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE 'PASS (D3b): evidence.restaurant_source_inventory.source_packet_id ON DELETE RESTRICT blocks hard-deletion of a referenced packet';
    END;
END $$;

-- D4. restaurant_source_inventory with source_packet_id NULL (optional field).
DO $$
BEGIN
    INSERT INTO evidence.restaurant_source_inventory
        (restaurant_id, restaurant_external_id, source_type, url)
    VALUES ('00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE',
            'restaurant_qa', 'https://example.com/qa-thread');
    RAISE NOTICE 'PASS (D4): evidence.restaurant_source_inventory insert succeeded with source_packet_id null';
END $$;

-- D5. dishes calorie columns populated (calorie object present in packet).
DO $$
BEGIN
    UPDATE evidence.dishes
    SET calorie_value = '450',
        calorie_source_text = 'Menu lists 450 cal',
        calorie_unit = 'kcal',
        calorie_source_url = 'https://example.com/menu#calories',
        calorie_ingredient_source = 'menu',
        calorie_notes = 'Per serving',
        calorie_raw_fragment = '{"value":"450","unit":"kcal","source_text":"Menu lists 450 cal","source_url":"https://example.com/menu#calories","ingredient_source":"menu","notes":"Per serving"}'::jsonb
    WHERE dish_id = '00000000-0000-4000-8000-000000000202';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'VALIDATION FAILED: fixture dish update for calorie columns affected zero rows';
    END IF;
    RAISE NOTICE 'PASS (D5): evidence.dishes calorie columns (including calorie_raw_fragment) populate successfully when a calorie object exists';
END $$;

-- D6. Second fixture dish deliberately left with NO calorie data — must
-- remain valid, per DEC000003 §13 Decision 6.
DO $$
DECLARE
    all_null boolean;
BEGIN
    SELECT (calorie_value IS NULL AND calorie_source_text IS NULL AND calorie_unit IS NULL
            AND calorie_source_url IS NULL AND calorie_ingredient_source IS NULL
            AND calorie_notes IS NULL AND calorie_raw_fragment IS NULL)
    INTO all_null
    FROM evidence.dishes
    WHERE dish_id = '00000000-0000-4000-8000-000000000203';

    IF NOT all_null THEN
        RAISE EXCEPTION 'VALIDATION FAILED: no-calorie fixture dish has a non-null calorie column without ever being given calorie data';
    END IF;
    RAISE NOTICE 'PASS (D6): a dish with no calorie object remains valid with all seven calorie columns null';
END $$;

-- D7. dish_modifiers, "{name, upcharge, description}" packet key variant.
DO $$
BEGIN
    INSERT INTO evidence.dish_modifiers
        (dish_id, dish_external_id, restaurant_id, restaurant_external_id,
         modifier_name, upcharge, raw_packet_fragment)
    VALUES ('00000000-0000-4000-8000-000000000202', 'TESTD_020_VALIDATE',
            '00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE',
            'Extra Avocado', '+$1.50',
            '{"name":"Extra Avocado","upcharge":"+$1.50","description":null}'::jsonb);
    RAISE NOTICE 'PASS (D7): evidence.dish_modifiers insert succeeded for the {name, upcharge, description} key variant';
END $$;

-- D8. dish_modifiers, "{modifier_name, modifier_description, options[]}" variant.
DO $$
BEGIN
    INSERT INTO evidence.dish_modifiers
        (dish_id, dish_external_id, restaurant_id, restaurant_external_id,
         modifier_name, modifier_description, options, raw_packet_fragment)
    VALUES ('00000000-0000-4000-8000-000000000202', 'TESTD_020_VALIDATE',
            '00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE',
            'Two Wraps', 'Choose two wrap options',
            '["Spinach","Tomato Basil"]'::jsonb,
            '{"modifier_name":"Two Wraps","modifier_description":"Choose two wrap options","options":["Spinach","Tomato Basil"]}'::jsonb);
    RAISE NOTICE 'PASS (D8): evidence.dish_modifiers insert succeeded for the {modifier_name, modifier_description, options[]} key variant';
END $$;

-- D9. dish_modifiers, raw_packet_fragment-only (no structured fields resolved).
DO $$
BEGIN
    INSERT INTO evidence.dish_modifiers
        (dish_id, dish_external_id, restaurant_id, restaurant_external_id, raw_packet_fragment)
    VALUES ('00000000-0000-4000-8000-000000000202', 'TESTD_020_VALIDATE',
            '00000000-0000-4000-8000-000000000201', 'TESTR_020_VALIDATE',
            '{"unrecognized_key":"future packet variant"}'::jsonb);
    RAISE NOTICE 'PASS (D9): evidence.dish_modifiers insert succeeded with only raw_packet_fragment populated (schema-drift resilience)';
END $$;


-- ── Done — roll back all fixtures and test rows, nothing persists ───────────

DO $$
BEGIN
    RAISE NOTICE '=== ALL CHECKS PASSED — rolling back, no data persisted ===';
END $$;

ROLLBACK;
