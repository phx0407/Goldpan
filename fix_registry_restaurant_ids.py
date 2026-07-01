"""
fix_registry_restaurant_ids.py — One-time fix: correct Restaurant_ID for Blue Root and Wasabi Juan's.

Changes:
  Blue Root    →  R016  (was blank)
  Wasabi Juan's →  R026  (was R016, conflicted with Blue Root)

Dry-run by default. Use --apply to write.

Usage:
    python3 fix_registry_restaurant_ids.py
    python3 fix_registry_restaurant_ids.py --apply
"""

import sys
import os
import datetime

import gspread
from google.oauth2.service_account import Credentials

GOLDPAN_DIR    = os.path.dirname(os.path.abspath(__file__))
KEY_FILE       = os.path.join(GOLDPAN_DIR, "service_account.json")
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
REGISTRY_TAB   = "Menu Source Registry"
TODAY          = datetime.date.today().isoformat()
DRY_RUN        = "--apply" not in sys.argv

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Corrections: {Restaurant_Name: new_Restaurant_ID}
CORRECTIONS = {
    "Blue Root":    "R016",
    "Wasabi Juan's": "R026",
}


def main():
    mode = "DRY RUN" if DRY_RUN else "APPLYING"
    print(f"\nfix_registry_restaurant_ids.py  —  {TODAY}  [{mode}]")

    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ws     = client.open_by_key(SPREADSHEET_ID).worksheet(REGISTRY_TAB)

    all_values = ws.get_all_values()
    headers    = [h.strip() for h in all_values[0]]

    if "Restaurant_Name" not in headers or "Restaurant_ID" not in headers:
        print("  ERROR: Required columns not found.")
        sys.exit(1)

    name_col = headers.index("Restaurant_Name") + 1
    rid_col  = headers.index("Restaurant_ID") + 1

    updates = []
    for row_idx, row in enumerate(all_values[1:], start=2):
        name    = row[name_col - 1].strip() if name_col - 1 < len(row) else ""
        current = row[rid_col  - 1].strip() if rid_col  - 1 < len(row) else ""
        if name in CORRECTIONS:
            new_id = CORRECTIONS[name]
            print(f"  {name:<30}  {current or '(blank)':<8}  →  {new_id}")
            updates.append(gspread.Cell(row=row_idx, col=rid_col, value=new_id))

    if len(updates) != len(CORRECTIONS):
        found = {all_values[c.row - 1][name_col - 1] for c in updates}
        missing = set(CORRECTIONS) - found
        print(f"\n  WARNING: could not find row(s): {missing}")

    if DRY_RUN:
        print(f"\n  DRY RUN — no changes written.")
        print(f"  To apply: python3 fix_registry_restaurant_ids.py --apply")
        return

    ws.update_cells(updates, value_input_option="USER_ENTERED")

    # Verify
    refreshed = ws.get_all_values()
    h2 = [h.strip() for h in refreshed[0]]
    nc = h2.index("Restaurant_Name") + 1
    rc = h2.index("Restaurant_ID")   + 1
    print(f"\n  Verification:")
    for row in refreshed[1:]:
        name = row[nc - 1].strip()
        rid  = row[rc - 1].strip()
        if name in CORRECTIONS:
            ok = rid == CORRECTIONS[name]
            print(f"  {'✓' if ok else '✗'}  {name:<30}  {rid}")

    print(f"\n  Done. Next steps:")
    print(f"    python3 check_freshness.py --apply   # re-snapshot with correct IDs")
    print(f"    python3 pipeline.py --apply          # full pipeline run")


if __name__ == "__main__":
    main()
