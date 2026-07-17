-- ============================================================
-- 013_identity_enrichment_columns.sql
-- Add identity enrichment fields to evidence.restaurants.
--
-- New columns:
--   google_place_id  — Google Places ID; enables Places API enrichment
--   postal_code      — structured postal code (Blueprint standard name)
--
-- Existing columns confirmed present (from 002):
--   address, city, state, zip, latitude, longitude, phone
--
-- Note on zip vs postal_code:
--   `zip` is the legacy column from migration 002. It remains in place for
--   backwards compatibility with existing scripts. `postal_code` is the
--   Blueprint-standard column name. identity_enrichment.py writes to
--   `postal_code`. `postal_code` is seeded from `zip` in the UPDATE below.
--   `zip` is otherwise deprecated — new code should use `postal_code`.
--
-- Safe to re-run: ADD COLUMN IF NOT EXISTS is idempotent.
-- The UPDATE backfill is also safe — it only fills null postal_code
-- rows from non-null zip values.
-- ============================================================

-- ── New columns ───────────────────────────────────────────────────────────────

ALTER TABLE evidence.restaurants
    ADD COLUMN IF NOT EXISTS google_place_id  text,
    ADD COLUMN IF NOT EXISTS postal_code      text;

COMMENT ON COLUMN evidence.restaurants.google_place_id IS
    'Google Places ID for this restaurant. Populated by identity_enrichment.py. '
    'Enables Places API lookups for address, phone, hours, and geocoordinates. '
    'Source: Identity Enrichment Pipeline — not Intake.';

COMMENT ON COLUMN evidence.restaurants.postal_code IS
    'Structured ZIP/postal code. Blueprint-standard column name. '
    'Populated by identity_enrichment.py via Google Places API. '
    'See also: zip (legacy column — same data, kept for backwards compatibility).';

COMMENT ON COLUMN evidence.restaurants.zip IS
    'Legacy postal code column from migration 002. '
    'New code should use postal_code instead. '
    'Kept for backwards compatibility with existing scripts.';

-- ── Seed postal_code from existing zip values ─────────────────────────────────
-- One-time backfill: copy non-null zip values into postal_code where
-- postal_code has not yet been set. Does not overwrite any future
-- identity_enrichment.py results.

UPDATE evidence.restaurants
SET    postal_code = zip
WHERE  zip         IS NOT NULL
  AND  postal_code IS NULL;

-- ── Enrichment tracking columns ───────────────────────────────────────────────
-- Track when enrichment was last run and what source produced the data.
-- Allows re-enrichment to be scoped to stale records only.

ALTER TABLE evidence.restaurants
    ADD COLUMN IF NOT EXISTS identity_enriched_at     timestamptz,
    ADD COLUMN IF NOT EXISTS identity_enrichment_source text
        CHECK (identity_enrichment_source IN (
            'google_places', 'nominatim', 'manual', 'restaurant_submission', NULL
        ));

COMMENT ON COLUMN evidence.restaurants.identity_enriched_at IS
    'Timestamp of last successful Identity Enrichment Pipeline run for this restaurant.';

COMMENT ON COLUMN evidence.restaurants.identity_enrichment_source IS
    'Primary source used in last enrichment run: google_places, nominatim, manual, or restaurant_submission.';

-- ── Index ─────────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_restaurants_google_place_id
    ON evidence.restaurants(google_place_id)
    WHERE google_place_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_restaurants_enriched_at
    ON evidence.restaurants(identity_enriched_at)
    WHERE identity_enriched_at IS NOT NULL;
