"""
migrate_sheets_to_supabase.py — Migrate GoldPan data from Google Sheets to Supabase.

Reads five Google Sheets tabs:
  - Goldpan Dish Level Data (DLD)
  - Ingredient Details
  - Transparency Scoring
  - Menu Source Registry
  - Allergen Disclosures

Writes to Supabase:
  - evidence.restaurants           (one row per unique Restaurant_ID)
  - evidence.menu_sources          (one row per restaurant from Menu Source Registry)
  - evidence.dishes                (one row per dish from DLD)
  - evidence.ingredients           (one row per ingredient from Ingredient Details)
  - knowledge.transparency_scores  (one row per dish from Transparency Scoring)
  - evidence.allergen_disclosures  (one row per row from Allergen Disclosures)

Idempotency:
  - restaurants, dishes   → upsert on external_id (UNIQUE constraint in DB)
  - menu_sources          → upsert on restaurant_id (UNIQUE, migration 008)
  - ingredients           → upsert on source_row_hash (nullable TEXT, UNIQUE, migration 008)
                            MD5 fingerprint of content fields — set here for migrated rows,
                            NULL for API-created rows (NULLs don't conflict in PG UNIQUE)
  - transparency_scores   → pre-flight check; FORCE mode truncates then re-inserts
                            (partial unique index exists at DB level; supabase-py can't
                             pass the WHERE predicate for partial-index conflict resolution)
  - allergen_disclosures  → pre-flight check; FORCE mode truncates then re-inserts
                            (two partial unique indexes at DB level for future inserts;
                             same partial-index limitation as transparency_scores)

Prerequisites:
  pip install gspread google-auth supabase python-dotenv --break-system-packages
  Apply supabase/migrations/ 001–008 in order before running this script.

Credentials in .env (or environment):
  SUPABASE_URL              = https://xxxx.supabase.co
  SUPABASE_SERVICE_ROLE_KEY = eyJ...  (service role, NOT anon key — bypasses RLS)
  GOOGLE_SERVICE_ACCOUNT_FILE = service_account.json

Usage:
  python3 migrate_sheets_to_supabase.py           # dry run (no writes)
  python3 migrate_sheets_to_supabase.py --apply   # write to Supabase
  python3 migrate_sheets_to_supabase.py --apply --force  # truncate non-idempotent
                                                          # tables and re-seed

SECURITY: SUPABASE_SERVICE_ROLE_KEY bypasses all RLS policies.
          Use only locally. Never expose in client-side code or logs.
"""

import hashlib
import os
import sys
import datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

import gspread
from google.oauth2.service_account import Credentials
from supabase import create_client, Client

# ── Config ─────────────────────────────────────────────────────────────────────

GOLDPAN_DIR    = Path(__file__).parent
load_dotenv(GOLDPAN_DIR / ".env")

SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
KEY_FILE       = GOLDPAN_DIR / os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

APPLY = "--apply" in sys.argv
FORCE = "--force" in sys.argv   # truncate non-idempotent tables, then re-insert

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Tables that are NOT protected by a unique constraint suitable for supabase-py upsert.
# On re-run: normal mode skips; FORCE mode truncates then re-inserts.
NON_IDEMPOTENT_TABLES = [
    ("evidence",   "allergen_disclosures"),
    ("knowledge",  "transparency_scores"),
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_tab(ss: gspread.Spreadsheet, tab_name: str) -> list[dict]:
    """Return all rows from a sheet tab as list of dicts (header-keyed)."""
    try:
        ws   = ss.worksheet(tab_name)
        rows = ws.get_all_values()
    except gspread.exceptions.WorksheetNotFound:
        print(f"  WARNING: Tab '{tab_name}' not found — skipping.")
        return []
    if len(rows) < 2:
        return []
    headers = [h.strip() for h in rows[0]]
    return [
        {headers[i]: (row[i].strip() if i < len(row) else "")
         for i in range(len(headers))}
        for row in rows[1:]
        if any(cell.strip() for cell in row)   # skip blank rows
    ]


def load_tab_any(ss: gspread.Spreadsheet, *names: str) -> list:
    """
    Try each tab name in order and return rows from the first one found.
    If none exist, print a warning listing all candidates and return [].
    Used when a tab may have been created with either a space or underscore
    in the name (e.g. 'Allergen Disclosures' vs 'Allergen_Disclosures').
    """
    available = {ws.title for ws in ss.worksheets()}
    for name in names:
        if name in available:
            rows = load_tab(ss, name)
            if name != names[0]:
                print(f"  NOTE: Found tab as '{name}' (tried {list(names)})")
            return rows
    print(f"  WARNING: None of these tabs found: {list(names)} — skipping.")
    return []


def s(val) -> Optional[str]:
    """Return stripped string or None if empty."""
    v = str(val).strip() if val is not None else ""
    return v if v else None


def d(val) -> Optional[str]:
    """Return date string (YYYY-MM-DD) or None. Accepts ISO format only."""
    v = s(val)
    if not v:
        return None
    try:
        datetime.date.fromisoformat(v)
        return v
    except ValueError:
        return None


def n(val) -> Optional[float]:
    """Return numeric or None."""
    v = s(val)
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


# ── Preflight ──────────────────────────────────────────────────────────────────

def _preflight_check(sb: Client) -> dict[str, int]:
    """
    Verify all target tables exist and return current row counts.
    Aborts if a table is missing (means migrations were not applied).
    Warns if non-idempotent tables already have data (suggest --force).
    Returns a dict of {schema.table: row_count}.
    """
    print("Preflight: verifying Supabase tables...")
    target_tables = [
        ("evidence",  "restaurants"),
        ("evidence",  "menu_sources"),
        ("evidence",  "dishes"),
        ("evidence",  "ingredients"),
        ("knowledge", "transparency_scores"),
        ("evidence",  "allergen_disclosures"),
    ]

    existing_counts: dict[str, int] = {}

    for schema, table in target_tables:
        label = f"{schema}.{table}"
        try:
            result = (
                sb.schema(schema).table(table)
                .select("*", count="exact")
                .limit(0)
                .execute()
            )
            count = result.count or 0
            existing_counts[label] = count
            status = "empty" if count == 0 else f"{count} rows already present"
            print(f"  {label}: {status}")
        except Exception as e:
            print(f"\n  ERROR: Could not query {label} — {e}")
            print("  → Run migrations 001–008 in the Supabase SQL editor first.")
            sys.exit(1)

    # Warn about non-idempotent tables with existing data
    nonempty_non_idempotent = [
        f"{s}.{t}" for s, t in NON_IDEMPOTENT_TABLES
        if existing_counts.get(f"{s}.{t}", 0) > 0
    ]
    if nonempty_non_idempotent and not FORCE:
        print()
        print("  WARNING: The following tables already have data and do not have")
        print("  unique constraints suitable for upsert conflict resolution:")
        for label in nonempty_non_idempotent:
            print(f"    - {label} ({existing_counts[label]} rows)")
        print()
        print("  The migration will SKIP these tables on this run to avoid duplicates.")
        print("  To truncate and re-seed them, re-run with --apply --force.")

    print()
    return existing_counts


# ── Truncate helper ────────────────────────────────────────────────────────────

def _truncate_table(sb: Client, schema: str, table: str):
    """
    Delete all rows from a table via the Supabase REST API.
    The service role key bypasses RLS; the filter (created_at IS NOT NULL)
    matches every row since created_at is NOT NULL DEFAULT now().
    Used in FORCE mode for non-idempotent tables only.
    """
    label = f"{schema}.{table}"
    try:
        # PostgREST requires at least one filter on DELETE to prevent accidental
        # full-table deletes. All rows have created_at NOT NULL so this matches all.
        sb.schema(schema).table(table).delete().not_.is_("created_at", "null").execute()
        print(f"  Truncated {label}")
    except Exception as e:
        print(f"  ERROR truncating {label}: {e}")
        sys.exit(1)


# ── Write helpers ──────────────────────────────────────────────────────────────

def _write_restaurants(sb: Client, rows: list[dict]):
    """
    Insert restaurants in batches.
    - Normal mode: upsert with ignore_duplicates=True (skip on external_id conflict)
    - FORCE mode:  upsert with ignore_duplicates=False (overwrite on conflict)
    Uses supabase-py v2 upsert() which accepts on_conflict and ignore_duplicates.
    """
    if not rows:
        return
    BATCH = 100
    total = 0
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        result = sb.schema("evidence").table("restaurants").upsert(
            batch,
            on_conflict="external_id",
            ignore_duplicates=(not FORCE),
            count="exact",
        ).execute()
        total += result.count if result.count is not None else len(batch)
    action = "upserted" if FORCE else "inserted (skipped conflicts)"
    print(f"  evidence.restaurants: {total} rows {action}")


def _fetch_uuid_map(sb: Client, schema: str, table: str, ext_col: str) -> dict[str, str]:
    """Return dict mapping external_id value → UUID primary key."""
    pk_map = {
        "restaurants": "restaurant_id",
        "dishes":       "dish_id",
    }
    pk_col = pk_map.get(table)
    if not pk_col:
        raise ValueError(f"No PK mapping defined for table '{table}'")

    result = sb.schema(schema).table(table).select(f"{pk_col},{ext_col}").execute()
    return {
        row[ext_col]: row[pk_col]
        for row in result.data
        if row.get(ext_col)
    }


def _inject_fk(rows: list[dict], ext_col: str, uuid_map: dict, fk_col: str) -> list[dict]:
    """
    Add FK UUID column to each row by looking up the external_id in uuid_map.
    The original ext_col key is retained because it IS a real table column
    (denormalized for pipeline convenience per the schema design).
    """
    result = []
    for row in rows:
        new_row = dict(row)
        ext_val = row.get(ext_col)
        new_row[fk_col] = uuid_map.get(ext_val) if ext_val else None
        result.append(new_row)
    return result


def _write_rows_batched(
    sb: Client,
    schema: str,
    table: str,
    rows: list[dict],
    label: str,
    conflict_col: Optional[str],
):
    """
    Insert rows in batches.
    - If conflict_col is set: use upsert (supabase-py v2 syntax).
      Normal mode: ignore_duplicates=True (skip).
      FORCE mode:  ignore_duplicates=False (overwrite).
    - If conflict_col is None: plain insert (caller is responsible for
      ensuring the table was truncated in FORCE mode before calling this).
    """
    if not rows:
        print(f"  {label}: 0 rows")
        return
    BATCH = 200
    total = 0
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        if conflict_col:
            # supabase-py v2: upsert(json, on_conflict=str, ignore_duplicates=bool)
            sb.schema(schema).table(table).upsert(
                batch,
                on_conflict=conflict_col,
                ignore_duplicates=(not FORCE),
            ).execute()
        else:
            sb.schema(schema).table(table).insert(batch, returning="minimal").execute()
        total += len(batch)
    action = "upserted" if (conflict_col and FORCE) else "processed"
    print(f"  {label}: {total} rows {action}")


# ── Enum normalization maps ────────────────────────────────────────────────────
# Maps Sheets values → DB CHECK constraint values where the two diverge.

# Transparency_Level: Sheets uses both short ("Building") and long form
# ("Building Transparency"). The DB CHECK constraint requires the long form only.
TRANSPARENCY_LEVEL_MAP: dict[str, str] = {
    "Building":              "Building Transparency",
    "Moderate":              "Moderate Transparency",
    "High":                  "High Transparency",
    "Building Transparency": "Building Transparency",
    "Moderate Transparency": "Moderate Transparency",
    "High Transparency":     "High Transparency",
}


def normalize_transparency_level(val: Optional[str]) -> Optional[str]:
    """Coerce Sheets Transparency_Level to the DB CHECK constraint value, or None."""
    if not val:
        return None
    mapped = TRANSPARENCY_LEVEL_MAP.get(val.strip())
    if mapped is None:
        # Unknown value — pass through as None so the DB rejects it visibly
        # rather than silently inserting an invalid string.
        print(f"  WARNING: Unknown Transparency_Level value '{val}' — storing NULL")
    return mapped


# ── Ingredient content hash ────────────────────────────────────────────────────

def _ingredient_hash(row: dict) -> str:
    """
    Compute a stable MD5 fingerprint for an ingredient row.
    Used as source_row_hash to enable idempotent re-migration without
    constraining the data model.

    Hash inputs: the fields that uniquely identify one ingredient observation
    within a dish. All inputs are coerced to empty string when absent so the
    hash is always defined.

    A collision in a dataset of ~10,000 rows has probability ~10^-33.
    This is a deduplication fingerprint, not a security hash.
    """
    parts = [
        row.get("dish_external_id")   or "",
        row.get("ingredient_name")    or "",
        row.get("component_role")     or "",
        row.get("preparation")        or "",
        row.get("cut_type")           or "",
        row.get("allergen_flags")     or "",
        row.get("ingredient_type")    or "",
        row.get("ingredient_source")  or "",
    ]
    return hashlib.md5("|".join(parts).encode()).hexdigest()


# ── Post-migration row count validation ────────────────────────────────────────

def _validate_counts(sb: Client, source_counts: dict[str, int]):
    """
    Compare source (Sheets) row counts to Supabase row counts.
    Prints a table and returns True if all counts match.
    """
    print("\nRow count validation (source → Supabase):")
    tables = [
        ("evidence",  "restaurants",          "evidence.restaurants"),
        ("evidence",  "menu_sources",          "evidence.menu_sources"),
        ("evidence",  "dishes",                "evidence.dishes"),
        ("evidence",  "ingredients",           "evidence.ingredients"),
        ("knowledge", "transparency_scores",   "knowledge.transparency_scores"),
        ("evidence",  "allergen_disclosures",  "evidence.allergen_disclosures"),
    ]
    all_match = True
    for schema, table, label in tables:
        try:
            result = (
                sb.schema(schema).table(table)
                .select("*", count="exact")
                .limit(0)
                .execute()
            )
            sb_count = result.count or 0
        except Exception as e:
            print(f"  {label}: ERROR — {e}")
            all_match = False
            continue

        src_count = source_counts.get(label, 0)
        if sb_count == src_count:
            print(f"  {label}: {src_count} → {sb_count}  ✓")
        else:
            print(f"  {label}: {src_count} → {sb_count}  ✗ MISMATCH")
            all_match = False

    if all_match:
        print("\n  All counts match. ✓")
    else:
        print("\n  WARNING: Count mismatches detected. Review migration logs above.")
        print("  Common causes: FK lookup failures, placeholder row skips, existing data.")
    return all_match


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    mode = "APPLY" if APPLY else "DRY RUN"
    force_note = " + FORCE (truncate non-idempotent tables)" if FORCE and APPLY else ""
    print(f"\nmigrate_sheets_to_supabase.py  [{mode}{force_note}]")
    print(f"  Source: Google Sheets {SPREADSHEET_ID}")
    print(f"  Target: {SUPABASE_URL or '(SUPABASE_URL not set)'}")

    if APPLY:
        print()
        print("  ⚠  SERVICE ROLE KEY IN USE — bypasses all RLS policies.")
        print("     Never run this script in a web server or expose the key to clients.")

    print()

    if APPLY and not SUPABASE_URL:
        print("ERROR: SUPABASE_URL not set in .env")
        sys.exit(1)
    if APPLY and not SUPABASE_KEY:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set in .env")
        sys.exit(1)

    # ── Connect to Google Sheets ───────────────────────────────────────────────
    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(str(KEY_FILE), scopes=SCOPES)
    gs     = gspread.authorize(creds)
    ss     = gs.open_by_key(SPREADSHEET_ID)
    print("  Connected.\n")

    # ── Connect to Supabase ────────────────────────────────────────────────────
    sb: Optional[Client] = None
    existing_counts: dict[str, int] = {}
    if APPLY:
        print("Connecting to Supabase...")
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("  Connected.\n")
        existing_counts = _preflight_check(sb)

    # ── Load all tabs ──────────────────────────────────────────────────────────
    print("Loading Google Sheets tabs...")
    dld_rows        = load_tab(ss, "Goldpan Dish Level Data")
    ingredient_rows = load_tab(ss, "Ingredient Details")
    scoring_rows    = load_tab(ss, "Transparency Scoring")
    registry_rows   = load_tab(ss, "Menu Source Registry")
    allergen_rows   = load_tab_any(ss, "Allergen Disclosures", "Allergen_Disclosures")

    print(f"  Goldpan Dish Level Data : {len(dld_rows)} rows")
    print(f"  Ingredient Details      : {len(ingredient_rows)} rows")
    print(f"  Transparency Scoring    : {len(scoring_rows)} rows")
    print(f"  Menu Source Registry    : {len(registry_rows)} rows")
    print(f"  Allergen Disclosures    : {len(allergen_rows)} rows")
    print()

    # ── Build evidence.restaurants ─────────────────────────────────────────────
    print("Building evidence.restaurants...")
    registry_by_id = {r.get("Restaurant_ID", "").strip(): r for r in registry_rows}

    seen_restaurant_ids: set[str] = set()
    restaurant_rows: list[dict] = []

    for row in dld_rows:
        rid = s(row.get("Restaurant_ID"))
        if not rid or rid in seen_restaurant_ids:
            continue
        seen_restaurant_ids.add(rid)

        reg = registry_by_id.get(rid, {})
        recanvass_status = s(reg.get("Recanvass_Status")) or "needs_review"
        # Infer lifecycle_status from freshness state for migration:
        # current/due_soon → published; everything else → evidence_acquisition
        lifecycle_status = (
            "published"
            if recanvass_status in ("current", "due_soon")
            else "evidence_acquisition"
        )

        restaurant_rows.append({
            "external_id":           rid,
            "name":                  s(row.get("Restaurant") or row.get("Restaurant_Name")) or rid,
            "location":              s(row.get("Location")),
            "official_website":      s(reg.get("Official_Website")),
            "menu_url":              s(reg.get("Official_Menu_URL")),
            "online_ordering_url":   s(reg.get("Online_Ordering_URL")),
            "hours":                 s(row.get("Hours")),
            "lifecycle_status":      lifecycle_status,
            "primary_source_url":    s(reg.get("Preferred_Data_Source") or reg.get("Official_Menu_URL")),
            "last_canvassed":        d(reg.get("Last_Canvassed")),
            "recanvass_status":      recanvass_status,
            "recanvass_tier":        int(n(reg.get("Recanvass_Tier")) or 2),
            "last_source_check":     d(reg.get("Last_Source_Check")),
            "source_check_status":   s(reg.get("Source_Check_Status")) or "unknown",
            "menu_changed":          s(reg.get("Menu_Changed")),
            "change_type":           s(reg.get("Change_Type")),
            "status_computed_date":  d(reg.get("Status_Computed_Date")),
            "forced_recanvass_flag": s(reg.get("Forced_Recanvass_Flag")),
            "recanvass_notes":       s(reg.get("Recanvass_Notes")),
            "notes":                 s(reg.get("Notes")),
        })

    # Add any restaurants in registry that aren't in DLD (prospects, qualified, etc.)
    for rid, reg in registry_by_id.items():
        if rid and rid not in seen_restaurant_ids:
            seen_restaurant_ids.add(rid)
            restaurant_rows.append({
                "external_id":           rid,
                "name":                  s(reg.get("Restaurant_Name")) or rid,
                "official_website":      s(reg.get("Official_Website")),
                "menu_url":              s(reg.get("Official_Menu_URL")),
                "online_ordering_url":   s(reg.get("Online_Ordering_URL")),
                "lifecycle_status":      "qualified",
                "primary_source_url":    s(reg.get("Preferred_Data_Source")),
                "last_canvassed":        d(reg.get("Last_Canvassed")),
                "recanvass_status":      s(reg.get("Recanvass_Status")) or "needs_review",
                "recanvass_tier":        int(n(reg.get("Recanvass_Tier")) or 2),
                "last_source_check":     d(reg.get("Last_Source_Check")),
                "source_check_status":   s(reg.get("Source_Check_Status")) or "unknown",
                "notes":                 s(reg.get("Notes")),
            })

    print(f"  {len(restaurant_rows)} unique restaurants")

    # ── Build evidence.menu_sources ────────────────────────────────────────────
    print("Building evidence.menu_sources...")
    menu_source_rows: list[dict] = []
    for reg in registry_rows:
        rid = s(reg.get("Restaurant_ID"))
        if not rid:
            continue
        menu_source_rows.append({
            "restaurant_external_id":  rid,     # real column (denormalized)
            "official_website":        s(reg.get("Official_Website")),
            "official_menu_url":       s(reg.get("Official_Menu_URL")),
            "online_ordering_url":     s(reg.get("Online_Ordering_URL")),
            "pdf_menu_url":            s(reg.get("PDF_Menu_URL")),
            "allergen_nutrition_url":  s(reg.get("Allergen_Nutrition_URL")),
            "menu_format":             s(reg.get("Menu_Format")),
            "source_confidence":       s(reg.get("Source_Confidence")),
            "preferred_data_source":   s(reg.get("Preferred_Data_Source")),
            "menu_status":             s(reg.get("Menu_Status")),
            "canvass_priority":        s(reg.get("Canvass_Priority")),
            "last_verified_date":      d(reg.get("Last_Verified_Date")),
            "last_canvassed":          d(reg.get("Last_Canvassed")),
            "last_source_check":       d(reg.get("Last_Source_Check")),
            "source_check_status":     s(reg.get("Source_Check_Status")) or "unknown",
            "menu_changed":            s(reg.get("Menu_Changed")),
            "change_type":             s(reg.get("Change_Type")),
            "recanvass_tier":          int(n(reg.get("Recanvass_Tier")) or 2),
            "recanvass_status":        s(reg.get("Recanvass_Status")) or "needs_review",
            "status_computed_date":    d(reg.get("Status_Computed_Date")),
            "forced_recanvass_flag":   s(reg.get("Forced_Recanvass_Flag")),
            "recanvass_notes":         s(reg.get("Recanvass_Notes")),
            "notes":                   s(reg.get("Notes")),
        })
    print(f"  {len(menu_source_rows)} menu source rows")

    # ── Build evidence.dishes ──────────────────────────────────────────────────
    print("Building evidence.dishes...")
    dish_rows: list[dict] = []
    for row in dld_rows:
        did = s(row.get("Dish_ID"))
        rid = s(row.get("Restaurant_ID"))
        if not did or not rid:
            continue
        dish_rows.append({
            "external_id":             did,
            "restaurant_external_id":  rid,     # real column (denormalized)
            "dish_name":               s(row.get("Dish_Name")) or did,
            "category":                s(row.get("Category")),
            "price":                   s(row.get("Menu_Price")),
            "dietary_tags":            s(row.get("Dietary_Tags")),
            "dietary_options":         s(row.get("Dietary_Options")),
            "tag_source":              s(row.get("Tag_Source")),
            "hours":                   s(row.get("Hours")),
            "menu_link":               s(row.get("Menu_Link")),
            "restaurant_address":      s(row.get("Restaurant_Address")),
            "restaurant_website":      s(row.get("Restaurant_Website")),
            "allergen_summary":        s(row.get("Allergen_summary")),   # lowercase s
            "calorie_value":           s(row.get("Calorie_Value")),
            "calorie_source_text":     s(row.get("Calorie_Source_Text")),
            "verification_status":     s(row.get("Verification_Status") or row.get("Recanvass_Status")),
            "status":                  s(row.get("Status")) or "Active",
            "version":                 s(row.get("Version")),
            "last_updated":            s(row.get("Last_Updated")),
            "is_active":               (s(row.get("Status")) or "Active") == "Active",
        })
    print(f"  {len(dish_rows)} dish rows")

    # ── Build evidence.ingredients ─────────────────────────────────────────────
    print("Building evidence.ingredients...")
    ingr_rows: list[dict] = []
    skip_names = {
        "building transparency",
        "ingredient detail pending confirmation",
        "none", "n/a", "tbd",
    }
    for row in ingredient_rows:
        did   = s(row.get("Dish_ID"))
        rid   = s(row.get("Restaurant_ID"))
        iname = s(row.get("Ingredient"))
        if not did or not rid or not iname:
            continue
        if iname.lower() in skip_names:
            continue
        ingr_row = {
            "dish_external_id":         did,    # real column (denormalized)
            "restaurant_external_id":   rid,    # real column (denormalized)
            "ingredient_name":          iname,
            "cut_type":                 s(row.get("Cut_Type")),
            "preparation":              s(row.get("Preparation")),
            "ingredient_type":          s(row.get("Ingredient_Type")),
            "component_role":           s(row.get("Component_Role")),
            "allergen_flags":           s(row.get("Allergen_Flags")),
            "ingredient_source":        s(row.get("Ingredient_Source")),
            "status":                   s(row.get("Status")) or "Active",
            "version":                  s(row.get("Version")),
            "is_active":                (s(row.get("Status")) or "Active") == "Active",
        }
        # source_row_hash: stable fingerprint for idempotent re-migration.
        # NULL for rows added via API — NULLs don't conflict in PostgreSQL UNIQUE.
        ingr_row["source_row_hash"] = _ingredient_hash(ingr_row)
        ingr_rows.append(ingr_row)
    print(f"  {len(ingr_rows)} ingredient rows (after placeholder skip)")

    # ── Build knowledge.transparency_scores ───────────────────────────────────
    print("Building knowledge.transparency_scores...")
    score_rows: list[dict] = []
    for row in scoring_rows:
        did = s(row.get("Dish_ID"))
        rid = s(row.get("Restaurant_ID"))
        if not did or not rid:
            continue
        score_rows.append({
            "dish_external_id":           did,  # real column (denormalized)
            "restaurant_external_id":     rid,  # real column (denormalized)
            # total_score is GENERATED ALWAYS AS — do NOT include it
            "core_clarity":               n(row.get("Core_Clarity")) or 0,
            "sauce_seasoning_disclosure": n(row.get("Sauce_Seasoning_Disclosure")
                                            or row.get("Sauce_Disclosure")) or 0,
            "allergen_transparency":      n(row.get("Allergen_Transparency")) or 0,
            "prep_clarity":               n(row.get("Prep_Clarity")) or 0,
            "transparency_level":         normalize_transparency_level(s(row.get("Transparency_Level"))),
            "scoring_notes":              s(row.get("Notes")),
            "is_current":                 True,
        })
    print(f"  {len(score_rows)} transparency score rows")

    # ── Build evidence.allergen_disclosures ───────────────────────────────────
    print("Building evidence.allergen_disclosures...")
    allergen_disc_rows: list[dict] = []
    for row in allergen_rows:
        rid      = s(row.get("Restaurant_ID"))
        allergen = s(row.get("Allergen"))
        status   = s(row.get("Disclosure_Status"))
        scope    = s(row.get("Scope"))
        src_type = s(row.get("Source_Type"))
        if not rid or not allergen or not status or not scope or not src_type:
            continue
        allergen_disc_rows.append({
            "restaurant_external_id":  rid,             # real column (denormalized)
            "dish_external_id":        s(row.get("Dish_ID")),  # real column; None if restaurant-scoped
            "allergen":                allergen.lower(),
            "disclosure_status":       status,
            "scope":                   scope,
            "source_type":             src_type,
            "source_reference":        s(row.get("Source_Reference")),
            "source_date":             d(row.get("Source_Date")),
            "confidence":              s(row.get("Confidence")),
            "notes":                   s(row.get("Notes")),
        })
    print(f"  {len(allergen_disc_rows)} allergen disclosure rows")

    # ── Source counts (for post-migration validation) ──────────────────────────
    source_counts = {
        "evidence.restaurants":         len(restaurant_rows),
        "evidence.menu_sources":        len(menu_source_rows),
        "evidence.dishes":              len(dish_rows),
        "evidence.ingredients":         len(ingr_rows),
        "knowledge.transparency_scores": len(score_rows),
        "evidence.allergen_disclosures": len(allergen_disc_rows),
    }

    # ── Summary ────────────────────────────────────────────────────────────────
    print()
    print("Summary:")
    for label, count in source_counts.items():
        print(f"  {label:<40}: {count}")
    total = sum(source_counts.values())
    print(f"  {'TOTAL':<40}: {total}")

    if not APPLY:
        print("\nDRY RUN complete — no writes. Add --apply to write to Supabase.")
        return

    # ── Write to Supabase ──────────────────────────────────────────────────────
    print("\nWriting to Supabase...")

    # Step 1: Insert restaurants (no FK dependencies)
    print("Step 1: evidence.restaurants")
    _write_restaurants(sb, restaurant_rows)

    # Step 2: Fetch restaurant UUID map (external_id → restaurant_id UUID)
    print("\nStep 2: Fetching restaurant UUID map...")
    r_map = _fetch_uuid_map(sb, "evidence", "restaurants", "external_id")
    print(f"  {len(r_map)} restaurant UUIDs fetched")
    if len(r_map) < len(restaurant_rows):
        print(f"  WARNING: {len(restaurant_rows) - len(r_map)} restaurants not found "
              f"after insert. FK injections for those restaurants will be skipped.")

    # Step 3: Insert menu_sources (upsert on restaurant_id — constraint in migration 008)
    print("\nStep 3: evidence.menu_sources")
    menu_source_rows_fk = _inject_fk(menu_source_rows, "restaurant_external_id", r_map, "restaurant_id")
    menu_source_rows_valid = [r for r in menu_source_rows_fk if r.get("restaurant_id")]
    skipped = len(menu_source_rows_fk) - len(menu_source_rows_valid)
    if skipped:
        print(f"  WARNING: {skipped} menu_source rows skipped (restaurant FK not found)")
    _write_rows_batched(sb, "evidence", "menu_sources", menu_source_rows_valid,
                        "evidence.menu_sources", conflict_col="restaurant_id")

    # Step 4: Insert dishes (upsert on external_id)
    print("\nStep 4: evidence.dishes")
    dish_rows_fk = _inject_fk(dish_rows, "restaurant_external_id", r_map, "restaurant_id")
    dish_rows_valid = [r for r in dish_rows_fk if r.get("restaurant_id")]
    skipped = len(dish_rows_fk) - len(dish_rows_valid)
    if skipped:
        print(f"  WARNING: {skipped} dish rows skipped (restaurant FK not found)")
    _write_rows_batched(sb, "evidence", "dishes", dish_rows_valid,
                        "evidence.dishes", conflict_col="external_id")

    # Step 5: Fetch dish UUID map (external_id → dish_id UUID)
    print("\nStep 5: Fetching dish UUID map...")
    d_map = _fetch_uuid_map(sb, "evidence", "dishes", "external_id")
    print(f"  {len(d_map)} dish UUIDs fetched")

    # Step 6: Insert ingredients (upsert on source_row_hash — UNIQUE nullable column, migration 008)
    print("\nStep 6: evidence.ingredients")
    ingr_fk = _inject_fk(
        _inject_fk(ingr_rows, "restaurant_external_id", r_map, "restaurant_id"),
        "dish_external_id", d_map, "dish_id"
    )
    ingr_valid = [r for r in ingr_fk if r.get("dish_id") and r.get("restaurant_id")]
    skipped = len(ingr_fk) - len(ingr_valid)
    if skipped:
        print(f"  WARNING: {skipped} ingredient rows skipped (dish or restaurant FK not found)")
    # Conflict on source_row_hash (UNIQUE constraint added in migration 008).
    # NULLs in source_row_hash don't conflict — API-entered rows are unrestricted.
    _write_rows_batched(sb, "evidence", "ingredients", ingr_valid,
                        "evidence.ingredients", conflict_col="source_row_hash")

    # Step 7: transparency_scores — pre-flight gate + FORCE truncate
    print("\nStep 7: knowledge.transparency_scores")
    existing_ts = existing_counts.get("knowledge.transparency_scores", 0)
    if existing_ts > 0 and not FORCE:
        print(f"  SKIPPED: {existing_ts} rows already present. Re-run with --force to truncate and re-seed.")
    else:
        if FORCE and existing_ts > 0:
            _truncate_table(sb, "knowledge", "transparency_scores")
        score_fk = _inject_fk(
            _inject_fk(score_rows, "restaurant_external_id", r_map, "restaurant_id"),
            "dish_external_id", d_map, "dish_id"
        )
        score_valid = [r for r in score_fk if r.get("dish_id") and r.get("restaurant_id")]
        skipped = len(score_fk) - len(score_valid)
        if skipped:
            print(f"  WARNING: {skipped} score rows skipped (dish or restaurant FK not found)")
        _write_rows_batched(sb, "knowledge", "transparency_scores", score_valid,
                            "knowledge.transparency_scores", conflict_col=None)

    # Step 8: allergen_disclosures — pre-flight gate + FORCE truncate
    print("\nStep 8: evidence.allergen_disclosures")
    existing_ad = existing_counts.get("evidence.allergen_disclosures", 0)
    if existing_ad > 0 and not FORCE:
        print(f"  SKIPPED: {existing_ad} rows already present. Re-run with --force to truncate and re-seed.")
    else:
        if FORCE and existing_ad > 0:
            _truncate_table(sb, "evidence", "allergen_disclosures")
        allergen_fk = []
        for row in allergen_disc_rows:
            new_row = dict(row)
            new_row["restaurant_id"] = r_map.get(row.get("restaurant_external_id"))
            did_ext = row.get("dish_external_id")
            new_row["dish_id"] = d_map.get(did_ext) if did_ext else None
            if new_row["restaurant_id"]:
                allergen_fk.append(new_row)
        skipped = len(allergen_disc_rows) - len(allergen_fk)
        if skipped:
            print(f"  WARNING: {skipped} allergen rows skipped (restaurant FK not found)")
        _write_rows_batched(sb, "evidence", "allergen_disclosures", allergen_fk,
                            "evidence.allergen_disclosures", conflict_col=None)

    # ── Post-migration row count validation ────────────────────────────────────
    _validate_counts(sb, source_counts)

    print("\n✓ Migration complete.")
    print("\nNext steps:")
    print("  1. Inspect any count mismatches above")
    print("  2. Run validate_database.py against Supabase to verify data integrity")
    print("  3. Run pipeline.py --dry-run against Supabase to confirm identical output")
    print("  4. Compare dishes.json from Sheets run vs Supabase run")
    print("  5. If clean for 30 days, set feature flag: supabase_pipeline_mode = true")


if __name__ == "__main__":
    main()
