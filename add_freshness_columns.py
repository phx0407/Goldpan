"""
add_freshness_columns.py — One-time migration: add freshness columns to Menu Source Registry.

Adds the following columns (in order) to the right of existing headers,
skipping any that already exist:

    Recanvass_Tier        — integer (1/2/3); backfilled to "2" for all existing rows
    Last_Canvassed        — date YYYY-MM-DD; left blank (canvasser fills)
    Last_Source_Check     — date YYYY-MM-DD; left blank (check_sources.py fills)
    Source_Check_Status   — string; left blank
    Menu_Changed          — string yes/no/unknown; left blank
    Change_Type           — comma-separated string; left blank
    Recanvass_Status      — COMPUTED by check_freshness.py — never manually set
    Status_Computed_Date  — COMPUTED by check_freshness.py — never manually set
    Forced_Recanvass_Flag — string yes/blank; left blank
    Recanvass_Notes       — free text; left blank

Dry-run by default. Use --apply to write.

Usage:
    python3 add_freshness_columns.py           # dry run — show plan only
    python3 add_freshness_columns.py --apply   # apply to sheet
"""

import sys
import os
import datetime

import gspread
from google.oauth2.service_account import Credentials

# ── Config ────────────────────────────────────────────────────────────────────

GOLDPAN_DIR    = os.path.dirname(os.path.abspath(__file__))
KEY_FILE       = os.path.join(GOLDPAN_DIR, "service_account.json")
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
REGISTRY_TAB   = "Menu Source Registry"
TODAY          = datetime.date.today().isoformat()
DRY_RUN        = "--apply" not in sys.argv

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ── New columns in order ──────────────────────────────────────────────────────
#
# Each entry: (column_name, default_value_for_existing_rows)
# "" = leave blank. Recanvass_Tier gets "2" as the standard default.

NEW_COLUMNS = [
    ("Recanvass_Tier",        "2"),   # backfill default tier for all existing restaurants
    ("Last_Canvassed",        ""),
    ("Last_Source_Check",     ""),
    ("Source_Check_Status",   ""),
    ("Menu_Changed",          ""),
    ("Change_Type",           ""),
    ("Recanvass_Status",      ""),    # COMPUTED — check_freshness.py will populate
    ("Status_Computed_Date",  ""),    # COMPUTED — check_freshness.py will populate
    ("Forced_Recanvass_Flag", ""),
    ("Recanvass_Notes",       ""),
]

COMPUTED_COLS = {"Recanvass_Status", "Status_Computed_Date"}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    mode = "DRY RUN" if DRY_RUN else "APPLYING"
    print(f"\nadd_freshness_columns.py  —  {TODAY}  [{mode}]")
    print(f"  Tab: {REGISTRY_TAB}")

    print(f"\n  Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)
    ws     = ss.worksheet(REGISTRY_TAB)

    all_values = ws.get_all_values()
    if not all_values:
        print("  ERROR: Sheet is empty.")
        sys.exit(1)

    existing_headers = [h.strip() for h in all_values[0]]
    data_rows        = all_values[1:]
    n_data_rows      = len(data_rows)

    print(f"  {len(existing_headers)} existing columns, {n_data_rows} data rows")
    print(f"  Existing headers: {existing_headers}")

    # ── Determine which columns need to be added ──────────────────────────────
    to_add   = [(col, default) for col, default in NEW_COLUMNS if col not in existing_headers]
    to_skip  = [(col, default) for col, default in NEW_COLUMNS if col in existing_headers]

    if to_skip:
        print(f"\n  Already present (will skip):")
        for col, _ in to_skip:
            print(f"    {col}")

    if not to_add:
        print(f"\n  All columns already present. Nothing to do.")
        return

    print(f"\n  Columns to add ({len(to_add)}):")
    for col, default in to_add:
        computed_note = "  ← COMPUTED (check_freshness.py)" if col in COMPUTED_COLS else ""
        default_note  = f'  default: "{default}"' if default else "  blank"
        print(f"    {col}{default_note}{computed_note}")

    print(f"\n  Data rows affected: {n_data_rows}")

    if DRY_RUN:
        print(f"\n  DRY RUN — no changes written.")
        print(f"  To apply: python3 add_freshness_columns.py --apply")
        return

    # ── Build batch update ────────────────────────────────────────────────────
    # Append each new column: write header in row 1, default values in rows 2..N

    start_col = len(existing_headers) + 1   # 1-indexed column after last existing

    all_cells = []

    for i, (col, default) in enumerate(to_add):
        col_index = start_col + i   # 1-indexed

        # Header cell (row 1)
        all_cells.append(gspread.Cell(row=1, col=col_index, value=col))

        # Data cells (rows 2..N+1)
        for row_idx in range(n_data_rows):
            row_num = row_idx + 2   # 1-indexed, accounting for header
            all_cells.append(
                gspread.Cell(row=row_num, col=col_index, value=default)
            )

    # Expand the grid to fit the new columns before writing
    required_cols = len(existing_headers) + len(to_add)
    current_cols  = ws.col_count
    if required_cols > current_cols:
        print(f"  Expanding grid: {current_cols} → {required_cols} columns...")
        ws.resize(cols=required_cols)

    print(f"\n  Writing {len(all_cells)} cells ({len(to_add)} columns × {n_data_rows + 1} rows)...")
    ws.update_cells(all_cells, value_input_option="USER_ENTERED")

    # ── Verify ────────────────────────────────────────────────────────────────
    refreshed = ws.get_all_values()
    new_headers = [h.strip() for h in refreshed[0]]
    added_confirmed = [col for col, _ in to_add if col in new_headers]
    missing         = [col for col, _ in to_add if col not in new_headers]

    print(f"\n  Verification:")
    for col in added_confirmed:
        print(f"    ✓  {col}")
    for col in missing:
        print(f"    ✗  {col}  — NOT FOUND after write")

    if missing:
        print(f"\n  WARNING: {len(missing)} column(s) not confirmed. Check sheet manually.")
        sys.exit(1)

    print(f"\n  Done. {len(added_confirmed)} column(s) added to {REGISTRY_TAB}.")
    print(f"\n  Next steps:")
    print(f"    1. Fill Last_Canvassed for each restaurant (use known canvass dates)")
    print(f"    2. Run: python3 check_freshness.py")
    print(f"       → Computes Recanvass_Status for all restaurants (dry run)")
    print(f"    3. Run: python3 check_freshness.py --apply")
    print(f"       → Writes Recanvass_Status + Status_Computed_Date to sheet")


if __name__ == "__main__":
    main()
