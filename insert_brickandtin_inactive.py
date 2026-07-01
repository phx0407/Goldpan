"""
insert_brickandtin_inactive.py

Inserts D012, D013, D014, D016 into Goldpan Dish Level Data as Inactive.
These are seasonal/legacy Brick & Tin dishes that exist in Transparency
Scoring but never had Dish Level Data rows, causing the build validation
to fail.

D012 — legacy Sesame Chicken Bowl (superseded by D126)
D013 — Crispy Brussels (seasonal, off current menu)
D014 — Fall Harvest Salad (seasonal, off current menu)
D016 — Fall Farro Salad (seasonal, off current menu)
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

RESTAURANT_NAME    = "Brick & Tin Mountain Brook"
LOCATION           = "Mountain Brook, AL"
HOURS              = "Mon–Sun 10:30 AM–8:00 PM"
MENU_LINK          = "https://brickandtin.com/mountain-brook-brick-and-tin-menus"
RESTAURANT_ADDRESS = "2901 Cahaba Rd, Mountain Brook, AL 35223"
RESTAURANT_WEBSITE = "https://brickandtin.com/"

INACTIVE_DISHES = {
    "D012": "Sesame Chicken Bowl",   # legacy — superseded by D126
    "D013": "Crispy Brussels",       # seasonal
    "D014": "Fall Harvest Salad",    # seasonal
    "D016": "Fall Farro Salad",      # seasonal
}


def main():
    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)
    ws     = ss.worksheet("Goldpan Dish Level Data")

    headers = ws.row_values(1)
    try:
        did_col_idx  = headers.index("Dish_ID")
        rid_col_idx  = headers.index("Restaurant_ID")
        rest_col_idx = headers.index("Restaurant")
    except ValueError as e:
        print(f"ERROR: Column not found — {e}")
        return

    all_vals = ws.get_all_values()

    # Find existing DIDs and Brick & Tin restaurant_id
    existing_dids = {
        row[did_col_idx].strip()
        for row in all_vals[1:]
        if len(row) > did_col_idx and row[did_col_idx].strip()
    }

    restaurant_id = ""
    for row in all_vals[1:]:
        if len(row) <= rest_col_idx:
            continue
        if "Brick" in row[rest_col_idx].strip() and len(row) > rid_col_idx:
            restaurant_id = row[rid_col_idx].strip()
            if restaurant_id:
                print(f"Found Restaurant_ID: {restaurant_id}")
                break

    if not restaurant_id:
        # Check Transparency Scoring as fallback
        ts = ss.worksheet("Transparency Scoring")
        ts_h = ts.row_values(1)
        ts_v = ts.get_all_values()
        try:
            ts_rid = ts_h.index("Restaurant_ID")
            ts_rn  = ts_h.index("Restaurant_Name")
            for row in ts_v[1:]:
                if len(row) > ts_rn and "Brick" in row[ts_rn]:
                    if len(row) > ts_rid and row[ts_rid].strip():
                        restaurant_id = row[ts_rid].strip()
                        print(f"Found Restaurant_ID from Scoring: {restaurant_id}")
                        break
        except ValueError:
            pass

    if not restaurant_id:
        restaurant_id = "R004"
        print(f"WARNING: Could not find Restaurant_ID — using fallback {restaurant_id}")

    # Build rows — Status = Inactive
    new_rows = []
    skipped  = []
    for did, name in INACTIVE_DISHES.items():
        if did in existing_dids:
            skipped.append(did)
            continue
        row = [
            restaurant_id,
            RESTAURANT_NAME,
            LOCATION,
            did,
            name,
            "none",        # Dietary_Tags
            "",            # Dietary_Options
            "menu",        # Source
            "unconfirmed", # Confidence
            HOURS,
            MENU_LINK,
            "",            # Price
            RESTAURANT_ADDRESS,
            "Unknown",     # Allergen_summary
            TODAY,         # Last_Updated
            RESTAURANT_WEBSITE,
            "Inactive",    # Status ← key field
            "",            # Version
            "",            # Category
        ]
        new_rows.append(row)
        print(f"  Queued inactive insert: {did} {name}")

    if skipped:
        print(f"Already in sheet (skipped): {', '.join(skipped)}")

    if not new_rows:
        print("Nothing to insert.")
        return

    ws.append_rows(new_rows, value_input_option="USER_ENTERED")
    print(f"\nInserted {len(new_rows)} inactive rows.")
    print("Run: bash update.sh")


if __name__ == "__main__":
    main()
