"""
fix_header_whitespace.py

One-time fix: strips leading/trailing whitespace from all column headers
in every Goldpan tab. Specifically fixes "Preparation " → "Preparation"
in Ingredient Details.

Safe to run multiple times — only writes a cell if its value actually changes.

Usage: python3 fix_header_whitespace.py
"""

import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

TABS = [
    "Goldpan Dish Level Data",
    "Ingredient Details",
    "Transparency Scoring",
    "Menu Source Registry",
]


def main():
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    total_fixed = 0

    for tab in TABS:
        try:
            ws      = ss.worksheet(tab)
            headers = ws.row_values(1)
        except gspread.exceptions.WorksheetNotFound:
            print(f"  {tab}: NOT FOUND — skipping")
            continue

        updates = []
        for i, h in enumerate(headers):
            stripped = h.strip()
            if stripped != h:
                col_letter = gspread.utils.rowcol_to_a1(1, i + 1)
                updates.append({"range": col_letter, "values": [[stripped]]})
                print(f"  {tab} col {i+1}: {repr(h)} → {repr(stripped)}")

        if updates:
            ws.batch_update(updates)
            total_fixed += len(updates)
            print(f"  {tab}: fixed {len(updates)} header(s)")
        else:
            print(f"  {tab}: all headers clean")

    print(f"\nDone. {total_fixed} header(s) corrected.")
    if total_fixed:
        print("Re-run validate_database.py to confirm clean schema.")


if __name__ == "__main__":
    main()
