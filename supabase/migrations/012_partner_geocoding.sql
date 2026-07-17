-- ============================================================
-- 012_partner_geocoding.sql
-- Add geocoordinate fields to operations.partners
--
-- Enables the BD map view (/admin/business-development/map).
-- Coordinates are auto-populated by the API layer via Nominatim
-- geocoding when city + state are saved. Can be overridden manually.
--
-- Safe to re-run: ALTER TABLE ADD COLUMN IF NOT EXISTS is idempotent.
-- ============================================================

ALTER TABLE operations.partners
    ADD COLUMN IF NOT EXISTS latitude       numeric(10, 7),
    ADD COLUMN IF NOT EXISTS longitude      numeric(10, 7),
    ADD COLUMN IF NOT EXISTS geocoded_at    timestamptz,
    ADD COLUMN IF NOT EXISTS geocode_source text
        CHECK (geocode_source IN ('manual', 'nominatim', 'mapbox', 'google') OR geocode_source IS NULL);

COMMENT ON COLUMN operations.partners.latitude IS
    'WGS-84 latitude. Auto-populated by Nominatim geocoding from city+state on save. '
    'Can be overridden manually (geocode_source = ''manual'').';

COMMENT ON COLUMN operations.partners.longitude IS
    'WGS-84 longitude. Same provenance as latitude.';

COMMENT ON COLUMN operations.partners.geocode_source IS
    'How coordinates were obtained: manual entry, Nominatim (OSM), Mapbox, or Google.';

-- Index for map queries: filter to rows that have coordinates
CREATE INDEX IF NOT EXISTS idx_partners_coords
    ON operations.partners(latitude, longitude)
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
