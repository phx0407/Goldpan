"""
insert_brickandtin_dish_level.py

Inserts the 5 active Brick & Tin dishes into Goldpan Dish Level Data.
These rows were missing — they exist in Transparency Scoring but were
never upserted to Dish Level Data, so allergens/tags/category showed
as Unknown on the site.

Does NOT touch Transparency Scoring or Ingredient Details.
"""

import datetime
import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TODAY          = datetime.date.today().strftime("%Y-%m-%d")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Restaurant metadata
RESTAURANT_NAME    = "Brick & Tin Mountain Brook"
RESTAURANT_DISPLAY = "Brick & Tin"
LOCATION           = "Mountain Brook, AL"
HOURS              = "Mon–Sun 10:30 AM–8:00 PM"
MENU_LINK          = "https://brickandtin.com/mountain-brook-brick-and-tin-menus"
RESTAURANT_ADDRESS = "2901 Cahaba Rd, Mountain Brook, AL 35223"
RESTAURANT_WEBSITE = "https://brickandtin.com/"

# Active dishes to insert
DISHES = {
    "D015": {
        "name":      "Simple Salad",
        "category":  "salad",
        "allergens": "None identified. Contact restaurant to confirm.",
        "tags":      "vegan, gluten-free",
        "price":     "",
    },
    "D111": {
        "name":      "Brisket Panini",
        "category":  "sandwich",
        "allergens": "Wheat (pain de mie flatbread). Contact restaurant to confirm.",
        "tags":      "none",
        "price":     "",
    },
    "D118": {
        "name":      "Classic Salad",
        "category":  "salad",
        "allergens": "Dairy (cheddar, buttermilk ranch), Wheat (croutons). Contact restaurant to confirm.",
        "tags":      "vegetarian",
        "price":     "",
    },
    "D123": {
        "name":      "Pork Belly Lettuce Wraps",
        "category":  "wrap",
        "allergens": "Sesame (sesame glaze), Soy (chili sauce). Contact restaurant to confirm.",
        "tags":      "gluten-free",
        "price":     "",
    },
    "D126": {
        "name":      "Sesame Chicken Bowl",
        "category":  "bowl",
        "allergens": "Tree Nuts (cashews), Sesame, Soy (teriyaki, edamame). Contact restaurant to confirm.",
        "tags":      "gluten-free",
        "price":     "",
    },
}


def main():
    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)
    ws     = ss.worksheet("Goldpan Dish Level Data")

    headers = ws.row_values(1)
    print(f"Headers: {headers}")

    # Find which dishes already have rows (so we don't double-insert)
    all_vals = ws.get_all_values()
    try:
        did_col_idx = headers.index("Dish_ID")
    except ValueError:
        print("ERROR: Dish_ID column not found!")
        return

    existing_dids = {
        row[did_col_idx].strip()
        for row in all_vals[1:]
        if len(row) > did_col_idx and row[did_col_idx].strip()
    }

    # Find Brick & Tin's Restaurant_ID from an existing row
    # (look for any row with matching restaurant name)
    restaurant_id = ""
    try:
        rest_col_idx = headers.index("Restaurant_ID")
        rest_name_idx = headers.index("Restaurant")
        for row in all_vals[1:]:
            if len(row) <= rest_name_idx:
                continue
            rname = row[rest_name_idx].strip()
            if "Brick" in rname and len(row) > rest_col_idx:
                restaurant_id = row[rest_col_idx].strip()
                print(f"Found Restaurant_ID: {restaurant_id} (from row with restaurant={rname!r})")
                break
    except ValueError:
        pass

    if not restaurant_id:
        # Fall back: read from Transparency Scoring tab
        print("Restaurant_ID not found in Dish Level Data — checking Transparency Scoring...")
        ts_ws = ss.worksheet("Transparency Scoring")
        ts_headers = ts_ws.row_values(1)
        ts_vals = ts_ws.get_all_values()
        try:
            ts_rid_idx  = ts_headers.index("Restaurant_ID")
            ts_name_idx = ts_headers.index("Restaurant_Name")
            for row in ts_vals[1:]:
                if len(row) <= ts_name_idx:
                    continue
                rname = row[ts_name_idx].strip()
                if "Brick" in rname and len(row) > ts_rid_idx:
                    restaurant_id = row[ts_rid_idx].strip()
                    print(f"Found Restaurant_ID from Transparency Scoring: {restaurant_id}")
                    break
        except ValueError:
            pass

    if not restaurant_id:
        print("WARNING: Could not determine Restaurant_ID — using 'R001' as fallback")
        restaurant_id = "R001"

    # Build rows to insert
    # Column order from upsert_dishes.py build_dish_level_rows():
    # Restaurant_ID | Restaurant | Location | Dish_ID | Dish_Name |
    # Dietary_Tags | Dietary_Options | Source | Confidence | Hours |
    # Menu_Link | Price | Restaurant_Address | Allergen_summary |
    # Last_Updated | Restaurant_Website | Status | Version | Category
    new_rows = []
    skipped  = []
    for did, dish in DISHES.items():
        if did in existing_dids:
            skipped.append(did)
            continue
        row = [
            restaurant_id,
            RESTAURANT_NAME,
            LOCATION,
            did,
            dish["name"],
            dish["tags"],
            "",              # Dietary_Options
            "menu",          # Source
            "unconfirmed",   # Confidence
            HOURS,
            MENU_LINK,
            dish["price"],
            RESTAURANT_ADDRESS,
            dish["allergens"],
            TODAY,           # Last_Updated
            RESTAURANT_WEBSITE,
            "",              # Status (Active by default / managed in sheet)
            "",              # Version
            dish["category"],
        ]
        new_rows.append(row)
        print(f"  Queued: {did} {dish['name']}")

    if skipped:
        print(f"\nAlready in sheet (skipped): {', '.join(skipped)}")

    if not new_rows:
        print("Nothing to insert.")
        return

    ws.append_rows(new_rows, value_input_option="USER_ENTERED")
    print(f"\nInserted {len(new_rows)} rows into Goldpan Dish Level Data.")
    print("Run: bash update.sh")


if __name__ == "__main__":
    main()
