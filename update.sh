#!/bin/bash
set -e
cd ~/goldpan

# ── Step 1: Validate database before touching anything ────────────────────────
echo "Running database validation..."
if ! python3 validate_database.py; then
  echo ""
  echo "=================================================="
  echo "  UPDATE BLOCKED — database validation FAILED."
  echo "  Review validation_report.txt for details."
  echo "  Fix all blocking errors before running update.sh."
  echo "=================================================="
  exit 1
fi

echo ""
echo "Validation passed. Building..."

# ── Step 2: Regenerate public JSON from Google Sheets ─────────────────────────
python3 fetch_dishes.py
python3 fetch_filters.py

# ── Step 3: Commit and push if anything changed ───────────────────────────────
git add dishes.json restaurants.json filters.json
if git diff --cached --quiet; then
  echo "Nothing changed — data already up to date."
else
  git commit -m "data: update dishes + filters $(date '+%Y-%m-%d')"
  git push
fi
