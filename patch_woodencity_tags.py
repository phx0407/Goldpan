"""
patch_woodencity_tags.py — patch dietary_tags for Wooden City (R018)
Updates only the Dietary_Tags column in Goldpan Dish Level Data
for dishes with explicit restaurant dietary claims.

Usage:
    python3 patch_woodencity_tags.py
    python3 patch_woodencity_tags.py --dry-run
"""

import sys
import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TAB_NAME       = "Goldpan Dish Level Data"

# Columns are 0-indexed in the row list.
# Goldpan Dish Level Data columns:
#   0: Restaurant_ID
#   1: Restaurant_Name
#   2: Location
#   3: Dish_ID
#   4: Dish_Name
#   5: Dietary_Tags   ← we're patching this
#   6: Dietary_Options
#   ...

DID_COL  = 3   # Dish_ID column (0-indexed)
TAGS_COL = 5   # Dietary_Tags column (0-indexed)

DRY_RUN = "--dry-run" in sys.argv

# Only dishes with explicit restaurant dietary claims.
# "Veggie"/"Vegan" in dish name = explicit claim.
# "gluten free bun +1" on menu = explicit GF option claim.
PATCHES = {
    "D363": "vegetarian",
    "D367": "vegetarian, vegan",
    "D368": "gluten-free",
    "D370": "vegetarian",
}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def main():
    if DRY_RUN:
        print("-- DRY RUN — no writes --\n")

    print(f"Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ws     = client.open_by_key(SPREADSHEET_ID).worksheet(TAB_NAME)

    all_values = ws.get_all_values()
    header     = all_values[0]

    # Confirm column positions
    print(f"Dish_ID col header:    {header[DID_COL]}")
    print(f"Dietary_Tags col header: {header[TAGS_COL]}\n")

    updates = []  # list of (row_1indexed, col_1indexed, value)

    for i, row in enumerate(all_values[1:], start=2):
        did = row[DID_COL].strip() if len(row) > DID_COL else ""
        if did in PATCHES:
            new_tag = PATCHES[did]
            current = row[TAGS_COL].strip() if len(row) > TAGS_COL else ""
            print(f"  {did}: '{current}' → '{new_tag}'")
            updates.append((i, TAGS_COL + 1, new_tag))  # gspread is 1-indexed

    if not updates:
        print("No matching rows found.")
        return

    print(f"\n{len(updates)} row(s) to update.")

    if not DRY_RUN:
        for row_num, col_num, value in updates:
            ws.update_cell(row_num, col_num, value)
        print("Done. Run fetch_dishes.py and git push to publish.")
    else:
        print("(dry run — no changes written)")


if __name__ == "__main__":
    main()
