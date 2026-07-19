#!/usr/bin/env python3
"""
identity_enrichment.py  —  GoldPan Restaurant Identity Enrichment Pipeline
v1.1.0

Entry-point agnostic: runs against active restaurants regardless of how they
entered GoldPan (BD, Intake, Portal, bulk import, future API).

Fields populated:
    google_place_id, address, city, state, postal_code,
    latitude, longitude, phone

Enrichment strategy:
    1. Google Places API  (full enrichment — requires GOOGLE_PLACES_API_KEY)
       Find Place from text → Place Details → structured address + phone + coords
    2. Nominatim fallback (geocoding only — no API key required)
       Used ONLY if Google Places is unavailable or returns no result.
       Nominatim fills latitude/longitude only — never fills address/phone.

Safety rules:
    - Never overwrites existing non-null values unless --overwrite is passed.
    - Never invents street addresses from city-level geocoding.
    - Never uses delivery platforms (DoorDash, Yelp, etc.) as sources.
    - Low-confidence Places results are skipped and flagged for manual review.
    - R026 is reserved for manual review (in MANUAL_SKIP) unless removed.
    - Dry run by default — pass --commit to write to the database.

Usage:
    python3 scripts/identity_enrichment.py                        # dry run
    python3 scripts/identity_enrichment.py --commit               # write
    python3 scripts/identity_enrichment.py --overwrite            # allow overwriting non-null
    python3 scripts/identity_enrichment.py --commit --overwrite
    python3 scripts/identity_enrichment.py --restaurant R001      # single restaurant

Environment variables (.env):
    SUPABASE_URL                required
    SUPABASE_SERVICE_ROLE_KEY   required
    GOOGLE_PLACES_API_KEY       optional — enables Places enrichment
                                Without this, only Nominatim geocoding runs.
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv(".env")

try:
    from supabase import create_client
except ImportError:
    print("ERROR: supabase package not found. Run: pip install supabase")
    sys.exit(1)

# ── Configuration ─────────────────────────────────────────────────────────────

DRY_RUN         = "--commit" not in sys.argv
OVERWRITE       = "--overwrite" in sys.argv
ONLY_RESTAURANT = None  # set via --restaurant R001
for i, arg in enumerate(sys.argv):
    if arg == "--restaurant" and i + 1 < len(sys.argv):
        ONLY_RESTAURANT = sys.argv[i + 1].upper()

# Restaurants reserved for manual backfill — not touched by this script
MANUAL_SKIP = {"R026"}

# Restaurants that must NOT receive city-centroid coordinates.
# These require a real street address (from Places or manual entry) before
# lat/lng can be written. Nominatim geocoding will be skipped for these IDs
# even if address is available only at city level.
NO_CENTROID_IDS = {"R001", "R003", "R007", "R010", "R011", "R016"}

# Birmingham metro cities — city mismatches within this set are treated as
# acceptable when state=AL and the name match is strong. Places is more
# authoritative than our city field for intra-metro suburb differences.
BIRMINGHAM_METRO_CITIES = {
    "birmingham", "hoover", "homewood", "vestavia hills", "mountain brook",
    "pelham", "alabaster", "helena", "trussville", "gardendale", "center point",
    "fairfield", "bessemer", "fultondale", "clay", "leeds", "irondale",
    "moody", "pell city", "hueytown", "midfield",
}

# Market context for Nominatim scoping.
# City-only geocoding resolves to wrong state without context:
#   "Homewood, USA" → Illinois  ✗
#   "Homewood, Alabama, USA" → Alabama  ✓
NOMINATIM_MARKET_CONTEXT = "Alabama"

NOMINATIM_UA    = "GoldPan-IdentityEnrichment/1.0 (internal; contact bradcad1@gmail.com)"
NOMINATIM_DELAY = 1.1   # Nominatim rate limit: 1 req/s

PLACES_DELAY    = 0.1   # Google Places has generous rate limits; small courtesy delay
PLACES_BASE     = "https://maps.googleapis.com/maps/api/place"

# Minimum word-overlap to consider a Places result name trustworthy
MIN_NAME_TOKEN_OVERLAP = 1

# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class EnrichmentResult:
    google_place_id: Optional[str] = None
    address:         Optional[str] = None
    city:            Optional[str] = None
    state:           Optional[str] = None
    postal_code:     Optional[str] = None
    latitude:        Optional[float] = None
    longitude:       Optional[float] = None
    phone:           Optional[str] = None
    source:          str = "none"
    confidence:      str = "none"   # verified | declared | inferred | low

@dataclass
class ReviewItem:
    external_id: str
    name:        str
    reason:      str
    detail:      str = ""

# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_name(s: str) -> set[str]:
    """
    Tokenize a restaurant name for fuzzy matching.

    Handles:
    - CamelCase / CompoundWords: insert space before each uppercase letter
      that follows a lowercase letter ("SluttyVegan" → "Slutty Vegan")
    - All-caps: passed through unchanged ("BLUEROOT" stays "BLUEROOT" but
      lowercased to "blueroot" — handled by concat check in names_similar)
    """
    # Split CamelCase: "EastWest" → "East West", "SluttyVegan" → "Slutty Vegan"
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
    return set(re.sub(r"[^a-z0-9\s]", "", s.lower()).split())


def names_similar(a: str, b: str) -> bool:
    """
    True if two restaurant names are likely the same, handling:
    - Token overlap: "Slutty Vegan" vs "SluttyVegan Birmingham"
    - CamelCase splits: "East West" vs "EastWest"
    - Concatenated forms: "Blue Root" vs "BLUEROOT"
    - City suffixes in Places names: "Name, Birmingham, AL" style
    """
    STOP = {"the", "a", "an", "of", "and", "or", "at", "in", "on", "by", "for",
            "to", "restaurant", "cafe", "kitchen", "grill", "bar", "house"}

    # 1. Token overlap (handles CamelCase via normalize_name)
    ta = normalize_name(a) - STOP
    tb = normalize_name(b) - STOP
    if not ta or not tb:
        ta, tb = normalize_name(a), normalize_name(b)
    if len(ta & tb) >= MIN_NAME_TOKEN_OVERLAP:
        return True

    # 2. Concatenated form: "blue root" == "blueroot", "sluttyvegan" ⊆ "sluttyveganbirmingham"
    a_concat = re.sub(r"[^a-z0-9]", "", a.lower())
    b_concat = re.sub(r"[^a-z0-9]", "", b.lower())
    if a_concat and b_concat:
        if a_concat in b_concat or b_concat in a_concat:
            return True

    return False


def parse_address_components(components: list[dict]) -> tuple[
    Optional[str], Optional[str], Optional[str], Optional[str]
]:
    """
    Extract (street_address, city, state, postal_code) from Google Places
    address_components array.

    Returns (None, None, None, None) on empty input.
    """
    mapping = {
        "street_number": "",
        "route":         "",
        "locality":      "",                      # city
        "administrative_area_level_1": "",        # state (short_name = "AL")
        "postal_code":   "",
    }
    for c in components:
        for t in c.get("types", []):
            if t in mapping:
                if t == "administrative_area_level_1":
                    mapping[t] = c.get("short_name", "")
                else:
                    mapping[t] = c.get("long_name", "")

    number = mapping["street_number"]
    route  = mapping["route"]
    street = f"{number} {route}".strip() if (number or route) else None
    city   = mapping["locality"] or None
    state  = mapping["administrative_area_level_1"] or None
    postal = mapping["postal_code"] or None
    return street, city, state, postal


def field_is_missing(row: dict, key: str) -> bool:
    """True if the field is null/empty in the restaurant row."""
    v = row.get(key)
    return v is None or (isinstance(v, str) and not v.strip())


def needs_enrichment(row: dict) -> bool:
    """True if any target field is missing (or OVERWRITE is set)."""
    targets = ["google_place_id", "address", "city", "state",
               "postal_code", "latitude", "longitude", "phone"]
    if OVERWRITE:
        return True
    return any(field_is_missing(row, f) for f in targets)

# ── Google Places ─────────────────────────────────────────────────────────────

def places_find(name: str, city: Optional[str], state: Optional[str],
                api_key: str) -> Optional[dict]:
    """
    Step 1: Find Place from text → returns basic match with place_id.
    Returns the first result dict, or None.
    """
    location_hint = ", ".join(filter(None, [city, state, "USA"]))
    query = f"{name}, {location_hint}" if location_hint else name

    params = urllib.parse.urlencode({
        "input":      query,
        "inputtype":  "textquery",
        "fields":     "place_id,name,formatted_address,geometry",
        "key":        api_key,
    })
    url = f"{PLACES_BASE}/findplacefromtext/json?{params}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        candidates = data.get("candidates", [])
        return candidates[0] if candidates else None
    except Exception as exc:
        print(f"    [Places findplace error: {exc}]")
        return None


def places_details(place_id: str, api_key: str) -> Optional[dict]:
    """
    Step 2: Place Details → returns address_components and phone number.
    Returns the result dict, or None.
    """
    params = urllib.parse.urlencode({
        "place_id": place_id,
        "fields":   "name,formatted_phone_number,address_components",
        "key":      api_key,
    })
    url = f"{PLACES_BASE}/details/json?{params}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data.get("result")
    except Exception as exc:
        print(f"    [Places details error: {exc}]")
        return None


def enrich_via_places(row: dict, api_key: str) -> tuple[Optional[EnrichmentResult], str]:
    """
    Full Google Places enrichment for one restaurant.
    Returns (EnrichmentResult, reason_string).
    reason_string is non-empty only on skip/failure.
    """
    name  = row["name"]
    city  = row.get("city")
    state = row.get("state")

    time.sleep(PLACES_DELAY)
    candidate = places_find(name, city, state, api_key)
    if not candidate:
        return None, "Places returned no candidates"

    places_name = candidate.get("name", "")
    if not names_similar(name, places_name):
        return None, (
            f"Places name mismatch: our={name!r} vs places={places_name!r}"
        )

    # Geometry (lat/lng) from Find Place result
    geometry = candidate.get("geometry", {}).get("location", {})
    lat = geometry.get("lat")
    lng = geometry.get("lng")
    place_id = candidate["place_id"]

    # Step 2: Place Details for address_components + phone
    time.sleep(PLACES_DELAY)
    details = places_details(place_id, api_key)
    if not details:
        # Use what we have from Find Place — no address components, no phone
        return EnrichmentResult(
            google_place_id=place_id,
            latitude=lat,
            longitude=lng,
            source="google_places",
            confidence="declared",
        ), ""

    components = details.get("address_components", [])
    street, p_city, p_state, p_postal = parse_address_components(components)
    phone = details.get("formatted_phone_number")

    # Confidence check: state must match
    if state and p_state and state.upper() != p_state.upper():
        return None, (
            f"Places state mismatch: ours={state!r} vs places={p_state!r}"
        )

    # City check: mismatch within the Birmingham metro is acceptable.
    # Places is more authoritative than our city field for intra-metro suburbs
    # (e.g. we have "Hoover", Places returns "Birmingham" for the same location).
    city_mismatch = city and p_city and city.lower() != p_city.lower()
    if city_mismatch:
        both_in_metro = (
            p_state and p_state.upper() == "AL"
            and city.lower() in BIRMINGHAM_METRO_CITIES
            and p_city.lower() in BIRMINGHAM_METRO_CITIES
        )
        if both_in_metro:
            print(f"    note: city differs within Birmingham metro "
                  f"({city!r} → {p_city!r}) — accepting Places result")
        else:
            return None, (
                f"Places city mismatch: ours={city!r} vs places={p_city!r}"
            )

    return EnrichmentResult(
        google_place_id=place_id,
        address=street,
        city=p_city,
        state=p_state,
        postal_code=p_postal,
        latitude=lat,
        longitude=lng,
        phone=phone,
        source="google_places",
        confidence="declared",
    ), ""

# ── Nominatim geocoding (fallback) ────────────────────────────────────────────

def geocode_via_nominatim(row: dict) -> Optional[EnrichmentResult]:
    """
    Nominatim fallback: fills latitude/longitude from a known street address only.

    Requires address + city/state. City-centroid geocoding (city+state with no
    street address) is intentionally not supported — it produces inaccurate
    pin placement and should never be written to the database.

    Never fills address, city, state, or postal_code from Nominatim.
    """
    address = row.get("address")
    city    = row.get("city")
    state   = row.get("state")

    if not address or not (city or state):
        # Refuse to geocode without a street address.
        # Callers should send these to manual_review instead.
        return None

    parts = [p for p in [address, city, state, "USA"] if p]
    q_str = ", ".join(parts)
    query = urllib.parse.urlencode({
        "q": q_str, "format": "json", "limit": "1", "countrycodes": "us",
    })

    url = f"https://nominatim.openstreetmap.org/search?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": NOMINATIM_UA})

    try:
        time.sleep(NOMINATIM_DELAY)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if not data:
            return None
        return EnrichmentResult(
            latitude=float(data[0]["lat"]),
            longitude=float(data[0]["lon"]),
            source="nominatim",
            confidence="inferred",
        )
    except Exception as exc:
        print(f"    [Nominatim error: {exc}]")
        return None

# ── Field merge: apply EnrichmentResult to restaurant row ─────────────────────

def build_update_payload(row: dict, result: EnrichmentResult) -> dict:
    """
    Build the Supabase update dict from an EnrichmentResult.
    Respects OVERWRITE: only writes fields that are currently null (or all if OVERWRITE).
    """
    candidate = {
        "google_place_id":            result.google_place_id,
        "address":                    result.address,
        "city":                       result.city,
        "state":                      result.state,
        "postal_code":                result.postal_code,
        "latitude":                   result.latitude,
        "longitude":                  result.longitude,
        "phone":                      result.phone,
        "identity_enrichment_source": result.source,
    }

    payload = {}
    for key, new_val in candidate.items():
        if new_val is None:
            continue  # nothing to write
        if key == "identity_enrichment_source":
            payload[key] = new_val  # always update source metadata
            continue
        existing = row.get(key)
        if existing is None or (isinstance(existing, str) and not existing.strip()):
            payload[key] = new_val  # field is empty — safe to fill
        elif OVERWRITE:
            payload[key] = new_val  # --overwrite flag set — overwrite
        # else: field has a value and OVERWRITE is off — skip silently

    return payload

# ── Printing ──────────────────────────────────────────────────────────────────

def fmt_val(v) -> str:
    if v is None or (isinstance(v, str) and not v.strip()):
        return "·"
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


def print_before_after(row: dict, payload: dict) -> None:
    FIELDS = [
        ("google_place_id", "place_id"),
        ("address",         "address"),
        ("city",            "city"),
        ("state",           "state"),
        ("postal_code",     "postal"),
        ("latitude",        "lat"),
        ("longitude",       "lng"),
        ("phone",           "phone"),
    ]
    changes = []
    for key, label in FIELDS:
        old = fmt_val(row.get(key))
        new = fmt_val(payload.get(key))
        if key in payload and old != new:
            changes.append(f"{label}: {old} → {new}")
    if changes:
        for c in changes:
            print(f"      {c}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    sb_url = os.environ.get("SUPABASE_URL")
    sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not sb_url or not sb_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        sys.exit(1)

    places_api_key = os.environ.get("GOOGLE_PLACES_API_KEY")

    sb = create_client(sb_url, sb_key)

    # ── Fetch restaurants ──────────────────────────────────────────────────────
    query = (
        sb.schema("evidence").table("restaurants")
        .select(
            "restaurant_id,external_id,name,location,address,city,state,"
            "zip,postal_code,latitude,longitude,phone,official_website,"
            "google_place_id,lifecycle_status"
        )
        .neq("lifecycle_status", "deactivated")
        .neq("lifecycle_status", "suspended")
        .order("external_id")
    )
    if ONLY_RESTAURANT:
        query = query.eq("external_id", ONLY_RESTAURANT)

    res   = query.execute()
    rows  = res.data

    # ── Summary header ─────────────────────────────────────────────────────────
    mode_tag = "DRY RUN" if DRY_RUN else "COMMIT"
    print("=" * 70)
    print(f"  GoldPan Identity Enrichment  [{mode_tag}]")
    print(f"  Google Places:  {'ENABLED' if places_api_key else 'DISABLED (set GOOGLE_PLACES_API_KEY)'}")
    print(f"  Nominatim:      ENABLED (geocoding fallback)")
    print(f"  Overwrite:      {'YES' if OVERWRITE else 'NO'}")
    if ONLY_RESTAURANT:
        print(f"  Scope:          {ONLY_RESTAURANT} only")
    print(f"  Restaurants:    {len(rows)} found")
    print("=" * 70)
    print()

    # ── Per-restaurant enrichment ──────────────────────────────────────────────
    n_enriched    = 0
    n_skipped     = 0
    n_manual_skip = 0
    n_no_change   = 0
    manual_review: list[ReviewItem] = []

    for row in rows:
        eid  = row["external_id"]
        name = row["name"]

        # Manual skip list
        if eid in MANUAL_SKIP:
            print(f"  MANUAL_SKIP    {eid:<8} {name}")
            n_manual_skip += 1
            continue

        # Nothing to enrich
        if not needs_enrichment(row):
            print(f"  COMPLETE       {eid:<8} {name}")
            n_no_change += 1
            continue

        print(f"  ENRICHING      {eid:<8} {name}")

        result    = None
        skip_reason = ""

        # ── Path 1: Google Places ──────────────────────────────────────────────
        if places_api_key:
            result, skip_reason = enrich_via_places(row, places_api_key)
            if result:
                print(f"    source: google_places  confidence: {result.confidence}")
            else:
                print(f"    google_places: {skip_reason}")

        # ── Path 2: Nominatim fallback (street-address geocoding only) ───────────
        if result is None:
            needs_coords = (
                field_is_missing(row, "latitude") or field_is_missing(row, "longitude")
            )
            has_address = not field_is_missing(row, "address")

            if not needs_coords:
                print(f"    nominatim: lat/lng already set — skipped")
            elif eid in NO_CENTROID_IDS:
                print(f"    nominatim: skipped — {eid} in NO_CENTROID_IDS "
                      f"(requires Google Places or manual entry)")
            elif not has_address:
                print(f"    nominatim: skipped — no street address, "
                      f"city centroid coordinates refused")
            else:
                nom = geocode_via_nominatim(row)
                if nom:
                    result = nom
                    print(f"    source: nominatim (address geocode)  "
                          f"confidence: {result.confidence}")
                else:
                    print(f"    nominatim: no result for address")

        # ── No result at all ───────────────────────────────────────────────────
        if result is None:
            if eid in NO_CENTROID_IDS:
                reason = (skip_reason or "Places returned no result") + \
                         " — in NO_CENTROID_IDS, requires Places or manual entry"
            elif field_is_missing(row, "address"):
                reason = (skip_reason or "Places returned no result") + \
                         " — no street address, city centroid refused"
            else:
                reason = skip_reason or "no enrichment source produced a result"
            print(f"    → MANUAL REVIEW: {reason}")
            manual_review.append(ReviewItem(
                external_id=eid,
                name=name,
                reason=reason,
            ))
            n_skipped += 1
            continue

        # ── Build update payload ───────────────────────────────────────────────
        payload = build_update_payload(row, result)
        # Always stamp enrichment timestamp
        from datetime import datetime, timezone
        payload["identity_enriched_at"] = datetime.now(timezone.utc).isoformat()

        if not payload or list(payload.keys()) == ["identity_enriched_at", "identity_enrichment_source"]:
            print(f"    → no new fields to write")
            n_no_change += 1
            continue

        print_before_after(row, payload)

        tag = "DRY" if DRY_RUN else "WRITE"
        print(f"    → [{tag}] {len([k for k in payload if k not in ('identity_enriched_at','identity_enrichment_source')])} field(s)")

        if not DRY_RUN:
            sb.schema("evidence").table("restaurants").update(
                payload
            ).eq("restaurant_id", row["restaurant_id"]).execute()

        n_enriched += 1
        print()

    # ── Summary footer ─────────────────────────────────────────────────────────
    print()
    print("─" * 70)
    print(f"  Restaurants scanned:    {len(rows)}")
    print(f"  Enriched / updated:     {n_enriched}")
    print(f"  Already complete:       {n_no_change}")
    print(f"  Manual skip (MANUAL_SKIP):  {n_manual_skip}")
    print(f"  Needs manual review:    {len(manual_review) + n_skipped}")

    if manual_review:
        print()
        print("  MANUAL REVIEW list:")
        for item in manual_review:
            print(f"    {item.external_id:<8} {item.name[:40]:<40} — {item.reason}")

    if not places_api_key:
        print()
        print("  NOTE: GOOGLE_PLACES_API_KEY is not set.")
        print("  Only Nominatim geocoding (lat/lng) ran.")
        print("  To enrich address, postal_code, phone, and google_place_id:")
        print("    1. Obtain a Google Places API key")
        print("    2. Add GOOGLE_PLACES_API_KEY=<key> to .env")
        print("    3. Re-run this script")

    if DRY_RUN:
        print()
        print("  DRY RUN — no changes written.")
        print("  Run with --commit to apply.")
    else:
        print()
        print(f"  COMMITTED — {n_enriched} restaurant(s) updated.")

    # ── Write machine-readable manual review list ──────────────────────────────
    if manual_review:
        out_path = "docs/identity_enrichment_manual_review.json"
        with open(out_path, "w") as f:
            json.dump(
                [{"external_id": r.external_id, "name": r.name, "reason": r.reason}
                 for r in manual_review],
                f, indent=2
            )
        print()
        print(f"  Manual review list written to: {out_path}")


if __name__ == "__main__":
    main()
