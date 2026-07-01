"""
print_sheet_headers.py — Print actual headers for every Goldpan tab.
Run this locally to confirm canonical column names before updating validate_database.py.

Usage: python3 print_sheet_headers.py
"""

import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
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

    for tab in TABS:
        print(f"\n{'='*60}")
        print(f"TAB: {tab}")
        print(f"{'='*60}")
        try:
            ws      = ss.worksheet(tab)
            headers = ws.row_values(1)
            for i, h in enumerate(headers):
                raw  = repr(h)           # shows trailing spaces, hidden chars
                flag = " ⚠ TRAILING SPACE" if h != h.strip() else ""
                print(f"  col {i+1:>2}: {raw}{flag}")
        except gspread.exceptions.WorksheetNotFound:
            print("  NOT FOUND")

if __name__ == "__main__":
    main()
