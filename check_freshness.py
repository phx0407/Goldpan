"""
check_freshness.py — GoldPan freshness audit and snapshot writer.

Reads the Menu Source Registry from Google Sheets, computes Recanvass_Status
and Source_Check_Status for every active restaurant, produces a structured
freshness report, and (with --apply) writes the computed snapshot fields back
to the sheet.

This script never modifies ingredient data, scores, claims, or staging files.
It is pure freshness bookkeeping.

Usage:
    python3 check_freshness.py               # dry run — report only
    python3 check_freshness.py --apply       # compute + write snapshot fields
    python3 check_freshness.py --apply --report  # write + save report to docs/

Writes (--apply only):
    Recanvass_Status       ← computed verdict per GP-RULE-008 v1.1
    Status_Computed_Date   ← today (used to detect stale snapshots)

Output:
    Freshness report to stdout (always)
    docs/freshness_report_YYYY-MM-DD.txt (with --report)
"""

import datetime
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

from freshness import (
    compute_freshness_map,
    freshness_summary,
    FreshnessRecord,
    TIER_RECANVASS_WINDOWS,
    TIER_SOURCE_CHECK_WINDOWS,
)

# ── Config ────────────────────────────────────────────────────────────────────

GOLDPAN_DIR    = os.path.dirname(os.path.abspath(__file__))
KEY_FILE       = os.path.join(GOLDPAN_DIR, "service_account.json")
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TODAY          = datetime.date.today().isoformat()
DRY_RUN        = "--apply" not in sys.argv
SAVE_REPORT    = "--report" in sys.argv
REGISTRY_TAB   = "Menu Source Registry"
REPORT_DIR     = os.path.join(GOLDPAN_DIR, "docs")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Columns written back to the sheet on --apply
WRITE_COLUMNS = ["Recanvass_Status", "Status_Computed_Date"]


# ── Sheet helpers ─────────────────────────────────────────────────────────────

def load_registry(ss) -> tuple[list[dict], list[str], gspread.Worksheet]:
    """
    Load the Menu Source Registry tab.
    Returns (rows, headers, worksheet).
    """
    ws   = ss.worksheet(REGISTRY_TAB)
    rows = ws.get_all_values()
    if len(rows) < 2:
        return [], [], ws
    headers = [h.strip() for h in rows[0]]
    records = [
        {headers[i]: (rows[r][i].strip() if i < len(rows[r]) else "")
         for i in range(len(headers))}
        for r in range(1, len(rows))
    ]
    return records, headers, ws


def write_snapshot(
    ws: gspread.Worksheet,
    freshness_map: dict[str, FreshnessRecord],
    headers: list[str],
) -> int:
    """
    Write Recanvass_Status and Status_Computed_Date back to the sheet.

    Uses batch update for efficiency. Skips restaurants not found in the sheet.
    Returns count of rows updated.
    """
    all_values = ws.get_all_values()
    if not all_values:
        return 0

    header_row = [h.strip() for h in all_values[0]]

    # Ensure required columns exist
    missing = [c for c in WRITE_COLUMNS if c not in header_row]
    if missing:
        print(f"  ERROR: Cannot write snapshot — columns missing from sheet: {missing}")
        print(f"         Add these columns to '{REGISTRY_TAB}' first.")
        return 0

    status_col  = header_row.index("Recanvass_Status") + 1    # 1-indexed
    date_col    = header_row.index("Status_Computed_Date") + 1
    rid_col     = header_row.index("Restaurant_ID") + 1 if "Restaurant_ID" in header_row else None

    if not rid_col:
        print("  ERROR: Restaurant_ID column not found in sheet.")
        return 0

    # Build {restaurant_id: row_number} lookup (1-indexed, accounting for header row)
    rid_to_row: dict[str, int] = {}
    for i, row in enumerate(all_values[1:], start=2):
        rid = row[rid_col - 1].strip() if rid_col - 1 < len(row) else ""
        if rid:
            rid_to_row[rid] = i

    # Build batch cell updates
    updates = []
    updated = 0
    for rid, rec in freshness_map.items():
        row_num = rid_to_row.get(rid)
        if row_num is None:
            print(f"  WARNING: {rid} ({rec.restaurant_name}) not found in sheet — skipping")
            continue
        updates.append(
            gspread.Cell(row=row_num, col=status_col, value=rec.status)
        )
        updates.append(
            gspread.Cell(row=row_num, col=date_col, value=rec.computed_date)
        )
        updated += 1

    if updates:
        ws.update_cells(updates)

    return updated


# ── Report formatting ─────────────────────────────────────────────────────────

W = 76   # report width

def _bar(char="─") -> str:
    return char * W

def _header_block(title: str) -> str:
    return f"\n{'═' * W}\n{title:<{W}}\n{'═' * W}"

def _status_icon(status: str) -> str:
    return {
        "ok":          "  ",
        "current":     "  ",
        "due_soon":    "⚠ ",
        "overdue":     "⚠ ",
        "needs_review": "🔴",
        "unknown":     "? ",
        "changed":     "🔴",
        "unreachable": "🔴",
    }.get(status, "  ")


def format_report(
    freshness_map: dict[str, FreshnessRecord],
    summary: dict,
    dry_run: bool,
) -> str:
    lines = []
    mode  = "DRY RUN — snapshot not written" if dry_run else "APPLIED — snapshot written"

    lines.append(_header_block(
        f"DATA FRESHNESS REPORT   Computed: {TODAY}   [{mode}]"
    ))

    # ── Source Check Track ─────────────────────────────────────────────────────
    lines.append(f"\nSOURCE CHECK STATUS (Track A)")
    lines.append(_bar())
    lines.append(
        f"  {'Restaurant':<28} {'Tier':>4}  {'Last Checked':<14}  "
        f"{'Source Status':<14}  Notes"
    )
    lines.append(_bar("─"))

    for rec in sorted(freshness_map.values(), key=lambda r: r.restaurant_name):
        icon  = _status_icon(rec.source_check_status)
        last  = rec.last_source_check or "—"
        notes = ""
        if rec.source_check_status == "overdue":
            notes = f"overdue (window: {rec.source_check_window}d)"
        elif rec.source_check_status == "unknown":
            notes = "never checked"
        elif rec.source_check_status == "changed":
            notes = "→ needs_review"
        elif rec.source_check_status == "unreachable":
            notes = "→ needs_review"

        lines.append(
            f"  {icon}{rec.restaurant_name:<27} {rec.recanvass_tier:>4}  "
            f"{last:<14}  {rec.source_check_status:<14}  {notes}"
        )

    # ── Recanvass Track ───────────────────────────────────────────────────────
    lines.append(f"\nRECANVASS STATUS (Track B — synthesized verdict)")
    lines.append(_bar())
    lines.append(
        f"  {'Restaurant':<28} {'Tier':>4}  {'Last Canvassed':<14}  "
        f"{'Status':<14}  Days"
    )
    lines.append(_bar("─"))

    for rec in sorted(freshness_map.values(), key=lambda r: r.restaurant_name):
        icon   = _status_icon(rec.status)
        last   = rec.last_canvassed or "—"
        if rec.status == "overdue":
            days_note = f"{rec.days_overdue}d overdue"
        elif rec.status in ("current", "due_soon"):
            days_note = f"{rec.days_remaining}d remaining"
        elif rec.status == "needs_review":
            days_note = f"{rec.triggers[0][:40]}..." if rec.triggers else "trigger active"
        else:
            days_note = "—"

        lines.append(
            f"  {icon}{rec.restaurant_name:<27} {rec.recanvass_tier:>4}  "
            f"{last:<14}  {rec.status:<14}  {days_note}"
        )

    # ── Triggers detail ───────────────────────────────────────────────────────
    triggered = [r for r in freshness_map.values() if r.triggers]
    if triggered:
        lines.append(f"\nACTIVE TRIGGERS")
        lines.append(_bar("─"))
        for rec in sorted(triggered, key=lambda r: r.restaurant_name):
            lines.append(f"  {rec.restaurant_name} ({rec.restaurant_id})")
            for t in rec.triggers:
                lines.append(f"    • {t}")

    # ── Summary ───────────────────────────────────────────────────────────────
    lines.append(f"\n{_bar()}")
    lines.append(f"FRESHNESS SUMMARY")
    lines.append(
        f"  current:      {summary['current']:>3} restaurant(s)   "
        f"due_soon: {summary['due_soon']:>3}   "
        f"overdue: {summary['overdue']:>3}   "
        f"needs_review: {summary['needs_review']:>3}"
    )
    lines.append(
        f"\n  Freshness Score: {summary['freshness_score']}%  "
        f"(current + due_soon / total)  "
        f"Target ≥80%: {'✓' if summary['target_met'] else '✗'}"
    )
    nr = summary["needs_review"]
    critical_str = "✓" if summary["critical_ok"] else f"✗ — {nr} active, action required"
    lines.append(f"  Critical (0 needs_review): {critical_str}")

    # Effect on derived filters
    lines.append(f"\nEFFECT ON DERIVED CONCLUSIONS (GP-RULE-008 v1.1 / GP-RULE-009)")
    lines.append(_bar("─"))
    current_r  = summary["current"] + summary["due_soon"]
    overdue_r  = summary["overdue"]
    review_r   = summary["needs_review"]
    total_r    = summary["total"]
    if total_r:
        pct_full   = round(current_r / total_r * 100)
        pct_capped = round(overdue_r / total_r * 100)
        pct_supp   = round(review_r  / total_r * 100)
    else:
        pct_full = pct_capped = pct_supp = 0

    lines.append(
        f"  Full confidence (current/due_soon):          "
        f"{current_r:>3}/{total_r} restaurants  ({pct_full}% of evidence)"
    )
    lines.append(
        f"  Confidence capped at 'likely' (overdue):     "
        f"{overdue_r:>3}/{total_r} restaurants  ({pct_capped}% of evidence)  [GP-RULE-009]"
    )
    lines.append(
        f"  Derived conclusions suppressed (needs_review):"
        f"{review_r:>3}/{total_r} restaurants  ({pct_supp}% of evidence)  [GP-RULE-008]"
    )
    lines.append(_bar("═"))

    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print(f"\ncheck_freshness.py  —  {TODAY}")
    print(f"  Mode: {'DRY RUN' if DRY_RUN else 'APPLY'}")
    print(f"  Connecting to Google Sheets...")

    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    print(f"  Loading {REGISTRY_TAB}...")
    records, headers, ws = load_registry(ss)
    print(f"  {len(records)} restaurant(s) loaded.")

    if not records:
        print("  ERROR: No records found in Menu Source Registry.")
        sys.exit(1)

    print(f"  Computing freshness...")
    freshness_map = compute_freshness_map(records)
    summary       = freshness_summary(freshness_map)

    # ── Report ─────────────────────────────────────────────────────────────────
    report = format_report(freshness_map, summary, DRY_RUN)
    print(report)

    # ── Apply ──────────────────────────────────────────────────────────────────
    if not DRY_RUN:
        print(f"\n  Writing snapshot fields to sheet...")
        updated = write_snapshot(ws, freshness_map, headers)
        print(f"  {updated} restaurant(s) updated: Recanvass_Status + Status_Computed_Date")

    # ── Save report ────────────────────────────────────────────────────────────
    if SAVE_REPORT:
        report_path = os.path.join(REPORT_DIR, f"freshness_report_{TODAY}.txt")
        os.makedirs(REPORT_DIR, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n  Report saved: {report_path}")

    # ── Exit code ──────────────────────────────────────────────────────────────
    if not summary["critical_ok"]:
        print(
            f"\n  ⚠  {summary['needs_review']} restaurant(s) in needs_review. "
            f"Derived conclusions are suppressed for those restaurants' dishes."
        )
        # Not a pipeline-blocking failure — needs_review is an attention signal, not an error.
        # Use --require-fresh in compute_derived_filters.py to enforce blocking if needed.


if __name__ == "__main__":
    main()
