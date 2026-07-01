"""
analyze_enrichment.py — Ingredient Details Data Richness Report

Reads Ingredient Details from Google Sheets and produces a richness report
that distinguishes between:

  • blank          — UNPROCESSED. Row has not been reviewed. This is a gap.
  • "None"         — Reviewed. No value applies / no allergen present.
  • "Unknown"      — Reviewed. Source was checked; value could not be determined.
  • "N/A"          — Reviewed. Field does not apply to this ingredient.
  • (other value)  — Reviewed. A real, source-backed verified value.

Policy (per INGREDIENT_ENRICHMENT_RULES.md):
  After a row is processed, no enrichment field should be blank.
  Blank means unprocessed — it is a completeness gap, not an acceptable
  final state.

  Do NOT infer enrichment fields. Only populate from verified sources:
  live menu, official allergen/nutrition PDFs, restaurant website, or
  direct restaurant confirmation.

This script is READ-ONLY. It writes no changes to Google Sheets.

Enrichment fields audited:
  Cut_Type | Preparation | Ingredient_Type | Status |
  Version  | Ingredient_Source | Allergen_Flags | Component_Role

Output:
  enrichment_report.json  — full row-level detail for every row with gaps
  stdout                  — summary tables

Usage:
    python3 analyze_enrichment.py
"""

import json
import datetime
import os
import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "service_account.json")
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
OUTPUT_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "enrichment_report.json")
TODAY          = datetime.date.today().isoformat()

REQUIRED_FIELDS = [
    "Restaurant_ID", "Restaurant_Name", "Location",
    "Dish_ID", "Dish_Name", "Ingredient",
]

ENRICHMENT_FIELDS = [
    "Cut_Type", "Preparation", "Ingredient_Type", "Status",
    "Version", "Ingredient_Source", "Allergen_Flags", "Component_Role",
]

CANONICAL_HEADERS = REQUIRED_FIELDS + ENRICHMENT_FIELDS

# After review, these values indicate a deliberate reviewed state — NOT gaps.
# Case-insensitive comparison used below.
REVIEWED_STATES = {"none", "unknown", "n/a", "na"}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def col_index(headers, name):
    try:
        return headers.index(name)
    except ValueError:
        return None


def get_val(row, idx):
    if idx is None or idx >= len(row):
        return ""
    return row[idx].strip()


def classify_field(value):
    """
    Classify an enrichment field value:
      'blank'            — empty string; row has not been processed
      'reviewed_none'    — 'None'; verified no value applies
      'reviewed_unknown' — 'Unknown'; source checked, value not determined
      'reviewed_na'      — 'N/A'; field does not apply to this ingredient
      'verified'         — any other non-empty value; source-backed
    """
    v = value.strip()
    if not v:
        return "blank"
    vl = v.lower()
    if vl == "none":
        return "reviewed_none"
    if vl == "unknown":
        return "reviewed_unknown"
    if vl in ("n/a", "na"):
        return "reviewed_na"
    return "verified"


def is_reviewed(classification):
    """Return True if classification represents any reviewed state (not blank)."""
    return classification != "blank"


def classify_source(source_value):
    v = source_value.lower().strip()
    if v in ("menu", "pdf", "website", "restaurant_confirmation"):
        return "verified"
    if v == "inferred":
        return "inferred"
    if v == "unknown":
        return "reviewed_unknown"
    return "blank"


def main():
    print(f"analyze_enrichment.py — Data Richness Report  —  {TODAY}")
    print("Connecting to Google Sheets...")

    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    print("Reading Ingredient Details...")
    ing_ws     = ss.worksheet("Ingredient Details")
    all_values = ing_ws.get_all_values()

    if len(all_values) < 2:
        print("ERROR: Ingredient Details is empty or header-only.")
        return

    headers = [h.strip() for h in all_values[0]]
    col = {h: col_index(headers, h) for h in CANONICAL_HEADERS}

    total_rows = len(all_values) - 1

    # ── Per-field classification counters ─────────────────────────────────────
    field_counts = {
        f: {"verified": 0, "reviewed_none": 0, "reviewed_unknown": 0,
            "reviewed_na": 0, "blank": 0}
        for f in ENRICHMENT_FIELDS
    }

    # ── Row-level tracking ─────────────────────────────────────────────────────
    rows_fully_processed  = 0   # no blank fields
    rows_with_gaps        = []  # at least one blank field

    rest_stats = {}   # rname -> stats dict
    source_class_counts = {"verified": 0, "inferred": 0, "reviewed_unknown": 0, "blank": 0}

    for i, row in enumerate(all_values[1:], start=2):
        rname = get_val(row, col["Restaurant_Name"]) or "(unknown)"
        did   = get_val(row, col["Dish_ID"])
        dname = get_val(row, col["Dish_Name"])
        ing   = get_val(row, col["Ingredient"])
        src   = get_val(row, col["Ingredient_Source"])

        if rname not in rest_stats:
            rest_stats[rname] = {
                "total_rows": 0,
                "fully_processed": 0,
                "rows_with_gaps": 0,
                "blank_field_count": 0,
                "dishes_with_gaps": set(),
            }
        rest_stats[rname]["total_rows"] += 1

        # Classify Ingredient_Source for provenance breakdown
        src_cls = classify_source(src)
        source_class_counts[src_cls] = source_class_counts.get(src_cls, 0) + 1

        row_detail = {
            "sheet_row":       i,
            "Dish_ID":         did,
            "Dish_Name":       dname,
            "Restaurant_Name": rname,
            "Ingredient":      ing,
            "Ingredient_Source": src,
            "source_class":    src_cls,
            "fields": {},
            "blank_fields":    [],
        }

        row_has_blank = False
        for field in ENRICHMENT_FIELDS:
            val = get_val(row, col[field])
            cls = classify_field(val)
            field_counts[field][cls] += 1
            row_detail["fields"][field] = {"value": val, "classification": cls}
            if cls == "blank":
                row_detail["blank_fields"].append(field)
                row_has_blank = True

        if row_has_blank:
            rows_with_gaps.append(row_detail)
            rest_stats[rname]["rows_with_gaps"] += 1
            rest_stats[rname]["blank_field_count"] += len(row_detail["blank_fields"])
            rest_stats[rname]["dishes_with_gaps"].add(did)
        else:
            rows_fully_processed += 1
            rest_stats[rname]["fully_processed"] += 1

    # ── stdout report ─────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print(f"INGREDIENT DETAILS DATA RICHNESS REPORT  —  {TODAY}")
    print(f"{'='*72}")
    print(f"Total ingredient rows      : {total_rows}")
    print(f"Fully processed (no blanks): {rows_fully_processed}")
    print(f"Rows with blank gaps       : {len(rows_with_gaps)}")
    print()
    print("Field value key:")
    print("  verified         = source-backed value (e.g. 'sauce', 'grilled', 'Active')")
    print("  None             = reviewed — no value applies / no allergen present")
    print("  Unknown          = reviewed — source checked, value not determined")
    print("  N/A              = reviewed — field does not apply to this ingredient")
    print("  blank            = UNPROCESSED — completeness gap")
    print()

    # Field breakdown table
    hdr = f"{'Field':<22}  {'Verified':>9}  {'None':>7}  {'Unknown':>9}  {'N/A':>7}  {'BLANK':>7}"
    print(hdr)
    print("─" * len(hdr))
    for f in ENRICHMENT_FIELDS:
        c = field_counts[f]
        blank_flag = " ◄" if c["blank"] > 0 else ""
        print(f"  {f:<20}  {c['verified']:>9}  {c['reviewed_none']:>7}  "
              f"{c['reviewed_unknown']:>9}  {c['reviewed_na']:>7}  "
              f"{c['blank']:>7}{blank_flag}")

    total_blanks = sum(field_counts[f]["blank"] for f in ENRICHMENT_FIELDS)
    print(f"\n  Total blank field slots: {total_blanks} across {len(rows_with_gaps)} rows")

    # Source provenance
    print()
    print("Ingredient_Source provenance:")
    labels = {
        "verified":        "verified (menu/pdf/website/confirmation)",
        "inferred":        "inferred (not source-backed)",
        "reviewed_unknown": "Unknown (reviewed, source not recorded)",
        "blank":           "blank (unprocessed)",
    }
    for cls, cnt in source_class_counts.items():
        if cnt:
            pct = cnt / total_rows * 100
            print(f"  {labels.get(cls, cls):<45}: {cnt:>4}  ({pct:.1f}%)")

    # Restaurant breakdown (only those with gaps)
    gaps_exist = [(rn, st) for rn, st in rest_stats.items() if st["rows_with_gaps"] > 0]
    if gaps_exist:
        print()
        print(f"{'Restaurant':<38}  {'Rows':>5}  {'Processed':>9}  {'Gap rows':>8}  {'Blank slots':>11}")
        print("─" * 78)
        for rname, st in sorted(gaps_exist, key=lambda x: -x[1]["rows_with_gaps"]):
            print(f"  {rname:<36}  {st['total_rows']:>5}  {st['fully_processed']:>9}  "
                  f"{st['rows_with_gaps']:>8}  {st['blank_field_count']:>11}")

    # ── Gap analysis ──────────────────────────────────────────────────────────
    print()
    print(f"{'='*72}")
    print("GAP ANALYSIS — how to resolve blank fields")
    print(f"{'='*72}")
    print()

    gap_guidance = {
        "Status":           ("Safe default",   "Set 'Active' if parent dish is Active. Not source-dependent."),
        "Version":          ("Safe default",   "Set '1' for initial schema version. Not source-dependent."),
        "Ingredient_Source":("Provenance",     "Must reflect actual collection method. Set 'Unknown' if source was not recorded."),
        "Cut_Type":         ("Source doc",     "Live menu or PDF only. If reviewed and not stated, set 'Unknown'. If not applicable, set 'N/A'."),
        "Preparation":      ("Source doc",     "Live menu or PDF only. If reviewed and not stated, set 'Unknown'. If not applicable, set 'N/A'."),
        "Ingredient_Type":  ("Source doc",     "Live menu + ingredient name, only if unambiguous. Set 'Unknown' if reviewed but unclear."),
        "Allergen_Flags":   ("Source doc ⚠",  "Official allergen PDF or restaurant confirmation only. Set 'Unknown' until reviewed. Never guess."),
        "Component_Role":   ("Source doc",     "Live menu structure only. Set 'N/A' if not a sauce/base/topping/etc. Set 'Unknown' if unclear."),
    }

    for field in ENRICHMENT_FIELDS:
        cnt = field_counts[field]["blank"]
        if cnt:
            category, guidance = gap_guidance[field]
            print(f"  {field} — {cnt} blank  [{category}]")
            print(f"    {guidance}")
            print()

    # ── JSON output ───────────────────────────────────────────────────────────
    for rn in rest_stats:
        rest_stats[rn]["dishes_with_gaps"] = sorted(rest_stats[rn]["dishes_with_gaps"])

    report = {
        "generated":               TODAY,
        "total_data_rows":         total_rows,
        "rows_fully_processed":    rows_fully_processed,
        "rows_with_blank_gaps":    len(rows_with_gaps),
        "total_blank_field_slots": total_blanks,
        "field_classification":    field_counts,
        "source_provenance":       source_class_counts,
        "gaps_by_restaurant": {
            rn: {
                "total_rows":        st["total_rows"],
                "fully_processed":   st["fully_processed"],
                "rows_with_gaps":    st["rows_with_gaps"],
                "blank_field_count": st["blank_field_count"],
                "dishes_with_gaps":  st["dishes_with_gaps"],
            }
            for rn, st in rest_stats.items()
        },
        "rows_with_gaps": rows_with_gaps,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Full row-level detail saved to: enrichment_report.json")
    print(f"({len(rows_with_gaps)} rows with blank gaps, {total_blanks} total blank field slots)")
    print()


if __name__ == "__main__":
    main()
