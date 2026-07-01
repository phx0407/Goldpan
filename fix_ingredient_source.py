"""
fix_ingredient_source.py — CL-001 Phase 2: Correct non-canonical Ingredient_Source values.

Targets 28 dishes confirmed safe by staging file provenance:
  - Eli's Jerusalem Grill (14 dishes, staging_elis.json)
  - The Essential (14 dishes, staging_essential_dinner_backup.json)

For every ingredient row in Ingredient Details where Dish_ID is in the safe set
AND Ingredient_Source is a non-canonical category value (plant-based, dairy, animal,
animal-based, seafood, house, neutral, organic, grass-fed), sets Ingredient_Source = "menu".

Safety guarantee: Only these 28 Dish_IDs are touched. All other rows are untouched.

Usage:
    python3 fix_ingredient_source.py          # dry run — show what would change
    python3 fix_ingredient_source.py --apply  # write to sheet
"""

import datetime
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

# ── Config ─────────────────────────────────────────────────────────────────────

GOLDPAN_DIR    = os.path.dirname(os.path.abspath(__file__))
KEY_FILE       = os.path.join(GOLDPAN_DIR, "service_account.json")
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
INGREDIENT_TAB = "Ingredient Details"
TODAY          = datetime.date.today().isoformat()
DRY_RUN        = "--apply" not in sys.argv

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ── Safe dish IDs (staging provenance confirmed) ────────────────────────────────
#
# Eli's Jerusalem Grill — staging_elis.json
ELIS_DISH_IDS = {
    "D316", "D317", "D327", "D328", "D330", "D331",
    "D333", "D334", "D335", "D338", "D340", "D342", "D347", "D348",
}

# The Essential — staging_essential_dinner_backup.json
ESSENTIAL_DISH_IDS = {
    "D097", "D098", "D099", "D100", "D101", "D102",
    "D103", "D104", "D105", "D106", "D107", "D108", "D109", "D110",
}

SAFE_DISH_IDS = ELIS_DISH_IDS | ESSENTIAL_DISH_IDS

# ── Non-canonical Ingredient_Source values to correct ──────────────────────────
#
# These are ingredient TYPE/category values that were erroneously used as
# acquisition channel values in the pre-staging era. Per CL-001 audit, all
# of these should be "menu" for dishes confirmed via staging files.

NON_CANONICAL = {
    "plant-based",
    "dairy",
    "animal",
    "animal-based",
    "seafood",
    "house",
    "neutral",
    "organic",
    "grass-fed",
}


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    mode = "DRY RUN — no writes" if DRY_RUN else "APPLY MODE — writing to sheet"
    print(f"\nfix_ingredient_source.py  —  {TODAY}")
    print(f"{'='*65}")
    print(f"  {mode}")
    print(f"  Safe dish IDs : {len(SAFE_DISH_IDS)}")
    print(f"    Eli's Jerusalem Grill : {len(ELIS_DISH_IDS)}")
    print(f"    The Essential         : {len(ESSENTIAL_DISH_IDS)}")
    print(f"  Non-canonical sources  : {sorted(NON_CANONICAL)}")
    print(f"{'='*65}\n")

    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ws     = client.open_by_key(SPREADSHEET_ID).worksheet(INGREDIENT_TAB)

    all_values = ws.get_all_values()
    headers    = [h.strip() for h in all_values[0]]

    required = {"Dish_ID", "Ingredient_Source"}
    missing_cols = required - set(headers)
    if missing_cols:
        print(f"  ERROR: Required columns missing from sheet: {missing_cols}")
        print(f"  Found columns: {headers[:10]}...")
        return

    did_col  = headers.index("Dish_ID") + 1           # 1-indexed
    src_col  = headers.index("Ingredient_Source") + 1

    print(f"  Dish_ID column           : {did_col}")
    print(f"  Ingredient_Source column : {src_col}")
    print(f"  Total data rows          : {len(all_values) - 1}\n")

    # Build update list
    updates    = []   # gspread.Cell objects to write
    skipped    = []   # already "menu" — no change needed
    other_skip = []   # canonical non-menu value — not touching
    not_in_set = 0    # dish ID not in SAFE_DISH_IDS — skip entirely

    for row_idx, row in enumerate(all_values[1:], start=2):
        did = row[did_col - 1].strip() if did_col - 1 < len(row) else ""
        if did not in SAFE_DISH_IDS:
            not_in_set += 1
            continue

        current_src = row[src_col - 1].strip() if src_col - 1 < len(row) else ""

        if current_src == "menu":
            skipped.append((did, row_idx))
        elif current_src in NON_CANONICAL:
            updates.append(gspread.Cell(row=row_idx, col=src_col, value="menu"))
        else:
            # Already has some other canonical value (e.g. "website") — do not touch
            other_skip.append((did, row_idx, current_src))

    print(f"  Rows to update           : {len(updates)}")
    print(f"  Already 'menu' (no-op)   : {len(skipped)}")
    print(f"  Other canonical (skip)   : {len(other_skip)}")
    print(f"  Rows outside safe set    : {not_in_set}")

    if other_skip:
        print(f"\n  Rows with other canonical Ingredient_Source (untouched):")
        for did, ridx, src in other_skip[:10]:
            print(f"    Row {ridx}  {did}: '{src}'")

    # Show preview of updates
    if updates:
        print(f"\n  Preview (first 10 updates):")
        # Re-scan to show dish + old value
        preview_map = {}
        for row_idx, row in enumerate(all_values[1:], start=2):
            did = row[did_col - 1].strip() if did_col - 1 < len(row) else ""
            src = row[src_col - 1].strip() if src_col - 1 < len(row) else ""
            if did in SAFE_DISH_IDS and src in NON_CANONICAL:
                preview_map[row_idx] = (did, src)

        shown = 0
        for cell in updates:
            if shown >= 10:
                break
            info = preview_map.get(cell.row, ("?", "?"))
            print(f"    Row {cell.row:4d}  {info[0]}  '{info[1]}' → 'menu'")
            shown += 1

    if DRY_RUN:
        print(f"\n  DRY RUN — no changes written.")
        print(f"  To apply: python3 fix_ingredient_source.py --apply")
        return

    if not updates:
        print(f"\n  Nothing to write — all safe dish ingredient rows already canonical.")
        return

    print(f"\n  Writing {len(updates)} cells...")
    BATCH = 200
    for i in range(0, len(updates), BATCH):
        batch = updates[i:i + BATCH]
        ws.update_cells(batch, value_input_option="USER_ENTERED")
        print(f"    Wrote batch {i // BATCH + 1}: {len(batch)} cells")

    print(f"\n  ✓ Done. {len(updates)} Ingredient_Source values set to 'menu'.")
    print(f"\n  Next steps:")
    print(f"    python3 validate_database.py --table ingredient")
    print(f"    python3 compute_derived_filters.py       # check before/after Unknowns")
    print(f"    python3 pipeline.py --apply              # regenerate dishes.json")


if __name__ == "__main__":
    main()
