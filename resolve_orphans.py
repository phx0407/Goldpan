"""
resolve_orphans.py

Resolves the 4 orphaned Dish_IDs found after the shifted-row repair:

  D008  (Yo Chef Surf & Turf Smokehouse, R002)
    → DELETE ingredient rows (dish no longer on menu; dish name not recoverable)

  D113  (Brick & Tin Mountain Brook, R015)
    → RESTORE as "Turkey Club" — confirmed on current B&T menu
    → Insert Dish Level Data row; Ingredient Details rows already exist

  D116  (Brick & Tin Mountain Brook, R015)
    → RESTORE as "Mushroom Soup" — confirmed on current B&T menu (GF)
    → Insert Dish Level Data row; Ingredient Details rows already exist

  D121  (Brick & Tin Mountain Brook, R015)
    → RESTORE as "Spring Harvest Salad" — confirmed on current B&T menu
    → Insert Dish Level Data row; Ingredient Details rows already exist

After running with --apply:
  1. Run backfill_ingredient_details.py to fill Restaurant_ID/Restaurant_Name/
     Location/Dish_Name into the D113/D116/D121 ingredient rows.
  2. Run fix_database_errors.py --apply (if not yet done) for duplicates/blank Status.
  3. Run validate_database.py to confirm PASS.

Usage:
  python3 resolve_orphans.py            # dry run — report only
  python3 resolve_orphans.py --apply    # apply all changes
"""

import sys
import datetime
import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TODAY          = datetime.date.today().strftime("%Y-%m-%d")
APPLY          = "--apply" in sys.argv

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ── Brick & Tin restaurant metadata ──────────────────────────────────────────
R015_ID      = "R015"
R015_NAME    = "Brick & Tin Mountain Brook"
R015_LOC     = "Mountain Brook, AL"
R015_HOURS   = "Mon–Sun 10:30 AM–8:00 PM"
R015_MENU    = "https://brickandtin.com/mountain-brook-brick-and-tin-food-menu"
R015_ADDRESS = "2901 Cahaba Rd, Mountain Brook, AL 35223"
R015_WEBSITE = "https://brickandtin.com/"

# ── New Dish Level Data rows to insert ───────────────────────────────────────
# Column order matches Goldpan Dish Level Data canonical schema:
# Restaurant_ID | Restaurant | Location | Dish_ID | Dish_Name |
# Dietary_Tags | Dietary_Options | Tag_Source | Verification_Status | Hours |
# Menu_Link | Menu_Price | Restaurant_Address | Allergen_summary |
# Last_Updated | Restaurant_Website | Status | Version | Category

NEW_DISH_ROWS = [
    [
        R015_ID, R015_NAME, R015_LOC,
        "D113", "Turkey Club",
        "none",                    # Dietary_Tags
        "",                        # Dietary_Options
        "menu",                    # Tag_Source
        "menu-verified",           # Verification_Status
        R015_HOURS,
        R015_MENU,
        "$17",                     # Menu_Price
        R015_ADDRESS,
        "Dairy (swiss cheese), Wheat (sourdough bread), Egg (aioli). Contact restaurant to confirm.",
        TODAY,
        R015_WEBSITE,
        "Active",
        "1",
        "sandwich",
    ],
    [
        R015_ID, R015_NAME, R015_LOC,
        "D116", "Mushroom Soup",
        "gluten-free",             # Dietary_Tags
        "",                        # Dietary_Options
        "menu",                    # Tag_Source
        "menu-verified",           # Verification_Status
        R015_HOURS,
        R015_MENU,
        "$5 cup / $9 bowl",        # Menu_Price
        R015_ADDRESS,
        "Unknown (verify dairy/cream content). Contact restaurant to confirm.",
        TODAY,
        R015_WEBSITE,
        "Active",
        "1",
        "soup",
    ],
    [
        R015_ID, R015_NAME, R015_LOC,
        "D121", "Spring Harvest Salad",
        "vegetarian, gluten-free", # Dietary_Tags
        "",                        # Dietary_Options
        "menu",                    # Tag_Source
        "menu-verified",           # Verification_Status
        R015_HOURS,
        R015_MENU,
        "$17",                     # Menu_Price
        R015_ADDRESS,
        "Dairy (feta), Tree Nuts (almonds). Contact restaurant to confirm.",
        TODAY,
        R015_WEBSITE,
        "Active",
        "1",
        "salad",
    ],
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


def delete_rows(ws, row_numbers):
    """Delete rows by sheet row number, highest first (avoids index shift)."""
    if not row_numbers:
        return 0
    requests = [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": ws._properties["sheetId"],
                    "dimension": "ROWS",
                    "startIndex": r - 1,
                    "endIndex": r,
                }
            }
        }
        for r in sorted(row_numbers, reverse=True)
    ]
    ws.spreadsheet.batch_update({"requests": requests})
    return len(row_numbers)


def delete_d008(ss):
    """Delete all Ingredient Details rows where Dish_ID = D008."""
    print("\n── D008 — Delete ingredient rows (Yo Chef, dish removed from menu) ──")
    ws         = ss.worksheet("Ingredient Details")
    all_values = ws.get_all_values()
    headers    = [h.strip() for h in all_values[0]]
    did_col    = col_idx(headers, "Dish_ID")

    to_delete = []
    for i, row in enumerate(all_values[1:], start=2):
        if cell(row, did_col) == "D008":
            to_delete.append(i)

    print(f"  Found {len(to_delete)} ingredient row(s) for D008.")
    for r in to_delete:
        print(f"    Row {r}")

    if not to_delete:
        print("  Nothing to delete.")
        return 0

    if APPLY:
        deleted = delete_rows(ws, to_delete)
        print(f"  ✓ Deleted {deleted} row(s).")
    else:
        print(f"  [DRY RUN] Would delete {len(to_delete)} row(s).")

    return len(to_delete)


def restore_brick_and_tin(ss):
    """
    Insert Dish Level Data rows for D113, D116, D121.
    Skips any that already exist to make the script safe to re-run.
    """
    print("\n── D113 / D116 / D121 — Restore Brick & Tin dishes ──")
    ws         = ss.worksheet("Goldpan Dish Level Data")
    all_values = ws.get_all_values()
    headers    = [h.strip() for h in all_values[0]]
    did_col    = col_idx(headers, "Dish_ID")

    existing = {cell(r, did_col) for r in all_values[1:] if cell(r, did_col)}

    to_insert = []
    for row in NEW_DISH_ROWS:
        did       = row[3]
        dish_name = row[4]
        if did in existing:
            print(f"  SKIP {did} ({dish_name}) — already in Dish Level Data")
        else:
            to_insert.append(row)
            print(f"  Queued: {did} — {dish_name}")

    if not to_insert:
        print("  Nothing to insert.")
        return 0

    # Validate column count matches header count
    expected_cols = len(headers)
    for row in to_insert:
        if len(row) != expected_cols:
            print(f"  ERROR: Row for {row[3]} has {len(row)} values but sheet has {expected_cols} columns.")
            print(f"  Headers: {headers}")
            print("  Aborting. Fix column count mismatch before applying.")
            sys.exit(1)

    if APPLY:
        ws.append_rows(to_insert, value_input_option="USER_ENTERED")
        print(f"  ✓ Inserted {len(to_insert)} row(s) into Goldpan Dish Level Data.")
    else:
        print(f"  [DRY RUN] Would insert {len(to_insert)} row(s) into Goldpan Dish Level Data.")

    return len(to_insert)


def main():
    print(f"resolve_orphans.py  —  {TODAY}")
    print("MODE: " + ("APPLY — changes will be written" if APPLY else "DRY RUN — run with --apply to write changes"))

    print("\nConnecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    d008_deleted  = delete_d008(ss)
    rows_inserted = restore_brick_and_tin(ss)

    print("\n" + "=" * 55)
    print("SUMMARY")
    print("=" * 55)
    print(f"  D008 ingredient rows deleted       : {d008_deleted}")
    print(f"  Dish Level Data rows inserted      : {rows_inserted}")
    print(f"    D113 Turkey Club                 : {'✓' if APPLY and rows_inserted else '[dry run]'}")
    print(f"    D116 Mushroom Soup               : {'✓' if APPLY and rows_inserted else '[dry run]'}")
    print(f"    D121 Spring Harvest Salad        : {'✓' if APPLY and rows_inserted else '[dry run]'}")

    if not APPLY:
        print()
        print("  Run with --apply to apply changes.")
    else:
        print()
        print("  Next steps:")
        print("    python3 backfill_ingredient_details.py   # fill R_ID/R_Name/Location/Dish_Name into D113/D116/D121 rows")
        print("    python3 fix_database_errors.py --apply   # duplicates + blank Status (if not yet run)")
        print("    python3 validate_database.py             # confirm PASS")


if __name__ == "__main__":
    main()
