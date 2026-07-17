-- ============================================================
-- 001_create_schemas.sql
-- Create the four GoldPan schemas.
--
-- evidence   — Evidence System tables (Intake OS owns these)
-- knowledge  — Knowledge System tables (Governance OS writes these)
-- operations — Users, jobs, audit trail, feature flags, rules
-- public     — Materialized views for application output
--
-- The evidence/knowledge schema separation enforces the hard
-- architectural boundary: Knowledge outputs never flow back
-- into Evidence tables. This is not a code convention — it is
-- enforced by schema ownership and RLS.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS evidence;
CREATE SCHEMA IF NOT EXISTS knowledge;
CREATE SCHEMA IF NOT EXISTS operations;
-- public schema already exists in Postgres/Supabase

COMMENT ON SCHEMA evidence  IS 'GoldPan Evidence System — Intake OS tables. Facts only, fully provenanced.';
COMMENT ON SCHEMA knowledge IS 'GoldPan Knowledge System — Governance OS output. Computed from evidence; never written by humans.';
COMMENT ON SCHEMA operations IS 'GoldPan operational layer — users, audit trail, jobs, feature flags, rules registry.';
COMMENT ON SCHEMA public     IS 'GoldPan public output — materialized views for the application API.';
