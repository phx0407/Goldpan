"""
patch_r015_address.py — Add address and website for Brick & Tin Mountain Brook (R015)

Updates Restaurant_Address and Restaurant_Website for all R015 rows
in Goldpan Dish Level Data.

Usage:
    python3 patch_r015_address.py
    python3 patch_r015_address.py --dry-run
"""

import sys
import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
DRY_RUN        = "--dry-run" in sys.argv

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

RESTAURANT_ID      = "R015"
ADDRESS            = "2901 Cahaba Road, Mountain Brook, AL 35223"
WEBSITE            = "https://brickandtin.com/"


def main():
    if DRY_RUN:
        print("-- DRY RUN — no changes will be written --\n")

    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)
    ws     = ss.worksheet("Goldpan Dish Level Data")

    headers = ws.row_values(1)
    try:
        rid_col     = headers.index("Restaurant_ID") + 1
        addr_col    = headers.index("Restaurant_Address") + 1
        website_col = headers.index("Restaurant_Website") + 1
    except ValueError as e:
        print(f"ERROR: Column not found — {e}")
        return

    all_values = ws.get_all_values()
    updated = 0
    for i, row in enumerate(all_values[1:], start=2):
        rid = row[rid_col - 1].strip() if len(row) >= rid_col else ""
        if rid == RESTAURANT_ID:
            if DRY_RUN:
                print(f"  row {i}: would set address='{ADDRESS}', website='{WEBSITE}'")
            else:
                ws.update_cell(i, addr_col, ADDRESS)
                ws.update_cell(i, website_col, WEBSITE)
            updated += 1

    print(f"\n{'Would update' if DRY_RUN else 'Updated'} {updated} rows for {RESTAURANT_ID}.")


if __name__ == "__main__":
    main()
