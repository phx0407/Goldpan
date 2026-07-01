"""
validate_database.py — Goldpan Full Database Validation Report

Validates all Goldpan database tables against DATA_RULES.md standards.
Writes a full report to validation_report.txt in the current directory.
Terminal output shows only errors, warnings, and final summary.

Overall result: PASS (exit 0) or FAIL (exit 1).
The pipeline must not proceed until this report is clean.

Usage:
  python3 validate_database.py                      # all tables
  python3 validate_database.py --table ingredient   # Ingredient Details only
  python3 validate_database.py --table dish         # Goldpan Dish Level Data only
  python3 validate_database.py --table scoring      # Transparency Scoring only
  python3 validate_database.py --table registry     # Menu Source Registry only
  python3 validate_database.py --table allergen     # Allergen Disclosures only
  python3 validate_database.py --verbose            # full detail in terminal too
"""

import re
import sys
import datetime
import gspread
from google.oauth2.service_account import Credentials
from schema import (
    ALLERGEN_CANONICAL_SLUGS,
    ALLERGEN_SLUG_ALIASES,
    ALLERGEN_DISCLOSURE_STATUSES,
    ALLERGEN_DISCLOSURE_SCOPES,
    ALLERGEN_FREE_FROM_ELIGIBLE_SOURCES,
    MACRO_ELIGIBLE_SOURCES,
)

# ── Config ─────────────────────────────────────────────────────────────────────

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TODAY          = datetime.date.today().strftime("%Y-%m-%d")

# Freshness snapshot thresholds (days since Status_Computed_Date)
SNAPSHOT_WARN_DAYS  = 7    # warn if snapshot not refreshed in this many days
SNAPSHOT_ERROR_DAYS = 30   # error if snapshot is critically stale

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ── Canonical schemas (from DATA_RULES.md) ─────────────────────────────────────

SCHEMA = {
    "Ingredient Details": {
        "required": ["Restaurant_ID", "Restaurant_Name", "Location", "Dish_ID", "Dish_Name", "Ingredient"],
        "canonical": [
            "Restaurant_ID", "Restaurant_Name", "Location", "Dish_ID", "Dish_Name",
            "Ingredient", "Cut_Type", "Preparation", "Ingredient_Type", "Status",
            "Version", "Ingredient_Source", "Allergen_Flags", "Component_Role",
        ],
    },
    "Goldpan Dish Level Data": {
        "required": ["Restaurant_ID", "Restaurant", "Location", "Dish_ID", "Dish_Name", "Last_Updated", "Status"],
        "canonical": [
            "Restaurant_ID", "Restaurant", "Location", "Dish_ID", "Dish_Name",
            "Dietary_Tags", "Dietary_Options", "Tag_Source", "Verification_Status", "Hours",
            "Menu_Link", "Menu_Price", "Restaurant_Address", "Allergen_summary",
            "Last_Updated", "Restaurant_Website", "Status", "Version", "Category",
        ],
    },
    "Transparency Scoring": {
        "required": ["Restaurant_ID", "Restaurant_Name", "Dish_ID", "Dish_Name", "Transparency_Level"],
        "canonical": [
            "Restaurant_ID", "Restaurant_Name", "Dish_ID", "Dish_Name",
            "Core_Clarity", "Sauce_Seasoning_Disclosure", "Allergen_Transparency",
            "Prep_Clarity", "Total_Score", "Transparency_Level", "Notes",
        ],
    },
    "Allergen Disclosures": {
        # GP-RULE-014 (Allergen Evidence Rule v1.0)
        # Dish_ID is required when Scope = dish; blank when Scope = restaurant.
        # Cross-validation is enforced in validate_allergen_disclosures().
        "required": [
            "Restaurant_ID", "Restaurant_Name", "Allergen",
            "Disclosure_Status", "Source_Type", "Source_Reference", "Source_Date", "Scope",
        ],
        "canonical": [
            "Restaurant_ID", "Restaurant_Name", "Dish_ID", "Dish_Name",
            "Allergen", "Disclosure_Status", "Source_Type", "Source_Reference",
            "Source_Date", "Scope", "Notes",
        ],
    },
    "Menu Source Registry": {
        "required": [
            "Restaurant_Name", "Official_Website", "Official_Menu_URL",
            "Source_Confidence", "Preferred_Data_Source", "Menu_Status", "Canvass_Priority",
        ],
        "canonical": [
            "Restaurant_ID", "Restaurant_Name", "Official_Website", "Official_Menu_URL",
            "Online_Ordering_URL", "PDF_Menu_URL", "Allergen_Nutrition_URL", "Menu_Format",
            "Last_Verified_Date", "Last_Menu_Change_Detected", "Source_Confidence",
            "Preferred_Data_Source", "Menu_Status", "Canvass_Priority", "Notes",
            # Freshness columns (added by add_freshness_columns.py)
            "Recanvass_Tier", "Last_Canvassed", "Last_Source_Check", "Source_Check_Status",
            "Menu_Changed", "Change_Type", "Recanvass_Status", "Status_Computed_Date",
            "Forced_Recanvass_Flag", "Recanvass_Notes",
        ],
    },
}

# ── Valid enum values ──────────────────────────────────────────────────────────

VALID = {
    "Status":              {"Active", "Inactive"},
    "Source_Confidence":   {"Official", "Third-Party", "Unverified", "Inferred"},
    "Menu_Status":         {"Active", "Needs Review"},
    "Canvass_Priority":    {"High", "Medium", "Low"},
    "Transparency_Level":  {
        "Building", "Moderate", "High",
        "Building Transparency", "Moderate Transparency", "High Transparency",
    },
    "Ingredient_Type":     {"standard", "sauce", "dressing", "seasoning", "base", "protein", "topping",
                            "unknown", "Unknown", "None", "N/A"},
    # Freshness columns
    "Recanvass_Status":      {"current", "due_soon", "overdue", "needs_review", ""},
    "Source_Check_Status":   {"ok", "changed", "unreachable", "overdue", "unknown", ""},
    "Menu_Changed":          {"yes", "no", "unknown", ""},
    "Forced_Recanvass_Flag": {"yes", ""},
    # Dietary tag provenance (GP-RULE-013)
    "Tag_Source":            {"restaurant_disclosed", "goldpan_inferred", ""},
}

DISH_ID_RE = re.compile(r"^D\d+$")
REST_ID_RE = re.compile(r"^R\d+$")


def normalize_restaurant_name(name):
    """Mirror fetch_dishes.py normalization so registry lookups match correctly."""
    if name == "East West":
        return "EastWest"
    if name == "Brick & Tin Mountain Brook":
        return "Brick & Tin"
    return name

REPORT_FILE = "validation_report.txt"
VERBOSE     = "--verbose" in sys.argv

# ── Reporting helpers ──────────────────────────────────────────────────────────

errors   = []
warnings = []
_report_lines = []   # buffer for file output


def _emit(text, terminal=False):
    """Write to report file always; write to terminal only if terminal=True or VERBOSE."""
    _report_lines.append(text)
    if terminal or VERBOSE:
        print(text)


def _flush_report():
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(_report_lines) + "\n")


def error(table, row, record_id, problem, fix=""):
    errors.append({
        "table": table, "row": row, "id": record_id,
        "problem": problem, "fix": fix,
    })


def warn(table, row, record_id, problem):
    warnings.append({
        "table": table, "row": row, "id": record_id, "problem": problem,
    })


def section(title):
    _emit(f"\n{'─'*65}")
    _emit(f"  {title}")
    _emit(f"{'─'*65}")


def hdr(text):
    _emit(f"\n  {text}")


def ok(text):
    _emit(f"    ✓ {text}")


def issue(text):
    _emit(f"    ✗ {text}")


def note(text):
    _emit(f"    ⚠ {text}")


# ── Sheet helpers ──────────────────────────────────────────────────────────────

def get_col(headers, name):
    try:
        return headers.index(name)
    except ValueError:
        return None


def cell(row, idx):
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip()


def load_dish_ids(ss):
    """Lightweight load of Dish_IDs from Goldpan Dish Level Data — no validation run.
    Used by --table ingredient / --table scoring to satisfy cross-table referential checks
    without running full GDL validation."""
    headers, rows = read_tab(ss, "Goldpan Dish Level Data")
    if not headers or not rows:
        return set()
    did_col = get_col(headers, "Dish_ID")
    if did_col is None:
        return set()
    return {row[did_col].strip() for row in rows if did_col < len(row) and row[did_col].strip()}


def read_tab(ss, tab_name):
    """Read a worksheet and return (headers, data_rows). Returns ([], []) if tab missing.
    Headers are stripped of leading/trailing whitespace on read so trailing-space
    column names never cause false schema mismatches."""
    try:
        ws = ss.worksheet(tab_name)
        all_values = ws.get_all_values()
        if not all_values:
            return [], []
        headers = [h.strip() for h in all_values[0]]   # strip ALL headers defensively
        return headers, all_values[1:]
    except gspread.exceptions.WorksheetNotFound:
        return None, None   # None signals tab is missing


# ── Validation functions ───────────────────────────────────────────────────────

def validate_schema(tab_name, headers):
    """Check headers against canonical schema. Returns missing and unexpected columns."""
    schema = SCHEMA.get(tab_name, {})
    canonical = schema.get("canonical", [])
    required  = schema.get("required", [])

    missing_required  = [c for c in required  if c not in headers]
    missing_canonical = [c for c in canonical if c not in headers]
    unexpected        = [h for h in headers   if h and h not in canonical]

    hdr("Header / Schema Validation")
    if not missing_required and not missing_canonical:
        ok(f"All canonical headers present ({len(headers)} columns)")
    else:
        if missing_required:
            issue(f"Missing REQUIRED headers: {missing_required}")
            error(tab_name, 1, "SCHEMA", f"Missing required headers: {missing_required}",
                  "Add the missing columns to the sheet.")
        if missing_canonical:
            note(f"Missing optional canonical headers: {missing_canonical}")
            warn(tab_name, 1, "SCHEMA", f"Missing optional columns: {missing_canonical}")

    if unexpected:
        note(f"Unexpected columns (not in canonical schema): {unexpected}")
        warn(tab_name, 1, "SCHEMA", f"Unexpected columns found: {unexpected}")

    return missing_required


def validate_required_fields(tab_name, headers, rows, key_col_name):
    """Check every row for missing required fields."""
    schema   = SCHEMA.get(tab_name, {})
    required = schema.get("required", [])
    key_col  = get_col(headers, key_col_name)

    field_missing = {f: [] for f in required}  # field -> [(row_num, record_id)]

    for i, row in enumerate(rows, start=2):
        record_id = cell(row, key_col) if key_col is not None else f"row {i}"
        for field in required:
            col_idx = get_col(headers, field)
            val = cell(row, col_idx)
            if not val:
                field_missing[field].append((i, record_id))

    hdr("Required Field Validation")
    any_missing = False
    for field, hits in field_missing.items():
        if hits:
            any_missing = True
            ids = ", ".join(f"row {r}:{rid}" for r, rid in hits[:10])
            if len(hits) > 10:
                ids += f" ... (+{len(hits)-10} more)"
            issue(f"{field}: {len(hits)} row(s) missing — {ids}")
            error(tab_name, hits[0][0], hits[0][1],
                  f"Missing required field '{field}' in {len(hits)} row(s)",
                  f"Populate '{field}' for all affected rows.")
    if not any_missing:
        ok(f"All required fields populated across {len(rows)} rows")


def validate_duplicates(tab_name, headers, rows, natural_keys):
    """Check for duplicate records by natural key(s)."""
    col_idxs  = [(k, get_col(headers, k)) for k in natural_keys]
    seen      = {}  # key_tuple -> first row number
    dupes     = []

    for i, row in enumerate(rows, start=2):
        key = tuple(cell(row, idx) for _, idx in col_idxs if idx is not None)
        if not any(key):
            continue
        if key in seen:
            dupes.append((i, key, seen[key]))
        else:
            seen[key] = i

    hdr(f"Duplicate Validation  (key: {' + '.join(natural_keys)})")
    if dupes:
        for row_num, key, first_row in dupes[:20]:
            key_str = " | ".join(f"{n}={v}" for n, (k, _) in zip(natural_keys, col_idxs) for v in [key[natural_keys.index(n)]])
            issue(f"Row {row_num} duplicates row {first_row}: {key_str}")
            error(tab_name, row_num, str(key[0]),
                  f"Duplicate record — same key as row {first_row}: {key}",
                  "Remove or merge the duplicate row.")
        if len(dupes) > 20:
            note(f"  ... and {len(dupes)-20} more duplicates not shown")
    else:
        ok(f"No duplicate {' + '.join(natural_keys)} records")

    return seen  # return key->row_num map for use by other validators


def validate_id_format(tab_name, headers, rows, dish_id_col=None, rest_id_col=None):
    """Check that Dish_IDs and Restaurant_IDs match expected patterns."""
    hdr("ID Format Validation")
    did_idx = get_col(headers, dish_id_col) if dish_id_col else None
    rid_idx = get_col(headers, rest_id_col) if rest_id_col else None

    bad_dids = []
    bad_rids = []

    for i, row in enumerate(rows, start=2):
        if did_idx is not None:
            did = cell(row, did_idx)
            if did and not DISH_ID_RE.match(did):
                bad_dids.append((i, did))
        if rid_idx is not None:
            rid = cell(row, rid_idx)
            if rid and not REST_ID_RE.match(rid):
                bad_rids.append((i, rid))

    if bad_dids:
        for row_num, did in bad_dids[:10]:
            issue(f"Invalid Dish_ID format at row {row_num}: '{did}' (expected D + integer)")
            error(tab_name, row_num, did, f"Invalid Dish_ID format: '{did}'",
                  "Dish_IDs must be D followed by an integer (e.g. D001, D100).")
    else:
        if did_idx is not None:
            ok("All Dish_IDs match expected format (D + integer)")

    if bad_rids:
        for row_num, rid in bad_rids[:10]:
            issue(f"Invalid Restaurant_ID format at row {row_num}: '{rid}' (expected R + integer)")
            error(tab_name, row_num, rid, f"Invalid Restaurant_ID format: '{rid}'",
                  "Restaurant_IDs must be R followed by zero-padded integer (e.g. R001).")
    else:
        if rid_idx is not None:
            ok("All Restaurant_IDs match expected format (R + integer)")


def validate_enum(tab_name, headers, rows, enum_fields, key_col_name):
    """Check fields that must contain specific values."""
    key_col = get_col(headers, key_col_name)
    hdr("Enum / Status Value Validation")
    any_invalid = False

    for field, valid_set in enum_fields.items():
        col_idx = get_col(headers, field)
        if col_idx is None:
            continue
        invalid_rows = []
        for i, row in enumerate(rows, start=2):
            val = cell(row, col_idx)
            if val and val not in valid_set:
                record_id = cell(row, key_col) if key_col is not None else f"row {i}"
                invalid_rows.append((i, record_id, val))

        if invalid_rows:
            any_invalid = True
            for row_num, record_id, val in invalid_rows[:10]:
                issue(f"'{field}' = '{val}' at row {row_num} ({record_id}) — valid values: {sorted(valid_set)}")
                warn(tab_name, row_num, record_id,
                     f"Invalid {field} value: '{val}'. Expected one of: {sorted(valid_set)}")
        else:
            ok(f"{field}: all values valid")

    if not any_invalid:
        ok("All enum fields contain valid values")


# ── Table validators ───────────────────────────────────────────────────────────

def validate_ingredient_details(ss, dish_ids_in_dl):
    """Full validation of Ingredient Details tab."""
    tab = "Ingredient Details"
    section(f"TABLE: {tab}")

    headers, rows = read_tab(ss, tab)
    if headers is None:
        error(tab, 0, "TAB", "Tab not found in spreadsheet.", "Create the Ingredient Details tab.")
        issue("Tab not found — skipping all Ingredient Details validation.")
        return

    if not rows:
        warn(tab, 0, "TAB", "Tab exists but has no data rows.")
        note("Tab is empty.")
        return

    # ── Record summary ──────────────────────────────────────────────────────────
    hdr("Record Summary")
    dish_id_col = get_col(headers, "Dish_ID")
    rest_id_col = get_col(headers, "Restaurant_ID")

    dish_ids_seen = set()
    rest_ids_seen = set()
    for row in rows:
        did = cell(row, dish_id_col)
        rid = cell(row, rest_id_col)
        if did:
            dish_ids_seen.add(did)
        if rid:
            rest_ids_seen.add(rid)

    ok(f"Total rows         : {len(rows)}")
    ok(f"Unique dishes      : {len(dish_ids_seen)}")
    ok(f"Unique restaurants : {len(rest_ids_seen)}")

    # ── Schema ──────────────────────────────────────────────────────────────────
    validate_schema(tab, headers)

    # ── Required fields ─────────────────────────────────────────────────────────
    validate_required_fields(tab, headers, rows, "Dish_ID")

    # ── Duplicates: Dish_ID + Ingredient ────────────────────────────────────────
    validate_duplicates(tab, headers, rows, ["Dish_ID", "Ingredient"])

    # ── ID format ───────────────────────────────────────────────────────────────
    validate_id_format(tab, headers, rows, dish_id_col="Dish_ID", rest_id_col="Restaurant_ID")

    # ── Enum validation ─────────────────────────────────────────────────────────
    validate_enum(tab, headers, rows, {"Status": VALID["Status"]}, "Dish_ID")

    # ── Referential integrity: Dish_ID must exist in Dish Level Data ────────────
    hdr("Referential Integrity")
    orphaned = []
    for i, row in enumerate(rows, start=2):
        did = cell(row, dish_id_col)
        if did and did not in dish_ids_in_dl:
            ing = cell(row, get_col(headers, "Ingredient"))
            orphaned.append((i, did, ing))

    if orphaned:
        for row_num, did, ing in orphaned[:20]:
            issue(f"Orphaned row {row_num}: Dish_ID {did} ('{ing}') not in Dish Level Data")
            error(tab, row_num, did,
                  f"Orphaned ingredient row — Dish_ID '{did}' not in Goldpan Dish Level Data",
                  "Add the dish to Dish Level Data first, or remove this ingredient row.")
        if len(orphaned) > 20:
            note(f"  ... and {len(orphaned)-20} more orphaned rows")
    else:
        ok(f"All {len(rows)} ingredient rows reference valid Dish_IDs")

    # ── Sparse row check ─────────────────────────────────────────────────────────
    hdr("Sparse Row Detection")
    required_cols = SCHEMA[tab]["required"]
    sparse = []
    for i, row in enumerate(rows, start=2):
        missing = [f for f in required_cols
                   if not cell(row, get_col(headers, f))]
        if missing:
            did = cell(row, dish_id_col) or "(no Dish_ID)"
            sparse.append((i, did, missing))

    if sparse:
        for row_num, did, missing in sparse[:20]:
            issue(f"Sparse row {row_num} ({did}): missing {missing}")
            error(tab, row_num, did,
                  f"Sparse row — missing context fields: {missing}",
                  "Run backfill_ingredient_details.py to resolve.")
        if len(sparse) > 20:
            note(f"  ... and {len(sparse)-20} more sparse rows")
        note(f"Run: python3 backfill_ingredient_details.py")
    else:
        ok(f"No sparse rows — all {len(rows)} rows are fully self-describing")

    # ── Enrichment completeness metrics (non-blocking) ───────────────────────
    # Blank enrichment fields mean the row has not been processed yet.
    # After review, every enrichment field must contain a verified value,
    # "None", "Unknown", or "N/A" — never blank.
    # These gaps are reported as completeness metrics, NOT blocking errors.
    # See INGREDIENT_ENRICHMENT_RULES.md for policy.
    hdr("Enrichment Completeness (non-blocking — blank = unprocessed)")
    enrichment_fields = [
        "Cut_Type", "Preparation", "Ingredient_Type", "Status",
        "Version", "Ingredient_Source", "Allergen_Flags", "Component_Role",
    ]
    # Reviewed states: any of these means the field was deliberately set.
    # Only empty string counts as a gap.
    enrichment_gaps  = {f: 0 for f in enrichment_fields}
    rows_with_blanks = 0
    for row in rows:
        row_has_blank = False
        for field in enrichment_fields:
            val = cell(row, get_col(headers, field))
            if not val:
                enrichment_gaps[field] += 1
                row_has_blank = True
        if row_has_blank:
            rows_with_blanks += 1

    total_blank = sum(enrichment_gaps.values())
    if total_blank == 0:
        ok("All enrichment fields processed — no blank slots")
    else:
        note(f"{rows_with_blanks} of {len(rows)} rows have unprocessed enrichment fields "
             f"({total_blank} blank slots — not blocking)")
        note("  Blank = unprocessed. After review, set a verified value, None, Unknown, or N/A.")
        for field, cnt in enrichment_gaps.items():
            if cnt:
                note(f"  {field}: {cnt} blank")
        note("  Run: python3 analyze_enrichment.py  for full Data Richness Report")


def validate_dish_level_data(ss):
    """Full validation of Goldpan Dish Level Data tab. Returns set of valid Dish_IDs."""
    tab = "Goldpan Dish Level Data"
    section(f"TABLE: {tab}")

    headers, rows = read_tab(ss, tab)
    if headers is None:
        error(tab, 0, "TAB", "Tab not found.", "Create the Goldpan Dish Level Data tab.")
        issue("Tab not found — skipping.")
        return set(), set()

    if not rows:
        warn(tab, 0, "TAB", "Tab exists but has no data rows.")
        return set(), set()

    dish_id_col = get_col(headers, "Dish_ID")
    rest_id_col = get_col(headers, "Restaurant_ID")
    status_col  = get_col(headers, "Status")

    # ── Record summary ──────────────────────────────────────────────────────────
    hdr("Record Summary")
    dish_ids    = set()
    rest_ids    = set()
    active_ids  = set()
    inactive_ids = set()

    for row in rows:
        did    = cell(row, dish_id_col)
        rid    = cell(row, rest_id_col)
        status = cell(row, status_col)
        if did:
            dish_ids.add(did)
            if status == "Active":
                active_ids.add(did)
            elif status == "Inactive":
                inactive_ids.add(did)
        if rid:
            rest_ids.add(rid)

    ok(f"Total rows         : {len(rows)}")
    ok(f"Unique Dish_IDs    : {len(dish_ids)}")
    ok(f"Active dishes      : {len(active_ids)}")
    ok(f"Inactive dishes    : {len(inactive_ids)}")
    ok(f"Unique restaurants : {len(rest_ids)}")

    # ── Schema ──────────────────────────────────────────────────────────────────
    validate_schema(tab, headers)

    # ── Required fields ─────────────────────────────────────────────────────────
    validate_required_fields(tab, headers, rows, "Dish_ID")

    # ── Duplicates: Dish_ID ──────────────────────────────────────────────────────
    validate_duplicates(tab, headers, rows, ["Dish_ID"])

    # ── ID format ───────────────────────────────────────────────────────────────
    validate_id_format(tab, headers, rows, dish_id_col="Dish_ID", rest_id_col="Restaurant_ID")

    # ── Enum validation ─────────────────────────────────────────────────────────
    validate_enum(tab, headers, rows, {"Status": VALID["Status"]}, "Dish_ID")

    # ── Last_Updated format ──────────────────────────────────────────────────────
    hdr("Data Integrity — Last_Updated")
    lu_col = get_col(headers, "Last_Updated")
    bad_dates = []
    if lu_col is not None:
        for i, row in enumerate(rows, start=2):
            val = cell(row, lu_col)
            if val:
                # Accept M/D/YYYY, MM/DD/YYYY, or YYYY-MM-DD
                if not re.match(r"^\d{1,4}[-/]\d{1,2}[-/]\d{2,4}$", val):
                    did = cell(row, dish_id_col) or f"row {i}"
                    bad_dates.append((i, did, val))
    if bad_dates:
        for row_num, did, val in bad_dates[:10]:
            note(f"Row {row_num} ({did}): Last_Updated = '{val}' — unusual date format")
            warn(tab, row_num, did, f"Unusual Last_Updated format: '{val}'")
    else:
        ok("Last_Updated dates all appear well-formed")

    # ── Dietary Tag Provenance (GP-RULE-013) ────────────────────────────────────
    # Every row with Dietary_Tags must also have a Tag_Source.
    # Blank Tag_Source is a data quality WARNING (non-blocking per R6).
    hdr("Dietary Tag Provenance — Tag_Source (GP-RULE-013)")
    tags_col       = get_col(headers, "Dietary_Tags")
    tag_source_col = get_col(headers, "Tag_Source")

    if tag_source_col is None:
        note("Tag_Source column not found — add it to Goldpan Dish Level Data")
        warn(tab, 1, "SCHEMA", "Missing optional column: Tag_Source (required by GP-RULE-013)")
    else:
        # Enum validation for Tag_Source values
        validate_enum(tab, headers, rows,
                      {"Tag_Source": VALID["Tag_Source"]}, "Dish_ID")

        # Provenance gap check: Dietary_Tags present but Tag_Source blank
        provenance_gaps = []
        for i, row in enumerate(rows, start=2):
            did        = cell(row, dish_id_col) or f"row {i}"
            tags_val   = cell(row, tags_col) if tags_col is not None else ""
            source_val = cell(row, tag_source_col)
            if tags_val and tags_val.lower() not in {"none", ""} and not source_val:
                provenance_gaps.append((i, did, tags_val))

        if provenance_gaps:
            note(f"{len(provenance_gaps)} dish(es) have Dietary_Tags but no Tag_Source "
                 f"(GP-RULE-013 R6 — data quality warning, non-blocking)")
            for row_num, did, tags_val in provenance_gaps[:10]:
                note(f"  Row {row_num} ({did}): tags='{tags_val}', Tag_Source blank")
                warn(tab, row_num, did,
                     f"Dietary_Tags present but Tag_Source is blank. "
                     f"Set 'restaurant_disclosed' or 'goldpan_inferred' per GP-RULE-013.")
            if len(provenance_gaps) > 10:
                note(f"  ... and {len(provenance_gaps) - 10} more")
        else:
            ok("All rows with Dietary_Tags have a Tag_Source (GP-RULE-013)")

    return dish_ids, rest_ids


def validate_transparency_scoring(ss, dish_ids_in_dl, registry_names):
    """Full validation of Transparency Scoring tab. Returns set of restaurant names scored."""
    tab = "Transparency Scoring"
    section(f"TABLE: {tab}")

    headers, rows = read_tab(ss, tab)
    if headers is None:
        error(tab, 0, "TAB", "Tab not found.", "Create the Transparency Scoring tab.")
        issue("Tab not found — skipping.")
        return set()

    if not rows:
        warn(tab, 0, "TAB", "Tab exists but has no data rows.")
        return set()

    dish_id_col  = get_col(headers, "Dish_ID")
    rest_id_col  = get_col(headers, "Restaurant_ID")
    rname_col    = get_col(headers, "Restaurant_Name")
    tl_col       = get_col(headers, "Transparency_Level")

    # ── Record summary ──────────────────────────────────────────────────────────
    hdr("Record Summary")
    dish_ids  = set()
    rest_ids  = set()
    rnames    = set()

    for row in rows:
        did = cell(row, dish_id_col)
        rid = cell(row, rest_id_col)
        rn  = normalize_restaurant_name(cell(row, rname_col))
        if did:
            dish_ids.add(did)
        if rid:
            rest_ids.add(rid)
        if rn:
            rnames.add(rn)

    ok(f"Total rows              : {len(rows)}")
    ok(f"Unique scored Dish_IDs  : {len(dish_ids)}")
    ok(f"Unique restaurants      : {len(rest_ids)}")

    # ── Schema ──────────────────────────────────────────────────────────────────
    validate_schema(tab, headers)

    # ── Required fields ─────────────────────────────────────────────────────────
    validate_required_fields(tab, headers, rows, "Dish_ID")

    # ── Duplicates: Dish_ID ──────────────────────────────────────────────────────
    validate_duplicates(tab, headers, rows, ["Dish_ID"])

    # ── Enum: Transparency_Level ─────────────────────────────────────────────────
    validate_enum(tab, headers, rows,
                  {"Transparency_Level": VALID["Transparency_Level"]}, "Dish_ID")

    # ── Relationship: scored dish must exist in Dish Level Data ────────────────
    hdr("Referential Integrity — Dish Level Data coverage")
    missing_in_dl = []
    for i, row in enumerate(rows, start=2):
        did = cell(row, dish_id_col)
        if did and did not in dish_ids_in_dl:
            dname = cell(row, get_col(headers, "Dish_Name")) if get_col(headers, "Dish_Name") else ""
            missing_in_dl.append((i, did, dname))

    if missing_in_dl:
        for row_num, did, dname in missing_in_dl[:20]:
            issue(f"Row {row_num}: scored dish {did} ('{dname}') not in Dish Level Data")
            error(tab, row_num, did,
                  f"Scored dish '{did}' has no Dish Level Data row",
                  "Add the dish to Dish Level Data or mark it Inactive.")
    else:
        ok(f"All {len(dish_ids)} scored dishes found in Dish Level Data")

    # ── Relationship: restaurant must have Menu Source Registry entry ──────────
    hdr("Referential Integrity — Menu Source Registry coverage")
    if registry_names is None:
        note("Menu Source Registry not loaded — skipping registry coverage check")
    else:
        missing_in_reg = [rn for rn in rnames if rn not in registry_names]
        if missing_in_reg:
            for rn in missing_in_reg:
                issue(f"Restaurant '{rn}' in Transparency Scoring has no Menu Source Registry entry")
                error(tab, "?", rn,
                      f"Restaurant '{rn}' is missing from the Menu Source Registry",
                      "Add this restaurant to the Menu Source Registry before canvassing.")
        else:
            ok(f"All {len(rnames)} scored restaurants have a Menu Source Registry entry")

    return rnames


def validate_menu_source_registry(ss, scored_restaurant_names):
    """Full validation of Menu Source Registry tab."""
    tab = "Menu Source Registry"
    section(f"TABLE: {tab}")

    headers, rows = read_tab(ss, tab)
    if headers is None:
        warn(tab, 0, "TAB", "Menu Source Registry tab not found.")
        note("Tab not found — create it with create_menu_source_registry.py")
        return None  # non-blocking — registry is operational, not pipeline-critical

    if not rows:
        warn(tab, 0, "TAB", "Tab exists but has no data rows.")
        return set()

    rname_col = get_col(headers, "Restaurant_Name")

    # ── Record summary ──────────────────────────────────────────────────────────
    hdr("Record Summary")
    rnames = set()
    for row in rows:
        rn = cell(row, rname_col)
        if rn:
            # Apply same normalization as fetch_dishes.py and validate_transparency_scoring
            # so that "East West" → "EastWest" and "Brick & Tin Mountain Brook" → "Brick & Tin"
            # match correctly against scored restaurant names.
            rnames.add(normalize_restaurant_name(rn))

    ok(f"Total rows              : {len(rows)}")
    ok(f"Unique restaurants      : {len(rnames)}")

    # ── Schema ──────────────────────────────────────────────────────────────────
    validate_schema(tab, headers)

    # ── Required fields ─────────────────────────────────────────────────────────
    validate_required_fields(tab, headers, rows, "Restaurant_Name")

    # ── Duplicates: Restaurant_Name ──────────────────────────────────────────────
    validate_duplicates(tab, headers, rows, ["Restaurant_Name"])

    # ── Enum values ─────────────────────────────────────────────────────────────
    validate_enum(tab, headers, rows, {
        "Source_Confidence":  VALID["Source_Confidence"],
        "Menu_Status":        VALID["Menu_Status"],
        "Canvass_Priority":   VALID["Canvass_Priority"],
    }, "Restaurant_Name")

    # ── Coverage: every scored restaurant must be in registry ──────────────────
    hdr("Coverage — Transparency Scoring → Registry")
    if scored_restaurant_names:
        not_in_registry = [rn for rn in scored_restaurant_names if rn not in rnames]
        if not_in_registry:
            for rn in not_in_registry:
                issue(f"Scored restaurant not in registry: '{rn}'")
                error(tab, "?", rn,
                      f"'{rn}' appears in Transparency Scoring but has no registry entry",
                      "Add to Menu Source Registry.")
        else:
            ok(f"All {len(scored_restaurant_names)} scored restaurants are in registry")
    else:
        note("No scored restaurant names provided — coverage check skipped")

    # ── Needs Review flag ───────────────────────────────────────────────────────
    hdr("Business Rule — Needs Review restaurants")
    status_col = get_col(headers, "Menu_Status")
    needs_review = []
    if status_col is not None:
        for i, row in enumerate(rows, start=2):
            st = cell(row, status_col)
            rn = cell(row, rname_col)
            if st == "Needs Review":
                needs_review.append((i, rn))

    if needs_review:
        for row_num, rn in needs_review:
            note(f"Row {row_num}: '{rn}' has Menu_Status = Needs Review — do not canvass until resolved")
            warn(tab, row_num, rn,
                 f"'{rn}' is marked Needs Review. Must not be canvassed until status is resolved.")
    else:
        ok("No restaurants flagged as Needs Review")

    # ── Freshness column enum validation ────────────────────────────────────────
    hdr("Freshness — enum validation")
    freshness_enums = {
        "Recanvass_Status":      VALID["Recanvass_Status"],
        "Source_Check_Status":   VALID["Source_Check_Status"],
        "Menu_Changed":          VALID["Menu_Changed"],
        "Forced_Recanvass_Flag": VALID["Forced_Recanvass_Flag"],
    }
    freshness_cols_present = {
        col: get_col(headers, col)
        for col in freshness_enums
        if get_col(headers, col) is not None
    }
    if not freshness_cols_present:
        note("Freshness columns not found — run add_freshness_columns.py --apply")
    else:
        for col, col_idx in freshness_cols_present.items():
            valid_vals = freshness_enums[col]
            bad = []
            for i, row in enumerate(rows, start=2):
                v = cell(row, col_idx).strip()
                if v not in valid_vals:
                    rn = cell(row, rname_col)
                    bad.append((i, rn, v))
            if bad:
                for row_num, rn, v in bad:
                    error(tab, row_num, rn,
                          f"{col} has invalid value '{v}'",
                          f"Valid values: {sorted(valid_vals)}")
            else:
                ok(f"{col}: all values valid")

    # ── Freshness snapshot — stale detection ────────────────────────────────────
    hdr("Freshness — snapshot staleness (GP-RULE-008 v1.1)")
    scd_col = get_col(headers, "Status_Computed_Date")
    if scd_col is None:
        note("Status_Computed_Date column not found — run add_freshness_columns.py --apply")
    else:
        today_dt = datetime.date.fromisoformat(TODAY)
        stale_warn  = []
        stale_error = []
        missing_snapshot = []

        for i, row in enumerate(rows, start=2):
            rn  = cell(row, rname_col)
            scd = cell(row, scd_col).strip()
            if not scd:
                missing_snapshot.append((i, rn))
                continue
            try:
                scd_dt = datetime.date.fromisoformat(scd)
                age = (today_dt - scd_dt).days
                if age >= SNAPSHOT_ERROR_DAYS:
                    stale_error.append((i, rn, scd, age))
                elif age >= SNAPSHOT_WARN_DAYS:
                    stale_warn.append((i, rn, scd, age))
            except ValueError:
                error(tab, i, rn,
                      f"Status_Computed_Date has invalid date format: '{scd}'",
                      "Expected YYYY-MM-DD. Run check_freshness.py --apply to reset.")

        if missing_snapshot:
            for row_num, rn in missing_snapshot:
                warn(tab, row_num, rn,
                     f"Status_Computed_Date is blank — freshness snapshot not yet computed.",
                     )
            note(f"{len(missing_snapshot)} restaurant(s) missing snapshot — run: check_freshness.py --apply")

        if stale_error:
            for row_num, rn, scd, age in stale_error:
                error(tab, row_num, rn,
                      f"Freshness snapshot critically stale: {age} days old (computed {scd}). "
                      f"Threshold: {SNAPSHOT_ERROR_DAYS} days.",
                      "Run: python3 check_freshness.py --apply")
        if stale_warn:
            for row_num, rn, scd, age in stale_warn:
                warn(tab, row_num, rn,
                     f"Freshness snapshot stale: {age} days old (computed {scd}). "
                     f"Threshold: {SNAPSHOT_WARN_DAYS} days.")
            note(f"Stale snapshots affect derived conclusion confidence. Run: check_freshness.py --apply")

        if not missing_snapshot and not stale_error and not stale_warn:
            # Find oldest snapshot for reporting
            oldest_age = 0
            for i, row in enumerate(rows, start=2):
                scd = cell(row, scd_col).strip()
                if scd:
                    try:
                        age = (today_dt - datetime.date.fromisoformat(scd)).days
                        oldest_age = max(oldest_age, age)
                    except ValueError:
                        pass
            ok(f"All snapshots current — oldest: {oldest_age} day(s) (threshold: warn={SNAPSHOT_WARN_DAYS}d, error={SNAPSHOT_ERROR_DAYS}d)")

    return rnames


def validate_allergen_disclosures(ss, dish_ids_in_dl):
    """Full validation of Allergen Disclosures tab (GP-RULE-014).

    This tab is Evidence System. Its contents are canvasser-recorded restaurant
    disclosures. No field in it may be computed by GoldPan's rules engine.

    Key checks:
    - Schema and required fields
    - Allergen value must be a canonical slug (ALLERGEN_CANONICAL_SLUGS)
    - Disclosure_Status must be in ALLERGEN_DISCLOSURE_STATUSES
    - Scope must be in ALLERGEN_DISCLOSURE_SCOPES
    - Source_Type must be in MACRO_ELIGIBLE_SOURCES
    - free_from requires Source_Type in ALLERGEN_FREE_FROM_ELIGIBLE_SOURCES
    - Scope=dish requires Dish_ID; Scope=restaurant requires blank Dish_ID
    - Source_Date must be a valid ISO 8601 date
    - Dish_ID (when present) must exist in Goldpan Dish Level Data
    - Duplicate detection: (Dish_ID or Restaurant_ID) + Allergen + Disclosure_Status
    - Alias detection: warns if Allergen matches a known non-canonical alias
    """
    tab = "Allergen Disclosures"
    section(f"TABLE: {tab}")

    headers, rows = read_tab(ss, tab)
    if headers is None:
        warn(tab, 0, "TAB",
             "Allergen Disclosures tab not found. Create it with headers from ALLERGEN_ARCHITECTURE.md.")
        note("Tab not yet created — no allergen disclosure data to validate.")
        return

    if not rows:
        note("Tab exists but has no data rows — no allergen disclosures recorded yet.")
        ok("0 rows. Nothing to validate.")
        return

    # ── Column index lookups ────────────────────────────────────────────────────
    col = {name: get_col(headers, name) for name in SCHEMA[tab]["canonical"]}

    # ── Record summary ──────────────────────────────────────────────────────────
    hdr("Record Summary")
    rest_ids_seen = set()
    dish_ids_seen = set()
    for row in rows:
        rid = cell(row, col["Restaurant_ID"])
        did = cell(row, col["Dish_ID"])
        if rid:
            rest_ids_seen.add(rid)
        if did:
            dish_ids_seen.add(did)
    ok(f"Total rows              : {len(rows)}")
    ok(f"Unique restaurants      : {len(rest_ids_seen)}")
    ok(f"Unique dishes with data : {len(dish_ids_seen)}")

    # ── Schema ──────────────────────────────────────────────────────────────────
    validate_schema(tab, headers)

    # ── Required fields ─────────────────────────────────────────────────────────
    validate_required_fields(tab, headers, rows, "Restaurant_ID")

    # ── ID format ───────────────────────────────────────────────────────────────
    validate_id_format(tab, headers, rows, dish_id_col="Dish_ID", rest_id_col="Restaurant_ID")

    # ── Duplicate detection (scope-aware) ───────────────────────────────────────
    # Natural key: (Dish_ID + Allergen + Disclosure_Status) for dish-scope rows,
    # (Restaurant_ID + Allergen + Disclosure_Status) for restaurant-scope rows.
    hdr("Duplicate Validation  (scope-aware natural key)")
    seen_keys = {}
    dupes = []
    for i, row in enumerate(rows, start=2):
        scope  = cell(row, col["Scope"])
        alg    = cell(row, col["Allergen"])
        status = cell(row, col["Disclosure_Status"])
        if scope == "restaurant":
            key = ("restaurant", cell(row, col["Restaurant_ID"]), alg, status)
        else:
            key = ("dish", cell(row, col["Dish_ID"]), alg, status)
        if not any(key[1:]):
            continue
        if key in seen_keys:
            dupes.append((i, key, seen_keys[key]))
        else:
            seen_keys[key] = i

    if dupes:
        for row_num, key, first_row in dupes[:20]:
            issue(f"Row {row_num} duplicates row {first_row}: scope={key[0]} id={key[1]} "
                  f"allergen={key[2]} status={key[3]}")
            error(tab, row_num, key[1],
                  f"Duplicate disclosure — same scope/ID/allergen/status as row {first_row}",
                  "Remove or merge the duplicate row.")
        if len(dupes) > 20:
            note(f"  ... and {len(dupes) - 20} more duplicates not shown")
    else:
        ok("No duplicate disclosure records")

    # ── Enum validation ─────────────────────────────────────────────────────────
    hdr("Enum / Vocabulary Validation")

    allergen_errors = []
    allergen_alias_warns = []
    status_errors = []
    scope_errors = []
    source_type_errors = []

    for i, row in enumerate(rows, start=2):
        rid = cell(row, col["Restaurant_ID"]) or f"row {i}"

        alg = cell(row, col["Allergen"])
        if alg:
            if alg in ALLERGEN_SLUG_ALIASES:
                canonical = ALLERGEN_SLUG_ALIASES[alg]
                allergen_alias_warns.append((i, rid, alg, canonical))
            elif alg not in ALLERGEN_CANONICAL_SLUGS:
                allergen_errors.append((i, rid, alg))

        ds = cell(row, col["Disclosure_Status"])
        if ds and ds not in ALLERGEN_DISCLOSURE_STATUSES:
            status_errors.append((i, rid, ds))

        sc = cell(row, col["Scope"])
        if sc and sc not in ALLERGEN_DISCLOSURE_SCOPES:
            scope_errors.append((i, rid, sc))

        st = cell(row, col["Source_Type"])
        if st and st not in MACRO_ELIGIBLE_SOURCES:
            source_type_errors.append((i, rid, st))

    # Allergen slug errors
    if allergen_errors:
        for row_num, rid, val in allergen_errors[:10]:
            issue(f"Row {row_num} ({rid}): Allergen='{val}' is not a canonical slug. "
                  f"Valid: {sorted(ALLERGEN_CANONICAL_SLUGS)}")
            error(tab, row_num, rid,
                  f"Non-canonical Allergen value: '{val}'",
                  f"Use one of: {sorted(ALLERGEN_CANONICAL_SLUGS)}")
    else:
        ok("Allergen: all values are canonical slugs")

    # Allergen alias warnings
    if allergen_alias_warns:
        for row_num, rid, val, canonical in allergen_alias_warns:
            note(f"Row {row_num} ({rid}): Allergen='{val}' — known alias for '{canonical}'. "
                 f"Update to canonical slug.")
            warn(tab, row_num, rid,
                 f"Allergen alias '{val}' should be '{canonical}' (GP-RULE-014)")

    if status_errors:
        for row_num, rid, val in status_errors[:10]:
            issue(f"Row {row_num} ({rid}): Disclosure_Status='{val}' is invalid. "
                  f"Valid: {sorted(ALLERGEN_DISCLOSURE_STATUSES)}")
            error(tab, row_num, rid,
                  f"Invalid Disclosure_Status: '{val}'",
                  f"Use one of: {sorted(ALLERGEN_DISCLOSURE_STATUSES)}")
    else:
        ok("Disclosure_Status: all values valid")

    if scope_errors:
        for row_num, rid, val in scope_errors[:10]:
            issue(f"Row {row_num} ({rid}): Scope='{val}' is invalid. "
                  f"Valid: {sorted(ALLERGEN_DISCLOSURE_SCOPES)}")
            error(tab, row_num, rid,
                  f"Invalid Scope: '{val}'",
                  f"Use one of: {sorted(ALLERGEN_DISCLOSURE_SCOPES)}")
    else:
        ok("Scope: all values valid")

    if source_type_errors:
        for row_num, rid, val in source_type_errors[:10]:
            issue(f"Row {row_num} ({rid}): Source_Type='{val}' is not a macro-eligible source. "
                  f"Valid: {sorted(MACRO_ELIGIBLE_SOURCES)}")
            error(tab, row_num, rid,
                  f"Invalid Source_Type: '{val}' — not in MACRO_ELIGIBLE_SOURCES",
                  f"Use one of: {sorted(MACRO_ELIGIBLE_SOURCES)}")
    else:
        ok("Source_Type: all values are macro-eligible sources")

    # ── free_from source tier validation (GP-RULE-014) ──────────────────────────
    # free_from requires Tier 1 or Tier 2 source only.
    # Tier 3+ (ordering_platform, restaurant_qa, pdf) are macro-eligible but
    # insufficient for a restaurant allergen-free claim.
    hdr("GP-RULE-014 — free_from Source Tier Validation")
    free_from_tier_errors = []
    for i, row in enumerate(rows, start=2):
        ds = cell(row, col["Disclosure_Status"])
        st = cell(row, col["Source_Type"])
        if ds == "free_from" and st and st not in ALLERGEN_FREE_FROM_ELIGIBLE_SOURCES:
            rid = cell(row, col["Restaurant_ID"]) or f"row {i}"
            alg = cell(row, col["Allergen"])
            free_from_tier_errors.append((i, rid, alg, st))

    if free_from_tier_errors:
        for row_num, rid, alg, st in free_from_tier_errors[:10]:
            issue(f"Row {row_num} ({rid}): free_from disclosure for '{alg}' "
                  f"cites Source_Type='{st}' — below free_from threshold.")
            error(tab, row_num, rid,
                  f"free_from disclosure for '{alg}' requires a Tier 1 or Tier 2 source. "
                  f"'{st}' is macro-eligible but insufficient for a free_from claim. "
                  f"(GP-RULE-014)",
                  f"Re-canvass from: {sorted(ALLERGEN_FREE_FROM_ELIGIBLE_SOURCES)}")
    else:
        ok("free_from disclosures: all cite Tier 1 or Tier 2 sources")

    # ── Scope / Dish_ID cross-validation ────────────────────────────────────────
    hdr("Scope / Dish_ID Cross-Validation")
    scope_dish_errors = []
    scope_rest_errors = []
    for i, row in enumerate(rows, start=2):
        sc  = cell(row, col["Scope"])
        did = cell(row, col["Dish_ID"])
        rid = cell(row, col["Restaurant_ID"]) or f"row {i}"
        if sc == "dish" and not did:
            scope_dish_errors.append((i, rid))
        elif sc == "restaurant" and did:
            scope_rest_errors.append((i, rid, did))

    if scope_dish_errors:
        for row_num, rid in scope_dish_errors[:10]:
            issue(f"Row {row_num} ({rid}): Scope=dish but Dish_ID is blank.")
            error(tab, row_num, rid,
                  "Scope=dish requires a Dish_ID.",
                  "Add the Dish_ID or change Scope to 'restaurant'.")
    else:
        ok("Scope=dish rows: all have Dish_ID")

    if scope_rest_errors:
        for row_num, rid, did in scope_rest_errors[:10]:
            issue(f"Row {row_num} ({rid}): Scope=restaurant but Dish_ID='{did}' is populated.")
            error(tab, row_num, rid,
                  f"Scope=restaurant must have a blank Dish_ID. Found: '{did}'.",
                  "Clear the Dish_ID or change Scope to 'dish'.")
    else:
        ok("Scope=restaurant rows: all have blank Dish_ID")

    # ── Source_Date format validation ────────────────────────────────────────────
    hdr("Source_Date Format Validation")
    date_errors = []
    for i, row in enumerate(rows, start=2):
        sd  = cell(row, col["Source_Date"])
        rid = cell(row, col["Restaurant_ID"]) or f"row {i}"
        if sd:
            try:
                datetime.date.fromisoformat(sd)
            except ValueError:
                date_errors.append((i, rid, sd))

    if date_errors:
        for row_num, rid, sd in date_errors[:10]:
            issue(f"Row {row_num} ({rid}): Source_Date='{sd}' is not a valid ISO 8601 date.")
            error(tab, row_num, rid,
                  f"Invalid Source_Date format: '{sd}'",
                  "Use YYYY-MM-DD format (e.g. 2026-06-30).")
    else:
        ok("Source_Date: all values are valid ISO 8601 dates")

    # ── Referential integrity: Dish_ID must exist in Goldpan Dish Level Data ───
    hdr("Referential Integrity — Dish_ID → Goldpan Dish Level Data")
    orphaned = []
    for i, row in enumerate(rows, start=2):
        did = cell(row, col["Dish_ID"])
        sc  = cell(row, col["Scope"])
        if did and sc == "dish" and did not in dish_ids_in_dl:
            rid = cell(row, col["Restaurant_ID"]) or f"row {i}"
            alg = cell(row, col["Allergen"])
            orphaned.append((i, rid, did, alg))

    if orphaned:
        for row_num, rid, did, alg in orphaned[:20]:
            issue(f"Row {row_num} ({rid}): Dish_ID '{did}' ('{alg}') not in Goldpan Dish Level Data.")
            error(tab, row_num, did,
                  f"Orphaned allergen disclosure — Dish_ID '{did}' has no Dish Level Data row.",
                  "Add the dish to Goldpan Dish Level Data first.")
        if len(orphaned) > 20:
            note(f"  ... and {len(orphaned) - 20} more orphaned rows")
    else:
        dish_scope_count = sum(
            1 for row in rows
            if cell(row, col["Scope"]) == "dish" and cell(row, col["Dish_ID"])
        )
        ok(f"All {dish_scope_count} dish-scope disclosure rows reference valid Dish_IDs")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    filter_table = None
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--table" and i + 1 < len(args):
            filter_table = args[i + 1].lower()

    _emit("=" * 65)
    _emit(f"  GOLDPAN DATABASE VALIDATION REPORT")
    _emit(f"  {TODAY}")
    _emit("=" * 65)

    print(f"Goldpan Database Validation  —  {TODAY}")
    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)
    print("Connected. Running checks...\n")

    # Run validations in dependency order.
    # Dish Level Data must run first to provide Dish_ID reference set.
    # Registry must run before Scoring (or Scoring passes None for registry check).

    dish_ids_in_dl = set()
    rest_ids_in_dl = set()
    registry_names = None
    scored_names   = set()

    run_all = filter_table is None

    # Validation order matters for cross-table checks:
    #   1. Dish Level Data  → provides dish_ids_in_dl for Scoring + Ingredient checks
    #   2. Transparency Scoring → provides scored_names for Registry coverage check
    #   3. Menu Source Registry → uses scored_names (must run AFTER Scoring)
    #   4. Ingredient Details → uses dish_ids_in_dl

    # ── 1. Dish Level Data ──────────────────────────────────────────────────────
    if run_all or filter_table == "dish":
        dish_ids_in_dl, rest_ids_in_dl = validate_dish_level_data(ss)
    elif filter_table in ("ingredient", "scoring", "allergen"):
        # Load dish IDs without running full GDL validation — needed for
        # referential integrity checks in Ingredient Details, Scoring, and
        # Allergen Disclosures tabs.
        dish_ids_in_dl = load_dish_ids(ss)

    # ── 2. Transparency Scoring ─────────────────────────────────────────────────
    #    Run before Registry so scored_names is populated for the coverage check.
    if run_all or filter_table == "scoring":
        scored_names = validate_transparency_scoring(ss, dish_ids_in_dl, registry_names)

    # ── 3. Menu Source Registry ─────────────────────────────────────────────────
    #    scored_names is now populated — coverage check will work correctly.
    if run_all or filter_table == "registry":
        registry_names = validate_menu_source_registry(ss, scored_names)

    # ── 4. Ingredient Details ───────────────────────────────────────────────────
    if run_all or filter_table == "ingredient":
        validate_ingredient_details(ss, dish_ids_in_dl)

    # ── 5. Allergen Disclosures ─────────────────────────────────────────────────
    if run_all or filter_table == "allergen":
        validate_allergen_disclosures(ss, dish_ids_in_dl)

    # ── Error / Warning Summary (goes to file) ─────────────────────────────────
    section("ERRORS  (blocking)")
    if errors:
        for e in errors:
            row_str = f"row {e['row']}" if isinstance(e['row'], int) else str(e['row'])
            _emit(f"  ✗ [{e['table']}] {row_str} | {e['id']}")
            _emit(f"      Problem : {e['problem']}")
            if e['fix']:
                _emit(f"      Fix     : {e['fix']}")
    else:
        _emit("  ✓ No blocking errors.")

    section("WARNINGS  (non-blocking)")
    if warnings:
        for w in warnings:
            row_str = f"row {w['row']}" if isinstance(w['row'], int) else str(w['row'])
            _emit(f"  ⚠ [{w['table']}] {row_str} | {w['id']}")
            _emit(f"      {w['problem']}")
    else:
        _emit("  ✓ No warnings.")

    # ── Final Summary ───────────────────────────────────────────────────────────
    _emit("")
    _emit("=" * 65)
    status = "PASS" if not errors else "FAIL"
    _emit(f"  OVERALL STATUS: {status}")
    _emit("=" * 65)

    if run_all:
        tables_run = ["Goldpan Dish Level Data", "Transparency Scoring",
                      "Menu Source Registry", "Ingredient Details", "Allergen Disclosures"]
    else:
        tables_run = [filter_table]

    for t in tables_run:
        t_errors   = [e for e in errors   if e["table"] == t]
        t_warnings = [w for w in warnings if w["table"] == t]
        e_str = f"{len(t_errors)} error(s)" if t_errors else "0 errors"
        w_str = f"{len(t_warnings)} warning(s)" if t_warnings else "0 warnings"
        icon  = "✓" if not t_errors else "✗"
        _emit(f"  {icon} {t:<35} {e_str:<20} {w_str}")

    _emit("")

    # ── Flush full report to file ───────────────────────────────────────────────
    _flush_report()

    # ── Concise terminal output ─────────────────────────────────────────────────
    print("=" * 55)
    print(f"  RESULT: {status}")
    print("=" * 55)

    if errors:
        print(f"\n  {len(errors)} blocking error(s):\n")
        for e in errors:
            row_str = f"row {e['row']}" if isinstance(e['row'], int) else str(e['row'])
            print(f"  ✗ [{e['table']}] {row_str} | {e['id']}")
            print(f"      {e['problem']}")
            if e['fix']:
                print(f"      Fix: {e['fix']}")
    else:
        print(f"\n  ✓ No blocking errors.")

    if warnings:
        print(f"\n  {len(warnings)} warning(s) — see {REPORT_FILE} for details.")
    else:
        print(f"  ✓ No warnings.")

    print(f"\n  Full report written to: {REPORT_FILE}\n")

    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()
