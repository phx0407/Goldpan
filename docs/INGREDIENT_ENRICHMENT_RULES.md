# Ingredient Details — Data Enrichment Quality Rules

**Status:** Active policy  
**Last updated:** 2026-06-28

---

## Principle: Verified Richness, Not Artificial Completeness

GoldPan prioritizes verified data richness over completeness. **Blank is not a
valid post-review state.** After a row has been processed, every enrichment
field must contain a verified value, `None`, `Unknown`, or `N/A`.

Blank means the row has not been processed yet. It is a completeness gap, not
an acceptable final state.

**Do not infer values just to fill the database.**

---

## Standing Enrichment Backfill Rule

This rule applies both going forward and retroactively:

**When an Ingredient Details row has blank enrichment fields, the system
should safely backfill them whenever a verified source or approved default
supports the value.**

This applies in two modes:

1. **Going forward** — when new rows are written via `upsert_dishes.py` or
   patch scripts, enrichment fields should be populated from staging file data
   before the row is written. Rows should not enter the database blank if
   staging data is available.

2. **Retroactively** — legacy rows with blank enrichment fields should be
   migrated via `backfill_enrichment.py`. Always run a dry-run first, review
   the report, then apply.

Backfill rules (standing):

| Rule | Behavior |
|---|---|
| Do not overwrite existing verified values | Never touch a field that already has content |
| Do not infer just to fill a field | No guessing, no deriving from ingredient name or context |
| Only populate blank fields | Skip any field that already has a value |
| Reviewed but not determinable → `Unknown` | Source was examined; value cannot be confirmed |
| Verified no value applies → `None` | Explicit result: not applicable or no flag present |
| Field does not apply → `N/A` | Field is structurally irrelevant to this ingredient |
| Not yet reviewed → leave blank | Report it as incomplete; do not preemptively set Unknown |
| Always produce a dry-run report before writing | No writes without a review step |
| After applying, rerun `analyze_enrichment.py` + `validate_database.py` | Confirm richness improved and no new errors |

---

## Enrichment Field Value Semantics

After a row has been reviewed, each enrichment field must contain one of the
following four states:

| Value | Meaning |
|---|---|
| *(blank)* | **Unprocessed.** Row has not been reviewed. This is a completeness gap. |
| `None` | Reviewed. No value applies or no allergen/flag is present for this ingredient. |
| `Unknown` | Reviewed. Available sources were checked but the value could not be determined. |
| `N/A` | Reviewed. This field does not apply to this ingredient. |
| *(any other value)* | Reviewed. A source-backed verified value. |

**Never leave a field blank after reviewing the ingredient.** The choice between
`None`, `Unknown`, and `N/A` is a deliberate act that records what you found
(or didn't find) when you looked.

---

## Required Integrity Fields (blocking — must always be populated)

These fields must be present in every Ingredient Details row. Missing values
are database errors that block pipeline progression.

| Field | Source |
|---|---|
| Restaurant_ID | Goldpan Dish Level Data |
| Restaurant_Name | Goldpan Dish Level Data |
| Location | Goldpan Dish Level Data |
| Dish_ID | Canonical ID from upsert pipeline |
| Dish_Name | Goldpan Dish Level Data |
| Ingredient | Live menu, PDF, or restaurant confirmation |

---

## Optional Enrichment Fields (non-blocking — fill only from verified sources)

These fields must be populated after review. The correct reviewed state depends
on what the source reveals — never guess.

| Field | Fill from | If source doesn't support it |
|---|---|---|
| Cut_Type | Live menu or PDF, only if explicitly stated | `Unknown` if reviewed; `N/A` if not applicable |
| Preparation | Live menu or PDF, only if explicitly stated | `Unknown` if reviewed; `N/A` if not applicable |
| Ingredient_Type | Live menu + ingredient name, only if unambiguous | `Unknown` if reviewed |
| Status | Confirmed from parent dish status | `Active` if parent dish is Active |
| Version | Schema versioning | `1` (safe default after first review) |
| Ingredient_Source | How the ingredient data was collected | `Unknown` if provenance not recorded |
| Allergen_Flags | Official allergen PDF or restaurant confirmation only | `Unknown` until an allergen source is reviewed |
| Component_Role | Live menu structure, only if clearly identified | `N/A` if not a sauce/base/topping/etc.; `Unknown` if unclear |

---

## Verified Source Hierarchy

In descending order of reliability:

1. **Restaurant confirmation** — direct from restaurant staff or official documentation
2. **Official allergen/nutrition PDF** — linked from restaurant website
3. **Live menu** — current, verified from the restaurant's own website or in-person
4. **Restaurant website** — secondary to live menu; use for context only

The following are NOT valid enrichment sources:

- General knowledge about an ingredient category
- Inference from ingredient name or dish description
- Data from third-party aggregators (Yelp, DoorDash, etc.)
- Assumption that a common ingredient "probably" has a certain property

---

## Allergen Flags — Special Rules

Allergen transparency is a safety-critical field.

- **Blank ≠ no allergens.** Blank means the row has not been processed.
- `None` = reviewed an official allergen source; no allergens identified for this ingredient.
- `Unknown` = no official allergen source available; allergen status not determined.
- Only promote from `Unknown` to `None` after completing an allergen review.
- Never set `None` without reviewing an official allergen source (PDF, allergen statement, or direct confirmation).

---

## Ingredient_Source Values

| Value | When to use |
|---|---|
| `menu` | Data came from live restaurant menu |
| `pdf` | Data came from official PDF (menu or nutrition/allergen doc) |
| `website` | Data came from restaurant website content |
| `restaurant_confirmation` | Restaurant confirmed directly |
| `Unknown` | Provenance not recorded; data exists but source unclear |
| *(blank)* | Row not yet processed |

---

## None vs. Unknown vs. N/A — Quick Reference

| Situation | Correct value |
|---|---|
| Reviewed allergen PDF — ingredient has no allergens | `None` |
| No allergen PDF available — can't determine allergens | `Unknown` |
| Cut_Type — ingredient is a spice with no applicable cut | `N/A` |
| Cut_Type — ingredient is a protein; live menu reviewed but cut not stated | `Unknown` |
| Component_Role — ingredient is a sauce; confirmed from menu structure | *(the role, e.g. "sauce")* |
| Component_Role — plain ingredient; not a component | `N/A` |
| Preparation — reviewed menu; preparation method not stated | `Unknown` |

---

## Validation Behavior

**validate_database.py** distinguishes three categories:

1. **Blocking errors** — missing required integrity fields (Restaurant_ID → Ingredient).
   These prevent pipeline progression.

2. **Non-blocking enrichment gaps** — blank enrichment fields on unprocessed rows.
   Reported as completeness metrics. Not blocking. Rows with `None`, `Unknown`,
   or `N/A` are considered reviewed and do not appear as gaps.

3. **Warnings** — business rule violations (e.g., Slutty Vegan = Needs Review).

Run `python3 analyze_enrichment.py` for the full Data Richness Report.

---

## Scripts

| Script | Purpose |
|---|---|
| `analyze_enrichment.py` | Read-only Data Richness Report — shows blank gaps, field distribution, unresolved counts |
| `backfill_enrichment.py` | Safe enrichment migration — fills blank fields from staging/DLD, dry-run by default |

Run `backfill_enrichment.py` before `analyze_enrichment.py` when migrating legacy rows.
Always run `validate_database.py` after any backfill.

## Data Richness Report

Run `python3 analyze_enrichment.py` to produce a richness audit including:

- How many rows are fully processed (no blank enrichment fields)
- How many rows are unprocessed or partially processed (have blank fields)
- Which restaurants and dishes have the most unprocessed rows
- Which fields have the most gaps
- Which gaps need source documents vs. which have safe defaults

Output: `enrichment_report.json` + stdout summary.

---

## What NOT to Do

- Do not leave enrichment fields blank after reviewing an ingredient
- Do not set `Ingredient_Type` based on general knowledge — only from a verified source
- Do not set `Allergen_Flags = None` without reviewing an official allergen source
- Do not set `Component_Role` based on where an ingredient appears in a dish name
- Do not set `Ingredient_Source = menu` unless you actually pulled from the live menu
- Do not treat a fully-populated row as better than a partially-populated row
  if the extra fields were not sourced

**The goal is verified richness. Blank means unprocessed — resolve it, don't ignore it.**
