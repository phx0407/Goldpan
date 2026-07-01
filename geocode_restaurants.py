"""
geocode_restaurants.py — Geocodes all restaurant addresses using OpenStreetMap Nominatim.
Writes coordinates to restaurant_coords.json.

Run AFTER patch_hours_addresses.py && bash update.sh so addresses are populated.

Usage:
    python3 geocode_restaurants.py
"""

import json
import time
import os
import requests

GOLDPAN_DIR     = os.path.dirname(os.path.abspath(__file__))
RESTAURANTS_FILE = os.path.join(GOLDPAN_DIR, "restaurants.json")
OUTPUT_FILE     = os.path.join(GOLDPAN_DIR, "restaurant_coords.json")

HEADERS = {"User-Agent": "Goldpan/1.0 (goldpanapp.com)"}

# Manual fallback coords for restaurants without addresses in the sheet
FALLBACK_ADDRESSES = {
    "Adam and Eve Cafe":       "1022 20th St S, Birmingham, AL 35205",
    "Brick & Tin":             "2901 Cahaba Rd, Mountain Brook, AL 35223",
    "Chop N Fresh":            "291 Rele St, Mountain Brook, AL 35223",
    "Chopt Creative Salad Co.":"331 Summit Blvd, Birmingham, AL 35243",
    "Clean Eatz":              "1021 Brocks Gap Pkwy, Hoover, AL 35244",
    "EastWest":                "2306 2nd Ave N, Birmingham, AL 35203",
    "SoHo Standard":           "1830 29th Ave S, Homewood, AL 35209",
    "The Essential":           "2215 1st Ave N, Birmingham, AL 35203",
}


def geocode(address):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        results = r.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"  Error: {e}")
    return None, None


def main():
    with open(RESTAURANTS_FILE) as f:
        restaurants = json.load(f)

    coords = {}
    for r in restaurants:
        name    = r["name"]
        address = r.get("restaurant_address", "").strip() or FALLBACK_ADDRESSES.get(name, "")

        if not address:
            print(f"[{name}] — no address, skipping")
            continue

        print(f"[{name}] geocoding: {address}")
        lat, lng = geocode(address)
        if lat and lng:
            print(f"  → {lat:.4f}, {lng:.4f}")
            coords[name] = {
                "lat": lat,
                "lng": lng,
                "address": address,
                "location": r.get("location", ""),
                "hours": r.get("hours", ""),
                "menu_link": r.get("menu_link", ""),
                "website": r.get("restaurant_website", ""),
            }
        else:
            print(f"  → geocoding failed")

        time.sleep(1.1)  # Nominatim rate limit: 1 req/sec

    with open(OUTPUT_FILE, "w") as f:
        json.dump(coords, f, indent=2)

    print(f"\n✅ Saved {len(coords)} coordinates to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
