"""
fix_shifted_ingredient_rows.py

Detects and corrects column-shifted rows in the Ingredient Details tab.

ROOT CAUSE
----------
The legacy add_dishes.py wrote ingredient rows as only 2 values:
    [dish_id, ingredient_name]

With the current 14-column schema, those 2 values landed in columns A and B:
    A (Restaurant_ID) ← dish_id    e.g. "D064"
    B (Restaurant_Name) ← ingredient  e.g. "avocado spread"
    C–N: all blank

This means Dish_ID (col D) and Ingredient (col F) are empty, and the data
is sitting in the wrong columns. This script moves it to the right place,
backfills the missing context from Goldpan Dish Level Data, and clears the
wrong cells.

DETECTION CRITERIA (all three must be true)
-------------------------------------------
  1. Restaurant_ID matches ^D\\d+$ (looks like a Dish_ID, not R001 etc.)
  2. Dish_ID column is blank
  3. Ingredient column is blank

CORRECTION
----------
  1. Extract dish_id from Restaurant_ID column
  2. Extract ingredient from Restaurant_Name column
  3. Look up Restaurant_ID, Restaurant_Name, Location, Dish_Name from Dish Level Data
  4. Write a fully corrected row:
       Restaurant_ID, Restaurant_Name, Location, Dish_ID, Dish_Name,
       Ingredient, [preserve existing Cut_Type, Preparation, etc. or blank]
  5. Clear the wrong cells (Restaurant_ID and Restaurant_Name get overwritten with real values)

SAFETY
------
  - Does not modify rows that already have correct structure
  - Does not guess if Dish_ID cannot be matched in Dish Level Data
  - DRY RUN by default — pass --apply to write changes

Usage:
  python3 fix_shifted_ingredient_rows.py            # dry run — report only
  python3 fix_shifted_ingredient_rows.py --apply    # apply corrections
"""

import re
import sys
import datetime
import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TODAY          = datetime.date.today().strftime("%Y-%m-%d")
APPLY          = "--apply" in sys.argv

DISH_ID_RE = re.compile(r"^D\d+$")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Canonical Ingredient Details column order (confirmed from live sheet)
CANONICAL_COLS = [
    "Restaurant_ID", "Restaurant_Name", "Location", "Dish_ID", "Dish_Name",
    "Ingredient", "Cut_Type", "Preparation", "Ingredient_Type", "Status",
    "Version", "Ingredient_Source", "Allergen_Flags", "Component_Role",
]


def col_idx(headers, name):
    try:
        return headers.index(name)
    except ValueError:
        return None


def cell(row, idx):
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip()


def build_dish_lookup(dl_ws):
    """
    Build {dish_id: {Restaurant_ID, Restaurant_Name, Location, Dish_Name}}
    from Goldpan Dish Level Data. Uses header-name mapping.
    """
    all_values = dl_ws.get_all_values()
    if not all_values:
        return {}
    headers = [h.strip() for h in all_values[0]]

    rid_col   = col_idx(headers, "Restaurant_ID")
    rname_col = col_idx(headers, "Restaurant")          # Dish Level Data uses "Restaurant"
    if rname_col is None:
        rname_col = col_idx(headers, "Restaurant_Name")
    loc_col   = col_idx(headers, "Location")
    did_col   = col_idx(headers, "Dish_ID")
    dname_col = col_idx(headers, "Dish_Name")

    lookup = {}
    for row in all_values[1:]:
        did = cell(row, did_col)
        if not did:
            continue
        lookup[did] = {
            "Restaurant_ID":   cell(row, rid_col),
            "Restaurant_Name": cell(row, rname_col),
            "Location":        cell(row, loc_col),
            "Dish_Name":       cell(row, dname_col),
        }
    return lookup


def main():
    print(f"fix_shifted_ingredient_rows.py  —  {TODAY}")
    if APPLY:
        print("MODE: APPLY — changes will be written to the sheet")
    else:
        print("MODE: DRY RUN — no changes will be written")
        print("      Run with --apply to apply corrections.\n")

    print("\nConnecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    # ── Read Ingredient Details ─────────────────────────────────────────────────
    print("Reading Ingredient Details...")
    ing_ws     = ss.worksheet("Ingredient Details")
    all_values = ing_ws.get_all_values()

    if len(all_values) < 2:
        print("Ingredient Details is empty or header-only. Nothing to fix.")
        return

    raw_headers = all_values[0]
    headers     = [h.strip() for h in raw_headers]

    # Verify we have the expected columns
    for col in ["Restaurant_ID", "Restaurant_Name", "Dish_ID", "Ingredient"]:
        if col not in headers:
            print(f"ERROR: Column '{col}' not found in Ingredient Details headers.")
            print(f"Actual headers: {headers}")
            sys.exit(1)

    rid_col   = col_idx(headers, "Restaurant_ID")
    rname_col = col_idx(headers, "Restaurant_Name")
    loc_col   = col_idx(headers, "Location")
    did_col   = col_idx(headers, "Dish_ID")
    dname_col = col_idx(headers, "Dish_Name")
    ing_col   = col_idx(headers, "Ingredient")

    # ── Read Dish Level Data for backfill ────────────────────────────────────
    print("Reading Goldpan Dish Level Data for backfill lookup...")
    dl_ws       = ss.worksheet("Goldpan Dish Level Data")
    dish_lookup = build_dish_lookup(dl_ws)
    print(f"  Loaded {len(dish_lookup)} dishes.\n")

    # ── Detect shifted rows ──────────────────────────────────────────────────
    shifted     = []   # (sheet_row, dish_id_found, ingredient_found, lookup_data_or_None)
    unmatched   = []   # rows where Dish_ID not in Dish Level Data
    correct     = 0
    skipped     = 0

    for i, row in enumerate(all_values[1:], start=2):
        rid_val  = cell(row, rid_col)
        rname_val = cell(row, rname_col)
        did_val  = cell(row, did_col)
        ing_val  = cell(row, ing_col)

        # Detection: Restaurant_ID looks like a Dish_ID, Dish_ID blank, Ingredient blank
        if DISH_ID_RE.match(rid_val) and not did_val and not ing_val:
            dish_id    = rid_val
            ingredient = rname_val  # ingredient landed here

            if not ingredient:
                # Shifted but no ingredient value either — flag as unusual
                unmatched.append({
                    "row":       i,
                    "dish_id":   dish_id,
                    "ingredient": "(no ingredient value found in Restaurant_Name)",
                    "reason":    "Shifted row but Restaurant_Name is also blank",
                })
                continue

            lookup = dish_lookup.get(dish_id)
            if lookup:
                shifted.append({
                    "row":        i,
                    "dish_id":    dish_id,
                    "ingredient": ingredient,
                    "lookup":     lookup,
                })
            else:
                unmatched.append({
                    "row":        i,
                    "dish_id":    dish_id,
                    "ingredient": ingredient,
                    "reason":     f"Dish_ID {dish_id} not found in Goldpan Dish Level Data",
                })
        else:
            skipped += 1

    # ── Print detection report ────────────────────────────────────────────────
    print("=" * 65)
    print("DETECTION RULE")
    print("=" * 65)
    print("  A row is classified as SHIFTED when ALL of the following are true:")
    print("  1. Restaurant_ID matches ^D\\d+$ (looks like a Dish_ID, e.g. D064)")
    print("  2. Dish_ID column is blank")
    print("  3. Ingredient column is blank")
    print("  These three together mean data was written to the wrong columns.")
    print("  Restaurant_Name is assumed to contain the ingredient value.")
    print()

    print("=" * 65)
    print("DRY RUN REPORT")
    print("=" * 65)
    print(f"  Total rows scanned          : {len(all_values) - 1}")
    print(f"  Normal rows (no action)     : {skipped}")
    print(f"  Shifted rows — correctable  : {len(shifted)}")
    print(f"  Shifted rows — unmatched    : {len(unmatched)}")
    print()

    if not shifted and not unmatched:
        print("  ✓ No shifted rows found. Sheet structure is correct.")
        return

    # ── Sample before/after (first 3 correctable rows) ───────────────────────
    if shifted:
        print("=" * 65)
        print(f"SAMPLE BEFORE / AFTER  (first {min(3, len(shifted))} of {len(shifted)} correctable rows)")
        print("=" * 65)
        for r in shifted[:3]:
            ctx = r["lookup"]
            print(f"\n  Row {r['row']}:")
            print(f"  BEFORE:")
            print(f"    Restaurant_ID  : {r['dish_id']!r:30}  ← Dish_ID sitting here (wrong)")
            print(f"    Restaurant_Name: {r['ingredient']!r:30}  ← ingredient sitting here (wrong)")
            print(f"    Location       : {'':30}  (blank)")
            print(f"    Dish_ID        : {'':30}  (blank — should have Dish_ID)")
            print(f"    Dish_Name      : {'':30}  (blank)")
            print(f"    Ingredient     : {'':30}  (blank — should have ingredient)")
            print(f"  AFTER:")
            print(f"    Restaurant_ID  : {ctx['Restaurant_ID']!r:30}  ← backfilled from Dish Level Data")
            print(f"    Restaurant_Name: {ctx['Restaurant_Name']!r:30}  ← backfilled from Dish Level Data")
            print(f"    Location       : {ctx['Location']!r:30}  ← backfilled from Dish Level Data")
            print(f"    Dish_ID        : {r['dish_id']!r:30}  ← moved from Restaurant_ID")
            print(f"    Dish_Name      : {ctx['Dish_Name']!r:30}  ← backfilled from Dish Level Data")
            print(f"    Ingredient     : {r['ingredient']!r:30}  ← moved from Restaurant_Name")
        print()

    if unmatched:
        print("=" * 65)
        print(f"UNMATCHED — CANNOT CORRECT ({len(unmatched)} rows)")
        print("  Dish_ID found in the shifted row but not in Goldpan Dish Level Data.")
        print("  These rows will NOT be touched. Manual review required.")
        print("=" * 65)
        for r in unmatched:
            print(f"  Row {r['row']:>4} | {r['dish_id']:<8} | {r.get('ingredient', '')[:40]:<40}")
            print(f"          Reason: {r['reason']}")
        print()

    # ── Apply corrections ─────────────────────────────────────────────────────
    if not APPLY:
        print("─" * 65)
        print(f"  DRY RUN complete — no changes written.")
        print(f"  {len(shifted)} rows would be corrected.")
        print(f"  {len(unmatched)} rows cannot be corrected automatically.")
        print(f"  Confirm the sample above looks correct, then run:")
        print(f"    python3 fix_shifted_ingredient_rows.py --apply")
        print("─" * 65)
        return

    print(f"Applying {len(shifted)} corrections...")

    # Build batch updates — one per cell that needs to change
    updates = []

    def q(row_num, col_num, value):
        """Queue a cell update."""
        updates.append({
            "range":  gspread.utils.rowcol_to_a1(row_num, col_num + 1),  # 1-indexed
            "values": [[value]],
        })

    for r in shifted:
        row_num    = r["row"]
        dish_id    = r["dish_id"]
        ingredient = r["ingredient"]
        ctx        = r["lookup"]

        # Write correct values into correct columns
        q(row_num, rid_col,   ctx["Restaurant_ID"])    # A: Restaurant_ID (was Dish_ID)
        q(row_num, rname_col, ctx["Restaurant_Name"])  # B: Restaurant_Name (was ingredient)
        q(row_num, loc_col,   ctx["Location"])         # C: Location (was blank)
        q(row_num, did_col,   dish_id)                 # D: Dish_ID (was blank)
        q(row_num, dname_col, ctx["Dish_Name"])        # E: Dish_Name (was blank)
        q(row_num, ing_col,   ingredient)              # F: Ingredient (was blank)
        # G–N: Cut_Type, Preparation, Ingredient_Type, Status, Version,
        #       Ingredient_Source, Allergen_Flags, Component_Role
        # Leave as-is — they were blank in shifted rows, which is acceptable.
        # Status defaults to blank (not "Active") until a full upsert runs.

    # Send in batches of 500 to avoid API limits
    BATCH = 500
    for start in range(0, len(updates), BATCH):
        batch = updates[start:start + BATCH]
        ing_ws.batch_update(batch)
        print(f"  Wrote cells {start + 1}–{start + len(batch)}")

    print(f"\n✓ Corrected {len(shifted)} shifted rows.")

    if unmatched:
        print(f"\n⚠ {len(unmatched)} rows could not be corrected automatically:")
        for r in unmatched:
            print(f"  Row {r['row']} | {r['dish_id']} | {r.get('ingredient', '')} | {r['reason']}")
        print("  These rows require manual review before they can be included in the database.")

    print(f"\nNext steps:")
    print(f"  python3 backfill_ingredient_details.py  # fill any remaining sparse rows")
    print(f"  python3 validate_database.py            # confirm PASS")


if __name__ == "__main__":
    main()
