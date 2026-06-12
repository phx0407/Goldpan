"""
fetch_dishes.py — Goldpan Google Sheets sync
Joins data from three sheet tabs and writes dishes.json.

Tabs read (internal use only — nothing from these tabs leaks to output):
  - Transparency Scoring    → derives transparency level only
  - Ingredient Details      → ingredients list, location
  - Goldpan Dish Level Data → dietary tags, allergen summary

Public output fields per dish:
  id, name, restaurant, location, level, tags, allergens, ingredients

Usage:
    pip install gspread google-auth
    python3 fetch_dishes.py
"""

import json
import gspread
from google.oauth2.service_account import Credentials

# ── CONFIG ────────────────────────────────────────────────────────────────────

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
OUTPUT_FILE    = "dishes.json"

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
        scoring[did] = {
            "id":         did,
            "name":       str(r.get("Dish_Name", "")).strip(),
            "restaurant": str(r.get("Restaurant_Name", "")).strip(),
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
            "tags":      clean_tags(r.get("Dietary_Tags", "")),
            "allergens": str(r.get("Allergen_summary", "")).strip() or "Unknown",
        }

    # ── 4. Assemble — Scoring is the master list ────────────────────────────
    dishes = []
    for did, s in scoring.items():
        dl  = dish_level.get(did, {})
        ing = ingredients_by_dish.get(did, [])
        loc = location_by_dish.get(did, "Birmingham")

        # Public output only — no scores, sub-scores, notes, or internal fields
        dishes.append({
            "id":          s["id"],
            "name":        s["name"],
            "restaurant":  s["restaurant"],
            "location":    loc,
            "level":       s["level"],
            "tags":        dl.get("tags", []),
            "allergens":   dl.get("allergens", "Unknown"),
            "ingredients": ing,
        })

    dishes.sort(key=lambda d: d["id"])

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dishes, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Wrote {len(dishes)} dishes to {OUTPUT_FILE}")
    print(f"Restaurants: {len({d['restaurant'] for d in dishes})}")


if __name__ == "__main__":
    main()
