"""
backfill_last_canvassed.py — One-time backfill: populate Last_Canvassed in Menu Source Registry.

Derives Last_Canvassed dates from the most recent Last_Updated value across all
dishes for each restaurant (sourced from dishes.json).

Dry-run by default. Use --apply to write.

Usage:
    python3 backfill_last_canvassed.py           # dry run — show plan only
    python3 backfill_last_canvassed.py --apply   # apply to sheet
"""

import json
import os
import sys
import datetime

import gspread
from google.oauth2.service_account import Credentials

# ── Config ────────────────────────────────────────────────────────────────────

GOLDPAN_DIR    = os.path.dirname(os.path.abspath(__file__))
KEY_FILE       = os.path.join(GOLDPAN_DIR, "service_account.json")
DISHES_FILE    = os.path.join(GOLDPAN_DIR, "dishes.json")
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
REGISTRY_TAB   = "Menu Source Registry"
TODAY          = datetime.date.today().isoformat()
DRY_RUN        = "--apply" not in sys.argv

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_date(raw: str) -> str:
    """Normalize M/D/YYYY → YYYY-MM-DD. Pass through YYYY-MM-DD unchanged."""
    raw = raw.strip()
    if "/" in raw:
        parts = raw.split("/")
        return f"{parts[2]}-{int(parts[0]):02d}-{int(parts[1]):02d}"
    return raw


def derive_canvass_dates(dishes_path: str) -> dict[str, str]:
    """
    Build {restaurant_name: last_canvassed_date} from dishes.json.
    Uses the most recent Last_Updated date across all dishes per restaurant.
    """
    with open(dishes_path, encoding="utf-8") as f:
        dishes = json.load(f)

    by_restaurant: dict[str, str] = {}
    for dish in dishes:
        rname = (dish.get("restaurant") or "").strip()
        raw   = (dish.get("last_updated") or "").strip()
        if not rname or not raw:
            continue
        normalized = normalize_date(raw)
        if rname not in by_restaurant or normalized > by_restaurant[rname]:
            by_restaurant[rname] = normalized

    return by_restaurant


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    mode = "DRY RUN" if DRY_RUN else "APPLYING"
    print(f"\nbackfill_last_canvassed.py  —  {TODAY}  [{mode}]")
    print(f"  Source: {DISHES_FILE}")
    print(f"  Tab:    {REGISTRY_TAB}")

    # ── Derive dates from dishes.json ─────────────────────────────────────────
    print(f"\n  Reading dishes.json...")
    canvass_dates = derive_canvass_dates(DISHES_FILE)
    print(f"  {len(canvass_dates)} restaurant(s) with last_updated dates:")
    for rname, date in sorted(canvass_dates.items()):
        print(f"    {date}  {rname}")

    # ── Connect to sheet ──────────────────────────────────────────────────────
    print(f"\n  Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)
    ws     = ss.worksheet(REGISTRY_TAB)

    all_values = ws.get_all_values()
    if not all_values:
        print("  ERROR: Sheet is empty.")
        sys.exit(1)

    headers = [h.strip() for h in all_values[0]]

    if "Restaurant_Name" not in headers:
        print("  ERROR: Restaurant_Name column not found.")
        sys.exit(1)
    if "Last_Canvassed" not in headers:
        print("  ERROR: Last_Canvassed column not found.")
        print("         Run add_freshness_columns.py --apply first.")
        sys.exit(1)

    name_col = headers.index("Restaurant_Name") + 1     # 1-indexed
    lc_col   = headers.index("Last_Canvassed") + 1

    print(f"\n  Sheet: {len(all_values) - 1} restaurant rows")
    print(f"  Last_Canvassed column: {lc_col} ({headers[lc_col - 1]})")

    # ── Build update plan ─────────────────────────────────────────────────────
    updates   = []
    matched   = []
    unmatched = []
    already   = []

    for row_idx, row in enumerate(all_values[1:], start=2):
        sheet_name = row[name_col - 1].strip() if name_col - 1 < len(row) else ""
        current_lc = row[lc_col - 1].strip() if lc_col - 1 < len(row) else ""

        if not sheet_name:
            continue

        if sheet_name not in canvass_dates:
            unmatched.append(sheet_name)
            continue

        new_date = canvass_dates[sheet_name]

        if current_lc == new_date:
            already.append(sheet_name)
            continue

        updates.append(gspread.Cell(row=row_idx, col=lc_col, value=new_date))
        matched.append((sheet_name, current_lc or "blank", new_date))

    # ── Report plan ───────────────────────────────────────────────────────────
    if already:
        print(f"\n  Already set (no change needed): {len(already)}")
        for name in already:
            print(f"    {name}")

    if unmatched:
        print(f"\n  No match in dishes.json (will skip): {len(unmatched)}")
        for name in unmatched:
            print(f"    {name}")

    if not matched:
        print(f"\n  Nothing to update.")
        return

    print(f"\n  Will write Last_Canvassed for {len(matched)} restaurant(s):")
    for name, old, new in matched:
        print(f"    {name:<40}  {old} → {new}")

    if DRY_RUN:
        print(f"\n  DRY RUN — no changes written.")
        print(f"  To apply: python3 backfill_last_canvassed.py --apply")
        return

    # ── Write ─────────────────────────────────────────────────────────────────
    print(f"\n  Writing {len(updates)} cells...")
    ws.update_cells(updates, value_input_option="USER_ENTERED")

    # ── Verify ────────────────────────────────────────────────────────────────
    refreshed = ws.get_all_values()
    lc_col_check = [h.strip() for h in refreshed[0]].index("Last_Canvassed") + 1
    name_col_check = [h.strip() for h in refreshed[0]].index("Restaurant_Name") + 1

    confirmed = 0
    failed    = []
    for row in refreshed[1:]:
        name = row[name_col_check - 1].strip() if name_col_check - 1 < len(row) else ""
        val  = row[lc_col_check - 1].strip() if lc_col_check - 1 < len(row) else ""
        if name in canvass_dates:
            if val == canvass_dates[name]:
                confirmed += 1
            else:
                failed.append((name, val, canvass_dates[name]))

    print(f"\n  Verification:")
    if failed:
        for name, got, expected in failed:
            print(f"    ✗  {name}: got '{got}', expected '{expected}'")
        print(f"\n  WARNING: {len(failed)} row(s) not confirmed.")
        sys.exit(1)
    else:
        print(f"    ✓  All {confirmed} restaurant(s) confirmed.")

    print(f"\n  Done. Last_Canvassed populated for {len(matched)} restaurant(s).")
    print(f"\n  Next steps:")
    print(f"    python3 check_freshness.py        # dry run — review freshness report")
    print(f"    python3 check_freshness.py --apply # write Recanvass_Status to sheet")


if __name__ == "__main__":
    main()
