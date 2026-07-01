"""
migrate_scoring.py — Convert legacy normalized (0-10) scoring to canonical (0-25).

GoldPan canonical scoring model (per docs/SCORING_ARCHITECTURE.md):
  Core Ingredient Clarity:     0-25
  Sauce & Seasoning Disclosure: 0-25
  Allergen Transparency:        0-25
  Preparation Input Clarity:    0-25
  Total Score:                  0-100  (= sum of four components)

Legacy normalized model (to be retired):
  Components stored on 0-10 scale.
  total_score = round(sum(components) / 40 * 100)

Conversion formula: canonical = floor(legacy * 2.5 + 0.5)
  This is "round half up" — 0→0, 1→3, 2→5, 3→8, 4→10, 5→13,
                            6→15, 7→18, 8→20, 9→23, 10→25

Dry-run by default. Shows every change before writing.
Use --apply to write changes to disk.

Unrecognized scoring models (components 0-10 but total doesn't follow
the normalized formula) are flagged for manual review and NOT auto-migrated.

Usage:
  python3 migrate_scoring.py                     # dry-run on all staging files
  python3 migrate_scoring.py staging_chopt.json  # dry-run on one file
  python3 migrate_scoring.py --apply             # apply to all staging files
  python3 migrate_scoring.py staging_chopt.json --apply
"""

import json
import sys
import glob
import os
import math
import datetime


COMP_FIELDS = ["core_clarity", "sauce_disclosure", "allergen_transparency", "prep_clarity"]
TODAY = datetime.date.today().isoformat()
DRY_RUN = "--apply" not in sys.argv
non_flag_args = [a for a in sys.argv[1:] if not a.startswith("--")]


# ── Scoring model detection ───────────────────────────────────────────────────

def detect_model(dish: dict) -> str:
    if not all(f in dish for f in COMP_FIELDS) or "total_score" not in dish:
        return "absent"
    comps = [dish[f] for f in COMP_FIELDS]
    total = dish["total_score"]
    if not all(isinstance(c, (int, float)) for c in comps):
        return "absent"
    if sum(comps) == total:
        return "additive"
    if max(comps) <= 10:
        norm = round(sum(comps) / 40 * 100)
        if abs(norm - total) <= 1:
            return "normalized"
        return "unrecognized"
    return "unrecognized"


def to_canonical(x: float) -> int:
    """Convert a 0-10 component score to 0-25 canonical scale (round half up)."""
    return math.floor(x * 2.5 + 0.5)


# ── File migration ────────────────────────────────────────────────────────────

def migrate_file(fp: str, dry_run: bool) -> dict:
    """
    Migrate one staging file. Returns a summary dict.

    Summary keys:
      file, restaurant, dishes_canonical, dishes_migrated,
      dishes_unrecognized, dishes_absent, changes
    """
    with open(fp, "r", encoding="utf-8") as f:
        data = json.load(f)

    rname = data.get("restaurant_name", data.get("restaurant_note", "(unknown)"))
    summary = {
        "file": fp,
        "restaurant": rname,
        "dishes_canonical": 0,
        "dishes_migrated": 0,
        "dishes_unrecognized": 0,
        "dishes_absent": 0,
        "changes": [],       # list of change dicts for the report
        "manual_review": [], # dish IDs that need manual review
    }

    modified = False
    for dish in data.get("dishes", []):
        model = detect_model(dish)
        did   = dish.get("dish_id", "???")
        dname = dish.get("dish_name", "")

        if model == "additive":
            summary["dishes_canonical"] += 1

        elif model == "normalized":
            old_comps = [dish[f] for f in COMP_FIELDS]
            old_total = dish["total_score"]
            new_comps = [to_canonical(c) for c in old_comps]
            new_total = sum(new_comps)

            change = {
                "dish_id":   did,
                "dish_name": dname,
                "fields":    {},
            }
            for field, old, new in zip(COMP_FIELDS, old_comps, new_comps):
                change["fields"][field] = {"old": old, "new": new}
            change["fields"]["total_score"] = {"old": old_total, "new": new_total}
            summary["changes"].append(change)
            summary["dishes_migrated"] += 1

            if not dry_run:
                for field, new in zip(COMP_FIELDS, new_comps):
                    dish[field] = new
                dish["total_score"] = new_total
                modified = True

        elif model == "unrecognized":
            summary["dishes_unrecognized"] += 1
            summary["manual_review"].append({
                "dish_id":   did,
                "dish_name": dname,
                "comps":     [dish.get(f) for f in COMP_FIELDS],
                "total":     dish.get("total_score"),
            })

        else:  # absent
            summary["dishes_absent"] += 1

    if modified and not dry_run:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return summary


# ── Report printing ───────────────────────────────────────────────────────────

def print_file_report(s: dict, dry_run: bool):
    mode = "DRY RUN" if dry_run else "APPLIED"
    fname = os.path.basename(s["file"])
    print(f"\n{'=' * 68}")
    print(f"  {fname}  [{mode}]")
    print(f"  Restaurant: {s['restaurant']}")
    print(f"  Canonical (no change): {s['dishes_canonical']}")
    print(f"  Migrated (normalized → 0-25): {s['dishes_migrated']}")
    print(f"  Flagged for manual review: {s['dishes_unrecognized']}")
    print(f"  No scoring (absent):  {s['dishes_absent']}")

    if s["changes"]:
        print(f"\n  {'─' * 64}")
        print(f"  Conversion plan — normalized → canonical (0-25 scale):")
        print(f"  {'─' * 64}")
        for c in s["changes"]:
            print(f"\n  {c['dish_id']}  {c['dish_name']}")
            for field in COMP_FIELDS:
                fc = c["fields"][field]
                arrow = f"{fc['old']:>3} → {fc['new']:>2}"
                label = field.replace("_", " ").title()
                print(f"    {label:30} {arrow}")
            tf = c["fields"]["total_score"]
            delta = tf["new"] - tf["old"]
            delta_str = f"(Δ {delta:+d})" if delta != 0 else "(unchanged)"
            print(f"    {'Total Score':30} {tf['old']:>3} → {tf['new']:>2}  {delta_str}")

    if s["manual_review"]:
        print(f"\n  {'─' * 64}")
        print(f"  ⚠  Manual review required — unrecognized scoring model:")
        print(f"     These dishes have 0-10 components but the total does not")
        print(f"     follow the normalized formula. Auto-migration is not safe.")
        print(f"  {'─' * 64}")
        for d in s["manual_review"]:
            comp_str = " + ".join(str(c) for c in d["comps"])
            print(f"    {d['dish_id']}  {d['dish_name'][:40]:40}")
            print(f"         comps: {comp_str} = {sum(d['comps'])}  total: {d['total']}")


def print_overall_summary(summaries: list, dry_run: bool):
    mode = "DRY RUN COMPLETE" if dry_run else "MIGRATION COMPLETE"
    total_canonical    = sum(s["dishes_canonical"] for s in summaries)
    total_migrated     = sum(s["dishes_migrated"] for s in summaries)
    total_unrecognized = sum(s["dishes_unrecognized"] for s in summaries)
    total_absent       = sum(s["dishes_absent"] for s in summaries)
    files_with_changes = [s for s in summaries if s["changes"]]
    files_manual       = [s for s in summaries if s["manual_review"]]

    print(f"\n{'=' * 68}")
    print(f"  {mode}  —  {TODAY}")
    print(f"  Files processed:              {len(summaries)}")
    print(f"  Files with migrations:        {len(files_with_changes)}")
    print(f"  Files needing manual review:  {len(files_manual)}")
    print(f"  ─────────────────────────────────")
    print(f"  Dishes already canonical:     {total_canonical}")
    print(f"  Dishes migrated (0-10→0-25):  {total_migrated}")
    print(f"  Dishes needing manual review: {total_unrecognized}")
    print(f"  Dishes without scoring:       {total_absent}")

    if dry_run and total_migrated > 0:
        print(f"\n  To apply these conversions:")
        print(f"    python3 migrate_scoring.py --apply")

    if files_manual:
        print(f"\n  Files requiring manual scoring review:")
        for s in files_manual:
            print(f"    {os.path.basename(s['file'])}  ({len(s['manual_review'])} dish(es))")
        print(f"\n  For each flagged dish: re-score components on the 0-25 scale")
        print(f"  so that total_score = sum(components). See docs/SCORING_ARCHITECTURE.md.")

    print(f"{'=' * 68}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    mode_label = "DRY RUN" if DRY_RUN else "APPLYING"
    print(f"migrate_scoring.py  —  {TODAY}  [{mode_label}]")

    if non_flag_args:
        files = non_flag_args
    else:
        files = sorted(glob.glob(
            os.path.join(os.path.dirname(__file__) or ".", "staging*.json")
        ))

    if not files:
        print("No staging files found.")
        sys.exit(0)

    summaries = []
    for fp in files:
        if not os.path.exists(fp):
            print(f"\n  ✗  {fp}: file not found")
            continue
        s = migrate_file(fp, dry_run=DRY_RUN)
        print_file_report(s, dry_run=DRY_RUN)
        summaries.append(s)

    if summaries:
        print_overall_summary(summaries, dry_run=DRY_RUN)


if __name__ == "__main__":
    main()
