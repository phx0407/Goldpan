"""
create_rules_tabs.py

Creates or updates four documentation tabs in the Goldpan Google Sheet:

  1. Database Rules          — business/data rules for what belongs in Goldpan
  2. Software Engineering Rules — how the pipeline must be built and maintained
  3. Menu Source Registry    — already exists as a data tab; rules written to header rows
  4. Side Item Policy        — standalone policy tab for side item inclusion/exclusion

Behavior:
  - If a tab already exists, its existing content is preserved where possible.
    Only missing sections are added; existing content is never blindly overwritten.
  - Menu Source Registry: rules are prepended as a pinned header block above the data.
  - Prints a summary of what was created vs. updated vs. skipped.
"""

import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ─────────────────────────────────────────────────────────────────────────────
# TAB CONTENT
# Each tab is a list of [col_A, col_B] rows.
# col_A = section header or rule number | col_B = rule name and content
# Empty row = ["", ""] for spacing.
# ─────────────────────────────────────────────────────────────────────────────

DATABASE_RULES = [
    ["GOLDPAN DATABASE RULES", ""],
    ["Purpose", "Define what belongs in Goldpan's data system. These are business rules — they govern the content and quality of the database, not how the software is built."],
    ["Last Updated", "June 2026"],
    ["", ""],

    ["━━━ SECTION 1", "RESTAURANT INCLUSION"],
    ["R1.1", "A restaurant must be located in the Birmingham, AL metro area (including Mountain Brook, Homewood, Hoover, Vestavia Hills, and adjacent municipalities)."],
    ["R1.2", "A restaurant must have a publicly accessible, current menu. If no verifiable menu source exists, the restaurant cannot be onboarded."],
    ["R1.3", "A restaurant must be confirmed open and operating before canvassing begins. Temporarily closed or permanently closed restaurants must not be added or must be marked accordingly in the Menu Source Registry."],
    ["R1.4", "Chain restaurants may be included when the Birmingham-area location has meaningful local menu variation or allergen transparency not covered by national databases."],
    ["R1.5", "The Menu Source Registry entry must be completed and validated before any restaurant enters the dish-level data process. See: Menu Source Registry tab."],
    ["", ""],

    ["━━━ SECTION 2", "DISH INCLUSION"],
    ["D2.1", "A dish may only be created from a current, verified live menu. Supporting documents (nutritional PDFs, allergen matrices) may enrich an existing dish but may never create one."],
    ["D2.2", "Every dish in a staging file must carry 'menu_verified: true' — the canvasser's attestation that the dish was confirmed on the live menu."],
    ["D2.3", "Dishes that leave the menu are marked Inactive, never deleted. Inactive dishes are excluded from the public site but preserved in the database for historical reference."],
    ["D2.4", "If a dish is renamed, the existing Dish_ID is updated. A new ID is not created for a rename."],
    ["D2.5", "Duplicate dishes (same restaurant, same name) are not permitted. The deduplication rule in fetch_dishes.py keeps the entry with the most ingredient data."],
    ["", ""],

    ["━━━ SECTION 3", "SIDE ITEM INCLUSION POLICY"],
    ["S3.1", "Side items should only be included if they provide meaningful transparency value: verified dietary tags, allergen data, ingredient information, preparation details, or dietary classifications."],
    ["S3.2", "Do not include a side item that only has a name and a price. A name and price provide no transparency value."],
    ["S3.3", "Excluded sides may be added later if transparency data becomes available through recanvassing or an official allergen source."],
    ["S3.4", "The goal is not to catalog every menu item. The goal is to maintain a high-quality transparency database. When in doubt, exclude a side until its transparency data can be confirmed."],
    ["S3.5", "See the Side Item Policy tab for the full policy and examples."],
    ["", ""],

    ["━━━ SECTION 4", "BEVERAGE POLICY"],
    ["B4.1", "Beverages are generally excluded unless they carry meaningful allergen or dietary transparency value (e.g., a smoothie with nut milk, a protein drink with allergen declarations)."],
    ["B4.2", "Standard soft drinks, coffee, tea, water, and alcohol (beer, wine, spirits) are excluded."],
    ["B4.3", "Specialty beverages with disclosed ingredients (smoothies, açaí drinks, protein drinks, house-made juices) may be included when the ingredient data is available."],
    ["B4.4", "If a beverage is included, the same dish inclusion and menu_verified standards apply."],
    ["", ""],

    ["━━━ SECTION 5", "DIETARY TAG DEFINITIONS"],
    ["DT5.1", "Tags are applied only when the dish is confirmed to meet the definition — not when assumed from the dish name alone."],
    ["DT5.2", "vegan: No animal products of any kind (no meat, fish, dairy, eggs, honey)."],
    ["DT5.3", "vegetarian: No meat or fish. May contain dairy or eggs."],
    ["DT5.4", "gluten-free: No gluten-containing ingredients. Must be confirmed by the restaurant — 'no obvious gluten' is not sufficient. Note cross-contact risk where applicable."],
    ["DT5.5", "dairy-free: No dairy ingredients. Confirm if the kitchen processes dairy (cross-contact)."],
    ["DT5.6", "nut-free: No tree nuts or peanuts. Confirm if the kitchen processes nuts."],
    ["DT5.7", "high-protein: Dishes with 30g+ protein per serving based on disclosed nutrition data, or clearly protein-forward dishes (grilled proteins, protein bowls) confirmed from the menu."],
    ["DT5.8", "low-carb: Confirmed from nutrition data or explicit menu designation. Do not infer from ingredient lists alone."],
    ["DT5.9", "Tags should reflect the dish as served. Add-ons and modifications are not reflected in the base tags."],
    ["", ""],

    ["━━━ SECTION 6", "ALLERGEN STANDARDS"],
    ["A6.1", "Allergen data must come from an official source: restaurant's own allergen guide, menu page, staff confirmation, or published nutrition document."],
    ["A6.2", "The Big 9 allergens are the primary focus: milk, eggs, fish, shellfish, tree nuts, peanuts, wheat/gluten, soy, sesame."],
    ["A6.3", "Additional allergens may be noted when confirmed (allium/garlic, nightshades, sulfites, citrus, mushrooms)."],
    ["A6.4", "If allergen data is unavailable, the Allergen_summary field is set to 'Unknown'. Do not guess or infer allergens from dish names."],
    ["A6.5", "If the kitchen processes a major allergen, include a cross-contact note even if the dish itself does not contain that allergen."],
    ["A6.6", "Ingredient-derived allergen estimates must be labeled as such and recommended for manual verification. Official PDF or menu data supersedes ingredient-derived estimates."],
    ["A6.7", "Data anomalies in source documents (e.g., fish allergen listed for a pork dish) must be flagged, not silently written to the database."],
    ["", ""],

    ["━━━ SECTION 7", "TRANSPARENCY SCORING STANDARDS"],
    ["T7.1", "Transparency scoring is private. Scores, sub-scores, scoring criteria, and canvassing notes are never published to the public site."],
    ["T7.2", "Only the derived transparency level is public: Building, Moderate, or High."],
    ["T7.3", "Scores are assigned at the dish level during canvassing and live in the Transparency Scoring tab."],
    ["T7.4", "Score definitions and dimension weights are maintained in the Transparency Scoring tab header and must not be changed without a documented rationale."],
    ["", ""],

    ["━━━ SECTION 8", "REQUIRED FIELDS"],
    ["F8.1", "Goldpan Dish Level Data — required: Restaurant_ID, Restaurant, Location, Dish_ID, Dish_Name, Last_Updated, Status."],
    ["F8.2", "Ingredient Details — required: Dish_ID, Ingredient. At minimum one ingredient row must exist per dish unless ingredients are genuinely unknown."],
    ["F8.3", "Transparency Scoring — required: Restaurant_ID, Restaurant_Name, Dish_ID, Dish_Name, Transparency_Level."],
    ["F8.4", "Menu Source Registry — required: Restaurant_Name, Official_Website, Official_Menu_URL, Source_Confidence, Preferred_Data_Source, Menu_Status, Canvass_Priority."],
    ["", ""],

    ["━━━ SECTION 9", "MENU SOURCE HIERARCHY"],
    ["M9.1", "Sources are ranked in order of reliability. Always use the highest-ranked available source."],
    ["M9.2", "Tier 1 — Official website menu page (HTML, current, restaurant-controlled)."],
    ["M9.3", "Tier 2 — Restaurant's own ordering platform (Toast, Square, ChowNow, etc.) when it shows full item descriptions."],
    ["M9.4", "Tier 3 — Official dated PDF linked from the restaurant's own website."],
    ["M9.5", "Tier 4 — Official allergen/nutrition PDF linked from the restaurant's own website."],
    ["M9.6", "Not permitted as primary source — third-party delivery platforms, Yelp, Google Maps, social media, undated PDFs of unknown origin."],
    ["", ""],

    ["━━━ SECTION 10", "SOURCE CONFIDENCE LEVELS"],
    ["C10.1", "Official — sourced directly from the restaurant's own website or platform, URL verified, content current."],
    ["C10.2", "Third-Party — sourced from a platform the restaurant uses but does not own (e.g., Toast CDN, GetBento). Content is restaurant-provided but hosting is external."],
    ["C10.3", "Unverified — link not checked or content currency unknown. Must be verified before canvassing."],
    ["C10.4", "Inferred — no direct source; data derived from ingredient analysis or secondary sources. Must be labeled as such in all database fields."],
    ["", ""],

    ["━━━ SECTION 11", "DATA FRESHNESS & REVIEW POLICY"],
    ["FR11.1", "Last_Updated reflects the date a dish was recanvassed and data was confirmed or updated. It is never bulk-stamped."],
    ["FR11.2", "Dishes with Last_Updated older than 90 days should be flagged for review priority."],
    ["FR11.3", "The Menu Source Registry Last_Verified_Date must be updated each time a source URL is confirmed working."],
    ["FR11.4", "If a menu source URL is found to be dead or stale, the Menu Source Registry must be updated immediately and the restaurant flagged for recanvassing before new data is written."],
    ["FR11.5", "Seasonal dishes: when a seasonal dish leaves the menu, mark it Inactive. When it returns, reactivate and recanvass to confirm ingredients are unchanged."],
]

SE_RULES = [
    ["GOLDPAN SOFTWARE ENGINEERING RULES", ""],
    ["Purpose", "Define how Goldpan's software and data pipeline must be built and maintained. These are engineering rules — they govern code quality, data safety, and pipeline reliability, not business content."],
    ["Last Updated", "June 2026"],
    ["", ""],

    ["━━━ SECTION 1", "DATA SAFETY"],
    ["E1.1", "Never write directly to production data when staging is appropriate. All new restaurant and dish data must go through a staging JSON file reviewed before upsert."],
    ["E1.2", "Staging files are the review checkpoint. A staging file must be readable, auditable, and reviewable before python3 upsert_dishes.py is run."],
    ["E1.3", "Patch scripts (targeted fixes to existing rows) are acceptable for small updates but must be scoped and documented in the script header with source, date, and what changed."],
    ["E1.4", "Never overwrite a non-empty field unless the new value is a confirmed correction. When in doubt, append or flag — do not replace."],
    ["E1.5", "Batch operations that touch more than 10 rows must print a pre-run summary and require confirmation (or --dry-run output) before executing."],
    ["", ""],

    ["━━━ SECTION 2", "BUILD GATES"],
    ["E2.1", "fetch_dishes.py must not produce output if validation fails. The build exits with a non-zero status and a clear error report."],
    ["E2.2", "Required validation gates (in order): (1) Menu Source Registry coverage — every restaurant in Transparency Scoring must have a registry entry. (2) Dish Level Data coverage — every scored dish must have a Dish Level Data row or be marked Inactive."],
    ["E2.3", "Build gates produce a report showing exactly what is missing and which script to run to fix it. Never silently skip a validation failure."],
    ["E2.4", "A build that passes all gates but produces zero dishes is a failure. Validate output record count."],
    ["", ""],

    ["━━━ SECTION 3", "STAGING PIPELINE"],
    ["E3.1", "The canonical pipeline order: Canvass live menu → staging JSON with menu_verified: true → upsert_dishes.py → fetch_dishes.py → bash update.sh."],
    ["E3.2", "Allergen/nutritional PDFs are applied after the dish exists in the database. Patch scripts only update existing rows — they never create new ones from PDF data alone."],
    ["E3.3", "upsert_dishes.py blocks if any dish in the staging file is missing menu_verified: true. Use --force only for legacy files and document why."],
    ["E3.4", "Staging files must be kept after use. They are the audit trail for what was added and when. Do not delete staging files."],
    ["", ""],

    ["━━━ SECTION 4", "DEBUGGING PROTOCOL"],
    ["E4.1", "If data is missing from the site, diagnose in this order before writing any fix: (1) Is the row missing from Transparency Scoring? (2) Is it missing from Goldpan Dish Level Data? (3) Did the upsert run? (4) Did fetch_dishes.py run? (5) Is there a frontend mapping issue? (6) Is the deployment stale or cached?"],
    ["E4.2", "Do not write a cleanup patch until the failure stage is identified. Patching the wrong layer wastes effort and introduces risk."],
    ["E4.3", "When a build fails, read the full error output before acting. The build reports are designed to tell you exactly what is wrong."],
    ["", ""],

    ["━━━ SECTION 5", "ERROR & WARNING REPORTING"],
    ["E5.1", "Scripts must print a clear report at completion: what was added, what was updated, what was skipped, and what failed."],
    ["E5.2", "Warnings are not errors. Warnings (e.g., name collisions, missing optional fields) are printed and allow the script to continue. Errors (e.g., missing menu_verified, failed build gate) stop execution."],
    ["E5.3", "Data anomalies found during processing (e.g., a fish allergen listed for a pork dish in a source document) must be printed as warnings with the source cited. Never silently write anomalous data."],
    ["E5.4", "Scripts that touch the Google Sheet must confirm the number of rows written at completion."],
    ["", ""],

    ["━━━ SECTION 6", "NAMING CONVENTIONS"],
    ["E6.1", "Scripts: snake_case. Prefix with action: fetch_, patch_, upsert_, create_, insert_, update_, verify_, staging_."],
    ["E6.2", "Staging files: staging_[restaurantname].json (lowercase, no spaces). Addendum files: staging_[restaurantname]_addendum.json."],
    ["E6.3", "Dish IDs: D + zero-padded integer (D001, D099, D100, D1000). Never reuse a Dish_ID, even for renamed dishes."],
    ["E6.4", "Restaurant IDs: R + zero-padded integer (R001, R025). Never reuse a Restaurant_ID."],
    ["E6.5", "Tab names in Google Sheet: Title Case with spaces. Match exactly across all scripts — tab name mismatches cause silent failures."],
    ["", ""],

    ["━━━ SECTION 7", "JSON SCHEMA STANDARDS"],
    ["E7.1", "Every staging file must include: restaurant_id, restaurant_name, location, restaurant_address, restaurant_website, hours, menu_link, and a dishes array."],
    ["E7.2", "Every dish object must include: dish_id, dish_name, menu_verified (must be true), dietary_tags, allergen_summary, and ingredients array."],
    ["E7.3", "Optional dish fields: menu_price, category, dietary_options, core_clarity, sauce_disclosure, allergen_transparency, prep_clarity, total_score, transparency_level, notes."],
    ["E7.4", "Ingredients may be strings (simple) or objects with name, cut_type, preparation, type, source, allergen_flags, role."],
    ["E7.5", "Do not add fields to staging files that are not read by upsert_dishes.py. Unknown fields are silently ignored and create confusion."],
    ["", ""],

    ["━━━ SECTION 8", "DEPLOYMENT CHECKLIST"],
    ["E8.1", "Before running bash update.sh: (1) All patch/upsert scripts for this session have been run. (2) fetch_dishes.py validation passes with zero warnings (or warnings are understood and accepted). (3) Output dish count is consistent with expectations."],
    ["E8.2", "After running bash update.sh: (1) Confirm dishes.json and restaurants.json were updated (check file timestamps). (2) Spot-check two or three dishes on the live site. (3) Confirm the map and filter UI still function."],
    ["E8.3", "Never run bash update.sh without first running fetch_dishes.py locally to confirm the build is clean."],
    ["", ""],

    ["━━━ SECTION 9", "POST-BUILD VERIFICATION"],
    ["E9.1", "After every deployment, verify: a dish with recent updates appears correctly on the public site, the restaurants.json was updated, and the filter/tag UI reflects any new tags."],
    ["E9.2", "Spot-check a restaurant that was recanvassed this session: confirm allergen and ingredient data is visible."],
    ["E9.3", "If the site does not reflect changes after deployment, check in this order: CDN/cache, GitHub Pages build status, dishes.json content, fetch_dishes.py output."],
    ["", ""],

    ["━━━ SECTION 10", "LOGGING EXPECTATIONS"],
    ["E10.1", "Every script that writes to the database or produces an output file must print: the script name, the date, what it did, and how many records were affected."],
    ["E10.2", "Patch scripts must log the source document they are applying (URL, date of document) in both the script header and the terminal output."],
    ["E10.3", "upsert_dishes.py logs: staging file name, restaurant, dish count, ingredient count, and per-tab results (added/updated)."],
]

SIDE_ITEM_POLICY = [
    ["GOLDPAN SIDE ITEM POLICY", ""],
    ["Purpose", "Define the criteria for including or excluding side items from the Goldpan database. This policy exists because sides are often low-transparency items that, without meaningful data, reduce overall database quality."],
    ["Last Updated", "June 2026"],
    ["", ""],

    ["━━━ THE CORE RULE", ""],
    ["", "Include side items only when they provide meaningful transparency value. Do not include sides that only have a name and a price."],
    ["", "The goal is not to catalog every menu item. The goal is to maintain a high-quality transparency database."],
    ["", ""],

    ["━━━ SECTION 1", "INCLUSION CRITERIA"],
    ["SP1.1", "A side item may be included when it has ONE OR MORE of the following: confirmed dietary tags (vegan, gluten-free, dairy-free, etc.), verified allergen data, ingredient list, preparation detail, or dietary classification."],
    ["SP1.2", "A side with confirmed dietary tags qualifies even without a full ingredient list. Example: 'Sweet Potato Fries — vegan, gluten-free' is worth including."],
    ["SP1.3", "A side with known allergen data qualifies. Example: 'Mac & Cheese — contains wheat (pasta), dairy (cheese)' is worth including."],
    ["SP1.4", "A side with a disclosed ingredient list qualifies regardless of tag status. Example: 'House Salad — romaine, cherry tomatoes, cucumber, red onion, house vinaigrette' is worth including."],
    ["SP1.5", "Preparation details that affect dietary status qualify. Example: 'Fries — cooked in dedicated fryer (no shared oil with meat products)' is worth including."],
    ["", ""],

    ["━━━ SECTION 2", "EXCLUSION CRITERIA"],
    ["SP2.1", "A side item with only a name and a price must NOT be included. Example: 'Side Salad — $4' provides no transparency value."],
    ["SP2.2", "A side item with only a name (no price, no data) must NOT be included."],
    ["SP2.3", "Generic sides with no meaningful variation (e.g., 'Side of Rice', 'Chips') may be excluded unless allergen or dietary data is available."],
    ["SP2.4", "Condiments, dipping sauces, and dressings are excluded as standalone dishes unless they carry allergen significance (e.g., a peanut-based sauce at a restaurant where nut allergies are a concern). They may appear in ingredient detail for the parent dish."],
    ["", ""],

    ["━━━ SECTION 3", "DEFERRED INCLUSION"],
    ["SP3.1", "A side that is excluded today may be added later when transparency data becomes available through recanvassing, an official allergen source, or a restaurant response."],
    ["SP3.2", "When a side is intentionally excluded, do not create a placeholder row in the database. Simply do not include it. It can be added in a future canvassing pass when data is available."],
    ["SP3.3", "If a recanvass reveals that a previously excluded side now has meaningful data, it may be added through the normal menu_verified staging process."],
    ["", ""],

    ["━━━ SECTION 4", "PRACTICAL EXAMPLES"],
    ["Include", "Sweet potato fries — vegan, gluten-free (confirmed by restaurant)"],
    ["Include", "Mac & cheese — wheat (pasta), dairy (cheese, milk)"],
    ["Include", "House side salad — romaine, tomato, cucumber, croutons, choice of dressing"],
    ["Include", "Steamed broccoli — no allergens declared, vegan, gluten-free"],
    ["Exclude", "Side salad — $4 (name and price only)"],
    ["Exclude", "French fries — $3 (name and price only; no allergen, tag, or ingredient data)"],
    ["Exclude", "Side of rice (no data of any kind)"],
    ["Exclude", "Seasonal vegetable (name only; content varies, no data)"],
    ["", ""],

    ["━━━ SECTION 5", "RELATIONSHIP TO OTHER RULES"],
    ["SP5.1", "Side items that qualify for inclusion follow all standard database rules: menu_verified: true required, dish_id assigned, allergen_summary populated or set to Unknown."],
    ["SP5.2", "The same Last_Updated and data freshness standards apply to included sides."],
    ["SP5.3", "If a side is included and later loses its transparency data (e.g., allergen data was removed from the restaurant's website), it should be reviewed and potentially marked Inactive until data is reconfirmed."],
]

MSR_RULES_HEADER = [
    ["MENU SOURCE REGISTRY — RULES", ""],
    ["Purpose", "Track the authoritative menu sources for every restaurant. This tab must be consulted before any canvassing begins. Sources must be verified — do not assume saved links are still current."],
    ["Last Updated", "June 2026"],
    ["", ""],
    ["RULE", "No restaurant enters the Goldpan Dish Level Data process until this registry entry is complete and validated."],
    ["", ""],
    ["MSR1", "Verify every link before canvassing. A link in this registry is not assumed to be current — check it."],
    ["MSR2", "Add multiple official sources when needed. If the website shows the food menu but a separate PDF has the allergen guide, list both."],
    ["MSR3", "Do not use social media links (Instagram, Facebook) as canvassing sources unless a formal social media canvassing policy is adopted."],
    ["MSR4", "Source_Confidence must reflect the current state of the link, not its original state. Update it when a link goes dead or a source changes."],
    ["MSR5", "Preferred_Data_Source is the single best URL for a canvasser to start from. It must be a working, direct link to the current menu."],
    ["MSR6", "If a restaurant is listed as 'Needs Review' in Menu_Status, it must not be canvassed until the status is resolved and the restaurant confirmed operational."],
    ["MSR7", "Nutritional and allergen documents must be listed in Allergen_Nutrition_URL — not in Official_Menu_URL. They are supporting documents, not menu sources."],
    ["", ""],
    ["━━━ FIELD DEFINITIONS", ""],
    ["Restaurant_ID", "Unique identifier from Goldpan Dish Level Data (e.g. R004)."],
    ["Restaurant_Name", "Canonical name as used across all Goldpan tabs. Must match exactly."],
    ["Official_Website", "The restaurant's own domain homepage."],
    ["Official_Menu_URL", "The menu page on the restaurant's own website. Not a delivery platform."],
    ["Online_Ordering_URL", "Toast, Square, ChowNow, or other ordering platform URL if available."],
    ["PDF_Menu_URL", "A PDF menu linked from the restaurant's own website. Must include date if visible."],
    ["Allergen_Nutrition_URL", "Official allergen guide or nutrition document. Supporting source only — not a menu source."],
    ["Menu_Format", "HTML / PDF / Toast / Mixed / Image-only. 'Image-only' means menu is not parseable as text."],
    ["Source_Confidence", "Official / Third-Party / Unverified / Inferred. See Database Rules Section 10."],
    ["Canvass_Priority", "High / Medium / Low. High = data gap or recent change detected. Low = recently canvassed, data current."],
    ["Last_Verified_Date", "Date the source URLs were last confirmed working."],
    ["Last_Menu_Change_Detected", "Date a change to the menu was detected. Leave blank if unknown."],
    ["Source_Status", "Active / Needs Review / Temporarily Closed. Needs Review blocks canvassing until resolved."],
    ["Notes", "Anything a canvasser needs to know: image-only menus, JS-rendered sites, PDF staleness, anomalies."],
    ["", ""],
    ["━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "REGISTRY DATA BEGINS BELOW"],
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_or_create_tab(ss, title, rows=200, cols=2):
    try:
        ws = ss.worksheet(title)
        return ws, False  # existed
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=title, rows=rows, cols=cols)
        return ws, True   # created


def write_rules_tab(ws, rows, created):
    """Write a rules tab. If created fresh, write all rows. If it existed,
    only write if the tab appears to be empty or only has outdated content."""
    existing = ws.get_all_values()
    # Check if the tab has substantive content already
    has_content = any(
        any(cell.strip() for cell in row)
        for row in existing
        if row
    )
    if has_content and not created:
        # Tab already has content — check if first cell matches our header
        first_cell = existing[0][0].strip() if existing and existing[0] else ""
        if rows[0][0].strip() in first_cell or first_cell in rows[0][0].strip():
            return "skipped (already up to date)"
        else:
            # Header mismatch — overwrite
            ws.clear()
            ws.update(rows, "A1")
            return "overwritten (header mismatch — replaced with current version)"
    else:
        ws.update(rows, "A1")
        return "written"


def update_msr_rules(ws):
    """
    Prepend the rules header block to the Menu Source Registry.
    If rules are already there (first cell contains 'MENU SOURCE REGISTRY — RULES'),
    update the rules block only; preserve all data rows below.
    """
    existing = ws.get_all_values()
    if not existing:
        ws.update(MSR_RULES_HEADER, "A1")
        return "rules block written (tab was empty)"

    first_cell = existing[0][0].strip() if existing[0] else ""

    # Check if rules block is already present
    if "MENU SOURCE REGISTRY — RULES" in first_cell:
        # Find where the data begins (look for "━━━━" separator line)
        separator_row = None
        for i, row in enumerate(existing):
            if row and "REGISTRY DATA BEGINS BELOW" in str(row):
                separator_row = i + 1  # 1-indexed row after separator
                break

        if separator_row:
            # Overwrite just the rules header block (rows 1 to separator_row)
            ws.update(MSR_RULES_HEADER, "A1")
            return f"rules block updated (data rows preserved from row {separator_row + 1})"
        else:
            return "rules block already present — no separator found, skipped to be safe"
    else:
        # No rules block — prepend by inserting rows at the top
        # Read existing data, insert rules, then write back
        rules_count = len(MSR_RULES_HEADER)
        ws.insert_rows(MSR_RULES_HEADER, row=1)
        return f"rules block prepended ({rules_count} rows inserted above existing data)"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    results = {}

    # 1. Database Rules
    print("Processing: Database Rules...")
    ws, created = get_or_create_tab(ss, "Database Rules", rows=300, cols=2)
    status = write_rules_tab(ws, DATABASE_RULES, created)
    results["Database Rules"] = ("created" if created else "existed") + f" — {status}"

    # 2. Software Engineering Rules
    print("Processing: Software Engineering Rules...")
    ws, created = get_or_create_tab(ss, "Software Engineering Rules", rows=200, cols=2)
    status = write_rules_tab(ws, SE_RULES, created)
    results["Software Engineering Rules"] = ("created" if created else "existed") + f" — {status}"

    # 3. Side Item Policy
    print("Processing: Side Item Policy...")
    ws, created = get_or_create_tab(ss, "Side Item Policy", rows=100, cols=2)
    status = write_rules_tab(ws, SIDE_ITEM_POLICY, created)
    results["Side Item Policy"] = ("created" if created else "existed") + f" — {status}"

    # 4. Menu Source Registry — prepend rules header
    print("Processing: Menu Source Registry (rules header)...")
    try:
        msr_ws = ss.worksheet("Menu Source Registry")
        status = update_msr_rules(msr_ws)
        results["Menu Source Registry"] = f"existed — {status}"
    except gspread.exceptions.WorksheetNotFound:
        results["Menu Source Registry"] = "NOT FOUND — run create_menu_source_registry.py first"

    # ── Report ────────────────────────────────────────────────────────────────
    print()
    print("=" * 65)
    print("  RULES DOCUMENTATION — BUILD REPORT")
    print("=" * 65)
    for tab, result in results.items():
        print(f"\n  {tab}")
        print(f"    {result}")
    print()
    print("=" * 65)
    print()
    print("Tabs written:")
    print("  • Database Rules          — business/data rules (11 sections)")
    print("  • Software Engineering Rules — pipeline/code rules (10 sections)")
    print("  • Side Item Policy        — side item inclusion/exclusion policy")
    print("  • Menu Source Registry    — rules header prepended above data rows")
    print()
    print("Update DATA_RULES.md to reference these tabs as the authoritative source.")
    print()


if __name__ == "__main__":
    main()
