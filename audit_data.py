"""
audit_data.py — Goldpan data completeness audit.

Reads dishes.json and restaurants.json and reports missing or empty
values for every field that should be populated.

Usage:
    python3 audit_data.py
    python3 audit_data.py --summary   (restaurant-level summary only)
"""

import json
import sys
import os
from collections import defaultdict

GOLDPAN_DIR      = os.path.dirname(os.path.abspath(__file__))
DISHES_FILE      = os.path.join(GOLDPAN_DIR, "dishes.json")
RESTAURANTS_FILE = os.path.join(GOLDPAN_DIR, "restaurants.json")

SUMMARY_ONLY = "--summary" in sys.argv

# Fields that every dish should have
DISH_REQUIRED = {
    "name":               "Dish name",
    "restaurant":         "Restaurant",
    "location":           "Location",
    "level":              "Transparency level",
    "allergens":          "Allergen summary",
    "hours":              "Hours",
    "menu_link":          "Menu link",
    "restaurant_address": "Restaurant address",
    "restaurant_website": "Restaurant website",
    "category":           "Category",
}

# Fields that are important but not strictly required
DISH_RECOMMENDED = {
    "ingredients": "Ingredients",
    "tags":        "Dietary tags",
}

# Fields every restaurant should have
REST_REQUIRED = {
    "name":               "Name",
    "location":           "Location",
    "hours":              "Hours",
    "menu_link":          "Menu link",
    "restaurant_address": "Restaurant address",
    "restaurant_website": "Restaurant website",
}

def is_empty(val):
    if val is None:
        return True
    if isinstance(val, str):
        return not val.strip() or val.strip().lower() in ("unknown", "none", "")
    if isinstance(val, list):
        return len(val) == 0
    return False


def main():
    with open(DISHES_FILE) as f:
        dishes = json.load(f)
    with open(RESTAURANTS_FILE) as f:
        restaurants = json.load(f)

    # ── Restaurant audit ──────────────────────────────────────────────────────
    print("=" * 60)
    print("RESTAURANT COMPLETENESS")
    print("=" * 60)

    rest_issues = {}
    for r in restaurants:
        name = r.get("name", "?")
        missing = []
        for field, label in REST_REQUIRED.items():
            if is_empty(r.get(field)):
                missing.append(label)
        if missing:
            rest_issues[name] = missing

    if rest_issues:
        for name, missing in sorted(rest_issues.items()):
            print(f"\n  {name}")
            for m in missing:
                print(f"    ✗ {m}")
    else:
        print("  ✅ All restaurants have required fields.")

    # ── Dish audit — grouped by restaurant ───────────────────────────────────
    print("\n" + "=" * 60)
    print("DISH COMPLETENESS BY RESTAURANT")
    print("=" * 60)

    by_restaurant = defaultdict(list)
    for d in dishes:
        by_restaurant[d["restaurant"]].append(d)

    grand_total   = 0
    grand_issues  = 0

    for rname in sorted(by_restaurant.keys()):
        rdishes  = by_restaurant[rname]
        issues   = []

        for d in rdishes:
            dish_issues = []
            for field, label in DISH_REQUIRED.items():
                if is_empty(d.get(field)):
                    dish_issues.append(label)
            for field, label in DISH_RECOMMENDED.items():
                if is_empty(d.get(field)):
                    dish_issues.append(f"{label} ⚠")
            if dish_issues:
                issues.append((d["name"], dish_issues))

        grand_total  += len(rdishes)
        grand_issues += len(issues)

        complete_count = len(rdishes) - len(issues)
        pct = complete_count / len(rdishes) * 100

        status = "✅" if pct == 100 else ("🟡" if pct >= 70 else "🔴")
        print(f"\n{status} {rname} — {complete_count}/{len(rdishes)} complete ({pct:.0f}%)")

        if not SUMMARY_ONLY and issues:
            for dish_name, dish_issues in issues:
                print(f"    {dish_name}")
                for i in dish_issues:
                    print(f"      ✗ {i}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    complete = grand_total - grand_issues
    print(f"  Total dishes     : {grand_total}")
    print(f"  Fully complete   : {complete} ({complete/grand_total*100:.1f}%)")
    print(f"  Have gaps        : {grand_issues} ({grand_issues/grand_total*100:.1f}%)")
    print(f"  Restaurants with issues: {len(rest_issues)}")
    print()

    # Field-level breakdown
    print("  Missing field frequency (dishes):")
    field_counts = defaultdict(int)
    for d in dishes:
        for field, label in {**DISH_REQUIRED, **DISH_RECOMMENDED}.items():
            if is_empty(d.get(field)):
                field_counts[label] += 1
    for label, count in sorted(field_counts.items(), key=lambda x: -x[1]):
        bar = "█" * (count // 5)
        print(f"    {label:<30} {count:>4}  {bar}")


if __name__ == "__main__":
    main()
