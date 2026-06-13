"""
patch_d086.py — One-time patch for Five Grain Salad (D086)

The dinner menu revealed the five grains: farro, barley, wheat berry,
quinoa (already listed), and mixed lettuces as the fifth base.
This script:
  1. Appends the three missing grain rows to Ingredient Details
  2. Updates the Transparency Scoring row (score: 60 → 78, level: Moderate → High)
  3. Updates the allergen summary in Goldpan Dish Level Data (adds wheat from grains)

Usage:
    python3 patch_d086.py
    python3 patch_d086.py --dry-run
"""

import sys
import datetime
import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
DRY_RUN        = "--dry-run" in sys.argv
TODAY          = datetime.date.today().strftime("%-m/%-d/%Y")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Three grain rows to append to Ingredient Details
NEW_INGREDIENT_ROWS = [
    ["R014", "The Essential", "Birmingham, AL", "D086", "Five Grain Salad",
     "farro", "none", "cooked", "standard", "Active", TODAY, "1",
     "Unconfirmed", "plant-based", "none", "base"],
    ["R014", "The Essential", "Birmingham, AL", "D086", "Five Grain Salad",
     "barley", "none", "cooked", "standard", "Active", TODAY, "1",
     "Unconfirmed", "plant-based", "wheat", "base"],
    ["R014", "The Essential", "Birmingham, AL", "D086", "Five Grain Salad",
     "wheat berry", "none", "cooked", "standard", "Active", TODAY, "1",
     "Unconfirmed", "plant-based", "wheat", "base"],
]

# Updated score values for Transparency Scoring
NEW_SCORE = {
    "core_clarity":          38,
    "sauce_disclosure":       5,
    "allergen_transparency": 15,
    "prep_clarity":          15,
    "total_score":           73,
    "transparency_level":    "Moderate Transparency",
    "notes": "All five grains named (farro, barley, wheat berry, quinoa + lettuces); dressing still undisclosed; wheat allergen now visible",
}

# Updated allergen summary for Goldpan Dish Level Data
NEW_ALLERGEN_SUMMARY = "dairy (whipped feta), tree nuts (walnuts), wheat (barley, wheat berry)"


def main():
    if DRY_RUN:
        print("-- DRY RUN — no changes will be written --\n")

    if not DRY_RUN:
        print("Connecting to Google Sheets...")
        creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        ss     = client.open_by_key(SPREADSHEET_ID)

    # ── 1. Append new grain ingredients ──────────────────────────────────────
    print("Step 1: Add grain rows to Ingredient Details")
    if DRY_RUN:
        for r in NEW_INGREDIENT_ROWS:
            print(f"  would append: {r}")
    else:
        ws = ss.worksheet("Ingredient Details")
        ws.append_rows(NEW_INGREDIENT_ROWS, value_input_option="USER_ENTERED")
        print(f"  appended {len(NEW_INGREDIENT_ROWS)} rows")

    # ── 2. Update Transparency Scoring row for D086 ───────────────────────────
    print("\nStep 2: Update Transparency Scoring for D086")
    if DRY_RUN:
        print(f"  would update D086 → score {NEW_SCORE['total_score']}, {NEW_SCORE['transparency_level']}")
    else:
        ws = ss.worksheet("Transparency Scoring")
        records = ws.get_all_records()
        row_num = None
        for i, r in enumerate(records):
            if str(r.get("Dish_ID", "")).strip() == "D086":
                row_num = i + 2  # 1-indexed + header row
                break
        if row_num is None:
            print("  ERROR: D086 not found in Transparency Scoring")
        else:
            # Columns: Restaurant_ID, Restaurant_Name, Dish_ID, Dish_Name,
            #          Core_Clarity, Sauce_Disclosure, Allergen_Transparency,
            #          Prep_Clarity, Total_Score, Transparency_Level, Notes
            ws.update(f"E{row_num}:K{row_num}", [[
                NEW_SCORE["core_clarity"],
                NEW_SCORE["sauce_disclosure"],
                NEW_SCORE["allergen_transparency"],
                NEW_SCORE["prep_clarity"],
                NEW_SCORE["total_score"],
                NEW_SCORE["transparency_level"],
                NEW_SCORE["notes"],
            ]])
            print(f"  updated row {row_num}")

    # ── 3. Update allergen summary in Goldpan Dish Level Data ─────────────────
    print("\nStep 3: Update allergen summary for D086 in Goldpan Dish Level Data")
    if DRY_RUN:
        print(f"  would update allergen summary → '{NEW_ALLERGEN_SUMMARY}'")
    else:
        ws = ss.worksheet("Goldpan Dish Level Data")
        records = ws.get_all_records()
        row_num = None
        for i, r in enumerate(records):
            if str(r.get("Dish_ID", "")).strip() == "D086":
                row_num = i + 2
                break
        if row_num is None:
            print("  ERROR: D086 not found in Goldpan Dish Level Data")
        else:
            # Find the Allergen_summary column index
            headers = ws.row_values(1)
            try:
                col = headers.index("Allergen_summary") + 1
                ws.update_cell(row_num, col, NEW_ALLERGEN_SUMMARY)
                print(f"  updated row {row_num}, col {col}")
            except ValueError:
                print("  ERROR: Allergen_summary column not found")

    print("\nDone. Run update.sh to regenerate dishes.json.")


if __name__ == "__main__":
    main()
