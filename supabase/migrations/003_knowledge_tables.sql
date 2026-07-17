-- ============================================================
-- 003_knowledge_tables.sql
-- Knowledge System tables — written exclusively by the Governance pipeline.
--
-- CRITICAL: No human user may INSERT or UPDATE these tables.
-- Only the governance_engine service role may write here.
-- RLS policies in 005_rls_policies.sql enforce this.
--
-- Tables:
--   knowledge.pipeline_runs        — pipeline execution log
--   knowledge.pipeline_stages      — individual stage results per run
--   knowledge.derived_filters      — computed filter conclusions per dish
--   knowledge.transparency_scores  — per-dish transparency scoring
--   knowledge.filter_registry      — registered filters with metadata
--   knowledge.freshness_state      — current freshness snapshot per restaurant
-- ============================================================


-- ── knowledge.pipeline_runs ──────────────────────────────────────────────────
-- Every pipeline execution is logged here. This is the primary record of
-- what the Governance OS computed and when.

CREATE TABLE knowledge.pipeline_runs (
    run_id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type            text        NOT NULL DEFAULT 'full'
                        CHECK (run_type IN ('full','partial','dry_run','freshness_only')),
    restaurant_ids      text[],     -- NULL = all-restaurant run
    status              text        NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running','completed','failed','dry_run_complete')),
    started_at          timestamptz NOT NULL DEFAULT now(),
    completed_at        timestamptz,
    triggered_by        text,       -- user_id, 'schedule', or 'system'
    commit_mode         boolean     NOT NULL DEFAULT false,  -- false = dry run
    stages_summary      jsonb,      -- high-level per-stage pass/warn/fail summary
    error               text,
    goldpan_version     text        -- pipeline.py version if available
);

COMMENT ON TABLE knowledge.pipeline_runs IS
    'Pipeline execution log. Written by governance_engine only. One row per run.';


-- ── knowledge.pipeline_stages ────────────────────────────────────────────────
-- Individual StageResult for each stage of each pipeline run.

CREATE TABLE knowledge.pipeline_stages (
    stage_id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              uuid        NOT NULL
                            REFERENCES knowledge.pipeline_runs(run_id)
                            ON DELETE CASCADE,
    stage_number        int         NOT NULL,
    stage_name          text        NOT NULL,
    status              text        NOT NULL
                        CHECK (status IN ('passed','warned','failed','skipped')),
    blocking            boolean     NOT NULL DEFAULT false,
    inputs_received     jsonb,
    outputs_produced    jsonb,
    report              jsonb,
    errors              text[],
    warnings            text[],
    duration_s          numeric,
    timestamp           timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE knowledge.pipeline_stages IS
    'Individual StageResult per stage per run. Full structured output from each pipeline stage.';


-- ── knowledge.derived_filters ─────────────────────────────────────────────────
-- Computed filter conclusions — one row per (dish, filter_name) pair per run.
-- Replaces derived_filters.json.
--
-- No FK back to evidence tables for allergen_flags or ingredient rows —
-- the Knowledge/Evidence boundary is one-way. The pipeline reads evidence;
-- it writes here. Knowledge never modifies evidence.

CREATE TABLE knowledge.derived_filters (
    filter_result_id        uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  uuid    REFERENCES knowledge.pipeline_runs(run_id),
    dish_id                 uuid    NOT NULL
                                REFERENCES evidence.dishes(dish_id)
                                ON DELETE RESTRICT,
    dish_external_id        text    NOT NULL,
    restaurant_id           uuid    NOT NULL
                                REFERENCES evidence.restaurants(restaurant_id)
                                ON DELETE RESTRICT,
    restaurant_external_id  text    NOT NULL,

    -- Filter identity
    filter_slug             text    NOT NULL,   -- e.g. "no_beef_identified"
    filter_name             text    NOT NULL,   -- e.g. "No Beef Identified"
    dependency_type         text    NOT NULL
                            CHECK (dependency_type IN (
                                'macro_dependent','mixed_dependent',
                                'micro_dependent','restaurant_claim_dependent'
                            )),

    -- Result
    conclusion              text    NOT NULL,   -- "computed" / "unknown" / "not_applicable"
    conclusion_label        text,               -- human-readable result label
    confidence              text
                            CHECK (confidence IN ('verified','declared','inferred','likely','unknown', NULL)),

    -- Explanation (GP-RULE-006)
    evidence_used           jsonb,
    reasoning               text,
    limitations             text,
    rule_ids                text[],

    -- Freshness context at computation time
    recanvass_status_at_computation text,
    freshness_context       jsonb,

    computed_at             timestamptz NOT NULL DEFAULT now(),
    is_current              boolean     NOT NULL DEFAULT true   -- false = superseded by newer run
);

COMMENT ON TABLE knowledge.derived_filters IS
    'Computed filter conclusions. Written by governance_engine only. is_current=false for superseded runs.';
COMMENT ON COLUMN knowledge.derived_filters.conclusion IS
    'computed = filter evaluated and result available. unknown = evidence insufficient. not_applicable = filter not relevant to this dish.';

-- Index to quickly fetch current conclusions for a dish
CREATE INDEX idx_derived_filters_dish_current
    ON knowledge.derived_filters(dish_id, is_current)
    WHERE is_current = true;

CREATE INDEX idx_derived_filters_restaurant
    ON knowledge.derived_filters(restaurant_id, is_current);


-- ── knowledge.transparency_scores ─────────────────────────────────────────────
-- Per-dish transparency scores — one row per dish per run.
-- Replaces the Transparency Scoring Google Sheet as the live data source.

CREATE TABLE knowledge.transparency_scores (
    score_id                uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  uuid    REFERENCES knowledge.pipeline_runs(run_id),
    dish_id                 uuid    NOT NULL
                                REFERENCES evidence.dishes(dish_id)
                                ON DELETE RESTRICT,
    dish_external_id        text    NOT NULL,
    restaurant_id           uuid    NOT NULL
                                REFERENCES evidence.restaurants(restaurant_id)
                                ON DELETE RESTRICT,
    restaurant_external_id  text    NOT NULL,

    -- Score components (0–25 each, canonical model per SCORING_ARCHITECTURE.md)
    core_clarity            numeric NOT NULL DEFAULT 0
                            CHECK (core_clarity >= 0 AND core_clarity <= 25),
    sauce_seasoning_disclosure numeric NOT NULL DEFAULT 0
                            CHECK (sauce_seasoning_disclosure >= 0 AND sauce_seasoning_disclosure <= 25),
    allergen_transparency   numeric NOT NULL DEFAULT 0
                            CHECK (allergen_transparency >= 0 AND allergen_transparency <= 25),
    prep_clarity            numeric NOT NULL DEFAULT 0
                            CHECK (prep_clarity >= 0 AND prep_clarity <= 25),
    total_score             numeric GENERATED ALWAYS AS
                                (core_clarity + sauce_seasoning_disclosure + allergen_transparency + prep_clarity)
                                STORED,
    transparency_level      text
                            CHECK (transparency_level IN (
                                'Building Transparency','Moderate Transparency','High Transparency', NULL
                            )),
    scoring_notes           text,

    computed_at             timestamptz NOT NULL DEFAULT now(),
    is_current              boolean     NOT NULL DEFAULT true
);

COMMENT ON TABLE knowledge.transparency_scores IS
    'Per-dish transparency scores per SCORING_ARCHITECTURE.md. total_score is a generated column = sum of 4 components.';
COMMENT ON COLUMN knowledge.transparency_scores.total_score IS
    'Always = core_clarity + sauce_seasoning_disclosure + allergen_transparency + prep_clarity. No hidden normalization.';

CREATE INDEX idx_transparency_scores_dish_current
    ON knowledge.transparency_scores(dish_id, is_current)
    WHERE is_current = true;


-- ── knowledge.filter_registry ─────────────────────────────────────────────────
-- Registered derived filters — the canonical list of filters the pipeline
-- knows about. Analogous to derived/registry.py but stored in the database
-- for visibility in the Governance OS UI.

CREATE TABLE knowledge.filter_registry (
    filter_slug             text    PRIMARY KEY,    -- e.g. "no_beef_identified"
    filter_name             text    NOT NULL,       -- e.g. "No Beef Identified"
    dependency_type         text    NOT NULL
                            CHECK (dependency_type IN (
                                'macro_dependent','mixed_dependent',
                                'micro_dependent','restaurant_claim_dependent'
                            )),
    rule_ids                text[]  NOT NULL,       -- GP-RULE-XXX references
    description             text,
    is_active               boolean NOT NULL DEFAULT true,
    added_at                timestamptz NOT NULL DEFAULT now(),
    last_updated            timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE knowledge.filter_registry IS
    'Canonical list of registered derived filters. Mirrors derived/registry.py. Read-only for humans — updated by pipeline migrations only.';


-- ── Seed filter_registry with currently registered filters ───────────────────
INSERT INTO knowledge.filter_registry (filter_slug, filter_name, dependency_type, rule_ids, description) VALUES
    ('no_beef_identified',     'No Beef Identified',     'macro_dependent',
     ARRAY['GP-RULE-001','GP-RULE-002','GP-RULE-006','GP-RULE-007'],
     'No beef in the verified primary ingredient list. Not a beef-free claim.'),
    ('no_pork_identified',     'No Pork Identified',     'macro_dependent',
     ARRAY['GP-RULE-001','GP-RULE-002','GP-RULE-006','GP-RULE-007'],
     'No pork in the verified primary ingredient list. Not a pork-free claim.'),
    ('no_wheat_identified',    'No Wheat Ingredients Identified',  'macro_dependent',
     ARRAY['GP-RULE-001','GP-RULE-002','GP-RULE-006','GP-RULE-007','GP-RULE-014','GP-RULE-015','GP-RULE-016'],
     'No wheat-containing ingredients in the verified list. Not a gluten-free claim.'),
    ('no_milk_identified',     'No Milk Ingredients Identified',   'macro_dependent',
     ARRAY['GP-RULE-001','GP-RULE-002','GP-RULE-006','GP-RULE-007','GP-RULE-014','GP-RULE-015','GP-RULE-016'],
     'No milk/dairy ingredients in the verified list.'),
    ('no_eggs_identified',     'No Egg Ingredients Identified',    'macro_dependent',
     ARRAY['GP-RULE-001','GP-RULE-002','GP-RULE-006','GP-RULE-007','GP-RULE-014','GP-RULE-015','GP-RULE-016'],
     'No egg ingredients in the verified list.'),
    ('no_soy_identified',      'No Soy Ingredients Identified',    'macro_dependent',
     ARRAY['GP-RULE-001','GP-RULE-002','GP-RULE-006','GP-RULE-007','GP-RULE-014','GP-RULE-015','GP-RULE-016'],
     'No soy ingredients in the verified list.'),
    ('no_peanuts_identified',  'No Peanut Ingredients Identified', 'macro_dependent',
     ARRAY['GP-RULE-001','GP-RULE-002','GP-RULE-006','GP-RULE-007','GP-RULE-014','GP-RULE-015','GP-RULE-016'],
     'No peanut ingredients in the verified list.'),
    ('no_tree_nuts_identified','No Tree Nut Ingredients Identified','macro_dependent',
     ARRAY['GP-RULE-001','GP-RULE-002','GP-RULE-006','GP-RULE-007','GP-RULE-014','GP-RULE-015','GP-RULE-016'],
     'No tree nut ingredients in the verified list.'),
    ('no_fish_identified',     'No Fish Ingredients Identified',   'macro_dependent',
     ARRAY['GP-RULE-001','GP-RULE-002','GP-RULE-006','GP-RULE-007','GP-RULE-014','GP-RULE-015','GP-RULE-016'],
     'No fish ingredients in the verified list.'),
    ('no_shellfish_identified','No Shellfish Ingredients Identified','macro_dependent',
     ARRAY['GP-RULE-001','GP-RULE-002','GP-RULE-006','GP-RULE-007','GP-RULE-014','GP-RULE-015','GP-RULE-016'],
     'No shellfish ingredients in the verified list.'),
    ('no_sesame_identified',   'No Sesame Ingredients Identified', 'macro_dependent',
     ARRAY['GP-RULE-001','GP-RULE-002','GP-RULE-006','GP-RULE-007','GP-RULE-014','GP-RULE-015','GP-RULE-016'],
     'No sesame ingredients in the verified list.')
ON CONFLICT (filter_slug) DO NOTHING;


-- ── knowledge.freshness_state ─────────────────────────────────────────────────
-- Current freshness snapshot per restaurant — the synthesized verdict
-- that the rules engine reads (GP-RULE-008).
-- One active row per restaurant at any time.

CREATE TABLE knowledge.freshness_state (
    freshness_id            uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id           uuid    NOT NULL UNIQUE
                                REFERENCES evidence.restaurants(restaurant_id)
                                ON DELETE RESTRICT,
    restaurant_external_id  text    NOT NULL,
    recanvass_status        text    NOT NULL DEFAULT 'needs_review'
                            CHECK (recanvass_status IN (
                                'current','due_soon','overdue','needs_review'
                            )),
    source_check_status     text    NOT NULL DEFAULT 'unknown'
                            CHECK (source_check_status IN (
                                'ok','changed','unreachable','overdue','unknown'
                            )),
    last_canvassed          date,
    days_since_canvass      int,    -- computed at last freshness run
    recanvass_tier          int,
    recanvass_window_days   int,    -- days in the tier window (30/90/180)
    days_until_due          int,    -- negative = overdue
    computed_at             timestamptz NOT NULL DEFAULT now(),
    run_id                  uuid    REFERENCES knowledge.pipeline_runs(run_id)
);

COMMENT ON TABLE knowledge.freshness_state IS
    'Current freshness snapshot per restaurant. The rules engine reads recanvass_status from here (GP-RULE-008). One active row per restaurant.';
