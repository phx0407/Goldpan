#!/usr/bin/env python3
"""
location_backfill.py — Backfill city/state from free-form location field.

Resolution order for state when only city is known:
  1. Parse from location string (e.g. "Hoover, AL" → "AL")
  2. Geocode via Nominatim using city name
  3. Fall back to DEFAULT_STATE if geocoding fails or is disabled
  4. If DEFAULT_STATE is None, leave state null and report "Needs Manual Review"

Dry-run by default — pass --commit to write.

Usage:
    python3 scripts/location_backfill.py                      # dry run
    python3 scripts/location_backfill.py --commit             # write to database
    python3 scripts/location_backfill.py --no-geocode         # skip geocoding, use DEFAULT_STATE only
    python3 scripts/location_backfill.py --commit --no-geocode
"""

import os
import sys
import time
from typing import Optional

from dotenv import load_dotenv

load_dotenv(".env")

try:
    from supabase import create_client
except ImportError:
    print("ERROR: supabase package not found. Run: pip install supabase")
    sys.exit(1)

# ── Configuration ─────────────────────────────────────────────────────────────

DRY_RUN    = "--commit" not in sys.argv
USE_GEOCODE = "--no-geocode" not in sys.argv

# TODO: Replace with market-based config once GoldPan markets are defined.
# Each market should supply its own context so this script generalises to
# Nashville, Atlanta, Houston, etc. without manual edits.
# Set to None to disable the fallback entirely and require geocoding or manual review.
DEFAULT_STATE: Optional[str] = None

# Market context used to qualify geocoding queries.
# Geocoding "Homewood, USA" resolves to Illinois — unsafe for a Birmingham-market dataset.
# Setting MARKET_CONTEXT = "Alabama" makes the query "Homewood, Alabama, USA".
# TODO: Replace with per-market config once GoldPan markets are defined.
# If None, geocoding is skipped entirely and unresolved rows go to manual review.
MARKET_CONTEXT: Optional[str] = "Alabama"

# Restaurants to skip entirely — require manual backfill before commit
MANUAL_BACKFILL = {"R026"}

# Nominatim requires a unique User-Agent (free, no API key)
NOMINATIM_UA = "GoldPan-LocationBackfill/1.0 (internal; contact bradcad1@gmail.com)"
NOMINATIM_DELAY = 1.1  # seconds between requests — Nominatim rate limit is 1 req/s


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_location(location: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Derive (city, state) from a free-form location string.

    "Hoover"         → ("Hoover", None)
    "Hoover, AL"     → ("Hoover", "AL")
    "Birmingham, AL" → ("Birmingham", "AL")
    ""               → (None, None)
    """
    if not location or not location.strip():
        return (None, None)
    parts = [p.strip() for p in location.split(",")]
    city  = parts[0] if parts[0] else None
    state = parts[1].upper() if len(parts) >= 2 and parts[1].strip() else None
    return (city, state)


def geocode_city(city: str, market_context: str) -> Optional[str]:
    """
    Attempt to resolve state from city name via Nominatim, qualified by market context.

    City-only geocoding is unsafe — "Homewood" resolves to Illinois nationally.
    market_context (e.g. "Alabama") scopes the query to the correct region:
      "Homewood, Alabama, USA" → AL  ✓
      "Homewood, USA"          → IL  ✗

    Returns two-letter US state abbreviation, or None on failure.
    """
    import urllib.request
    import urllib.parse
    import json

    # US state name → abbreviation
    STATE_ABBR = {
        "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
        "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
        "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
        "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
        "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
        "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
        "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
        "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
        "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
        "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
        "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
        "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
        "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC",
    }

    query = urllib.parse.urlencode({
        "q": f"{city}, {market_context}, USA",
        "format": "json",
        "addressdetails": "1",
        "limit": "1",
        "countrycodes": "us",
    })
    url = f"https://nominatim.openstreetmap.org/search?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": NOMINATIM_UA})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if not data:
            return None
        address = data[0].get("address", {})
        state_name = address.get("state", "")
        return STATE_ABBR.get(state_name)
    except Exception as exc:
        print(f"    [geocode error: {exc}]")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        sys.exit(1)

    sb = create_client(url, key)

    res = (
        sb.schema("evidence").table("restaurants")
        .select("restaurant_id,external_id,name,location,city,state,lifecycle_status")
        .neq("lifecycle_status", "deactivated")
        .execute()
    )
    all_rows = res.data
    rows = [r for r in all_rows if not r.get("city") or not r.get("state")]

    print(f"Total non-deactivated restaurants: {len(all_rows)}")
    print(f"Missing city or state:             {len(rows)}")
    print(f"Geocoding enabled:                 {USE_GEOCODE}")
    print(f"Market context:                    {MARKET_CONTEXT!r}")
    print(f"DEFAULT_STATE fallback:            {DEFAULT_STATE!r}")
    print()

    if not rows:
        print("Nothing to backfill. All restaurants have city and state.")
        return

    updated      = 0
    skipped      = 0
    needs_review = 0
    geocoded     = 0

    for r in rows:
        existing_city  = r.get("city")
        existing_state = r.get("state")
        parsed_city, parsed_state = parse_location(r.get("location"))

        # ── Manual backfill exceptions ────────────────────────────────────────
        if r["external_id"] in MANUAL_BACKFILL:
            print(f"  SKIP           {r['external_id']:<8} {r['name'][:35]:<35} "
                  f"(reserved for manual backfill)")
            skipped += 1
            continue

        new_city  = existing_city or parsed_city
        new_state = existing_state or parsed_state

        # ── Geocode to resolve missing state ─────────────────────────────────
        if new_city and not new_state:
            if USE_GEOCODE and MARKET_CONTEXT:
                print(f"  GEOCODING      {r['external_id']:<8} {r['name'][:35]:<35} "
                      f'"{new_city}, {MARKET_CONTEXT}, USA" …', end=" ", flush=True)
                time.sleep(NOMINATIM_DELAY)
                geo_state = geocode_city(new_city, MARKET_CONTEXT)
                if geo_state:
                    print(f"→ {geo_state}")
                    new_state = geo_state
                    geocoded += 1
                else:
                    print("→ not found")
            elif USE_GEOCODE and not MARKET_CONTEXT:
                # City-only geocoding is unsafe — skip and let manual review catch it
                print(f"  GEOCODE SKIP   {r['external_id']:<8} {r['name'][:35]:<35} "
                      f"(MARKET_CONTEXT not set — city-only geocoding disabled)")

            # ── DEFAULT_STATE fallback ────────────────────────────────────────
            if not new_state and DEFAULT_STATE:
                # TODO: Replace with per-market defaults once GoldPan markets
                # are defined. Market config should map market_id → default state
                # so this script generalises across Birmingham, Nashville, etc.
                new_state = DEFAULT_STATE
                print(f"  DEFAULT_STATE  {r['external_id']:<8} {r['name'][:35]:<35} "
                      f"→ state={repr(new_state)} (DEFAULT_STATE fallback)")

        # ── Still no state — flag for manual review ───────────────────────────
        if not new_state and new_city:
            print(f"  MANUAL REVIEW  {r['external_id']:<8} {r['name'][:35]:<35} "
                  f"city={repr(new_city)} — state could not be determined")
            needs_review += 1
            continue

        if not new_city and not new_state:
            print(f"  NO-DATA        {r['external_id']:<8} {r['name'][:35]:<35} "
                  f"location={repr(r.get('location'))}")
            needs_review += 1
            continue

        # ── Check whether anything actually changed ───────────────────────────
        changed = (new_city != existing_city) or (new_state != existing_state)
        if not changed:
            skipped += 1
            continue

        tag = "DRY" if DRY_RUN else "WRITE"
        print(f"  {tag:<13}  {r['external_id']:<8} {r['name'][:35]:<35} "
              f"city: {repr(existing_city)} → {repr(new_city)}  "
              f"state: {repr(existing_state)} → {repr(new_state)}")

        if not DRY_RUN:
            update_payload = {}
            if new_city != existing_city:
                update_payload["city"] = new_city
            if new_state != existing_state:
                update_payload["state"] = new_state
            sb.schema("evidence").table("restaurants").update(
                update_payload
            ).eq("restaurant_id", r["restaurant_id"]).execute()

        updated += 1

    print()
    print("─" * 60)
    print(f"Would update:          {updated}")
    print(f"Resolved via geocode:  {geocoded}")
    print(f"Already set / no-op:   {skipped}")
    print(f"Needs manual review:   {needs_review}")

    if needs_review:
        print()
        print("NOTE: Restaurants marked 'MANUAL REVIEW' or 'NO-DATA' were not")
        print("written. Update them directly in Supabase or re-run after adding")
        print("structured location data to their records.")

    if DRY_RUN:
        print()
        print("DRY RUN — no changes written.")
        print("Run with --commit to apply.")
    else:
        print()
        print(f"COMMITTED — {updated} rows updated.")


if __name__ == "__main__":
    main()
