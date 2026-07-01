"""
backfill_enrichment.py — One-time enrichment migration for Ingredient Details.

Fills blank enrichment fields on existing rows using only verified sources.
Never infers. Never overwrites. Never guesses.

Policy:
  VERIFIED FILL   — a confirmed value exists from a verified source (DLD, staging file,
                    schema default). Write the value.
  UNKNOWN FILL    — the source was reviewed during canvassing but the detail was not
                    captured (e.g. live menu listed ingredient names only). Write "Unknown".
  NEEDS CANVASSING — no source has been reviewed for this row. Leave blank and report.

Report sections:
  [1] Fields populated from verified source data
  [2] Fields marked Unknown (reviewed, detail not captured)
  [3] Rows that still need menu canvassing before enrichment can be completed

Source hierarchy used:
  Status           → parent dish status from Goldpan Dish Level Data
  Version          → schema default "1" (not source-dependent)
  Ingredient_Source → "menu" if dish is in a staging file or known-canvassed patch;
                      "Unknown" if provenance is unrecorded
  Cut_Type         → staging file ingredient data, or Unknown if dish was canvassed
                      but detail not captured
  Preparation      → same as Cut_Type
  Ingredient_Type  → same as Cut_Type
  Allergen_Flags   → same as Cut_Type
  Component_Role   → same as Cut_Type

Usage:
    python3 backfill_enrichment.py             # dry run — shows what would change
    python3 backfill_enrichment.py --apply     # apply all fills
"""

import json
import os
import sys
import datetime
import gspread
from google.oauth2.service_account import Credentials

GOLDPAN_DIR    = os.path.dirname(os.path.abspath(__file__))
KEY_FILE       = os.path.join(GOLDPAN_DIR, "service_account.json")
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TODAY          = datetime.date.today().isoformat()
DRY_RUN        = "--apply" not in sys.argv

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Canonical field lists
REQUIRED_FIELDS    = ["Restaurant_ID", "Restaurant_Name", "Location",
                      "Dish_ID", "Dish_Name", "Ingredient"]
ENRICHMENT_FIELDS  = ["Cut_Type", "Preparation", "Ingredient_Type", "Status",
                      "Version", "Ingredient_Source", "Allergen_Flags", "Component_Role"]
ALL_FIELDS         = REQUIRED_FIELDS + ENRICHMENT_FIELDS

# Fields that are safe to fill from verified non-staging sources
SAFE_DEFAULT_FIELDS = {"Status", "Version"}

# Fields that come from staging ingredient records or the canvass fallback
STAGING_FIELDS = {"Cut_Type", "Preparation", "Ingredient_Type",
                  "Ingredient_Source", "Allergen_Flags", "Component_Role"}

# Staging Ingredient_Type values outside the canonical enum → remap to Unknown
NON_CANONICAL_TYPES = {
    "house", "vegetable", "dairy", "coating", "legume", "nut/seed",
    "nut", "fruit", "filling", "cheese", "grain", "spice",
}

# ── Dishes canvassed via patch scripts (no staging file) ──────────────────────
# These dishes were reviewed from a real source during canvassing, but only
# ingredient names were captured — not cut type, preparation, allergens, etc.
# Enrichment fields for these rows = Unknown (reviewed, detail not captured).
# Ingredient_Source = the source used during canvassing.
CANVASSED_DISHES = {
    # Adam & Eve Cafe — patch_adamandevecafe.py
    # Source: https://www.adamandevecafe.com/menu (live menu, June 27 2026)
    "D064": "menu", "D065": "menu", "D066": "menu", "D067": "menu",
    "D068": "menu", "D069": "menu", "D071": "menu", "D072": "menu",
    "D073": "menu", "D077": "menu", "D078": "menu", "D079": "menu",
    "D080": "menu", "D081": "menu", "D082": "menu", "D083": "menu",

    # Brick & Tin Mountain Brook — patch_brickandtin_ingredients.py
    # Source: physical menu (screenshots, June 27 2026)
    "D015": "menu", "D111": "menu",

    # Emmy Squared — patch_emmysquared.py
    # Source: unknown — pre-dates patch documentation
    "D021": "Unknown", "D233": "Unknown", "D235": "Unknown",
    "D239": "Unknown", "D241": "Unknown", "D249": "Unknown",
}


# ── Normalize staging values to sheet policy values ───────────────────────────

NORMALIZE = {"none": "None", "unknown": "Unknown", "n/a": "N/A", "na": "N/A"}

def norm(raw):
    """Normalize a raw staging value to sheet policy format.
    Returns None (Python None) if the raw value is empty."""
    if not raw and raw != 0:
        return None
    v = str(raw).strip()
    if not v:
        return None
    return NORMALIZE.get(v.lower(), v)


def norm_ingredient_type(raw):
    """Normalize Ingredient_Type. Non-canonical values → Unknown."""
    v = norm(raw)
    if v is None:
        return None, False
    if v.lower() in NON_CANONICAL_TYPES:
        return "Unknown", True   # remapped
    return v, False


# ── Load staging ingredient lookup ────────────────────────────────────────────

def build_staging_lookup():
    """
    Returns:
      ingredient_data: {(dish_id, ingredient_name_lower): {field: value, ...}}
      dish_in_staging: {dish_id: staging_filename}
    """
    ingredient_data = {}
    dish_in_staging = {}

    for fname in sorted(os.listdir(GOLDPAN_DIR)):
        if not (fname.startswith("staging_") and fname.endswith(".json")):
            continue
        try:
            with open(os.path.join(GOLDPAN_DIR, fname), encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"  WARNING: could not load {fname}: {e}")
            continue

        for dish in data.get("dishes", []):
            did = str(dish.get("dish_id", "")).strip()
            if not did:
                continue
            dish_in_staging[did] = fname
            for ing in dish.get("ingredients", []):
                name = str(ing.get("name", "")).strip()
                if not name:
                    continue
                key = (did, name.lower())
                if key not in ingredient_data:
                    ingredient_data[key] = {
                        "Cut_Type":         norm(ing.get("cut_type",  "")),
                        "Preparation":      norm(ing.get("preparation", "")),
                        "Ingredient_Type":  norm_ingredient_type(ing.get("type", ""))[0],
                        "Ingredient_Source": "menu",   # staging = collected from menu canvass
                        "Allergen_Flags":   norm(str(ing.get("allergen_flags", ""))),
                        "Component_Role":   norm(ing.get("role", "")),
                        "staging_file":     fname,
                    }

    return ingredient_data, dish_in_staging


# ── Load DLD status lookup ─────────────────────────────────────────────────────

def build_dld_lookup(ss):
    """Returns {dish_id: 'Active'|'Inactive'|''} from Goldpan Dish Level Data."""
    try:
        ws  = ss.worksheet("Goldpan Dish Level Data")
        rows = ws.get_all_values()
    except Exception as e:
        print(f"  WARNING: could not read Goldpan Dish Level Data: {e}")
        return {}
    if len(rows) < 2:
        return {}
    hdrs    = [h.strip() for h in rows[0]]
    did_idx = hdrs.index("Dish_ID")   if "Dish_ID" in hdrs else None
    st_idx  = hdrs.index("Status")    if "Status"  in hdrs else None
    lookup  = {}
    for row in rows[1:]:
        did = row[did_idx].strip() if did_idx is not None and did_idx < len(row) else ""
        st  = row[st_idx].strip()  if st_idx  is not None and st_idx  < len(row) else ""
        if did:
            lookup[did] = st
    return lookup


# ── Resolve one enrichment field for one row ──────────────────────────────────

# Result categories (used in the three-section report)
CAT_VERIFIED  = "verified"     # filled from a confirmed source
CAT_UNKNOWN   = "unknown_fill" # dish was reviewed; detail not captured → write Unknown
CAT_CANVASS   = "needs_canvass" # no source reviewed yet → leave blank

def resolve(field, dish_id, ingredient_name,
            ingredient_data, dish_in_staging, dld_lookup):
    """
    Returns (value_to_write, category, source_note).
    value_to_write = None means do not write (leave blank).
    """
    key = (dish_id, ingredient_name.lower())

    # ── Status: always resolvable from DLD ────────────────────────────────────
    if field == "Status":
        st = dld_lookup.get(dish_id, "")
        if st in ("Active", "Inactive"):
            return st, CAT_VERIFIED, "Goldpan Dish Level Data"
        # Dish not found in DLD — still write Unknown so row is not blank
        return "Unknown", CAT_UNKNOWN, "Goldpan Dish Level Data (dish not found)"

    # ── Version: safe schema default, no source review required ───────────────
    if field == "Version":
        return "1", CAT_VERIFIED, "schema default (initial version)"

    # ── Ingredient_Source ─────────────────────────────────────────────────────
    if field == "Ingredient_Source":
        if dish_id in dish_in_staging:
            return "menu", CAT_VERIFIED, f"staging file: {dish_in_staging[dish_id]}"
        if dish_id in CANVASSED_DISHES:
            src = CANVASSED_DISHES[dish_id]
            return src, CAT_VERIFIED, "canvassed dish (patch script provenance)"
        return None, CAT_CANVASS, "dish not in staging and not in canvassed dishes map"

    # ── Staging-backed enrichment fields ──────────────────────────────────────
    ing = ingredient_data.get(key)

    if ing is not None:
        # Dish + ingredient found in a staging file
        val = ing.get(field)
        if val is not None:
            return val, CAT_VERIFIED, f"staging file: {ing['staging_file']}"
        # Staging file exists but this specific field is blank in it
        return "Unknown", CAT_UNKNOWN, f"staging file reviewed ({ing['staging_file']}); field blank"

    # No staging record for this (dish_id, ingredient) pair
    if dish_id in dish_in_staging:
        # Dish IS in a staging file but this ingredient isn't listed there
        return "Unknown", CAT_UNKNOWN, \
               f"dish in staging ({dish_in_staging[dish_id]}) but ingredient not listed"

    if dish_id in CANVASSED_DISHES:
        # Menu was reviewed during canvassing; detail not captured at ingredient level
        return "Unknown", CAT_UNKNOWN, \
               "canvassed dish — menu reviewed; ingredient-level detail not captured"

    # Truly unreviewed — needs canvassing
    return None, CAT_CANVASS, "no source reviewed for this dish/ingredient"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    mode = "DRY RUN — no writes" if DRY_RUN else "APPLY MODE — writing to sheet"
    print(f"\nbackfill_enrichment.py  —  {TODAY}")
    print(f"{'='*65}")
    print(f"  {mode}")
    print(f"{'='*65}\n")

    # ── Load local data sources ────────────────────────────────────────────────
    print("Loading staging files...")
    ingredient_data, dish_in_staging = build_staging_lookup()
    print(f"  {len(ingredient_data)} ingredient records  |  "
          f"{len(dish_in_staging)} dishes in staging\n")

    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    print("Loading Goldpan Dish Level Data...")
    dld_lookup = build_dld_lookup(ss)
    print(f"  {len(dld_lookup)} dishes\n")

    print("Reading Ingredient Details...")
    ing_ws    = ss.worksheet("Ingredient Details")
    all_rows  = ing_ws.get_all_values()
    if len(all_rows) < 2:
        print("ERROR: Ingredient Details is empty or header-only.")
        return

    raw_headers = all_rows[0]
    headers     = [h.strip() for h in raw_headers]

    # Validate that every expected field has a column in the sheet
    col = {}
    missing_cols = []
    for f in ALL_FIELDS:
        try:
            col[f] = headers.index(f)
        except ValueError:
            col[f] = None
            missing_cols.append(f)

    if missing_cols:
        print(f"  ERROR: the following columns were NOT found in the sheet headers:")
        for mc in missing_cols:
            print(f"    '{mc}'")
        print(f"  Actual headers: {headers}")
        print(f"  Cannot proceed until column names match. Exiting.")
        return

    # Print resolved column map so every run self-documents its bindings
    print(f"  Resolved column map:")
    for f in ALL_FIELDS:
        marker = "  [enrichment]" if f in ENRICHMENT_FIELDS else "  [required] "
        print(f"    col[{col[f]:>2}]  {f:<22}{marker}")
    print(f"  {len(all_rows)-1} rows  |  {len(headers)} columns  ✓\n")

    # ── Scan every row ─────────────────────────────────────────────────────────
    updates = []   # gspread batch_update payload

    # Three report buckets
    verified_fills  = []  # (row, dish_id, restaurant, ingredient, field, value, source)
    unknown_fills   = []  # same shape
    needs_canvass   = []  # (row, dish_id, restaurant, ingredient, field, reason)

    for i, row in enumerate(all_rows[1:], start=2):
        def cell(f):
            idx = col[f]
            return row[idx].strip() if idx < len(row) else ""

        dish_id    = cell("Dish_ID")
        ingredient = cell("Ingredient")
        restaurant = cell("Restaurant_Name")

        for field in ENRICHMENT_FIELDS:
            existing = cell(field)

            # General rule: never overwrite an existing value.
            # Exception — Ingredient_Source only:
            #   Old versions of upsert_dishes.py wrote the staging JSON's "source"
            #   field (food ingredient origin: "house", "grass-fed", "organic", etc.)
            #   into Ingredient_Source, producing the value "unknown" for most rows.
            #   That "unknown" is a script placeholder, NOT a reviewed provenance
            #   decision. If a verified source now supports a better value, upgrade it.
            #   Only upgrade if the current value is exactly "unknown" (case-insensitive)
            #   and a staging file or CANVASSED_DISHES entry provides a real source.
            if existing:
                if field == "Ingredient_Source" and existing.lower() == "unknown":
                    if dish_id in dish_in_staging or dish_id in CANVASSED_DISHES:
                        pass  # fall through to resolve() — allow upgrade
                    else:
                        continue  # no source available, keep as-is
                else:
                    continue  # never overwrite any other field

            value, category, source = resolve(
                field, dish_id, ingredient,
                ingredient_data, dish_in_staging, dld_lookup,
            )

            if value is not None and category in (CAT_VERIFIED, CAT_UNKNOWN):
                col_idx = col[field]  # guaranteed non-None (checked above)
                cell_addr = gspread.utils.rowcol_to_a1(i, col_idx + 1)
                updates.append({"range": cell_addr, "values": [[value]]})

                entry = (i, dish_id, restaurant, ingredient, field, value, source)
                if category == CAT_VERIFIED:
                    verified_fills.append(entry)
                else:
                    unknown_fills.append(entry)

            elif category == CAT_CANVASS:
                needs_canvass.append((i, dish_id, restaurant, ingredient, field, source))

    # ── Report ─────────────────────────────────────────────────────────────────
    total_writes = len(verified_fills) + len(unknown_fills)

    print(f"{'='*65}")
    print(f"BACKFILL REPORT  —  {TODAY}")
    print(f"{'='*65}")
    print(f"  Total writes{'(planned)' if DRY_RUN else ''}  : {total_writes}")
    print(f"  [1] Verified source fills : {len(verified_fills)}")
    print(f"  [2] Unknown fills         : {len(unknown_fills)}")
    print(f"  [3] Needs canvassing      : {len(needs_canvass)}")
    print()

    # Section 1: Verified fills
    if verified_fills:
        print(f"{'─'*65}")
        print("[1] FIELDS POPULATED FROM VERIFIED SOURCE DATA")
        print(f"{'─'*65}")
        by_field = {}
        for entry in verified_fills:
            _, did, rn, ing, field, value, source = entry
            by_field.setdefault(field, []).append((did, rn, ing, value, source))
        for field in ENRICHMENT_FIELDS:
            rows = by_field.get(field, [])
            if rows:
                # Show unique (value, source) pairs and counts
                combos = {}
                for did, rn, ing, val, src in rows:
                    combos[(val, src)] = combos.get((val, src), 0) + 1
                print(f"\n  {field} — {len(rows)} rows")
                for (val, src), cnt in sorted(combos.items(), key=lambda x: -x[1]):
                    print(f"    {cnt}x  '{val}'  ← {src}")
        print()

    # Section 2: Unknown fills
    if unknown_fills:
        print(f"{'─'*65}")
        print("[2] FIELDS MARKED Unknown — SOURCE REVIEWED, DETAIL NOT CAPTURED")
        print(f"{'─'*65}")
        by_restaurant = {}
        for _, did, rn, ing, field, val, source in unknown_fills:
            by_restaurant.setdefault(rn, {}).setdefault(field, 0)
            by_restaurant[rn][field] += 1

        print()
        print(f"  {'Restaurant':<38}  {'Fields → Unknown':}")
        print(f"  {'─'*38}")
        for rn in sorted(by_restaurant):
            field_summary = ", ".join(
                f"{f}: {by_restaurant[rn][f]}"
                for f in ENRICHMENT_FIELDS if f in by_restaurant[rn]
            )
            print(f"  {rn:<38}  {field_summary}")
        print()

        by_field = {}
        for _, did, rn, ing, field, val, src in unknown_fills:
            by_field.setdefault(field, []).append(src)
        print("  Reason by field:")
        for field in ENRICHMENT_FIELDS:
            reasons = by_field.get(field, [])
            if reasons:
                unique_reasons = {}
                for r in reasons:
                    unique_reasons[r] = unique_reasons.get(r, 0) + 1
                print(f"    {field} ({len(reasons)} rows):")
                for reason, cnt in sorted(unique_reasons.items(), key=lambda x: -x[1]):
                    print(f"      {cnt}x  {reason}")
        print()

    # Section 3: Needs canvassing
    if needs_canvass:
        print(f"{'─'*65}")
        print("[3] ROWS REQUIRING MENU CANVASSING BEFORE ENRICHMENT")
        print(f"{'─'*65}")
        by_restaurant = {}
        for _, did, rn, ing, field, reason in needs_canvass:
            by_restaurant.setdefault(rn, set()).add(did)

        print(f"\n  {'Restaurant':<38}  Dishes needing review")
        print(f"  {'─'*38}")
        for rn, dishes in sorted(by_restaurant.items()):
            print(f"  {rn:<38}  {len(dishes)} dishes: {', '.join(sorted(dishes))}")
        print()

        # Field breakdown
        field_counts = {}
        for _, did, rn, ing, field, reason in needs_canvass:
            field_counts[field] = field_counts.get(field, 0) + 1
        print("  Blank fields by type:")
        for field in ENRICHMENT_FIELDS:
            if field in field_counts:
                print(f"    {field:<22} : {field_counts[field]} rows")
        print()
    else:
        print(f"{'─'*65}")
        print("[3] NEEDS CANVASSING: none — all rows have been reviewed")
        print()

    # ── Apply ──────────────────────────────────────────────────────────────────
    if DRY_RUN:
        print(f"{'='*65}")
        print(f"DRY RUN COMPLETE.")
        print(f"  {total_writes} cells would be written  "
              f"({len(verified_fills)} verified + {len(unknown_fills)} Unknown).")
        if needs_canvass:
            unique_canvass_dishes = {r[1] for r in needs_canvass}
            print(f"  {len(needs_canvass)} field slots still need canvassing "
                  f"({len(unique_canvass_dishes)} dishes).")
        print()
        print("To apply:")
        print("  python3 backfill_enrichment.py --apply")
        print("Then confirm:")
        print("  python3 analyze_enrichment.py")
        print("  python3 validate_database.py")

    else:
        if not updates:
            print("Nothing to write — all resolvable fields are already populated.")
        else:
            print(f"{'='*65}")
            print(f"APPLYING {len(updates)} cell updates...")
            chunk_size = 500
            for start in range(0, len(updates), chunk_size):
                chunk = updates[start : start + chunk_size]
                ing_ws.batch_update(chunk, value_input_option="USER_ENTERED")
                print(f"  {start + len(chunk)} / {len(updates)} cells written")
            print(f"\n  ✓ Done.")
            print(f"  {len(verified_fills)} verified fills.")
            print(f"  {len(unknown_fills)} Unknown fills.")
            if needs_canvass:
                unique_canvass_dishes = {r[1] for r in needs_canvass}
                print(f"  {len(needs_canvass)} field slots still need canvassing "
                      f"({len(unique_canvass_dishes)} dishes).")

        # ── Post-apply verification ────────────────────────────────────────────
        # Re-read the sheet and check every row we *intended* to process.
        # A processed row = one we attempted to write at least one field on,
        # OR one whose dish_id was in staging or CANVASSED_DISHES
        # (meaning a source was reviewed for it).
        # If such a row still has blank enrichment fields, report FAIL.
        print(f"\n{'='*65}")
        print("POST-APPLY VERIFICATION")
        print(f"{'='*65}")
        print("Re-reading Ingredient Details from sheet...")
        verified_sheet = ing_ws.get_all_values()
        post_headers   = [h.strip() for h in verified_sheet[0]]
        post_col       = {f: post_headers.index(f) for f in ALL_FIELDS}

        # Build set of row numbers we processed (wrote at least one cell on)
        processed_rows = {u["range"] for u in updates}
        # Translate to sheet row numbers — we know row i was processed if
        # any update targeted rowcol_to_a1(i, ...).
        processed_row_nums = set()
        for u in updates:
            # gspread A1 notation: parse row number from cell address
            addr = u["range"]
            # strip letters, parse digits
            row_num = int("".join(c for c in addr if c.isdigit()))
            processed_row_nums.add(row_num)

        # Also include any row whose dish is in staging or CANVASSED_DISHES
        # (source was reviewed even if no blank fields remained to fill)
        for i, row in enumerate(verified_sheet[1:], start=2):
            did = row[post_col["Dish_ID"]].strip() if post_col["Dish_ID"] < len(row) else ""
            if did in dish_in_staging or did in CANVASSED_DISHES:
                processed_row_nums.add(i)

        post_failures = []
        for i, row in enumerate(verified_sheet[1:], start=2):
            if i not in processed_row_nums:
                continue
            did    = row[post_col["Dish_ID"]].strip()      if post_col["Dish_ID"]         < len(row) else ""
            rname  = row[post_col["Restaurant_Name"]].strip() if post_col["Restaurant_Name"] < len(row) else ""
            ing    = row[post_col["Ingredient"]].strip()   if post_col["Ingredient"]      < len(row) else ""
            for field in ENRICHMENT_FIELDS:
                val = row[post_col[field]].strip() if post_col[field] < len(row) else ""
                if not val:
                    # Find the reason from needs_canvass (if available)
                    reason = next(
                        (nc[5] for nc in needs_canvass
                         if nc[0] == i and nc[4] == field),
                        "blank after apply — source review incomplete",
                    )
                    post_failures.append((i, did, rname, ing, field, reason))

        if post_failures:
            print(f"\n  FAIL — {len(post_failures)} blank enrichment fields remain in processed rows:\n")
            print(f"  {'Row':<5}  {'Dish_ID':<8}  {'Restaurant':<30}  {'Ingredient':<30}  {'Field':<20}  Reason")
            print(f"  {'─'*5}  {'─'*8}  {'─'*30}  {'─'*30}  {'─'*20}  {'─'*40}")
            for row_num, did, rname, ing, field, reason in post_failures:
                print(f"  {row_num:<5}  {did:<8}  {rname:<30}  {ing:<30}  {field:<20}  {reason}")
            print(f"\n  Action required: canvass the restaurants above to resolve remaining blanks.")
        else:
            print(f"\n  PASS — no blank enrichment fields in any processed row.")
        print()
        print("Next:")
        print("  python3 analyze_enrichment.py")
        print("  python3 validate_database.py")


if __name__ == "__main__":
    main()
