"""
backfill_categories.py — Goldpan category backfill
Reads every row in "Goldpan Dish Level Data", infers a category from the
dish name using keyword rules, adds a "Category" column header if missing,
and writes the inferred value into that column.

Dishes that don't match any rule are written as "" so they're easy to spot
and fill manually.

Usage:
    python3 backfill_categories.py            # live run
    python3 backfill_categories.py --dry-run  # preview, no writes
    python3 backfill_categories.py --show-unmatched  # list dishes with no match
"""

import re
import sys
import time
import gspread
from google.oauth2.service_account import Credentials

# ── CONFIG ────────────────────────────────────────────────────────────────────

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TAB_NAME       = "Goldpan Dish Level Data"

# ── END CONFIG ────────────────────────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DRY_RUN       = "--dry-run" in sys.argv
SHOW_UNMATCH  = "--show-unmatched" in sys.argv

# ── Category inference rules ──────────────────────────────────────────────────
# Ordered: more-specific / multi-word patterns first.
# Each entry: (compiled regex, category string)

_RAW_RULES = [
    # Multi-word / specific first
    (r"noodle\s+bowl",              "noodle bowl"),
    (r"pad\s+thai",                 "noodles"),
    (r"lo\s+mein",                  "noodles"),
    (r"mac\s+(&|and)\s+cheese",     "pasta"),
    (r"waffle\s+fries?",            "side"),
    (r"sweet\s+potato\s+fries?",    "side"),
    (r"aca[ií]\s+bowl",             "bowl"),
    (r"rice\s+bowl",                "bowl"),
    (r"grain\s+bowl",               "bowl"),
    (r"poke\s+bowl",                "bowl"),
    (r"burrito\s+bowl",             "bowl"),
    (r"smoothie\s+bowl",            "bowl"),
    (r"chicken\s+sandwich",         "sandwich"),
    (r"grilled\s+cheese",           "sandwich"),
    (r"club\s+sandwich",            "sandwich"),
    (r"egg\s+sandwich",             "sandwich"),
    (r"breakfast\s+sandwich",       "sandwich"),
    # Single-keyword patterns
    (r"\btaco[s]?\b",               "taco"),
    (r"\bburrito[s]?\b",            "burrito"),
    (r"\bquesadilla[s]?\b",         "quesadilla"),
    (r"\benchilada[s]?\b",          "enchilada"),
    (r"\bnachos?\b",                "nachos"),
    (r"\bbowl[s]?\b",               "bowl"),
    (r"\bsalad[s]?\b",              "salad"),
    (r"\bwrap[s]?\b",               "wrap"),
    (r"\bsandwich(es)?\b",          "sandwich"),
    (r"\bsub\b",                    "sandwich"),
    (r"\bhoagie[s]?\b",             "sandwich"),
    (r"\bpanini\b",                 "sandwich"),
    (r"\bburger[s]?\b",             "burger"),
    (r"\bpizza[s]?\b",              "pizza"),
    (r"\bflatbread[s]?\b",          "flatbread"),
    (r"\bplate[s]?\b",              "plate"),
    (r"\bkabob[s]?\b",              "kabob"),
    (r"\bkebab[s]?\b",              "kabob"),
    (r"\bsekuwa\b",                 "sekuwa"),
    (r"\broll[s]?\b",               "roll"),
    (r"\bnoodle[s]?\b",             "noodles"),
    (r"\bramen\b",                  "noodles"),
    (r"\budon\b",                   "noodles"),
    (r"\bpho\b",                    "noodles"),
    (r"\bpasta\b",                  "pasta"),
    (r"\brigatoni\b",               "pasta"),
    (r"\bpenne\b",                  "pasta"),
    (r"\bspaghetti\b",              "pasta"),
    (r"\bfettuccine\b",             "pasta"),
    (r"\blasagna\b",                "pasta"),
    (r"\bsushi\b",                  "sushi"),
    (r"\bsashimi\b",                "sashimi"),
    (r"\bnigiri\b",                 "sushi"),
    (r"\btoast[s]?\b",              "toast"),
    (r"\bwaffle[s]?\b",             "waffle"),
    (r"\bpancake[s]?\b",            "pancakes"),
    (r"\bfrench\s+toast\b",         "french toast"),
    (r"\bomelet(te)?\b",            "omelette"),
    (r"\bscramble[d]?\b",           "eggs"),
    (r"\bfrittata\b",               "eggs"),
    (r"\bsoup[s]?\b",               "soup"),
    (r"\bchili\b",                  "soup"),
    (r"\bbisque\b",                 "soup"),
    (r"\bchowder\b",                "soup"),
    (r"\bstew\b",                   "soup"),
    (r"\bwings?\b",                 "wings"),
    (r"\bslider[s]?\b",             "slider"),
    (r"\bfries?\b",                 "side"),
    (r"\bside[s]?\b",               "side"),
    (r"\bbroccoli\b",               "side"),   # broccoli salad / roasted veg sides
    (r"\bvegetable[s]?\b",          "side"),
    (r"\bveggies?\b",               "side"),
    (r"\bappetizer[s]?\b",          "appetizer"),
    (r"\bstarter[s]?\b",            "appetizer"),
    (r"\bspringer\s+roll",          "appetizer"),
    (r"\bspring\s+roll",            "appetizer"),
    (r"\bdumpling[s]?\b",           "dumpling"),
    (r"\bgyoza\b",                  "dumpling"),
    (r"\bsatay\b",                  "satay"),
    (r"\bsteak[s]?\b",              "steak"),
    (r"\bchop[s]?\b",               "chop"),
    (r"\bribs?\b",                  "ribs"),
    (r"\bbrisket\b",                "bbq"),
    (r"\bpulled\s+pork\b",          "bbq"),
    (r"\bbbq\b",                    "bbq"),
    (r"\bbar-?b-?q\b",              "bbq"),
    (r"\bsmoked\b",                 "bbq"),
    (r"\bsmoothie[s]?\b",           "smoothie"),
    (r"\bjuice[s]?\b",              "juice"),
    (r"\bhummus\b",                 "dip"),
    (r"\bguacamole\b",              "dip"),
    (r"\bdip[s]?\b",                "dip"),
    (r"\bsauce[s]?\b",              "sauce"),
    (r"\brice\b",                   "side"),
    (r"\bpilaf\b",                  "side"),
    (r"\bcoleslaw\b",               "side"),
    (r"\bslaw\b",                   "side"),
    (r"\bfrui[t]?\b",               "side"),
    (r"\bquinoa\b",                 "bowl"),
    (r"\bpita[s]?\b",               "sandwich"),
    (r"\btortilla[s]?\b",           "side"),
    (r"\bnaan\b",                   "bread"),
    (r"\bbread\b",                  "bread"),
    (r"\broll\b",                   "roll"),
    (r"\bcroissant\b",              "sandwich"),
    (r"\bbagel\b",                  "sandwich"),
    (r"\bblt\b",                    "sandwich"),
    (r"\bbalt\b",                   "sandwich"),
    (r"\bcubano\b",                 "sandwich"),
    (r"\bpimento\b",                "sandwich"),
    (r"\bshrimp\b",                 "seafood"),
    (r"\bsalmon\b",                 "seafood"),
    (r"\btuna\b",                   "seafood"),
    (r"\bcatfish\b",                "seafood"),
    (r"\btilapia\b",                "seafood"),
    (r"\bcrab\b",                   "seafood"),
    (r"\blobster\b",                "seafood"),
    (r"\boyster[s]?\b",             "seafood"),
    (r"\bscallop[s]?\b",            "seafood"),
    (r"\bfish\b",                   "seafood"),
    (r"\bchicken\b",                "chicken"),
    (r"\bpork\b",                   "pork"),
    (r"\blamb\b",                   "lamb"),
    (r"\btofu\b",                   "tofu"),
    (r"\bfalafel\b",                "falafel"),
    (r"\bcurry\b",                  "curry"),
    (r"\bbiriyani\b",               "biryani"),
    (r"\bbiryani\b",                "biryani"),
    (r"\bmasala\b",                 "curry"),
    (r"\btikka\b",                  "curry"),
    (r"\bmomo[s]?\b",               "dumpling"),
    (r"\bdosa\b",                   "dosa"),
    (r"\bidle?\b",                  "idli"),
    (r"\bsamosa[s]?\b",             "appetizer"),
    (r"\bchaat\b",                  "appetizer"),
    (r"\bpakora[s]?\b",             "appetizer"),
]

RULES = [(re.compile(pattern, re.IGNORECASE), cat) for pattern, cat in _RAW_RULES]


def infer_category(dish_name: str) -> str:
    """Return the best-match category for a dish name, or '' if unknown."""
    for pattern, cat in RULES:
        if pattern.search(dish_name):
            return cat
    return ""


def api_call_with_retry(fn, *args, retries=4, **kwargs):
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            if e.response.status_code == 429 and attempt < retries - 1:
                wait = 30 * (attempt + 1)
                print(f"  [quota] 429 — waiting {wait}s before retry {attempt + 2}/{retries}...")
                time.sleep(wait)
            else:
                raise


def main():
    print(f"Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)
    ws     = ss.worksheet(TAB_NAME)

    print(f"Reading {TAB_NAME}...")
    all_values = ws.get_all_values()
    if not all_values:
        print("Sheet is empty — nothing to do.")
        return

    headers = all_values[0]

    # Find or determine Category column
    if "Category" in headers:
        cat_col_idx = headers.index("Category")   # 0-indexed
        cat_col_num = cat_col_idx + 1              # 1-indexed (Sheets)
        print(f"  Category column already exists at col {cat_col_num}")
        added_header = False
    else:
        cat_col_idx = len(headers)                 # will be appended
        cat_col_num = cat_col_idx + 1
        print(f"  Category column not found — will add at col {cat_col_num}")
        added_header = True

    # Find Dish_Name column
    if "Dish_Name" not in headers:
        print("ERROR: Dish_Name column not found in headers.")
        print("Headers:", headers)
        return
    name_col_idx = headers.index("Dish_Name")

    # Build updates: list of (row_number_1indexed, category_string)
    updates      = []
    unmatched    = []
    already_set  = 0

    for i, row in enumerate(all_values[1:], start=2):   # row 1 = headers
        dish_name = row[name_col_idx].strip() if len(row) > name_col_idx else ""
        if not dish_name:
            continue

        # Current category value (if column already exists)
        current_cat = ""
        if not added_header and len(row) > cat_col_idx:
            current_cat = row[cat_col_idx].strip()

        if current_cat:
            already_set += 1
            continue

        cat = infer_category(dish_name)
        updates.append((i, dish_name, cat))
        if not cat:
            unmatched.append((i, dish_name))

    # Stats
    data_rows = len(all_values) - 1
    print(f"\n  Total data rows : {data_rows}")
    print(f"  Already have category : {already_set}")
    print(f"  To update : {len(updates)}")
    print(f"  No match (will write blank) : {len(unmatched)}")

    if SHOW_UNMATCH or unmatched:
        print(f"\nDishes with no inferred category ({len(unmatched)}):")
        for row_num, name in unmatched:
            print(f"  row {row_num:4d}  {name}")

    if DRY_RUN:
        print("\n-- DRY RUN — no changes written --")
        print("\nSample inferences (first 40):")
        for row_num, name, cat in updates[:40]:
            marker = "?" if not cat else " "
            print(f"  {marker} row {row_num:4d}  {name!r:55s}  → {cat!r}")
        return

    if not updates and not added_header:
        print("\nNothing to do.")
        return

    # Write header if needed
    if added_header:
        header_cell = gspread.utils.rowcol_to_a1(1, cat_col_num)
        print(f"\nWriting 'Category' header to {header_cell}...")
        api_call_with_retry(ws.update, header_cell, [["Category"]])
        time.sleep(3)

    # Batch-write category values using a single update call
    # Build a list of Cell objects
    print(f"Writing {len(updates)} category values...")
    cell_list = []
    for row_num, dish_name, cat in updates:
        cell_list.append(gspread.Cell(row=row_num, col=cat_col_num, value=cat))

    # gspread update_cells sends one batch request
    if cell_list:
        api_call_with_retry(ws.update_cells, cell_list)

    matched   = sum(1 for _, _, c in updates if c)
    unmatched_count = sum(1 for _, _, c in updates if not c)
    print(f"\nDone.")
    print(f"  Category written   : {matched}")
    print(f"  Left blank (review): {unmatched_count}")
    print(f"\nRun fetch_dishes.py to pull updated data into dishes.json.")


if __name__ == "__main__":
    main()
