"""
dedup_tabs.py — remove duplicate Dish_ID rows from Transparency Scoring
and Goldpan Dish Level Data. Keeps the FIRST occurrence, deletes later ones.

Usage:
    python3 dedup_tabs.py             # all restaurants
    python3 dedup_tabs.py R016        # filter to one restaurant
    python3 dedup_tabs.py R016 --dry-run
"""

import sys
import gspread
from google.oauth2.service_account import Credentials
from collections import defaultdict

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

FILTER_RID = None
DRY_RUN    = "--dry-run" in sys.argv

for arg in sys.argv[1:]:
    if not arg.startswith("--"):
        FILTER_RID = arg.strip().upper()

TABS = [
    ("Transparency Scoring",    2, 0),   # did_col=2, rid_col=0
    ("Goldpan Dish Level Data", 3, 0),   # did_col=3, rid_col=0
]


def find_duplicate_rows(ws, did_col, rid_col):
    all_values = ws.get_all_values()
    seen   = {}
    to_del = []

    for i, row in enumerate(all_values[1:], start=2):
        rid = row[rid_col].strip() if len(row) > rid_col else ""
        if FILTER_RID and rid != FILTER_RID:
            continue
        did = row[did_col].strip() if len(row) > did_col else ""
        if not did:
            continue
        if did in seen:
            to_del.append(i)
        else:
            seen[did] = i

    return sorted(to_del, reverse=True)


def batch_delete(ws, row_numbers):
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
        for r in row_numbers
    ]
    ws.spreadsheet.batch_update({"requests": requests})


def main():
    label = f"(filtered to {FILTER_RID})" if FILTER_RID else "(all restaurants)"
    print(f"Scanning tabs {label}...")
    if DRY_RUN:
        print("-- DRY RUN — no writes --\n")

    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    total = 0
    for tab_name, did_col, rid_col in TABS:
        ws     = ss.worksheet(tab_name)
        to_del = find_duplicate_rows(ws, did_col, rid_col)
        if not to_del:
            print(f"  ✓ {tab_name} — no duplicates")
            continue
        print(f"  ⚠ {tab_name} — {len(to_del)} duplicate row(s): {sorted(to_del)}")
        if not DRY_RUN:
            batch_delete(ws, to_del)
            print(f"    → deleted")
        total += len(to_del)

    print(f"\n{'Done.' if not DRY_RUN else '(dry run — no changes written)'} {total} row(s) {'removed' if not DRY_RUN else 'would be removed'}.")


if __name__ == "__main__":
    main()
