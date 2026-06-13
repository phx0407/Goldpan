"""
add_dishes.py — Goldpan Sheet writer
Reads staging.json (produced by canvassing) and appends rows to three
tabs in the Goldpan MVP spreadsheet:
  - Ingredient Details
  - Transparency Scoring
  - Goldpan Dish Level Data

Usage:
    python3 add_dishes.py
    python3 add_dishes.py --dry-run   (preview rows, don't write)

staging.json format:
{
  "restaurant_id": "R014",
  "restaurant_name": "Essential",
  "location": "Birmingham, AL",
  "dishes": [
    {
      "dish_id": "D090",
      "dish_name": "Avocado Toast",
      "dietary_tags": "vegan",
      "allergen_summary": "wheat (bread), unknown (toppings)",
      "transparency_level": "Building Transparency",
      "core_clarity": 25,
      "sauce_disclosure": 5,
      "allergen_transparency": 5,
      "prep_clarity": 5,
      "total_score": 40,
      "notes": "Bread compound, toppings vague",
      "ingredients": [
        {
          "name": "avocado",
          "cut_type": "none",
          "preparation": "raw",
          "type": "standard",
          "source": "plant-based",
          "allergen_flags": "none",
          "role": "base"
        }
      ]
    }
  ]
}
"""

import json
import sys
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


def build_ingredient_rows(data):
    """One row per ingredient across all dishes."""
    rows = []
    rid   = data["restaurant_id"]
    rname = data["restaurant_name"]
    loc   = data["location"]
    for dish in data["dishes"]:
        for ing in dish.get("ingredients", []):
            rows.append([
                rid,
                rname,
                loc,
                dish["dish_id"],
                dish["dish_name"],
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
    """One row per dish."""
    rows = []
    rid   = data["restaurant_id"]
    rname = data["restaurant_name"]
    for dish in data["dishes"]:
        rows.append([
            rid,
            rname,
            dish["dish_id"],
            dish["dish_name"],
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
    """One row per dish."""
    rows = []
    rid   = data["restaurant_id"]
    rname = data["restaurant_name"]
    loc   = data["location"]
    for dish in data["dishes"]:
        rows.append([
            rid,
            rname,
            loc,
            dish["dish_id"],
            dish["dish_name"],
            dish.get("dietary_tags", "none"),
            dish.get("dietary_options", ""),      # Dietary_Options
            "menu",                               # Tag_Source
            "unconfirmed",                        # Verification_Status
            data.get("hours", ""),                # Hours
            data.get("menu_link", ""),            # Menu_Link
            dish.get("menu_price", ""),           # Menu_Price
            data.get("restaurant_address", ""),   # Restaurant_Address
            dish.get("allergen_summary", "Unknown"),
            TODAY,                                # Last_Updated
            data.get("restaurant_website", ""),   # Restaurant_Website
        ])
    return rows


def append_rows(sheet, rows, label):
    if not rows:
        print(f"  {label}: no rows to add")
        return
    if DRY_RUN:
        print(f"  {label}: would append {len(rows)} rows")
        for r in rows:
            print(f"    {r}")
        return
    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"  {label}: appended {len(rows)} rows")


def main():
    print(f"Loading {STAGING_FILE}...")
    data = load_staging()

    rname     = data["restaurant_name"]
    n_dishes  = len(data["dishes"])
    n_ing     = sum(len(d.get("ingredients", [])) for d in data["dishes"])
    print(f"Restaurant : {rname}")
    print(f"Dishes     : {n_dishes}")
    print(f"Ingredients: {n_ing}")

    if DRY_RUN:
        print("\n-- DRY RUN — no changes will be written --\n")

    ing_rows   = build_ingredient_rows(data)
    score_rows = build_scoring_rows(data)
    dish_rows  = build_dish_level_rows(data)

    if not DRY_RUN:
        print("\nConnecting to Google Sheets...")
        creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        ss     = client.open_by_key(SPREADSHEET_ID)

    print("\nWriting...")
    if DRY_RUN:
        append_rows(None, ing_rows,   "Ingredient Details")
        append_rows(None, score_rows, "Transparency Scoring")
        append_rows(None, dish_rows,  "Goldpan Dish Level Data")
    else:
        append_rows(ss.worksheet("Ingredient Details"),    ing_rows,   "Ingredient Details")
        append_rows(ss.worksheet("Transparency Scoring"),  score_rows, "Transparency Scoring")
        append_rows(ss.worksheet("Goldpan Dish Level Data"), dish_rows, "Goldpan Dish Level Data")

    print(f"\nDone. Run update.sh to regenerate dishes.json and push.")


if __name__ == "__main__":
    main()
