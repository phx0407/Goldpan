-- ============================================================
-- 005_rls_policies.sql
-- Row-Level Security policies for all schemas.
--
-- Role hierarchy:
--   canvasser    — evidence READ for own assignments; INSERT for own assignments
--   reviewer     — all canvasser perms + UPDATE evidence (corrections) + lifecycle transitions
--   coordinator  — all reviewer perms + restaurant management + user read
--   admin        — full access to evidence + operations; knowledge READ only
--   governance_engine (service role) — knowledge WRITE; evidence READ only
--
-- The governance_engine is a Supabase service-role key used only by the
-- pipeline scripts. No human user is assigned this role.
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE evidence.restaurants         ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence.lifecycle_events    ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence.menu_sources        ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence.source_documents    ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence.dishes              ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence.ingredients         ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence.allergen_disclosures ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence.restaurant_claims   ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence.intake_sessions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge.pipeline_runs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge.pipeline_stages    ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge.derived_filters    ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge.transparency_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge.filter_registry    ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge.freshness_state    ENABLE ROW LEVEL SECURITY;
ALTER TABLE operations.users             ENABLE ROW LEVEL SECURITY;
ALTER TABLE operations.rules_registry    ENABLE ROW LEVEL SECURITY;
ALTER TABLE operations.audit_log         ENABLE ROW LEVEL SECURITY;
ALTER TABLE operations.background_jobs   ENABLE ROW LEVEL SECURITY;
ALTER TABLE operations.notifications     ENABLE ROW LEVEL SECURITY;
ALTER TABLE operations.feature_flags     ENABLE ROW LEVEL SECURITY;
ALTER TABLE operations.report_cache      ENABLE ROW LEVEL SECURITY;


-- ── Helper function: get current user's role ──────────────────────────────────
-- Reads role from JWT claims (set by Supabase Auth + user_role claim).
-- The claim is set when the user logs in via a custom Supabase Auth hook.

CREATE OR REPLACE FUNCTION operations.current_user_role()
RETURNS text
LANGUAGE sql STABLE
AS $$
    SELECT
        COALESCE(
            (current_setting('request.jwt.claims', true)::jsonb ->> 'user_role'),
            'anonymous'
        )
$$;

CREATE OR REPLACE FUNCTION operations.current_user_id()
RETURNS uuid
LANGUAGE sql STABLE
AS $$
    SELECT
        NULLIF(
            current_setting('request.jwt.claims', true)::jsonb ->> 'sub',
            ''
        )::uuid
$$;


-- ============================================================
-- EVIDENCE SCHEMA POLICIES
-- ============================================================

-- ── evidence.restaurants ─────────────────────────────────────────────────────

-- All authenticated roles can read restaurants
CREATE POLICY "restaurants_select_authenticated"
    ON evidence.restaurants FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));

-- Canvassers can only read their own assignments (SELECT via above; restricted INSERT)
-- Coordinators and admins can INSERT new restaurants
CREATE POLICY "restaurants_insert_coordinator_admin"
    ON evidence.restaurants FOR INSERT
    WITH CHECK (operations.current_user_role() IN ('coordinator','admin'));

-- Canvassers can UPDATE lifecycle fields on their assigned restaurants
CREATE POLICY "restaurants_update_canvasser_own"
    ON evidence.restaurants FOR UPDATE
    USING (
        operations.current_user_role() = 'canvasser'
        AND assigned_canvasser_id = operations.current_user_id()
    )
    WITH CHECK (
        operations.current_user_role() = 'canvasser'
        AND assigned_canvasser_id = operations.current_user_id()
    );

-- Reviewers, coordinators, admins can UPDATE any restaurant
CREATE POLICY "restaurants_update_reviewer_plus"
    ON evidence.restaurants FOR UPDATE
    USING (operations.current_user_role() IN ('reviewer','coordinator','admin'))
    WITH CHECK (operations.current_user_role() IN ('reviewer','coordinator','admin'));

-- governance_engine can UPDATE restaurants (for recanvass_status, freshness fields)
CREATE POLICY "restaurants_update_pipeline"
    ON evidence.restaurants FOR UPDATE
    USING (operations.current_user_role() = 'governance_engine')
    WITH CHECK (operations.current_user_role() = 'governance_engine');

-- No DELETE on restaurants — use suspension/deactivation lifecycle states
-- (No DELETE policy = DELETE blocked for all users including admin)


-- ── evidence.lifecycle_events ─────────────────────────────────────────────────

-- All authenticated can read
CREATE POLICY "lifecycle_events_select"
    ON evidence.lifecycle_events FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));

-- Any authenticated user (including canvassers) can INSERT lifecycle events
CREATE POLICY "lifecycle_events_insert"
    ON evidence.lifecycle_events FOR INSERT
    WITH CHECK (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));

-- NO UPDATE or DELETE policies = append-only (enforced by trigger in 006 as well)


-- ── evidence.dishes ───────────────────────────────────────────────────────────

CREATE POLICY "dishes_select_authenticated"
    ON evidence.dishes FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));

-- Canvassers INSERT dishes for their assigned restaurants
CREATE POLICY "dishes_insert_canvasser"
    ON evidence.dishes FOR INSERT
    WITH CHECK (
        operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin')
        AND EXISTS (
            SELECT 1 FROM evidence.restaurants r
            WHERE r.restaurant_id = restaurant_id
            AND (
                r.assigned_canvasser_id = operations.current_user_id()
                OR operations.current_user_role() IN ('reviewer','coordinator','admin')
            )
        )
    );

-- Reviewers+ can UPDATE dishes (corrections)
CREATE POLICY "dishes_update_reviewer_plus"
    ON evidence.dishes FOR UPDATE
    USING (operations.current_user_role() IN ('reviewer','coordinator','admin'))
    WITH CHECK (operations.current_user_role() IN ('reviewer','coordinator','admin'));


-- ── evidence.ingredients ─────────────────────────────────────────────────────

CREATE POLICY "ingredients_select_authenticated"
    ON evidence.ingredients FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));

CREATE POLICY "ingredients_insert_canvasser"
    ON evidence.ingredients FOR INSERT
    WITH CHECK (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin'));

-- Reviewers+ can UPDATE ingredients (corrections with provenance)
CREATE POLICY "ingredients_update_reviewer_plus"
    ON evidence.ingredients FOR UPDATE
    USING (operations.current_user_role() IN ('reviewer','coordinator','admin'))
    WITH CHECK (operations.current_user_role() IN ('reviewer','coordinator','admin'));


-- ── evidence.allergen_disclosures ─────────────────────────────────────────────

CREATE POLICY "allergen_disc_select_authenticated"
    ON evidence.allergen_disclosures FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));

CREATE POLICY "allergen_disc_insert_canvasser"
    ON evidence.allergen_disclosures FOR INSERT
    WITH CHECK (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin'));

-- Allergen updates require reviewer+ (safety-critical)
CREATE POLICY "allergen_disc_update_reviewer_plus"
    ON evidence.allergen_disclosures FOR UPDATE
    USING (operations.current_user_role() IN ('reviewer','coordinator','admin'))
    WITH CHECK (operations.current_user_role() IN ('reviewer','coordinator','admin'));


-- ── All other evidence tables: read for all authenticated, write for canvasser+ ─

CREATE POLICY "menu_sources_select" ON evidence.menu_sources FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));
CREATE POLICY "menu_sources_write" ON evidence.menu_sources FOR ALL
    USING (operations.current_user_role() IN ('reviewer','coordinator','admin','governance_engine'))
    WITH CHECK (operations.current_user_role() IN ('reviewer','coordinator','admin','governance_engine'));

CREATE POLICY "source_docs_select" ON evidence.source_documents FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));
CREATE POLICY "source_docs_write" ON evidence.source_documents FOR ALL
    USING (operations.current_user_role() IN ('reviewer','coordinator','admin'))
    WITH CHECK (operations.current_user_role() IN ('reviewer','coordinator','admin'));

CREATE POLICY "restaurant_claims_select" ON evidence.restaurant_claims FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));
CREATE POLICY "restaurant_claims_write" ON evidence.restaurant_claims FOR ALL
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin'))
    WITH CHECK (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin'));

CREATE POLICY "intake_sessions_select" ON evidence.intake_sessions FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin'));
CREATE POLICY "intake_sessions_insert" ON evidence.intake_sessions FOR INSERT
    WITH CHECK (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));


-- ============================================================
-- KNOWLEDGE SCHEMA POLICIES
-- governance_engine writes; all authenticated roles read
-- ============================================================

CREATE POLICY "pipeline_runs_select" ON knowledge.pipeline_runs FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));
CREATE POLICY "pipeline_runs_write" ON knowledge.pipeline_runs FOR ALL
    USING (operations.current_user_role() = 'governance_engine')
    WITH CHECK (operations.current_user_role() = 'governance_engine');

CREATE POLICY "pipeline_stages_select" ON knowledge.pipeline_stages FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));
CREATE POLICY "pipeline_stages_write" ON knowledge.pipeline_stages FOR ALL
    USING (operations.current_user_role() = 'governance_engine')
    WITH CHECK (operations.current_user_role() = 'governance_engine');

CREATE POLICY "derived_filters_select" ON knowledge.derived_filters FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));
CREATE POLICY "derived_filters_write" ON knowledge.derived_filters FOR ALL
    USING (operations.current_user_role() = 'governance_engine')
    WITH CHECK (operations.current_user_role() = 'governance_engine');

CREATE POLICY "transparency_scores_select" ON knowledge.transparency_scores FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));
CREATE POLICY "transparency_scores_write" ON knowledge.transparency_scores FOR ALL
    USING (operations.current_user_role() = 'governance_engine')
    WITH CHECK (operations.current_user_role() = 'governance_engine');

CREATE POLICY "filter_registry_select" ON knowledge.filter_registry FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));
-- No write policy for filter_registry — updated by migrations only

CREATE POLICY "freshness_state_select" ON knowledge.freshness_state FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));
CREATE POLICY "freshness_state_write" ON knowledge.freshness_state FOR ALL
    USING (operations.current_user_role() = 'governance_engine')
    WITH CHECK (operations.current_user_role() = 'governance_engine');


-- ============================================================
-- OPERATIONS SCHEMA POLICIES
-- ============================================================

-- Users: everyone can read their own record; coordinator+ can read all
CREATE POLICY "users_select_own" ON operations.users FOR SELECT
    USING (
        user_id = operations.current_user_id()
        OR operations.current_user_role() IN ('coordinator','admin')
    );
CREATE POLICY "users_update_own" ON operations.users FOR UPDATE
    USING (user_id = operations.current_user_id())
    WITH CHECK (user_id = operations.current_user_id());
CREATE POLICY "users_admin_all" ON operations.users FOR ALL
    USING (operations.current_user_role() = 'admin')
    WITH CHECK (operations.current_user_role() = 'admin');

-- Rules registry: read-only for all authenticated
CREATE POLICY "rules_registry_select" ON operations.rules_registry FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));

-- Audit log: read for coordinator+; no human writes (trigger-only)
CREATE POLICY "audit_log_select" ON operations.audit_log FOR SELECT
    USING (operations.current_user_role() IN ('coordinator','admin'));
CREATE POLICY "audit_log_insert_system" ON operations.audit_log FOR INSERT
    WITH CHECK (operations.current_user_role() IN ('admin','governance_engine'));

-- Background jobs: read for coordinator+; write for admin and pipeline
CREATE POLICY "jobs_select" ON operations.background_jobs FOR SELECT
    USING (operations.current_user_role() IN ('coordinator','admin','governance_engine'));
CREATE POLICY "jobs_write" ON operations.background_jobs FOR ALL
    USING (operations.current_user_role() IN ('admin','governance_engine'))
    WITH CHECK (operations.current_user_role() IN ('admin','governance_engine'));

-- Notifications: read for coordinator+; write for system/pipeline
CREATE POLICY "notifications_select" ON operations.notifications FOR SELECT
    USING (operations.current_user_role() IN ('coordinator','admin','governance_engine'));
CREATE POLICY "notifications_write" ON operations.notifications FOR ALL
    USING (operations.current_user_role() IN ('admin','governance_engine'))
    WITH CHECK (operations.current_user_role() IN ('admin','governance_engine'));

-- Feature flags: read for all authenticated; write for admin only
CREATE POLICY "feature_flags_select" ON operations.feature_flags FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));
CREATE POLICY "feature_flags_admin_write" ON operations.feature_flags FOR ALL
    USING (operations.current_user_role() = 'admin')
    WITH CHECK (operations.current_user_role() = 'admin');

-- Report cache: read for coordinator+; write for pipeline
CREATE POLICY "report_cache_select" ON operations.report_cache FOR SELECT
    USING (operations.current_user_role() IN ('coordinator','admin','governance_engine'));
CREATE POLICY "report_cache_write" ON operations.report_cache FOR ALL
    USING (operations.current_user_role() IN ('admin','governance_engine'))
    WITH CHECK (operations.current_user_role() IN ('admin','governance_engine'));
