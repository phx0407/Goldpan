"""
check_duplicates.py — scan for duplicate ingredient rows per dish

Ingredient Details: flags any (Dish_ID, Ingredient) pair that appears more than once.
Transparency Scoring & Goldpan Dish Level Data: flags any Dish_ID with more than one row.

Usage:
    python3 check_duplicates.py
    python3 check_duplicates.py R016    # filter to a specific restaurant ID
    python3 check_duplicates.py R017
"""

import sys
import gspread
from google.oauth2.service_account import Credentials
from collections import defaultdict

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

FILTER_RID = sys.argv[1].strip().upper() if len(sys.argv) > 1 else None


def check_ingredient_details(ws):
    """Check for duplicate (Dish_ID, Ingredient) pairs."""
    all_values = ws.get_all_values()
    # cols: 0=Restaurant_ID, 3=Dish_ID, 4=Dish_Name, 5=Ingredient
    counts = defaultdict(list)
    for i, row in enumerate(all_values[1:], start=2):
        rid = row[0].strip() if len(row) > 0 else ""
        if FILTER_RID and rid != FILTER_RID:
            continue
        did  = row[3].strip() if len(row) > 3 else ""
        ing  = row[5].strip() if len(row) > 5 else ""
        if did and ing:
            counts[(did, ing)].append(i)

    dupes = {k: v for k, v in counts.items() if len(v) > 1}
    if dupes:
        print(f"\n  ⚠ Ingredient Details — {len(dupes)} duplicate (Dish_ID, Ingredient) pair(s):")
        for (did, ing), rows in sorted(dupes.items()):
            print(f"    {did} | {ing!r}: rows {rows}")
    else:
        print(f"\n  ✓ Ingredient Details — no duplicate ingredient rows")
    return dupes


def check_one_row_per_dish(ws, did_col, rid_col, label):
    """Check for Dish_IDs that appear more than once (should be exactly 1 row each)."""
    all_values = ws.get_all_values()
    counts = defaultdict(list)
    for i, row in enumerate(all_values[1:], start=2):
        rid = row[rid_col].strip() if len(row) > rid_col else ""
        if FILTER_RID and rid != FILTER_RID:
            continue
        did = row[did_col].strip() if len(row) > did_col else ""
        if did:
            counts[did].append(i)

    dupes = {did: rows for did, rows in counts.items() if len(rows) > 1}
    if dupes:
        print(f"\n  ⚠ {label} — {len(dupes)} Dish_ID(s) with multiple rows:")
        for did, rows in sorted(dupes.items()):
            print(f"    {did}: rows {rows}")
    else:
        print(f"\n  ✓ {label} — no duplicates")
    return dupes


def main():
    if FILTER_RID:
        print(f"Checking for duplicates (filtered to {FILTER_RID})...")
    else:
        print("Checking for duplicates (all restaurants)...")

    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    d1 = check_ingredient_details(ss.worksheet("Ingredient Details"))
    d2 = check_one_row_per_dish(ss.worksheet("Transparency Scoring"),    2, 0, "Transparency Scoring")
    d3 = check_one_row_per_dish(ss.worksheet("Goldpan Dish Level Data"), 3, 0, "Goldpan Dish Level Data")

    total = len(d1) + len(d2) + len(d3)
    print(f"\n{'All clean.' if total == 0 else f'{total} issue(s) found.'}")


if __name__ == "__main__":
    main()
