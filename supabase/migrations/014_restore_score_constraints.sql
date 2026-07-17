-- ============================================================
-- 014_restore_score_constraints.sql
-- Restore canonical 0–25 CHECK constraints on knowledge.transparency_scores.
--
-- Context
-- -------
-- Migration 008 relaxed the per-component CHECK constraints from ≤ 25 to ≤ 100
-- to allow Google-Sheet-era legacy rows (some with component values > 25) to
-- migrate without data loss.  Those rows have been corrected by
-- rescore_legacy.py (run before applying this migration).
--
-- This migration drops the temporary ≤ 100 constraints and re-adds the
-- canonical ≤ 25 constraints that match the scoring model defined in
-- docs/SCORING_ARCHITECTURE.md.
--
-- Prerequisites
-- -------------
-- Run rescore_legacy.py --apply BEFORE applying this migration.
-- Verify zero rows with any component > 25:
--
--   SELECT COUNT(*) FROM knowledge.transparency_scores
--   WHERE is_current = true
--     AND (core_clarity > 25
--          OR sauce_seasoning_disclosure > 25
--          OR allergen_transparency > 25
--          OR prep_clarity > 25);
--
-- Expected result: 0.  If any rows remain, fix them first — this migration
-- will fail with a CHECK constraint violation.
--
-- Idempotency
-- -----------
-- DROP CONSTRAINT IF EXISTS  →  safe on re-run (no-op if already dropped).
-- ADD CONSTRAINT wrapped in DO $$ EXCEPTION WHEN duplicate_object → safe on re-run.
-- ============================================================

-- ── Preflight guard ──────────────────────────────────────────────────────────
-- Abort early with a clear message if any out-of-range rows remain.

DO $$
DECLARE
    remaining int;
BEGIN
    SELECT COUNT(*) INTO remaining
    FROM knowledge.transparency_scores
    WHERE is_current = true
      AND (   core_clarity              > 25
           OR sauce_seasoning_disclosure > 25
           OR allergen_transparency      > 25
           OR prep_clarity              > 25);

    IF remaining > 0 THEN
        RAISE EXCEPTION
            'Preflight failed: % row(s) still have a component > 25. '
            'Run rescore_legacy.py --apply before applying this migration.',
            remaining;
    END IF;

    RAISE NOTICE 'Preflight passed: zero is_current rows with component > 25.';
END $$;


-- ── Drop temporary ≤ 100 constraints (added in migration 008) ────────────────

ALTER TABLE knowledge.transparency_scores
    DROP CONSTRAINT IF EXISTS transparency_scores_core_clarity_check,
    DROP CONSTRAINT IF EXISTS transparency_scores_sauce_seasoning_disclosure_check,
    DROP CONSTRAINT IF EXISTS transparency_scores_allergen_transparency_check,
    DROP CONSTRAINT IF EXISTS transparency_scores_prep_clarity_check;


-- ── Restore canonical ≤ 25 constraints ───────────────────────────────────────

DO $$
BEGIN
    ALTER TABLE knowledge.transparency_scores
        ADD CONSTRAINT transparency_scores_core_clarity_check
            CHECK (core_clarity >= 0 AND core_clarity <= 25);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE knowledge.transparency_scores
        ADD CONSTRAINT transparency_scores_sauce_seasoning_disclosure_check
            CHECK (sauce_seasoning_disclosure >= 0 AND sauce_seasoning_disclosure <= 25);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE knowledge.transparency_scores
        ADD CONSTRAINT transparency_scores_allergen_transparency_check
            CHECK (allergen_transparency >= 0 AND allergen_transparency <= 25);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE knowledge.transparency_scores
        ADD CONSTRAINT transparency_scores_prep_clarity_check
            CHECK (prep_clarity >= 0 AND prep_clarity <= 25);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- ── Verify ───────────────────────────────────────────────────────────────────

DO $$
DECLARE
    c_count int;
    s_count int;
    a_count int;
    p_count int;
BEGIN
    SELECT COUNT(*) INTO c_count FROM knowledge.transparency_scores WHERE core_clarity > 25;
    SELECT COUNT(*) INTO s_count FROM knowledge.transparency_scores WHERE sauce_seasoning_disclosure > 25;
    SELECT COUNT(*) INTO a_count FROM knowledge.transparency_scores WHERE allergen_transparency > 25;
    SELECT COUNT(*) INTO p_count FROM knowledge.transparency_scores WHERE prep_clarity > 25;

    IF c_count + s_count + a_count + p_count > 0 THEN
        RAISE EXCEPTION
            'Post-migration check failed: % core_clarity, % sauce, % allergen, % prep rows exceed 25.',
            c_count, s_count, a_count, p_count;
    END IF;

    RAISE NOTICE 'Migration 014 complete. All component CHECK constraints restored to 0–25.';
END $$;
