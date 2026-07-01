"""
fix_database_errors.py

Fixes the remaining validation errors after shifted-row repair:

  1. Duplicate Dish_IDs in Goldpan Dish Level Data
     → Keep the row with the most non-empty fields; delete the rest.

  2. Duplicate (Dish_ID + Ingredient) in Ingredient Details
     → Keep first occurrence; delete duplicates.

  3. Orphaned ingredient rows (Dish_ID not in Dish Level Data)
     → Report for manual review; do NOT delete automatically.

  4. Blank Status in Dish Level Data
     → Backfill "Active" for any row where Status is blank.
     → Does not touch rows where Status is already "Active" or "Inactive".

Usage:
  python3 fix_database_errors.py            # dry run — report only
  python3 fix_database_errors.py --apply    # apply all fixes
"""

import sys
import datetime
import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TODAY          = datetime.date.today().strftime("%Y-%m-%d")
APPLY          = "--apply" in sys.argv

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

VALID_STATUS = {"Active", "Inactive"}


def col_idx(headers, name):
    try:
        return headers.index(name)
    except ValueError:
        return None


def cell(row, idx):
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip()


def count_nonempty(row):
    return sum(1 for v in row if str(v).strip())


def delete_rows(ws, row_numbers):
    """Delete rows in a single batch, highest index first."""
    if not row_numbers:
        return 0
    requests = [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": ws._properties["sheetId"],
                    "dimension": "ROWS",
                    "startIndex": r - 1,
                    "endIndex": r,
                }
            }
        }
        for r in sorted(row_numbers, reverse=True)
    ]
    ws.spreadsheet.batch_update({"requests": requests})
    return len(row_numbers)


def fix_dish_level_data_duplicates(ss):
    """Remove duplicate Dish_IDs from Goldpan Dish Level Data."""
    print("\n── Goldpan Dish Level Data — Duplicate Dish_IDs ──")
    ws         = ss.worksheet("Goldpan Dish Level Data")
    all_values = ws.get_all_values()
    headers    = [h.strip() for h in all_values[0]]
    did_col    = col_idx(headers, "Dish_ID")

    seen       = {}   # dish_id → (row_num, row_data, nonempty_count)
    to_delete  = []

    for i, row in enumerate(all_values[1:], start=2):
        did = cell(row, did_col)
        if not did:
            continue
        score = count_nonempty(row)
        if did not in seen:
            seen[did] = (i, row, score)
        else:
            # Keep whichever row has more data; delete the other
            existing_i, existing_row, existing_score = seen[did]
            if score > existing_score:
                # New row is richer — delete the old one, keep new
                to_delete.append(existing_i)
                seen[did] = (i, row, score)
                print(f"  {did}: keeping row {i} ({score} fields), deleting row {existing_i} ({existing_score} fields)")
            else:
                # Existing is richer or equal — delete new
                to_delete.append(i)
                print(f"  {did}: keeping row {existing_i} ({existing_score} fields), deleting row {i} ({score} fields)")

    print(f"  Found {len(to_delete)} duplicate rows to remove.")
    if to_delete and APPLY:
        deleted = delete_rows(ws, to_delete)
        print(f"  ✓ Deleted {deleted} duplicate rows.")
    elif to_delete:
        print(f"  [DRY RUN] Would delete {len(to_delete)} rows.")
    else:
        print(f"  ✓ No duplicates found.")

    return len(to_delete)


def fix_ingredient_details_duplicates(ss):
    """Remove duplicate (Dish_ID + Ingredient) rows from Ingredient Details."""
    print("\n── Ingredient Details — Duplicate Dish_ID + Ingredient ──")
    ws         = ss.worksheet("Ingredient Details")
    all_values = ws.get_all_values()
    headers    = [h.strip() for h in all_values[0]]
    did_col    = col_idx(headers, "Dish_ID")
    ing_col    = col_idx(headers, "Ingredient")

    seen      = set()
    to_delete = []

    for i, row in enumerate(all_values[1:], start=2):
        did = cell(row, did_col)
        ing = cell(row, ing_col).lower()
        if not did or not ing:
            continue
        key = (did, ing)
        if key in seen:
            to_delete.append(i)
            print(f"  Duplicate row {i}: {did} / {cell(row, ing_col)}")
        else:
            seen.add(key)

    print(f"  Found {len(to_delete)} duplicate rows to remove.")
    if to_delete and APPLY:
        deleted = delete_rows(ws, to_delete)
        print(f"  ✓ Deleted {deleted} duplicate rows.")
    elif to_delete:
        print(f"  [DRY RUN] Would delete {len(to_delete)} rows.")
    else:
        print(f"  ✓ No duplicates found.")

    return len(to_delete)


def report_orphaned_ingredients(ss):
    """Report orphaned ingredient rows — do not delete automatically."""
    print("\n── Ingredient Details — Orphaned Dish_IDs ──")
    ing_ws     = ss.worksheet("Ingredient Details")
    ing_vals   = ing_ws.get_all_values()
    ing_hdrs   = [h.strip() for h in ing_vals[0]]
    did_col    = col_idx(ing_hdrs, "Dish_ID")
    ing_col    = col_idx(ing_hdrs, "Ingredient")

    dl_ws      = ss.worksheet("Goldpan Dish Level Data")
    dl_vals    = dl_ws.get_all_values()
    dl_hdrs    = [h.strip() for h in dl_vals[0]]
    dl_did_col = col_idx(dl_hdrs, "Dish_ID")
    valid_dids = {cell(r, dl_did_col) for r in dl_vals[1:] if cell(r, dl_did_col)}

    orphans = {}
    for i, row in enumerate(ing_vals[1:], start=2):
        did = cell(row, did_col)
        ing = cell(row, ing_col)
        if did and did not in valid_dids:
            orphans.setdefault(did, []).append((i, ing))

    if orphans:
        print(f"  ⚠ {sum(len(v) for v in orphans.values())} orphaned rows across {len(orphans)} Dish_ID(s):")
        for did, rows in sorted(orphans.items()):
            print(f"    {did} ({len(rows)} row(s)) — ingredients: {', '.join(ing for _, ing in rows[:5])}")
        print()
        print("  These Dish_IDs do not exist in Goldpan Dish Level Data.")
        print("  Options:")
        print("    a) If the dish was deleted — delete these ingredient rows manually.")
        print("    b) If the dish was never added — add it to Dish Level Data first,")
        print("       then run backfill_ingredient_details.py.")
        print("  NOT automatically deleted — manual decision required.")
    else:
        print("  ✓ No orphaned ingredient rows.")

    return orphans


def fix_blank_status(ss):
    """Backfill Status = 'Active' for Dish Level Data rows where Status is blank."""
    print("\n── Goldpan Dish Level Data — Blank Status ──")
    ws         = ss.worksheet("Goldpan Dish Level Data")
    all_values = ws.get_all_values()
    headers    = [h.strip() for h in all_values[0]]
    did_col    = col_idx(headers, "Dish_ID")
    status_col = col_idx(headers, "Status")

    if status_col is None:
        print("  ERROR: Status column not found.")
        return 0

    updates   = []
    blank_rows = []

    for i, row in enumerate(all_values[1:], start=2):
        did    = cell(row, did_col)
        status = cell(row, status_col)
        if not status:
            blank_rows.append((i, did))
            cell_ref = gspread.utils.rowcol_to_a1(i, status_col + 1)
            updates.append({"range": cell_ref, "values": [["Active"]]})

    print(f"  Found {len(blank_rows)} rows with blank Status.")
    if blank_rows[:5]:
        print(f"  Sample: {[did for _, did in blank_rows[:5]]}")

    if updates and APPLY:
        # Batch in chunks of 500
        for start in range(0, len(updates), 500):
            ws.batch_update(updates[start:start + 500])
        print(f"  ✓ Set Status = 'Active' on {len(updates)} rows.")
    elif updates:
        print(f"  [DRY RUN] Would set Status = 'Active' on {len(updates)} rows.")
    else:
        print("  ✓ All rows have Status populated.")

    return len(updates)


def main():
    print(f"fix_database_errors.py  —  {TODAY}")
    print("MODE: " + ("APPLY" if APPLY else "DRY RUN — run with --apply to write changes"))

    print("\nConnecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    dl_dupes  = fix_dish_level_data_duplicates(ss)
    ing_dupes = fix_ingredient_details_duplicates(ss)
    orphans   = report_orphaned_ingredients(ss)
    status_fixed = fix_blank_status(ss)

    print("\n" + "=" * 55)
    print("SUMMARY")
    print("=" * 55)
    print(f"  Dish Level Data duplicate rows     : {dl_dupes}")
    print(f"  Ingredient Details duplicate rows  : {ing_dupes}")
    print(f"  Orphaned ingredient Dish_IDs       : {len(orphans)} (manual review required)")
    print(f"  Blank Status rows backfilled       : {status_fixed}")

    if not APPLY:
        print()
        print("  Run with --apply to apply all fixes.")
        print("  Orphaned rows will NOT be auto-deleted regardless of --apply.")
    else:
        print()
        print("  Done. Run validate_database.py to confirm PASS.")


if __name__ == "__main__":
    main()
