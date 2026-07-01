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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 1 — MENU VERIFICATION GATE  (see DATA_RULES.md)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A dish may only be created from a current, verified live menu.
Supporting documents may enrich an existing dish but may never
create one.

Every dish in a staging file MUST have:

    "menu_verified": true

This field is the canvasser's attestation that the dish was
confirmed on the restaurant's current live menu — not inferred
from a nutritional PDF, allergen document, or any secondary source.

If any dish is missing "menu_verified": true, the upsert will STOP.
Use --force to override (legacy files only — use with caution).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Usage:
    python3 upsert_dishes.py                          (uses staging.json)
    python3 upsert_dishes.py staging_chopt.json       (uses named file)
    python3 upsert_dishes.py staging_chopt.json --dry-run
    python3 upsert_dishes.py staging_chopt.json --force   (skip menu_verified check)
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
FORCE   = "--force"   in sys.argv
non_flag_args = [a for a in sys.argv[1:] if not a.startswith("--")]
if non_flag_args:
    STAGING_FILE = non_flag_args[0]
TODAY   = datetime.date.today().strftime("%-m/%-d/%Y")


def load_staging():
    with open(STAGING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_ingredient_rows(ing_rows):
    """
    Verify every ingredient row to be written has all required context fields.
    Required: Restaurant_ID (0), Restaurant_Name (1), Location (2),
              Dish_ID (3), Dish_Name (4), Ingredient (5).

    Returns (passed: bool, problem_rows: list[str])
    """
    REQUIRED_POSITIONS = {
        0: "Restaurant_ID",
        1: "Restaurant_Name",
        2: "Location",
        3: "Dish_ID",
        4: "Dish_Name",
        5: "Ingredient",
    }
    problems = []
    for row in ing_rows:
        missing = [name for pos, name in REQUIRED_POSITIONS.items()
                   if pos >= len(row) or not str(row[pos]).strip()]
        if missing:
            did = row[3] if len(row) > 3 else "???"
            ing = row[5] if len(row) > 5 else "???"
            problems.append(f"  Dish_ID={did!r}  Ingredient={ing!r}  missing: {missing}")
    return len(problems) == 0, problems


def validate_menu_verification(data):
    """
    Every dish must have "menu_verified": true before it can enter the database.

    A dish is menu_verified only when a canvasser has confirmed it appears
    on the restaurant's current live menu (website, ordering platform, or
    in-person menu). Nutritional PDFs, allergen documents, and secondary
    sources are NOT sufficient — they support existing dishes, they do not
    create them.

    Returns (passed: bool, unverified_dishes: list[str])
    """
    unverified = []
    for dish in data.get("dishes", []):
        if dish.get("menu_verified") is not True:
            unverified.append(
                f"  {dish.get('dish_id', '???')}  {dish.get('dish_name', '(unnamed)')}"
                + (" — menu_verified missing" if "menu_verified" not in dish
                   else " — menu_verified is not true")
            )
    return len(unverified) == 0, unverified


# ── Row builders ──────────────────────────────────────────────────────────────

def build_ingredient_rows(data):
    """
    Writes all 14 Ingredient Details columns in canonical order.
    Column order must match the sheet exactly:
      Restaurant_ID | Restaurant_Name | Location | Dish_ID | Dish_Name |
      Ingredient | Cut_Type | Preparation | Ingredient_Type | Status |
      Version | Ingredient_Source | Allergen_Flags | Component_Role

    HISTORY: The legacy add_dishes.py wrote only [dish_id, ingredient] (2 columns),
    which shifted values into Restaurant_ID and Restaurant_Name columns.
    That bug was fixed when upsert_dishes.py replaced add_dishes.py.
    The validate_ingredient_rows() gate below enforces the full-row requirement
    going forward — any staging file missing required fields will be blocked.
    Do not reduce the column count here under any circumstances.
    """
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
                source = "menu"   # staging pipeline requires menu_verified: true
                allergen_flags = "none"
                role = ""
            else:
                name = ing.get("name", "")
                cut_type = ing.get("cut_type", "none")
                preparation = ing.get("preparation", "none")
                ing_type = ing.get("type", "standard")
                # Ingredient_Source records data collection provenance, not food provenance.
                # All staging dishes require menu_verified: true, so the source is "menu".
                # The staging JSON "source" field describes ingredient origin (house-made,
                # grass-fed, local, etc.) — a different concept that is not stored here.
                source = "menu"
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
            dish.get("allergen_transparency", 5),   # canonical default per CANVASSING_RULES.md
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
            dish.get("status", "Active"),       # Status — defaults Active; set "Inactive" in staging to deactivate
            "",                                 # Version (col 17 — managed in sheet)
            dish.get("category", ""),           # Category (col 18)
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


def check_name_duplicates(ws, data):
    """
    Warn if any dish in staging has the same name as an existing dish
    for the same restaurant (but a different Dish_ID).
    Prints warnings — does not block the upsert.
    """
    all_values = ws.get_all_values()
    headers = all_values[0] if all_values else []
    try:
        name_col = headers.index("Dish_Name")
        did_col  = headers.index("Dish_ID")
        # Dish Level Data tab uses "Restaurant" — fall back to "Restaurant_Name"
        rest_col = headers.index("Restaurant") if "Restaurant" in headers else headers.index("Restaurant_Name")
    except ValueError:
        return  # can't check if columns missing

    existing = {}  # (restaurant_lower, name_lower) -> dish_id
    for row in all_values[1:]:
        r = row[rest_col].strip().lower() if len(row) > rest_col else ""
        n = row[name_col].strip().lower() if len(row) > name_col else ""
        d = row[did_col].strip()          if len(row) > did_col  else ""
        if r and n and d:
            existing[(r, n)] = d

    rname = data["restaurant_name"].lower()
    for dish in data["dishes"]:
        key = (rname, dish["dish_name"].strip().lower())
        if key in existing and existing[key] != dish["dish_id"]:
            print(f"  [WARN] Name collision: '{dish['dish_name']}' already exists as "
                  f"{existing[key]} — staging uses {dish['dish_id']}. "
                  f"Consider updating {existing[key]} instead.")


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

    # ── Menu verification gate ────────────────────────────────────────────────
    passed, unverified = validate_menu_verification(data)
    if not passed:
        print()
        print("=" * 60)
        print("BLOCKED — menu_verified check failed.")
        print()
        print("The following dishes are missing 'menu_verified: true':")
        for line in unverified:
            print(line)
        print()
        print("RULE: A dish must be confirmed on the restaurant's current")
        print("live menu before it can enter the database. Nutritional PDFs")
        print("and allergen documents are supporting sources only — they")
        print("cannot be the sole basis for adding a dish.")
        print()
        print("To fix: add '\"menu_verified\": true' to each dish in your")
        print(f"staging file after confirming it appears on the live menu.")
        print()
        if FORCE:
            print("--force flag detected. Proceeding anyway (legacy file).")
            print("=" * 60)
        else:
            print("Use --force to override for legacy staging files.")
            print("=" * 60)
            sys.exit(1)
    else:
        print(f"Menu verification : ✓ all {n_dishes} dishes verified")

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

    # ── Ingredient row completeness gate ──────────────────────────────────────
    ing_ok, ing_problems = validate_ingredient_rows(ing_rows)
    if not ing_ok:
        print()
        print("=" * 60)
        print("BLOCKED — ingredient rows are missing required context fields.")
        print()
        print("Every Ingredient Details row must be fully self-describing:")
        print("  Restaurant_ID, Restaurant_Name, Location, Dish_ID, Dish_Name, Ingredient")
        print()
        for p in ing_problems:
            print(p)
        print()
        print("Fix the staging file and re-run.")
        print("=" * 60)
        sys.exit(1)
    else:
        print(f"Ingredient row validation : ✓ all {len(ing_rows)} rows complete")

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

    print("\nChecking for name collisions...")
    if not DRY_RUN:
        check_name_duplicates(ss.worksheet("Goldpan Dish Level Data"), data)

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
