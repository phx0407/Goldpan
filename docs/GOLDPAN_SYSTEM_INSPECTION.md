# GoldPan System Rule Inspection
**Date:** 2026-06-28  
**Scope:** Full pipeline — codebase, data, rules, automation, human dependencies  
**Status:** ⛔ FAIL — database in non-passing state; multiple automation gaps identified  

> Inspection only. No changes made.

---

## Summary Scorecard

| # | Category | Result |
|---|----------|--------|
| 1 | Commit / Change Tracking | ⚠️ PARTIAL |
| 2 | Ingredient Details Automation | ⚠️ PARTIAL |
| 3 | Dish Level Data Automation | ❌ FAIL |
| 4 | Transparency Scoring Automation | ⚠️ PARTIAL |
| 5 | Cross-Table Integrity | ❌ FAIL |
| 6 | Automation vs. Human Reliance | ⚠️ PARTIAL |
| 7 | Rule Compliance | ⚠️ PARTIAL |

---

## 1. Commit / Change Tracking

### What automatically generates artifacts

| Script | Artifact produced |
|--------|------------------|
| `validate_database.py` | `validation_report.txt` — full report with PASS/FAIL |
| `recanvass_report.py` | `recanvass_reports/YYYY-MM-DD.json` and `.md` |
| `recanvass_new_dishes.py` | `recanvass_reports/YYYY-MM-DD_new_dishes.json` |
| `update.sh` | Git commit with date-stamped message |
| `fetch_dishes.py` | `dishes.json` and `restaurants.json` (data outputs, not audit artifacts) |

### What is currently silent

- **All 23+ patch scripts** (`patch_emmysquared.py`, `patch_d086.py`, `patch_hours_addresses.py`, etc.) write directly to Google Sheets and produce terminal output only. No artifact is saved. If the terminal session closes, the audit trail is gone.
- **`upsert_dishes.py`** prints per-tab counts to terminal (added/updated) but saves no artifact file. A `--dry-run` run produces output only to the terminal — it is not saved.
- **`backfill_ingredient_details.py`** modifies production data with no saved report.
- **`update.sh`** does not run `validate_database.py` after pushing — the build completes without a post-build health check.
- No session-level log tracks which scripts ran in a given work session.

### Whether any process modifies production data without a clear audit trail

**Yes.** Every patch script (`patch_*.py`, 23+ scripts) writes directly to the Google Sheet with only transient terminal output. The git commit only covers `dishes.json`, `restaurants.json`, and `filters.json` — not the underlying Google Sheet. Patch script changes to the Sheet are not represented in git history at all.

### Recommended additions
- Save `upsert_dishes.py` dry-run output to `staging_reports/YYYY-MM-DD_[restaurant]_dryrun.txt` automatically.
- Save patch script output to a `patch_log/` directory automatically.
- Add `python3 validate_database.py` to the end of `update.sh`.

---

## 2. Ingredient Details Automation

**Canonical schema:** Restaurant_ID | Restaurant_Name | Location | Dish_ID | Dish_Name | Ingredient | Cut_Type | Preparation | Ingredient_Type | Status | Version | Ingredient_Source | Allergen_Flags | Component_Role

### Is every required field automatically populated?

**Via `upsert_dishes.py`: ✓ Yes** — `build_ingredient_rows()` writes all 14 columns. `validate_ingredient_rows()` blocks if Restaurant_ID, Restaurant_Name, Location, Dish_ID, Dish_Name, or Ingredient are missing.

**Via patch scripts: ❌ No** — `patch_emmysquared.py` (and likely others) writes ingredient rows as **2-column sparse rows**: `[dish_id, ingredient]`. This creates rows missing Restaurant_ID, Restaurant_Name, Location, Dish_Name, and all detail columns. This directly bypasses the validation gate in `upsert_dishes.py`.

```python
# patch_emmysquared.py line 117 — FAILING pattern:
new_rows.append([did, ing])   # only 2 columns — creates sparse row
```

### Does every ingredient correctly map back to its parent dish and restaurant?

**Via `upsert_dishes.py`:** Yes — Restaurant_ID and Restaurant_Name are drawn from the staging file top level, not per-dish. This is correct.

**Via patch scripts:** Not guaranteed. `patch_emmysquared.py` doesn't write Restaurant_ID or Restaurant_Name at all.

### Can any process still create sparse or shifted rows?

**Yes.** Any patch script that appends `[dish_id, ingredient]` without the full 14-column structure creates sparse rows. The validation gate in `upsert_dishes.py` only applies to staging-file upserts — it does not protect against direct patch script writes.

### Non-canonical enum value in staging files

Staging files use `"type": "house"` for ingredients (visible in `staging_cleaneatz.json`, and others). The canonical `Ingredient_Type` enum in `validate_database.py` is: `standard, sauce, dressing, seasoning, base, protein, topping, unknown`. **"house" is not a valid enum value.** This writes an out-of-enum value into Ingredient_Details without triggering a validation error.

### Failures

| Finding | Severity | Type |
|---------|----------|------|
| `patch_emmysquared.py` writes 2-column ingredient rows | Critical | Write issue |
| "house" ingredient type not in canonical enum | Medium | Schema issue |
| No validation gate on patch script writes | High | Architecture issue |

---

## 3. Dish Level Data Automation

**Canonical schema:** Restaurant_ID | Restaurant | Location | Dish_ID | Dish_Name | Dietary_Tags | Dietary_Options | Tag_Source | Verification_Status | Hours | Menu_Link | Menu_Price | Restaurant_Address | Allergen_summary | Last_Updated | Restaurant_Website | Status | Version | Category

### Does every dish automatically populate every required field?

**Via `upsert_dishes.py`: Mostly yes.** `build_dish_level_rows()` writes all 19 columns. However:

- **Version** is explicitly written as `""` (blank). Comment in code: `"managed in sheet"`. No script populates Version automatically.
- **Category** is optional in staging — if omitted from the staging file, a blank writes to the sheet. UPSERT_GUIDE.md says Category is **required on every dish**, creating a disconnect between the guide and the enforcement.
- **Tag_Source** is hardcoded to `"menu"` — not configurable per dish.
- **Verification_Status** is hardcoded to `"unconfirmed"` — correct default, but never updated automatically.

### Is Status always populated correctly?

**❌ No — and this is a critical current failure.**

The latest validation report (`validation_report.txt`, run 2026-06-27) shows **702 rows in Goldpan Dish Level Data are missing Status**. Only 96 rows have a Status value (90 Active + 6 Inactive). This means approximately 86% of DLD rows have no Status. `fetch_dishes.py` filters by `status == "inactive"` — rows with blank Status are treated as active and included in public output.

The root cause appears to be that these dishes were written by the legacy `add_dishes.py` (replaced by `upsert_dishes.py`) which did not write a Status column.

### Are Version and Last_Updated maintained?

- **Last_Updated**: ✓ Auto-stamped to today's date by `upsert_dishes.py`. Correctly reflects actual upsert date.
- **Version**: ❌ Not maintained by any script. Written as blank.

### Can duplicate Dish_IDs still occur?

**Yes.** The validation report shows **66+ duplicate Dish_IDs in Dish Level Data** as of 2026-06-27. The upsert logic (delete old rows + append new) should prevent duplicates for staging upserts, but the duplicates appear to be a legacy residue from `add_dishes.py` combined with the upsert re-runs. `check_name_duplicates()` warns on name collisions but does not block them.

### Can orphaned dishes still occur?

**Partially protected.** `fetch_dishes.py` exits with an error if a scored dish (in Transparency Scoring) has no row in Dish Level Data — this is a production build gate. However, a dish can exist in Dish Level Data without a Transparency Scoring row (no reverse check), and validation of this direction requires running `validate_database.py` manually.

### Failures

| Finding | Severity | Type |
|---------|----------|------|
| 702 DLD rows missing Status (86% of rows) | Critical | Data quality issue |
| 66+ duplicate Dish_IDs in DLD | High | Data quality issue |
| Version never auto-populated | Medium | Architecture issue |
| Category not enforced at write time | Medium | Validation issue |
| No reverse check: DLD dish not in Transparency Scoring | Medium | Architecture issue |

---

## 4. Transparency Scoring Automation

**Canonical schema:** Restaurant_ID | Restaurant_Name | Dish_ID | Dish_Name | Core_Clarity | Sauce_Seasoning_Disclosure | Allergen_Transparency | Prep_Clarity | Total_Score | Transparency_Level | Notes

### Does every dish automatically receive a matching Transparency Scoring row?

**Via `upsert_dishes.py`: ✓ Yes** — `build_scoring_rows()` always creates a Transparency Scoring row for every dish in the staging file. Scores default to 0 and level to "Building Transparency" if not provided in staging.

### Can scoring records become orphaned?

**Yes.** Patch scripts that add dishes directly to Dish Level Data (like `resolve_orphans.py` which restores D113, D116, D121) do not automatically create matching Transparency Scoring rows. A dish added by a non-upsert path can exist in DLD with no score.

### Can scoring drift from Dish Level Data?

**Yes — and this is happening now.** When a patch script updates allergens or dietary tags in Dish Level Data, it does not automatically recalculate or update the matching Transparency Scoring row. Example: `patch_emmysquared.py` updates allergen summaries and dietary tags in DLD for 6 dishes but does not touch Transparency Scoring for those dishes. `patch_d086.py` is a positive exception — it updates both DLD and Scoring together, but this was done manually, not by a system rule.

### Does every update remain synchronized?

**No — synchronization is manual.** There is no trigger or hook that detects "DLD updated → Scoring may need recalculation." Each patch author must remember to update both tables.

### Current state

The validation report shows **67+ duplicate Dish_IDs in Transparency Scoring** — meaning the same dish has been scored twice. The scoring column heading in `validate_database.py` also has **12 columns** in its canonical schema definition (one more than the 11 listed in the inspection prompt, due to `Sauce_Seasoning_Disclosure` being listed separately from `Sauce_Disclosure`). This is a naming inconsistency worth verifying.

### Failures

| Finding | Severity | Type |
|---------|----------|------|
| 67+ duplicate Dish_IDs in Transparency Scoring | High | Data quality issue |
| Scoring drifts from DLD when patches are applied | High | Architecture issue |
| No automatic Transparency Scoring row for non-upsert dish additions | High | Write issue |
| No recalculation trigger when allergen/tag data changes | Medium | Architecture issue |

---

## 5. Cross-Table Integrity

### Automated checks in place

| Check | Where enforced | Action |
|-------|---------------|--------|
| Every Scoring dish → exists in DLD | `fetch_dishes.py` (build gate) | **Hard stop** — exits with error |
| Every restaurant in Scoring → in Menu Source Registry | `fetch_dishes.py` | Warning only, does not stop build |
| Ingredient Dish_IDs → exist in DLD | `validate_database.py` | Reports errors |
| Scoring Dish_IDs → exist in DLD | `validate_database.py` | Reports errors |
| Duplicate Dish_IDs per tab | `validate_database.py` | Reports errors |
| Every Restaurant_ID → in Menu Source Registry | Not checked | **No check exists** |

### Can cross-table relationships silently drift?

**Yes.** The cross-table checks require either a build (`fetch_dishes.py`) or an explicit manual run of `validate_database.py`. Patch scripts that write to a single tab do not trigger any cross-table verification. A patch can create an orphan and it remains undetected until the next validation run.

### Current state (from validation_report.txt, 2026-06-27)

**Overall status: FAIL**

- **Goldpan Dish Level Data:** 21 errors — 702 rows missing Status; 66+ duplicate Dish_IDs
- **Transparency Scoring:** 22 errors — 67+ duplicate Dish_IDs; 2 restaurants missing from Menu Source Registry (`East West`, `Brick & Tin Mountain Brook` — these are normalization variants that exist in the registry under normalized names, indicating a name normalization gap in `validate_database.py`)
- **Ingredient Details:** 36 errors — 344+ duplicate (Dish_ID, Ingredient) pairs; 16 orphaned ingredient rows for D008, D113, D116, D121
- **Menu Source Registry:** 0 errors, 1 warning (Slutty Vegan flagged Needs Review)

### Bug in `validate_database.py`

`validate_menu_source_registry(ss, scored_names)` is called with `scored_names = set()` (empty) because the registry validation runs before Transparency Scoring validation. The "Coverage: Transparency Scoring → Registry" check inside the registry validator therefore always skips. This is why the report shows: `⚠ No scored restaurant names provided — coverage check skipped`. The cross-check only works in the Scoring → Registry direction (inside `validate_transparency_scoring`), not Registry → Scoring.

### Failures

| Finding | Severity | Type |
|---------|----------|------|
| Database currently in FAIL state | Critical | Data quality issue |
| 702 missing Status values in DLD | Critical | Data quality issue |
| 66+ DLD duplicate Dish_IDs | High | Data quality issue |
| 67+ Scoring duplicate Dish_IDs | High | Data quality issue |
| 344+ duplicate ingredient rows | High | Data quality issue |
| 16 orphaned ingredient rows | High | Data quality issue |
| Registry coverage check bug (always skips) | Medium | Validation issue |
| No Restaurant_ID → Menu Source Registry check | Medium | Architecture issue |
| No automatic cross-table check after patch scripts | High | Architecture issue |

---

## 6. Automation vs. Human Reliance

The following places in the pipeline currently depend on you to provide information the system should already know or be able to discover:

### 1. Current maximum Dish_ID
- **What's asked:** You must manually track the max Dish_ID before assigning new ones.
- **Where the answer lives:** The Google Sheet, `dishes.json`, or any staging file.
- **Why it fails:** No script queries and reports the current max. `UPSERT_GUIDE.md` hard-codes `"Current max dish ID: D685"` — a static number that goes stale.
- **Fix:** Add a `next_id.py` (or equivalent) that reads the sheet or `dishes.json` and prints the next available Dish_ID and Restaurant_ID.

### 2. Dish ID assignment
- **What's asked:** You assign `dish_id` manually in every staging file.
- **Where the answer lives:** The database.
- **Why it fails:** No auto-assignment script exists.
- **Fix:** ID assignment should be automated as part of staging file generation.

### 3. Pre-flight restaurant lookup
- **What's asked:** Before creating a staging file, you must remember to check whether the restaurant already exists and what dishes it has.
- **Where the answer lives:** `dishes.json`, Google Sheet.
- **Why it fails:** No "show me what we already know about Restaurant X" command exists.
- **Fix:** A `lookup_restaurant.py` that queries the system and outputs existing dishes, IDs, and registry status.

### 4. Menu source URL discovery
- **What's asked:** You must discover and verify menu URLs manually before canvassing.
- **Where the answer lives:** Nowhere — this is genuinely new information for new restaurants.
- **Status:** Appropriate human input. However, for existing restaurants, `recanvass_report.py` could flag dead URLs automatically — this is partially automated.

### 5. Transparency scoring
- **What's asked:** You manually assign core_clarity, sauce_disclosure, allergen_transparency, prep_clarity scores for every dish.
- **Where the answer lives:** Scoring rubric in `CANVASSING_RULES.md`.
- **Status:** Scoring requires judgment and is appropriate for human input. However, the default values (defaulting to 0) are not safe defaults — the allergen default rule in `CANVASSING_RULES.md` states allergen transparency **defaults to 5** for all unconfirmed dishes, not 0.
- **Fix:** `upsert_dishes.py` should default `allergen_transparency` to 5 (not 0) when not provided in staging, per the canonical scoring rule.

### 6. Category assignment
- **What's asked:** You assign category in each staging file; if forgotten, it's blank.
- **Where the answer lives:** `UPSERT_GUIDE.md` has a full category list.
- **Fix:** `upsert_dishes.py` should warn (or block) when category is blank. A `backfill_categories.py` exists but is run manually.

### 7. Post-build validation
- **What's asked:** You must remember to run `validate_database.py` separately.
- **Where the answer lives:** Already built.
- **Fix:** Add to `update.sh`.

---

## 7. Rule Compliance Inspection

| Principle | Status | Notes |
|-----------|--------|-------|
| Menu verification before dish creation | ✅ Pass | `upsert_dishes.py` blocks without `menu_verified: true`. Gate is solid. |
| Supporting documents enrich but never create dishes | ✅ Pass | DATA_RULES.md R2.1 enforced by `menu_verified` gate. Patch scripts only update existing rows. |
| Source hierarchy (R9) | ⚠️ Partial | Documented in DATA_RULES.md but not enforced by any script. Any source can be used without automated tier checking. |
| Validation before upsert | ⚠️ Partial | `upsert_dishes.py` validates `menu_verified` and ingredient completeness. Does not run `validate_database.py` first. Full database validation is not a pre-upsert gate. |
| Dry-run before write | ⚠️ Partial | `--dry-run` flag exists in `upsert_dishes.py`, `patch_d086.py`, and some others. Not a required step. Dry-run output not saved to file. Several patch scripts have no dry-run flag at all. |
| Database Health Report after build | ❌ Fail | `update.sh` does not run `validate_database.py`. The build completes and pushes without a post-build health check. |
| Trusted automation | ⚠️ Partial | Automation is increasing but patch scripts write silently with no artifact. Current database is in FAIL state, meaning the last push deployed data with known integrity errors. |
| Self-describing database records | ⚠️ Partial | Ingredient rows written by `upsert_dishes.py` are fully self-describing (all 14 columns). Rows written by patch scripts (2-column) are not. 702 DLD rows missing Status. |
| Canonical schema usage | ✅ Pass | Schemas are defined in `validate_database.py` and match DATA_RULES.md. `upsert_dishes.py` writes all columns. Deviation: "house" ingredient type in staging is off-schema. |
| Header-name-based mapping | ✅ Pass | `upsert_dishes.py`, `validate_database.py`, and `backfill_ingredient_details.py` all use header-name lookups. Fixed column positions appear only in the legacy-documented but commented-out sections. |

---

## 8. Inspection Report

### PASS / FAIL by Category

| Category | Result | Errors |
|----------|--------|--------|
| 1. Commit / Change Tracking | ⚠️ PARTIAL | Patch scripts produce no saved artifacts. No post-build health report. |
| 2. Ingredient Details Automation | ⚠️ PARTIAL | Patch scripts write sparse rows. "house" type off-schema. |
| 3. Dish Level Data Automation | ❌ FAIL | 702 rows missing Status. 66+ duplicates. Version never populated. |
| 4. Transparency Scoring Automation | ⚠️ PARTIAL | 67+ duplicates. Score drifts when patches applied. No sync trigger. |
| 5. Cross-Table Integrity | ❌ FAIL | Database currently in FAIL state. Multiple open integrity errors. Registry coverage check has a bug. |
| 6. Automation vs. Human Reliance | ⚠️ PARTIAL | Max ID tracking, pre-flight lookups, scoring defaults are manual. |
| 7. Rule Compliance | ⚠️ PARTIAL | Menu verification ✓. Post-build health report ✗. Dry-run not required ✗. |

---

### Failure Detail

**F1 — Database currently in FAIL state**
- Root cause: Legacy `add_dishes.py` wrote rows without Status column. Duplicate rows from re-runs of upsert that didn't fully clean old data. Patch scripts wrote sparse ingredient rows.
- Severity: **Critical**
- Fix: Run `fix_database_errors.py --apply`, `dedup_tabs.py`, `dedup_ingredients.py`, `resolve_orphans.py --apply`, then `backfill_ingredient_details.py`. Rerun `validate_database.py` until PASS.
- Type: Data quality issue

**F2 — Patch scripts write sparse ingredient rows**
- Root cause: `patch_emmysquared.py` (and likely others) appends `[dish_id, ingredient]` — 2 columns only.
- Severity: **Critical**
- Fix: All patch scripts that write ingredient rows must use the full 14-column row format, matching `build_ingredient_rows()` in `upsert_dishes.py`.
- Type: Write issue + Architecture issue

**F3 — No Database Health Report after build**
- Root cause: `update.sh` does not call `validate_database.py`.
- Severity: **High**
- Fix: Add `python3 validate_database.py` to the end of `update.sh`. Exit non-zero if validation fails.
- Type: Architecture issue

**F4 — Score drift between DLD and Transparency Scoring**
- Root cause: No trigger links DLD changes to Scoring updates. Patch authors must manually remember to update both tables.
- Severity: **High**
- Fix: Any script that updates allergens, tags, or ingredients for a dish should also update (or flag for review) the matching Transparency Scoring row.
- Type: Architecture issue

**F5 — Registry coverage check bug**
- Root cause: `validate_database.py` calls `validate_menu_source_registry(ss, scored_names)` before populating `scored_names`, so the coverage check always runs with an empty set.
- Severity: **Medium**
- Fix: Reorder validation: run Transparency Scoring first to collect `scored_names`, then pass that set to the registry validator.
- Type: Validation issue

**F6 — Max Dish ID manually tracked**
- Root cause: No script queries the database for the current maximum.
- Severity: **Medium**
- Fix: Add `python3 next_id.py` that reads `dishes.json` (or the sheet) and prints the next available Dish_ID and Restaurant_ID.
- Type: Architecture issue

**F7 — Allergen transparency defaults to 0, not 5**
- Root cause: `build_scoring_rows()` defaults `allergen_transparency` to `dish.get("allergen_transparency", 0)`. The canonical scoring rule in CANVASSING_RULES.md states the allergen default is 5.
- Severity: **Medium**
- Fix: Change default in `build_scoring_rows()` from `0` to `5`.
- Type: Schema issue

**F8 — "house" ingredient type is off-canonical-schema**
- Root cause: Staging files use `"type": "house"` but canonical enum is: standard, sauce, dressing, seasoning, base, protein, topping, unknown.
- Severity: **Low**
- Fix: Either add "house" to the canonical enum in `validate_database.py`, or replace "house" with the correct canonical type in staging files and the UPSERT_GUIDE.md.
- Type: Schema issue

**F9 — Name normalization mismatch in registry checks**
- Root cause: `validate_database.py` applies `normalize_restaurant_name()` in `validate_transparency_scoring()` but not consistently — "East West" and "Brick & Tin Mountain Brook" appear as errors even though normalized versions exist in the registry.
- Severity: **Medium**
- Fix: Apply `normalize_restaurant_name()` when building `registry_names` in `validate_menu_source_registry()` so normalized names match.
- Type: Validation issue

---

### What is fully automated

- Menu verification gate before upsert (`menu_verified: true` required)
- Full 14-column ingredient row construction via `upsert_dishes.py`
- Full 19-column DLD row construction via `upsert_dishes.py`
- Transparency Scoring row creation for every staging-file upsert
- Deduplication in `fetch_dishes.py` output
- Cross-table referential integrity check (Scoring → DLD) as a build gate in `fetch_dishes.py`
- Weekly menu change detection via `recanvass_report.py`
- Potential new dish detection via `recanvass_new_dishes.py`
- `validate_database.py` full schema/duplicate/integrity report when run manually
- Git commit with date-stamped message via `update.sh`

### What is partially automated

- Post-build validation (tool exists; not wired into pipeline)
- Dry-run mode (flag exists; not required or artifact-saved)
- Category backfill (script exists; run manually)
- Allergen backfill from PDFs (patch scripts exist per-restaurant; no general pipeline)
- Registry coverage cross-check (tool exists; has bug; not in pipeline)
- Duplicate detection (tool exists; run manually)
- Sparse row backfill (tool exists; run manually)

### What still depends on you

- Assigning Dish_IDs and Restaurant_IDs (no auto-discovery of max)
- Pre-flight restaurant lookup (no "what do we know about this restaurant?" command)
- Transparency scoring (judgment required; but default values are wrong)
- Recognizing when scoring needs updating after a patch
- Running `validate_database.py` separately after any changes
- Running `update.sh` after upsert (not triggered automatically)
- Ensuring patch scripts use full-column writes (no enforcement)

### Highest-priority architectural improvements

1. **Resolve the database FAIL state** — run the repair scripts and get `validate_database.py` to PASS before any new data is written.
2. **Add `validate_database.py` to `update.sh`** — every build should produce a health report and fail loudly if the database has errors.
3. **Fix patch script ingredient rows** — all patch scripts writing to Ingredient Details must use the full 14-column format.
4. **Fix the allergen default in `build_scoring_rows()`** — change from 0 to 5 per the canonical scoring rule.
5. **Fix the registry coverage check bug** — pass `scored_names` to the registry validator in the correct order.
6. **Add a `next_id.py` script** — auto-discover the current max Dish_ID and Restaurant_ID from the live database.
7. **Save `--dry-run` output to file automatically** — dry runs are only useful if reviewable later.
8. **Add a patch log** — all patch scripts should append a record to `patch_log/YYYY-MM-DD.txt` with: script name, target dish(es), source, what changed.

---

*Inspection conducted by reading: `DATA_RULES.md`, `CANVASSING_RULES.md`, `UPSERT_GUIDE.md`, `upsert_dishes.py`, `fetch_dishes.py`, `validate_database.py`, `audit_data.py`, `recanvass_report.py`, `recanvass_new_dishes.py`, `update.sh`, `patch_emmysquared.py`, `patch_d086.py`, `check_duplicates.py`, `backfill_ingredient_details.py`, `resolve_orphans.py`, `staging_cleaneatz.json` (representative), `validation_report.txt` (2026-06-27). No changes were made.*
