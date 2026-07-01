"""
backfill_ingredient_details.py

Finds sparse rows in the Ingredient Details tab — rows that are missing one
or more required context fields — and backfills them from the authoritative
Goldpan Dish Level Data tab.

Required fields per row (per DATA_RULES.md):
  Restaurant_ID, Restaurant_Name, Location, Dish_ID, Dish_Name, Ingredient

Canonical Ingredient Details headers:
  Restaurant_ID | Restaurant_Name | Location | Dish_ID | Dish_Name |
  Ingredient | Cut_Type | Preparation | Ingredient_Type | Status |
  Version | Ingredient_Source | Allergen_Flags | Component_Role

What this script does:
  1. Reads Ingredient Details tab using header-name-based column mapping.
  2. Identifies every sparse row (missing any required field).
  3. Looks up missing context from Goldpan Dish Level Data by Dish_ID.
  4. Backfills what can be resolved automatically.
  5. Flags rows that cannot be resolved for manual review.
  6. Prints a full report before writing any changes.
  7. Applies fixes via batch_update.

Usage:
  python3 backfill_ingredient_details.py           (apply fixes)
  python3 backfill_ingredient_details.py --dry-run (report only, no writes)
"""

import sys
import datetime
import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TODAY          = datetime.date.today().strftime("%Y-%m-%d")
DRY_RUN        = "--dry-run" in sys.argv

REQUIRED_FIELDS = ["Restaurant_ID", "Restaurant_Name", "Location", "Dish_ID", "Dish_Name", "Ingredient"]

# Canonical headers — used for validation; script uses header-name lookup, not fixed positions
CANONICAL_HEADERS = [
    "Restaurant_ID", "Restaurant_Name", "Location", "Dish_ID", "Dish_Name",
    "Ingredient", "Cut_Type", "Preparation", "Ingredient_Type", "Status",
    "Version", "Ingredient_Source", "Allergen_Flags", "Component_Role",
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def col_index(headers, name):
    """Return 0-based column index for a header name, or None if missing."""
    try:
        return headers.index(name)
    except ValueError:
        return None


def get_cell_value(row, idx):
    """Safely get a cell value from a row list."""
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip()


def build_dish_lookup(dl_ws):
    """
    Build a lookup dict from Goldpan Dish Level Data:
      {dish_id: {Restaurant_ID, Restaurant_Name, Location, Dish_Name}}
    Uses header-name-based mapping.
    """
    all_values = dl_ws.get_all_values()
    if not all_values:
        return {}

    headers = all_values[0]
    rid_col   = col_index(headers, "Restaurant_ID")
    rname_col = col_index(headers, "Restaurant")       # Dish Level Data uses "Restaurant"
    loc_col   = col_index(headers, "Location")
    did_col   = col_index(headers, "Dish_ID")
    dname_col = col_index(headers, "Dish_Name")

    # Also try Restaurant_Name in case tab was updated
    if rname_col is None:
        rname_col = col_index(headers, "Restaurant_Name")

    lookup = {}
    for row in all_values[1:]:
        did = get_cell_value(row, did_col)
        if not did:
            continue
        lookup[did] = {
            "Restaurant_ID":   get_cell_value(row, rid_col),
            "Restaurant_Name": get_cell_value(row, rname_col),
            "Location":        get_cell_value(row, loc_col),
            "Dish_Name":       get_cell_value(row, dname_col),
        }
    return lookup


def main():
    print(f"backfill_ingredient_details.py  —  {TODAY}")
    if DRY_RUN:
        print("DRY RUN — no changes will be written.\n")
    else:
        print()

    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    # ── Read Ingredient Details ────────────────────────────────────────────────
    print("Reading Ingredient Details...")
    ing_ws     = ss.worksheet("Ingredient Details")
    all_values = ing_ws.get_all_values()

    if len(all_values) < 2:
        print("  Ingredient Details is empty or header-only. Nothing to check.")
        return

    headers = all_values[0]
    print(f"  Headers found: {headers}")

    # Validate headers
    missing_headers = [h for h in CANONICAL_HEADERS if h not in headers]
    if missing_headers:
        print(f"\nWARNING — Missing canonical headers: {missing_headers}")
        print("  Columns that exist will be used. Missing columns will be skipped.")

    # Build column index map
    col = {h: col_index(headers, h) for h in CANONICAL_HEADERS}

    # ── Build dish lookup from Goldpan Dish Level Data ─────────────────────────
    print("Reading Goldpan Dish Level Data for backfill lookup...")
    dl_ws       = ss.worksheet("Goldpan Dish Level Data")
    dish_lookup = build_dish_lookup(dl_ws)
    print(f"  Loaded {len(dish_lookup)} dishes from Dish Level Data.")

    # ── Scan ingredient rows ───────────────────────────────────────────────────
    print("\nScanning Ingredient Details for sparse rows...")

    sparse_rows   = []  # (sheet_row_1indexed, row_data, missing_fields, resolved_data)
    updates       = []  # gspread batch_update format

    total_rows = 0
    for i, row in enumerate(all_values[1:], start=2):
        total_rows += 1

        # Check each required field
        missing = []
        for field in REQUIRED_FIELDS:
            idx = col[field]
            val = get_cell_value(row, idx)
            if not val:
                missing.append(field)

        if not missing:
            continue  # row is fine

        # Row is sparse — try to resolve from Dish Level Data
        dish_id = get_cell_value(row, col["Dish_ID"])
        lookup_data = dish_lookup.get(dish_id, {}) if dish_id else {}

        resolved   = {}
        unresolved = []

        for field in missing:
            if field == "Dish_ID" or field == "Ingredient":
                # Cannot infer Dish_ID or Ingredient from anywhere
                unresolved.append(field)
            elif field in lookup_data and lookup_data[field]:
                resolved[field] = lookup_data[field]
            elif dish_id and not lookup_data:
                unresolved.append(field)  # Dish_ID not found in Dish Level Data
            else:
                unresolved.append(field)

        sparse_rows.append({
            "sheet_row":   i,
            "dish_id":     dish_id or "(missing)",
            "ingredient":  get_cell_value(row, col["Ingredient"]),
            "missing":     missing,
            "resolved":    resolved,
            "unresolved":  unresolved,
        })

        # Build cell updates for resolved fields
        for field, value in resolved.items():
            col_idx = col[field]
            if col_idx is not None:
                cell = gspread.utils.rowcol_to_a1(i, col_idx + 1)
                updates.append({"range": cell, "values": [[value]]})

    # ── Print report ───────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"INGREDIENT DETAILS BACKFILL REPORT  —  {TODAY}")
    print(f"{'='*65}")
    print(f"Total data rows scanned : {total_rows}")
    print(f"Sparse rows found       : {len(sparse_rows)}")
    print(f"Rows fully fixable      : {sum(1 for r in sparse_rows if not r['unresolved'])}")
    print(f"Rows needing manual fix : {sum(1 for r in sparse_rows if r['unresolved'])}")

    if sparse_rows:
        print()
        print(f"{'Row':<6} {'Dish_ID':<8} {'Ingredient':<30} {'Missing':<35} {'Result'}")
        print(f"{'-'*6} {'-'*8} {'-'*30} {'-'*35} {'-'*20}")

        for r in sparse_rows:
            missing_str = ", ".join(r["missing"])
            if not r["unresolved"]:
                result = "✓ FIXED — " + ", ".join(f"{k}={v}" for k, v in r["resolved"].items())
            elif r["resolved"]:
                result = f"⚠ PARTIAL — fixed {list(r['resolved'].keys())} | still missing: {r['unresolved']}"
            else:
                result = f"✗ MANUAL REVIEW — cannot resolve: {r['unresolved']}"

            ing_display = r["ingredient"][:29] if r["ingredient"] else "(none)"
            print(f"{r['sheet_row']:<6} {r['dish_id']:<8} {ing_display:<30} {missing_str:<35} {result}")

    # ── Apply fixes ────────────────────────────────────────────────────────────
    if updates and not DRY_RUN:
        print(f"\nApplying {len(updates)} cell updates...")
        ing_ws.batch_update(updates)
        print(f"  Done. {sum(1 for r in sparse_rows if not r['unresolved'])} rows fully backfilled.")
    elif updates and DRY_RUN:
        print(f"\n[DRY RUN] Would apply {len(updates)} cell updates. Run without --dry-run to apply.")
    elif not sparse_rows:
        print("\n✓ All rows are fully populated. No backfill needed.")
    else:
        print("\nNo automatic fixes available. Manual review required for flagged rows.")

    needs_manual = [r for r in sparse_rows if r["unresolved"]]
    if needs_manual:
        print(f"\n{'='*65}")
        print(f"MANUAL REVIEW REQUIRED ({len(needs_manual)} rows)")
        print(f"{'='*65}")
        for r in needs_manual:
            print(f"  Row {r['sheet_row']} | Dish_ID: {r['dish_id']} | Ingredient: {r['ingredient'] or '(none)'}")
            print(f"    Cannot resolve: {r['unresolved']}")
            if r['dish_id'] == "(missing)":
                print(f"    → Row has no Dish_ID. Cannot look up any context. Delete or fix manually.")
            else:
                print(f"    → Dish_ID {r['dish_id']} not found in Goldpan Dish Level Data.")
                print(f"    → Confirm this dish exists, then re-run.")

    print(f"\nDone.")
    if not DRY_RUN and updates:
        print("Run: python3 fetch_dishes.py  then  bash update.sh")


if __name__ == "__main__":
    main()
