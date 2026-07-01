"""
create_menu_source_registry.py

Creates (or updates) the "Menu Source Registry" tab in the Goldpan spreadsheet.

Rules:
  - If the tab does not exist, it is created and all known restaurants are inserted.
  - If the tab already exists, only MISSING rows are added. Existing rows are
    never overwritten — existing values are always preserved.
  - Pre-populates from restaurant_coords.json for fields we already know.
  - Looks up Restaurant_IDs from Goldpan Dish Level Data.

Gate rule (process documentation):
  No restaurant should enter the GoldPan Dish Level Data process until the
  Menu Source Registry has been completed and validated.

Report printed at end:
  1. Restaurants added (new rows)
  2. Restaurants already present (skipped)
  3. Missing source fields per row
  4. Restaurants in Transparency Scoring with no registry row
  5. Registry rows not found in Transparency Scoring
"""

import json
import os
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

REGISTRY_TAB = "Menu Source Registry"

HEADERS = [
    "Restaurant_ID",
    "Restaurant_Name",
    "Official_Website",
    "Official_Menu_URL",
    "Online_Ordering_URL",
    "PDF_Menu_URL",
    "Allergen_Nutrition_URL",
    "Menu_Format",
    "Last_Verified_Date",
    "Last_Menu_Change_Detected",
    "Source_Confidence",
    "Preferred_Data_Source",
    "Menu_Status",
    "Canvass_Priority",
    "Notes",
]

# Required fields — flagged in the missing-fields report
REQUIRED_FIELDS = {
    "Official_Website",
    "Official_Menu_URL",
    "Source_Confidence",
    "Preferred_Data_Source",
    "Menu_Status",
    "Canvass_Priority",
}

# Known online ordering URLs (not website menus)
ORDERING_URLS = {
    "Brick & Tin": "https://order.toasttab.com/online/brick-tin",
}

# Known allergen/nutrition URLs
ALLERGEN_URLS = {
    "Blue Root": "https://media-cdn.getbento.com/accounts/fc1d22826aaad1786b15c971c7a95214/media/OqW1YgHOS9u4J1ta1Drn_Blueroot%20Nutrition%20Facts.pdf",
}

# Canvass priority — based on current database state and recanvass needs
PRIORITY_MAP = {
    "Abhi Eatery and Bar":              "High",    # 10 dishes with no allergens
    "Brick & Tin":                      "High",    # recanvass in progress; new dishes found
    "Adam and Eve Cafe":                "Low",     # just recanvassed June 27 2026
    "Blue Root":                        "Medium",
    "Cayo Coco Rum Bar & Restaurant":   "Medium",
    "Chopt Creative Salad Co.":         "Medium",
    "EastWest":                         "Medium",
    "Emmy Squared":                     "Medium",
    "Frothy Monkey":                    "Medium",
    "Real & Rosemary":                  "Medium",
    "Slutty Vegan":                     "Medium",
    "The Essential":                    "Medium",
    "Wooden City Birmingham":           "Medium",
    "Yo Chef Surf & Turf Smokehouse":   "Medium",
    "Yo Mama's":                        "Medium",
    "Baha Burger":                      "Medium",
    "Chop N Fresh":                     "Medium",
    "Clean Eatz":                       "Medium",
    "Eli's Jerusalem Grill":            "Medium",
    "Kale Me Crazy":                    "Medium",
    "SoHo Social":                      "Medium",
    "SoHo Standard":                    "Medium",
    "The Battery":                      "Medium",
    "Urban Cookhouse":                  "Medium",
    "Wasabi Juan's":                    "Medium",
}

# Normalize restaurant name variants (matches fetch_dishes.py logic)
NAME_NORMALIZE = {
    "Brick & Tin Mountain Brook": "Brick & Tin",
    "East West": "EastWest",
}


def infer_menu_format(url):
    if not url:
        return ""
    u = url.lower()
    if "toasttab" in u:
        return "Toast"
    if u.endswith(".pdf") or "getbento" in u or "/media/" in u:
        return "PDF"
    return "HTML"


def infer_confidence(url):
    """Simple heuristic — if the URL is on the restaurant's own domain, mark Official."""
    if not url:
        return "Unverified"
    # Aggregators / third-party
    third_party = ["toasttab", "getbento", "yelp", "grubhub", "doordash", "ubereats"]
    if any(t in url.lower() for t in third_party):
        return "Third-Party"
    return "Official"


def build_row(rid, name, coords):
    website   = coords.get("website", "").strip()
    menu_link = coords.get("menu_link", "").strip()

    # Decide which URL goes where
    ordering_url = ORDERING_URLS.get(name, "")
    pdf_url      = ""
    official_menu_url = menu_link

    # If the menu_link is a PDF, put it in PDF_Menu_URL and leave Official_Menu_URL as website
    u = menu_link.lower()
    if u.endswith(".pdf") or "getbento" in u or "/media/" in u:
        pdf_url = menu_link
        official_menu_url = website
    # If the menu_link is a Toast URL, it's an ordering URL not an official menu URL
    elif "toasttab" in u:
        ordering_url = ordering_url or menu_link
        official_menu_url = website

    allergen_url = ALLERGEN_URLS.get(name, "")
    menu_format  = infer_menu_format(official_menu_url or ordering_url or pdf_url)
    confidence   = infer_confidence(official_menu_url)

    # Preferred_Data_Source: the single best URL to use when canvassing
    if official_menu_url and "toasttab" not in official_menu_url.lower():
        preferred = official_menu_url
    elif ordering_url:
        preferred = ordering_url
    elif pdf_url:
        preferred = pdf_url
    else:
        preferred = website

    return [
        rid,                             # Restaurant_ID
        name,                            # Restaurant_Name
        website,                         # Official_Website
        official_menu_url,               # Official_Menu_URL
        ordering_url,                    # Online_Ordering_URL
        pdf_url,                         # PDF_Menu_URL
        allergen_url,                    # Allergen_Nutrition_URL
        menu_format,                     # Menu_Format
        TODAY,                           # Last_Verified_Date
        "",                              # Last_Menu_Change_Detected
        confidence,                      # Source_Confidence
        preferred,                       # Preferred_Data_Source
        "Active",                        # Menu_Status
        PRIORITY_MAP.get(name, "Medium"),# Canvass_Priority
        "",                              # Notes
    ]


def main():
    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    # ── Load restaurant_coords.json ──────────────────────────────────────────
    coords_path = os.path.join(os.path.dirname(__file__), "restaurant_coords.json")
    with open(coords_path, "r", encoding="utf-8") as f:
        coords_data = json.load(f)

    # ── Look up Restaurant_IDs from Goldpan Dish Level Data ─────────────────
    print("Looking up Restaurant_IDs...")
    dl_ws      = ss.worksheet("Goldpan Dish Level Data")
    dl_headers = dl_ws.row_values(1)
    rid_col  = dl_headers.index("Restaurant_ID") + 1
    rnam_col = dl_headers.index("Restaurant") + 1

    rid_by_name = {}
    for row in dl_ws.get_all_values()[1:]:
        if len(row) < max(rid_col, rnam_col):
            continue
        rname = NAME_NORMALIZE.get(row[rnam_col - 1].strip(), row[rnam_col - 1].strip())
        rid   = row[rid_col - 1].strip()
        if rname and rid and rname not in rid_by_name:
            rid_by_name[rname] = rid

    # ── Load Transparency Scoring restaurant names ───────────────────────────
    print("Reading Transparency Scoring...")
    ts_ws       = ss.worksheet("Transparency Scoring")
    ts_headers  = ts_ws.row_values(1)
    ts_rname_col = ts_headers.index("Restaurant_Name") + 1
    scoring_restaurants = set()
    for row in ts_ws.get_all_values()[1:]:
        if len(row) >= ts_rname_col:
            rn = NAME_NORMALIZE.get(row[ts_rname_col - 1].strip(), row[ts_rname_col - 1].strip())
            if rn:
                scoring_restaurants.add(rn)

    # ── Get or create the registry tab ──────────────────────────────────────
    tab_existed = True
    try:
        reg_ws = ss.worksheet(REGISTRY_TAB)
        print(f'Tab "{REGISTRY_TAB}" already exists — updating missing rows only.')
    except gspread.exceptions.WorksheetNotFound:
        tab_existed = False
        print(f'Creating new tab "{REGISTRY_TAB}"...')
        reg_ws = ss.add_worksheet(title=REGISTRY_TAB, rows=100, cols=len(HEADERS))

    # ── Write headers if tab is new ──────────────────────────────────────────
    if not tab_existed:
        reg_ws.update([HEADERS], "A1")

    # ── Read existing rows ───────────────────────────────────────────────────
    existing_vals    = reg_ws.get_all_values()
    existing_headers = existing_vals[0] if existing_vals else []

    # Map restaurant name → row index (1-based, header is row 1)
    existing_by_name = {}
    if len(existing_vals) > 1:
        try:
            name_col_idx = existing_headers.index("Restaurant_Name")
        except ValueError:
            name_col_idx = 1  # fallback
        for i, row in enumerate(existing_vals[1:], start=2):
            if len(row) > name_col_idx:
                existing_by_name[row[name_col_idx].strip()] = i

    # ── Build new rows for restaurants not yet in registry ──────────────────
    added    = []
    skipped  = []
    new_rows = []

    for name, coords in coords_data.items():
        rid = rid_by_name.get(name, "")
        if name in existing_by_name:
            skipped.append(name)
            continue
        row = build_row(rid, name, coords)
        new_rows.append(row)
        added.append(name)

    if new_rows:
        reg_ws.append_rows(new_rows, value_input_option="USER_ENTERED")

    # ── Reload registry for missing-field audit ──────────────────────────────
    reg_vals = reg_ws.get_all_values()
    reg_headers = reg_vals[0] if reg_vals else HEADERS
    missing_fields_report = {}

    if len(reg_vals) > 1:
        for row in reg_vals[1:]:
            # Pad row to header length
            padded = row + [""] * (len(reg_headers) - len(row))
            name   = padded[reg_headers.index("Restaurant_Name")] if "Restaurant_Name" in reg_headers else ""
            if not name:
                continue
            missing = []
            for field in REQUIRED_FIELDS:
                if field in reg_headers:
                    val = padded[reg_headers.index(field)].strip()
                    if not val:
                        missing.append(field)
            if missing:
                missing_fields_report[name] = missing

    # ── Cross-check: Scoring ↔ Registry ─────────────────────────────────────
    registry_names = {
        row[reg_headers.index("Restaurant_Name")].strip()
        for row in reg_vals[1:]
        if len(row) > reg_headers.index("Restaurant_Name")
        and row[reg_headers.index("Restaurant_Name")].strip()
    } if len(reg_vals) > 1 else set()

    scoring_not_in_registry = scoring_restaurants - registry_names
    registry_not_in_scoring = registry_names - scoring_restaurants

    # ── Print report ─────────────────────────────────────────────────────────
    print()
    print("=" * 65)
    print("  MENU SOURCE REGISTRY — BUILD REPORT")
    print("=" * 65)

    print(f"\n✅  Restaurants added ({len(added)}):")
    for n in sorted(added):
        print(f"      {n}")
    if not added:
        print("      (none)")

    print(f"\n⏭   Restaurants already present / skipped ({len(skipped)}):")
    for n in sorted(skipped):
        print(f"      {n}")
    if not skipped:
        print("      (none)")

    print(f"\n⚠️   Rows with missing required fields ({len(missing_fields_report)}):")
    for n, fields in sorted(missing_fields_report.items()):
        print(f"      {n}")
        for f in fields:
            print(f"        — {f}")
    if not missing_fields_report:
        print("      (none — all required fields populated)")

    print(f"\n🔴  In Transparency Scoring but NOT in registry ({len(scoring_not_in_registry)}):")
    for n in sorted(scoring_not_in_registry):
        print(f"      {n}")
    if not scoring_not_in_registry:
        print("      (none — registry is complete)")

    print(f"\n🔵  In registry but NOT in Transparency Scoring ({len(registry_not_in_scoring)}):")
    for n in sorted(registry_not_in_scoring):
        print(f"      {n}")
    if not registry_not_in_scoring:
        print("      (none)")

    print()
    print("=" * 65)
    print(f"  Tab: \"{REGISTRY_TAB}\"  |  {len(registry_names)} total rows")
    print("=" * 65)
    print()


if __name__ == "__main__":
    main()
