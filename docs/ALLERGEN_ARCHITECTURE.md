# GoldPan Structured Allergen Model — Architecture

**Status:** Approved — canonical architecture  
**Date:** 2026-06-30 (revised)  
**Scope:** Canonical allergen data model, evidence pathways, provenance, confidence, validation, and migration from `Allergen_summary`

---

## Problem Statement

The current allergen model has three defects:

**Defect 1 — Dish-level data is narrative, not structured.**  
`Allergen_summary` in Goldpan Dish Level Data is free text. It cannot be filtered, validated, compared, or used as engine input.

**Defect 2 — No provenance.**  
There is no `Allergen_Source` field. GoldPan cannot distinguish between a restaurant's official allergen guide claim and something a canvasser typed from memory.

**Defect 3 — Two fundamentally different concepts are conflated.**  
A restaurant saying "gluten-free" and GoldPan observing "no gluten ingredients in the disclosed list" are not the same thing. The first is a restaurant claim. The second is a GoldPan derived conclusion with lower authority and mandatory limitations. Treating them as the same "allergen status" violates the evidence architecture that governs dietary tags, provenance, and derived filters.

---

## Governing Principle

> **The absence of identified ingredients is not evidence of allergen absence.**

GoldPan can observe that a restaurant's disclosed primary ingredient list does not contain wheat. GoldPan cannot conclude from that observation that the dish is wheat-free. Cross-contact, compound ingredient sub-components, processing aids, preparation variations, and undisclosed ingredients all exist outside what a primary ingredient list captures. An absence in the list is an absence in the evidence — not an absence in the dish.

Everything in this architecture flows from that principle. It is why restaurant disclosures and ingredient analysis are separate systems. It is why "No Wheat Ingredients Identified" carries mandatory limitations. It is why `free_from` requires a restaurant source and cannot be derived from ingredient analysis. And it is why GoldPan will never present an ingredient-analysis conclusion as the equivalent of a restaurant allergen claim.

---

## The Two-System Architecture

The structured allergen model is not one system — it is two independent systems with different evidence sources, different output fields, different confidence levels, and different consumer-facing language.

```
SYSTEM A                              SYSTEM B
Restaurant Allergen Disclosures       GoldPan Ingredient Analysis
───────────────────────────────       ────────────────────────────────────────────
Source: Allergen_Disclosures tab      Source: Allergen_Flags on ingredient rows
        (restaurant-level claims)             (GoldPan canvasser analysis)

Evidence: what the restaurant says    Evidence: what the disclosed ingredient
          about allergen status                list contains or omits

Status vocab:                         Conclusion type:
  contains                              "No [X] Ingredients Identified"
  may_contain                           (same engine as No Beef / No Pork)
  free_from  [internal]                 (not_applicable when allergen IS found)

Consumer label:                       Consumer label:
  "Restaurant disclosed gluten-free"    "No gluten ingredients identified
  "Contains: wheat, dairy"              from disclosed ingredients."
  "Cross-contact risk: peanuts"

Confidence: declared / verified       Confidence: inferred (ceiling)

Limitations: restaurant claims        Limitations: MANDATORY — does not
  may change; contact restaurant         confirm cross-contact, hidden
  to confirm                             ingredients, preparation aids,
                                         or undisclosed components

Output: allergen_disclosures          Output: derived_filters
        (separate field in dishes.json)         (same field as No Beef / No Pork)
```

These two systems must never be merged into a single "allergen status" field. They answer different questions with different evidence and different authority.

---

## Canonical Allergen Vocabulary

### The Nine FDA Allergens

GoldPan tracks the nine FDA-mandated major food allergens. Each has a canonical machine-readable slug:

| Canonical slug | Human label | Notes |
|---|---|---|
| `milk` | Milk / Dairy | `dairy` accepted as alias |
| `eggs` | Eggs | `egg` alias → `eggs` |
| `fish` | Fish | |
| `shellfish` | Shellfish | |
| `tree_nuts` | Tree Nuts | `tree nuts` (space) accepted |
| `peanuts` | Peanuts | `peanut` alias → `peanuts` |
| `wheat` | Wheat | `gluten` alias → `wheat` (see note) |
| `soy` | Soy / Soybeans | `soybeans`, `soybean` → `soy` |
| `sesame` | Sesame | Added to FDA list 2023 |

**On `gluten` vs `wheat`:** The FDA major allergen is wheat. Gluten is the protein. A non-wheat gluten source (rye, barley) is not a wheat allergen. If a source says "gluten-free" the canvasser must confirm wheat is the specific allergen intended before applying the alias. Already documented in `schema.py`.

**Special flags** (non-allergen, used for evidence gaps — existing):

| Flag | Meaning |
|---|---|
| `unknown` | Allergen status not determinable at canvass time |
| `none` | No allergens flagged |

These remain in `CANONICAL_ALLERGEN_FLAGS` and continue to be valid on `Allergen_Flags` ingredient rows.

---

## System A — Restaurant Allergen Disclosures

### Purpose

Restaurant Disclosures captures what restaurants explicitly communicate about allergen status — on their menu, on their website, in their allergen guide, or via direct confirmation. This is a restaurant claim. GoldPan records it faithfully and attributes it to the restaurant.

Restaurant Disclosures does **not** capture GoldPan's conclusions from analyzing ingredients. It does not contain `not_identified`. A restaurant not having an allergen guide is not a restaurant claim — it is an absence of evidence.

### Data Layer — `Allergen_Disclosures` Tab (new)

**Location:** New tab in the Google Sheet  
**Granularity:** One row per dish-allergen pair (or restaurant-allergen pair for kitchen-wide claims)

**Schema:**

| Column | Type | Description |
|---|---|---|
| `Restaurant_ID` | string | e.g., R001 |
| `Restaurant_Name` | string | |
| `Dish_ID` | string | e.g., D045. Blank for `scope = restaurant` rows |
| `Dish_Name` | string | Blank for `scope = restaurant` rows |
| `Allergen` | enum | Canonical slug from CANONICAL_ALLERGEN_FLAGS |
| `Disclosure_Status` | enum | `contains`, `may_contain`, `free_from` |
| `Source_Type` | enum | Canonical provenance value from GP-RULE-010 |
| `Source_Reference` | string | URL, document name, or exchange description |
| `Source_Date` | date | YYYY-MM-DD — date evidence was obtained |
| `Scope` | enum | `dish`, `restaurant` |
| `Notes` | string | Optional clarifying notes |

### `Disclosure_Status` Values

These are the only three things a restaurant can disclose about an allergen:

| Value | Meaning | Evidence required |
|---|---|---|
| `contains` | Restaurant or allergen documentation confirms this allergen is present | Any tier source explicitly stating the allergen is present |
| `may_contain` | Restaurant disclosed cross-contact or shared-equipment risk | Restaurant explicitly disclosed cross-contact — not inferred |
| `free_from` | Restaurant explicitly stated this dish or menu is free from this allergen | See source tier requirements below |

**`free_from` source tier requirements:**

| Source | Tier | `Disclosure_Status` | Confidence |
|---|---|---|---|
| Official allergen guide or nutrition document | Tier 1 | `free_from` | `verified` |
| Restaurant written confirmation | Tier 1 | `free_from` | `verified` |
| Menu or website explicit statement | Tier 2 | `free_from` | `declared` |

A restaurant saying "gluten-free" on a menu produces `free_from` with confidence `declared`. An allergen guide PDF explicitly listing the dish as containing no wheat produces `free_from` with confidence `verified`. Both are valid disclosures — they differ in confidence, not in kind. Both belong in Restaurant Disclosures.

A canvasser may **not** create a `free_from` row based on the absence of an allergen from the ingredient list. That belongs in GoldPan Ingredient Analysis.

**`free_from` is an internal canonical status, not consumer-facing language.** Consumer output should reflect the restaurant's actual disclosure wherever possible. Examples:

| Internal status | Consumer-facing label |
|---|---|
| `free_from` (verified, allergen_guide) | "Restaurant allergen guide: gluten-free" |
| `free_from` (declared, menu) | "Restaurant disclosed: gluten-free" |
| `free_from` (declared, website) | "Restaurant disclosed: dairy-free" |
| `contains` | "Contains: wheat, dairy" |
| `may_contain` | "Cross-contact risk: peanuts (restaurant-disclosed)" |

The `free_from` enum value is used internally for validation, engine logic, and conflict detection. The presentation layer translates it into language that reflects the source and confidence, not the enum name.

### `Scope` Values

| Value | Meaning |
|---|---|
| `dish` | Evidence applies specifically to this dish. `Dish_ID` required. |
| `restaurant` | Restaurant-wide claim (e.g., "our kitchen never uses peanuts"). Applies to all dishes at this restaurant. `Dish_ID` is blank. |

Restaurant-scoped `may_contain` claims escalate every dish at that restaurant unless overridden by a dish-scoped `free_from` with a Tier 1 source.

### Confidence

| Confidence | Meaning |
|---|---|
| `verified` | Tier 1 source (allergen_guide, nutrition_document, restaurant_confirmation) |
| `declared` | Tier 2 source (menu, website) — restaurant stated it publicly but not in formal documentation |

No other confidence levels exist in Restaurant Disclosures. `inferred` is a GoldPan Ingredient Analysis concept.

### Consumer Output Label Examples

```
"Restaurant disclosed: gluten-free"               (free_from, verified, allergen_guide)
"Restaurant menu states: gluten-free"             (free_from, declared, menu)
"Contains: wheat, dairy, soy"                     (contains, declared, menu)
"Cross-contact risk: peanuts (restaurant-disclosed)" (may_contain, declared, website)
```

### Output Location in `dishes.json`

New field `allergen_disclosures` — an array of disclosure objects, one per allergen the restaurant has disclosed:

```json
"allergen_disclosures": [
  {
    "allergen": "wheat",
    "status": "free_from",
    "confidence": "verified",
    "source_type": "allergen_guide",
    "source_reference": "https://example.com/allergen-guide.pdf",
    "source_date": "2026-06-01",
    "scope": "dish",
    "rule_ids": ["GP-RULE-014", "GP-RULE-015", "GP-RULE-016"]
  }
]
```

Dishes with no allergen disclosures have `allergen_disclosures: []`. This is not the same as no allergens — it means no allergen evidence has been obtained from the restaurant.

---

## GoldPan Ingredient Analysis — GoldPan Ingredient Analysis

### Purpose

GoldPan Ingredient Analysis captures what GoldPan concludes from analyzing a verified primary ingredient list. These are derived filter conclusions — same engine, same dependency model, same explanation schema as No Beef Identified and No Pork Identified.

"No gluten ingredients identified" means: GoldPan reviewed the disclosed primary ingredient list and did not find wheat or wheat-derived ingredients. It does not mean the dish is gluten-free. It does not address cross-contact, compound ingredient sub-components, processing aids, or undisclosed components.

GoldPan Ingredient Analysis is structurally identical to the existing derived filter architecture. No new engine logic is required. A new family of filters is registered.

### Filter Family — "No [X] Ingredients Identified"

Each FDA allergen gets its own filter in `derived/registry.py`:

| Filter name | Allergen | Dependency type |
|---|---|---|
| No Wheat Ingredients Identified | wheat | macro_dependent |
| No Milk Ingredients Identified | milk / dairy | macro_dependent |
| No Egg Ingredients Identified | eggs | macro_dependent |
| No Soy Ingredients Identified | soy | macro_dependent |
| No Peanut Ingredients Identified | peanuts | macro_dependent |
| No Tree Nut Ingredients Identified | tree_nuts | macro_dependent |
| No Fish Ingredients Identified | fish | macro_dependent |
| No Shellfish Ingredients Identified | shellfish | macro_dependent |
| No Sesame Ingredients Identified | sesame | macro_dependent |

These are registered exactly as No Beef Identified and No Pork Identified are registered. The engine handles them identically.

### Engine Behavior

The compute function for each allergen-elimination filter scans `Allergen_Flags` across all ingredient rows for the dish:

- If any ingredient row carries the target allergen flag → conclusion: `not_applicable` (allergen IS identified; the "no X" filter does not apply)
- If no ingredient carries the target allergen flag AND the materiality test passes (GP-RULE-001) → conclusion: `"No [X] Ingredients Identified"` (computed)
- If dependency not met (no macro-eligible ingredients) → `unknown`

**Critical:** An ingredient row carrying `Allergen_Flags = "wheat"` is evidence of wheat presence from ingredient analysis — it is a GoldPan assessment, not a restaurant disclosure. It produces a GoldPan Ingredient Analysis `not_applicable` result. It does not populate Restaurant Disclosures. The canvasser identified wheat in an ingredient; the restaurant did not say "this dish contains wheat." These are different claims.

### Dependency Type

All allergen-elimination filters are `macro_dependent`. The existing engine dependency check applies without modification. A dish with no macro-eligible ingredient rows returns `unknown` for all allergen-elimination filters.

### Mandatory Limitations Language

Every GoldPan Ingredient Analysis conclusion — for every allergen, on every dish — must carry this limitations language (per GP-RULE-016):

> "No [X] Ingredients Identified" means the verified disclosed primary ingredient list for this dish does not contain [X] or [X]-derived ingredients as explicitly listed. This is **not** a claim that the dish is [X]-free. It does not address: undisclosed compound ingredient components, micro ingredients, processing aids, cross-contact risk, shared equipment, preparation variations, or ingredients that may have been added or changed since last canvass. Diners with [X] allergies or intolerances must contact the restaurant directly before dining.

This language is governed by GP-RULE-016 and may not be omitted, shortened, or softened by implementation.

### Consumer Output Label Examples

```
"No gluten ingredients identified from disclosed ingredients."
"No dairy ingredients identified from disclosed ingredients."
"No shellfish ingredients identified from disclosed ingredients."
```

Each must link to or display the full limitations language.

### Output Location in `dishes.json`

These conclusions flow into the existing `derived_filters` field — the same place No Beef Identified and No Pork Identified already appear. No new output section is needed for GoldPan Ingredient Analysis.

---

## What Belongs Where

| Concept | System | Reason |
|---|---|---|
| Restaurant says "gluten-free" on menu | A | Restaurant claim — Tier 2 |
| Allergen guide confirms dish is wheat-free | A | Restaurant claim — Tier 1 |
| Restaurant kitchen uses shared peanut equipment | A | Cross-contact disclosure — restaurant claim |
| Allergen guide says dish contains milk and soy | A | Restaurant claim — contains |
| GoldPan found no wheat flag in any ingredient row | B | Derived from ingredient analysis |
| GoldPan found a "milk" flag on an ingredient row | B | not_applicable for "No Milk Ingredients Identified" |
| Dish has no macro-eligible ingredient rows | B | unknown for all allergen-elimination filters |
| Canvasser wrote "gluten-free" in Allergen_summary | Neither — migrate | No provenance; must be re-classified |

---

## Evidence Lifecycle Invariant

The Evidence System and Knowledge System have different lifecycles. This invariant governs both allergen systems and must be preserved as GoldPan grows.

**Evidence is durable.** The `Allergen_Disclosures` tab is a historical record of what restaurants disclosed, when, and from what source. Once a disclosure is recorded with full provenance, it is preserved. A future engine improvement, rule revision, or schema migration does not invalidate the disclosure — it is what the restaurant said. Evidence does not expire when conclusions are regenerated.

**Knowledge is reproducible.** Every derived conclusion in the Knowledge System — including all nine allergen-elimination filters in `derived_filters` and the `allergen_disclosures` field in `dishes.json` — must be regenerable from the Evidence System alone. If every Knowledge System output were deleted today and the pipeline were re-run, the result should be identical or better. If anything would be lost, something has drifted.

This means two things for the allergen model:

1. The `Allergen_Disclosures` tab must never contain a field that was computed by GoldPan's rules. Conclusions do not belong in Evidence. If a field looks like a conclusion (a confidence level, an eligibility flag, an engine-assigned tier), it must be moved to the Knowledge System output or removed.

2. The `derived_filters` and `allergen_disclosures` Knowledge System outputs must never become the source of truth for anything. The Evidence System feeds the engine; the engine produces Knowledge outputs; Knowledge outputs are consumed by the product. Nothing flows backward.

**The Allergen_Flags invariant — engine reads, never writes.**

`Allergen_Flags` on ingredient rows in the Ingredient Details tab are Evidence. A canvasser observed that a given ingredient is associated with a particular allergen and recorded that observation. This is legitimate evidence — conservative, attributable, and tied to the ingredient's acquisition source.

The following rules are canonical and non-negotiable:

- The engine **may read** `Allergen_Flags`.
- The engine **may never write** `Allergen_Flags`.
- The engine **may never backfill** `Allergen_Flags`.
- A **blank** `Allergen_Flags` value means absence of evidence. To the engine, blank is Unknown — not None, not safe, not "not applicable."
- **`none`** means a canvasser explicitly recorded that no allergen flags were associated with the ingredient. It is a canvasser observation, not an engine computation.
- The engine **must never convert blank to `none`**. If the engine derived "no allergen present" and wrote `none` into the flag, it would be storing a Knowledge System conclusion inside an Evidence System field. That is an architectural violation.

This is the specific failure mode to watch: canvasser judgment quietly becoming hidden computation. If the engine writes back to `Allergen_Flags`, canvasser observations and GoldPan computations become indistinguishable. The Evidence System boundary is broken and the lifecycle invariant is violated — the Knowledge System has become a source of truth for the Evidence System it is supposed to depend on.

The safeguard: `Allergen_Flags` are append-only from a canvassing operation and read-only from any pipeline script. Any script that writes to `Allergen_Flags` must be a canvassing tool, not a derived filter run.

---

## Corroboration Between Systems

When both systems produce compatible signals for the same dish and allergen, the GoldPan Ingredient Analysis conclusion becomes supporting evidence for the Restaurant Disclosures conclusion. The systems remain independent — this is not a confidence upgrade and it does not merge them.

| Restaurant Disclosures | GoldPan Ingredient Analysis | Interpretation |
|---|---|---|
| `free_from` (verified or declared) | computed ("No [X] Ingredients Identified") | Compatible — both point toward absence. GoldPan Ingredient Analysis corroborates the restaurant claim. |
| `contains` | not_applicable (allergen found in ingredients) | Compatible — both point toward presence. GoldPan Ingredient Analysis corroborates the restaurant claim. |
| `may_contain` | computed ("No [X] Ingredients Identified") | Compatible — no contradiction. The restaurant discloses cross-contact risk that ingredient analysis cannot detect; the ingredient list confirms the allergen is not a declared primary ingredient. |

**Consumer output when corroboration exists:**

> "Restaurant disclosed: gluten-free. GoldPan ingredient analysis: no gluten ingredients identified in disclosed ingredients."

The restaurant claim is the primary conclusion. The GoldPan Ingredient Analysis conclusion is surfaced as independent supporting evidence — explicitly labeled as GoldPan's analysis, not the restaurant's. This structure communicates corroboration without implying the two conclusions are the same type of evidence or that corroboration makes the conclusion more definitive.

**What corroboration does not change:**
- The mandatory limitations language on the GoldPan Ingredient Analysis conclusion remains in full
- The consumer-facing label for the GoldPan Ingredient Analysis conclusion does not change
- Confidence levels are not upgraded
- The Restaurant Disclosures conclusion and the GoldPan Ingredient Analysis conclusion remain in separate output fields

---

## Conflict Between Systems

When Restaurant Disclosures and GoldPan Ingredient Analysis produce contradictory signals for the same dish and allergen:

| Restaurant Disclosures | GoldPan Ingredient Analysis | Resolution |
|---|---|---|
| `free_from` (verified) | not_applicable (allergen found in ingredients) | **Conflict** — flag for human review; serve `unknown`. Per GP-RULE-012 Principle 5: allergen conflicts are never auto-resolved. |
| `free_from` (declared) | not_applicable | **Conflict** — flag for review; the declared menu claim and the ingredient analysis disagree. |
| `contains` | computed ("No X Identified") | **Conflict** — Restaurant Disclosures takes precedence for positive presence; also flag, because ingredient analysis missed it. |
| `may_contain` | computed ("No X Identified") | Not a conflict — Restaurant Disclosures adds cross-contact risk that ingredient analysis cannot detect. Both conclusions are surfaced. |
| `free_from` | unknown (dependency not met) | No conflict — Restaurant Disclosures fills evidence gap that GoldPan Ingredient Analysis cannot. Both surfaced. |

Conflicts between systems on the same allergen must always be logged and surfaced in `validate_database.py`.

---

## Provenance

Restaurant Disclosures provenance fields (on each `Allergen_Disclosures` row):

| Field | Description |
|---|---|
| `Source_Type` | Acquisition channel from GP-RULE-010 hierarchy |
| `Source_Reference` | Specific URL, document name, or exchange description |
| `Source_Date` | ISO 8601 date evidence was obtained |
| `Scope` | `dish` or `restaurant` |

GoldPan Ingredient Analysis provenance is carried by the derived filter explanation object, exactly as No Beef Identified carries it — citing ingredient rows, the Menu Source Registry `Last_Canvassed` date, and the macro-eligible source types used.

---

## New Rules Required

### GP-RULE-014 — Canonical Allergen Model

Defines the nine FDA allergen slugs, the `Disclosure_Status` vocabulary for Restaurant Disclosures (`contains`, `may_contain`, `free_from`), and establishes that Restaurant Disclosures and GoldPan Ingredient Analysis are architecturally separate evidence layers that may not be merged.

**Core prohibition:** `free_from` (restaurant disclosure) and "No [X] Ingredients Identified" (GoldPan derived conclusion) are not equivalent and must never be presented as equivalent in consumer output, schema design, or validation logic.

### GP-RULE-015 — Allergen Evidence Source Rule

Defines source tier requirements by status:
- `free_from` with confidence `verified`: Tier 1 sources only (allergen_guide, nutrition_document, restaurant_confirmation)
- `free_from` with confidence `declared`: Tier 2 sources (menu, website)
- `contains`, `may_contain`: any tier
- Allergen-elimination derived filters (GoldPan Ingredient Analysis): macro_dependent (same as No Beef / No Pork)
- No GoldPan ingredient analysis result may populate Restaurant Disclosures. The two evidence pathways are one-way into their respective systems.

### GP-RULE-016 — Allergen Safety Limitation Rule

Defines mandatory limitation language for both systems:

**Restaurant Disclosures limitation (all statuses):**
> Allergen information is disclosed by the restaurant. GoldPan records restaurant claims faithfully but cannot verify kitchen practices, preparation variations, supply chain changes, or menu updates made after the last canvass date. Diners with food allergies should contact the restaurant directly to confirm current allergen status before dining.

**GoldPan Ingredient Analysis limitation (all conclusions, non-waivable):**
> "No [X] Ingredients Identified" means the verified disclosed primary ingredient list for this dish does not contain [X] or [X]-derived ingredients as explicitly listed. This is not a claim that the dish is [X]-free. It does not address undisclosed compound ingredient components, micro ingredients, processing aids, cross-contact risk, shared equipment, preparation variations, or ingredients added or changed since last canvass. Diners with [X] allergies or intolerances must contact the restaurant directly before dining.

This language is non-waivable. It must appear in full in every consumer output surface that displays a GoldPan Ingredient Analysis conclusion.

---

## What Remains Implementation Detail

The following flow from the above rules and require no further architectural governance:

- Schema column names in `Allergen_Disclosures` tab
- `allergen_disclosures` field schema in `dishes.json`
- Compute function signatures in `derived/registry.py` for allergen-elimination filters
- Validation checks in `validate_database.py` for the new tab
- Conflict detection logic between Restaurant Disclosures and GoldPan Ingredient Analysis
- Migration script from `Allergen_summary` free text
- Specific format of evidence_summary strings in derived filter output

---

## Validation Rules

**`Allergen_Flags` column in Ingredient Details (existing, new checks):**
- All values must be in `CANONICAL_ALLERGEN_FLAGS`
- Multi-value: comma-separated, no spaces around commas
- `unknown` and `none` may not co-exist with other flags

**`Allergen_Disclosures` tab (new):**
- `Allergen` must be a canonical allergen slug (not `unknown` or `none` — those are engine outputs, not disclosure inputs)
- `Disclosure_Status` must be in `{contains, may_contain, free_from}`
- `free_from` rows with confidence `verified` must have `Source_Type` in Tier 1 set: `{allergen_guide, nutrition_document, restaurant_confirmation}`
- `Source_Type` must be a canonical provenance value from GP-RULE-010
- `Source_Date` must be present and ISO 8601
- `scope = dish` rows must have a valid `Dish_ID` present in Goldpan Dish Level Data
- `scope = restaurant` rows must have blank `Dish_ID`
- Duplicate rows (same Dish_ID + Allergen + Disclosure_Status) generate a warning

**Cross-system conflict detection (new, in validate step):**
- Flag any dish where Restaurant Disclosures has `free_from` for an allergen AND GoldPan Ingredient Analysis ingredient rows carry that allergen flag — this is a potential allergen data conflict requiring review

**`allergen_disclosures` in `dishes.json`:**
- Each entry must have `rule_ids` citing GP-RULE-014, GP-RULE-015, and GP-RULE-016
- `free_from` with confidence `verified` must cite a Tier 1 `source_type`

---

## Migration Strategy from `Allergen_summary`

### Phase 0 — Audit

Classify all current `Allergen_summary` values:
- **Structured presence:** "Contains: wheat, dairy" → candidate for Restaurant Disclosures `contains`
- **Structured absence (restaurant claim):** "Gluten-free", "Dairy-free" → candidate for Restaurant Disclosures `free_from` (needs source)
- **Narrative cross-contact:** "May contain traces of nuts" → candidate for Restaurant Disclosures `may_contain` (needs source)
- **Blank / Unknown:** No evidence — no migration possible
- **Pointer:** "See allergen guide" — canvasser must read the source and enter it properly

The audit output classifies each `Allergen_summary` value and identifies whether it is a Restaurant Disclosures candidate (restaurant claim) or has no structural home. No `Allergen_summary` value may be auto-migrated into Restaurant Disclosures without provenance — a source must be identified and recorded.

**No `Allergen_summary` values migrate into GoldPan Ingredient Analysis.** GoldPan Ingredient Analysis conclusions are computed from `Allergen_Flags` on ingredient rows. Free-text summaries are not evidence for derived filter computation.

### Phase 1 — Keep `Allergen_summary` as Legacy

`Allergen_summary` remains in the sheet and `allergens` (free-text) remains in `dishes.json`. No data is removed. Both new systems are built alongside the existing field.

### Phase 2 — Populate Restaurant Disclosures (Allergen_Disclosures tab)

For restaurants with documented allergen guides or nutrition documents (tracked in `Allergen_Nutrition_URL` in Menu Source Registry), canvassers populate the `Allergen_Disclosures` tab. This is human work — structured allergen data requires reading the source and recording each claim with provenance. Do not auto-generate from `Allergen_summary`.

### Phase 3 — Compute GoldPan Ingredient Analysis (Allergen-Elimination Derived Filters)

Register the allergen-elimination filter family in `derived/registry.py`. The engine already supports them — no engine changes required. On first run, dishes with sparse `Allergen_Flags` data will return `unknown`. This is correct and honest.

### Phase 4 — Deprecate `Allergen_summary`

Once both systems are populated for a restaurant and validated, the `Allergen_summary` field for that restaurant is marked deprecated and removed from `dishes.json`. Done restaurant-by-restaurant.

---

## Open Decisions

**Decision 1 — Allergen-elimination filter registration order**  
All nine allergens could be registered at once, or incrementally starting with the highest-prevalence allergens (wheat, milk, peanuts, tree nuts). Recommendation: register all nine at once — the engine cost is the same and partial registration creates inconsistent consumer output.

**Decision 2 — Handling restaurant-scoped `may_contain` propagation**  
If a restaurant discloses "prepared in a kitchen that processes peanuts" (scope=restaurant), should this automatically escalate every dish at that restaurant to `may_contain: peanuts` in Restaurant Disclosures output?  
Recommendation: Yes. A restaurant-scoped `may_contain` is a blanket cross-contact disclosure. Only a dish-scoped `free_from` with `verified` confidence from a Tier 1 source may override it for a specific dish.

**Decision 3 — GoldPan Ingredient Analysis output co-location with No Beef / No Pork**  
Allergen-elimination filters are derived filters. Should they appear in the same `derived_filters` output section as No Beef and No Pork, or in a separate `derived_allergen_filters` section?  
Recommendation: Same `derived_filters` section. These are structurally identical filter conclusions. Splitting by topic (allergen vs. ingredient) would require the consumer to query two sections for the same evidence type.

**Decision 4 — Consumer display when both systems have compatible data for the same allergen**  
Resolved by the Corroboration section. Restaurant Disclosures is the primary conclusion. GoldPan Ingredient Analysis is surfaced as independent supporting evidence, explicitly labeled. Both limitation sets remain in full. No confidence upgrade.

---

## Architecture Diagram

```
LAYER 1                               LAYER 2
Ingredient Details tab                Allergen_Disclosures tab
(Allergen_Flags per row)              (explicit restaurant claims)
        │                                       │
        ▼                                       ▼
INGREDIENT ANALYSIS                   RESTAURANT ALLERGEN DISCLOSURES
(GP-RULE-014, 015)                    (GP-RULE-014, 015)

Engine: existing derived filter       Engine: fetch + validate Source_Type
        engine, unchanged                      and Scope; no computation
                                               (these ARE the evidence)

Dependency: macro_dependent           Confidence: verified / declared
                                               (from source tier)

Conclusion vocab:                     Status vocab (internal):
  computed (no X identified)            contains
  not_applicable (X found)              may_contain
  unknown (dependency not met)          free_from

MANDATORY limitations on every        Appropriate limitations per status
conclusion (GP-RULE-016)              (GP-RULE-016)
        │                                       │
        ▼                                       ▼
derived_filters in dishes.json        allergen_disclosures in dishes.json
        │                                       │
        ▼                                       ▼
Consumer:                             Consumer (translated from internal status):
  "No gluten ingredients identified     "Restaurant disclosed: gluten-free"
   from disclosed ingredients."         "Restaurant allergen guide: dairy-free"
  [+ full mandatory limitations]        "Cross-contact risk: peanuts"

        └──────── Corroboration ────────────────┘
          When compatible, GoldPan Ingredient Analysis
          is surfaced as supporting evidence
          for the restaurant claim. Systems
          remain independent — no merge,
          no confidence upgrade.
```

---

## Summary: Rules vs Implementation Details

| Item | Category | Reason |
|---|---|---|
| Restaurant Disclosures and GoldPan Ingredient Analysis are separate evidence layers | **Rule (GP-RULE-014)** | Cross-system conflation is an evidence integrity violation, not an engineering choice |
| `free_from` and "No X Identified" are not equivalent | **Rule (GP-RULE-014)** | Safety boundary |
| Nine FDA allergen canonical slugs | **Rule (GP-RULE-014)** | Shared vocabulary across canvassers, engine, validators, output |
| Tier 1 required for `free_from` with `verified` confidence | **Rule (GP-RULE-015)** | Source authority decision; extends GP-RULE-010 |
| Allergen-elimination filters are `macro_dependent` | **Rule (GP-RULE-015)** | Engine dependency gate — policy, not implementation |
| No ingredient analysis result populates Restaurant Disclosures | **Rule (GP-RULE-015)** | Evidence boundary — one-way pathways |
| Mandatory GoldPan Ingredient Analysis limitation language | **Rule (GP-RULE-016)** | Non-waivable; governs all output surfaces |
| Restaurant Disclosures consumer limitation language | **Rule (GP-RULE-016)** | Non-waivable |
| `Allergen_Disclosures` tab column names | Implementation detail | |
| `allergen_disclosures` field schema in dishes.json | Implementation detail | |
| Compute function signatures in registry.py | Implementation detail | |
| Conflict detection validator logic | Implementation detail | |
| Migration script | Implementation detail | |
