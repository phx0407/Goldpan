# GoldPan Cleanup Backlog

Items logged here are known data or code quality issues that do not block the current sprint and do not affect correctness of derived conclusions. They should be addressed in a dedicated cleanup pass.

---

## CL-001 — Provenance backfill gap (236 dishes)

**Logged:** 2026-06-29  
**Severity:** Data quality — does not affect correctness; blocks derived filter computation for affected dishes  
**Affects:** ~236 dishes showing "Dependency not met" (Unknown) in compute_derived_filters.py

**Description:**  
Approximately 236 dishes have `Ingredient_Source` values that are food-origin categories (`Unknown`, `animal`, `neutral`, `plant-based`) rather than data provenance values (`menu`, `pdf`, etc.). These values come from the old `upsert_dishes.py` behavior that wrote the staging file's `source` field (ingredient origin) directly into `Ingredient_Source` (data provenance). That bug was fixed, but the historical rows were not fully corrected.

**Example:**  
Real & Rosemary — D001 Grilled Herb Chicken has `Ingredient_Source` values of `Unknown, animal, neutral, plant-based`. The backfill corrected other restaurants but Real & Rosemary was not in `CANVASSED_DISHES` at backfill time.

**Root cause:**  
`backfill_enrichment.py` only corrects dishes whose restaurant appears in `CANVASSED_DISHES`. The backfill was applied before all restaurants were added to that dict.

**Resolution path:**  
1. Audit which restaurants are missing from `CANVASSED_DISHES` in `backfill_enrichment.py`
2. Add verified restaurants to `CANVASSED_DISHES`
3. Run `python3 backfill_enrichment.py` (dry run) to confirm planned writes
4. Run `python3 backfill_enrichment.py --apply`
5. Re-run `python3 compute_derived_filters.py` to confirm Computed count increases

**Expected impact:** Most of the 236 "Dependency not met" Unknowns should convert to Computed or Not Applicable once provenance is corrected.

**Blocked by:** Nothing — can proceed independently when prioritized.

---

## CL-002 — D111 duplicate ingredient rows (Brisket Panini, Brick & Tin)

**Logged:** 2026-06-29  
**Severity:** Data noise — conclusion is correct (Not Applicable); rows are redundant  
**Affects:** D111 only

**Description:**  
D111 Brisket Panini at Brick & Tin has two nearly identical beef brisket rows:
- `'certified angus braised beef brisket'`
- `'certified angus beef braised beef brisket'`

Both are beef-positive and the derived conclusion (Not Applicable) is correct. The duplication is cosmetic noise in the ingredient list and the compute report.

**Root cause:**  
Likely a double-entry when the dish was canvassed or patched. The deduplication in `fetch_dishes.py` operates at the dish level (restaurant + dish name), not at the ingredient row level.

**Resolution path:**  
1. Open Ingredient Details in Google Sheets
2. Find D111 rows
3. Delete the duplicate row (keep the more accurate of the two ingredient names)
4. Re-run `python3 fetch_dishes.py` to confirm clean output

**Blocked by:** Nothing — manual sheet edit, 5 minutes.

---

## CL-003 — Schema A / Schema B scoring normalization (33 dishes)

**Logged:** Prior session (re-logged 2026-06-29)  
**Severity:** Data inconsistency — does not affect application output today; may cause issues if scoring is queried programmatically  
**Affects:** ~33 dishes using Schema B field names

**Description:**  
Two scoring schemas exist across staging files and the Transparency Scoring tab:

- **Schema A** (majority): `core_clarity`, `sauce_disclosure`, `allergen_transparency`, `prep_clarity`, `total_score`, `transparency_level`
- **Schema B** (~33 dishes, e.g. Blue Root): `core_ingredient_score`, `sauce_score`, `prep_score`, `allergen_transparency_score`, `transparency_score`, `transparency_tier`

`fetch_dishes.py` only reads `Transparency_Level`, not the sub-scores, so this inconsistency is invisible in `dishes.json` today. It becomes a problem if sub-scores are ever surfaced.

**Resolution path:**  
1. Decide on canonical schema (Schema A is the majority; recommend standardizing on it)
2. Write a migration script to rename Schema B columns in the Transparency Scoring tab
3. Update the affected staging files to use Schema A names
4. Update `validate_staging.py` if needed

**Blocked by:** Schema decision. Low urgency.

---

## CL-004 — Allergen flag vocabulary: "gluten" vs. "wheat"

**Logged:** Prior session (re-logged 2026-06-29)  
**Severity:** Data consistency — affects how allergen flags display and filter  
**Affects:** Any dish using `"gluten"` as an allergen flag

**Description:**  
FDA Big 9 uses `"wheat"` as the named allergen. GoldPan staging files use `"gluten"` in some places. These refer to the same primary allergen but `"gluten"` is a symptom of wheat, not the allergen itself. Celiac disease is triggered by wheat (and rye and barley), not just gluten from wheat.

**Resolution path:**  
1. Audit `Allergen_Flags` column in Ingredient Details for `"gluten"` values
2. Determine whether to replace with `"wheat"` or add `"wheat"` alongside
3. Update affected staging files
4. Update `RECOGNIZED_ALLERGEN_FLAGS` in `schema.py`

**Blocked by:** Policy decision on allergen vocabulary. Medium urgency.

---

## CL-005 — Structured allergen fields (replace free-text allergen_flags)

**Logged:** 2026-06-29  
**Severity:** Data quality / schema evolution  
**Affects:** All staging files; Ingredient Details tab

**Description:**  
`allergen_flags` currently stores free-text strings (e.g., `"tree nuts (almonds)"`, `"dairy (grits)"`, `"wheat (flour option)"`). Parenthetical qualifiers that specify the exact allergen source (variety, dish component, preparation form) have no canonical home. They are stripped by the validator, which means the specificity is silently discarded.

The current design enforces atomic allergen tokens at the flag level. Detail beyond the allergen atom (specific nut variety, which component carries the allergen, preparation-dependent presence) belongs in a structured field that doesn't exist yet.

**Resolution path:**  
1. Add an `allergen_note` field to the ingredient schema (staging files and Ingredient Details)
2. Update `upsert_dishes.py` to write `allergen_note` to a new column in Ingredient Details
3. Migrate existing parenthetical detail from `allergen_flags` into `allergen_note`:
   - `"tree nuts (almonds)"` → flag: `"tree_nuts"`, note: `"almonds"`
   - `"dairy (grits)"` → flag: `"dairy"`, note: `"via grits"`
   - `"wheat (flour option)"` → flag: `"wheat"`, note: `"flour option only"`
4. Update `validate_staging.py` to warn when parenthetical detail appears in a flag
   and suggest moving it to `allergen_note`

**Blocked by:** Schema migration and upsert_dishes.py update. Low urgency — the existing data is not wrong, just unstructured.

---

## CL-006 — Manual re-scoring: 57 dishes with unrecognized scoring model

**Logged:** 2026-06-29  
**Severity:** Data quality — scoring schema inconsistency  
**Affects:** staging_abhieatery.json (36), staging_bahaburger.json (5), staging_emmysquared_pizzas.json (1), staging_urbancookhouse.json (15)

**Description:**  
57 dishes have component scores on a 0-10 scale but `total_score` values that do not follow the normalized formula (`round(sum/40*100)`). These were scored with the total set independently of the components. Auto-migration is not safe because reversing the intent of an independently-set total is not possible without the original canvasser's assessment.

The `migrate_scoring.py` script identifies these dishes and flags them for manual review. `validate_staging.py` generates `UNRECOGNIZED_SCORING_MODEL` warnings for them.

**Resolution path:**  
1. For each flagged dish, re-assess all four component scores on the 0-25 canonical scale
2. Set `total_score = sum(new component scores)`
3. Run `validate_staging.py` to confirm warnings are resolved
4. Re-run `migrate_scoring.py` to confirm no dishes remain flagged

**Blocked by:** Canvasser availability to re-evaluate 57 dishes. Medium urgency.
