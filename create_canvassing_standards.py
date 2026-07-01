"""
create_canvassing_standards.py

Creates the "Canvassing Standards" tab in the Goldpan Google Sheet.
This tab is for non-technical canvassers only — lightweight, practical guidance.

Full business/database rules live in DATA_RULES.md in this repo.
Full software engineering rules live in DATA_RULES.md in this repo.

Run once to create; safe to re-run (checks if tab exists, skips if present).
"""

import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TAB_NAME       = "Canvassing Standards"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ── Tab content ───────────────────────────────────────────────────────────────
# Each entry is [row_values]. Bold/header rows use a leading marker so the
# script can apply formatting after writing.
# Format: ("HEADER", text) | ("RULE", label, text) | ("BLANK",) | ("ROW", col1, col2, ...)

CONTENT = [

    # ── Title ─────────────────────────────────────────────────────────────────
    ("TITLE",   "Goldpan Canvassing Standards"),
    ("SUBHEAD", "For non-technical/menu canvassers. Full rule set in DATA_RULES.md (repo)."),
    ("BLANK",),

    # ── 1. Menu Verification ──────────────────────────────────────────────────
    ("SECTION", "1. Menu Verification — The Most Important Rule"),
    ("RULE",
     "A dish may ONLY be created from a current, verified live menu.",
     "Canvass the live menu at the restaurant website, Toast/Square/ChowNow ordering page, "
     "or an official dated PDF linked from the restaurant's own site. "
     "If you cannot confirm the dish is on the menu right now, do not add it."),
    ("RULE",
     "PDFs (nutrition, allergen) are supporting documents only.",
     "A nutrition or allergen PDF can update allergen data for a dish that already exists in the "
     "database. It can NEVER be used to create a new dish. The dish must be on the live menu first."),
    ("RULE",
     "Set menu_verified: true in your staging file.",
     "Every dish in a staging JSON must have \"menu_verified\": true — your attestation that "
     "you confirmed the dish on the live menu. The upsert script will block if this is missing."),
    ("BLANK",),

    # ── 2. Valid Menu Sources ─────────────────────────────────────────────────
    ("SECTION", "2. Valid Menu Sources (use the highest tier available)"),
    ("TABLE_HEADER", "Tier", "Source", "Notes"),
    ("TABLE_ROW",    "1",    "Official restaurant website — menu page (HTML)",
     "Best source. Use this when available."),
    ("TABLE_ROW",    "2",    "Restaurant's own ordering platform (Toast, Square, ChowNow)",
     "OK when it shows full item descriptions."),
    ("TABLE_ROW",    "3",    "Official dated PDF linked from the restaurant's own site",
     "Use the date on the PDF. Flag if undated."),
    ("TABLE_ROW",    "4",    "Official allergen/nutrition PDF from the restaurant's site",
     "Supporting source only — enriches existing dishes, never creates new ones."),
    ("TABLE_ROW",    "✗",    "Third-party delivery (DoorDash, Uber Eats, Grubhub)",
     "NOT permitted as a primary source."),
    ("TABLE_ROW",    "✗",    "Yelp, Google Maps, social media, undated PDFs",
     "NOT permitted as a primary source."),
    ("BLANK",),

    # ── 3. Source Confidence ──────────────────────────────────────────────────
    ("SECTION", "3. Source Confidence — What to Enter in the Menu Source Registry"),
    ("TABLE_HEADER", "Level", "When to use it"),
    ("TABLE_ROW",    "Official",
     "Sourced directly from the restaurant's own website or platform. URL verified. Content confirmed current."),
    ("TABLE_ROW",    "Third-Party",
     "Platform the restaurant uses but doesn't own (e.g., Toast CDN, GetBento). Restaurant-provided content, external hosting."),
    ("TABLE_ROW",    "Unverified",
     "Link not checked or content currency unknown. Must be verified before canvassing."),
    ("TABLE_ROW",    "Inferred",
     "No direct source; data derived from ingredient analysis. Must be labeled as such everywhere."),
    ("BLANK",),

    # ── 4. Side Item Policy ───────────────────────────────────────────────────
    ("SECTION", "4. Side Item Policy"),
    ("RULE",
     "Include sides only when they add transparency value.",
     "A side item must have at least one of: verified dietary tags, allergen data, "
     "ingredient information, preparation details, or dietary classifications."),
    ("RULE",
     "Do NOT include a side that only has a name and price.",
     "Name + price = no transparency value. Leave it out. It can be added later when data is available."),
    ("RULE",
     "Examples — INCLUDE",
     "Sweet potato fries (vegan, GF confirmed) | Mac & cheese (wheat, dairy declared) | "
     "House salad with ingredient list"),
    ("RULE",
     "Examples — EXCLUDE",
     "\"Side salad — $4\" (name and price only) | \"Side of rice\" (no data of any kind)"),
    ("BLANK",),

    # ── 5. Beverage Policy ────────────────────────────────────────────────────
    ("SECTION", "5. Beverage Policy"),
    ("RULE",
     "Standard beverages are excluded.",
     "Soft drinks, coffee, tea, water, and alcohol are not included in the database."),
    ("RULE",
     "Specialty beverages with disclosed ingredients may be included.",
     "Smoothies, açaí drinks, protein drinks, house-made juices — include if ingredient "
     "or allergen data is disclosed. Apply the same menu_verified and dish inclusion standards."),
    ("BLANK",),

    # ── 6. Dietary Tags ───────────────────────────────────────────────────────
    ("SECTION", "6. Dietary Tag Definitions — Apply Only When Confirmed"),
    ("TABLE_HEADER", "Tag", "Definition"),
    ("TABLE_ROW",    "vegan",
     "No animal products (no meat, fish, dairy, eggs, honey)."),
    ("TABLE_ROW",    "vegetarian",
     "No meat or fish. May contain dairy or eggs."),
    ("TABLE_ROW",    "gluten-free",
     "No gluten-containing ingredients, confirmed by the restaurant. Note cross-contact risk where applicable."),
    ("TABLE_ROW",    "dairy-free",
     "No dairy ingredients. Note if kitchen processes dairy."),
    ("TABLE_ROW",    "nut-free",
     "No tree nuts or peanuts. Note if kitchen processes nuts."),
    ("TABLE_ROW",    "high-protein",
     "30g+ protein per serving from disclosed nutrition data, or clearly protein-forward dish confirmed from menu."),
    ("TABLE_ROW",    "low-carb",
     "Confirmed from nutrition data or explicit menu designation. Do not infer from ingredient lists alone."),
    ("BLANK",),
    ("RULE",
     "Tags reflect the dish as served.",
     "Add-ons and modifications are not reflected in base tags. Do not assume tags from the dish name."),
    ("BLANK",),

    # ── 7. Allergen Standards ─────────────────────────────────────────────────
    ("SECTION", "7. Allergen Standards"),
    ("RULE",
     "Allergen data must come from an official source.",
     "Restaurant's own allergen guide, menu page, staff confirmation, or published nutrition document."),
    ("RULE",
     "Focus: The Big 9.",
     "Milk, eggs, fish, shellfish, tree nuts, peanuts, wheat/gluten, soy, sesame. "
     "Additional allergens (allium, nightshades, sulfites, citrus, mushrooms) may be noted when confirmed."),
    ("RULE",
     "If allergen data is unavailable, write: Unknown.",
     "Do not guess or infer allergens from dish names. Leave as Unknown until confirmed."),
    ("RULE",
     "Cross-contact: note it.",
     "If the kitchen processes a major allergen, include a cross-contact note even if the dish itself doesn't contain it."),
    ("BLANK",),

    # ── 8. Menu Source Registry Fields ───────────────────────────────────────
    ("SECTION", "8. Menu Source Registry — Field Reference"),
    ("TABLE_HEADER", "Field", "What to enter"),
    ("TABLE_ROW",    "Official_Website",      "The restaurant's main homepage URL."),
    ("TABLE_ROW",    "Official_Menu_URL",     "The direct URL to the menu page. Verify it loads."),
    ("TABLE_ROW",    "Online_Ordering_URL",   "Toast/Square/ChowNow ordering link if separate from menu."),
    ("TABLE_ROW",    "PDF_Menu_URL",          "Direct URL to a dated PDF menu, if one exists."),
    ("TABLE_ROW",    "Allergen_Nutrition_URL","Direct URL to an official allergen or nutrition guide PDF."),
    ("TABLE_ROW",    "Menu_Format",           "html | pdf | toast | square | chownow | image-only"),
    ("TABLE_ROW",    "Source_Confidence",     "Official | Third-Party | Unverified | Inferred (see section 3)"),
    ("TABLE_ROW",    "Preferred_Data_Source", "Which source to use for canvassing (usually Official_Menu_URL)."),
    ("TABLE_ROW",    "Menu_Status",           "Active = confirmed open and current. Needs Review = unverified or possibly closed."),
    ("TABLE_ROW",    "Canvass_Priority",      "High = urgent recanvass needed. Medium = routine. Low = recently updated."),
    ("TABLE_ROW",    "Last_Verified_Date",    "Date you last confirmed the source URL is working."),
    ("TABLE_ROW",    "Notes",                 "Anything unusual: JS-rendered menus, image-only menus, redirect behavior, closed flags."),
    ("BLANK",),

    # ── 9. Data Freshness ─────────────────────────────────────────────────────
    ("SECTION", "9. Data Freshness"),
    ("RULE",
     "Last_Updated reflects the date you recanvassed.",
     "Never bulk-stamp this date. Only update it when you actually verify the dish on the live menu."),
    ("RULE",
     "Dishes older than 90 days are review priority.",
     "Flag them in the registry or in your notes for recanvassing."),
    ("RULE",
     "Seasonal dishes: mark Inactive when they leave the menu.",
     "When a seasonal dish returns, recanvass and confirm ingredients are unchanged before reactivating."),
    ("RULE",
     "If a menu source URL is dead or stale:",
     "Update the Menu Source Registry immediately. Flag the restaurant for recanvassing "
     "before writing any new data."),
    ("BLANK",),

    # ── 10. What to Flag for Manual Review ────────────────────────────────────
    ("SECTION", "10. Flag for Manual Review"),
    ("RULE",
     "Dish in nutrition PDF but NOT on the live menu.",
     "Do not add it. Note it in your canvassing notes so it can be checked again."),
    ("RULE",
     "Dish appears to be renamed (same dish, different name).",
     "Do not create a new Dish_ID. Flag it — the existing ID should be updated."),
    ("RULE",
     "Data anomaly in a source document.",
     "E.g., fish allergen listed for a pork dish. Flag it. Do not silently write it."),
    ("RULE",
     "Restaurant possibly closed or temporarily closed.",
     "Set Menu_Status to Needs Review. Do not canvass until confirmed open."),
    ("RULE",
     "Menu is image-only or JavaScript-rendered.",
     "Note this in the registry. It limits what can be verified automatically."),
    ("BLANK",),

    # ── Footer ─────────────────────────────────────────────────────────────────
    ("FOOTER", "Full rule set: DATA_RULES.md in the Goldpan repo. Last updated: June 2026."),
]


def build_rows(content):
    """Convert CONTENT spec to flat list of row arrays for writing."""
    rows = []
    for item in content:
        kind = item[0]
        if kind == "TITLE":
            rows.append([item[1]])
        elif kind == "SUBHEAD":
            rows.append([item[1]])
        elif kind == "BLANK":
            rows.append([""])
        elif kind == "SECTION":
            rows.append([item[1]])
        elif kind == "RULE":
            rows.append([item[1], item[2]])
        elif kind == "TABLE_HEADER":
            rows.append(list(item[1:]))
        elif kind == "TABLE_ROW":
            rows.append(list(item[1:]))
        elif kind == "FOOTER":
            rows.append([item[1]])
    return rows


def apply_formatting(ws, content):
    """Apply bold to TITLE, SECTION, TABLE_HEADER rows."""
    bold_rows = []
    row_idx = 1
    for item in content:
        kind = item[0]
        if kind in ("TITLE", "SECTION", "TABLE_HEADER"):
            bold_rows.append(row_idx)
        row_idx += 1

    requests = []
    for r in bold_rows:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": ws.id,
                    "startRowIndex": r - 1,
                    "endRowIndex": r,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True}
                    }
                },
                "fields": "userEnteredFormat.textFormat.bold"
            }
        })

    # Title row: larger font
    requests.append({
        "repeatCell": {
            "range": {
                "sheetId": ws.id,
                "startRowIndex": 0,
                "endRowIndex": 1,
            },
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {"bold": True, "fontSize": 14}
                }
            },
            "fields": "userEnteredFormat.textFormat"
        }
    })

    # Freeze first row
    requests.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": ws.id,
                "gridProperties": {"frozenRowCount": 1}
            },
            "fields": "gridProperties.frozenRowCount"
        }
    })

    # Column widths: col A = 280px, col B = 600px
    for col_idx, width in [(0, 280), (1, 600)]:
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": ws.id,
                    "dimension": "COLUMNS",
                    "startIndex": col_idx,
                    "endIndex": col_idx + 1,
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize"
            }
        })

    # Wrap text in all cells
    requests.append({
        "repeatCell": {
            "range": {"sheetId": ws.id},
            "cell": {
                "userEnteredFormat": {
                    "wrapStrategy": "WRAP"
                }
            },
            "fields": "userEnteredFormat.wrapStrategy"
        }
    })

    ws.spreadsheet.batch_update({"requests": requests})


def main():
    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    # Check if tab exists
    existing = [ws.title for ws in ss.worksheets()]
    if TAB_NAME in existing:
        print(f"Tab '{TAB_NAME}' already exists. Skipping creation.")
        print("To recreate, delete the tab manually and re-run.")
        return

    print(f"Creating tab '{TAB_NAME}'...")
    ws = ss.add_worksheet(title=TAB_NAME, rows=200, cols=4)

    rows = build_rows(CONTENT)
    print(f"Writing {len(rows)} rows...")
    ws.update(f"A1:D{len(rows)}", rows)

    print("Applying formatting...")
    apply_formatting(ws, CONTENT)

    print(f"\nDone. '{TAB_NAME}' tab created with {len(rows)} rows.")
    print("Full rule set is in DATA_RULES.md in the repo.")


if __name__ == "__main__":
    main()
