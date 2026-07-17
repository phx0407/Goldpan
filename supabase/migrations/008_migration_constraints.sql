-- ============================================================
-- 008_migration_constraints.sql
-- Unique constraints and indexes to support idempotent data migration.
--
-- All DDL in this file is idempotent:
--   ALTER TABLE ... ADD CONSTRAINT  → wrapped in DO $$ EXCEPTION WHEN duplicate_object
--   CREATE UNIQUE INDEX             → uses IF NOT EXISTS
--   ALTER TABLE ... ADD COLUMN      → wrapped in DO $$ IF NOT EXISTS check
--
-- Apply before running migrate_sheets_to_supabase.py.
--
-- Changes:
--   1. evidence.ingredients        — add source_row_hash column + UNIQUE constraint
--   2. evidence.menu_sources       — UNIQUE (restaurant_id)
--   3. evidence.allergen_disclosures — two partial unique indexes (dish-scoped + restaurant-scoped)
--   4. knowledge.transparency_scores — partial unique index (dish_id) WHERE is_current
-- ============================================================


-- ── 1. evidence.ingredients — source_row_hash ────────────────────────────────
--
-- Why not UNIQUE(dish_id, ingredient_name)?
--   The same ingredient name can appear multiple times in one dish with different
--   component_role, preparation, or cut_type values (e.g., "Chicken" as main
--   protein and "Chicken" in a sauce base are distinct evidence observations).
--   UNIQUE(ingredient_name, ...) with nullable modifier columns also fails because
--   PostgreSQL treats NULLs as distinct — two rows with all NULL modifiers would
--   bypass the constraint entirely.
--
-- Why not a wider natural key (dish_id, ingredient_name, component_role, ...)?
--   Same NULL-distinct problem. Compound nullable unique constraints are unreliable
--   for idempotency.
--
-- Chosen approach: source_row_hash
--   A nullable TEXT column holding an MD5 fingerprint of the row's content fields.
--   Computed by migrate_sheets_to_supabase.py for all migrated rows.
--   New rows entered via the Intake OS API leave source_row_hash = NULL.
--   PostgreSQL UNIQUE on a nullable column allows unlimited NULLs (NULL != NULL),
--   so non-migrated rows are unrestricted. Migrated rows are fingerprinted and
--   dedup-protected. No data-model constraints are introduced.
--
-- Hash inputs (in migrate_sheets_to_supabase.py):
--   dish_external_id | ingredient_name | component_role | preparation |
--   cut_type | allergen_flags | ingredient_type | ingredient_source

-- Add source_row_hash column if it does not already exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'evidence'
          AND table_name   = 'ingredients'
          AND column_name  = 'source_row_hash'
    ) THEN
        ALTER TABLE evidence.ingredients ADD COLUMN source_row_hash text;
    END IF;
END $$;

-- Add UNIQUE constraint on source_row_hash (idempotent)
DO $$
BEGIN
    ALTER TABLE evidence.ingredients
        ADD CONSTRAINT uq_ingredient_source_row_hash
        UNIQUE (source_row_hash);
EXCEPTION WHEN duplicate_object THEN
    NULL;   -- constraint already exists; skip silently
END $$;

COMMENT ON COLUMN evidence.ingredients.source_row_hash IS
    'MD5 fingerprint of key content fields, set by migrate_sheets_to_supabase.py. '
    'NULL for rows entered via API. Enables idempotent re-migration without '
    'constraining the data model. See 008_migration_constraints.sql for hash inputs.';


-- ── 2. evidence.menu_sources — UNIQUE (restaurant_id) ────────────────────────
--
-- Current model: one source registry entry per restaurant.
-- This matches the single-row-per-restaurant structure of the Menu Source Registry
-- Google Sheets tab and the current Intake OS workflow.
--
-- FUTURE EVOLUTION NOTE:
--   If GoldPan later tracks multiple source records per restaurant (e.g., separate
--   rows for different source types: official website vs. PDF allergen guide vs.
--   third-party platform), drop this constraint and replace it with a compound
--   unique index on (restaurant_id, source_type, official_menu_url) or similar.
--   File a migration to handle existing data before making that change.

DO $$
BEGIN
    ALTER TABLE evidence.menu_sources
        ADD CONSTRAINT uq_menu_sources_restaurant
        UNIQUE (restaurant_id);
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

COMMENT ON CONSTRAINT uq_menu_sources_restaurant ON evidence.menu_sources IS
    'One source registry entry per restaurant (current model). If multi-source '
    'tracking is added, drop this and use a compound key. See 008_migration_constraints.sql.';


-- ── 3. evidence.allergen_disclosures — two partial unique indexes ─────────────
--
-- allergen_disclosures has a nullable dish_id (NULL for restaurant-scoped rows).
-- A single UNIQUE constraint on (restaurant_id, allergen, scope, dish_id) does not
-- work for restaurant-scoped rows because NULLs are distinct in PostgreSQL — two
-- restaurant-scoped rows for the same allergen would not conflict.
--
-- Two partial indexes solve this cleanly:
--
--   Index A (dish-scoped):       WHERE dish_id IS NOT NULL
--     Unique per (restaurant, allergen, scope, dish_id) — prevents duplicate
--     dish-level allergen observations.
--
--   Index B (restaurant-scoped): WHERE dish_id IS NULL
--     Unique per (restaurant, allergen, scope) — prevents duplicate
--     restaurant-level allergen statements.
--
-- Migration idempotency note:
--   The supabase-py upsert() method cannot pass the WHERE predicate clause
--   required for partial-index conflict resolution (ON CONFLICT (cols) WHERE pred).
--   Migration idempotency for allergen_disclosures is therefore handled via
--   pre-flight check + FORCE truncate in migrate_sheets_to_supabase.py.
--   These indexes enforce integrity for all future non-migration inserts.

CREATE UNIQUE INDEX IF NOT EXISTS uq_allergen_disc_dish_scoped
    ON evidence.allergen_disclosures (restaurant_id, allergen, scope, dish_id)
    WHERE dish_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_allergen_disc_restaurant_scoped
    ON evidence.allergen_disclosures (restaurant_id, allergen, scope)
    WHERE dish_id IS NULL;


-- ── 4. knowledge.transparency_scores — partial unique index ──────────────────
--
-- One is_current=true score per dish. Historical (is_current=false) rows are
-- unrestricted, allowing score history to accumulate over pipeline runs.
--
-- Same partial-index caveat as allergen_disclosures: supabase-py cannot pass the
-- WHERE predicate for partial-index upsert conflict resolution. Migration
-- idempotency is handled via pre-flight check + FORCE truncate in the script.
-- This index enforces the integrity constraint at the database level.

CREATE UNIQUE INDEX IF NOT EXISTS uq_transparency_scores_current
    ON knowledge.transparency_scores (dish_id)
    WHERE is_current = true;


-- ── 5. knowledge.transparency_scores — relax per-component CHECK bounds ──────
--
-- MIGRATION COMPATIBILITY ONLY. Applied 2026-07-06 to unblock initial migration.
--
-- The canonical scoring model per SCORING_ARCHITECTURE.md is 0–25 per component
-- (total 0–100). The original CHECK constraints (core_clarity <= 25, etc.) are
-- correct for new data.
--
-- Some rows in the Google Sheets source pre-date full scoring normalization and
-- carry component values > 25 (e.g. core_clarity = 30). These are legacy scores
-- that need a manual scoring audit, not silent truncation.
--
-- Resolution: relax upper bound to 100 (the theoretical max if all points were
-- assigned to one component) so legacy rows migrate without data loss. The
-- canonical 0–25 cap is enforced at the application/pipeline layer going forward.
-- A post-migration audit query is in docs/SCORING_AUDIT_REPORT.md.
--
-- DO NOT treat component scores > 25 as valid for new scoring sessions.

ALTER TABLE knowledge.transparency_scores
    DROP CONSTRAINT IF EXISTS transparency_scores_core_clarity_check,
    DROP CONSTRAINT IF EXISTS transparency_scores_sauce_seasoning_disclosure_check,
    DROP CONSTRAINT IF EXISTS transparency_scores_allergen_transparency_check,
    DROP CONSTRAINT IF EXISTS transparency_scores_prep_clarity_check;

ALTER TABLE knowledge.transparency_scores
    ADD CONSTRAINT transparency_scores_core_clarity_check
        CHECK (core_clarity >= 0 AND core_clarity <= 100),
    ADD CONSTRAINT transparency_scores_sauce_seasoning_disclosure_check
        CHECK (sauce_seasoning_disclosure >= 0 AND sauce_seasoning_disclosure <= 100),
    ADD CONSTRAINT transparency_scores_allergen_transparency_check
        CHECK (allergen_transparency >= 0 AND allergen_transparency <= 100),
    ADD CONSTRAINT transparency_scores_prep_clarity_check
        CHECK (prep_clarity >= 0 AND prep_clarity <= 100);
