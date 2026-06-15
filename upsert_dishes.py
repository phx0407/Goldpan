"""
upsert_dishes.py — Goldpan Sheet upsert
Reads staging.json and upserts rows into three tabs:
  - Ingredient Details
  - Transparency Scoring
  - Goldpan Dish Level Data

For existing dishes (matched by Dish_ID):
  Deletes old rows and writes fresh ones with today's date.
For new dishes:
  Appends rows.

This replaces add_dishes.py. Safe to run multiple times —
re-running with the same staging.json is a no-op beyond updating the date.

Usage:
    python3 upsert_dishes.py
    python3 upsert_dishes.py --dry-run   (preview, no writes)
"""

import json
import sys
import time
import datetime
import gspread
from google.oauth2.service_account import Credentials

# ── CONFIG ────────────────────────────────────────────────────────────────────

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
STAGING_FILE   = "staging.json"

# ── END CONFIG ────────────────────────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DRY_RUN = "--dry-run" in sys.argv
TODAY   = datetime.date.today().strftime("%-m/%-d/%Y")


def load_staging():
    with open(STAGING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Row builders (same logic as add_dishes.py) ────────────────────────────────

def build_ingredient_rows(data):
    rows = []
    rid   = data["restaurant_id"]
    rname = data["restaurant_name"]
    loc   = data["location"]
    for dish in data["dishes"]:
        for ing in dish.get("ingredients", []):
            rows.append([
                rid, rname, loc,
                dish["dish_id"], dish["dish_name"],
                ing.get("name", ""),
                ing.get("cut_type", "none"),
                ing.get("preparation", "none"),
                ing.get("type", "standard"),
                "Active",
                "1",
                "Unconfirmed",
                ing.get("source", "unknown"),
                ing.get("allergen_flags", "none"),
                ing.get("role", ""),
            ])
    return rows


def build_scoring_rows(data):
    rows = []
    rid   = data["restaurant_id"]
    rname = data["restaurant_name"]
    for dish in data["dishes"]:
        rows.append([
            rid, rname,
            dish["dish_id"], dish["dish_name"],
            dish.get("core_clarity", 0),
            dish.get("sauce_disclosure", 0),
            dish.get("allergen_transparency", 0),
            dish.get("prep_clarity", 0),
            dish.get("total_score", 0),
            dish.get("transparency_level", "Building Transparency"),
            dish.get("notes", ""),
        ])
    return rows


def build_dish_level_rows(data):
    rows = []
    rid   = data["restaurant_id"]
    rname = data["restaurant_name"]
    loc   = data["location"]
    for dish in data["dishes"]:
        rows.append([
            rid, rname, loc,
            dish["dish_id"], dish["dish_name"],
            ", ".join(dish["dietary_tags"]) if dish.get("dietary_tags") else "none",
            dish.get("dietary_options", ""),
            "menu",
            "unconfirmed",
            data.get("hours", ""),
            data.get("menu_link", ""),
            dish.get("menu_price", ""),
            data.get("restaurant_address", ""),
            dish.get("allergen_summary", "Unknown"),
            TODAY,                              # Last_Updated
            data.get("restaurant_website", ""), # Restaurant_Website
        ])
    return rows


# ── Upsert helpers ────────────────────────────────────────────────────────────

def index_by_dish_id(ws, did_col):
    """
    Returns {dish_id: [1-indexed row numbers]} for all data rows.
    did_col is 0-indexed position of Dish_ID in the sheet.
    """
    all_values = ws.get_all_values()
    index = {}
    for i, row in enumerate(all_values[1:], start=2):  # skip header, rows are 1-indexed
        did = row[did_col].strip() if len(row) > did_col else ""
        if did:
            index.setdefault(did, []).append(i)
    return index


def delete_rows_batch(ws, row_numbers):
    """Delete rows in a single batch_update request to avoid API quota limits."""
    if not row_numbers:
        return
    sorted_rows = sorted(row_numbers, reverse=True)
    requests = [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": ws._properties["sheetId"],
                    "dimension": "ROWS",
                    "startIndex": row_num - 1,
                    "endIndex": row_num,
                }
            }
        }
        for row_num in sorted_rows
    ]
    ws.spreadsheet.batch_update({"requests": requests})


def upsert_tab(ws, new_rows_by_did, did_col, label):
    """
    For each dish_id in new_rows_by_did:
      - If rows exist: delete them and append fresh rows.
      - If new: append rows.
    Returns (n_updated, n_added).
    """
    existing = index_by_dish_id(ws, did_col) if not DRY_RUN else {}
    n_updated = 0
    n_added   = 0
    rows_to_append = []

    for did, rows in new_rows_by_did.items():
        if did in existing:
            if DRY_RUN:
                print(f"  {label} [{did}]: would update (delete old rows, write {len(rows)} new)")
            else:
                delete_rows_batch(ws, existing[did])
            n_updated += 1
        else:
            if DRY_RUN:
                print(f"  {label} [{did}]: new — would append {len(rows)} row(s)")
            n_added += 1
        rows_to_append.extend(rows)

    if rows_to_append:
        if not DRY_RUN:
            ws.append_rows(rows_to_append, value_input_option="USER_ENTERED")

    return n_updated, n_added


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Loading {STAGING_FILE}...")
    data = load_staging()

    rname    = data["restaurant_name"]
    n_dishes = len(data["dishes"])
    n_ing    = sum(len(d.get("ingredients", [])) for d in data["dishes"])
    print(f"Restaurant : {rname}")
    print(f"Dishes     : {n_dishes}")
    print(f"Ingredients: {n_ing}")

    if DRY_RUN:
        print("\n-- DRY RUN — no changes will be written --\n")

    # Build rows grouped by Dish_ID
    ing_by_did   = {}
    score_by_did = {}
    dish_by_did  = {}

    ing_rows   = build_ingredient_rows(data)
    score_rows = build_scoring_rows(data)
    dish_rows  = build_dish_level_rows(data)

    # Group by Dish_ID (col index 3 for ing/dish, col index 2 for scoring)
    for row in ing_rows:
        ing_by_did.setdefault(row[3], []).append(row)
    for row in score_rows:
        score_by_did.setdefault(row[2], []).append(row)
    for row in dish_rows:
        dish_by_did.setdefault(row[3], []).append(row)

    if not DRY_RUN:
        print("\nConnecting to Google Sheets...")
        creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        ss     = client.open_by_key(SPREADSHEET_ID)

    print("\nUpserting...")

    if DRY_RUN:
        upsert_tab(None, ing_by_did,   3, "Ingredient Details")
        upsert_tab(None, score_by_did, 2, "Transparency Scoring")
        upsert_tab(None, dish_by_did,  3, "Goldpan Dish Level Data")
    else:
        u, a = upsert_tab(ss.worksheet("Ingredient Details"),      ing_by_did,   3, "Ingredient Details")
        print(f"  Ingredient Details      : {a} added, {u} updated")
        time.sleep(3)
        u, a = upsert_tab(ss.worksheet("Transparency Scoring"),    score_by_did, 2, "Transparency Scoring")
        print(f"  Transparency Scoring    : {a} added, {u} updated")
        time.sleep(3)
        u, a = upsert_tab(ss.worksheet("Goldpan Dish Level Data"), dish_by_did,  3, "Goldpan Dish Level Data")
        print(f"  Goldpan Dish Level Data : {a} added, {u} updated")

    print(f"\nDone. Run update.sh to regenerate dishes.json and push.")


if __name__ == "__main__":
    main()
