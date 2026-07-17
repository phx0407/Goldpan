-- ============================================================
-- 004_operations_tables.sql
-- Operations layer — users, audit trail, jobs, feature flags,
-- rules registry.
--
-- Tables:
--   operations.users           — canvassers, reviewers, admins
--   operations.user_roles      — role assignments
--   operations.rules_registry  — GP-RULE definitions (read-only)
--   operations.audit_log       — catch-all evidence change log
--   operations.background_jobs — job queue
--   operations.notifications   — alert queue
--   operations.feature_flags   — per-level feature toggles
--   operations.report_cache    — pre-generated report cache
-- ============================================================


-- ── operations.users ─────────────────────────────────────────────────────────
-- Mirrors Supabase Auth users. Created automatically via trigger when a
-- new Supabase Auth user is created. The uuid matches auth.users.id.

CREATE TABLE operations.users (
    user_id             uuid        PRIMARY KEY,    -- matches auth.users.id
    email               text        UNIQUE NOT NULL,
    display_name        text,
    role                text        NOT NULL DEFAULT 'canvasser'
                        CHECK (role IN ('canvasser','reviewer','coordinator','admin')),
    is_active           boolean     NOT NULL DEFAULT true,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE operations.users IS
    'GoldPan users. UUID matches Supabase Auth user. role determines access scope.';

-- Now that operations.users exists, add FK constraints that reference it
ALTER TABLE evidence.restaurants
    ADD CONSTRAINT fk_status_updated_by
        FOREIGN KEY (status_updated_by) REFERENCES operations.users(user_id),
    ADD CONSTRAINT fk_coverage_approved_by
        FOREIGN KEY (coverage_approved_by) REFERENCES operations.users(user_id),
    ADD CONSTRAINT fk_assigned_canvasser
        FOREIGN KEY (assigned_canvasser_id) REFERENCES operations.users(user_id),
    ADD CONSTRAINT fk_assigned_reviewer
        FOREIGN KEY (assigned_reviewer_id) REFERENCES operations.users(user_id);

ALTER TABLE evidence.lifecycle_events
    ADD CONSTRAINT fk_actor_id
        FOREIGN KEY (actor_id) REFERENCES operations.users(user_id);


-- ── operations.rules_registry ─────────────────────────────────────────────────
-- GP-RULE definitions — read-only in the UI.
-- Updated only by database migrations (never by admin actions).

CREATE TABLE operations.rules_registry (
    rule_id             text        PRIMARY KEY,    -- "GP-RULE-001"
    rule_name           text        NOT NULL,
    category            text        NOT NULL
                        CHECK (category IN (
                            'General Knowledge','Evidence',
                            'Domain-Specific Knowledge','Communication'
                        )),
    version             text        NOT NULL DEFAULT '1.0',
    last_updated        date        NOT NULL,
    description         text,
    is_active           boolean     NOT NULL DEFAULT true,
    deprecated_by       text,       -- rule_id that supersedes this one
    changelog           text,       -- version changelog notes
    created_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE operations.rules_registry IS
    'GP-RULE definitions. Read-only in the UI — changes require a database migration and version increment.';

-- Seed all 16 current GP-RULEs
INSERT INTO operations.rules_registry (rule_id, rule_name, category, version, last_updated, description) VALUES
    ('GP-RULE-001', 'Material Evidence Rule',                    'General Knowledge',         '1.1', '2026-06-28', 'Governs when GoldPan has enough verified evidence to compute a derived conclusion.'),
    ('GP-RULE-002', 'Disclosed Absence Rule',                    'General Knowledge',         '1.1', '2026-06-28', 'Governs when GoldPan may conclude a specific ingredient or allergen is absent.'),
    ('GP-RULE-003', 'Undisclosed Ingredient Rule',               'General Knowledge',         '1.1', '2026-06-28', 'GoldPan cannot reason from the absence of a micro ingredient disclosure to conclude it is absent.'),
    ('GP-RULE-004', 'Supporting Documents Rule',                 'General Knowledge',         '1.0', '2026-06-28', 'Defines how GoldPan uses official supporting documents as evidence sources.'),
    ('GP-RULE-005', 'No Unsupported Inference Rule',             'General Knowledge',         '1.0', '2026-06-28', 'Prohibits derived conclusions through inference, extrapolation, or general knowledge.'),
    ('GP-RULE-006', 'Derived Filter Explanation Rule',           'General Knowledge',         '1.0', '2026-06-28', 'Every derived filter must have a structured four-part explanation.'),
    ('GP-RULE-007', 'Filter Evidence Dependency Rule',           'General Knowledge',         '1.0', '2026-06-28', 'Every derived filter must declare its evidence dependency type.'),
    ('GP-RULE-008', 'Data Freshness Rule',                       'General Knowledge',         '1.1', '2026-06-29', 'A derived conclusion is only valid while its evidence source is reasonably current.'),
    ('GP-RULE-009', 'Stale Evidence Confidence Degradation Rule','General Knowledge',         '1.0', '2026-06-28', 'Specifies confidence outcomes for each Recanvass_Status value.'),
    ('GP-RULE-010', 'Source Authority Hierarchy Rule',           'Evidence',                  '1.0', '2026-06-28', 'Defines the canonical hierarchy of trusted acquisition sources.'),
    ('GP-RULE-011', 'Evidence Provenance Rule',                  'Evidence',                  '1.0', '2026-06-28', 'Every fact used as engine input must carry complete provenance.'),
    ('GP-RULE-012', 'Acquisition Conflict Resolution Rule',      'Evidence',                  '1.0', '2026-06-28', 'Defines what GoldPan does when two sources disagree about the same fact.'),
    ('GP-RULE-013', 'Dietary Tag Provenance Rule',               'Evidence',                  '1.0', '2026-06-30', 'Defines Tag_Source requirements for all dietary tags.'),
    ('GP-RULE-014', 'Allergen Evidence Rule',                    'Evidence',                  '1.0', '2026-06-30', 'Governs how GoldPan records allergen evidence in the Evidence System.'),
    ('GP-RULE-015', 'Allergen Knowledge Rule',                   'Domain-Specific Knowledge', '1.0', '2026-06-30', 'Governs how GoldPan computes allergen-related conclusions from Evidence inputs.'),
    ('GP-RULE-016', 'Allergen Communication Rule',               'Communication',             '1.0', '2026-06-30', 'Governs how GoldPan presents allergen information to customers.')
ON CONFLICT (rule_id) DO NOTHING;


-- ── operations.audit_log ─────────────────────────────────────────────────────
-- Catch-all audit log for all evidence table changes and admin actions.
-- Written by triggers in 006_triggers.sql.

CREATE TABLE operations.audit_log (
    audit_id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    table_schema        text        NOT NULL DEFAULT 'evidence',
    table_name          text        NOT NULL,
    record_id           uuid,
    operation           text        NOT NULL
                        CHECK (operation IN ('INSERT','UPDATE','DELETE','ADMIN')),
    actor_id            uuid,       -- FK to operations.users; NULL = system/pipeline
    actor_type          text        NOT NULL DEFAULT 'system'
                        CHECK (actor_type IN ('user','pipeline','system','schedule')),
    old_values          jsonb,      -- NULL for INSERT
    new_values          jsonb,      -- NULL for DELETE
    reason              text,       -- required for allergen-related changes
    changed_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE operations.audit_log IS
    'Catch-all audit log. Triggers prevent UPDATE/DELETE on this table. Allergen changes require a reason.';

CREATE INDEX idx_audit_log_table     ON operations.audit_log(table_name, changed_at DESC);
CREATE INDEX idx_audit_log_actor     ON operations.audit_log(actor_id, changed_at DESC);
CREATE INDEX idx_audit_log_record    ON operations.audit_log(record_id);


-- ── operations.background_jobs ───────────────────────────────────────────────
-- Job queue for async operations: source checks, pipeline runs, report generation.

CREATE TABLE operations.background_jobs (
    job_id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type            text        NOT NULL
                        CHECK (job_type IN (
                            'source_check','recanvass_scan','pipeline_run',
                            'report_generation','ai_cost_summary','freshness_run'
                        )),
    status              text        NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','running','completed','failed')),
    restaurant_id       uuid        REFERENCES evidence.restaurants(restaurant_id),
    restaurant_external_id text,    -- denormalized
    triggered_by        text        NOT NULL DEFAULT 'schedule',
    triggered_at        timestamptz NOT NULL DEFAULT now(),
    started_at          timestamptz,
    completed_at        timestamptz,
    error               text,
    result_summary      jsonb,
    retry_count         int         NOT NULL DEFAULT 0
);

COMMENT ON TABLE operations.background_jobs IS
    'Job queue for async operations. Polled by the job worker process.';

CREATE INDEX idx_jobs_status    ON operations.background_jobs(status, triggered_at);
CREATE INDEX idx_jobs_type      ON operations.background_jobs(job_type, status);


-- ── operations.notifications ─────────────────────────────────────────────────
-- Alert queue surfaced in the backend dashboard.

CREATE TABLE operations.notifications (
    notification_id     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_type   text        NOT NULL,
    severity            text        NOT NULL DEFAULT 'info'
                        CHECK (severity IN ('info','warning','alert','critical')),
    restaurant_id       uuid        REFERENCES evidence.restaurants(restaurant_id),
    title               text        NOT NULL,
    message             text,
    is_read             boolean     NOT NULL DEFAULT false,
    created_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE operations.notifications IS
    'Alert queue. Surfaced in the backend dashboard. Triggered by jobs, pipeline failures, and freshness events.';

CREATE INDEX idx_notifications_unread ON operations.notifications(is_read, created_at DESC)
    WHERE is_read = false;


-- ── operations.feature_flags ─────────────────────────────────────────────────
-- Per-level feature toggles: global, restaurant, or user.

CREATE TABLE operations.feature_flags (
    flag_id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    flag_name           text        NOT NULL,
    flag_type           text        NOT NULL
                        CHECK (flag_type IN ('global','restaurant','user')),
    target_id           uuid,       -- restaurant_id or user_id; NULL for global
    is_enabled          boolean     NOT NULL DEFAULT false,
    description         text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),

    UNIQUE (flag_name, flag_type, target_id)
);

COMMENT ON TABLE operations.feature_flags IS
    'Feature toggles. Resolution order: restaurant > user > global. Default = disabled.';

-- Seed global feature flags
INSERT INTO operations.feature_flags (flag_name, flag_type, is_enabled, description) VALUES
    ('ask_goldpan_beta',          'global', false, 'Enables Ask GoldPan™ AI explanation layer in the public interface'),
    ('public_api_v2',             'global', false, 'Enables v2 of the public dishes endpoint'),
    ('allergen_communication_v2', 'global', false, 'Enables GP-RULE-016 compliant allergen display format'),
    ('supabase_pipeline_mode',    'global', false, 'Pipeline reads from Supabase instead of Google Sheets')
ON CONFLICT DO NOTHING;


-- ── operations.report_cache ──────────────────────────────────────────────────
-- Pre-generated report cache. Reports are generated by background jobs and
-- read by the UI from cache. Never generated inline.

CREATE TABLE operations.report_cache (
    cache_id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    report_name         text        NOT NULL,
    report_params       jsonb,      -- any filter params used to generate this report
    report_data         jsonb       NOT NULL,
    generated_at        timestamptz NOT NULL DEFAULT now(),
    expires_at          timestamptz,
    job_id              uuid        REFERENCES operations.background_jobs(job_id),

    UNIQUE (report_name, report_params)
);

COMMENT ON TABLE operations.report_cache IS
    'Pre-generated report cache. Reports are generated by background jobs; UI reads from here.';

CREATE INDEX idx_report_cache_name ON operations.report_cache(report_name, generated_at DESC);
