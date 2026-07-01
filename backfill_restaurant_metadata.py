"""
backfill_restaurant_metadata.py

Fills in Hours, Menu_Link, Restaurant_Address, and Restaurant_Website
for every empty cell in both the Transparency Scoring and Goldpan Dish
Level Data tabs. Data source: restaurant_coords.json.

Only writes to cells that are currently empty — will not overwrite
existing values.
"""

import json
import os
import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ── Normalize sheet restaurant names to match coords keys ─────────────────────
NAME_MAP = {
    "East West":                   "EastWest",
    "Brick & Tin Mountain Brook":  "Brick & Tin",
    "Brick & Tin Downtown":        "Brick & Tin",
    "Brick & Tin Homewood":        "Brick & Tin",
}

def normalize(name):
    return NAME_MAP.get(name.strip(), name.strip())


def load_coords():
    path = os.path.join(os.path.dirname(__file__), "restaurant_coords.json")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # key by normalized name
    return {normalize(k): v for k, v in raw.items()}


def backfill_tab(ws, coords, restaurant_col_name, tab_label):
    """
    Backfill Hours, Menu_Link, Restaurant_Address, Restaurant_Website
    in `ws`. restaurant_col_name is the header used to find the restaurant.
    Returns number of cells updated.
    """
    headers = ws.row_values(1)
    col = {h: i + 1 for i, h in enumerate(headers)}

    # Columns to fill — map sheet header → coords key
    FIELD_MAP = {
        "Hours":                "hours",
        "Menu_Link":            "menu_link",
        "Restaurant_Address":   "address",
        "Restaurant_Website":   "website",
    }

    # Only process columns that actually exist in this tab
    fillable = {h: coords_key for h, coords_key in FIELD_MAP.items() if h in col}
    if not fillable:
        print(f"  [{tab_label}] No fillable columns found — skipping")
        return 0

    if restaurant_col_name not in col:
        print(f"  [{tab_label}] Restaurant column '{restaurant_col_name}' not found — skipping")
        return 0

    rest_col_idx = col[restaurant_col_name]  # 1-based

    all_rows = ws.get_all_values()
    updates = []
    skipped_names = set()

    for row_i, row in enumerate(all_rows[1:], start=2):
        raw_name = row[rest_col_idx - 1].strip() if len(row) >= rest_col_idx else ""
        if not raw_name:
            continue
        rname = normalize(raw_name)
        if rname not in coords:
            skipped_names.add(raw_name)
            continue

        c = coords[rname]
        for sheet_col, coords_key in fillable.items():
            col_idx = col[sheet_col]
            current = row[col_idx - 1].strip() if len(row) >= col_idx else ""
            value   = c.get(coords_key, "").strip()
            if not current and value:
                updates.append({
                    "range":  gspread.utils.rowcol_to_a1(row_i, col_idx),
                    "values": [[value]],
                })

    if skipped_names:
        print(f"  [{tab_label}] No coords match for: {sorted(skipped_names)}")

    if updates:
        # batch_update has a 40k cell limit per call — chunk if needed
        CHUNK = 500
        for i in range(0, len(updates), CHUNK):
            ws.batch_update(updates[i:i+CHUNK])
        print(f"  [{tab_label}] Filled {len(updates)} empty cells across {len(fillable)} columns")
    else:
        print(f"  [{tab_label}] Nothing to fill — all cells already populated")

    return len(updates)


def main():
    print("Loading restaurant_coords.json...")
    coords = load_coords()
    print(f"  {len(coords)} restaurants loaded")

    print("\nConnecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    total = 0

    # ── Transparency Scoring ──────────────────────────────────────────────────
    print("\nProcessing Transparency Scoring tab...")
    ts_ws = ss.worksheet("Transparency Scoring")
    total += backfill_tab(ts_ws, coords,
                          restaurant_col_name="Restaurant_Name",
                          tab_label="Transparency Scoring")

    # ── Goldpan Dish Level Data ───────────────────────────────────────────────
    print("\nProcessing Goldpan Dish Level Data tab...")
    dl_ws = ss.worksheet("Goldpan Dish Level Data")
    # This tab may use "Restaurant_Name" or "Restaurant" — try both
    dl_headers = dl_ws.row_values(1)
    rest_col = "Restaurant_Name" if "Restaurant_Name" in dl_headers else "Restaurant"
    total += backfill_tab(dl_ws, coords,
                          restaurant_col_name=rest_col,
                          tab_label="Goldpan Dish Level Data")

    print(f"\nDone. Total cells updated: {total}")


if __name__ == "__main__":
    main()
