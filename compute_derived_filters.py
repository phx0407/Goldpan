"""
compute_derived_filters.py — GoldPan derived filter computation.

Reads verified ingredient data from Google Sheets, runs every registered
derived filter for every dish, and produces a structured report. In apply
mode, writes derived_filters.json.

Derived conclusions are computed output — not raw source data. They are
generated from verified facts in the sheet and stored as a separate derived
layer. The sheet stores verified facts; this script produces the derived layer.

Architecture:
  derived/models.py    — DerivedConclusion, DishEvidence, FilterDefinition
  derived/registry.py  — filter definitions and FILTER_REGISTRY dict
  derived/engine.py    — dependency checker and filter runner

Usage:
    python3 compute_derived_filters.py                        # dry run — report only, no writes
    python3 compute_derived_filters.py --apply                # write derived_filters.json
    python3 compute_derived_filters.py --apply --require-fresh  # abort if any restaurant needs_review

Output (--apply):
    derived_filters.json — one entry per dish_id with all filter conclusions
"""

import json
import os
import sys
import datetime
from collections import defaultdict

import gspread
from google.oauth2.service_account import Credentials

from derived.engine import build_dish_evidence, run_all_filters
from derived.registry import FILTER_REGISTRY
from freshness import compute_freshness_map, freshness_summary

# ── Config ────────────────────────────────────────────────────────────────────

GOLDPAN_DIR    = os.path.dirname(os.path.abspath(__file__))
KEY_FILE       = os.path.join(GOLDPAN_DIR, "service_account.json")
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TODAY          = datetime.date.today().isoformat()
DRY_RUN        = "--apply" not in sys.argv
REQUIRE_FRESH  = "--require-fresh" in sys.argv   # abort if any restaurant is needs_review
OUTPUT_FILE    = os.path.join(GOLDPAN_DIR, "derived_filters.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Ingredient values that indicate placeholder / not-yet-canvassed rows
SKIP_INGREDIENTS = {
    "building transparency",
    "ingredient detail pending confirmation",
    "none",
    "",
}


# ── Sheet loader ──────────────────────────────────────────────────────────────

def load_records(ss, tab_name: str) -> list[dict]:
    """Return all rows from a sheet tab as a list of dicts (header-keyed)."""
    ws   = ss.worksheet(tab_name)
    rows = ws.get_all_values()
    if len(rows) < 2:
        return []
    headers = [h.strip() for h in rows[0]]
    return [
        {headers[i]: (row[i].strip() if i < len(row) else "")
         for i in range(len(headers))}
        for row in rows[1:]
    ]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    mode = "DRY RUN — no writes" if DRY_RUN else "APPLY MODE — writing derived_filters.json"
    print(f"\ncompute_derived_filters.py  —  {TODAY}")
    print(f"{'='*65}")
    print(f"  {mode}")
    print(f"\n  Registered filters:")
    for slug, fdef in FILTER_REGISTRY.items():
        print(f"    [{fdef.dependency_type}]  {fdef.name}")
        print(f"      Rules: {', '.join(fdef.rule_ids)}")
    print(f"{'='*65}\n")

    # ── Connect ────────────────────────────────────────────────────────────────
    print("Connecting to Google Sheets...")
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    # ── Load Menu Source Registry + compute freshness ─────────────────────────
    print("Loading Menu Source Registry...")
    registry_rows = load_records(ss, "Menu Source Registry")
    print(f"  {len(registry_rows)} restaurant(s)")
    freshness_map = compute_freshness_map(registry_rows)
    fsummary      = freshness_summary(freshness_map)
    print(
        f"  Freshness: {fsummary['current']} current, {fsummary['due_soon']} due_soon, "
        f"{fsummary['overdue']} overdue, {fsummary['needs_review']} needs_review  "
        f"[score: {fsummary['freshness_score']}%]"
    )
    if not fsummary["critical_ok"]:
        print(
            f"  ⚠  {fsummary['needs_review']} restaurant(s) in needs_review — "
            f"derived conclusions will be suppressed for those dishes"
        )
        if REQUIRE_FRESH:
            print(
                f"\n  ABORT — --require-fresh is set and {fsummary['needs_review']} "
                f"restaurant(s) are in needs_review. "
                f"Resolve freshness issues first, then re-run without --require-fresh "
                f"or after running: python3 check_freshness.py --apply"
            )
            sys.exit(1)

    # ── Load Ingredient Details ────────────────────────────────────────────────
    print("Loading Ingredient Details...")
    ing_rows = load_records(ss, "Ingredient Details")
    print(f"  {len(ing_rows)} rows")

    # ── Load Goldpan Dish Level Data ───────────────────────────────────────────
    print("Loading Goldpan Dish Level Data...")
    dl_rows = load_records(ss, "Goldpan Dish Level Data")
    print(f"  {len(dl_rows)} dishes\n")

    # ── Build lookups ──────────────────────────────────────────────────────────

    # DLD: one row per dish
    dish_context: dict[str, dict] = {}
    for row in dl_rows:
        did = row.get("Dish_ID", "").strip()
        if did:
            dish_context[did] = row

    # Ingredient Details: group by Dish_ID, skip inactive dishes and placeholders
    inactive_ids = {
        did for did, ctx in dish_context.items()
        if ctx.get("Status", "").strip().lower() == "inactive"
    }
    by_dish: dict[str, list[dict]] = defaultdict(list)
    for row in ing_rows:
        did = row.get("Dish_ID", "").strip()
        ing = row.get("Ingredient", "").strip()
        if did and did not in inactive_ids and ing.lower() not in SKIP_INGREDIENTS:
            by_dish[did].append(row)

    # All active dish IDs: union of DLD (active) and Ingredient Details
    active_dld_ids = {
        did for did, ctx in dish_context.items()
        if ctx.get("Status", "").strip().lower() != "inactive"
    }
    all_dish_ids = sorted(active_dld_ids | set(by_dish.keys()))

    print(f"Processing {len(all_dish_ids)} active dishes × "
          f"{len(FILTER_REGISTRY)} filter(s)...\n")

    # ── Run filters ────────────────────────────────────────────────────────────
    results: dict[str, dict] = {}

    for did in all_dish_ids:
        ctx              = dish_context.get(did, {})
        ingredient_rows  = by_dish.get(did, [])

        # Prefer DLD for dish context; fall back to ingredient row if DLD missing
        def _ctx(key, fallback_key=None):
            v = ctx.get(key, "").strip()
            if not v and fallback_key and ingredient_rows:
                v = ingredient_rows[0].get(fallback_key, "").strip()
            return v

        dish_name     = _ctx("Dish_Name")
        restaurant    = _ctx("Restaurant", "Restaurant_Name")
        restaurant_id = _ctx("Restaurant_ID")
        location      = _ctx("Location")
        last_updated  = _ctx("Last_Updated")

        evidence = build_dish_evidence(
            dish_id=did,
            dish_name=dish_name,
            restaurant=restaurant,
            restaurant_id=restaurant_id,
            location=location,
            ingredient_rows=ingredient_rows,
            last_updated=last_updated,
        )

        conclusions = run_all_filters(evidence, FILTER_REGISTRY, freshness_map)

        # Freshness context for this dish (embedded in derived_filters.json output)
        frec = freshness_map.get(restaurant_id)
        freshness_context = frec.to_context_dict() if frec else {
            "recanvass_status":    "unknown",
            "source_check_status": "unknown",
            "last_canvassed":      None,
            "last_source_check":   None,
            "status_computed_date": TODAY,
        }

        results[did] = {
            "dish_id":       did,
            "dish_name":     dish_name,
            "restaurant":    restaurant,
            "restaurant_id": restaurant_id,
            "location":      location,
            "freshness":     freshness_context,
            "computed":      TODAY,
            "filters": {
                slug: conclusion.to_dict()
                for slug, conclusion in conclusions.items()
            },
        }

    # ── Report ─────────────────────────────────────────────────────────────────
    print(f"{'='*65}")
    print(f"DERIVED FILTER REPORT  —  {TODAY}")
    print(f"{'='*65}")

    for slug, fdef in FILTER_REGISTRY.items():
        computed_list      = []
        unknown_list       = []
        not_applicable_list = []

        for did, result in results.items():
            fc = result["filters"].get(slug)
            if not fc:
                continue
            entry = (did, result["dish_name"], result["restaurant"], fc)
            if fc["status"] == "computed":
                computed_list.append(entry)
            elif fc["status"] == "not_applicable":
                not_applicable_list.append(entry)
            else:
                unknown_list.append(entry)

        total = len(computed_list) + len(unknown_list) + len(not_applicable_list)

        print(f"\nFilter: {fdef.name}")
        print(f"  Dependency  : {fdef.dependency_type}")
        print(f"  Rules cited : {', '.join(fdef.rule_ids)}")
        print(f"  {'─'*55}")
        print(f"  Total dishes processed : {total}")
        print(f"  ✓ Computed             : {len(computed_list)}  (conclusion reached)")
        print(f"  ? Unknown              : {len(unknown_list)}  (insufficient evidence)")
        print(f"  — Not Applicable       : {len(not_applicable_list)}  (filter does not apply)")

        # ── Sample computed conclusions ────────────────────────────────────────
        if computed_list:
            print(f"\n  ── Sample computed conclusions (first 5 of {len(computed_list)}) ──")
            for did, dname, rname, fc in computed_list[:5]:
                print(f"\n  {did}  {dname}")
                print(f"         Restaurant : {rname}")
                print(f"         Conclusion : {fc['conclusion']}")
                print(f"         Evidence   : {fc['evidence_used'][0] if fc['evidence_used'] else '—'}")
                print(f"         Confidence : {fc['confidence']}")

        # ── Unknown breakdown ──────────────────────────────────────────────────
        if unknown_list:
            print(f"\n  ── Unknown cases ({len(unknown_list)}) — breakdown by reason ──")
            reason_buckets: dict[str, list] = defaultdict(list)
            for did, dname, rname, fc in unknown_list:
                r = fc.get("reasoning", "")
                if "No ingredient data" in r:
                    bucket = "No ingredient data (dish not yet canvassed)"
                elif "provenance is unverified" in r or "source provenance" in r:
                    bucket = "Ingredient_Source not verified (run backfill_enrichment.py)"
                elif "ambiguous" in r.lower() and "materiality test" in r.lower():
                    bucket = "Ambiguous ingredient(s) — materiality test fails"
                elif "dependency check" in r.lower():
                    bucket = "Dependency not met"
                else:
                    bucket = "Other"
                reason_buckets[bucket].append((did, dname, rname))

            for bucket, dishes in sorted(reason_buckets.items(), key=lambda x: -len(x[1])):
                print(f"\n    [{len(dishes):>3}]  {bucket}")
                for did, dname, rname in dishes[:4]:
                    print(f"            {did}  {dname[:40]:<40}  {rname}")
                if len(dishes) > 4:
                    print(f"            ... and {len(dishes)-4} more")

        # ── Not Applicable list ────────────────────────────────────────────────
        if not_applicable_list:
            print(f"\n  ── Not Applicable — filter does not apply ({len(not_applicable_list)}) ──")
            for did, dname, rname, fc in not_applicable_list[:8]:
                # Extract the first sentence of reasoning as a compact note
                reasoning_note = fc.get("reasoning", "").split(".")[0].strip()
                if len(reasoning_note) > 80:
                    reasoning_note = reasoning_note[:77] + "..."
                print(f"    {did}  {dname[:40]:<40}  ({reasoning_note})")
            if len(not_applicable_list) > 8:
                print(f"    ... and {len(not_applicable_list)-8} more")

        # ── Validation: every dish should have a status ────────────────────────
        statusless = [
            did for did, result in results.items()
            if not result["filters"].get(slug, {}).get("status")
        ]
        if statusless:
            print(f"\n  FAIL — {len(statusless)} dishes have no status for this filter:")
            for did in statusless[:5]:
                print(f"    {did}")
        else:
            print(f"\n  ✓ Validation: every dish has a filter status (no silent blanks).")

        # ── Architecture reusability note ──────────────────────────────────────
        print(f"\n  ── Pattern reusability ──")
        print(f"  The engine branches on dependency_type ('{fdef.dependency_type}'),")
        print(f"  not filter identity. To add the next macro_dependent filter:")
        print(f"    1. Write a compute_fn: (DishEvidence, FilterDefinition) → DerivedConclusion")
        print(f"    2. Define a FilterDefinition with dependency_type='macro_dependent'")
        print(f"    3. Add it to FILTER_REGISTRY in derived/registry.py")
        print(f"  Engine, dependency checker, and main script need no changes.")

    # ── Apply ──────────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    if DRY_RUN:
        print(f"DRY RUN COMPLETE.")
        print(f"  {len(results)} dishes processed across {len(FILTER_REGISTRY)} filter(s).")
        print(f"  No data written.")
        print(f"\n  To write derived_filters.json:")
        print(f"    python3 compute_derived_filters.py --apply")
        print(f"\n  After applying, integrate into fetch_dishes.py to embed derived")
        print(f"  conclusions into dishes.json.")
    else:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        size_kb = os.path.getsize(OUTPUT_FILE) / 1024
        print(f"WRITTEN: {OUTPUT_FILE}")
        print(f"  {len(results)} dishes × {len(FILTER_REGISTRY)} filter(s).")
        print(f"  File size: {size_kb:.1f} KB")
        print(f"\n  Next: integrate derived_filters.json into fetch_dishes.py so")
        print(f"  derived conclusions are embedded in the dishes.json output.")


if __name__ == "__main__":
    main()
