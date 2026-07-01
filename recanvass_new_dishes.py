"""
recanvass_new_dishes.py — Potential new dish detector.

Reads cached menu text from recanvass_report.py and looks for items
that appear on the current menu but aren't in the Goldpan database.

Run AFTER recanvass_report.py (uses its cached menu text).

Usage:
    python3 recanvass_new_dishes.py
    python3 recanvass_new_dishes.py 2026-06-25   (use specific date's cache)

Output: recanvass_reports/YYYY-MM-DD_new_dishes.json
"""

import json
import sys
import os
import re
import datetime

GOLDPAN_DIR  = os.path.dirname(os.path.abspath(__file__))
DISHES_FILE  = os.path.join(GOLDPAN_DIR, "dishes.json")
CACHE_DIR    = os.path.join(GOLDPAN_DIR, "recanvass_cache")
REPORTS_DIR  = os.path.join(GOLDPAN_DIR, "recanvass_reports")

# Noise words that appear in menus but aren't dish names
NOISE_WORDS = {
    "menu", "items", "allergen", "calories", "serving", "contains",
    "gluten", "dairy", "vegan", "vegetarian", "gf", "df", "v",
    "add", "extra", "side", "choose", "select", "included",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "daily", "seasonal", "limited",
    "available", "ask", "server", "prices", "subject", "change",
    "tax", "gratuity", "parties", "please", "note", "notice",
    "hours", "open", "closed", "location", "address", "phone",
    "follow", "instagram", "facebook", "website", "order",
    "online", "delivery", "pickup", "catering", "gift", "card",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_candidates(text):
    """
    Extract potential dish name candidates from menu text.
    Looks for short title-case phrases (2-6 words) that could be dish names.
    """
    candidates = set()

    # Split into sentences/lines by punctuation and line breaks
    chunks = re.split(r'[|\n\r•·–—]', text)

    for chunk in chunks:
        chunk = chunk.strip()
        # Skip very short or very long chunks
        if len(chunk) < 4 or len(chunk) > 60:
            continue
        # Skip chunks with prices only
        if re.match(r'^\$?\d+\.?\d*$', chunk):
            continue
        # Skip chunks that are mostly numbers/punctuation
        if len(re.findall(r'[a-zA-Z]', chunk)) < len(chunk) * 0.5:
            continue
        # Clean up
        chunk = re.sub(r'\$[\d.]+', '', chunk).strip()
        chunk = re.sub(r'\s+', ' ', chunk).strip()
        if not chunk:
            continue

        words = chunk.split()
        if len(words) < 1 or len(words) > 8:
            continue

        # Must start with a capital letter (likely a proper noun / dish name)
        if not chunk[0].isupper():
            continue

        # Skip if any noise word is the first word
        if words[0].lower() in NOISE_WORDS:
            continue

        # Skip if more than 2 noise words total
        noise_count = sum(1 for w in words if w.lower() in NOISE_WORDS)
        if noise_count > 2:
            continue

        candidates.add(chunk)

    return candidates


def normalize(name):
    return re.sub(r'[^a-z0-9 ]', '', name.lower().strip())


def main():
    # Determine which cache date to use
    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        today = sys.argv[1]
    else:
        today = datetime.date.today().isoformat()

    cache_day = os.path.join(CACHE_DIR, today)
    if not os.path.exists(cache_day):
        print(f"No cache found for {today}. Run recanvass_report.py first.")
        sys.exit(1)

    out_path = os.path.join(REPORTS_DIR, f"{today}_new_dishes.json")
    os.makedirs(REPORTS_DIR, exist_ok=True)

    print(f"Loading dishes.json...")
    dishes = load_json(DISHES_FILE)

    # Build known dish names per restaurant (normalized)
    known_by_restaurant = {}
    for d in dishes:
        r = d["restaurant"]
        known_by_restaurant.setdefault(r, set()).add(normalize(d["name"]))

    # Also build a global set of normalized known names for fuzzy skip
    all_known = {normalize(d["name"]) for d in dishes}

    report = {"date": today, "restaurants": []}
    total_candidates = 0

    cache_files = sorted(os.listdir(cache_day))
    print(f"Checking {len(cache_files)} cached menu(s)...\n")

    # Map slug back to restaurant name
    dishes_by_restaurant = {}
    for d in dishes:
        dishes_by_restaurant.setdefault(d["restaurant"], [])

    # Build slug → restaurant name map
    slug_to_restaurant = {}
    for rname in dishes_by_restaurant:
        slug = re.sub(r'[^a-z0-9]+', '_', rname.lower()).strip('_')
        slug_to_restaurant[slug] = rname

    for fname in cache_files:
        if not fname.endswith('.txt'):
            continue
        slug = fname[:-4]
        rname = slug_to_restaurant.get(slug)

        cache_path = os.path.join(cache_day, fname)
        with open(cache_path, "r", encoding="utf-8") as f:
            text = f.read()

        candidates = extract_candidates(text)
        known = known_by_restaurant.get(rname, set())

        # Filter out already-known dishes
        new_candidates = []
        for c in sorted(candidates):
            norm = normalize(c)
            # Skip if it matches a known dish (exact or close)
            if norm in all_known:
                continue
            # Skip if it's a substring of a known dish name
            if any(norm in k or k in norm for k in all_known if len(k) > 4):
                continue
            new_candidates.append(c)

        if new_candidates:
            label = rname or slug
            print(f"[{label}] — {len(new_candidates)} potential new item(s)")
            for c in new_candidates[:20]:  # cap display at 20
                print(f"  + {c}")
            report["restaurants"].append({
                "name": label,
                "potential_new": new_candidates,
                "count": len(new_candidates),
            })
            total_candidates += len(new_candidates)
        else:
            print(f"[{rname or slug}] — nothing new detected")

    print(f"\nTotal candidates across all restaurants: {total_candidates}")
    print("Note: these are unverified candidates — review before adding to database.")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"✅ Report saved to {out_path}")


if __name__ == "__main__":
    main()
