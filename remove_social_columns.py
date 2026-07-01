"""
remove_social_columns.py
One-off: removes Instagram and Facebook columns from Menu Source Registry.
Safe to delete after running.
"""

import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

def main():
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)
    ws     = ss.worksheet("Menu Source Registry")

    headers = ws.row_values(1)
    to_remove = []
    for col_name in ["Instagram", "Facebook"]:
        if col_name in headers:
            to_remove.append(headers.index(col_name) + 1)  # 1-based

    if not to_remove:
        print("Instagram/Facebook columns not found — nothing to do.")
        return

    # Delete highest index first so earlier indices stay valid
    for col_idx in sorted(to_remove, reverse=True):
        ws.delete_columns(col_idx)
        print(f"Deleted column at index {col_idx}")

    print("Done.")

if __name__ == "__main__":
    main()
