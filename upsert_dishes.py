"""
upsert_dishes.py — Goldpan Sheet upsert
Reads staging.json and upserts rows into four tabs:
  - Ingredient Details
  - Transparency Scoring
  - Goldpan Dish Level Data
  - Restaurant Claims

For existing dishes (matched by Dish_ID) or restaurants (matched by Restaurant_ID):
  Deletes old rows and writes fresh ones with today's date.
For new records:
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


# ── Row builders ──────────────────────────────────────────────────────────────

def build_ingredient_rows(data):
    rows = []
    rid   = data["restaurant_id"]
    rname = data["restaurant_name"]
    loc   = data["location"]
    for dish in data["dishes"]:
        for ing in dish.get("ingredients", []):
            # Support both string ingredients ("tomato") and dict ingredients
            if isinstance(ing, str):
                name = ing
                cut_type = "none"
                preparation = "none"
                ing_type = "standard"
                source = "unknown"
                allergen_flags = "none"
                role = ""
            else:
                name = ing.get("name", "")
                cut_type = ing.get("cut_type", "none")
                preparation = ing.get("preparation", "none")
                ing_type = ing.get("type", "standard")
                source = ing.get("source", "unknown")
                allergen_flags = ing.get("allergen_flags", "none")
                role = ing.get("role", "")
            rows.append([
                rid, rname, loc,
                dish["dish_id"], dish["dish_name"],
                name, cut_type, preparation, ing_type,
                "Active", "1",
                source, allergen_flags, role,
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
            dish.get("category", ""),           # Category
        ])
    return rows


def build_claims_rows(data):
    """
    Builds rows for the Restaurant Claims tab.
    One row per claim. Keyed by Restaurant_ID (col 0) for upsert.

    Columns:
      Restaurant_ID | Restaurant_Name | Claim_Type | Claim_Scope |
      Claim_Text | Verified | Source | Date_Added
    """
    rows = []
    rid   = data["restaurant_id"]
    rname = data["restaurant_name"]
    for claim in data.get("claims", []):
        rows.append([
            rid,
            rname,
            claim.get("claim_type", ""),
            claim.get("claim_scope", ""),
            claim.get("claim_text", ""),
            claim.get("verified", "unverified"),
            claim.get("source", ""),
            TODAY,
        ])
    return rows


CLAIMS_HEADERS = [
    "Restaurant_ID", "Restaurant_Name", "Claim_Type", "Claim_Scope",
    "Claim_Text", "Verified", "Source", "Date_Added",
]


def ensure_claims_tab(ss):
    """Create the Restaurant Claims tab with headers if it doesn't exist."""
    try:
        ws = ss.worksheet("Restaurant Claims")
        # Tab exists — make sure it has headers
        existing = ws.row_values(1)
        if not existing:
            ws.append_row(CLAIMS_HEADERS)
            print("  (added headers to existing Restaurant Claims tab)")
        return ws
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title="Restaurant Claims", rows=500, cols=len(CLAIMS_HEADERS))
        ws.append_row(CLAIMS_HEADERS)
        print("  (created Restaurant Claims tab with headers)")
        return ws


# ── Upsert helpers ────────────────────────────────────────────────────────────

def index_by_dish_id(ws, did_col):
    """
    Returns {dish_id: [1-indexed row numbers]} for all data rows.
    did_col is 0-indexed position of the key column in the sheet.
    """
    all_values = ws.get_all_values()
    index = {}
    for i, row in enumerate(all_values[1:], start=2):  # skip header, rows are 1-indexed
        did = row[did_col].strip() if len(row) > did_col else ""
        if did:
            index.setdefault(did, []).append(i)
    return index


def api_call_with_retry(fn, *args, retries=4, **kwargs):
    """Call fn(*args, **kwargs), retrying on 429 with exponential backoff."""
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            if e.response.status_code == 429 and attempt < retries - 1:
                wait = 30 * (attempt + 1)
                print(f"  [quota] 429 received, waiting {wait}s before retry {attempt + 2}/{retries}...")
                time.sleep(wait)
            else:
                raise


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
    api_call_with_retry(ws.spreadsheet.batch_update, {"requests": requests})


def upsert_tab(ws, new_rows_by_key, key_col, label):
    """
    For each key in new_rows_by_key:
      - If rows exist: delete them and append fresh rows.
      - If new: append rows.
    Returns (n_updated, n_added).
    """
    existing = index_by_dish_id(ws, key_col) if not DRY_RUN else {}
    n_updated = 0
    n_added   = 0
    rows_to_append  = []
    all_rows_to_del = []

    for key, rows in new_rows_by_key.items():
        if key in existing:
            if DRY_RUN:
                print(f"  {label} [{key}]: would update (delete old rows, write {len(rows)} new)")
            else:
                all_rows_to_del.extend(existing[key])
            n_updated += 1
        else:
            if DRY_RUN:
                print(f"  {label} [{key}]: new — would append {len(rows)} row(s)")
            n_added += 1
        rows_to_append.extend(rows)

    if not DRY_RUN:
        if all_rows_to_del:
            delete_rows_batch(ws, all_rows_to_del)   # single batch — avoids stale-index shift
        if rows_to_append:
            api_call_with_retry(ws.append_rows, rows_to_append, value_input_option="USER_ENTERED")

    return n_updated, n_added


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Loading {STAGING_FILE}...")
    data = load_staging()

    rname    = data["restaurant_name"]
    n_dishes = len(data["dishes"])
    n_ing    = sum(len(d.get("ingredients", [])) for d in data["dishes"])
    n_claims = len(data.get("claims", []))
    print(f"Restaurant : {rname}")
    print(f"Dishes     : {n_dishes}")
    print(f"Ingredients: {n_ing}")
    print(f"Claims     : {n_claims}")

    if DRY_RUN:
        print("\n-- DRY RUN — no changes will be written --\n")

    # Build rows grouped by Dish_ID (or Restaurant_ID for claims)
    ing_by_did    = {}
    score_by_did  = {}
    dish_by_did   = {}
    claims_by_rid = {}

    ing_rows    = build_ingredient_rows(data)
    score_rows  = build_scoring_rows(data)
    dish_rows   = build_dish_level_rows(data)
    claims_rows = build_claims_rows(data)

    # Group by Dish_ID (col index 3 for ing/dish, col index 2 for scoring)
    for row in ing_rows:
        ing_by_did.setdefault(row[3], []).append(row)
    for row in score_rows:
        score_by_did.setdefault(row[2], []).append(row)
    for row in dish_rows:
        dish_by_did.setdefault(row[3], []).append(row)
    # Group claims by Restaurant_ID (col index 0) — all claims for a restaurant upserted together
    rid = data["restaurant_id"]
    if claims_rows:
        claims_by_rid[rid] = claims_rows

    if not DRY_RUN:
        print("\nConnecting to Google Sheets...")
        creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        ss     = client.open_by_key(SPREADSHEET_ID)

    print("\nUpserting...")

    if DRY_RUN:
        upsert_tab(None, ing_by_did,    3, "Ingredient Details")
        upsert_tab(None, score_by_did,  2, "Transparency Scoring")
        upsert_tab(None, dish_by_did,   3, "Goldpan Dish Level Data")
        if claims_by_rid:
            upsert_tab(None, claims_by_rid, 0, "Restaurant Claims")
    else:
        u, a = upsert_tab(ss.worksheet("Ingredient Details"),      ing_by_did,   3, "Ingredient Details")
        print(f"  Ingredient Details      : {a} added, {u} updated")
        time.sleep(20)
        u, a = upsert_tab(ss.worksheet("Transparency Scoring"),    score_by_did, 2, "Transparency Scoring")
        print(f"  Transparency Scoring    : {a} added, {u} updated")
        time.sleep(20)
        u, a = upsert_tab(ss.worksheet("Goldpan Dish Level Data"), dish_by_did,  3, "Goldpan Dish Level Data")
        print(f"  Goldpan Dish Level Data : {a} added, {u} updated")
        if claims_by_rid:
            time.sleep(20)
            claims_ws = ensure_claims_tab(ss)
            u, a = upsert_tab(claims_ws, claims_by_rid, 0, "Restaurant Claims")
            print(f"  Restaurant Claims       : {a} added, {u} updated")

    print(f"\nDone. Run update.sh to regenerate dishes.json and push.")


if __name__ == "__main__":
    main()
