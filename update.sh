#!/bin/bash
set -e
cd ~/goldpan
python3 fetch_dishes.py
git add dishes.json restaurants.json
if git diff --cached --quiet; then
  echo "Nothing changed — dishes.json already up to date."
else
  git commit -m "data: update dishes $(date '+%Y-%m-%d')"
  git push
fi
