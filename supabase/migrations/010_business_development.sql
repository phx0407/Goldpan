-- ============================================================
-- 010_business_development.sql
-- Business Development OS — CRM + Analytics schema
--
-- Tables:
--   operations.partners         — BD CRM: all partner types
--   operations.partner_actions  — Append-only action/note log
--
-- New schema:
--   analytics                   — Web analytics (schema-ready; ingestion pending)
--     analytics.page_views
--     analytics.events
--     analytics.restaurant_profile_views
--     analytics.search_terms
--     analytics.ask_goldpan_sessions
--
-- Design:
--   - partners.partner_type covers: restaurant, dietitian, nutrition_clinic,
--     gym, corporate_wellness, healthcare_partner, university, employer,
--     food_brand, investor_grant, community_organization, media, other
--   - Restaurant partners link to evidence.restaurants via restaurant_id (FK)
--   - Non-restaurant partners leave restaurant_id NULL
--   - external_id auto-generated as "BD001", "BD002" … via trigger + sequence
--   - partner_actions is append-only (no UPDATE/DELETE)
--
-- GA Analytics ingestion recommendation:
--   RECOMMENDED: Direct event logging from Next.js frontend via API endpoint.
--     Pros: real-time, full control, no third-party quotas, no OAuth.
--     Implement: POST /api/events from Next.js middleware or page components.
--   ALTERNATIVE: GA4 Data API (requires OAuth setup, has daily quotas, ~48h lag).
--   SKIP: BigQuery export (requires GA4 360 / paid plan, complex setup).
--   Tables below are schema-ready; populate when ingestion is wired up.
-- ============================================================


-- ── Analytics schema ──────────────────────────────────────────────────────────

CREATE SCHEMA IF NOT EXISTS analytics;

COMMENT ON SCHEMA analytics IS
    'GoldPan analytics — page views, events, search terms, Ask GoldPan sessions. '
    'Schema-ready; ingestion via Next.js frontend event logging (recommended).';


-- ── analytics.page_views ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS analytics.page_views (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  text,
    page_path   text        NOT NULL,
    referrer    text,
    user_agent  text,
    ip_hash     text,       -- SHA-256 of IP, for dedup/rate-limit, never raw IP
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pv_path    ON analytics.page_views(page_path, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pv_created ON analytics.page_views(created_at DESC);


-- ── analytics.events ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS analytics.events (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  text,
    event_name  text        NOT NULL,   -- e.g. 'filter_applied', 'dish_expanded'
    event_data  jsonb,                  -- arbitrary key/value payload
    page_path   text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ev_name    ON analytics.events(event_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ev_created ON analytics.events(created_at DESC);


-- ── analytics.restaurant_profile_views ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS analytics.restaurant_profile_views (
    id                      uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id              text,
    restaurant_external_id  text    NOT NULL,
    restaurant_name         text,
    source                  text,   -- 'search' | 'direct' | 'referral' | 'filter'
    created_at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rpv_restaurant ON analytics.restaurant_profile_views(restaurant_external_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rpv_created    ON analytics.restaurant_profile_views(created_at DESC);


-- ── analytics.search_terms ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS analytics.search_terms (
    id                      uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id              text,
    search_term             text    NOT NULL,
    results_count           int,
    clicked_restaurant_id   text,   -- external_id of clicked result, if any
    created_at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_st_term    ON analytics.search_terms(search_term, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_st_created ON analytics.search_terms(created_at DESC);


-- ── analytics.ask_goldpan_sessions ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS analytics.ask_goldpan_sessions (
    id                   uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id           text,
    question_preview     text,   -- first 120 chars, no PII
    restaurant_context   text,   -- which restaurant, if any
    response_latency_ms  int,
    created_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ag_created ON analytics.ask_goldpan_sessions(created_at DESC);


-- ── operations.partners ──────────────────────────────────────────────────────

CREATE SEQUENCE IF NOT EXISTS operations.partner_seq START 1;

CREATE TABLE IF NOT EXISTS operations.partners (
    partner_id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id         text        NOT NULL UNIQUE,    -- filled by trigger: BD001…

    -- Classification
    partner_type        text        NOT NULL
                        CHECK (partner_type IN (
                            'restaurant',
                            'dietitian',
                            'nutrition_clinic',
                            'gym',
                            'corporate_wellness',
                            'healthcare_partner',
                            'university',
                            'employer',
                            'food_brand',
                            'investor_grant',
                            'community_organization',
                            'media',
                            'other'
                        )),

    -- Restaurant link (only for partner_type = 'restaurant')
    restaurant_id       uuid        REFERENCES evidence.restaurants(restaurant_id)
                                    ON DELETE SET NULL,

    -- Identity
    name                text        NOT NULL,
    contact_name        text,
    contact_title       text,

    -- Pipeline
    status              text        NOT NULL DEFAULT 'prospect'
                        CHECK (status IN (
                            'prospect',
                            'outreach',
                            'engaged',
                            'negotiating',
                            'active',
                            'paused',
                            'declined',
                            'churned'
                        )),
    pipeline_stage      text
                        CHECK (pipeline_stage IN (
                            'awareness',
                            'interest',
                            'evaluation',
                            'decision',
                            'onboarded'
                        ) OR pipeline_stage IS NULL),
    priority            text        NOT NULL DEFAULT 'medium'
                        CHECK (priority IN ('high', 'medium', 'low')),
    opportunity_score   int         CHECK (
                            opportunity_score IS NULL OR
                            (opportunity_score >= 1 AND opportunity_score <= 10)
                        ),

    -- Relationship
    relationship_owner  text,       -- internal GoldPan team member
    source              text,       -- how we found them / referral source
    deal_value          text,       -- estimated value, free-form

    -- Contact info
    email               text,
    phone               text,
    instagram           text,
    website             text,
    address             text,
    city                text,
    state               text,

    -- Timing
    first_contact_date  date,
    last_contact_date   date,
    next_followup_date  date,

    -- Narrative fields
    notes               text,       -- general notes / context
    objections          text,       -- objections raised by partner

    -- Non-restaurant BD fields
    strategic_value     text,       -- why this partner matters
    audience_fit        text,       -- overlap with GoldPan user base
    partnership_model   text,       -- possible collaboration model

    -- Meta
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE operations.partners IS
    'Business Development CRM. One row per partner organization. '
    'Restaurant partners link to evidence.restaurants; others leave restaurant_id NULL.';

COMMENT ON COLUMN operations.partners.external_id IS
    'Human-readable ID, auto-generated as BD001, BD002, … via trigger.';
COMMENT ON COLUMN operations.partners.restaurant_id IS
    'FK to evidence.restaurants. Only set when partner_type = ''restaurant''. '
    'Enables live intel enrichment (dish count, transparency coverage, freshness).';


-- ── Trigger: auto-generate external_id ───────────────────────────────────────

CREATE OR REPLACE FUNCTION operations.gen_partner_external_id()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.external_id IS NULL OR NEW.external_id = '' THEN
        NEW.external_id := 'BD' || LPAD(
            nextval('operations.partner_seq')::text, 3, '0'
        );
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_partners_external_id ON operations.partners;
CREATE TRIGGER trg_partners_external_id
    BEFORE INSERT ON operations.partners
    FOR EACH ROW EXECUTE FUNCTION operations.gen_partner_external_id();


-- ── Trigger: updated_at ───────────────────────────────────────────────────────
-- Reuses operations.set_updated_at() defined in 006_triggers.sql

DROP TRIGGER IF EXISTS trg_partners_updated_at ON operations.partners;
CREATE TRIGGER trg_partners_updated_at
    BEFORE UPDATE ON operations.partners
    FOR EACH ROW EXECUTE FUNCTION operations.set_updated_at();


-- Indexes
CREATE INDEX IF NOT EXISTS idx_partners_type       ON operations.partners(partner_type);
CREATE INDEX IF NOT EXISTS idx_partners_status     ON operations.partners(status);
CREATE INDEX IF NOT EXISTS idx_partners_priority   ON operations.partners(priority);
CREATE INDEX IF NOT EXISTS idx_partners_followup   ON operations.partners(next_followup_date);
CREATE INDEX IF NOT EXISTS idx_partners_restaurant ON operations.partners(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_partners_owner      ON operations.partners(relationship_owner);


-- ── operations.partner_actions ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS operations.partner_actions (
    action_id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id      uuid        NOT NULL
                    REFERENCES operations.partners(partner_id) ON DELETE CASCADE,

    action_type     text        NOT NULL
                    CHECK (action_type IN (
                        'note',
                        'email_sent',
                        'email_received',
                        'call',
                        'meeting',
                        'follow_up_set',
                        'status_change',
                        'contacted',
                        'dm_instagram',
                        'other'
                    )),

    content         text,               -- note text, call summary, etc.
    old_status      text,               -- populated on status_change actions
    new_status      text,               -- populated on status_change actions
    performed_by    text,               -- GoldPan team member
    performed_at    timestamptz NOT NULL DEFAULT now(),
    created_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE operations.partner_actions IS
    'Append-only action log for each partner. Records notes, calls, emails, '
    'status changes, follow-up dates, and contact events.';

CREATE INDEX IF NOT EXISTS idx_pactions_partner ON operations.partner_actions(partner_id, performed_at DESC);
CREATE INDEX IF NOT EXISTS idx_pactions_type    ON operations.partner_actions(action_type, performed_at DESC);


-- ── RLS ───────────────────────────────────────────────────────────────────────

ALTER TABLE operations.partners        ENABLE ROW LEVEL SECURITY;
ALTER TABLE operations.partner_actions ENABLE ROW LEVEL SECURITY;

-- Partners: coordinators and admins can read; service_role writes
DROP POLICY IF EXISTS "partners_select" ON operations.partners;
CREATE POLICY "partners_select" ON operations.partners FOR SELECT
    USING (
        operations.current_user_role() IN ('coordinator', 'admin')
        OR current_user IN ('postgres', 'service_role')
    );

DROP POLICY IF EXISTS "partners_insert" ON operations.partners;
CREATE POLICY "partners_insert" ON operations.partners FOR INSERT
    WITH CHECK (
        operations.current_user_role() IN ('coordinator', 'admin')
        OR current_user IN ('postgres', 'service_role')
    );

DROP POLICY IF EXISTS "partners_update" ON operations.partners;
CREATE POLICY "partners_update" ON operations.partners FOR UPDATE
    USING (
        operations.current_user_role() IN ('coordinator', 'admin')
        OR current_user IN ('postgres', 'service_role')
    );

-- partner_actions: append-only
DROP POLICY IF EXISTS "partner_actions_select" ON operations.partner_actions;
CREATE POLICY "partner_actions_select" ON operations.partner_actions FOR SELECT
    USING (
        operations.current_user_role() IN ('coordinator', 'admin')
        OR current_user IN ('postgres', 'service_role')
    );

DROP POLICY IF EXISTS "partner_actions_insert" ON operations.partner_actions;
CREATE POLICY "partner_actions_insert" ON operations.partner_actions FOR INSERT
    WITH CHECK (
        operations.current_user_role() IN ('coordinator', 'admin')
        OR current_user IN ('postgres', 'service_role')
    );


-- ── Grants ────────────────────────────────────────────────────────────────────

GRANT SELECT, INSERT, UPDATE ON operations.partners        TO service_role, authenticated;
GRANT SELECT, INSERT         ON operations.partner_actions TO service_role, authenticated;
GRANT USAGE                  ON SEQUENCE operations.partner_seq TO service_role, authenticated;

-- Analytics: service_role writes; authenticated reads
GRANT USAGE ON SCHEMA analytics TO service_role, authenticated;
GRANT SELECT, INSERT ON analytics.page_views                TO service_role, authenticated;
GRANT SELECT, INSERT ON analytics.events                    TO service_role, authenticated;
GRANT SELECT, INSERT ON analytics.restaurant_profile_views  TO service_role, authenticated;
GRANT SELECT, INSERT ON analytics.search_terms              TO service_role, authenticated;
GRANT SELECT, INSERT ON analytics.ask_goldpan_sessions      TO service_role, authenticated;
