"""
verify_patches.py
Reads the live Google Sheet and prints the exact values for
Brick & Tin, Emmy Squared, and Wooden City target dishes.
This tells us whether the patch scripts actually wrote to the sheet.
"""

import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
SCOPES         = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

TARGETS = {
    "D015": "Brick & Tin — Simple Salad",
    "D111": "Brick & Tin — Brisket Panini",
    "D118": "Brick & Tin — Classic Salad",
    "D123": "Brick & Tin — Pork Belly Lettuce Wraps",
    "D126": "Brick & Tin — Sesame Chicken Bowl",
    "D021": "Emmy Squared — Shaved Brussels Sprouts Salad",
    "D233": "Emmy Squared — Cheesy Garlic Sticks",
    "D235": "Emmy Squared — Zia Fries",
    "D239": "Emmy Squared — Le Big Matt",
    "D241": "Emmy Squared — Chicken Parm Sandwich",
    "D249": "Emmy Squared — Big Hawaiian Pizza",
    "D354": "Wooden City — Peel n Eat Shrimp",
    "D356": "Wooden City — Autumn Salad",
    "D359": "Wooden City — Blistered Hungarian Peppers",
    "D361": "Wooden City — Wood-Fired Bone Marrow",
    "D364": "Wooden City — Pepperoni Pizza",
    "D366": "Wooden City — Bacon Pesto Pizza",
    "D369": "Wooden City — Fancy Burger",
    "D374": "Wooden City — Seared Scallops",
    "D376": "Wooden City — Beet Ravioli",
    "D379": "Wooden City — Jerk Cauliflower",
    "D384": "Wooden City — Espresso Martini",
}

def main():
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)
    ws     = ss.worksheet("Goldpan Dish Level Data")

    headers  = ws.row_values(1)
    all_vals = ws.get_all_values()

    # Build column index
    def col(name):
        try:
            return headers.index(name)
        except ValueError:
            return None

    did_i      = col("Dish_ID")
    tags_i     = col("Dietary_Tags")
    allergen_i = col("Allergen_summary")
    status_i   = col("Status")
    updated_i  = col("Last_Updated")
    cat_i      = col("Category")

    print(f"Sheet has {len(all_vals)-1} data rows")
    print(f"Columns — Dish_ID:{did_i} Tags:{tags_i} Allergens:{allergen_i} Status:{status_i} Last_Updated:{updated_i} Category:{cat_i}")
    print()

    found = {}
    for row in all_vals[1:]:
        did = row[did_i].strip() if did_i is not None and len(row) > did_i else ""
        if did in TARGETS:
            found[did] = row

    for did, label in TARGETS.items():
        if did not in found:
            print(f"❌ {did} ({label}): NOT FOUND IN SHEET")
        else:
            row = found[did]
            tags     = row[tags_i].strip()     if tags_i     is not None and len(row) > tags_i     else "—"
            allergen = row[allergen_i].strip() if allergen_i is not None and len(row) > allergen_i else "—"
            status   = row[status_i].strip()   if status_i   is not None and len(row) > status_i   else "—"
            updated  = row[updated_i].strip()  if updated_i  is not None and len(row) > updated_i  else "—"
            cat      = row[cat_i].strip()      if cat_i      is not None and len(row) > cat_i      else "—"
            print(f"{'✅' if allergen and allergen.lower() != 'unknown' else '❌'} {did} {label}")
            print(f"   status={status} | tags={repr(tags)} | allergens={repr(allergen[:60])} | last_updated={updated} | category={cat}")
        print()

if __name__ == "__main__":
    main()
