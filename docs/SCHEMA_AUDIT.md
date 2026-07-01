# GoldPan Schema Audit

**Status:** Active — update when schema changes  
**Last audited:** 2026-06-28  
**Scope:** Ingredient Details, Goldpan Dish Level Data, staging JSON (ingredient and dish fields)

---

## Audit Method

Every field was inventoried for: canonical meaning, actual values found in staging files and the sheet, and whether the field is carrying multiple distinct concepts. Severity ratings:

- 🔴 **Critical** — causes downstream computation errors or silent data corruption
- 🟡 **Medium** — creates ambiguity, blocks future automation, or causes data loss
- 🟢 **Low** — cosmetic, inconsistent formatting, or technical debt without current impact

---

## Ingredient Details (14 columns in sheet)

### `Restaurant_ID`, `Restaurant_Name`, `Location`, `Dish_ID`, `Dish_Name`, `Ingredient`
**Status: ✅ Clean.** Required integrity fields. One meaning each. No violations found.

---

### `Ingredient_Source`
**Canonical meaning:** How GoldPan obtained the ingredient information.  
**Valid values:** `menu`, `pdf`, `website`, `restaurant_confirmation`, `Unknown`

**🔴 VIOLATION (fixed 2026-06-28):**  
`upsert_dishes.py` was reading `ing.get("source", "unknown")` from staging JSON and writing it to `Ingredient_Source`. The staging `source` field describes food ingredient origin ("house-made", "grass-fed", "organic"), not data collection provenance. This produced `Ingredient_Source = "unknown"` for ~2,481 ingredient rows, blocking all derived filter dependency checks.

**Fix applied:** `upsert_dishes.py` now writes `"menu"` for all staged ingredients (staging requires `menu_verified: true`). `backfill_enrichment.py` now upgrades legacy `"unknown"` values for dishes with confirmed staging provenance.

**Remaining work:** Backfill `--apply` must be run to upgrade existing legacy rows. ~673 dishes affected.

---

### `Ingredient_Type`
**Canonical meaning (intended):** The structural/functional type of the ingredient in the dish.  
**Intended canonical values:** `standard`, `sauce`, `dressing`, `seasoning`, `base`, `protein`, `topping`

**🟡 VIOLATION — SEMANTIC OVERLAP:**  
The staging JSON `type` field contains two distinct categories of values:

| Category | Values found | Concept |
|---|---|---|
| Functional role in dish | `sauce`, `dressing`, `base`, `condiment`, `compound` | What role does this ingredient play? |
| Food category | `vegetable`, `grain`, `dairy`, `fruit`, `herb`, `seed`, `house`, `house-made`, `housemade` | What kind of food is this? |

"Protein" is particularly ambiguous — it means both "food category" (this is a protein source) and "functional role" (this is the protein component of the dish). "House" and "house-made" are production origin, not a type.

`Component_Role` (see below) also stores functional role information. There is semantic overlap between `Ingredient_Type` and `Component_Role` for values like `sauce`, `base`, and `protein`.

**Recommendation:**  
Define `Ingredient_Type` as food category only: `protein`, `vegetable`, `grain`, `dairy`, `fat`, `legume`, `fruit`, `herb/spice`, `sauce`, `condiment`, `compound`. Move functional dish-role information exclusively to `Component_Role`. Document the canonical enum in the Rules Registry and validate against it in `validate_database.py`.

**Current impact:** Non-canonical values are remapped to `Unknown` in `backfill_enrichment.py`. This is safe but loses information that could be recovered with a proper enum.

---

### `Component_Role`
**Canonical meaning:** The functional role this ingredient plays in the dish structure.  
**Staging `role` values found:** `topping`, `base`, `protein`, `sauce`, `vegetable`, `component`, `cheese`, `filling`, `dressing`, `side`, `garnish`, `condiment`, `vessel`, `bread`, `wrapper`

**🟡 VIOLATION — FOOD CATEGORY CONTAMINATION:**  
`vegetable` and `cheese` are food categories, not dish roles. They describe what the ingredient *is*, not what it *does* in the dish. These belong in `Ingredient_Type`, not `Component_Role`.

`protein` is again ambiguous — "the protein component" (role) vs "a protein-category food" (type).

**Recommendation:** Restrict `Component_Role` to structural dish roles only: `base`, `protein-component`, `sauce`, `topping`, `filling`, `vessel`, `wrapper`, `garnish`, `side`, `condiment`, `dressing`. Retire `vegetable` and `cheese` as role values.

---

### `Cut_Type`
**Status: ✅ Clean.** Values are physically accurate cut descriptions: `sliced`, `chopped`, `shredded`, `diced`, `ground`, `crumbled`, `fillet`, `none`. No violations found.

---

### `Preparation`
**Canonical meaning:** How the ingredient was prepared before it appears in the dish.  
**Values found:** `grilled`, `fried`, `roasted`, `smoked`, `baked`, `raw`, `fresh`, `pickled`, `steamed`, `cooked`, `toasted`, `house-made`, `compound`, `unspecified`, `none`

**🟡 VIOLATION — ORIGIN CONTAMINATION:**  
`house-made` is a production origin (where it was made), not a preparation method. `compound` describes the ingredient's complexity (it's a multi-ingredient preparation), not the method itself. `fresh` and `raw` overlap — both mean "uncooked."

**Recommendation:** Define `Preparation` as cooking/processing method only. Move `house-made` to a future `Ingredient_Origin` field. Clarify the `fresh` vs `raw` distinction or standardize to one term.

---

### `Allergen_Flags` (ingredient-level)
**Canonical meaning:** Allergens present in this specific ingredient, from a verified source.  
**Values found:** allergen names (`dairy`, `gluten`, `wheat`, `fish`, `eggs`, `sesame`, `shellfish`, `soy`, `tree nuts`), `none`, `unknown`

**Status: ✅ Functionally clean.** Consistent with enrichment policy. However, `gluten` and `wheat` overlap — gluten is a component of wheat, not a separate allergen category. The Big 9 allergen framework uses `wheat`, not `gluten`. Using both creates ambiguity.

**Recommendation:** Standardize to the FDA Big 9 allergen list: milk, eggs, fish, shellfish, tree nuts, peanuts, wheat, soybeans, sesame. Retire `gluten` in favor of `wheat`. Document in the schema.

---

### `Status`
**Canonical meaning in Ingredient Details:** Whether this ingredient row is active.  
**Canonical meaning in DLD:** Whether this dish is active.

**🟡 DUAL-LOCATION RISK:**  
`Status` appears in both Ingredient Details and Goldpan Dish Level Data. There is no enforcement that they stay synchronized. An inactive dish could have Active ingredient rows, which would cause the ingredient rows to appear in enrichment analysis but the dish to be excluded from derived filter computation. The engine currently excludes inactive dishes by checking DLD, not ingredient row Status.

**Recommendation:** Document the authority hierarchy: DLD `Status` is authoritative for dish-level decisions. Ingredient Details `Status` is informational. Add a validation check that flags ingredient rows whose dish is Inactive but whose row Status is Active.

---

### `Version`
**Status: ✅ Clean.** Schema versioning field. Always `1` for initial rows. Well-defined.

---

## Goldpan Dish Level Data

### `Allergen_summary`
**Canonical meaning (intended):** A human-readable allergen summary for the dish.

**🟡 VIOLATION — THREE CONCEPTS IN ONE FIELD:**  
The field currently contains a mixture of:
1. Structured allergen lists: `"Contains gluten, dairy, eggs"`
2. Source attribution: `"Allergens sourced from Blue Root's published nutrition document"`
3. Advisory language: `"Contact restaurant to confirm"`
4. Uncertainty markers: `"Unknown"`

These are three distinct things: *what* the allergens are, *where* the information came from, and *how confident* GoldPan is. Combining them into one free-text field makes the field unqueryable and unreliable as a data source for derived filters.

**Recommendation:** Separate into structured fields:
- `Allergen_list` — canonical allergen identifiers (queryable)
- `Allergen_source` — where GoldPan obtained this allergen information
- `Allergen_confidence` — `confirmed`, `likely`, `unknown`

Until structured allergen fields are implemented, `allergen_summary` is display-only and must not be used as a data source for derived filter computation.

---

### `Dietary_Tags`
**Canonical meaning:** Dietary categories that apply to this dish as served.  
**Values found:** lists of tags like `vegetarian`, `vegan`, `gluten-free`, `high-protein`, `dairy-free`

**Status: ✅ Clean.** Values are consistent. Tags describe what the dish *is*. Well-defined.

---

### `Dietary_Options`
**Canonical meaning (intended):** Modifications available for this dish on request.

**🟡 VIOLATION — MULTIPLE CONCEPTS:**  
Values found include:
- Dietary modifications: `"GF, Vegan"`, `"GF, DF"`
- Serving variations: `"Available as sandwich, laffa, or plate"`, `"available in 16 oz or 24 oz"`
- Specific substitutions: `"Egg whites available upon request"`, `"vegan cheese (+$4)"`

These are different concepts: *dietary modification options* vs *serving format options* vs *ingredient substitution options*. All three are useful but they belong in separate fields or a structured modification schema.

**Current impact:** Low — `Dietary_Options` is passed through to `dishes.json` as-is. No derived filters use it. Low risk of computation error, but not queryable.

---

### `Status` (in DLD)
**Status: ✅ Clean.** `Active` / `Inactive`. Authoritative for dish-level pipeline decisions.

---

## Staging JSON — Ingredient-Level Fields

### `source`
**🔴 FIELD MISROUTED (fixed 2026-06-28):**  
This field describes food ingredient origin ("house-made", "grass-fed", "organic", "KY Farm Fresh", "SIMPLi"). It was being written to `Ingredient_Source` in the sheet, which is a data collection provenance field. Fix: `upsert_dishes.py` now ignores `source` when writing `Ingredient_Source`.

**🟡 DATA LOSS:**  
The `source` field is now dropped entirely during upsert — the information is not stored anywhere in the sheet. Ingredient provenance data (grass-fed, locally sourced, house-made, named supplier) is a transparency-relevant data point that GoldPan is currently discarding.

**Recommendation:** Define a new `Ingredient_Origin` field in Ingredient Details to capture food provenance. Add it to the staging JSON spec, upsert pipeline, and schema validation.

---

### `type`
See `Ingredient_Type` above. Same semantic overlap issue applies at the source.

---

### `role`
See `Component_Role` above. Same food-category contamination applies at the source.

---

## Staging JSON — Dish-Level Fields

### Scoring field proliferation
**🟡 SCHEMA DRIFT:**  
Two different scoring schemas are present across staging files:

| Schema A (475 dishes) | Schema B (33 dishes) |
|---|---|
| `total_score` | `transparency_score` |
| `core_clarity` | `core_ingredient_score` |
| `prep_clarity` | `prep_score` |
| `sauce_disclosure` | `sauce_score` |
| `allergen_transparency` | `allergen_transparency_score` |
| `transparency_level` | `transparency_tier` |

These appear to be two versions of the transparency scoring methodology applied at different times. The second schema (33 dishes) uses different field names and possibly different scales.

**Current impact:** `upsert_dishes.py` reads `transparency_level` (Schema A) for the Transparency Scoring tab. Schema B dishes (`transparency_tier`) are not read — their scores may not be landing correctly.

**Recommendation:** Audit which restaurant the 33 Schema B dishes belong to. Normalize to one scoring schema. Document the canonical schema in a staging file spec.

---

### `allergen_flags` at dish level
**🟡 FORMAT INCONSISTENCY:**  
33 dishes in staging have a dish-level `allergen_flags` field containing Python list strings like `"['tree nuts']"`, `"['sesame', 'tree nuts']"`. This is different from the ingredient-level `allergen_flags` (which stores a single allergen string). Same field name, different format, different semantic scope.

**Recommendation:** Rename dish-level allergen flags to `dish_allergen_list` and store as a proper JSON array, not a stringified Python list.

---

### `notes` (dish-level)
**🟡 MULTI-PURPOSE FIELD:**  
Contains canvasser observations, data gap explanations, and other miscellaneous notes: "GF marked on menu", "Protein addition. No ingredient detail on menu. Tags and allergens unknown.", "Popular item."

These serve different purposes — some are data quality annotations, some are informational. No downstream system reads `notes` currently, so impact is low, but structured canvasser annotations would be more useful than a free-text notes field.

---

## Field Inventory Summary

| Field | Location | Status | Issue |
|---|---|---|---|
| `Ingredient_Source` | Ingredient Details | 🔴 Fixed | Was storing food origin; now correct |
| `Ingredient_Type` | Ingredient Details | 🟡 | Mixes food category and functional role |
| `Component_Role` | Ingredient Details | 🟡 | Contains food category values (vegetable, cheese) |
| `Preparation` | Ingredient Details | 🟡 | Contains origin value (house-made) |
| `Allergen_Flags` | Ingredient Details | 🟡 | `gluten` vs `wheat` ambiguity |
| `Status` | Both sheets | 🟡 | Dual-location, no sync enforcement |
| `Allergen_summary` | DLD | 🟡 | Three concepts in one free-text field |
| `Dietary_Options` | DLD | 🟡 | Mixes dietary mods, serving options, substitutions |
| `source` | Staging JSON | 🔴 Fixed / 🟡 Data loss | Fixed routing; data now discarded |
| `type` | Staging JSON | 🟡 | Same as Ingredient_Type issue |
| `role` | Staging JSON | 🟡 | Same as Component_Role issue |
| Scoring fields | Staging JSON | 🟡 | Two schemas present, field names differ |
| `allergen_flags` (dish) | Staging JSON | 🟡 | Stringified Python list, different from ingredient-level |
| `notes` | Staging JSON | 🟢 | Multi-purpose free text, low current impact |
| All other fields | — | ✅ | No violations found |

---

## Clean Fields (No Action Required)

`Restaurant_ID`, `Restaurant_Name`, `Location`, `Dish_ID`, `Dish_Name`, `Ingredient`, `Cut_Type`, `Version`, `Status` (DLD), `Dietary_Tags`, `cut_type` (staging), `preparation` (mostly clean), `allergen_flags` (mostly clean).
