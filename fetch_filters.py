"""
fetch_filters.py — Reads the Filter Catalog tab from Google Sheets and writes
filters.json to the repo root. Only Active=TRUE rows are included.

filters.json is loaded by discover/index.html to render filter buttons
dynamically — flip Active to TRUE in the sheet and run this script (or
bash update.sh) to surface a new filter on the site.

Usage:
    python3 fetch_filters.py

Output: filters.json
"""

import json
import os
import datetime
import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TAB_NAME       = "Filter Catalog"
OUTPUT_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "filters.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Column names expected in the sheet
COL_TAG_ID   = "Tag_ID"
COL_LABEL    = "Label"
COL_CATEGORY = "Category"
COL_DEF      = "Definition"
COL_VERIFY   = "Requires_Verification"
COL_ACTIVE   = "Active"
COL_PRIORITY = "Priority"
COL_NOTES    = "Notes"


def main():
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ws     = client.open_by_key(SPREADSHEET_ID).worksheet(TAB_NAME)

    print(f"Reading '{TAB_NAME}'...")
    rows    = ws.get_all_records()
    active  = [r for r in rows if str(r.get(COL_ACTIVE, "")).strip().upper() == "TRUE"]

    print(f"  {len(rows)} total tags, {len(active)} active")

    # Group by category, preserving order
    categories = {}
    for r in active:
        cat = r.get(COL_CATEGORY, "Other").strip()
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({
            "id":                   r.get(COL_TAG_ID,   "").strip(),
            "label":                r.get(COL_LABEL,    "").strip(),
            "definition":           r.get(COL_DEF,      "").strip(),
            "requires_verification": str(r.get(COL_VERIFY, "")).strip().upper() == "TRUE",
            "priority":             r.get(COL_PRIORITY, ""),
        })

    output = {
        "updated":      datetime.date.today().isoformat(),
        "total_active": len(active),
        "categories": [
            {"name": cat, "filters": filters}
            for cat, filters in categories.items()
        ],
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"✅ Wrote {len(active)} active filters to filters.json")
    for cat, filters in categories.items():
        print(f"   {cat}: {len(filters)} filter(s)")


if __name__ == "__main__":
    main()
