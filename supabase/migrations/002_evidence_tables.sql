-- ============================================================
-- 002_evidence_tables.sql
-- Evidence System tables — owned exclusively by Intake OS.
--
-- Tables:
--   evidence.restaurants         — canonical restaurant entity
--   evidence.lifecycle_events    — append-only audit trail
--   evidence.menu_sources        — Menu Source Registry
--   evidence.source_documents    — archived PDFs / allergen guides
--   evidence.dishes              — one row per dish
--   evidence.ingredients         — one row per ingredient per dish
--   evidence.allergen_disclosures — restaurant allergen statements
--   evidence.restaurant_claims   — restaurant-level dietary claims
--   evidence.intake_sessions     — AI/human intake session log
-- ============================================================

-- ── Enable uuid extension ────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ── evidence.restaurants ─────────────────────────────────────────────────────
-- The canonical restaurant entity. Every OS module references this table.
-- External IDs ("R027") are preserved for backwards compatibility with all
-- existing scripts, staging files, and Google Sheets rows.

CREATE TABLE evidence.restaurants (
    -- Core identity (immutable after creation)
    restaurant_id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id         text        UNIQUE NOT NULL,    -- e.g. "R027"
    name                text        NOT NULL,
    location            text,                           -- free-form, e.g. "Nashville, TN"
    address             text,
    neighborhood        text,
    city                text,
    state               text,
    zip                 text,
    latitude            numeric,
    longitude           numeric,

    -- Operating identity (updated on recanvassing)
    official_website    text,
    menu_url            text,
    online_ordering_url text,
    phone               text,
    hours               text,       -- raw hours string from primary source
    menu_statement      text,       -- restaurant's own description of their food

    -- Lifecycle state
    lifecycle_status    text        NOT NULL DEFAULT 'prospect'
                        CHECK (lifecycle_status IN (
                            'prospect','qualified','onboarding',
                            'evidence_acquisition','verification','qa_review',
                            'published','recanvassing','suspended','deactivated'
                        )),
    status_updated_at   timestamptz,
    status_updated_by   uuid,       -- FK to operations.users added in 004

    -- Coverage (written at qualification)
    prospect_source     text        CHECK (prospect_source IN (
                            'customer_request','canvasser_discovery',
                            'market_expansion','partner_referral', NULL
                        )),
    prospect_date       date,
    coverage_signal     text,       -- documented rationale (S1–S5)
    coverage_approved_by uuid,      -- FK to operations.users added in 004
    coverage_approved_at timestamptz,

    -- Evidence quality
    evidence_tier       text        CHECK (evidence_tier IN (
                            'Tier_1_Confirmed','Tier_2_Disclosed',
                            'Tier_3_Inferred', NULL
                        )),
    primary_source_url  text,
    primary_source_tier text        CHECK (primary_source_tier IN ('Tier_1','Tier_2','Tier_3', NULL)),
    has_allergen_guide  boolean     NOT NULL DEFAULT false,

    -- Operations
    assigned_canvasser_id uuid,     -- FK to operations.users added in 004
    assigned_reviewer_id  uuid,     -- FK to operations.users added in 004
    published_date      date,
    last_canvassed      date,
    recanvass_status    text        NOT NULL DEFAULT 'needs_review'
                        CHECK (recanvass_status IN (
                            'current','due_soon','overdue','needs_review'
                        )),
    recanvass_tier      int         NOT NULL DEFAULT 2
                        CHECK (recanvass_tier IN (1, 2, 3)),

    -- Source check (Track A freshness — automated URL monitoring)
    last_source_check   date,
    source_check_status text        NOT NULL DEFAULT 'unknown'
                        CHECK (source_check_status IN (
                            'ok','changed','unreachable','overdue','unknown'
                        )),

    -- Menu_Changed / Change_Type (from freshness system)
    menu_changed        text,
    change_type         text,
    status_computed_date date,
    forced_recanvass_flag text,
    recanvass_notes     text,

    -- Exceptions
    suspension_reason   text,
    deactivation_reason text,
    notes               text,

    -- Timestamps
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE evidence.restaurants IS
    'Canonical restaurant entity. One row per restaurant. Referenced by every OS module.';
COMMENT ON COLUMN evidence.restaurants.external_id IS
    'Human-readable ID used in all scripts and staging files (e.g. R027). Never reassigned.';
COMMENT ON COLUMN evidence.restaurants.lifecycle_status IS
    'Current stage in INTAKE_OS_RESTAURANT_LIFECYCLE.md. Transitions are append-only in lifecycle_events.';


-- ── evidence.lifecycle_events ─────────────────────────────────────────────────
-- Append-only audit trail for every restaurant lifecycle transition.
-- Trigger in 006_triggers.sql prevents UPDATE and DELETE.
-- Also auto-created by trigger whenever restaurants.lifecycle_status changes.

CREATE TABLE evidence.lifecycle_events (
    lifecycle_event_id  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id       uuid        NOT NULL
                            REFERENCES evidence.restaurants(restaurant_id)
                            ON DELETE RESTRICT,
    event_date          date        NOT NULL DEFAULT current_date,
    from_status         text        NOT NULL,
    to_status           text        NOT NULL,
    actor_id            uuid,       -- FK to operations.users; NULL = system
    actor_type          text        NOT NULL DEFAULT 'system'
                        CHECK (actor_type IN (
                            'canvasser','reviewer','coordinator','admin',
                            'pipeline','freshness_system','system'
                        )),
    notes               text,
    created_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE evidence.lifecycle_events IS
    'Append-only audit trail. Trigger prevents UPDATE/DELETE. Auto-written on every restaurants status change.';


-- ── evidence.menu_sources ─────────────────────────────────────────────────────
-- Menu Source Registry — one row per restaurant (currently), tracks all
-- source URLs, freshness fields, and source-level metadata.

CREATE TABLE evidence.menu_sources (
    source_id               uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id           uuid    NOT NULL
                                REFERENCES evidence.restaurants(restaurant_id)
                                ON DELETE RESTRICT,
    restaurant_external_id  text    NOT NULL,   -- denormalized for pipeline convenience

    -- Source URLs
    official_website        text,
    official_menu_url       text,
    online_ordering_url     text,
    pdf_menu_url            text,
    allergen_nutrition_url  text,
    preferred_data_source   text,

    -- Source metadata
    menu_format             text,   -- HTML / PDF / App / etc.
    source_confidence       text    CHECK (source_confidence IN (
                                'Official','Third-Party','Unverified','Inferred', NULL
                            )),
    menu_status             text    CHECK (menu_status IN ('Active','Needs Review', NULL)),
    canvass_priority        text    CHECK (canvass_priority IN ('High','Medium','Low', NULL)),

    -- Freshness (Track A — source check)
    last_verified_date      date,
    last_menu_change_detected date,
    last_source_check       date,
    source_check_status     text    NOT NULL DEFAULT 'unknown'
                            CHECK (source_check_status IN (
                                'ok','changed','unreachable','overdue','unknown'
                            )),
    menu_changed            text,
    change_type             text,

    -- Freshness (Track B — full recanvass)
    recanvass_tier          int     NOT NULL DEFAULT 2
                            CHECK (recanvass_tier IN (1, 2, 3)),
    last_canvassed          date,
    recanvass_status        text    NOT NULL DEFAULT 'needs_review'
                            CHECK (recanvass_status IN (
                                'current','due_soon','overdue','needs_review'
                            )),
    status_computed_date    date,
    forced_recanvass_flag   text,
    recanvass_notes         text,

    notes                   text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE evidence.menu_sources IS
    'Menu Source Registry — one row per restaurant. Tracks source URLs and freshness state.';


-- ── evidence.source_documents ─────────────────────────────────────────────────
-- Archived PDFs, allergen guides, and other documents with Supabase Storage references.

CREATE TABLE evidence.source_documents (
    document_id             uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id           uuid    NOT NULL
                                REFERENCES evidence.restaurants(restaurant_id)
                                ON DELETE RESTRICT,
    document_type           text    NOT NULL
                            CHECK (document_type IN (
                                'allergen_guide','nutrition_document','menu_pdf','other'
                            )),
    storage_path            text,   -- Supabase Storage object path
    source_url              text,   -- original URL the document was obtained from
    document_date           date,   -- date the document was published/obtained
    is_current              boolean NOT NULL DEFAULT true,
    notes                   text,
    created_at              timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE evidence.source_documents IS
    'Archived source documents (PDFs, allergen guides). Storage path links to Supabase Storage.';


-- ── evidence.dishes ───────────────────────────────────────────────────────────
-- One row per dish. Tracks all fields from Goldpan Dish Level Data (DLD).
-- External IDs ("D766") are preserved for backwards compatibility.

CREATE TABLE evidence.dishes (
    dish_id                 uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id             text    UNIQUE NOT NULL,    -- e.g. "D766"
    restaurant_id           uuid    NOT NULL
                                REFERENCES evidence.restaurants(restaurant_id)
                                ON DELETE RESTRICT,
    restaurant_external_id  text    NOT NULL,           -- denormalized

    -- Dish identity
    dish_name               text    NOT NULL,
    menu_section            text,   -- raw menu section (from staging)
    category                text,   -- normalized category (Enhanced field v1.4.0)
    description             text,

    -- Pricing
    price                   text,   -- stored as text to preserve "$12" format

    -- Dietary
    dietary_tags            text,   -- comma-separated restaurant-disclosed tags
    dietary_options         text,   -- modifiers / options
    tag_source              text,   -- "restaurant_disclosed" / "goldpan_inferred" / "none"

    -- Restaurant context (denormalized from restaurant record)
    hours                   text,
    menu_link               text,
    restaurant_address      text,
    restaurant_website      text,

    -- Allergen
    allergen_summary        text,   -- legacy summary field (from DLD "Allergen_summary")

    -- Calorie (Enhanced field v1.4.0)
    calorie_value           text,
    calorie_source_text     text,

    -- Operational
    verification_status     text,   -- was "Recanvass_Status" in older DLD rows
    status                  text    NOT NULL DEFAULT 'Active'
                            CHECK (status IN ('Active','Inactive')),
    version                 text,
    last_updated            text,   -- stored as text, format "July 5, 2026"
    is_active               boolean NOT NULL DEFAULT true,

    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE evidence.dishes IS
    'One row per dish. Maps to Goldpan Dish Level Data (DLD) tab. External IDs preserved for pipeline compatibility.';
COMMENT ON COLUMN evidence.dishes.dietary_tags IS
    'Restaurant-disclosed dietary tags only. Tag_Source must be set. GoldPan-derived conclusions live in knowledge.derived_filters.';


-- ── evidence.ingredients ─────────────────────────────────────────────────────
-- One row per ingredient per dish. Maps to Ingredient Details tab.
-- Allergen_Flags are Evidence System records — canvasser-observed, sourced.

CREATE TABLE evidence.ingredients (
    ingredient_id           uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id             text,                       -- e.g. "I001" (if assigned)
    dish_id                 uuid    NOT NULL
                                REFERENCES evidence.dishes(dish_id)
                                ON DELETE RESTRICT,
    dish_external_id        text    NOT NULL,           -- denormalized
    restaurant_id           uuid    NOT NULL
                                REFERENCES evidence.restaurants(restaurant_id)
                                ON DELETE RESTRICT,
    restaurant_external_id  text    NOT NULL,           -- denormalized

    -- Ingredient data
    ingredient_name         text    NOT NULL,           -- "Ingredient" column in Sheets
    cut_type                text,
    preparation             text,
    ingredient_type         text,
    component_role          text,

    -- Allergen evidence (Evidence System — GP-RULE-014)
    allergen_flags          text,   -- canonical comma-separated slugs or "none"/"unknown"

    -- Provenance (GP-RULE-011)
    ingredient_source       text,   -- canonical provenance value from GP-RULE-010

    -- Operational
    status                  text    NOT NULL DEFAULT 'Active'
                            CHECK (status IN ('Active','Inactive')),
    version                 text,
    notes                   text,
    is_active               boolean NOT NULL DEFAULT true,

    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE evidence.ingredients IS
    'One row per ingredient per dish. Maps to Ingredient Details tab. allergen_flags are Evidence System records — not Knowledge outputs.';
COMMENT ON COLUMN evidence.ingredients.allergen_flags IS
    'Canonical allergen slugs per GP-RULE-014 (comma-separated) or "none"/"unknown". Set by canvasser with source reference. Never set by the pipeline.';
COMMENT ON COLUMN evidence.ingredients.ingredient_source IS
    'Provenance value per GP-RULE-010 authority hierarchy: menu/website/allergen_guide/nutrition_document/restaurant_confirmation/ordering_platform/restaurant_qa/pdf';


-- ── evidence.allergen_disclosures ─────────────────────────────────────────────
-- Restaurant allergen disclosures — what the restaurant explicitly stated
-- about allergen presence, absence, or cross-contact risk.
-- Governed by GP-RULE-014 (Allergen Evidence Rule).

CREATE TABLE evidence.allergen_disclosures (
    disclosure_id           uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id           uuid    NOT NULL
                                REFERENCES evidence.restaurants(restaurant_id)
                                ON DELETE RESTRICT,
    restaurant_external_id  text    NOT NULL,
    dish_id                 uuid    REFERENCES evidence.dishes(dish_id)
                                ON DELETE RESTRICT,     -- NULL when scope = restaurant
    dish_external_id        text,                       -- NULL when scope = restaurant

    -- Disclosure content
    allergen                text    NOT NULL,   -- canonical slug per GP-RULE-014
    disclosure_status       text    NOT NULL
                            CHECK (disclosure_status IN ('contains','may_contain','free_from')),
    scope                   text    NOT NULL
                            CHECK (scope IN ('dish','restaurant')),

    -- Provenance (GP-RULE-011) — all four fields required for engine use
    source_type             text    NOT NULL,   -- canonical provenance value
    source_reference        text,               -- specific URL or document description
    source_date             date,
    confidence              text
                            CHECK (confidence IN ('verified','declared', NULL)),

    notes                   text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),

    -- Scope constraint: dish-scoped rows must have dish_id
    CONSTRAINT scope_dish_requires_dish_id
        CHECK (scope != 'dish' OR dish_id IS NOT NULL),
    -- Scope constraint: restaurant-scoped rows must have NULL dish_id
    CONSTRAINT scope_restaurant_requires_no_dish_id
        CHECK (scope != 'restaurant' OR dish_id IS NULL)
);

COMMENT ON TABLE evidence.allergen_disclosures IS
    'Restaurant allergen disclosures — what the restaurant stated. Governed by GP-RULE-014. One-way boundary: Knowledge conclusions never flow back here.';


-- ── evidence.restaurant_claims ───────────────────────────────────────────────
-- Restaurant-level dietary and operational claims from intake packets.
-- Distinct from allergen_disclosures (which are allergen-specific).

CREATE TABLE evidence.restaurant_claims (
    claim_id                uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id           uuid    NOT NULL
                                REFERENCES evidence.restaurants(restaurant_id)
                                ON DELETE RESTRICT,
    restaurant_external_id  text    NOT NULL,
    claim_type              text,   -- e.g. "dietary_certification", "preparation_practice"
    claim_text              text    NOT NULL,
    source_type             text,
    source_reference        text,
    source_date             date,
    notes                   text,
    created_at              timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE evidence.restaurant_claims IS
    'Restaurant-level claims from intake packets (restaurant_claims[] field). Distinct from allergen_disclosures.';


-- ── evidence.intake_sessions ─────────────────────────────────────────────────
-- Log of every intake session (AI-assisted or human).
-- Used by AI Usage OS for cost attribution and quality tracking.

CREATE TABLE evidence.intake_sessions (
    session_id              uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_id           uuid    REFERENCES evidence.restaurants(restaurant_id),
    restaurant_external_id  text,
    session_type            text    NOT NULL DEFAULT 'ai_assisted'
                            CHECK (session_type IN ('ai_assisted','human')),
    model_used              text,   -- e.g. "claude-sonnet-4-6"
    intake_agent_version    text,   -- e.g. "1.4.0"
    dishes_captured         int,
    ingredients_captured    int,
    token_input             int,
    token_output            int,
    estimated_cost_usd      numeric(10,6),
    quality_flags           jsonb,  -- any review flags from the session
    packet_path             text,   -- path to the staging JSON file
    status                  text    DEFAULT 'completed',
    actor_id                uuid,   -- which canvasser triggered this
    session_date            date    NOT NULL DEFAULT current_date,
    created_at              timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE evidence.intake_sessions IS
    'Intake session log. Used by AI Usage OS for cost attribution and quality tracking.';


-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX idx_restaurants_external_id     ON evidence.restaurants(external_id);
CREATE INDEX idx_restaurants_lifecycle       ON evidence.restaurants(lifecycle_status);
CREATE INDEX idx_restaurants_recanvass       ON evidence.restaurants(recanvass_status);
CREATE INDEX idx_lifecycle_events_restaurant ON evidence.lifecycle_events(restaurant_id);
CREATE INDEX idx_lifecycle_events_created    ON evidence.lifecycle_events(created_at);
CREATE INDEX idx_menu_sources_restaurant     ON evidence.menu_sources(restaurant_id);
CREATE INDEX idx_dishes_external_id          ON evidence.dishes(external_id);
CREATE INDEX idx_dishes_restaurant           ON evidence.dishes(restaurant_id);
CREATE INDEX idx_dishes_active               ON evidence.dishes(is_active);
CREATE INDEX idx_ingredients_dish            ON evidence.ingredients(dish_id);
CREATE INDEX idx_ingredients_restaurant      ON evidence.ingredients(restaurant_id);
CREATE INDEX idx_allergen_disc_restaurant    ON evidence.allergen_disclosures(restaurant_id);
CREATE INDEX idx_allergen_disc_dish          ON evidence.allergen_disclosures(dish_id);
