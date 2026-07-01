# GoldPan Architectural Health Review

**Date:** 2026-06-28  
**Scope:** Full pipeline — staging, upsert, enrichment, derived filters, output  
**Purpose:** Identify structural issues that could prevent GoldPan from becoming a reliable, rules-driven, self-validating knowledge system. This review complements the `SCHEMA_AUDIT.md` (which covers field-level violations) and the `BACKFILL_RELIABILITY_REPORT.md` (which covers write verification). This document covers architectural patterns — how the pipeline is organized and what structural choices create fragility.

---

## Summary of Findings

| # | Issue | Severity | Impact |
|---|---|---|---|
| 1 | Patch script proliferation — 30+ one-off scripts with duplicated boilerplate | 🔴 High | Reliability, maintainability, no audit trail |
| 2 | `upsert_dishes.py` uses delete-and-reinsert, not true upsert | 🔴 High | Data loss risk on interrupted runs |
| 3 | No centralized schema definition — column order duplicated in five places | 🔴 High | Any column change requires manual multi-file updates |
| 4 | Staging JSON `source` field is silently discarded — no `Ingredient_Origin` column | 🟡 Medium | Verified food provenance data permanently lost |
| 5 | `Allergen_summary` is free text — blocks all derived allergen filter computation | 🟡 Medium | Allergen-based filters cannot be reliably computed |
| 6 | Two scoring schemas in staging files — Schema A vs Schema B | 🟡 Medium | 33 dishes may have scores not landing in the sheet |
| 7 | No staging file JSON schema validation at upsert time | 🟡 Medium | Malformed staging files produce silent row corruption |
| 8 | `derived_filters.json` is not integrated into `fetch_dishes.py` or `dishes.json` | 🟡 Medium | Derived filter work is not reaching the application |
| 9 | Patch scripts use `if col_idx is not None` guards — silent column drops | 🔴 High | Wrong column targets fail silently |
| 10 | No staging file versioning or naming convention for the archive | 🟢 Low | 22 staging files with no registry; provenance unclear |

---

## Finding 1: Patch Script Proliferation

### What is happening

The `goldpan/` directory contains approximately 30 one-off Python scripts named `patch_*.py` or `fix_*.py`. Current count includes:

```
patch_adamandevecafe.py       patch_emmysquared.py
patch_brickandtin_ingredients.py  patch_emmysquared_allergens.py
patch_kalemecrazy_allergens.py    patch_woodencity.py
patch_woodencity_tags.py          patch_urbancookhouse.py
patch_brickandtin.py              patch_categories_manual.py
patch_cleaneatz_categories.py     patch_eastwest_categories.py
patch_emmy_options.py             patch_high_protein.py
patch_hours_addresses.py          patch_inactive_dishes.py
patch_last_updated.py             patch_menu_urls.py
patch_metadata.py                 patch_rename_dish.py
patch_restaurant_links.py         patch_sohostandard_website.py
patch_sluttyvegan_website.py      patch_d086.py
patch_r015_address.py             fix_header_whitespace.py
fix_shifted_ingredient_rows.py    fix_database_errors.py
```

Each script duplicates the same boilerplate:

```python
KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", ...]
creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
client = gspread.authorize(creds)
ss     = client.open_by_key(SPREADSHEET_ID)
```

The DLD context-loading pattern is also duplicated across at least `patch_adamandevecafe.py`, `patch_emmysquared.py`, and `patch_brickandtin_ingredients.py`. Each reimplements column lookup, context extraction, and row assembly independently. If the column order, tab name, or Spreadsheet ID changes, every script must be updated manually.

### Why this matters

Patch scripts carry no audit trail. There is no record of which scripts have been run, in what order, or what state the sheet was in before they ran. Running a patch script a second time may produce duplicate rows (if not guarded) or silently overwrite values that were correct (if using overwrite logic). There is no standard for whether a patch is idempotent, and no verification step confirms the patch landed.

Some of these scripts will be run only once and never again. Others (allergen patches, metadata patches) are candidates for being run repeatedly as canvassing improves. Without a standard interface, there is no way to distinguish them.

### What this should become

A single `sheets_client.py` module should provide:
- `connect()` → authenticated `Spreadsheet` object
- `get_tab(name)` → worksheet, with loud failure if tab not found
- Standard column-lookup utilities

All scripts that write to the sheet should import from this module. Patch logic (the data to write) should be separated from transport logic (how to write it). Ideally, most patch use cases should be handled by `upsert_dishes.py` with a proper staging file rather than a bespoke script.

---

## Finding 2: `upsert_dishes.py` Uses Delete-and-Reinsert

### What is happening

When `upsert_dishes.py` encounters an existing `Dish_ID`, it:

1. Reads all rows matching that `Dish_ID` across all four tabs
2. Deletes those rows in a batch
3. Appends the new rows from the staging file

This is documented in `upsert_dishes.py`:
> "For existing dishes (matched by Dish_ID): Deletes old rows and writes fresh ones with today's date."

### Why this matters

Delete-and-reinsert is not atomic. If the process is interrupted after the delete but before the reinsert — by a network failure, an API rate limit error, or a script crash — the dish rows are gone. There is no recovery mechanism. The staging file would need to be re-run, but any enrichment that was applied to the old rows after the original upsert (via backfill, patch scripts, or manual canvassing) is also gone.

Additionally, `upsert_dishes.py` has no dry-run mode by default for the delete phase. The `--dry-run` flag exists, but the comments say "Safe to run multiple times — re-running with the same staging.json is a no-op beyond updating the date." This is only true if no enrichment has been applied since the original upsert. In practice, enrichment is applied separately, and a re-run would delete those enrichment values.

### What this should become

A true upsert: compare the staging row values against the existing sheet values field by field; update only the fields that have changed; never delete an existing row unless the dish is being explicitly retired. Enrichment values (Cut_Type, Preparation, Allergen_Flags, etc.) should be preserved by upsert because they are not present in the staging file — the staging file carries canvass data only. The upsert should write to the six canonical columns from staging, and leave the eight enrichment columns untouched.

Until a true upsert is implemented, the delete phase should require an explicit `--overwrite` flag (distinct from `--dry-run`) and should print a count of rows that will be deleted before proceeding.

---

## Finding 3: No Centralized Schema Definition

### What is happening

The 14-column Ingredient Details column order is defined, enforced, or assumed in at least five places:

| Location | Role |
|---|---|
| `upsert_dishes.py` `build_ingredient_rows()` | Produces rows in column order |
| `backfill_enrichment.py` `build_col_map()` | Resolves columns by name for writes |
| `patch_adamandevecafe.py` `new_rows.append([...])` | Hardcodes column order in patch |
| `patch_emmysquared.py` | Same — hardcodes position |
| `fetch_dishes.py` | Reads by column name from `get_all_records()` |

The canonical column order `Restaurant_ID | Restaurant_Name | Location | Dish_ID | Dish_Name | Ingredient | Cut_Type | Preparation | Ingredient_Type | Status | Version | Ingredient_Source | Allergen_Flags | Component_Role` exists only in comments in `upsert_dishes.py` — not as an importable constant.

There is also no schema registry for: valid `Ingredient_Type` values, valid `Component_Role` values, valid `Preparation` values, or valid `Ingredient_Source` values. `backfill_enrichment.py` has a `NON_CANONICAL_TYPES` set as a local constant. `validate_database.py` likely has its own list. These are not shared.

### Why this matters

Adding a column, renaming a column, or reordering columns requires finding and updating every script that touches the sheet. Patch scripts that hardcode column positions will silently write to the wrong column if the sheet is ever restructured. There is currently no script that verifies the sheet header matches the expected schema before performing any operation.

### What this should become

A single `schema.py` module should define:
- `INGREDIENT_DETAILS_COLUMNS: list[str]` — canonical column order
- `ENRICHMENT_FIELDS: frozenset[str]` — which columns are enrichment (not from staging)
- `VALID_INGREDIENT_TYPES: frozenset[str]` — canonical enum
- `VALID_COMPONENT_ROLES: frozenset[str]` — canonical enum
- `VALID_PREPARATION_VALUES: frozenset[str]` — canonical enum
- `VALID_INGREDIENT_SOURCES: frozenset[str]` — canonical enum
- `VALID_ALLERGENS: frozenset[str]` — FDA Big 9 plus `none`, `unknown`

Every script that reads or writes the sheet should import from `schema.py`. The header validation currently in `backfill_enrichment.py` should be a shared utility: `verify_sheet_headers(ws, expected_columns)`.

---

## Finding 4: Staging JSON `source` Field Is Discarded

### What is happening

The staging JSON `source` field carries food ingredient provenance: values like `"grass-fed"`, `"house-made"`, `"KY Farm Fresh"`, `"SIMPLi"`, `"organic"`. This information was collected during canvassing.

`upsert_dishes.py` previously routed this field to `Ingredient_Source` (data collection provenance) — a semantic mismatch documented in `SCHEMA_AUDIT.md`. The fix correctly stopped writing `source` to `Ingredient_Source`. However, the fix also means the `source` field is now read from the staging JSON and immediately discarded:

```python
# The staging JSON "source" field describes ingredient origin (house-made,
# grass-fed, local, etc.) — a different concept that is not stored here.
source = "menu"
```

There is no column in Ingredient Details that corresponds to food ingredient provenance. The canvassing work that produced `"grass-fed"`, `"house-made"`, and named-supplier values is permanently lost on upsert.

### Why this matters

Food provenance — whether an ingredient is locally sourced, organic, house-made, or from a named supplier — is transparency-relevant data. It is the kind of information GoldPan's customers would want to know. The staging files contain this data, and it is being discarded without a destination.

This is an active data loss problem for all future upserts. Past staging data that was upserted before the fix was never stored anywhere in the sheet.

### What this should become

A new `Ingredient_Origin` column should be added to Ingredient Details to capture food provenance. The staging JSON spec should document `source` as the input for this field. `upsert_dishes.py` should write `ing.get("source", "")` to `Ingredient_Origin`. The `SCHEMA_AUDIT.md` `Recommendation` section for the `source` field already calls for this.

Until the column exists, the `source` values in the 22 staging files represent a known backlog of food provenance data that can be recovered when the column is created.

---

## Finding 5: `Allergen_summary` Blocks All Derived Allergen Filter Computation

### What is happening

The `Allergen_summary` field in Goldpan Dish Level Data is a free-text field that combines three distinct concepts in one string (see `SCHEMA_AUDIT.md`):

1. What allergens are present: `"Contains gluten, dairy, eggs"`
2. Where the information came from: `"Allergens sourced from Blue Root's published nutrition document"`
3. Confidence level: `"Contact restaurant to confirm"` or `"Unknown"`

This design means no derived filter can reliably query allergen data. The `compute_derived_filters.py` engine cannot read `Allergen_summary` and determine whether a dish is dairy-free, nut-free, or gluten-free — the field is not queryable.

The current derived filter set (`No Beef Identified`) bypasses this by working from ingredient-level data. But allergen-based filters (`Dairy-Free`, `Gluten-Free`, `Nut-Free`, `Shellfish-Free`, `Soy-Free`) are the highest-value transparency features GoldPan can offer. All of them depend on structured allergen data that does not currently exist as a queryable field.

### Why this matters

GoldPan's primary value proposition is helping people with dietary restrictions find safe options. The current data model cannot support this. Even if every restaurant's allergens were perfectly canvassed into `Allergen_summary`, the engine could not derive `Dairy-Free = True` from a string that reads `"Dairy (parmesan), Wheat (croutons). Caesar dressing may contain eggs. Contact restaurant to confirm."`.

### What this should become

Structured allergen fields as described in `SCHEMA_AUDIT.md`:
- `Allergen_list` — pipe-separated or JSON array of canonical allergen identifiers from the FDA Big 9 list
- `Allergen_source` — `menu`, `pdf`, `restaurant_confirmation`, `inferred`, `unknown`
- `Allergen_confidence` — `confirmed`, `likely`, `unknown`

`Allergen_summary` can remain as a human-readable display field. It must not be used as a data source for derived filter computation. Allergen-based derived filters should be blocked (returning `Unknown`) until `Allergen_list` exists and is populated for a dish.

---

## Finding 6: Two Scoring Schemas in Staging Files

### What is happening

As documented in `SCHEMA_AUDIT.md`, two distinct scoring schemas exist across the 22 staging files:

**Schema A** (475 dishes across most staging files):
`total_score`, `core_clarity`, `prep_clarity`, `sauce_disclosure`, `allergen_transparency`, `transparency_level`

**Schema B** (33 dishes — location TBD):
`transparency_score`, `core_ingredient_score`, `prep_score`, `sauce_score`, `allergen_transparency_score`, `transparency_tier`

`upsert_dishes.py` reads `transparency_level` (Schema A) for the Transparency Scoring tab. Schema B dishes that use `transparency_tier` may not be landing their scores correctly — depending on what `upsert_dishes.py` writes when `transparency_level` is absent.

### Why this matters

If 33 dishes have schema B staging files and `upsert_dishes.py` reads `transparency_level` which doesn't exist in schema B, those dishes land in the Transparency Scoring tab without a score, or with a blank. The Transparency Scoring tab then cannot compute a transparency level for those dishes. This is a silent failure — the upsert completes without error, but the data is wrong.

### What this should become

Identify which restaurant's 33 dishes use Schema B (check staging files for the presence of `transparency_tier`). Normalize those staging files to Schema A. Document the canonical scoring schema in the staging file spec. Add validation to `upsert_dishes.py` that checks for the presence of canonical scoring fields before writing and flags schema B files loudly instead of silently defaulting to blank.

---

## Finding 7: No Staging File JSON Schema Validation

### What is happening

`upsert_dishes.py` validates:
- `menu_verified: true` is present on every dish (hard gate)
- Every ingredient row has the six required context fields (post-build validation)

`upsert_dishes.py` does not validate:
- That `dish_id` values are unique within the staging file
- That `dish_id` format is correct (`D` + digits)
- That `restaurant_id` is consistent across the file
- That ingredient `type` values are from the canonical enum
- That ingredient `role` values are from the canonical enum
- That `preparation` values are from the canonical enum
- That `allergen_flags` values are from the FDA Big 9 list
- That the scoring fields are present and use Schema A naming
- That required dish-level fields (`dish_name`, `dish_id`, `menu_verified`) are all present

Non-canonical values in `type`, `role`, and `preparation` currently flow into the sheet and are later remapped to `Unknown` by `backfill_enrichment.py`. This creates a multi-step correctness dependency: upsert → sheet → backfill → correct values. The canonical values should be enforced at the staging file boundary, not corrected downstream.

### What this should become

A `validate_staging.py` script (or a validation function in `upsert_dishes.py`) that checks every staging file against a declared schema before any write occurs. The validation should exit with a detailed error report if any field contains a non-canonical value. This is analogous to the `menu_verified` gate, extended to all fields. Running `validate_staging.py <file>` should be step zero of any canvass workflow.

---

## Finding 8: `derived_filters.json` Is Not Integrated Into the Application

### What is happening

`compute_derived_filters.py --apply` writes `derived_filters.json` to the goldpan directory. This file contains the computed derived filter results for every active dish: `No Beef Identified`, confidence levels, evidence lists, and reasoning.

`fetch_dishes.py` reads from the sheet and writes `dishes.json`. It does not read `derived_filters.json`. Therefore the derived filter data does not appear in `dishes.json`, and the GitHub Pages application has no access to derived filter results.

### Why this matters

The derived filter pipeline (`derived/engine.py`, `derived/registry.py`, `compute_derived_filters.py`) is fully implemented and producing correct results. But those results are not reaching the application. The pipeline exists in isolation — it does not yet improve the product.

Additionally, the pipeline for updating derived filters is not documented. The sequence is: `backfill_enrichment.py --apply` → `compute_derived_filters.py --apply` → `fetch_dishes.py` → GitHub push. This sequence is not written down anywhere. There is no script or Makefile that runs all four steps in order.

### What this should become

`fetch_dishes.py` should load `derived_filters.json` (if present) and merge derived filter results into each dish's output in `dishes.json`. The merge key is `dish_id`. If no derived filter result exists for a dish, the dish entry should include an empty `derived_filters: {}` object rather than no key.

The full update sequence should be documented in a `PIPELINE.md` or a `Makefile`:
```
backfill → compute → fetch → push
```

---

## Finding 9: Patch Scripts Use `if col_idx is not None` Guards

### What is happening

Several patch scripts use a column-lookup pattern that fails silently if a column is missing:

```python
def dl_col(name):
    try:
        return dl_headers.index(name)
    except ValueError:
        return None

dl_did_col = dl_col("Dish_ID")
# Later:
if dl_did_col is not None and len(row) > dl_did_col:
    did = row[dl_did_col]
```

If `"Dish_ID"` is not found in the headers, `dl_col("Dish_ID")` returns `None`, and every subsequent read of that column returns an empty string. The script continues and processes zero dishes because no `did` ever matches `INGREDIENT_PATCHES`. There is no error, no warning, and no report of why nothing happened.

This was identified in `BACKFILL_RELIABILITY_REPORT.md` as a pattern that was eliminated from `backfill_enrichment.py`. It persists in the patch scripts.

### What this should become

All column lookups should use the loud-failure pattern established in `backfill_enrichment.py`:
```python
if name not in headers:
    raise ValueError(f"Column '{name}' not found in sheet headers: {headers}")
return headers.index(name)
```

If a shared `schema.py` module exists (Finding 3), the column-validation utility should live there and be imported by all scripts.

---

## Finding 10: No Staging File Registry or Naming Convention

### What is happening

There are 22 staging JSON files in the goldpan directory:

```
staging.json
staging_blueroot.json
staging_blueroot_addendum.json
staging_elis.json
staging_yomamas.json
staging_woodencity.json
staging_battery.json
staging_rr_ingredients.json
staging_cayococo.json
staging_eastwest.json
staging_bahaburger.json
staging_frothymonkey.json
staging_abhieatery.json
staging_chopnfresh.json
staging_wasabijuans.json
staging_urbancookhouse.json
staging_emmysquared_pizzas.json
staging_chopt.json
staging_cleaneatz.json
staging_sohosocial.json
staging_sluttyvegan.json
staging_essential_dinner_backup.json
```

There is no registry of which staging files have been upserted, when they were upserted, or what version of the dish data they represent. `staging.json` (no restaurant suffix) is ambiguous — it is not clear which restaurant or canvass event it represents. `staging_essential_dinner_backup.json` suggests a backup was made at some point, but there is no record of what changed.

If a staging file is modified and re-upserted, the delete-and-reinsert behavior (Finding 2) means previous enrichment is silently lost. There is no way to know whether re-upsert is safe for any given file.

### What this should become

A staging file manifest (`staging_manifest.json` or a tab in the sheet) tracking: filename, restaurant_id, upsert date, dish count, and status (`pending`, `upserted`, `archived`). Staging files that have been upserted should be treated as read-only archives — modifications should produce a new file, not mutate the existing one. This makes the staging layer an immutable log of canvassing events, not a mutable working file.

---

## Priority Order

These findings are listed in priority order for resolution:

**Do now (blocking reliability or causing data loss):**
1. Finding 9: Silent column drops in patch scripts — easy fix, copy the loud-failure pattern
2. Finding 3: Centralized schema module — creates foundation for all other fixes
3. Finding 2: Upsert delete-reinsert risk — add `--overwrite` gate before delete phase

**Do next (blocking derived filter value):**
4. Finding 5: Structured allergen fields — prerequisite for all allergen-based filters
5. Finding 8: Integrate `derived_filters.json` into `fetch_dishes.py` and `dishes.json`
6. Finding 4: Add `Ingredient_Origin` column — recovers canvassed food provenance data

**Do before next restaurant onboarding:**
7. Finding 7: Staging file schema validation — enforces canonical values at the entry point
8. Finding 6: Normalize scoring schemas — audit the 33 Schema B dishes and fix

**Ongoing hygiene:**
9. Finding 1: Patch script consolidation — reduce patch scripts as use cases are absorbed by upsert
10. Finding 10: Staging file registry — add manifest before the next canvass event

---

## What a Healthy Pipeline Looks Like

When these findings are resolved, the GoldPan pipeline should operate as follows:

1. **Canvasser produces a staging file** → `validate_staging.py` checks it against the declared schema and exits with errors on any violation.
2. **`upsert_dishes.py <file>`** → dry-run shows what would change, preserves enrichment columns, never deletes without `--overwrite`.
3. **`backfill_enrichment.py --apply`** → fills enrichment fields from verified sources, verifies expected values were written (Level 1 + Level 2).
4. **`compute_derived_filters.py --apply`** → computes all derived filters, writes `derived_filters.json`.
5. **`fetch_dishes.py`** → reads sheet + `derived_filters.json`, writes `dishes.json` and `restaurants.json`.
6. **GitHub push** → application reflects the current verified state of the database.

Every step produces a self-documenting report. No step reports success without verification. No human inspection is required to confirm a step completed correctly.

---

## Cleanup Log

### D111 — Brisket Panini (Brick & Tin) — duplicate ingredient rows

**Detected:** 2026-06-29 during derived filter dry-run output  
**Issue:** Two ingredient rows with slightly different names for the same ingredient:
- `"certified angus braised beef brisket"`
- `"certified angus beef braised beef brisket"`

**Current impact:** Low — both rows correctly trigger Not Applicable (beef present). Conclusion is correct; data is redundant.  
**Required action:** Dedup — keep the more accurate name, delete the duplicate row. Use `dedup_ingredients.py` or a targeted patch.  
**Blocks:** Nothing currently. Does not affect derived filter correctness.
