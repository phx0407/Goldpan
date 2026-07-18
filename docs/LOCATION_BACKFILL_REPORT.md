# GoldPan™ Location Data Backfill Report
**Version:** 1.0  
**Date:** 2026-07-06  
**Status:** Open — Backfill Required  
**Classification:** Data Completeness Gap (not a migration failure)

---

## Summary

During the initial Supabase migration (`migrate_sheets_to_supabase.py`), restaurant location data was imported from the spreadsheet `Location` column as a single free-form `location` field (e.g. `"Hoover"`, `"Birmingham, AL"`). The structured columns `address`, `city`, `state`, and geocoordinate fields (`latitude`, `longitude`) were **not populated** because the source spreadsheet did not contain them in structured form.

This is a data completeness gap, not a schema error. The columns exist in `evidence.restaurants` (added in `002_evidence_tables.sql`). They are simply empty for all pre-migration restaurants.

**Impact:** Until backfilled, the BD partner auto-fill falls back to parsing `location`. City can usually be derived; state may be partially derivable from `"City, ST"` format. Address is unavailable. Map geocoding requires city+state at minimum.

---

## Known State (From Migration Audit)

The import script (`migrate_sheets_to_supabase.py`, line 512) set:

```python
"location": s(row.get("Location")),  # Free-form, e.g. "Hoover"
```

It did not set `address`, `city`, or `state`. The `official_website` field was populated from a separate Registry sheet. Geocoordinate fields (`latitude`, `longitude`) do not exist on `evidence.restaurants` — they live on `operations.partners` after geocoding.

---

## Backfill Categories

Run the following SQL in Supabase SQL Editor to get current counts:

```sql
SELECT
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE address IS NULL)               AS missing_address,
  COUNT(*) FILTER (WHERE city IS NULL)                  AS missing_city,
  COUNT(*) FILTER (WHERE state IS NULL)                 AS missing_state,
  COUNT(*) FILTER (
    WHERE location IS NOT NULL
      AND city IS NULL AND state IS NULL AND address IS NULL
  )                                                      AS location_only,
  COUNT(*) FILTER (
    WHERE location IS NULL
      AND city IS NULL AND state IS NULL AND address IS NULL
  )                                                      AS no_location_at_all,
  COUNT(*) FILTER (WHERE city IS NOT NULL AND state IS NOT NULL) AS fully_structured
FROM evidence.restaurants
WHERE lifecycle_status != 'deactivated';
```

To list all restaurants needing backfill:

```sql
SELECT
  external_id,
  name,
  location,
  address,
  city,
  state,
  lifecycle_status
FROM evidence.restaurants
WHERE lifecycle_status != 'deactivated'
  AND (city IS NULL OR state IS NULL OR address IS NULL)
ORDER BY external_id;
```

---

## Gap Categories

### Category 1 — Missing address

All pre-migration restaurants. The spreadsheet contained only a free-form `Location` column.

**Required action:** During the next recanvass of each restaurant, the canvasser must capture the full street address from the official website or ordering platform and write it into the Intake packet as `restaurant_address`.

**Interim handling:** Address field is blank in BD auto-fill. No substitute is available.

### Category 2 — Missing city / state (structured)

All pre-migration restaurants. City and state are null; the `location` field contains the data in free-form (e.g. `"Hoover"` or `"Hoover, AL"`).

**Required action:** Backfill `city` and `state` by parsing the `location` field. Script below.

**Interim handling:** The `/admin/restaurants/lookup` FastAPI endpoint derives `city` and `state` from `location` using `_parse_location()` as a fallback. This covers the BD auto-fill UI until the database is backfilled.

### Category 3 — Location-only (no structured data)

All pre-migration restaurants that have `location` but no `city`, `state`, or `address`.

**Required action:** Both the structured backfill (Category 2) and recanvass (Category 1).

**Flag:** These restaurants should be considered **Location Backfill Required** — see Tagging section below.

### Category 4 — No location data at all

Restaurants with no `location`, `city`, `state`, or `address`. These cannot be placed on any map or associated with a geographic market.

**Required action:** Immediate recanvass priority.

### Category 5 — Missing geocoordinates (partner records)

Applies to `operations.partners`, not `evidence.restaurants`. Partners without `latitude`/`longitude` cannot appear on the BD map. Auto-geocoding runs from `city`+`state` on create/update.

**Required action:** Edit any partner record (even without changes) to trigger geocoding once city+state are populated from the restaurant backfill.

---

## Backfill Script

Save as `scripts/location_backfill.py` and run locally. Parses `location` into `city`/`state` for all restaurants where structured fields are null.

```python
#!/usr/bin/env python3
"""
location_backfill.py — Backfill city/state from free-form location field.

Parses "Hoover" → city="Hoover", state=None
Parses "Hoover, AL" → city="Hoover", state="AL"
Parses "Birmingham, AL" → city="Birmingham", state="AL"

Only writes rows where city IS NULL or state IS NULL.
Dry-run by default — pass --commit to write.
"""

import os, sys
from dotenv import load_dotenv

load_dotenv(".env")
from supabase import create_client

DRY_RUN = "--commit" not in sys.argv


def parse_location(location: str | None) -> tuple[str | None, str | None]:
    if not location:
        return (None, None)
    parts = [p.strip() for p in location.split(",")]
    city  = parts[0] if parts[0] else None
    state = parts[1].upper() if len(parts) >= 2 and parts[1].strip() else None
    return (city, state)


def main():
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    res = (
        sb.schema("evidence").table("restaurants")
        .select("restaurant_id,external_id,name,location,city,state")
        .or_("city.is.null,state.is.null")
        .execute()
    )
    rows = res.data
    print(f"Rows needing city/state backfill: {len(rows)}")

    updated = 0
    skipped = 0
    for r in rows:
        parsed_city, parsed_state = parse_location(r.get("location"))
        city  = r.get("city")  or parsed_city
        state = r.get("state") or parsed_state

        if not city and not state:
            print(f"  SKIP {r['external_id']} — no location to parse: {r.get('location')}")
            skipped += 1
            continue

        print(f"  {'DRY' if DRY_RUN else 'UPD'} {r['external_id']:<8} {r['name'][:30]:<30} → city={city}, state={state}")

        if not DRY_RUN:
            sb.schema("evidence").table("restaurants").update(
                {"city": city, "state": state}
            ).eq("restaurant_id", r["restaurant_id"]).execute()
            updated += 1
        else:
            updated += 1

    print(f"\nWould update: {updated} | Skip (no parseable location): {skipped}")
    if DRY_RUN:
        print("DRY RUN — pass --commit to write changes.")


if __name__ == "__main__":
    main()
```

Run dry run first:
```bash
python3 scripts/location_backfill.py
```

Commit when satisfied:
```bash
python3 scripts/location_backfill.py --commit
```

---

## Tagging Recommendation (Future)

Add a `location_quality` enum to `evidence.restaurants`:

| Value | Meaning |
|---|---|
| `structured` | Has city + state (and ideally address) from verified source |
| `location_only` | Has free-form location only — backfill required |
| `geocoded` | Has structured address + lat/lng |
| `unknown` | No location data of any kind |

This allows the Restaurant OS dashboard to surface and track backfill progress without requiring a separate audit script.

---

## Long-Term Resolution

1. **Run `location_backfill.py --commit`** to populate `city`/`state` from `location` for all existing restaurants.
2. **During each recanvass**, capture `restaurant_address` per the new Intake Location Standard.
3. **On each partner edit/create**, geocoding auto-runs from `city`+`state` in `operations.partners`.
4. **Restaurant map** (Phase 4 feature) will require geocoordinates on the restaurant record itself — add `latitude`/`longitude` to `evidence.restaurants` in a future migration.

---

## Related Documents

- `docs/GOLDPAN_MASTER_OS_BLUEPRINT.md` — Section 5d: Location Data Standard
- `docs/INTAKE_AGENT_STANDARD.md` — Location Fields section
- `supabase/migrations/002_evidence_tables.sql` — schema definition
- `migrate_sheets_to_supabase.py` — original import (source of gap)
