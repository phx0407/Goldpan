# Backfill Reliability Report

**Date:** 2026-06-28  
**Scope:** All scripts that write to Google Sheets or produce output files used downstream  
**Trigger:** Backfill runs appeared to complete successfully but Google Sheets data was not changing, causing `compute_derived_filters.py` to show identical results across multiple runs.

---

## Summary of Findings

| # | Finding | Severity |
|---|---|---|
| 1 | `backfill_enrichment.py` runs dry-run by default — requires `--apply` | ⚠️ Easy to miss |
| 2 | Post-apply verification checks for blank fields, not for whether the write actually landed | 🔴 Reliability gap |
| 3 | "0 writes planned" dry-run report is misleading — it means fields are non-blank, not that they're correct | 🔴 Root cause of confusion |
| 4 | `upsert_dishes.py` was writing food ingredient origin ("house", "grass-fed") into `Ingredient_Source`, making it non-blank with a wrong value | 🔴 Silent data corruption |
| 5 | Backfill's "never overwrite" rule treated wrong-value-non-blank the same as correct-value-non-blank | 🔴 Blocked all fixes |
| 6 | No script currently reads the sheet back and confirms specific expected values were written | 🔴 No true write verification |
| 7 | `compute_derived_filters.py` reads live from Google Sheets — no cache or staleness issue | ✅ Not the cause |
| 8 | `batch_update` in gspread is synchronous — if no exception is raised, the write was accepted | ✅ Not the cause |
| 9 | All scripts target the correct sheet/tab/range when they run | ✅ Not the cause |

---

## 1. Which commands write to Google Sheets?

| Script | Writes to Sheets? | Condition |
|---|---|---|
| `backfill_enrichment.py` | Yes | Only with `--apply` flag |
| `upsert_dishes.py` | Yes | Always (no dry-run mode) |
| `patch_adamandevecafe.py` | Yes | Always |
| `patch_emmysquared.py` | Yes | Always |
| `patch_brickandtin_ingredients.py` | Yes | Always |
| `fetch_dishes.py` | No | Read-only |
| `compute_derived_filters.py` | No (writes local JSON only) | — |
| `analyze_enrichment.py` | No | Read-only |
| `validate_database.py` | No | Read-only |

---

## 2. Which commands are dry-run by default?

Only `backfill_enrichment.py`. It is dry-run by default. Every other script that connects to Sheets writes immediately, with no confirmation prompt.

`compute_derived_filters.py` is dry-run by default for its own output (`derived_filters.json`), but it never writes to Sheets regardless.

---

## 3. Which commands require `--apply`?

Only `backfill_enrichment.py`:
```bash
python3 backfill_enrichment.py           # dry run — reads sheet, produces report, no writes
python3 backfill_enrichment.py --apply   # reads sheet, writes fills, re-reads for verification
```

The dry-run report header clearly states `DRY RUN — no writes`, but this is easy to miss when running commands quickly.

---

## 4. Commands that complete successfully without making changes

**`backfill_enrichment.py` (dry run)** — always completes without writes. Reports "0 cells would be written" when all fields are non-blank, even if those fields contain wrong values (see Finding #3 below).

**`backfill_enrichment.py --apply` with 0 updates** — prints "Nothing to write — all resolvable fields are already populated." This is not the same as "all fields are correct." It means no blank fields were found.

---

## 5. Root Cause: Why "0 writes planned" Was Misleading

### The actual problem

`upsert_dishes.py` writes `Ingredient_Source` using this line:
```python
source = ing.get("source", "unknown")
```

The `source` field in staging JSON files describes **food ingredient origin** ("house", "grass-fed", "organic", "unknown"), not **data collection provenance** (menu, pdf, website). For the vast majority of ingredients, `"source": "unknown"` in the staging JSON means the canvasser didn't know whether the ingredient was house-made or sourced from a supplier — not that GoldPan doesn't know where the menu data came from.

This write produced `Ingredient_Source = "unknown"` in the sheet for ~2,481 ingredients across ~511 dishes.

### Why backfill couldn't fix it

`backfill_enrichment.py` has the rule: **never overwrite an existing value.**

```python
if existing:
    continue  # never overwrite
```

Since `Ingredient_Source = "unknown"` is non-blank, the backfill skipped it. The dry-run reported "0 writes planned" — which looked like success. It wasn't. The fields were populated with a wrong value the backfill refused to touch.

### Why this wasn't caught earlier

The `compute_derived_filters.py` engine checks:
```python
VERIFIED_SOURCES = {"menu", "pdf", "website", "restaurant_confirmation"}
```

`"unknown"` is not in this set → dependency check fails → 673 dishes returned Unknown. The engine was correct. The data was wrong.

---

## 6. Column/Header Lookup Failures

**Current state: none.** `backfill_enrichment.py` validates all columns at startup with an explicit check that exits loudly if any column is missing:

```python
if missing_cols:
    print(f"  ERROR: the following columns were NOT found...")
    return   # ← exits before writing anything
```

This was added in the rewrite. Silent column drops (old `if col_idx is not None:` guard) have been eliminated.

**One latent risk:** The post-apply verification parses A1 notation cell addresses to extract row numbers:
```python
row_num = int("".join(c for c in addr if c.isdigit()))
```
This works for rows 1–9 but would misparse addresses like `K1234` (extracts `1234` correctly) or `AA12` (extracts `12` correctly). However, it would fail for columns beyond Z where the address contains letters embedded in the number, like `AB12` → extracts `12` ✓. This parsing is technically fragile but works for the current sheet size.

---

## 7. Whether Google Sheets API Writes Are Delayed or Failing Silently

`gspread.batch_update()` is synchronous. It sends an HTTP request and waits for the response. If the call returns without raising an exception, the write was accepted by the API.

The script prints per-chunk progress:
```
APPLYING 1234 cell updates...
  500 / 1234 cells written
  1000 / 1234 cells written
  1234 / 1234 cells written
```

If the API rejected a write, `batch_update` would raise an exception, not silently continue. **The API is not the reliability gap.**

**However:** The current post-apply verification does not confirm that specific expected values now appear in the sheet. It re-reads the sheet and checks for blank enrichment fields — but a wrong non-blank value passes that check. This is the verification gap (see Finding #2).

---

## 8. Whether Validation Reads Fresh or Stale Data

`compute_derived_filters.py`, `analyze_enrichment.py`, and `validate_database.py` all call `ws.get_all_values()` or `ws.get_all_records()` on a freshly connected sheet object. There is no local cache or file-based intermediary.

**No staleness issue.** If the script reads the same data across multiple runs, it means the sheet hasn't changed between runs — not that the script is reading a cache.

---

## 9. Local JSON vs. Sheet Mismatch

`derived_filters.json` is written by `compute_derived_filters.py --apply`. It is derived output — computed from what the sheet contains at run time. If the sheet hasn't changed, the JSON won't change either.

`dishes.json` and `restaurants.json` are written by `fetch_dishes.py`. They reflect the sheet state at the time `fetch_dishes.py` last ran.

No local file is authoritative for sheet state. The sheet is always the source of truth. Scripts that read the sheet get live data.

---

## 10. Whether the Report Proves the Write Happened

**Currently: no.**

The post-apply verification in `backfill_enrichment.py`:
- Re-reads the sheet ✓
- Checks for blank enrichment fields ✓
- Reports FAIL if any processed row has a blank field ✓

**What it does NOT do:**
- Confirm that specific cells now contain the expected values
- Detect wrong-value-non-blank (e.g., `Ingredient_Source = "unknown"` when it should be `"menu"`)
- Report how many cells changed vs. how many stayed the same

A write verification that proves the write happened must:
1. Record the before state for targeted cells
2. Write
3. Re-read those specific cells
4. Confirm each expected value is now present
5. Report FAIL if any written cell does not match

---

## Fixes Applied This Session

### Fix 1: `upsert_dishes.py` — wrong field written to `Ingredient_Source`

**Before:**
```python
source = ing.get("source", "unknown")
```

**After:**
```python
source = "menu"   # staging pipeline requires menu_verified: true
# The staging JSON "source" field describes ingredient origin (house-made,
# grass-fed, local, etc.) — a different concept that is not stored here.
```

**Effect:** All future upserts write correct data collection provenance to `Ingredient_Source`.

### Fix 2: `backfill_enrichment.py` — allow upgrade of placeholder "unknown"

Added a targeted exception to the "never overwrite" rule, specifically for `Ingredient_Source = "unknown"` written by the old upsert script:

```python
if field == "Ingredient_Source" and existing.lower() == "unknown":
    if dish_id in dish_in_staging or dish_id in CANVASSED_DISHES:
        pass  # fall through to resolve() — allow upgrade
    else:
        continue
```

**Justification:** `"unknown"` in `Ingredient_Source` from old upsert runs is a script default (food provenance field misread as data provenance). It is not a reviewed conclusion. When a staging file or canvass record provides a confirmed source, upgrading is safe and correct.

---

## Required: Post-Write Verification Upgrade

The current verification checks for blanks. It needs to also check that upgraded fields now contain expected values.

**Minimum verification a write script must produce:**

```
POST-WRITE VERIFICATION
  Cells targeted:   1,234
  Cells confirmed:  1,234   ← re-read and matched expected value
  Cells mismatched:     0   ← expected X, found Y
  Cells still blank:    0   ← targeted but empty after write
  Result: PASS / FAIL
```

This is not yet implemented. Until it is, run the following after `--apply` to manually confirm:

```bash
python3 backfill_enrichment.py           # should now report 0 fills (all upgraded)
python3 compute_derived_filters.py       # Computed count should jump from 15 to ~535
```

If `compute_derived_filters.py` still shows 15 Computed after backfill `--apply`, the writes did not land and the API call should be inspected for exceptions.

---

## Recommended Next Steps

1. Run `python3 backfill_enrichment.py` (dry run) — confirm it now plans to upgrade `Ingredient_Source` from "unknown" to "menu" for staging dishes. The report should show fills in Section [1].

2. Run `python3 backfill_enrichment.py --apply` — confirm "X cells written" appears in output.

3. Run `python3 compute_derived_filters.py` — confirm Computed jumps from 15 to ~535. This is the functional proof that writes landed.

4. Upgrade the post-write verification to check expected values, not just blanks. Until then, step 3 is the reliable confirmation.
