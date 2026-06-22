"""
fetch_dishes.py — Goldpan Google Sheets sync
Joins data from four sheet tabs and writes dishes.json + restaurants.json.

Tabs read (internal use only — nothing from these tabs leaks to output):
  - Transparency Scoring    → derives transparency level only
  - Ingredient Details      → ingredients list, location
  - Goldpan Dish Level Data → dietary tags, allergen summary
  - Restaurant Claims       → public restaurant-level claims

Public output:
  dishes.json      — one entry per dish
  restaurants.json — one entry per restaurant, with claims array

Usage:
    pip install gspread google-auth
    python3 fetch_dishes.py
"""

import json
import os
import gspread
from google.oauth2.service_account import Credentials

# ── CONFIG ────────────────────────────────────────────────────────────────────

KEY_FILE            = "service_account.json"
SPREADSHEET_ID      = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
OUTPUT_FILE         = "dishes.json"
RESTAURANTS_FILE    = "restaurants.json"

# ── END CONFIG ────────────────────────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

SKIP_INGREDIENTS = {
    "building transparency",
    "ingredient detail pending confirmation",
    "none",
    "",
}


def clean_tags(raw):
    if not raw or str(raw).strip().lower() == "none":
        return []
    return [
        t.strip().lower()
        for t in str(raw).split(",")
        if t.strip() and t.strip().lower() != "none"
    ]


def level_short(raw):
    s = str(raw).strip().lower()
    if "high" in s:
        return "High"
    if "moderate" in s:
        return "Moderate"
    return "Building"


def normalize_restaurant_name(name):
    """Normalize known restaurant name variants from the sheet."""
    if name == "East West":
        return "EastWest"
    if name == "Brick & Tin Mountain Brook":
        return "Brick & Tin"
    return name


def main():
    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    # ── 1. Transparency Scoring — derive level only ─────────────────────────
    print("Reading Transparency Scoring...")
    scoring = {}
    for r in ss.worksheet("Transparency Scoring").get_all_records():
        did = str(r.get("Dish_ID", "")).strip()
        if not did:
            continue
        rest_name = normalize_restaurant_name(str(r.get("Restaurant_Name", "")).strip())
        scoring[did] = {
            "id":         did,
            "name":       str(r.get("Dish_Name", "")).strip(),
            "restaurant": rest_name,
            "level":      level_short(r.get("Transparency_Level", "")),
        }

    # ── 2. Ingredient Details — many rows per dish ──────────────────────────
    print("Reading Ingredient Details...")
    ingredients_by_dish = {}
    location_by_dish    = {}
    for r in ss.worksheet("Ingredient Details").get_all_records():
        did = str(r.get("Dish_ID", "")).strip()
        if not did:
            continue
        ing = str(r.get("Ingredient", "")).strip()
        if ing.lower() not in SKIP_INGREDIENTS:
            ingredients_by_dish.setdefault(did, [])
            if ing not in ingredients_by_dish[did]:
                ingredients_by_dish[did].append(ing)
        loc = str(r.get("Location", "")).strip().rstrip(",").strip()
        if loc:
            location_by_dish[did] = loc

    # ── 3. Goldpan Dish Level Data — one row per dish ───────────────────────
    print("Reading Goldpan Dish Level Data...")
    dish_level = {}
    for r in ss.worksheet("Goldpan Dish Level Data").get_all_records():
        did = str(r.get("Dish_ID", "")).strip()
        if not did:
            continue
        dish_level[did] = {
            "tags":               clean_tags(r.get("Dietary_Tags", "")),
            "allergens":          str(r.get("Allergen_summary", "")).strip() or "Unknown",
            "hours":              str(r.get("Hours", "")).strip(),
            "menu_link":          str(r.get("Menu_Link", "")).strip(),
            "restaurant_address": str(r.get("Restaurant_Address", "")).strip(),
            "restaurant_website": str(r.get("Restaurant_Website", "")).strip(),
            "category":           str(r.get("Category", "")).strip().lower(),
        }

    # ── 4. Restaurant Claims — public claims per restaurant ─────────────────
    print("Reading Restaurant Claims...")
    claims_by_restaurant = {}
    try:
        for r in ss.worksheet("Restaurant Claims").get_all_records():
            rid   = str(r.get("Restaurant_ID", "")).strip()
            rname = normalize_restaurant_name(str(r.get("Restaurant_Name", "")).strip())
            if not rid and not rname:
                continue
            key = rname or rid
            claim = {
                "type":  str(r.get("Claim_Type", "")).strip(),
                "scope": str(r.get("Claim_Scope", "")).strip(),
                "text":  str(r.get("Claim_Text", "")).strip(),
            }
            if claim["text"]:
                claims_by_restaurant.setdefault(key, []).append(claim)
    except gspread.exceptions.WorksheetNotFound:
        print("  (Restaurant Claims tab not found — skipping)")

    # ── 5. Restaurant metadata (legacy menu_statement fallback) ─────────────
    rest_meta = {}
    meta_file = os.path.join(os.path.dirname(__file__), "restaurant_meta.json")
    if os.path.exists(meta_file):
        with open(meta_file, "r", encoding="utf-8") as f:
            rest_meta = json.load(f)

    # ── 6. Assemble dishes — Scoring is the master list ─────────────────────
    dishes = []
    for did, s in scoring.items():
        dl     = dish_level.get(did, {})
        ing    = ingredients_by_dish.get(did, [])
        loc    = location_by_dish.get(did, "Birmingham")
        meta   = rest_meta.get(s["restaurant"], {})
        claims = claims_by_restaurant.get(s["restaurant"], [])

        # Public output only — no scores, sub-scores, notes, or internal fields
        dish = {
            "id":                 s["id"],
            "name":               s["name"],
            "restaurant":         s["restaurant"],
            "location":           loc,
            "level":              s["level"],
            "tags":               dl.get("tags", []),
            "allergens":          dl.get("allergens", "Unknown"),
            "hours":              dl.get("hours", ""),
            "menu_link":          dl.get("menu_link", ""),
            "restaurant_address": dl.get("restaurant_address", ""),
            "restaurant_website": dl.get("restaurant_website", ""),
            "ingredients":        ing,
            "category":           dl.get("category", ""),
        }
        # Legacy menu_statement from restaurant_meta.json
        if meta.get("menu_statement"):
            dish["menu_statement"] = meta["menu_statement"]
        # Restaurant-level claims (sourcing, certifications, etc.)
        if claims:
            dish["restaurant_claims"] = claims
        dishes.append(dish)

    dishes.sort(key=lambda d: d["id"])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dishes, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(dishes)} dishes to {OUTPUT_FILE}")

    # ── 7. Assemble restaurants.json ────────────────────────────────────────
    restaurants_map = {}
    for dish in dishes:
        rname = dish["restaurant"]
        if rname not in restaurants_map:
            restaurants_map[rname] = {
                "name":               rname,
                "location":           dish["location"],
                "hours":              dish["hours"],
                "menu_link":          dish["menu_link"],
                "restaurant_address": dish["restaurant_address"],
                "restaurant_website": dish["restaurant_website"],
                "claims":             claims_by_restaurant.get(rname, []),
            }
            # Include legacy menu_statement if present
            meta = rest_meta.get(rname, {})
            if meta.get("menu_statement"):
                restaurants_map[rname]["menu_statement"] = meta["menu_statement"]

    restaurants = sorted(restaurants_map.values(), key=lambda r: r["name"])

    with open(RESTAURANTS_FILE, "w", encoding="utf-8") as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(restaurants)} restaurants to {RESTAURANTS_FILE}")
    print(f"Restaurants with claims: {sum(1 for r in restaurants if r['claims'])}")


if __name__ == "__main__":
    main()
