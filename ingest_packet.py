"""
ingest_packet.py — Convert a GoldPan Intake Packet → Google Sheets rows.

Reads a reviewed intake packet (intake_packets/*.json), assigns IDs, maps
contents to the existing Sheets schema, and either reports what would be
written (dry run) or commits to production (--commit).

Sheets written:
  Ingredient Details        — one row per verified ingredient
  Goldpan Dish Level Data   — one row per dish (21 columns, incl. Calorie_Value + Calorie_Source_Text)
  Restaurant Claims         — one row per restaurant claim

Reported but not written (no current Sheets tab):
  verbatim_components       — flagged in ingestion report
  review_flags              — printed in ingestion report
  advisory_notes            — printed in ingestion report
  allergen_disclosures      — flagged as requires manual entry in Allergen_Disclosures tab

Governance is NOT run by this script. After a successful commit, run:
    python3 pipeline.py --apply

Usage:
    python3 ingest_packet.py <packet_file>              # dry run
    python3 ingest_packet.py <packet_file> --commit     # write to Sheets
    python3 ingest_packet.py <packet_file> --test-mode  # allow pending_review status

Exit codes:
    0  — success (dry run report or successful commit)
    1  — blocked (reviewer_status not approved, or validation error)
    2  — usage error
"""

from __future__ import annotations

import json
import os
import re
import sys
import datetime
import time
from collections import defaultdict

# ── Config ────────────────────────────────────────────────────────────────────

GOLDPAN_DIR    = os.path.dirname(os.path.abspath(__file__))
KEY_FILE       = os.path.join(GOLDPAN_DIR, "service_account.json")
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
DISHES_FILE    = os.path.join(GOLDPAN_DIR, "dishes.json")
RESTAURANTS_FILE = os.path.join(GOLDPAN_DIR, "restaurants.json")
TODAY_ISO      = datetime.date.today().isoformat()
TODAY_DISPLAY  = datetime.date.today().strftime("%-m/%-d/%Y")

DISH_ID_RE     = re.compile(r"^D(\d+)$")
REST_ID_RE     = re.compile(r"^R(\d+)$")

COMMIT     = "--commit" in sys.argv
TEST_MODE  = "--test-mode" in sys.argv
NO_COLOR   = "--no-color" in sys.argv or not sys.stdout.isatty()

# Approved ingredient_source values
APPROVED_SOURCES = {
    "menu", "website", "allergen_guide", "nutrition_document",
    "ordering_platform", "restaurant_qa", "restaurant_confirmation", "pdf",
}

# ── ANSI helpers ──────────────────────────────────────────────────────────────

def _c(code, text):
    if NO_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"

GREEN  = lambda t: _c("32", t)
RED    = lambda t: _c("31", t)
YELLOW = lambda t: _c("33", t)
BOLD   = lambda t: _c("1", t)
DIM    = lambda t: _c("2", t)


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args():
    non_flags = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not non_flags:
        print("Usage: python3 ingest_packet.py <packet_file> [--commit] [--test-mode]",
              file=sys.stderr)
        sys.exit(2)
    return non_flags[0]


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_packet(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_dishes() -> list:
    if not os.path.exists(DISHES_FILE):
        return []
    with open(DISHES_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_restaurants() -> list:
    if not os.path.exists(RESTAURANTS_FILE):
        return []
    with open(RESTAURANTS_FILE, encoding="utf-8") as f:
        return json.load(f)


# ── ID resolution ─────────────────────────────────────────────────────────────

def _parse_int_id(raw: str, pattern) -> int | None:
    m = pattern.match(str(raw).strip())
    return int(m.group(1)) if m else None


def resolve_restaurant_id(restaurant_name: str, dishes: list) -> tuple[str, bool]:
    """
    Find existing Restaurant_ID for this restaurant in dishes.json.
    Returns (restaurant_id, is_new).
    """
    name_lower = restaurant_name.strip().lower()
    for dish in dishes:
        if dish.get("restaurant", "").strip().lower() == name_lower:
            rid = dish.get("restaurant_id", "")
            if rid and REST_ID_RE.match(rid):
                return rid, False

    # New restaurant — scan staging files + dishes for max R ID
    max_r = 0
    for dish in dishes:
        n = _parse_int_id(dish.get("restaurant_id", ""), REST_ID_RE)
        if n and n > max_r:
            max_r = n

    for fname in os.listdir(GOLDPAN_DIR):
        if not fname.startswith("staging_") or not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(GOLDPAN_DIR, fname), encoding="utf-8") as f:
                data = json.load(f)
            rid = data.get("restaurant_id", "")
            n = _parse_int_id(rid, REST_ID_RE)
            if n and n > max_r:
                max_r = n
        except Exception:
            continue

    if max_r == 0:
        max_r = len(load_restaurants())

    return f"R{max_r + 1:03d}", True


def assign_dish_ids(n_dishes: int, dishes: list) -> list[str]:
    """
    Return n_dishes sequential Dish_IDs starting from max existing + 1.
    """
    nums = [_parse_int_id(d.get("id", ""), DISH_ID_RE) for d in dishes]
    nums = [n for n in nums if n is not None]
    start = max(nums) + 1 if nums else 1
    return [f"D{start + i:03d}" for i in range(n_dishes)]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _allergen_flags_str(flags) -> str:
    """Normalize allergen_flags (array or string) to a single Sheet-compatible string."""
    if isinstance(flags, list):
        cleaned = [f.strip() for f in flags if f.strip()]
        return ", ".join(cleaned) if cleaned else "none"
    if isinstance(flags, str):
        return flags.strip() or "none"
    return "none"


def _modifiers_to_str(modifiers: list) -> str:
    """Flatten modifiers to a human-readable options string."""
    if not modifiers:
        return ""
    parts = []
    for m in modifiers:
        if isinstance(m, dict):
            name = m.get("modifier_name", "")
            price = m.get("modifier_price", "")
            desc = m.get("modifier_description", "")
            part = name
            if price:
                part += f" ({price})"
            if desc and desc != name:
                part += f": {desc}"
            parts.append(part)
        else:
            parts.append(str(m))
    return "; ".join(parts)


def _allergen_summary(dish: dict) -> str:
    """Derive Allergen_Summary from allergen_disclosures if present."""
    disclosures = dish.get("allergen_disclosures", [])
    if disclosures:
        statements = [d.get("statement", d.get("source_text", "")) for d in disclosures]
        return " | ".join(s for s in statements if s)
    return "Unknown"


def _menu_link(restaurant: dict) -> str:
    """Extract primary menu link from source_inventory or menu_link field."""
    if restaurant.get("menu_link"):
        return restaurant["menu_link"]
    for src in restaurant.get("source_inventory", []):
        if src.get("url"):
            return src["url"]
    return ""


# ── Row builders ──────────────────────────────────────────────────────────────

def build_ingredient_rows(packet: dict, rid: str, dish_ids: list[str]) -> list[list]:
    """
    Ingredient Details tab — 14 columns:
    Restaurant_ID | Restaurant_Name | Location | Dish_ID | Dish_Name |
    Ingredient | Cut_Type | Preparation | Ingredient_Type | Status |
    Version | Ingredient_Source | Allergen_Flags | Component_Role
    """
    restaurant = packet["restaurant"]
    rname = restaurant["restaurant_name"]
    loc   = restaurant.get("location", "")
    rows  = []

    for dish, did in zip(packet["dishes"], dish_ids):
        for ing in dish.get("ingredients", []):
            if isinstance(ing, str):
                name, cut_type, prep, ing_type, source, allergen_flags, role = (
                    ing, "none", "none", "standard", "menu", "none", ""
                )
            else:
                name         = ing.get("name", "")
                cut_type     = ing.get("cut_type", "none") or "none"
                prep         = ing.get("preparation", "none") or "none"
                ing_type     = ing.get("type", "standard") or "standard"
                source       = ing.get("ingredient_source", "menu")
                allergen_flags = _allergen_flags_str(ing.get("allergen_flags", "none"))
                role         = ing.get("role", "") or ""

            rows.append([
                rid, rname, loc,
                did, dish["dish_name"],
                name, cut_type, prep, ing_type,
                "Active", "1",
                source, allergen_flags, role,
            ])

    return rows


def build_dish_level_rows(packet: dict, rid: str, dish_ids: list[str]) -> list[list]:
    """
    Goldpan Dish Level Data tab — 21 columns:
    Restaurant_ID | Restaurant_Name | Location | Dish_ID | Dish_Name |
    Dietary_Tags | Dietary_Options | Tag_Source | Recanvass_Status | Hours |
    Menu_Link | Menu_Price | Restaurant_Address | Allergen_Summary |
    Last_Updated | Restaurant_Website | Status | Version | Category |
    Calorie_Value | Calorie_Source_Text
    """
    restaurant = packet["restaurant"]
    rname      = restaurant["restaurant_name"]
    loc        = restaurant.get("location", "")
    hours      = restaurant.get("hours", "")
    menu_link  = _menu_link(restaurant)
    rest_addr  = restaurant.get("restaurant_address", "")
    rest_web   = restaurant.get("restaurant_website", "")
    rows       = []

    for dish, did in zip(packet["dishes"], dish_ids):
        stated_tags = dish.get("stated_tags", [])
        tag_source  = dish.get("tag_source", "")
        tags_str    = ", ".join(stated_tags) if stated_tags else "none"
        if not tag_source and stated_tags:
            tag_source = "menu"

        cal               = dish.get("restaurant_calorie_content")
        calorie_value     = str(cal["value"]) if cal and cal.get("value") else ""
        calorie_src_text  = cal.get("source_text", "") if cal else ""

        rows.append([
            rid, rname, loc,
            did, dish["dish_name"],
            tags_str,
            _modifiers_to_str(dish.get("modifiers", [])),
            tag_source or "none",
            "unconfirmed",
            hours,
            menu_link,
            dish.get("price", ""),
            rest_addr,
            _allergen_summary(dish),
            TODAY_DISPLAY,
            rest_web,
            "Active",
            "",
            dish.get("category", dish.get("menu_section", "")),
            calorie_value,
            calorie_src_text,
        ])

    return rows


def build_claims_rows(packet: dict, rid: str) -> tuple[list[list], list[str]]:
    """
    Restaurant Claims tab — 8 columns:
    Restaurant_ID | Restaurant_Name | Claim_Type | Claim_Scope |
    Claim_Text | Verified | Source | Date_Added

    Returns (rows, warnings).

    Claim_Type inference: the intake packet's restaurant_claims scope enum
    blends two concepts — location scope (restaurant_level, dish_level) and
    content type (ownership, sourcing, health_positioning, operational).
    Content-type scope values are safe to infer as Claim_Type.
    Location-only scope values (restaurant_level, menu_section_level, dish_level)
    cannot be inferred — Claim_Type is left blank and a warning is issued.
    """
    # Scope values that are also valid Claim_Type content descriptors
    SCOPE_TO_TYPE: dict[str, str] = {
        "ownership":          "ownership",
        "sourcing":           "sourcing",
        "health_positioning": "health_positioning",
        "operational":        "operational",
    }

    restaurant = packet["restaurant"]
    rname      = restaurant["restaurant_name"]
    rows:     list[list] = []
    warnings: list[str]  = []

    for i, claim in enumerate(restaurant.get("restaurant_claims", []), start=1):
        if not isinstance(claim, dict):
            continue

        claim_type = claim.get("claim_type", "").strip()
        scope      = claim.get("scope", "").strip()

        if not claim_type:
            inferred = SCOPE_TO_TYPE.get(scope, "")
            if inferred:
                claim_type = inferred
            else:
                warnings.append(
                    f"Claim {i}: claim_type missing and cannot be safely inferred "
                    f"from scope='{scope}'. Claim_Type written as blank — manual entry required."
                )

        rows.append([
            rid,
            rname,
            claim_type,
            scope,
            claim.get("claim_text", ""),
            "unverified",
            claim.get("source_url", ""),
            TODAY_DISPLAY,
        ])

    return rows, warnings


# ── Validation ────────────────────────────────────────────────────────────────

def validate_packet(packet: dict, test_mode: bool, commit: bool = False) -> list[str]:
    """
    Validate the packet before ingestion.
    Returns list of blocking error strings. Empty = pass.

    Reviewer status rules:
      approved        → always allowed
      pending_review  → allowed in dry run with --test-mode only
                        BLOCKED for --commit regardless of --test-mode
      anything else   → always blocked
    """
    errors = []
    restaurant = packet.get("restaurant", {})

    # Reviewer status check
    status = restaurant.get("reviewer_status", "")
    if status == "approved":
        pass
    elif status == "pending_review" and test_mode and not commit:
        pass  # dry-run inspection only — commit still requires approved
    elif status == "pending_review" and commit:
        extra = " (--test-mode only bypasses this for dry runs)" if test_mode else ""
        errors.append(
            f"reviewer_status is 'pending_review'. --commit requires 'approved' status.{extra} "
            f"Advance the packet to 'approved' before committing to Sheets."
        )
    elif status == "pending_review":
        errors.append(
            f"reviewer_status is 'pending_review'. Add --test-mode to inspect in dry run, "
            f"or advance the packet to 'approved' before using --commit."
        )
    else:
        errors.append(
            f"reviewer_status is '{status}'. Must be 'approved' to commit, "
            f"or 'pending_review' with --test-mode for dry-run inspection."
        )

    # Required structure
    if not restaurant.get("restaurant_name"):
        errors.append("restaurant.restaurant_name is missing or empty.")
    if not packet.get("dishes"):
        errors.append("packet has no dishes.")

    # Ingredient source validation
    for dish in packet.get("dishes", []):
        for ing in dish.get("ingredients", []):
            if isinstance(ing, dict):
                src = ing.get("ingredient_source", "")
                if src and src not in APPROVED_SOURCES:
                    errors.append(
                        f"Dish '{dish.get('dish_name', '?')}' ingredient '{ing.get('name', '?')}': "
                        f"ingredient_source '{src}' is not in the approved source enum."
                    )

    return errors


# ── Unsupported field collector ───────────────────────────────────────────────

def collect_unsupported(packet: dict, dish_ids: list[str]) -> dict:
    """
    Collect fields that have no current Sheets destination.
    Returns structured dict for the ingestion report.

    Note: restaurant_calorie_content is no longer unsupported — it is written
    to the Calorie_Value and Calorie_Source_Text columns of the DLD tab.
    """
    report = {
        "verbatim_components": [],
        "allergen_disclosures": [],
        "review_flags": packet.get("review_flags", []),
        "advisory_notes": packet.get("advisory_notes", []),
    }

    for dish, did in zip(packet["dishes"], dish_ids):
        # verbatim_components
        for vc in dish.get("verbatim_components", []):
            report["verbatim_components"].append({
                "dish_id": did,
                "dish_name": dish["dish_name"],
                "verbatim_text": vc.get("verbatim_text", ""),
                "ingredient_source": vc.get("ingredient_source", ""),
                "resolution_status": vc.get("resolution_status", "unresolved"),
            })

        # allergen_disclosures
        for ad in dish.get("allergen_disclosures", []):
            report["allergen_disclosures"].append({
                "dish_id": did,
                "dish_name": dish["dish_name"],
                "allergen": ad.get("allergen", ""),
                "statement": ad.get("statement", ""),
                "ingredient_source": ad.get("ingredient_source", ""),
                "source_text": ad.get("source_text", ""),
            })

    return report


# ── Gap check ─────────────────────────────────────────────────────────────────

def check_gaps(packet: dict) -> list[str]:
    """Report missing Enhanced fields that are in the Gap Report."""
    restaurant = packet.get("restaurant", {})
    warnings = []
    if not restaurant.get("location"):
        warnings.append("location: not in packet (Gap Report GAP-04 — needed for DLD + Sheets rows)")
    if not restaurant.get("restaurant_address"):
        warnings.append("restaurant_address: not in packet (Gap Report GAP-05)")
    if not restaurant.get("restaurant_website"):
        warnings.append("restaurant_website: not in packet (Gap Report GAP-05)")
    if not restaurant.get("hours"):
        warnings.append("hours: not in packet (Gap Report GAP-05)")
    if not restaurant.get("menu_link") and not restaurant.get("source_inventory"):
        warnings.append("menu_link: not in packet (Gap Report GAP-08)")
    for dish in packet.get("dishes", []):
        if not dish.get("stated_tags") and not dish.get("category"):
            break  # report once, not per dish
    return warnings


# ── Report printer ────────────────────────────────────────────────────────────

def print_report(
    packet: dict,
    rid: str,
    is_new_restaurant: bool,
    dish_ids: list[str],
    ing_rows: list[list],
    dld_rows: list[list],
    claims_rows: list[list],
    claims_warnings: list[str],
    unsupported: dict,
    gap_warnings: list[str],
    test_mode: bool,
    commit: bool,
):
    restaurant = packet["restaurant"]
    rname      = restaurant["restaurant_name"]
    status     = restaurant.get("reviewer_status", "unknown")
    n_dishes   = len(packet["dishes"])
    n_vc       = len(unsupported["verbatim_components"])
    n_ad       = len(unsupported["allergen_disclosures"])
    n_cal      = sum(1 for d in packet["dishes"] if d.get("restaurant_calorie_content"))
    n_flags    = len(unsupported["review_flags"])

    print()
    print(BOLD("─" * 65))
    print(BOLD(f"  GoldPan Ingestion Report  —  {TODAY_ISO}"))
    mode_label = "COMMIT" if commit else "DRY RUN"
    test_label = " [TEST MODE]" if test_mode else ""
    print(f"  Mode: {BOLD(mode_label)}{test_label}")
    print(BOLD("─" * 65))

    print(f"\n  Restaurant   : {rname}")
    print(f"  Restaurant_ID: {rid}  {'(new)' if is_new_restaurant else '(existing)'}")
    print(f"  Status       : {status}")
    print(f"  Canvass date : {restaurant.get('canvass_date', '—')}")
    print(f"  Dishes       : {n_dishes}")

    print(f"\n  {'─' * 55}")
    print(f"  Rows to write:")
    print(f"    Ingredient Details      : {len(ing_rows)} row(s)")
    print(f"    Dish Level Data         : {len(dld_rows)} row(s)")
    print(f"    Restaurant Claims       : {len(claims_rows)} row(s)")
    if n_cal:
        print(f"    Calorie records (DLD)   : {n_cal} dish(es) with restaurant_calorie_content")

    # Per-dish summary
    print(f"\n  {'─' * 55}")
    print(f"  Dish assignments:")
    for dish, did in zip(packet["dishes"], dish_ids):
        n_ing = len(dish.get("ingredients", []))
        n_vc_d = len(dish.get("verbatim_components", []))
        n_ad_d = len(dish.get("allergen_disclosures", []))
        cal_d  = "✓" if dish.get("restaurant_calorie_content") else ""
        markers = []
        if n_vc_d:
            markers.append(f"{n_vc_d} verbatim")
        if n_ad_d:
            markers.append(f"{n_ad_d} disclosures")
        if cal_d:
            markers.append("calories")
        note = f"  [{', '.join(markers)}]" if markers else ""
        print(f"    {did}  {dish['dish_name'][:45]:<45}  {n_ing} ingredient(s){note}")

    # Gap warnings
    if gap_warnings:
        print(f"\n  {'─' * 55}")
        print(YELLOW(f"  Gap warnings ({len(gap_warnings)}) — rows written with blanks:"))
        for w in gap_warnings:
            print(YELLOW(f"    ⚠  {w}"))

    # Unsupported: verbatim_components
    if n_vc:
        print(f"\n  {'─' * 55}")
        print(YELLOW(f"  Verbatim components ({n_vc}) — no Sheets tab, manual review required:"))
        for vc in unsupported["verbatim_components"]:
            print(f"    {vc['dish_id']}  {vc['dish_name'][:35]:<35}  \"{vc['verbatim_text']}\"")

    # Unsupported: allergen_disclosures — manual entry required
    if n_ad:
        print(f"\n  {'─' * 55}")
        print(YELLOW(f"  ALLERGEN DISCLOSURES — MANUAL ENTRY REQUIRED ({n_ad}):"))
        print(YELLOW(f"  Disclosure_Status (contains / may_contain / free_from) requires human judgment."))
        print(YELLOW(f"  Enter these rows directly in the Allergen_Disclosures tab:"))
        for ad in unsupported["allergen_disclosures"]:
            print(f"    {ad['dish_id']}  {ad['allergen']:<12}  source={ad['ingredient_source']}")
            print(f"           Statement: \"{ad['statement'][:80]}\"")
            if ad["source_text"] and ad["source_text"] != ad["statement"]:
                print(f"           Source text: \"{ad['source_text'][:80]}\"")

    # Claims warnings (claim_type inference)
    if claims_warnings:
        print(f"\n  {'─' * 55}")
        print(YELLOW(f"  Restaurant Claims warnings ({len(claims_warnings)}):"))
        for w in claims_warnings:
            print(YELLOW(f"    ⚠  {w}"))

    # Review flags
    if n_flags:
        print(f"\n  {'─' * 55}")
        print(YELLOW(f"  Review flags ({n_flags}):"))
        for flag in unsupported["review_flags"]:
            if isinstance(flag, dict):
                ftype  = flag.get("type", flag.get("flag_type", ""))
                phrase = flag.get("phrase", flag.get("component", ""))
                dish   = flag.get("dish", flag.get("dish_name", ""))
                action = flag.get("suggested_action", flag.get("action", ""))
                print(f"    [{ftype}]  {phrase or dish}")
                if action:
                    print(f"      → {action}")
            else:
                print(f"    {flag}")

    # Advisory notes
    advisory_notes = unsupported.get("advisory_notes", [])
    if advisory_notes:
        print(f"\n  {'─' * 55}")
        print(DIM(f"  Advisory notes ({len(advisory_notes)}):"))
        for note in advisory_notes:
            if isinstance(note, dict):
                print(DIM(f"    {note.get('note', note)}"))
            else:
                print(DIM(f"    {note}"))

    print(f"\n  {'─' * 55}")
    if commit:
        print(GREEN(f"  Rows committed to Sheets."))
        print(f"  Next step: python3 pipeline.py --apply")
    else:
        print(DIM(f"  DRY RUN — no writes. Add --commit to write to Sheets."))

    print(BOLD("─" * 65))
    print()


# ── Sheets writer ─────────────────────────────────────────────────────────────

def api_call_with_retry(fn, *args, retries=4, **kwargs):
    import gspread
    for attempt in range(retries):
        try:
            return fn(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            if e.response.status_code == 429 and attempt < retries - 1:
                wait = 30 * (attempt + 1)
                print(f"  [quota] 429 received — waiting {wait}s before retry {attempt + 2}/{retries}...")
                time.sleep(wait)
            else:
                raise


def index_by_dish_id(ws, did_col_idx: int) -> dict:
    """Return {dish_id: [1-indexed row numbers]} for all data rows."""
    all_values = ws.get_all_values()
    index = defaultdict(list)
    for i, row in enumerate(all_values[1:], start=2):
        did = row[did_col_idx].strip() if len(row) > did_col_idx else ""
        if did:
            index[did].append(i)
    return dict(index)


def delete_rows_batch(ws, row_numbers: list):
    if not row_numbers:
        return
    requests = [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": ws._properties["sheetId"],
                    "dimension": "ROWS",
                    "startIndex": rn - 1,
                    "endIndex": rn,
                }
            }
        }
        for rn in sorted(row_numbers, reverse=True)
    ]
    api_call_with_retry(ws.spreadsheet.batch_update, {"requests": requests})


def write_to_sheets(
    ing_rows: list[list],
    dld_rows: list[list],
    claims_rows: list[list],
    dish_ids: list[str],
):
    """Write prepared rows to Google Sheets."""
    import gspread
    from google.oauth2.service_account import Credentials

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    print("\n  Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    # ── Ingredient Details ─────────────────────────────────────────────────────
    print("  Writing Ingredient Details...")
    ws_ing = ss.worksheet("Ingredient Details")
    ing_index = index_by_dish_id(ws_ing, did_col_idx=3)  # Dish_ID is col 3 (0-indexed)
    to_delete = []
    for did in dish_ids:
        to_delete.extend(ing_index.get(did, []))
    if to_delete:
        print(f"    Deleting {len(to_delete)} existing ingredient row(s)...")
        delete_rows_batch(ws_ing, to_delete)
        time.sleep(1)
    if ing_rows:
        api_call_with_retry(ws_ing.append_rows, ing_rows, value_input_option="USER_ENTERED")
        print(f"    {GREEN('✓')} {len(ing_rows)} ingredient row(s) written.")

    # ── Goldpan Dish Level Data ────────────────────────────────────────────────
    print("  Writing Goldpan Dish Level Data...")
    ws_dld = ss.worksheet("Goldpan Dish Level Data")
    dld_index = index_by_dish_id(ws_dld, did_col_idx=3)
    to_delete = []
    for did in dish_ids:
        to_delete.extend(dld_index.get(did, []))
    if to_delete:
        print(f"    Deleting {len(to_delete)} existing DLD row(s)...")
        delete_rows_batch(ws_dld, to_delete)
        time.sleep(1)
    if dld_rows:
        api_call_with_retry(ws_dld.append_rows, dld_rows, value_input_option="USER_ENTERED")
        print(f"    {GREEN('✓')} {len(dld_rows)} DLD row(s) written.")

    # ── Restaurant Claims ──────────────────────────────────────────────────────
    if claims_rows:
        print("  Writing Restaurant Claims...")
        try:
            ws_claims = ss.worksheet("Restaurant Claims")
        except Exception:
            CLAIMS_HEADERS = [
                "Restaurant_ID", "Restaurant_Name", "Claim_Type", "Claim_Scope",
                "Claim_Text", "Verified", "Source", "Date_Added",
            ]
            ws_claims = ss.add_worksheet(title="Restaurant Claims", rows=500,
                                          cols=len(CLAIMS_HEADERS))
            ws_claims.append_row(CLAIMS_HEADERS)
            print("    (created Restaurant Claims tab)")

        # Delete existing rows for this restaurant_id (col 0)
        all_values = ws_claims.get_all_values()
        rid = claims_rows[0][0]
        to_delete = [i for i, row in enumerate(all_values[1:], start=2)
                     if row and row[0].strip() == rid]
        if to_delete:
            delete_rows_batch(ws_claims, to_delete)
            time.sleep(1)

        api_call_with_retry(ws_claims.append_rows, claims_rows, value_input_option="USER_ENTERED")
        print(f"    {GREEN('✓')} {len(claims_rows)} claim row(s) written.")
    else:
        print("  Restaurant Claims: none to write.")

    print(f"\n  {GREEN('Sheets commit complete.')}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    packet_path = parse_args()

    if not os.path.exists(packet_path):
        print(f"ERROR: File not found: {packet_path}", file=sys.stderr)
        sys.exit(2)

    print(f"\n  Loading packet: {os.path.basename(packet_path)}")
    packet = load_packet(packet_path)

    # Validate
    errors = validate_packet(packet, TEST_MODE, commit=COMMIT)
    if errors:
        print(f"\n{RED('  BLOCKED — packet failed validation:')}")
        for e in errors:
            print(f"    {RED('✗')}  {e}")
        print()
        sys.exit(1)

    # Load existing data
    dishes = load_dishes()

    # Resolve IDs
    restaurant = packet["restaurant"]
    rname = restaurant["restaurant_name"]
    rid, is_new = resolve_restaurant_id(rname, dishes)
    dish_ids = assign_dish_ids(len(packet["dishes"]), dishes)

    # Build rows
    ing_rows              = build_ingredient_rows(packet, rid, dish_ids)
    dld_rows              = build_dish_level_rows(packet, rid, dish_ids)
    claims_rows, claims_warnings = build_claims_rows(packet, rid)
    unsupported           = collect_unsupported(packet, dish_ids)
    gap_warnings          = check_gaps(packet)

    # Commit to Sheets
    if COMMIT:
        write_to_sheets(ing_rows, dld_rows, claims_rows, dish_ids)

    # Print ingestion report
    print_report(
        packet, rid, is_new, dish_ids,
        ing_rows, dld_rows, claims_rows,
        claims_warnings,
        unsupported, gap_warnings,
        test_mode=TEST_MODE,
        commit=COMMIT,
    )


if __name__ == "__main__":
    main()
