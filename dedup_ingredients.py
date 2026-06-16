"""
dedup_ingredients.py — remove duplicate (Dish_ID, Ingredient) rows from Ingredient Details.
Keeps the FIRST occurrence of each pair and deletes all later duplicates.
Deletions are batched into a single API call per pass to stay within quota.

Usage:
    python3 dedup_ingredients.py             # all restaurants
    python3 dedup_ingredients.py R017        # filter to one restaurant
    python3 dedup_ingredients.py R017 --dry-run
"""

import sys
import time
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


def find_duplicate_rows(ws):
    """Return sorted list of row numbers (1-indexed) to DELETE (later duplicates only)."""
    all_values = ws.get_all_values()
    seen   = {}   # (did, ing) -> first row number seen
    to_del = []

    for i, row in enumerate(all_values[1:], start=2):
        rid = row[0].strip() if len(row) > 0 else ""
        if FILTER_RID and rid != FILTER_RID:
            continue
        did = row[3].strip() if len(row) > 3 else ""
        ing = row[5].strip() if len(row) > 5 else ""
        if not did or not ing:
            continue
        key = (did, ing)
        if key in seen:
            to_del.append(i)
        else:
            seen[key] = i

    return sorted(to_del, reverse=True)  # reverse so deletes don't shift earlier rows


def batch_delete(ws, row_numbers):
    """Delete rows in a single batch_update call."""
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
        for r in row_numbers  # already sorted reverse
    ]
    ws.spreadsheet.batch_update({"requests": requests})


def main():
    label = f"(filtered to {FILTER_RID})" if FILTER_RID else "(all restaurants)"
    print(f"Scanning Ingredient Details {label}...")
    if DRY_RUN:
        print("-- DRY RUN — no writes --\n")

    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ws     = client.open_by_key(SPREADSHEET_ID).worksheet("Ingredient Details")

    to_del = find_duplicate_rows(ws)

    if not to_del:
        print("No duplicates found.")
        return

    print(f"Found {len(to_del)} duplicate row(s) to delete: {sorted(to_del)}")

    if DRY_RUN:
        print("(dry run — no changes written)")
        return

    print("Deleting in batch...")
    batch_delete(ws, to_del)
    print(f"Done. {len(to_del)} row(s) removed.")


if __name__ == "__main__":
    main()
