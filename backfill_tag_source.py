"""
backfill_tag_source.py — Apply confirmed Tag_Source values to Goldpan Dish Level Data.

Reads confirmed Tag_Source classifications from the audit (GP-RULE-013 Phase 2A)
and writes them to the Tag_Source column in the GDL sheet.

Only applies CONFIRMED assignments (those with sufficient evidence per the audit).
PROBABLE and NEEDS_VERIFICATION assignments are not touched.

Usage:
    python3 backfill_tag_source.py                 # dry run — show what would change
    python3 backfill_tag_source.py --apply         # write to sheet

Evidence classes applied:
    goldpan_inferred   — high-protein / gluten-friendly tags (GoldPan analytical conclusions)
    restaurant_disclosed — Slutty Vegan brand identity + dishes with explicit opts text in staging
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
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
GDL_TAB        = "Goldpan Dish Level Data"
TODAY          = datetime.date.today().isoformat()
DRY_RUN        = "--apply" not in sys.argv

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ── Confirmed Tag_Source assignments (GP-RULE-013 Phase 2A audit) ─────────────
#
# Evidence basis:
#   goldpan_inferred  — tag is 'high-protein' or 'gluten-friendly':
#                       GoldPan analytical classification; no restaurant labels dishes this way
#   restaurant_disclosed — either:
#       (a) Slutty Vegan: brand identity; all dishes are vegan by design
#       (b) staging dietary_options recorded explicit restaurant disclosure language

CONFIRMED_ASSIGNMENTS: dict[str, str] = {
    "D004": "goldpan_inferred",
    "D010": "goldpan_inferred",
    "D025": "goldpan_inferred",
    "D028": "restaurant_disclosed",
    "D030": "restaurant_disclosed",
    "D032": "restaurant_disclosed",
    "D033": "goldpan_inferred",
    "D034": "goldpan_inferred",
    "D035": "goldpan_inferred",
    "D036": "goldpan_inferred",
    "D037": "goldpan_inferred",
    "D040": "goldpan_inferred",
    "D041": "goldpan_inferred",
    "D043": "goldpan_inferred",
    "D050": "goldpan_inferred",
    "D054": "goldpan_inferred",
    "D055": "goldpan_inferred",
    "D056": "goldpan_inferred",
    "D058": "goldpan_inferred",
    "D059": "goldpan_inferred",
    "D060": "goldpan_inferred",
    "D062": "goldpan_inferred",
    "D063": "goldpan_inferred",
    "D070": "goldpan_inferred",
    "D136": "goldpan_inferred",
    "D137": "goldpan_inferred",
    "D139": "goldpan_inferred",
    "D141": "goldpan_inferred",
    "D144": "goldpan_inferred",
    "D145": "goldpan_inferred",
    "D146": "goldpan_inferred",
    "D147": "goldpan_inferred",
    "D148": "goldpan_inferred",
    "D149": "goldpan_inferred",
    "D154": "goldpan_inferred",
    "D156": "goldpan_inferred",
    "D160": "goldpan_inferred",
    "D162": "goldpan_inferred",
    "D164": "goldpan_inferred",
    "D166": "goldpan_inferred",
    "D168": "goldpan_inferred",
    "D170": "goldpan_inferred",
    "D172": "goldpan_inferred",
    "D201": "goldpan_inferred",
    "D206": "goldpan_inferred",
    "D207": "goldpan_inferred",
    "D208": "goldpan_inferred",
    "D209": "goldpan_inferred",
    "D212": "goldpan_inferred",
    "D217": "goldpan_inferred",
    "D219": "goldpan_inferred",
    "D258": "goldpan_inferred",
    "D263": "goldpan_inferred",
    "D265": "goldpan_inferred",
    "D270": "goldpan_inferred",
    "D271": "goldpan_inferred",
    "D280": "goldpan_inferred",
    "D281": "goldpan_inferred",
    "D282": "goldpan_inferred",
    "D283": "goldpan_inferred",
    "D285": "goldpan_inferred",
    "D290": "restaurant_disclosed",
    "D292": "restaurant_disclosed",
    "D293": "restaurant_disclosed",
    "D294": "restaurant_disclosed",
    "D295": "restaurant_disclosed",
    "D296": "restaurant_disclosed",
    "D297": "restaurant_disclosed",
    "D298": "restaurant_disclosed",
    "D299": "restaurant_disclosed",
    "D300": "restaurant_disclosed",
    "D301": "restaurant_disclosed",
    "D302": "restaurant_disclosed",
    "D303": "restaurant_disclosed",
    "D304": "restaurant_disclosed",
    "D305": "restaurant_disclosed",
    "D306": "restaurant_disclosed",
    "D307": "goldpan_inferred",
    "D308": "goldpan_inferred",
    "D309": "restaurant_disclosed",
    "D311": "restaurant_disclosed",
    "D312": "restaurant_disclosed",
    "D313": "restaurant_disclosed",
    "D314": "restaurant_disclosed",
    "D315": "restaurant_disclosed",
    "D318": "restaurant_disclosed",
    "D319": "restaurant_disclosed",
    "D320": "restaurant_disclosed",
    "D321": "restaurant_disclosed",
    "D322": "restaurant_disclosed",
    "D323": "restaurant_disclosed",
    "D324": "restaurant_disclosed",
    "D325": "restaurant_disclosed",
    "D326": "restaurant_disclosed",
    "D327": "restaurant_disclosed",
    "D328": "goldpan_inferred",
    "D329": "goldpan_inferred",
    "D330": "goldpan_inferred",
    "D331": "goldpan_inferred",
    "D332": "restaurant_disclosed",
    "D333": "goldpan_inferred",
    "D334": "goldpan_inferred",
    "D335": "goldpan_inferred",
    "D336": "goldpan_inferred",
    "D337": "restaurant_disclosed",
    "D338": "goldpan_inferred",
    "D339": "goldpan_inferred",
    "D340": "goldpan_inferred",
    "D341": "restaurant_disclosed",
    "D342": "restaurant_disclosed",
    "D343": "goldpan_inferred",
    "D344": "restaurant_disclosed",
    "D345": "restaurant_disclosed",
    "D346": "restaurant_disclosed",
    "D347": "restaurant_disclosed",
    "D348": "restaurant_disclosed",
    "D349": "restaurant_disclosed",
    "D363": "restaurant_disclosed",
    "D367": "restaurant_disclosed",
    "D368": "restaurant_disclosed",
    "D370": "restaurant_disclosed",
    "D399": "restaurant_disclosed",
    "D419": "restaurant_disclosed",
    "D420": "restaurant_disclosed",
    "D421": "restaurant_disclosed",
    "D422": "restaurant_disclosed",
    "D423": "restaurant_disclosed",
    "D424": "restaurant_disclosed",
    "D425": "restaurant_disclosed",
    "D426": "restaurant_disclosed",
    "D427": "restaurant_disclosed",
    "D428": "restaurant_disclosed",
    "D429": "restaurant_disclosed",
    "D430": "restaurant_disclosed",
    "D431": "restaurant_disclosed",
    "D432": "restaurant_disclosed",
    "D433": "restaurant_disclosed",
    "D434": "restaurant_disclosed",
    "D435": "goldpan_inferred",
    "D436": "restaurant_disclosed",
    "D437": "restaurant_disclosed",
    "D438": "goldpan_inferred",
    "D440": "restaurant_disclosed",
    "D441": "restaurant_disclosed",
    "D442": "restaurant_disclosed",
    "D443": "restaurant_disclosed",
    "D445": "goldpan_inferred",
    "D447": "goldpan_inferred",
    "D448": "goldpan_inferred",
    "D449": "goldpan_inferred",
    "D450": "goldpan_inferred",
    "D451": "goldpan_inferred",
    "D452": "goldpan_inferred",
    "D453": "goldpan_inferred",
    "D454": "goldpan_inferred",
    "D455": "goldpan_inferred",
    "D456": "restaurant_disclosed",
    "D457": "goldpan_inferred",
    "D458": "goldpan_inferred",
    "D462": "goldpan_inferred",
    "D466": "goldpan_inferred",
    "D474": "restaurant_disclosed",
    "D475": "goldpan_inferred",
    "D477": "goldpan_inferred",
    "D480": "goldpan_inferred",
    "D483": "goldpan_inferred",
    "D484": "goldpan_inferred",
    "D485": "goldpan_inferred",
    "D487": "goldpan_inferred",
    "D489": "goldpan_inferred",
    "D490": "goldpan_inferred",
    "D491": "goldpan_inferred",
    "D507": "restaurant_disclosed",
    "D510": "goldpan_inferred",
    "D512": "restaurant_disclosed",
    "D514": "goldpan_inferred",
    "D515": "goldpan_inferred",
    "D516": "goldpan_inferred",
    "D517": "goldpan_inferred",
    "D518": "goldpan_inferred",
    "D519": "goldpan_inferred",
    "D520": "restaurant_disclosed",
    "D521": "restaurant_disclosed",
    "D522": "restaurant_disclosed",
    "D523": "restaurant_disclosed",
    "D524": "goldpan_inferred",
    "D525": "goldpan_inferred",
    "D526": "goldpan_inferred",
    "D527": "restaurant_disclosed",
    "D533": "goldpan_inferred",
    "D534": "goldpan_inferred",
    "D535": "goldpan_inferred",
    "D536": "goldpan_inferred",
    "D537": "goldpan_inferred",
    "D538": "goldpan_inferred",
    "D540": "goldpan_inferred",
    "D541": "goldpan_inferred",
    "D543": "goldpan_inferred",
    "D546": "goldpan_inferred",
    "D547": "goldpan_inferred",
    "D549": "goldpan_inferred",
    "D551": "goldpan_inferred",
    "D553": "goldpan_inferred",
    "D554": "goldpan_inferred",
    "D563": "goldpan_inferred",
    "D567": "goldpan_inferred",
    "D572": "goldpan_inferred",
    "D615": "goldpan_inferred",
    "D621": "goldpan_inferred",
    "D622": "goldpan_inferred",
    "D623": "goldpan_inferred",
    "D624": "goldpan_inferred",
    "D625": "goldpan_inferred",
    "D628": "goldpan_inferred",
    "D629": "goldpan_inferred",
    "D630": "goldpan_inferred",
    "D631": "goldpan_inferred",
    "D632": "goldpan_inferred",
    "D633": "goldpan_inferred",
    "D634": "goldpan_inferred",
    "D635": "goldpan_inferred",
    "D636": "goldpan_inferred",
    "D637": "goldpan_inferred",
    "D640": "goldpan_inferred",
    "D641": "goldpan_inferred",
    "D642": "goldpan_inferred",
    "D643": "goldpan_inferred",
    "D644": "goldpan_inferred",
    "D645": "goldpan_inferred",
    "D651": "goldpan_inferred",
    "D652": "goldpan_inferred",
    "D654": "goldpan_inferred",
    "D655": "goldpan_inferred",
    "D658": "goldpan_inferred",
    "D661": "goldpan_inferred",
    "D662": "goldpan_inferred",
    "D663": "goldpan_inferred",
    "D664": "goldpan_inferred",
    "D679": "goldpan_inferred",
    "D681": "restaurant_disclosed",
    "D682": "restaurant_disclosed",
    "D683": "restaurant_disclosed",
    "D684": "restaurant_disclosed",
    "D685": "restaurant_disclosed",
    "D686": "goldpan_inferred",
    "D688": "goldpan_inferred",
    "D693": "goldpan_inferred",
    "D696": "goldpan_inferred",
    "D699": "goldpan_inferred",
    "D700": "goldpan_inferred",
    "D701": "goldpan_inferred",
    "D702": "goldpan_inferred",
    "D704": "goldpan_inferred",
    "D707": "goldpan_inferred",
    "D708": "goldpan_inferred",
    "D713": "goldpan_inferred",
    "D714": "goldpan_inferred",
    "D715": "goldpan_inferred",
    "D716": "goldpan_inferred",
    "D717": "goldpan_inferred",
    "D718": "goldpan_inferred",
    "D719": "goldpan_inferred",
    "D720": "goldpan_inferred",
    "D721": "goldpan_inferred",
    "D722": "goldpan_inferred",
    "D723": "goldpan_inferred",
    "D724": "goldpan_inferred",
    "D725": "goldpan_inferred",
    "D726": "goldpan_inferred",
    "D727": "goldpan_inferred",
    "D731": "goldpan_inferred",
    "D732": "goldpan_inferred",
    "D733": "goldpan_inferred",
    "D734": "goldpan_inferred",
    "D735": "goldpan_inferred",
    "D736": "goldpan_inferred",
    "D741": "restaurant_disclosed",
    "D742": "goldpan_inferred",
    "D745": "goldpan_inferred",
    "D747": "goldpan_inferred",
    "D748": "goldpan_inferred",
    "D749": "goldpan_inferred",
    "D750": "goldpan_inferred",
    "D751": "goldpan_inferred",
    "D752": "goldpan_inferred",
    "D753": "goldpan_inferred",
    "D754": "goldpan_inferred",
    "D755": "goldpan_inferred",
    "D757": "goldpan_inferred",
    "D758": "goldpan_inferred",
    "D759": "goldpan_inferred",
    "D760": "goldpan_inferred",
    "D761": "goldpan_inferred",
    "D762": "goldpan_inferred",
    "D763": "goldpan_inferred",
    "D764": "goldpan_inferred",
    "D765": "goldpan_inferred",
    # ── Phase 2B — newly confirmed restaurant_disclosed (web verification) ────────
    # Abhi Eatery and Bar: menu uses explicit "GF" notation on abhieatery.com
    "D560": "restaurant_disclosed",
    "D561": "restaurant_disclosed",
    "D562": "restaurant_disclosed",
    "D564": "restaurant_disclosed",
    "D565": "restaurant_disclosed",
    "D566": "restaurant_disclosed",
    "D568": "restaurant_disclosed",
    "D569": "restaurant_disclosed",
    "D570": "restaurant_disclosed",
    "D571": "restaurant_disclosed",
    "D573": "restaurant_disclosed",
    "D574": "restaurant_disclosed",
    "D586": "restaurant_disclosed",
    "D601": "restaurant_disclosed",
    "D602": "restaurant_disclosed",
    "D603": "restaurant_disclosed",
    "D604": "restaurant_disclosed",
    "D605": "restaurant_disclosed",
    "D606": "restaurant_disclosed",
    "D607": "restaurant_disclosed",
    "D608": "restaurant_disclosed",
    "D610": "restaurant_disclosed",
    "D613": "restaurant_disclosed",
    "D616": "restaurant_disclosed",
    "D617": "restaurant_disclosed",
    "D618": "restaurant_disclosed",
    "D619": "restaurant_disclosed",
    "D620": "restaurant_disclosed",
    # Blue Root: menu uses GF/DF/V/VG labels; nutrition facts PDF published
    "D386": "restaurant_disclosed",
    "D388": "restaurant_disclosed",
    "D391": "restaurant_disclosed",
    "D395": "restaurant_disclosed",
    "D398": "restaurant_disclosed",
    "D401": "restaurant_disclosed",
    "D403": "restaurant_disclosed",
    "D404": "restaurant_disclosed",
    "D406": "restaurant_disclosed",
    "D407": "restaurant_disclosed",
    "D409": "restaurant_disclosed",
    "D411": "restaurant_disclosed",
    "D412": "restaurant_disclosed",
    "D413": "restaurant_disclosed",
    "D414": "restaurant_disclosed",
    "D417": "restaurant_disclosed",
    # Wasabi Juan's: menu is marked GF per findmeglutenfree, Tripadvisor, atly.com
    "D529": "restaurant_disclosed",
    "D530": "restaurant_disclosed",
    "D532": "restaurant_disclosed",
    "D539": "restaurant_disclosed",
    "D542": "restaurant_disclosed",
    "D544": "restaurant_disclosed",
    "D545": "restaurant_disclosed",
    "D548": "restaurant_disclosed",
    "D550": "restaurant_disclosed",
    "D552": "restaurant_disclosed",
    "D555": "restaurant_disclosed",
    "D556": "restaurant_disclosed",
}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    mode = "DRY RUN — no writes" if DRY_RUN else "APPLY MODE — writing to sheet"
    print(f"\nbackfill_tag_source.py  —  {TODAY}")
    print(f"{'='*65}")
    print(f"  {mode}")
    print(f"  Confirmed assignments: {len(CONFIRMED_ASSIGNMENTS)}")
    gi_count = sum(1 for v in CONFIRMED_ASSIGNMENTS.values() if v == "goldpan_inferred")
    rd_count = sum(1 for v in CONFIRMED_ASSIGNMENTS.values() if v == "restaurant_disclosed")
    print(f"    goldpan_inferred   : {gi_count}")
    print(f"    restaurant_disclosed: {rd_count}")
    print(f"{'='*65}\n")

    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ws     = client.open_by_key(SPREADSHEET_ID).worksheet(GDL_TAB)

    all_values = ws.get_all_values()
    headers    = [h.strip() for h in all_values[0]]

    if "Dish_ID" not in headers or "Tag_Source" not in headers:
        print(f"  ERROR: Required columns missing. Found: {headers}")
        return

    did_col = headers.index("Dish_ID") + 1      # 1-indexed for gspread
    ts_col  = headers.index("Tag_Source") + 1

    print(f"  Dish_ID column : {did_col}   Tag_Source column : {ts_col}")
    print(f"  Total data rows: {len(all_values) - 1}\n")

    # Build cell updates
    updates   = []
    skipped   = []   # already set to correct value
    conflicts = []   # already set but to different value

    for row_idx, row in enumerate(all_values[1:], start=2):
        did = row[did_col - 1].strip() if did_col - 1 < len(row) else ""
        if did not in CONFIRMED_ASSIGNMENTS:
            continue

        current_ts = row[ts_col - 1].strip() if ts_col - 1 < len(row) else ""
        new_ts     = CONFIRMED_ASSIGNMENTS[did]

        if current_ts == new_ts:
            skipped.append((did, current_ts))
        elif current_ts and current_ts != new_ts:
            conflicts.append((did, current_ts, new_ts))
            updates.append(gspread.Cell(row=row_idx, col=ts_col, value=new_ts))
        else:
            updates.append(gspread.Cell(row=row_idx, col=ts_col, value=new_ts))

    print(f"  To write   : {len(updates)} cells")
    print(f"  Already set: {len(skipped)} cells (no change needed)")
    if conflicts:
        print(f"  Conflicts  : {len(conflicts)} (overwriting existing value):")
        for did, old, new in conflicts[:10]:
            print(f"    {did}: '{old}' → '{new}'")

    # Check for dish IDs in CONFIRMED_ASSIGNMENTS not found in the sheet
    found_dids = set()
    for row in all_values[1:]:
        did = row[did_col - 1].strip() if did_col - 1 < len(row) else ""
        if did:
            found_dids.add(did)
    missing = [did for did in CONFIRMED_ASSIGNMENTS if did not in found_dids]
    if missing:
        print(f"\n  WARNING: {len(missing)} dish IDs in assignments not found in sheet: {missing[:5]}")

    if DRY_RUN:
        print(f"\n  DRY RUN — no changes written.")
        print(f"  To apply: python3 backfill_tag_source.py --apply")
        return

    if not updates:
        print(f"\n  Nothing to write — all assigned dishes already have correct Tag_Source.")
        return

    print(f"\n  Writing {len(updates)} cells...")
    # Write in batches of 200 to avoid API limits
    BATCH = 200
    for i in range(0, len(updates), BATCH):
        batch = updates[i:i + BATCH]
        ws.update_cells(batch, value_input_option="USER_ENTERED")
        print(f"    Wrote batch {i//BATCH + 1}: {len(batch)} cells")

    print(f"\n  ✓ Done. {len(updates)} Tag_Source values written.")
    print(f"\n  Next steps:")
    print(f"    python3 pipeline.py --apply          # regenerate dishes.json with tag_source")
    print(f"    python3 validate_database.py --table dish  # check remaining blank warnings")


if __name__ == "__main__":
    main()

