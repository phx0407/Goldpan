-- ============================================================
-- 007_views.sql
-- Public views for application output.
--
-- These views power the public dishes API endpoint and replace
-- the dishes.json / restaurants.json static files.
-- They join evidence + knowledge tables into the shapes the
-- application currently expects.
--
-- Views:
--   public.v_dishes          — replaces dishes.json
--   public.v_restaurants     — replaces restaurants.json
--   public.v_freshness       — freshness monitor for the Governance OS UI
--   public.v_pipeline_status — restaurant pipeline status for Intake OS UI
-- ============================================================


-- ── public.v_dishes ───────────────────────────────────────────────────────────
-- Replaces dishes.json. Joins dishes with their current transparency score
-- and all current derived filter conclusions.
-- The application (fetch_dishes.py) builds this; in Supabase it is a view.

CREATE OR REPLACE VIEW public.v_dishes AS
SELECT
    d.external_id           AS dish_id,
    d.dish_name,
    d.category,
    d.description,
    d.price,
    d.dietary_tags          AS tags,
    d.tag_source,
    d.dietary_options       AS options,
    d.allergen_summary      AS allergens,
    d.calorie_value,
    d.calorie_source_text,
    d.hours,
    d.menu_link,
    d.restaurant_address,
    d.restaurant_website,
    d.last_updated,

    -- Restaurant identity
    r.external_id           AS restaurant_id,
    r.name                  AS restaurant_name,
    r.location,

    -- Current transparency score
    ts.core_clarity,
    ts.sauce_seasoning_disclosure,
    ts.allergen_transparency,
    ts.prep_clarity,
    ts.total_score,
    ts.transparency_level,

    -- Freshness state
    r.recanvass_status,
    r.last_canvassed,

    -- Derived filter conclusions (aggregated as JSON object keyed by filter_slug)
    COALESCE(
        jsonb_object_agg(
            df.filter_slug,
            jsonb_build_object(
                'conclusion',       df.conclusion,
                'conclusion_label', df.conclusion_label,
                'confidence',       df.confidence,
                'reasoning',        df.reasoning,
                'limitations',      df.limitations,
                'rule_ids',         df.rule_ids,
                'computed_at',      df.computed_at
            )
        ) FILTER (WHERE df.filter_slug IS NOT NULL),
        '{}'::jsonb
    )                       AS derived_filters

FROM evidence.dishes d
JOIN evidence.restaurants r ON r.restaurant_id = d.restaurant_id
LEFT JOIN knowledge.transparency_scores ts
    ON ts.dish_id = d.dish_id AND ts.is_current = true
LEFT JOIN knowledge.derived_filters df
    ON df.dish_id = d.dish_id AND df.is_current = true

WHERE d.is_active = true
  AND r.lifecycle_status = 'published'

GROUP BY
    d.dish_id, d.external_id, d.dish_name, d.category, d.description, d.price,
    d.dietary_tags, d.tag_source, d.dietary_options, d.allergen_summary,
    d.calorie_value, d.calorie_source_text, d.hours, d.menu_link,
    d.restaurant_address, d.restaurant_website, d.last_updated,
    r.external_id, r.name, r.location, r.recanvass_status, r.last_canvassed,
    ts.core_clarity, ts.sauce_seasoning_disclosure, ts.allergen_transparency,
    ts.prep_clarity, ts.total_score, ts.transparency_level;

COMMENT ON VIEW public.v_dishes IS
    'Application dish output. Replaces dishes.json. Joins evidence + knowledge for all published dishes.';


-- ── public.v_restaurants ─────────────────────────────────────────────────────
-- Restaurant-level summary view. Replaces restaurants.json.

CREATE OR REPLACE VIEW public.v_restaurants AS
SELECT
    r.external_id           AS restaurant_id,
    r.name                  AS restaurant_name,
    r.location,
    r.address,
    r.city,
    r.state,
    r.official_website      AS restaurant_website,
    r.menu_url              AS menu_link,
    r.hours,
    r.menu_statement,
    r.has_allergen_guide,
    r.evidence_tier,
    r.recanvass_status,
    r.last_canvassed,
    COUNT(DISTINCT d.dish_id) AS dish_count,
    AVG(ts.total_score)       AS avg_transparency_score
FROM evidence.restaurants r
LEFT JOIN evidence.dishes d ON d.restaurant_id = r.restaurant_id AND d.is_active = true
LEFT JOIN knowledge.transparency_scores ts
    ON ts.restaurant_id = r.restaurant_id AND ts.is_current = true
WHERE r.lifecycle_status = 'published'
GROUP BY
    r.restaurant_id, r.external_id, r.name, r.location, r.address, r.city, r.state,
    r.official_website, r.menu_url, r.hours, r.menu_statement, r.has_allergen_guide,
    r.evidence_tier, r.recanvass_status, r.last_canvassed;

COMMENT ON VIEW public.v_restaurants IS
    'Restaurant-level summary view. Replaces restaurants.json.';


-- ── public.v_freshness ───────────────────────────────────────────────────────
-- Freshness monitor for the Governance OS UI dashboard.
-- Shows all published restaurants with their current freshness state.

CREATE OR REPLACE VIEW public.v_freshness AS
SELECT
    r.external_id               AS restaurant_id,
    r.name                      AS restaurant_name,
    r.lifecycle_status,
    r.recanvass_status,
    r.recanvass_tier,
    r.last_canvassed,
    r.source_check_status,
    r.last_source_check,
    fs.days_since_canvass,
    fs.recanvass_window_days,
    fs.days_until_due,
    fs.computed_at              AS freshness_computed_at,
    COUNT(DISTINCT d.dish_id)   AS dish_count
FROM evidence.restaurants r
LEFT JOIN knowledge.freshness_state fs ON fs.restaurant_id = r.restaurant_id
LEFT JOIN evidence.dishes d ON d.restaurant_id = r.restaurant_id AND d.is_active = true
WHERE r.lifecycle_status IN ('published','recanvassing')
GROUP BY
    r.restaurant_id, r.external_id, r.name, r.lifecycle_status,
    r.recanvass_status, r.recanvass_tier, r.last_canvassed,
    r.source_check_status, r.last_source_check,
    fs.days_since_canvass, fs.recanvass_window_days, fs.days_until_due, fs.computed_at
ORDER BY
    CASE r.recanvass_status
        WHEN 'needs_review' THEN 1
        WHEN 'overdue'      THEN 2
        WHEN 'due_soon'     THEN 3
        WHEN 'current'      THEN 4
    END,
    r.last_canvassed ASC NULLS FIRST;

COMMENT ON VIEW public.v_freshness IS
    'Freshness monitor view for Governance OS UI. Ordered by urgency: needs_review → overdue → due_soon → current.';


-- ── public.v_pipeline_status ─────────────────────────────────────────────────
-- Restaurant pipeline status for the Intake OS dashboard.
-- Shows all restaurants with their current lifecycle stage and blocker flags.

CREATE OR REPLACE VIEW public.v_pipeline_status AS
SELECT
    r.external_id           AS restaurant_id,
    r.name                  AS restaurant_name,
    r.lifecycle_status,
    r.status_updated_at,
    r.recanvass_status,
    r.last_canvassed,
    r.has_allergen_guide,
    r.evidence_tier,
    -- Canvasser info
    cu.display_name         AS canvasser_name,
    ru.display_name         AS reviewer_name,
    -- Last lifecycle event
    (
        SELECT le.to_status || ' — ' || COALESCE(le.notes, '')
        FROM evidence.lifecycle_events le
        WHERE le.restaurant_id = r.restaurant_id
        ORDER BY le.created_at DESC
        LIMIT 1
    )                       AS last_transition,
    COUNT(DISTINCT d.dish_id) AS dish_count
FROM evidence.restaurants r
LEFT JOIN operations.users cu ON cu.user_id = r.assigned_canvasser_id
LEFT JOIN operations.users ru ON ru.user_id = r.assigned_reviewer_id
LEFT JOIN evidence.dishes d ON d.restaurant_id = r.restaurant_id AND d.is_active = true
WHERE r.lifecycle_status NOT IN ('deactivated')
GROUP BY
    r.restaurant_id, r.external_id, r.name, r.lifecycle_status, r.status_updated_at,
    r.recanvass_status, r.last_canvassed, r.has_allergen_guide, r.evidence_tier,
    cu.display_name, ru.display_name
ORDER BY
    CASE r.lifecycle_status
        WHEN 'qa_review'           THEN 1
        WHEN 'verification'        THEN 2
        WHEN 'evidence_acquisition' THEN 3
        WHEN 'onboarding'          THEN 4
        WHEN 'qualified'           THEN 5
        WHEN 'prospect'            THEN 6
        WHEN 'recanvassing'        THEN 7
        WHEN 'published'           THEN 8
        WHEN 'suspended'           THEN 9
    END,
    r.name ASC;

COMMENT ON VIEW public.v_pipeline_status IS
    'Restaurant pipeline status for Intake OS UI. Ordered by stage urgency.';
