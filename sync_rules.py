"""
sync_rules.py — Write CANVASSING_RULES.md to a 'Canvassing Rules' tab in Google Sheets.
Clears and rewrites the tab on every run so it stays in sync with the local file.

Usage:
    python3 sync_rules.py
"""

import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TAB_NAME       = "Canvassing Rules"
RULES_FILE     = "CANVASSING_RULES.md"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def main():
    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    # Get or create the tab
    try:
        ws = ss.worksheet(TAB_NAME)
        ws.clear()
        print(f"Cleared existing '{TAB_NAME}' tab.")
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=TAB_NAME, rows=300, cols=4)
        print(f"Created new '{TAB_NAME}' tab.")

    # Read and parse the markdown file
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    rows = []
    for line in lines:
        line = line.rstrip("\n")

        # Section headers → bold-style (capitalize, single cell)
        if line.startswith("## "):
            rows.append([""])  # blank spacer
            rows.append([line.replace("## ", "").upper()])
            continue

        if line.startswith("### "):
            rows.append([line.replace("### ", "")])
            continue

        if line.startswith("# "):
            rows.append([line.replace("# ", "").upper()])
            continue

        # Table rows → split on | into columns, strip whitespace
        if line.startswith("|"):
            cols = [c.strip() for c in line.strip("|").split("|")]
            # Skip separator rows (---|---|---)
            if all(set(c.replace("-", "").replace(":", "")) <= {""} for c in cols):
                continue
            rows.append(cols)
            continue

        # Blockquote → indent
        if line.startswith("> "):
            rows.append(["    " + line[2:]])
            continue

        # Bullet points
        if line.startswith("- "):
            rows.append(["  • " + line[2:]])
            continue

        # Horizontal rule → skip
        if line.strip() == "---":
            continue

        # Everything else → single cell
        rows.append([line] if line.strip() else [""])

    # Write in one batch
    if rows:
        ws.update(rows, value_input_option="RAW")

    print(f"Done. Wrote {len(rows)} rows to '{TAB_NAME}'.")


if __name__ == "__main__":
    main()
