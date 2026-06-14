"""
patch_metadata.py — Goldpan metadata backfill
Scans Goldpan Dish Level Data and patches:
  - Restaurant-level: Hours, Menu_Link, Restaurant_Address, Restaurant_Website
  - Dish-level (from staging.json): Dietary_Options, Allergen_Summary
  - Dish-level (from DISH_OVERRIDES): Allergen_Summary, Dietary_Options
  - Always: Last_Updated set to today on any patched row

Note: Menu_Price is retained in the sheet as an internal field but is not
published to dishes.json (stripped in fetch_dishes.py).

Matching: Restaurant_ID (col 0) first; restaurant name (col 1) as fallback.
Null state: set menu_price="" and allergen_summary="Discontinued" for delisted dishes.

Add new restaurants to RESTAURANT_METADATA as they are onboarded.
Add per-dish corrections to DISH_OVERRIDES as needed.

Usage:
    python3 patch_metadata.py                        # live update, no staging
    python3 patch_metadata.py --staging staging.json # also patch dish-level fields
    python3 patch_metadata.py --dry-run              # preview only
    python3 patch_metadata.py --staging staging.json --dry-run
"""

import json
import os
import sys
import datetime
import gspread
from google.oauth2.service_account import Credentials

# ── CONFIG ────────────────────────────────────────────────────────────────────

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TAB_NAME       = "Goldpan Dish Level Data"

# ── RESTAURANT METADATA ───────────────────────────────────────────────────────
# Add or update entries here as restaurants are onboarded or corrected.
# Keys are Restaurant_IDs (col 0). Matching is done by Restaurant_ID first;
# if no ID match, the name check (col 1) is used as a fallback.

RESTAURANT_METADATA = {
    "R001": {
        "name_aliases": ["Real & Rosemary", "Real and Rosemary"],
        "restaurant_address":  "1922 29th Ave S, Homewood, AL 35209",
        "restaurant_website":  "https://www.realandrosemary.com",
        "menu_link":           "https://www.realandrosemary.com/menu/",
        "hours":               "Mon-Sat 11am-8pm",
    },
    "R002": {
        "name_aliases": [
            "Yo Chef Surf & Turf Smokehouse",
            "Yo Chef Surf and Turf Smokehouse",
            "Yo Chef Surf & Turf",
            "Yo Chef Surf and Turf",
        ],
        "restaurant_address":  "2201 4th Place W, Birmingham, AL 35204",
        "restaurant_website":  "https://yochefsurfandturf.net/",
        "menu_link":           "https://yochefsurfandturf.net/birmingham-yo-chef-surf-and-turf-smokehouse-food-menu",
        "hours":               "Thur 11am-5am, Fri-Sat 11am-6am, Sun/Tue/Wed 11am-4am",
    },
    "R003": {
        "name_aliases": ["Kale Me Crazy"],
        "restaurant_address":  "1831 28th Ave. South, Ste. 106, Homewood, AL 35209",
        "restaurant_website":  "https://kalemecrazy.net",
        "menu_link":           "https://kalemecrazy.net/menu/",
        "hours":               "",  # not publicly listed
    },
    "R004": {
        "name_aliases": ["Emmy Squared", "Emmy Squared Pizza"],
        "restaurant_address":  "300 Summit Blvd, Birmingham, AL 35243",
        "restaurant_website":  "https://www.emmysquaredpizza.com",
        "menu_link":           "https://www.emmysquaredpizza.com/birmingham-menus/",
        "hours":               "Mon-Wed 4pm-9pm, Thu 11am-9pm, Fri-Sat 11am-10pm, Sun 11am-9pm",
    },
}

# ── DISHES TO DELETE ─────────────────────────────────────────────────────────
# Dish_IDs to remove entirely from all three tabs (delisted / discontinued).
# Rows are deleted in reverse order to avoid index shifting.

DELETE_DISH_IDS = {
    "D007",  # Yo' Beyond Burger — no longer on Yo Chef menu
    "D009",  # Swamp Love Gumbo — no longer on Yo Chef menu
}

# ── DISH OVERRIDES ───────────────────────────────────────────────────────────
# Per-dish corrections keyed by Dish_ID.
# Leave a key out entirely to skip that field for a given dish.

DISH_OVERRIDES = {
    "D001": {
        "menu_price":       "$13.99",
        "allergen_summary": "mustard (sorghum honey mustard)",
    },
    "D003": {
        "menu_price":       "$13.99",
        "allergen_summary": "soy (Impossible patty), wheat (patty, brioche bun)",
    },
    "D005": {
        "menu_price":       "$12.99",
        "allergen_summary": "wheat (pasta), egg (likely in meatballs), dairy (parmesan)",
    },
    "D010": {
        "menu_price":       "$15.00",
        "allergen_summary": "wheat (tortilla, croutons), dairy (parmesan, likely in dressing), egg/fish (likely in caesar dressing)",
    },
    "D017": {
        "menu_price":       "$16.80",
        "allergen_summary": "dairy (cheese blend), wheat (Detroit-style dough)",
        "dietary_options":  "vegan cheese, gluten-free crust available on Sixer (6-slice) upon request (+$4)",
    },
    "D018": {
        "menu_price":       "$18.80",
        "allergen_summary": "dairy (cheese blend), wheat (Detroit-style dough), unknown (house-made red sauce)",
        "dietary_options":  "vegan cheese, gluten-free crust available on Sixer (6-slice) upon request (+$4)",
    },
    "D019": {
        "menu_price":       "$16.80",
        "allergen_summary": "dairy (cheese blend, pecorino), wheat (Detroit-style dough), unknown (vodka sauce)",
        "dietary_options":  "vegan cheese, gluten-free crust available on Sixer (6-slice) upon request (+$4)",
    },
    "D020": {
        "menu_price":       "$21.80",
        "allergen_summary": "dairy (cheese blend, burrata), wheat (Detroit-style dough)",
        "dietary_options":  "vegan cheese, gluten-free crust available on Sixer (6-slice) upon request (+$4)",
    },
    "D021": {
        "menu_price":       "$11.50",
        "allergen_summary": "dairy (blue cheese), tree nuts (cashew), unknown (miso dressing)",
    },
}

# ── END DISH OVERRIDES ────────────────────────────────────────────────────────

# Build a reverse lookup: lowercase name → restaurant_id
_NAME_TO_ID = {}
for rid, meta in RESTAURANT_METADATA.items():
    for alias in meta.get("name_aliases", []):
        _NAME_TO_ID[alias.lower()] = rid

# ── COLUMN INDICES (0-based) in Goldpan Dish Level Data ──────────────────────
COL_RESTAURANT_ID      = 0
COL_RESTAURANT_NAME    = 1
COL_DISH_ID            = 3
COL_DIETARY_OPTIONS    = 6
COL_HOURS              = 9
COL_MENU_LINK          = 10
COL_MENU_PRICE         = 11
COL_RESTAURANT_ADDRESS = 12
COL_ALLERGEN_SUMMARY   = 13
COL_LAST_UPDATED       = 14
COL_RESTAURANT_WEBSITE = 15

# ── END CONFIG ────────────────────────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

DRY_RUN        = "--dry-run" in sys.argv
TODAY          = datetime.date.today().strftime("%-m/%-d/%Y")

# Parse --staging <file> argument
STAGING_FILE = None
if "--staging" in sys.argv:
    idx = sys.argv.index("--staging")
    if idx + 1 < len(sys.argv):
        STAGING_FILE = sys.argv[idx + 1]


def load_dish_lookup(staging_path):
    """
    Returns {dish_id: dish_dict} from staging.json.
    Returns {} if staging_path is None or file not found.
    """
    if not staging_path or not os.path.exists(staging_path):
        return {}
    with open(staging_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    lookup = {}
    for dish in data.get("dishes", []):
        did = dish.get("dish_id", "").strip()
        if did:
            lookup[did] = dish
    print(f"Loaded {len(lookup)} dish(es) from {staging_path}")
    return lookup


def resolve_rid(row):
    """Return matching Restaurant_ID from the metadata dict, or None."""
    rid_cell  = row[COL_RESTAURANT_ID].strip()  if len(row) > COL_RESTAURANT_ID  else ""
    name_cell = row[COL_RESTAURANT_NAME].strip() if len(row) > COL_RESTAURANT_NAME else ""

    if rid_cell in RESTAURANT_METADATA:
        return rid_cell
    return _NAME_TO_ID.get(name_cell.lower())


def cell_addr(row_1indexed, col_0indexed):
    """Convert to A1 notation for batch_update."""
    col_letter = chr(ord('A') + col_0indexed)
    return f"{col_letter}{row_1indexed}"


def delete_dish_rows(ws, dish_ids_to_delete, did_col, label):
    """Delete all rows matching any Dish_ID in dish_ids_to_delete (reverse order)."""
    all_vals = ws.get_all_values()
    to_delete = []
    for i, row in enumerate(all_vals[1:], start=2):
        did = row[did_col].strip() if len(row) > did_col else ""
        if did in dish_ids_to_delete:
            to_delete.append((i, did))
    for row_num, did in sorted(to_delete, reverse=True):
        if DRY_RUN:
            print(f"  {label}: would delete row {row_num} ({did})")
        else:
            ws.delete_rows(row_num)
    return len(to_delete)


def main():
    dish_lookup = load_dish_lookup(STAGING_FILE)

    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    if DRY_RUN:
        print("\n-- DRY RUN — no changes will be written --\n")

    # ── Step 1: Delete discontinued dishes from all three tabs ────────────────
    if DELETE_DISH_IDS:
        print("Deleting discontinued dishes...")
        n  = delete_dish_rows(ss.worksheet("Goldpan Dish Level Data"), DELETE_DISH_IDS, COL_DISH_ID, "Goldpan Dish Level Data")
        n += delete_dish_rows(ss.worksheet("Ingredient Details"),      DELETE_DISH_IDS, 3,            "Ingredient Details")
        n += delete_dish_rows(ss.worksheet("Transparency Scoring"),    DELETE_DISH_IDS, 2,            "Transparency Scoring")
        print(f"  {n} row(s) {'would be ' if DRY_RUN else ''}deleted across all tabs")

    # ── Step 2: Patch metadata on remaining rows ──────────────────────────────
    ws       = ss.worksheet("Goldpan Dish Level Data")
    all_rows = ws.get_all_values()
    data_rows = all_rows[1:]

    updates        = []
    patched_by_rid = {}

    for i, row in enumerate(data_rows):
        sheet_row = i + 2
        did = row[COL_DISH_ID].strip() if len(row) > COL_DISH_ID else ""

        # Skip rows queued for deletion
        if did in DELETE_DISH_IDS:
            continue

        rid = resolve_rid(row)
        if rid is None:
            continue

        meta        = RESTAURANT_METADATA[rid]
        dish        = dish_lookup.get(did, {})
        row_changed = False

        def get_current(col_idx):
            return row[col_idx].strip() if len(row) > col_idx else ""

        def queue(col_idx, new_val, force=False):
            nonlocal row_changed
            if get_current(col_idx) != new_val and (new_val != "" or force):
                updates.append({"range": cell_addr(sheet_row, col_idx), "values": [[new_val]]})
                row_changed = True

        # Restaurant-level fields
        queue(COL_HOURS,              meta["hours"])
        queue(COL_MENU_LINK,          meta["menu_link"])
        queue(COL_RESTAURANT_ADDRESS, meta["restaurant_address"])
        queue(COL_RESTAURANT_WEBSITE, meta["restaurant_website"])

        # Dish-level fields from staging.json (if provided)
        if dish:
            queue(COL_DIETARY_OPTIONS,  dish.get("dietary_options", ""))
            queue(COL_MENU_PRICE,       dish.get("menu_price", ""))
            queue(COL_ALLERGEN_SUMMARY, dish.get("allergen_summary", ""))

        # Dish-level overrides (DISH_OVERRIDES wins over staging)
        override = DISH_OVERRIDES.get(did, {})
        if override:
            if "dietary_options"  in override: queue(COL_DIETARY_OPTIONS,  override["dietary_options"],  force=True)
            if "menu_price"       in override: queue(COL_MENU_PRICE,       override["menu_price"],       force=True)
            if "allergen_summary" in override: queue(COL_ALLERGEN_SUMMARY, override["allergen_summary"], force=True)

        # Always stamp Last_Updated when any field changes
        if row_changed:
            updates.append({"range": cell_addr(sheet_row, COL_LAST_UPDATED), "values": [[TODAY]]})
            patched_by_rid.setdefault(rid, []).append(did or f"row {sheet_row}")

    if not updates:
        print("Nothing to patch — all fields are already up to date.")
        return

    for rid, dish_ids in patched_by_rid.items():
        label = ', '.join(dish_ids[:5]) + ('...' if len(dish_ids) > 5 else '')
        print(f"  {rid}: {len(dish_ids)} row(s)  ({label})")

    print(f"\nTotal cell updates: {len(updates)}")

    if DRY_RUN:
        print("\nDry run complete — no writes made.")
        return

    print("Writing patches to sheet...")
    ws.batch_update(updates, value_input_option="USER_ENTERED")
    print(f"Done. {len(updates)} cells updated on {TODAY}.")


if __name__ == "__main__":
    main()
