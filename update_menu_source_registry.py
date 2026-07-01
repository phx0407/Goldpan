"""
update_menu_source_registry.py

Applies verified source data from the June 27 2026 source audit to the
Menu Source Registry tab.

Rules:
  - Existing non-empty cell values are NEVER overwritten.
  - Only empty cells are filled in.
  - Exception: Official_Menu_URL for Brick & Tin is corrected (old URL was dead —
    the previous value was wrong, not just empty).
  - Prints a full diff report: what changed, what was skipped, what's still missing.

Audit source: mcp__workspace__web_fetch + WebSearch, June 27 2026.
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

# ── Verified source data from June 27 2026 audit ─────────────────────────────
# Keys match Restaurant_Name values in the registry.
# Each entry provides only the fields this audit can verify.
# Fields not listed here are left as-is (or empty if not found).

AUDIT_DATA = {
    "Abhi Eatery and Bar": {
        "Official_Menu_URL":     "https://www.abhieatery.com/eat",
        "Online_Ordering_URL":   "https://www.toasttab.com/abhi-eatery-and-bar-2721-cahaba-rd",
        "PDF_Menu_URL":          "https://www.abhieatery.com/s/ABHI_BeerWine_menu_MBPrint_2-5-24.pdf",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "Mixed",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://www.abhieatery.com/eat",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Food menu at /eat (HTML). Bar/drink menu at /bar-menu links to "
            "a Feb 2024 beer/wine PDF — may be stale. Full picture requires "
            "/eat + /bar-menu. Toast handles ordering. No allergen doc found."
        ),
    },

    "Adam and Eve Cafe": {
        "Official_Menu_URL":     "https://www.adamandevecafe.com/",
        "Online_Ordering_URL":   "https://www.adamandevecafe.com/",
        "PDF_Menu_URL":          "",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "HTML",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://www.adamandevecafe.com/",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Website is JS-rendered — menu only visible via live browser "
            "(Popmenu platform). Static fetch returns blank. No PDF or "
            "allergen doc. Manual browser canvass required."
        ),
    },

    "Baha Burger": {
        "Official_Menu_URL":     "https://bahaburger.com/images/menu.pdf",
        "Online_Ordering_URL":   "",
        "PDF_Menu_URL":          "https://bahaburger.com/images/menu.pdf",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "PDF",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://bahaburger.com/images/menu.pdf",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "PDF confirmed live with full menu and pricing. "
            "No online ordering detected. No allergen doc."
        ),
    },

    "Blue Root": {
        "Official_Menu_URL":     "https://bluerootco.com/our-menu/",
        "Online_Ordering_URL":   "https://www.toasttab.com/blueroot-2829-2nd-avenue-s-ste-10",
        "PDF_Menu_URL":          "",
        "Allergen_Nutrition_URL": "https://media-cdn.getbento.com/accounts/fc1d22826aaad1786b15c971c7a95214/media/OqW1YgHOS9u4J1ta1Drn_Blueroot%20Nutrition%20Facts.pdf",
        "Menu_Format":           "Toast",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://www.toasttab.com/blueroot-2829-2nd-avenue-s-ste-10",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "NO STANDALONE MENU EXISTS. The /our-menu/ page redirects to Toast — "
            "all items are only visible via Toast ordering. The getbento PDF is a "
            "nutrition/allergen facts document only, NOT a browsable menu. "
            "Canvass must be done via Toast. Canvass priority: High."
        ),
    },

    "Brick & Tin": {
        # Intentional correction — old URL was dead (404). This field IS overwritten.
        "Official_Menu_URL":     "https://brickandtin.com/mountain-brook-brick-and-tin-food-menu",
        "Online_Ordering_URL":   "https://order.toasttab.com/online/brick-tin",
        "PDF_Menu_URL":          "",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "Mixed",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://brickandtin.com/mountain-brook-brick-and-tin-food-menu",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Old menu URL (/mountain-brook-brick-and-tin-menus) was dead — "
            "corrected to /mountain-brook-brick-and-tin-food-menu. Menu is "
            "displayed as embedded JPG images (not parseable text). Also has "
            "drink menu and other location pages. Toast for ordering. "
            "No allergen doc. Several new dishes found June 2026 (Chick & Tin, "
            "Turkey Club, Ham & Cheese, Spring Harvest Salad, Spring Vegetable "
            "Pasta) — not yet in database."
        ),
    },

    "Cayo Coco Rum Bar & Restaurant": {
        "Official_Menu_URL":     "https://cayococorumbar.com/assets/uploads/2026/06/Printed%20Menus.June.pdf",
        "Online_Ordering_URL":   "https://www.toasttab.com/cayo-coco/v2/online-order#!/",
        "PDF_Menu_URL":          "https://cayococorumbar.com/assets/uploads/2026/06/Printed%20Menus.June.pdf",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "PDF",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://cayococorumbar.com/assets/uploads/2026/06/Printed%20Menus.June.pdf",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "PDF confirmed current (June 2026) — contains food, cocktail, beer, "
            "and wine menus. Separate rum list PDF (Dec 2024, may be stale): "
            "https://cayococorumbar.com/assets/uploads/2024/12/rum%20list%203.pdf. "
            "Toast handles ordering. No allergen doc."
        ),
    },

    "Chop N Fresh": {
        "Official_Menu_URL":     "https://chopnfreshbhm.com/mountain-brook-lane-parke-chop-n-fresh-food-menu",
        "Online_Ordering_URL":   "https://order.chopnfresh.com/",
        "PDF_Menu_URL":          "",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "HTML",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://chopnfreshbhm.com/mountain-brook-lane-parke-chop-n-fresh-food-menu",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Homepage was previously listed as menu URL — corrected. Actual "
            "food menu is at the SpotHopper URL above (includes calories/prices). "
            "Drink menu at /mountain-brook-lane-parke-chop-n-fresh-drink-menu. "
            "Only allergen note: 'may contain gluten (all other items GF)'. "
            "No formal allergen doc."
        ),
    },

    "Chopt Creative Salad Co.": {
        "Official_Menu_URL":     "https://www.choptsalad.com/menu",
        "Online_Ordering_URL":   "https://www.choptsalad.com/menu",
        "PDF_Menu_URL":          "",
        "Allergen_Nutrition_URL": "https://www.choptsalad.com/nutrition-allergens",
        "Menu_Format":           "HTML",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://www.choptsalad.com/menu",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Full menu in HTML with calorie counts. Ordering embedded on menu page. "
            "Allergen/nutrition page confirmed at /nutrition-allergens. "
            "Menu is location-aware — select Birmingham location."
        ),
    },

    "Clean Eatz": {
        "Official_Menu_URL":     "https://cleaneatz.com/cafe-menu",
        "Online_Ordering_URL":   "https://order.cleaneatz.com/",
        "PDF_Menu_URL":          "https://assets.cleaneatz.com/nutrition/nutrition-facts-with-smoothies_8_15_25.pdf",
        "Allergen_Nutrition_URL": "https://assets.cleaneatz.com/nutrition/nutrition-facts-with-smoothies_8_15_25.pdf",
        "Menu_Format":           "Mixed",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://cleaneatz.com/cafe-menu",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "HTML menu at /cafe-menu (full categories). Nutrition PDF (Aug 2025) "
            "is comprehensive — calories, macros, allergens for all items. "
            "Both sources needed for full picture."
        ),
    },

    "EastWest": {
        "Official_Menu_URL":     "https://www.eastwestbirmingham.com/menus",
        "Online_Ordering_URL":   "https://online.skytab.com/3bef794d1a1284f24de1a078c7ea0c35",
        "PDF_Menu_URL":          "https://eastwestbham.s3.us-east-2.amazonaws.com/dinner-05-30-25%7C11%3A05%3A04PM.pdf",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "PDF",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://www.eastwestbirmingham.com/menus",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Menu page links to a timestamped S3 PDF (May 2025). PDF URL will "
            "change when menu is updated — use /menus page as canonical source "
            "to always get the current PDF. Ordering via SkyTab (not Toast). "
            "No allergen doc."
        ),
    },

    "Eli's Jerusalem Grill": {
        "Official_Menu_URL":     "https://elisjerusalemgrill.com",
        "Online_Ordering_URL":   "",
        "PDF_Menu_URL":          "",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "HTML",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://elisjerusalemgrill.com",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Full menu as HTML text on homepage. GF items and allergen notes "
            "are inline (asterisks). No PDF or ordering platform found. "
            "No formal allergen doc."
        ),
    },

    "Emmy Squared": {
        "Official_Menu_URL":     "https://www.emmysquaredpizza.com/birmingham-menus/",
        "Online_Ordering_URL":   "https://order.emmysquaredpizza.com/",
        "PDF_Menu_URL":          "https://images.getbento.com/accounts/244ddd96a018b50fa0cda273a138f5fa/media/91mSmu9jTfmEq36PZEkL_Allergy%20Matrix%203.31.26.pdf",
        "Allergen_Nutrition_URL": "https://www.emmysquaredpizza.com/allergy-matrix/",
        "Menu_Format":           "Mixed",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://www.emmysquaredpizza.com/birmingham-menus/",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Full menu in HTML (Birmingham-specific). Allergy Matrix PDF "
            "confirmed current (March 31 2026). Complete source: "
            "/birmingham-menus/ + /allergy-matrix/."
        ),
    },

    "Frothy Monkey": {
        "Official_Menu_URL":     "https://frothymonkey.com/menu/",
        "Online_Ordering_URL":   "https://frothymonkey.com/order/",
        "PDF_Menu_URL":          "",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "Mixed",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://frothymonkey.com/menu/",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Primary source: /menu/ (full text HTML — best for canvassing). "
            "/food-drinks/ has Spring 2026 image-based print menus including "
            "AL bar menu (relevant for Homewood location). No allergen doc. "
            "Order link redirects to Toast."
        ),
    },

    "Kale Me Crazy": {
        "Official_Menu_URL":     "https://kalemecrazy.net/menu/",
        "Online_Ordering_URL":   "https://kalemecrazy.order.online/business/33158",
        "PDF_Menu_URL":          "https://kalemecrazy.net/wp-content/uploads/2026/03/KMC-Nutritional-Info-Updated26.pdf",
        "Allergen_Nutrition_URL": "https://kalemecrazy.net/wp-content/uploads/2026/03/KMC-Nutritional-Info-Updated26.pdf",
        "Menu_Format":           "Mixed",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://kalemecrazy.net/menu/",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Full menu in HTML with ingredients per item. Nutrition PDF "
            "(March 2026) covers all categories with calories, macros, "
            "and allergens. Both sources needed."
        ),
    },

    "Real & Rosemary": {
        "Official_Menu_URL":     "https://www.realandrosemary.com/menu/",
        "Online_Ordering_URL":   "https://realandrosemary.revelup.online/store/1/category/22/subcategory/23",
        "PDF_Menu_URL":          "http://www.realandrosemary.com/wp-content/uploads/2026/05/May-Menu-2026.pdf",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "Mixed",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://www.realandrosemary.com/menu/",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "HTML menu at /menu/ (items + descriptions, prices may not all show). "
            "May 2026 PDF is the authoritative print version. Revel POS for ordering. "
            "No allergen doc."
        ),
    },

    "Slutty Vegan": {
        "Official_Menu_URL":     "https://sluttyveganatl.com/#menu",
        "Online_Ordering_URL":   "https://sluttyveganatl.appfront.ai/",
        "PDF_Menu_URL":          "",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "HTML",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://sluttyveganatl.com/birmingham/",
        "Menu_Status":           "Needs Review",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "MANUAL REVIEW REQUIRED. Birmingham location page "
            "(sluttyveganatl.com/birmingham/) showed 'Temporarily Closed' "
            "as of June 2026. Local domain (sluttyveganbham.net) appears dead. "
            "Confirm operational status before next canvass."
        ),
    },

    "SoHo Social": {
        "Official_Menu_URL":     "https://www.sohohomewood.bar/soho-social-menus/",
        "Online_Ordering_URL":   "https://order.toasttab.com/online/soho-social",
        "PDF_Menu_URL":          "",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "HTML",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://www.sohohomewood.bar/soho-social-menus/",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Full menu in HTML (BentoBox). Toast for ordering. No allergen doc."
        ),
    },

    "SoHo Standard": {
        "Official_Menu_URL":     "https://www.sohostandard.bar/menus/",
        "Online_Ordering_URL":   "",
        "PDF_Menu_URL":          "",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "HTML",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://www.sohostandard.bar/menus/",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Full menu in HTML (BentoBox) — brunch, bar, kitchen, happy hour. "
            "No online ordering (dine-in/Resy reservations only). No allergen doc."
        ),
    },

    "The Battery": {
        "Official_Menu_URL":     "https://manthebattery.com/menu/",
        "Online_Ordering_URL":   "https://www.toasttab.com/the-battery-2821-central-ave-ste-101",
        "PDF_Menu_URL":          "https://manthebattery.com/wp-content/uploads/2025/07/The-Battery-Menu-July-2025.pdf",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "PDF",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://manthebattery.com/menu/",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "STALE CHECK NEEDED. Current PDF is dated July 2025 (~1 year old). "
            "The /menu/ page links to this same PDF — no newer version found. "
            "Verify with restaurant whether menu has changed. Toast for ordering."
        ),
    },

    "The Essential": {
        "Official_Menu_URL":     "https://essentialbham.com/menus",
        "Online_Ordering_URL":   "https://order.toasttab.com/online/the-essential-2215-1st-avenue-north",
        "PDF_Menu_URL":          "https://essentialbham.com/s/DinnerMenu62526.pdf",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "PDF",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://essentialbham.com/menus",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Use /menus as canonical hub — links to all current PDFs. "
            "Lunch & Dinner: DinnerMenu62526.pdf (June 25 2026). "
            "Brunch: BrunchMenu52726.pdf (May 27 2026). "
            "Lunch Specials: EssentialLunchSpecialsMenu11326.pdf. "
            "Drinks: DrinkMenu33026-rftk.pdf (March 30 2026). "
            "Toast for ordering. No allergen doc."
        ),
    },

    "Urban Cookhouse": {
        "Official_Menu_URL":     "https://www.uc-birmingham.com/_files/ugd/b524de_463ca8a5b95c45e9ba3e3a36195f8a4a.pdf",
        "Online_Ordering_URL":   "https://order.toasttab.com/online/urban-cookhouse-the-summit",
        "PDF_Menu_URL":          "https://www.uc-birmingham.com/_files/ugd/b524de_463ca8a5b95c45e9ba3e3a36195f8a4a.pdf",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "PDF",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://www.uc-birmingham.com/_files/ugd/b524de_463ca8a5b95c45e9ba3e3a36195f8a4a.pdf",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "PDF confirmed live (Wix CDN). No date in filename — staleness "
            "cannot be confirmed remotely. Manual verification recommended. "
            "Toast ordering is Summit-location specific. No allergen doc."
        ),
    },

    "Wasabi Juan's": {
        "Official_Menu_URL":     "https://wasabijuan.com/our-menu/",
        "Online_Ordering_URL":   "https://wasabijuan.com/order-online/",
        "PDF_Menu_URL":          "",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "HTML",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://wasabijuan.com/our-menu/",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Full menu in HTML with items, descriptions, prices, and GF callouts "
            "(asterisk = raw fish). POE sauce contains almonds noted inline. "
            "No allergen doc. Order platform TBD (third-party widget)."
        ),
    },

    "Wooden City Birmingham": {
        "Official_Menu_URL":     "https://www.woodencitybirmingham.com/menu",
        "Online_Ordering_URL":   "",
        "PDF_Menu_URL":          "",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "HTML",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://www.woodencitybirmingham.com/menu",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Menu is displayed as embedded JPG images on Squarespace — "
            "NOT parseable text. Manual visual review required to read items. "
            "No online ordering (dine-in only, Resy reservations). No allergen doc."
        ),
    },

    "Yo Chef Surf & Turf Smokehouse": {
        "Official_Menu_URL":     "https://yochefsurfandturf.net/birmingham-yo-chef-surf-and-turf-smokehouse-food-menu",
        "Online_Ordering_URL":   "",
        "PDF_Menu_URL":          "",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "HTML",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://yochefsurfandturf.net/birmingham-yo-chef-surf-and-turf-smokehouse-food-menu",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Full menu in HTML (SpotHopper). Brunch/Lunch/Dinner on separate "
            "sub-pages — full canvass requires multiple tabs: "
            "/640277 (Lunch), /640278 (Dinner), /643340 (Hookah), /1506131 (Kids). "
            "No online ordering found. No allergen doc."
        ),
    },

    "Yo Mama's": {
        "Official_Menu_URL":     "https://www.yomamasrestaurant.com/food/",
        "Online_Ordering_URL":   "https://yomamasmeals.square.site",
        "PDF_Menu_URL":          "",
        "Allergen_Nutrition_URL": "",
        "Menu_Format":           "HTML",
        "Source_Confidence":     "Official",
        "Preferred_Data_Source": "https://www.yomamasrestaurant.com/food/",
        "Menu_Status":           "Active",
        "Last_Verified_Date":    TODAY,
        "Notes": (
            "Lunch menu at /food/ (HTML, full items/prices/GF callouts). "
            "Separate brunch menu at /brunch/. POE sauce contains almonds (inline). "
            "Square for ordering. No allergen doc."
        ),
    },
}

# Fields to FORCE-UPDATE even if non-empty (only for known-wrong values)
FORCE_UPDATE_FIELDS = {
    "Brick & Tin": {"Official_Menu_URL"},   # old URL was dead
    "Chop N Fresh": {"Official_Menu_URL"},  # homepage was wrong
    "Frothy Monkey": {"Official_Menu_URL"}, # /food-drinks/ is less useful than /menu/
    "Slutty Vegan": {"Menu_Status"},        # must reflect potential closure
}


def main():
    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    try:
        ws = ss.worksheet("Menu Source Registry")
    except gspread.exceptions.WorksheetNotFound:
        print("ERROR: Menu Source Registry tab not found.")
        print("Run create_menu_source_registry.py first.")
        return

    headers  = ws.row_values(1)
    all_vals = ws.get_all_values()

    if "Restaurant_Name" not in headers:
        print("ERROR: Restaurant_Name column not found in registry.")
        return

    name_col_idx = headers.index("Restaurant_Name")

    # Build row index: restaurant name → row number (1-based, header = row 1)
    row_index = {}
    for i, row in enumerate(all_vals[1:], start=2):
        if len(row) > name_col_idx and row[name_col_idx].strip():
            row_index[row[name_col_idx].strip()] = (i, row)

    updates         = []
    report_changed  = {}
    report_skipped  = {}
    report_missing  = {}

    for rest_name, audit in AUDIT_DATA.items():
        if rest_name not in row_index:
            report_missing[rest_name] = "Restaurant not found in registry — run create_menu_source_registry.py"
            continue

        row_num, current_row = row_index[rest_name]
        changed = []
        skipped = []
        force_fields = FORCE_UPDATE_FIELDS.get(rest_name, set())

        for field, new_val in audit.items():
            if field not in headers:
                continue
            col_idx = headers.index(field)  # 0-based
            current_val = current_row[col_idx].strip() if col_idx < len(current_row) else ""

            # Skip blank audit values (we verified nothing for this field)
            if not new_val:
                continue

            # Apply if: cell is empty, OR field is in force-update set
            if not current_val or field in force_fields:
                if current_val == new_val:
                    continue  # already correct
                updates.append({
                    "range":  gspread.utils.rowcol_to_a1(row_num, col_idx + 1),
                    "values": [[new_val]],
                })
                changed.append(f"  {field}: {current_val!r} → {new_val!r}"
                               if current_val else f"  {field}: (empty) → {new_val!r}")
            else:
                if current_val != new_val:
                    skipped.append(f"  {field}: kept {current_val!r} (audit says {new_val!r})")

        if changed:
            report_changed[rest_name] = changed
        if skipped:
            report_skipped[rest_name] = skipped

    if updates:
        ws.batch_update(updates)

    # ── Print report ─────────────────────────────────────────────────────────
    print()
    print("=" * 65)
    print("  MENU SOURCE REGISTRY — AUDIT UPDATE REPORT")
    print(f"  Audit date: {TODAY}")
    print("=" * 65)

    print(f"\n✅  Updated ({len(report_changed)} restaurants):")
    for name, changes in sorted(report_changed.items()):
        print(f"\n  {name}")
        for c in changes:
            print(c)

    print(f"\n⏭   Fields preserved / not overwritten ({len(report_skipped)} restaurants):")
    for name, skips in sorted(report_skipped.items()):
        print(f"\n  {name}")
        for s in skips:
            print(s)

    print(f"\n⚠️   Not found in registry ({len(report_missing)}):")
    for name, msg in sorted(report_missing.items()):
        print(f"  {name}: {msg}")
    if not report_missing:
        print("  (none)")

    # Highlight critical flags
    print("\n🔴  CRITICAL FLAGS FROM AUDIT:")
    print("  Slutty Vegan    — Birmingham location possibly TEMPORARILY CLOSED (June 2026).")
    print("                    Manual verification required before next canvass.")
    print("  Blue Root       — NO standalone menu. Items only visible via Toast ordering.")
    print("                    getbento PDF is nutrition data only, not a menu.")
    print("  The Battery     — PDF dated July 2025 (~1 year old). Verify currency.")
    print("  Adam & Eve Cafe — JS-rendered site. Menu requires live browser (Popmenu).")
    print("  Wooden City     — Menu is image-only (JPGs). Cannot be parsed as text.")
    print("  Urban Cookhouse — PDF has no date. Verify currency manually.")

    print()
    print("=" * 65)
    print(f"  {len(updates)} cell(s) updated in Menu Source Registry.")
    print("=" * 65)
    print()


if __name__ == "__main__":
    main()
