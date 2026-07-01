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

DERIVED_FILTERS_FILE = "derived_filters.json"

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


def load_derived_filters(path: str) -> dict:
    """Load derived_filters.json, keyed by Dish_ID. Graceful fallback to {}."""
    if not os.path.exists(path):
        print(f"  (derived_filters.json not found at {path} — run compute_derived_filters.py --apply first)")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Top-level keys are Dish_IDs; each entry has a "filters" sub-dict
    return data


def main():
    # ── 0. Load derived filters (computed offline) ───────────────────────────
    print("Loading derived_filters.json...")
    derived_filters_data = load_derived_filters(
        os.path.join(os.path.dirname(__file__), DERIVED_FILTERS_FILE)
    )
    print(f"  Loaded derived filter results for {len(derived_filters_data)} dish(es).")

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
    dish_level   = {}
    inactive_ids = set()
    for r in ss.worksheet("Goldpan Dish Level Data").get_all_records():
        did = str(r.get("Dish_ID", "")).strip()
        if not did:
            continue
        status = str(r.get("Status", "")).strip().lower()
        if status == "inactive":
            inactive_ids.add(did)
            continue
        dish_level[did] = {
            "restaurant_id":      str(r.get("Restaurant_ID", "")).strip(),
            "tags":               clean_tags(r.get("Dietary_Tags", "")),
            "tag_source":         str(r.get("Tag_Source", "")).strip().lower() or None,
            "options":            clean_tags(r.get("Dietary_Options", "")),
            "allergens":          str(r.get("Allergen_summary", "")).strip() or "Unknown",
            "hours":              str(r.get("Hours", "")).strip(),
            "menu_link":          str(r.get("Menu_Link", "")).strip(),
            "restaurant_address": str(r.get("Restaurant_Address", "")).strip(),
            "restaurant_website": str(r.get("Restaurant_Website", "")).strip(),
            "category":           str(r.get("Category", "")).strip().lower(),
            "last_updated":       str(r.get("Last_Updated", "")).strip(),
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

    # ── 4b. Allergen Disclosures — Evidence System (GP-RULE-014) ───────────────
    # System A: restaurant-disclosed allergen status (contains / may_contain / free_from).
    # Separate from derived_filters (System B — GoldPan ingredient analysis).
    # Raw disclosure rows only — no consumer labels, no confidence tokens (GP-RULE-016).
    # Graceful fallback: empty if tab is missing or contains no data.
    print("Reading Allergen Disclosures...")
    # dish-scope disclosures keyed by Dish_ID
    allergen_disclosures_by_dish: dict = {}
    # restaurant-scope disclosures keyed by Restaurant_ID
    allergen_disclosures_by_restaurant: dict = {}
    try:
        for r in ss.worksheet("Allergen Disclosures").get_all_records():
            scope  = str(r.get("Scope", "")).strip().lower()
            did    = str(r.get("Dish_ID", "")).strip()
            rid    = str(r.get("Restaurant_ID", "")).strip()
            alg    = str(r.get("Allergen", "")).strip().lower()
            ds     = str(r.get("Disclosure_Status", "")).strip().lower()
            st     = str(r.get("Source_Type", "")).strip().lower()
            sref   = str(r.get("Source_Reference", "")).strip()
            sdate  = str(r.get("Source_Date", "")).strip()
            notes  = str(r.get("Notes", "")).strip()
            if not alg or not ds:
                continue  # skip malformed rows
            row_out = {
                "allergen":          alg,
                "disclosure_status": ds,
                "source_type":       st,
                "source_reference":  sref,
                "source_date":       sdate,
                "scope":             scope,
                "notes":             notes or None,
            }
            if scope == "dish" and did:
                allergen_disclosures_by_dish.setdefault(did, []).append(row_out)
            elif scope == "restaurant" and rid:
                allergen_disclosures_by_restaurant.setdefault(rid, []).append(row_out)
        disc_count = (
            sum(len(v) for v in allergen_disclosures_by_dish.values()) +
            sum(len(v) for v in allergen_disclosures_by_restaurant.values())
        )
        print(f"  {disc_count} disclosure row(s) loaded "
              f"({len(allergen_disclosures_by_dish)} dish-scope, "
              f"{len(allergen_disclosures_by_restaurant)} restaurant-scope)")
    except gspread.exceptions.WorksheetNotFound:
        print("  (Allergen Disclosures tab not found — no allergen disclosure data in output)")

    # ── 5. Restaurant metadata (legacy menu_statement fallback) ─────────────
    rest_meta = {}
    meta_file = os.path.join(os.path.dirname(__file__), "restaurant_meta.json")
    if os.path.exists(meta_file):
        with open(meta_file, "r", encoding="utf-8") as f:
            rest_meta = json.load(f)

    # ── 5b. restaurant_coords.json — fallback for website & menu_link ────────
    coords_meta = {}
    coords_file = os.path.join(os.path.dirname(__file__), "restaurant_coords.json")
    if os.path.exists(coords_file):
        with open(coords_file, "r", encoding="utf-8") as f:
            for name, d in json.load(f).items():
                coords_meta[name] = {
                    "website":   d.get("website", "").strip(),
                    "menu_link": d.get("menu_link", "").strip(),
                    "address":   d.get("address", "").strip(),
                    "hours":     d.get("hours", "").strip(),
                }

    # ── 5c. Validation — Menu Source Registry coverage ──────────────────────────
    print("Validating Menu Source Registry coverage...")
    try:
        reg_ws      = ss.worksheet("Menu Source Registry")
        reg_headers = reg_ws.row_values(1)
        reg_name_col = reg_headers.index("Restaurant_Name") if "Restaurant_Name" in reg_headers else None
        registry_names = set()
        if reg_name_col is not None:
            for row in reg_ws.get_all_values()[1:]:
                if len(row) > reg_name_col and row[reg_name_col].strip():
                    registry_names.add(normalize_restaurant_name(row[reg_name_col].strip()))
        missing_from_registry = [
            rname for rname in set(s["restaurant"] for s in scoring.values())
            if rname not in registry_names
        ]
        if missing_from_registry:
            print("\n" + "=" * 60)
            print("BUILD WARNING: restaurants in Transparency Scoring have no")
            print("row in the Menu Source Registry. Complete the registry before")
            print("adding new dishes for these restaurants.")
            print("-" * 60)
            for rname in sorted(missing_from_registry):
                print(f"  {rname}")
            print("=" * 60)
            print(f"\n{len(missing_from_registry)} restaurant(s) missing from Menu Source Registry.")
            print("Run: python3 create_menu_source_registry.py\n")
        else:
            print(f"  OK — all restaurants have Menu Source Registry entries.")
    except gspread.exceptions.WorksheetNotFound:
        print("  WARNING: Menu Source Registry tab not found.")
        print("  Run: python3 create_menu_source_registry.py")

    # ── 5e. Validation — every Scoring dish must exist in Dish Level Data ───────
    print("Validating Dish Level Data coverage...")
    missing = [
        s for did, s in scoring.items()
        if did not in dish_level and did not in inactive_ids
    ]
    if missing:
        print("\n" + "=" * 60)
        print("BUILD WARNING: dishes in Transparency Scoring have no")
        print("row in Goldpan Dish Level Data — allergens/tags will be")
        print("missing on the site. Fix before publishing.")
        print("-" * 60)
        for s in sorted(missing, key=lambda x: (x["restaurant"], x["id"])):
            print(f"  {s['restaurant']:35} {s['id']}  {s['name']}")
        print("=" * 60)
        print(f"\n{len(missing)} dish(es) missing from Goldpan Dish Level Data.")
        print("Run the appropriate insert/upsert script, then re-run fetch_dishes.py.\n")
        import sys
        sys.exit(1)
    else:
        print(f"  OK — all {len(scoring)} scored dishes have Dish Level Data rows.")

    # ── 6. Assemble dishes — Scoring is the master list ─────────────────────
    if inactive_ids:
        print(f"  Skipping {len(inactive_ids)} inactive dish(es)")
    dishes = []
    for did, s in scoring.items():
        if did in inactive_ids:
            continue
        dl     = dish_level.get(did, {})
        ing    = ingredients_by_dish.get(did, [])
        loc    = location_by_dish.get(did, "Birmingham")
        meta   = rest_meta.get(s["restaurant"], {})
        claims = claims_by_restaurant.get(s["restaurant"], [])

        # Derived filter results — keyed by filter slug, empty dict if none.
        # Includes both macro-elimination filters (No Beef / No Pork) and the
        # nine allergen-elimination filters (No Wheat / Milk / Egg / Soy / Sesame
        # / Peanut / Tree Nut / Fish / Shellfish Ingredients Identified).
        # All fields preserved: conclusion, evidence_used, reasoning, limitations,
        # rule_ids, confidence, status. Consumer label translation is the
        # presentation layer's responsibility (GP-RULE-016).
        derived_entry   = derived_filters_data.get(did, {})
        derived_filters = derived_entry.get("filters", {})

        # Allergen disclosures — Evidence System (GP-RULE-014).
        # System A: restaurant-disclosed allergen status, separate from derived_filters.
        # dish-scope rows for this Dish_ID + restaurant-scope rows for this Restaurant_ID.
        # Raw evidence only — no consumer labels, no confidence tokens (GP-RULE-016).
        restaurant_id = dl.get("restaurant_id", "")
        allergen_disclosures = (
            allergen_disclosures_by_dish.get(did, []) +
            allergen_disclosures_by_restaurant.get(restaurant_id, [])
        )

        # Public output only — no scores, sub-scores, notes, or internal fields
        dish = {
            "id":                   s["id"],
            "name":                 s["name"],
            "restaurant":           s["restaurant"],
            "restaurant_id":        restaurant_id,
            "location":             loc,
            "level":                s["level"],
            "tags":                 dl.get("tags", []),
            "tag_source":           dl.get("tag_source"),
            "options":              dl.get("options", []),
            "allergens":            dl.get("allergens", "Unknown"),
            "hours":                dl.get("hours", ""),
            "menu_link":            dl.get("menu_link", ""),
            "restaurant_address":   dl.get("restaurant_address", ""),
            "restaurant_website":   dl.get("restaurant_website", ""),
            "ingredients":          ing,
            "category":             dl.get("category", ""),
            "last_updated":         dl.get("last_updated", ""),
            "allergen_disclosures": allergen_disclosures,
            "derived_filters":      derived_filters,
        }
        # Legacy menu_statement from restaurant_meta.json
        if meta.get("menu_statement"):
            dish["menu_statement"] = meta["menu_statement"]
        # Restaurant-level claims (sourcing, certifications, etc.)
        if claims:
            dish["restaurant_claims"] = claims
        dishes.append(dish)

    dishes.sort(key=lambda d: d["id"])

    # ── Deduplicate by (restaurant, name) — keep dish with most ingredients;
    #    tie-break on lower ID (which sorts first after the sort above).
    seen = {}
    deduped = []
    for d in dishes:
        key = (d["restaurant"].lower(), d["name"].lower())
        if key not in seen:
            seen[key] = d
            deduped.append(d)
        else:
            existing = seen[key]
            if len(d.get("ingredients", [])) > len(existing.get("ingredients", [])):
                # Replace existing with this richer entry
                deduped[deduped.index(existing)] = d
                seen[key] = d
                print(f"  [dedup] {d['id']} supersedes {existing['id']} ({d['name']} @ {d['restaurant']})")
            else:
                print(f"  [dedup] dropped {d['id']} (duplicate of {existing['id']}: {d['name']} @ {d['restaurant']})")
    dishes = deduped

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(dishes, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(dishes)} dishes to {OUTPUT_FILE}")

    # ── Derived filters report ───────────────────────────────────────────────
    exported_ids        = {d["id"] for d in dishes}
    with_filters        = [d for d in dishes if d["derived_filters"]]
    without_filters     = [d for d in dishes if not d["derived_filters"]]
    missing_in_export   = [did for did in derived_filters_data if did not in exported_ids]

    print(f"\nDerived filters report:")
    print(f"  Total dishes exported:        {len(dishes)}")
    print(f"  Dishes with derived filters:  {len(with_filters)}")
    print(f"  Dishes without derived filters: {len(without_filters)}")
    if missing_in_export:
        print(f"  Derived results not in export (inactive/deduped): {len(missing_in_export)}")
        for mid in sorted(missing_in_export)[:10]:
            print(f"    {mid}")
        if len(missing_in_export) > 10:
            print(f"    ... and {len(missing_in_export) - 10} more")
    else:
        print(f"  No derived results outside export.")

    # ── Sample dish with derived filters ────────────────────────────────────
    sample = next((d for d in dishes if d["derived_filters"]), None)
    if sample:
        print(f"\nSample dish with derived filters ({sample['id']} — {sample['name']}):")
        print(json.dumps(sample, indent=2, ensure_ascii=False)[:1200])

    # ── 7. Assemble restaurants.json ────────────────────────────────────────
    # First pass: scan ALL dishes per restaurant to find the best
    # (non-empty) value for each field — not just the first dish encountered.
    rest_fields = {}
    for dish in dishes:
        rname = dish["restaurant"]
        if rname not in rest_fields:
            rest_fields[rname] = {
                "location": "", "hours": "", "menu_link": "",
                "restaurant_address": "", "restaurant_website": "",
            }
        f = rest_fields[rname]
        if not f["location"]           and dish.get("location"):           f["location"]           = dish["location"]
        if not f["hours"]              and dish.get("hours"):              f["hours"]              = dish["hours"]
        if not f["menu_link"]          and dish.get("menu_link"):          f["menu_link"]          = dish["menu_link"]
        if not f["restaurant_address"] and dish.get("restaurant_address"): f["restaurant_address"] = dish["restaurant_address"]
        if not f["restaurant_website"] and dish.get("restaurant_website"): f["restaurant_website"] = dish["restaurant_website"]

    # Second pass: build restaurants_map, falling back to restaurant_coords.json
    restaurants_map = {}
    for rname, f in rest_fields.items():
        coords = coords_meta.get(rname, {})
        restaurants_map[rname] = {
            "name":               rname,
            "location":           f["location"],
            "hours":              f["hours"]              or coords.get("hours",     ""),
            "menu_link":          f["menu_link"]          or coords.get("menu_link", ""),
            "restaurant_address": f["restaurant_address"] or coords.get("address",   ""),
            "restaurant_website": f["restaurant_website"] or coords.get("website",   ""),
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
