-- ============================================================
-- 020_intake_evidence_schema_extension.sql
-- Intake OS — evidence schema extension (Track A, additive only).
--
-- Adds faithful persistence destinations for five packet fields that
-- currently have no evidence.* destination, per the gap map recorded in
-- docs/decisions/DEC000003_INTAKE_EVIDENCE_SCHEMA_GAP_MAP.md (§8, §13).
--
-- Scope of this migration (DEC000003 items 1-4 and 7 only):
--   1. evidence.restaurant_claims.scope           (new column)
--   2. evidence.dish_verbatim_components           (new table)
--   3. evidence.restaurant_source_inventory        (new table)
--   4. evidence.dishes calorie columns              (new nullable columns)
--   5. evidence.dish_modifiers                      (new table)
--
-- Explicitly OUT of scope (Track B — see DEC000003 §9, §9a, §9b, §10, §11):
--   allergen-disclosure classification (disclosure_status / scope capture),
--   the Evidence Disposition mechanism, the GP422 approval precondition,
--   the approved-packet reopen workflow, Task #46, Task #47.
--
-- All five changes are additive: new nullable columns and new tables only.
-- No existing column is altered or dropped, no existing row is touched, and
-- no existing read path requires a code change for this migration to be
-- safe to apply. Per DEC000003 §13 Decision 6, all calorie-related columns
-- on evidence.dishes remain nullable with no cross-column requirement — a
-- dish with no approved calorie evidence must ingest with all seven
-- calorie fields null.
--
-- This migration must not be executed until reviewed and explicitly
-- authorized. Writing this file does not constitute running it.
-- ============================================================

-- ── 1. evidence.restaurant_claims.scope ─────────────────────────────────────
-- Packet field: restaurant.restaurant_claims[].scope. Store the raw packet
-- value verbatim — do NOT collapse it into the existing claim_type column
-- (claim_type has no packet source of its own; see DEC000003 §2 item 5).

ALTER TABLE evidence.restaurant_claims
    ADD COLUMN IF NOT EXISTS scope text
        CHECK (scope IN (
            'dish_level','menu_section_level','restaurant_level',
            'ownership','sourcing','health_positioning','operational'
        ));

COMMENT ON COLUMN evidence.restaurant_claims.scope IS
    'Raw claim-applicability scope from the intake packet (restaurant_claims[].scope). Verbatim packet value — never derived from or collapsed into claim_type. Nullable: evidence.restaurant_claims was empty prior to this migration, and pre-existing rows (if any) have no source value for this field.';

CREATE INDEX IF NOT EXISTS idx_restaurant_claims_scope
    ON evidence.restaurant_claims(scope);


-- ── 2. evidence.dish_verbatim_components ────────────────────────────────────
-- Packet field: dishes[].verbatim_components[]. Raw menu/source text for a
-- dish component the intake agent could not confidently resolve into a
-- structured evidence.ingredients row. Purely additive — this data was
-- never persisted anywhere before this migration.

CREATE TABLE IF NOT EXISTS evidence.dish_verbatim_components (
    verbatim_component_id   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

    dish_id                  uuid        NOT NULL
                                REFERENCES evidence.dishes(dish_id)
                                ON DELETE RESTRICT,
    dish_external_id         text        NOT NULL,           -- denormalized for pipeline convenience
    restaurant_id            uuid        NOT NULL
                                REFERENCES evidence.restaurants(restaurant_id)
                                ON DELETE RESTRICT,
    restaurant_external_id   text        NOT NULL,           -- denormalized for pipeline convenience

    verbatim_text            text        NOT NULL,
    ingredient_source         text,       -- provenance value per GP-RULE-010, if captured

    resolution_status         text        NOT NULL DEFAULT 'unresolved'
                            CHECK (resolution_status IN ('unresolved', 'resolved')),

    created_at                timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE evidence.dish_verbatim_components IS
    'Raw dish-component text the intake agent could not resolve into a structured evidence.ingredients row (dishes[].verbatim_components[]). Preserves canvassed evidence a human reviewer already approved rather than dropping it silently. resolution_status is observed as always "unresolved" today — nothing downstream currently resolves these rows; the column exists so a future Evidence System workflow can do so without a schema change.';
COMMENT ON COLUMN evidence.dish_verbatim_components.ingredient_source IS
    'Provenance value per GP-RULE-010, if the packet captured one for this fragment. Nullable — not every verbatim component has an independently sourced provenance value.';

CREATE INDEX IF NOT EXISTS idx_dish_verbatim_components_dish
    ON evidence.dish_verbatim_components(dish_id);
CREATE INDEX IF NOT EXISTS idx_dish_verbatim_components_restaurant
    ON evidence.dish_verbatim_components(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_dish_verbatim_components_status
    ON evidence.dish_verbatim_components(resolution_status);


-- ── 3. evidence.restaurant_source_inventory ─────────────────────────────────
-- Packet field: restaurant.source_inventory[]. The list of source URLs the
-- intake agent actually drew from during one canvassing run.
--
-- Deliberately a separate table from evidence.menu_sources, NOT an extension
-- of it. evidence.menu_sources carries a UNIQUE(restaurant_id) constraint
-- (migration 008) and models one row per restaurant with fixed single-valued
-- URL columns per source type. source_inventory[] is an unbounded list that
-- can contain multiple entries of the same source_type across canvassing
-- runs, and includes source_type values (restaurant_qa,
-- restaurant_confirmation) that have no corresponding column on
-- menu_sources at all. Migration 008's own comment anticipated this exact
-- conflict and calls for a new table rather than relaxing its constraint
-- without a data migration. This table leaves menu_sources and its
-- UNIQUE(restaurant_id) constraint completely untouched.

CREATE TABLE IF NOT EXISTS evidence.restaurant_source_inventory (
    source_inventory_id      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

    restaurant_id             uuid        NOT NULL
                                REFERENCES evidence.restaurants(restaurant_id)
                                ON DELETE RESTRICT,
    restaurant_external_id    text        NOT NULL,          -- denormalized for pipeline convenience

    source_type               text        NOT NULL
                            CHECK (source_type IN (
                                'menu','website','allergen_guide','nutrition_document',
                                'ordering_platform','restaurant_qa','restaurant_confirmation','pdf'
                            )),
    url                        text        NOT NULL,

    -- Which canvassing-run packet this inventory entry came from. Nullable
    -- (a row may exist without a known originating packet), but once set,
    -- ON DELETE RESTRICT: Intake Packets are permanent audit records that
    -- should be archived rather than hard-deleted, and canonical evidence
    -- must remain traceable to the packet that produced it. If a packet is
    -- referenced by evidence, an attempted hard deletion must fail rather
    -- than silently severing lineage — same provenance principle as every
    -- other FK in this migration.
    source_packet_id          uuid        REFERENCES operations.intake_packets(packet_id)
                                ON DELETE RESTRICT,

    captured_at                timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE evidence.restaurant_source_inventory IS
    'Per-canvassing-run source provenance record (restaurant.source_inventory[]). Unbounded list, deliberately separate from evidence.menu_sources (see migration 008 UNIQUE(restaurant_id) note) — multiple rows per restaurant and per source_type are expected across canvassing runs.';
COMMENT ON COLUMN evidence.restaurant_source_inventory.source_packet_id IS
    'Originating operations.intake_packets row, if known (nullable). ON DELETE RESTRICT once set — Intake Packets are permanent audit records and canonical evidence must remain traceable to the packet that produced it; hard-deleting a referenced packet must fail, not silently sever lineage.';

CREATE INDEX IF NOT EXISTS idx_restaurant_source_inventory_restaurant
    ON evidence.restaurant_source_inventory(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_restaurant_source_inventory_packet
    ON evidence.restaurant_source_inventory(source_packet_id);
CREATE INDEX IF NOT EXISTS idx_restaurant_source_inventory_type
    ON evidence.restaurant_source_inventory(source_type);


-- ── 4. evidence.dishes — calorie sub-fields ─────────────────────────────────
-- Packet field: dishes[].restaurant_calorie_content {value, unit,
-- source_text, source_url, ingredient_source, notes}. evidence.dishes
-- already has calorie_value and calorie_source_text (Enhanced field
-- v1.4.0); this adds the remaining four named sub-fields plus a defensive
-- raw-fragment column.
--
-- Per DEC000003 §13 Decision 6: calories are optional evidence, not a
-- required property of every dish. All seven calorie-related columns
-- (calorie_value, calorie_source_text, calorie_unit, calorie_source_url,
-- calorie_ingredient_source, calorie_notes, calorie_raw_fragment) are
-- nullable with no CHECK or NOT NULL constraint tying them to each other or
-- to any other dish column. A dish with no approved restaurant_calorie_content
-- object in the packet must ingest successfully with all seven left null;
-- absence must never block packet approval or commit_ingest, and
-- commit_ingest must never infer, estimate, or fabricate a calorie value
-- through this path. Restaurant-published calorie data captured here is a
-- distinct record from any future GoldPan-estimated calorie model — the two
-- must never be conflated in this or any downstream table.

ALTER TABLE evidence.dishes
    ADD COLUMN IF NOT EXISTS calorie_unit              text,
    ADD COLUMN IF NOT EXISTS calorie_source_url         text,
    ADD COLUMN IF NOT EXISTS calorie_ingredient_source  text,
    ADD COLUMN IF NOT EXISTS calorie_notes              text,
    ADD COLUMN IF NOT EXISTS calorie_raw_fragment       jsonb;

COMMENT ON COLUMN evidence.dishes.calorie_unit IS
    'Unit for calorie_value (e.g. "kcal"), from dishes[].restaurant_calorie_content.unit. Nullable — absent when no calorie object exists for the dish.';
COMMENT ON COLUMN evidence.dishes.calorie_source_url IS
    'Source URL for the calorie disclosure, from dishes[].restaurant_calorie_content.source_url. Nullable.';
COMMENT ON COLUMN evidence.dishes.calorie_ingredient_source IS
    'Provenance value (GP-RULE-010) for the calorie disclosure, from dishes[].restaurant_calorie_content.ingredient_source. Independent of the dish''s other ingredient provenance. Nullable.';
COMMENT ON COLUMN evidence.dishes.calorie_notes IS
    'Free-text notes on the calorie disclosure, from dishes[].restaurant_calorie_content.notes. Nullable.';
COMMENT ON COLUMN evidence.dishes.calorie_raw_fragment IS
    'Defensive fidelity copy of the exact approved restaurant_calorie_content object (DEC000003 §13 Decision 6). Not canonical — never overrides calorie_value/calorie_source_text/calorie_unit/calorie_source_url/calorie_ingredient_source/calorie_notes. Guards against future agent output containing additional keys, alternate key names, or nested structure the named columns do not represent. Populated by commit_ingest only when a calorie object exists in the approved packet; left null when no calorie object exists for the dish. The packet itself and intake_packet_revisions remain the authoritative historical source regardless of what is captured here.';


-- ── 5. evidence.dish_modifiers ───────────────────────────────────────────────
-- Packet field: dishes[].modifiers[]. Real packets use inconsistent keys for
-- this field across canvassing runs (observed variants: {name, upcharge,
-- description} and {modifier_name, modifier_description, options[]}).
-- raw_packet_fragment is NOT NULL and stores the modifier object verbatim so
-- no data is lost regardless of which key variant a given packet used —
-- this replaces the lossy/buggy evidence.dishes.dietary_options flattening
-- (_modifiers_to_str() in ingest_packet.py silently produces blank output
-- for the {name, upcharge} variant; see DEC000003 §7). dietary_options is
-- left in place unmodified as a derived/rendered summary for backward read
-- compatibility.

CREATE TABLE IF NOT EXISTS evidence.dish_modifiers (
    modifier_id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

    dish_id                    uuid        NOT NULL
                                REFERENCES evidence.dishes(dish_id)
                                ON DELETE RESTRICT,
    dish_external_id           text        NOT NULL,          -- denormalized for pipeline convenience
    restaurant_id               uuid        NOT NULL
                                REFERENCES evidence.restaurants(restaurant_id)
                                ON DELETE RESTRICT,
    restaurant_external_id      text        NOT NULL,          -- denormalized for pipeline convenience

    -- Best-effort structured fields — populated when the packet's key
    -- variant maps cleanly; may be null/blank if it doesn't. Not the
    -- source of truth (see raw_packet_fragment below).
    modifier_name                text,
    modifier_description         text,
    upcharge                      text,       -- stored as text to preserve "$1.50" / "+$1.50" formatting
    options                        jsonb,      -- structured options[] sub-list, when present

    -- Verbatim copy of the modifier object exactly as it appeared in the
    -- approved packet, regardless of key-naming variant. Canonical fidelity
    -- record — never optional, never derived.
    raw_packet_fragment            jsonb       NOT NULL,

    created_at                      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE evidence.dish_modifiers IS
    'Dish customization options (dishes[].modifiers[]) — extra toppings, size upgrades, swaps, with price deltas. raw_packet_fragment is the canonical fidelity record; modifier_name/modifier_description/upcharge/options are a best-effort structured projection that may be incomplete for either observed packet key-naming variant.';
COMMENT ON COLUMN evidence.dish_modifiers.raw_packet_fragment IS
    'Verbatim copy of the modifier object as it appeared in the approved packet (either the {name, upcharge, description} or {modifier_name, modifier_description, options[]} key variant, or any future variant). NOT NULL — this is the fidelity guarantee for the row; the structured columns are best-effort only.';

CREATE INDEX IF NOT EXISTS idx_dish_modifiers_dish
    ON evidence.dish_modifiers(dish_id);
CREATE INDEX IF NOT EXISTS idx_dish_modifiers_restaurant
    ON evidence.dish_modifiers(restaurant_id);


-- ── RLS: three new tables ────────────────────────────────────────────────────
-- Self-contained in this migration (per the 015_intake_packets.sql
-- convention for newer tables), rather than appended to
-- 005_rls_policies.sql. Policy shape mirrors the closest existing
-- precedent for a sibling intake-evidence table —
-- evidence.restaurant_claims's restaurant_claims_select /
-- restaurant_claims_write pair in 005_rls_policies.sql: read open to all
-- authenticated evidence roles including governance_engine; write (INSERT/
-- UPDATE/DELETE) restricted to canvasser and above (governance_engine
-- excluded from write, consistent with restaurant_claims_write).
--
-- Interim mapping, not a permanent grant: these database-role policies are
-- the current row-level backstop only, matching the existing evidence.*
-- convention exactly and broadening nothing. Long-term authorization for
-- Intake OS is capability-based and governed at the API/RPC layer (per
-- DEC000001); these RLS policies must not be read as, or treated as,
-- permanent organizational ownership grants over these tables.

ALTER TABLE evidence.dish_verbatim_components    ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence.restaurant_source_inventory  ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence.dish_modifiers               ENABLE ROW LEVEL SECURITY;

CREATE POLICY "dish_verbatim_components_select" ON evidence.dish_verbatim_components FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));
CREATE POLICY "dish_verbatim_components_write" ON evidence.dish_verbatim_components FOR ALL
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin'))
    WITH CHECK (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin'));

CREATE POLICY "restaurant_source_inventory_select" ON evidence.restaurant_source_inventory FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));
CREATE POLICY "restaurant_source_inventory_write" ON evidence.restaurant_source_inventory FOR ALL
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin'))
    WITH CHECK (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin'));

CREATE POLICY "dish_modifiers_select" ON evidence.dish_modifiers FOR SELECT
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin','governance_engine'));
CREATE POLICY "dish_modifiers_write" ON evidence.dish_modifiers FOR ALL
    USING (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin'))
    WITH CHECK (operations.current_user_role() IN ('canvasser','reviewer','coordinator','admin'));

-- ============================================================
-- End of 020_intake_evidence_schema_extension.sql
-- NOT executed. NOT committed. Track B (allergen-disclosure classification,
-- Evidence Disposition, GP422 precondition, reopen workflow) is a separate,
-- later migration — see DEC000003 §9-§12.
-- ============================================================
