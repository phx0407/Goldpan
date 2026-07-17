-- ============================================================
-- 009_ai_usage_tracking.sql
-- AI Usage OS foundation — cost tracking and budget controls.
--
-- Tables:
--   operations.ai_usage_logs    — one row per AI API call
--   operations.budget_controls  — singleton budget/feature flag config
--
-- Design principles:
--   - Every AI call writes a row here before returning output
--   - budget_controls is a singleton (enforced by CHECK on scope='global')
--   - Cost estimates are stored at call time; actual_cost populated if
--     provider confirms billing (future)
--   - This table is append-only for logs; budget_controls is admin-writable
--   - Costs are in USD. estimated_cost uses published per-token pricing
--     at call time. actual_cost reflects confirmed billing when available.
--
-- Note: schema uses 'operations' (not 'ops') per GoldPan schema conventions.
-- ============================================================


-- ── operations.ai_usage_logs ──────────────────────────────────────────────────
-- One row per AI API call. Written by goldpan_ai_client.py on every call.

CREATE TABLE IF NOT EXISTS operations.ai_usage_logs (
    log_id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Call identity
    session_id          text,       -- intake session ID, pipeline run ID, or Ask GoldPan session
    run_id              uuid        REFERENCES knowledge.pipeline_runs(run_id) ON DELETE SET NULL,

    -- What was called
    provider            text        NOT NULL DEFAULT 'anthropic'
                        CHECK (provider IN ('anthropic','openai','google','other')),
    model               text        NOT NULL,   -- e.g. 'claude-haiku-4-5-20251001', 'claude-sonnet-4-6'
    purpose             text        NOT NULL
                        CHECK (purpose IN (
                            'intake',           -- intake_agent.py canvassing call
                            'escalation',       -- intake_agent.py escalation to stronger model
                            'ask_goldpan',      -- Ask GoldPan™ customer-facing AI explanation
                            'governance',       -- pipeline.py governance rule evaluation
                            'scoring',          -- transparency scoring AI assist
                            'testing',          -- dev/test calls
                            'other'
                        )),

    -- Context
    restaurant_id       uuid        REFERENCES evidence.restaurants(restaurant_id) ON DELETE SET NULL,
    restaurant_external_id text,    -- denormalized for query convenience
    dish_id             uuid        REFERENCES evidence.dishes(dish_id) ON DELETE SET NULL,
    dish_external_id    text,       -- denormalized

    -- Token counts
    input_tokens        int         NOT NULL DEFAULT 0,
    output_tokens       int         NOT NULL DEFAULT 0,
    total_tokens        int         GENERATED ALWAYS AS (input_tokens + output_tokens) STORED,

    -- Cost
    estimated_cost      numeric(10,6) NOT NULL DEFAULT 0,   -- USD, computed at call time
    actual_cost         numeric(10,6),                       -- USD, from provider billing if available
    cost_per_mtok_input  numeric(8,4),  -- input price per 1M tokens used for estimate
    cost_per_mtok_output numeric(8,4),  -- output price per 1M tokens used for estimate

    -- Outcome
    status              text        NOT NULL DEFAULT 'success'
                        CHECK (status IN ('success','error','timeout','budget_exceeded')),
    error_message       text,
    latency_ms          int,        -- wall-clock time of the API call

    -- Actor
    actor_id            uuid        REFERENCES operations.users(user_id) ON DELETE SET NULL,
    actor_type          text        NOT NULL DEFAULT 'system'
                        CHECK (actor_type IN ('canvasser','coordinator','admin','system','pipeline','customer')),

    created_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE operations.ai_usage_logs IS
    'One row per AI API call. Written by goldpan_ai_client.py. Append-only. '
    'Foundation of the AI Usage OS — cost attribution, budget enforcement, model performance tracking.';

COMMENT ON COLUMN operations.ai_usage_logs.session_id IS
    'Opaque session identifier. For intake: intake session UUID. For pipeline: run_id string. For Ask GoldPan: user session token.';
COMMENT ON COLUMN operations.ai_usage_logs.estimated_cost IS
    'USD cost computed at call time using published per-token pricing. Not guaranteed to match actual billing.';
COMMENT ON COLUMN operations.ai_usage_logs.total_tokens IS
    'Always = input_tokens + output_tokens. Generated column — do not set directly.';

-- Indexes for the cost query patterns the API will use
CREATE INDEX idx_ai_usage_created     ON operations.ai_usage_logs(created_at DESC);
CREATE INDEX idx_ai_usage_purpose     ON operations.ai_usage_logs(purpose, created_at DESC);
CREATE INDEX idx_ai_usage_model       ON operations.ai_usage_logs(model, created_at DESC);
CREATE INDEX idx_ai_usage_restaurant  ON operations.ai_usage_logs(restaurant_id, created_at DESC);
CREATE INDEX idx_ai_usage_status      ON operations.ai_usage_logs(status, created_at DESC);


-- ── operations.budget_controls ────────────────────────────────────────────────
-- Singleton budget and feature flag config for AI usage.
-- One active row (scope = 'global'). Admin-writable.

CREATE TABLE IF NOT EXISTS operations.budget_controls (
    control_id              uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    scope                   text    NOT NULL DEFAULT 'global'
                            CHECK (scope = 'global'),   -- singleton enforcement

    -- Budget limits (USD)
    daily_budget_limit      numeric(8,2) NOT NULL DEFAULT 10.00,
    monthly_budget_limit    numeric(8,2) NOT NULL DEFAULT 200.00,

    -- Per-feature budget caps
    ask_goldpan_daily_limit  numeric(8,2) NOT NULL DEFAULT 2.00,
    ask_goldpan_monthly_limit numeric(8,2) NOT NULL DEFAULT 30.00,

    -- Feature flags
    ask_goldpan_enabled     boolean NOT NULL DEFAULT false,
    intake_ai_enabled       boolean NOT NULL DEFAULT true,
    governance_ai_enabled   boolean NOT NULL DEFAULT true,

    -- Beta capacity messaging
    ask_goldpan_beta_message text    NOT NULL DEFAULT
        'Ask GoldPan™ is in limited beta. Daily capacity has been reached — please try again tomorrow.',
    budget_exceeded_message  text    NOT NULL DEFAULT
        'GoldPan AI services are temporarily paused. Please contact support.',

    -- Pricing reference (update when Anthropic pricing changes)
    -- Per 1M tokens, USD
    price_haiku_input       numeric(8,4) NOT NULL DEFAULT 0.80,
    price_haiku_output      numeric(8,4) NOT NULL DEFAULT 4.00,
    price_sonnet_input      numeric(8,4) NOT NULL DEFAULT 3.00,
    price_sonnet_output     numeric(8,4) NOT NULL DEFAULT 15.00,
    price_opus_input        numeric(8,4) NOT NULL DEFAULT 15.00,
    price_opus_output       numeric(8,4) NOT NULL DEFAULT 75.00,

    updated_at              timestamptz NOT NULL DEFAULT now(),
    updated_by              uuid        REFERENCES operations.users(user_id) ON DELETE SET NULL,

    UNIQUE (scope)  -- enforces singleton
);

COMMENT ON TABLE operations.budget_controls IS
    'Singleton budget and feature flag config for AI usage. One row (scope=global). '
    'Admin-writable. Read by goldpan_ai_client.py before every AI call.';

-- Seed the singleton row
INSERT INTO operations.budget_controls (scope) VALUES ('global')
ON CONFLICT (scope) DO NOTHING;


-- ── RLS policies ──────────────────────────────────────────────────────────────

ALTER TABLE operations.ai_usage_logs   ENABLE ROW LEVEL SECURITY;
ALTER TABLE operations.budget_controls ENABLE ROW LEVEL SECURITY;

-- ai_usage_logs: coordinators and admins can read; system/pipeline writes
CREATE POLICY "ai_usage_logs_select" ON operations.ai_usage_logs FOR SELECT
    USING (operations.current_user_role() IN ('coordinator','admin','governance_engine'));

CREATE POLICY "ai_usage_logs_insert" ON operations.ai_usage_logs FOR INSERT
    WITH CHECK (operations.current_user_role() IN (
        'canvasser','reviewer','coordinator','admin','governance_engine'
    ) OR current_user IN ('postgres','service_role'));

-- budget_controls: all authenticated can read; admin only writes
CREATE POLICY "budget_controls_select" ON operations.budget_controls FOR SELECT
    USING (operations.current_user_role() IN (
        'canvasser','reviewer','coordinator','admin','governance_engine'
    ));

CREATE POLICY "budget_controls_update" ON operations.budget_controls FOR UPDATE
    USING (operations.current_user_role() = 'admin')
    WITH CHECK (operations.current_user_role() = 'admin');


-- ── Grants ────────────────────────────────────────────────────────────────────
GRANT SELECT, INSERT ON operations.ai_usage_logs   TO service_role, authenticated;
GRANT SELECT         ON operations.budget_controls TO service_role, authenticated;
GRANT UPDATE         ON operations.budget_controls TO service_role;
