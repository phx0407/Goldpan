"""
next_id.py — Calculate the next available Dish_ID and Restaurant_ID.

Reads dishes.json and restaurants.json (the live published data) to find
the current maximum IDs, then prints the next available values.

Never assign IDs manually from memory or from the UPSERT_GUIDE.md — always
run this script immediately before creating a new staging file.

Usage:
    python3 next_id.py

Output example:
    Next Dish_ID       : D686
    Next Restaurant_ID : R026
    (based on dishes.json: 685 dishes, restaurants.json: 25 restaurants)
"""

import json
import os
import re
import sys

GOLDPAN_DIR      = os.path.dirname(os.path.abspath(__file__))
DISHES_FILE      = os.path.join(GOLDPAN_DIR, "dishes.json")
RESTAURANTS_FILE = os.path.join(GOLDPAN_DIR, "restaurants.json")

DISH_ID_RE = re.compile(r"^D(\d+)$")
REST_ID_RE = re.compile(r"^R(\d+)$")


def parse_int_id(raw, pattern):
    """Return the integer portion of an ID string, or None if it doesn't match."""
    m = pattern.match(str(raw).strip())
    return int(m.group(1)) if m else None


def next_dish_id(dishes):
    nums = [parse_int_id(d.get("id", ""), DISH_ID_RE) for d in dishes]
    nums = [n for n in nums if n is not None]
    if not nums:
        return "D001"
    return f"D{max(nums) + 1}"


def next_restaurant_id(restaurants):
    """
    Restaurants in restaurants.json don't carry an ID field — we derive the
    max from the count of unique restaurants and assume sequential assignment.
    For a more precise answer, also scan staging files for the highest R-ID seen.
    """
    # Scan staging files for highest Restaurant_ID
    max_r = 0
    for fname in os.listdir(GOLDPAN_DIR):
        if not fname.startswith("staging_") or not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(GOLDPAN_DIR, fname), encoding="utf-8") as f:
                data = json.load(f)
            rid = data.get("restaurant_id", "")
            n = parse_int_id(rid, REST_ID_RE)
            if n is not None and n > max_r:
                max_r = n
        except Exception:
            continue

    if max_r == 0:
        # Fall back to count of restaurants
        max_r = len(restaurants)

    return f"R{max_r + 1:03d}"


def main():
    if not os.path.exists(DISHES_FILE):
        print(f"ERROR: {DISHES_FILE} not found. Run fetch_dishes.py first.")
        sys.exit(1)
    if not os.path.exists(RESTAURANTS_FILE):
        print(f"ERROR: {RESTAURANTS_FILE} not found. Run fetch_dishes.py first.")
        sys.exit(1)

    with open(DISHES_FILE, encoding="utf-8") as f:
        dishes = json.load(f)
    with open(RESTAURANTS_FILE, encoding="utf-8") as f:
        restaurants = json.load(f)

    next_d = next_dish_id(dishes)
    next_r = next_restaurant_id(restaurants)

    # Show the last few IDs for context
    nums_d = sorted(
        [parse_int_id(d.get("id", ""), DISH_ID_RE) for d in dishes
         if parse_int_id(d.get("id", ""), DISH_ID_RE) is not None],
        reverse=True,
    )
    recent_d = [f"D{n}" for n in nums_d[:5]]

    print()
    print(f"  Next Dish_ID       : {next_d}")
    print(f"  Next Restaurant_ID : {next_r}")
    print()
    print(f"  Based on:")
    print(f"    dishes.json       — {len(dishes)} active dishes")
    print(f"    restaurants.json  — {len(restaurants)} restaurants")
    print(f"    Recent Dish_IDs   : {', '.join(recent_d)}")
    print()
    print("  Always run this script immediately before creating a staging file.")
    print("  Never assign IDs from memory or from UPSERT_GUIDE.md.")
    print()


if __name__ == "__main__":
    main()
