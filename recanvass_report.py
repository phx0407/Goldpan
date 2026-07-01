"""
recanvass_report.py — Weekly Goldpan menu change detector.

Fetches each restaurant's menu URL and checks whether known dish names
still appear on the page. Writes a JSON results file for the scheduled
Cowork task to analyze and present.

Usage:
    python3 recanvass_report.py
    python3 recanvass_report.py --dry-run

Output: recanvass_reports/YYYY-MM-DD.json
"""

import json
import sys
import datetime
import os
import time
import re
import io

try:
    import requests
except ImportError:
    print("Missing: pip install requests --break-system-packages")
    sys.exit(1)

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# ── Config ────────────────────────────────────────────────────────────────────

GOLDPAN_DIR      = os.path.dirname(os.path.abspath(__file__))
DISHES_FILE      = os.path.join(GOLDPAN_DIR, "dishes.json")
RESTAURANTS_FILE = os.path.join(GOLDPAN_DIR, "restaurants.json")
REPORTS_DIR      = os.path.join(GOLDPAN_DIR, "recanvass_reports")
CACHE_DIR        = os.path.join(GOLDPAN_DIR, "recanvass_cache")
DRY_RUN          = "--dry-run" in sys.argv

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

# Restaurants with no stable public menu URL
MANUAL_ONLY = {
    "Chop N Fresh",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_pdf_text(content):
    """Extract text from PDF bytes using pdfplumber."""
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return " ".join(pages)[:20000]
    except Exception as e:
        return None


def fetch_menu(url, timeout=30):
    """Returns (clean_text, error_string). text is None on failure."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        is_pdf = "pdf" in ct or url.lower().endswith(".pdf")

        if is_pdf:
            if not PDF_SUPPORT:
                return None, "PDF — install pdfplumber: pip install pdfplumber --break-system-packages"
            text = fetch_pdf_text(r.content)
            if not text:
                return None, "PDF — could not extract text (possibly scanned image)"
            clean = re.sub(r'\s+', ' ', text).strip()
            return clean[:20000], None

        # HTML page
        text = r.text
        clean = re.sub(r'<[^>]+>', ' ', text)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean[:20000], None

    except requests.exceptions.Timeout:
        return None, "Timeout"
    except requests.exceptions.ConnectionError as e:
        return None, f"Connection error: {str(e)[:60]}"
    except requests.exceptions.RequestException as e:
        return None, str(e)[:80]


def check_dishes(menu_text, dish_names):
    """
    For each dish name, check if it (or a close variant) appears in menu_text.
    Returns dict: {dish_name: found (bool)}
    """
    menu_lower = menu_text.lower()
    results = {}
    for name in dish_names:
        # Check for the dish name or first 3+ words of it
        name_lower = name.lower()
        words = name_lower.split()
        # Match full name or first 3 significant words
        core = " ".join(words[:3]) if len(words) >= 3 else name_lower
        results[name] = (name_lower in menu_lower) or (core in menu_lower)
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def save_cache(today, slug, text):
    cache_day = os.path.join(CACHE_DIR, today)
    os.makedirs(cache_day, exist_ok=True)
    with open(os.path.join(cache_day, f"{slug}.txt"), "w", encoding="utf-8") as f:
        f.write(text)


def main():
    today = datetime.date.today().isoformat()
    os.makedirs(REPORTS_DIR, exist_ok=True)
    out_path = os.path.join(REPORTS_DIR, f"{today}.json")

    print("Loading data...")
    dishes      = load_json(DISHES_FILE)
    restaurants = load_json(RESTAURANTS_FILE)

    # Group dish names by restaurant
    dishes_by_restaurant = {}
    for d in dishes:
        dishes_by_restaurant.setdefault(d["restaurant"], []).append(d["name"])

    report = {
        "date": today,
        "total_dishes": len(dishes),
        "restaurants": []
    }

    for rest in sorted(restaurants, key=lambda r: r["name"]):
        name     = rest["name"]
        menu_url = rest.get("menu_link", "").strip()
        current  = dishes_by_restaurant.get(name, [])

        entry = {
            "name": name,
            "dish_count": len(current),
            "menu_url": menu_url,
            "status": None,
            "error": None,
            "dishes_found": [],
            "dishes_missing": [],
            "menu_text_length": 0,
        }

        print(f"\n[{name}]  ({len(current)} dishes)")

        if name in MANUAL_ONLY or not menu_url:
            entry["status"] = "manual"
            print("  → manual check required (no URL)")
            report["restaurants"].append(entry)
            continue

        if DRY_RUN:
            entry["status"] = "dry_run"
            print(f"  → would fetch: {menu_url}")
            report["restaurants"].append(entry)
            continue

        print(f"  fetching {menu_url} ...")
        menu_text, err = fetch_menu(menu_url)

        if err:
            entry["status"] = "error"
            entry["error"]  = err
            print(f"  ✗ {err}")
            report["restaurants"].append(entry)
            continue

        entry["menu_text_length"] = len(menu_text)
        slug = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
        save_cache(today, slug, menu_text)
        print(f"  fetched {len(menu_text):,} chars — checking {len(current)} dishes...")

        results = check_dishes(menu_text, current)
        entry["dishes_found"]   = [n for n, found in results.items() if found]
        entry["dishes_missing"] = [n for n, found in results.items() if not found]

        found_pct = len(entry["dishes_found"]) / len(current) * 100 if current else 0

        if found_pct >= 70:
            entry["status"] = "ok"
            print(f"  ✓ {found_pct:.0f}% of dishes found on page")
        elif found_pct >= 40:
            entry["status"] = "warn"
            print(f"  ⚠ {found_pct:.0f}% found — possible changes")
        else:
            entry["status"] = "alert"
            print(f"  ✗ only {found_pct:.0f}% found — likely stale or page changed")

        report["restaurants"].append(entry)
        time.sleep(1)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n✅ Report saved to {out_path}")
    return out_path


if __name__ == "__main__":
    main()
