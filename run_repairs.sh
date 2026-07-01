#!/bin/bash
# run_repairs.sh — GoldPan database repair sequence
# Run this once to fix all errors identified in the 2026-06-28 System Inspection.
# It is safe to re-run. Each script is idempotent or reports what it would do.
#
# Usage:
#   bash run_repairs.sh           # dry run — no writes (default)
#   bash run_repairs.sh --apply   # apply all repairs
#
# After a successful --apply run, validate_database.py should return PASS.

set -e
cd ~/goldpan

APPLY_FLAG=""
if [[ "$1" == "--apply" ]]; then
  APPLY_FLAG="--apply"
  echo "=================================================="
  echo "  APPLYING all database repairs"
  echo "=================================================="
else
  echo "=================================================="
  echo "  DRY RUN — no writes will be made"
  echo "  Pass --apply to execute repairs"
  echo "=================================================="
fi

echo ""

# ── Step 1: Fix header whitespace (idempotent — safe to run) ─────────────────
echo "[ 1/6 ] fix_header_whitespace.py"
python3 fix_header_whitespace.py
echo ""

# ── Step 2: Fix shifted ingredient rows (if any remain) ──────────────────────
echo "[ 2/6 ] fix_shifted_ingredient_rows.py"
if [[ -n "$APPLY_FLAG" ]]; then
  python3 fix_shifted_ingredient_rows.py --apply
else
  python3 fix_shifted_ingredient_rows.py
fi
echo ""

# ── Step 3: Resolve orphaned Dish_IDs ────────────────────────────────────────
# D008 → delete (off menu), D113/D116/D121 → restore in Dish Level Data
echo "[ 3/6 ] resolve_orphans.py"
if [[ -n "$APPLY_FLAG" ]]; then
  python3 resolve_orphans.py --apply
else
  python3 resolve_orphans.py
fi
echo ""

# ── Step 4: Fix database errors ───────────────────────────────────────────────
# Deduplicates DLD rows, backfills blank Status → Active,
# deduplicates ingredient rows, reports any remaining orphans
echo "[ 4/6 ] fix_database_errors.py"
if [[ -n "$APPLY_FLAG" ]]; then
  python3 fix_database_errors.py --apply
else
  python3 fix_database_errors.py
fi
echo ""

# ── Step 5: Dedup Transparency Scoring and Dish Level Data ───────────────────
echo "[ 5/6 ] dedup_tabs.py"
if [[ -n "$APPLY_FLAG" ]]; then
  python3 dedup_tabs.py
else
  python3 dedup_tabs.py --dry-run
fi
echo ""

# ── Step 6: Backfill sparse ingredient rows ───────────────────────────────────
# After resolve_orphans restores D113/D116/D121, their ingredient rows
# are sparse (missing Restaurant_ID, Restaurant_Name, etc). Backfill them.
echo "[ 6/6 ] backfill_ingredient_details.py"
if [[ -n "$APPLY_FLAG" ]]; then
  python3 backfill_ingredient_details.py
else
  python3 backfill_ingredient_details.py --dry-run
fi
echo ""

# ── Final validation ──────────────────────────────────────────────────────────
echo "=================================================="
echo "  Running validate_database.py..."
echo "=================================================="
python3 validate_database.py

echo ""
echo "Full report written to validation_report.txt"
echo "If status is PASS above, the database is clean."
echo "If status is FAIL, review validation_report.txt and fix remaining errors."
