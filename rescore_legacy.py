"""
rescore_legacy.py — Correct legacy transparency_scores with component values > 25.

Background
----------
The canonical GoldPan scoring model (SCORING_ARCHITECTURE.md) is 0–25 per
component (total 0–100). Migration 008 relaxed the CHECK constraints to ≤ 100
so that Google-Sheet-era rows that accidentally exceeded 25 could migrate
without data loss.

This script finds every is_current=true row where any component > 25, clamps
each offending component to 25, and writes the corrected values back to
Supabase.  total_score is a GENERATED column and recomputes automatically.

Clamping strategy
-----------------
The legacy over-scores are small overruns on a 0–25 intended scale
(e.g. core_clarity = 28, not 280).  "Score 28 out of 25" means the scorer
intended the maximum — clamping to 25 is the correct canonical interpretation.
We do NOT rescale (e.g. ÷ 4) because that would penalise dishes that were
intentionally given the highest possible score.

Usage
-----
    python3 rescore_legacy.py             # dry run — print report, no writes
    python3 rescore_legacy.py --apply     # apply corrections to Supabase
    python3 rescore_legacy.py --save      # dry run + save report to docs/

Prerequisites
-------------
    pip install supabase python-dotenv --break-system-packages
    .env must contain SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.
"""

import os
import sys
import datetime
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

APPLY = "--apply" in sys.argv
SAVE  = "--save"  in sys.argv

COMPONENTS = [
    "core_clarity",
    "sauce_seasoning_disclosure",
    "allergen_transparency",
    "prep_clarity",
]

CAP = 25
TODAY = datetime.date.today().isoformat()


# ── Helpers ───────────────────────────────────────────────────────────────────

def clamp(val, lo=0, hi=CAP):
    return max(lo, min(hi, float(val)))


def needs_correction(row: dict) -> bool:
    return any(float(row[c]) > CAP for c in COMPONENTS)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )

    # Fetch all current scores
    res = (
        sb.schema("knowledge")
        .table("transparency_scores")
        .select(
            "score_id,dish_external_id,restaurant_external_id,"
            "core_clarity,sauce_seasoning_disclosure,"
            "allergen_transparency,prep_clarity,"
            "total_score,transparency_level,scoring_notes"
        )
        .eq("is_current", True)
        .execute()
    )
    rows = res.data
    affected = [r for r in rows if needs_correction(r)]

    mode = "APPLY" if APPLY else "DRY RUN"
    lines = [
        f"# rescore_legacy.py — {mode}  —  {TODAY}",
        "",
        f"Scanned {len(rows)} is_current transparency_scores rows.",
        f"Rows with any component > {CAP}: **{len(affected)}**",
        "",
    ]

    if not affected:
        msg = "No out-of-range components found. Nothing to do."
        print(msg)
        lines.append(msg)
        if SAVE:
            _save(lines)
        return

    lines += [
        "## Corrections",
        "",
        "Strategy: clamp each component to min(value, 25).",
        "total_score is a PostgreSQL GENERATED column — recomputed automatically.",
        "",
    ]

    corrections = []
    for r in sorted(affected, key=lambda x: x["dish_external_id"]):
        old = {c: float(r[c]) for c in COMPONENTS}
        new = {c: clamp(float(r[c])) for c in COMPONENTS}
        old_total = float(r["total_score"])
        new_total = sum(new.values())
        changed = {c: (old[c], new[c]) for c in COMPONENTS if old[c] != new[c]}

        entry = {
            "score_id":               r["score_id"],
            "dish_external_id":       r["dish_external_id"],
            "restaurant_external_id": r["restaurant_external_id"],
            "new_values":             new,
            "old_total":              old_total,
            "new_total":              new_total,
            "changed":                changed,
        }
        corrections.append(entry)

        lines.append(f"### {r['dish_external_id']}  ({r['restaurant_external_id']})")
        for comp, (o, n) in changed.items():
            over = o - CAP
            lines.append(f"- **{comp}**: {o} → {n}  *(was {over:.0f} over cap)*")
        lines.append(f"- total_score: {old_total:.0f} → {new_total:.0f}")
        if r.get("scoring_notes"):
            lines.append(f"- notes: {str(r['scoring_notes'])[:120]}")
        lines.append("")

    lines += [
        "---",
        "",
        f"**Total dishes corrected: {len(corrections)}**",
        "",
    ]

    if APPLY:
        print(f"Applying {len(corrections)} corrections to Supabase ...")
        errors = []
        for entry in corrections:
            try:
                (
                    sb.schema("knowledge")
                    .table("transparency_scores")
                    .update({c: entry["new_values"][c] for c in COMPONENTS})
                    .eq("score_id", entry["score_id"])
                    .execute()
                )
                print(f"  ✓  {entry['dish_external_id']}")
            except Exception as exc:
                msg = f"  ✗  {entry['dish_external_id']}: {exc}"
                print(msg)
                errors.append(msg)

        if errors:
            lines.append("## Errors during apply")
            lines.extend(errors)
            lines.append("")
            print(f"\n{len(errors)} error(s). See above.")
        else:
            ok_msg = f"All {len(corrections)} corrections applied successfully."
            lines.append(ok_msg)
            print(f"\n{ok_msg}")
            lines += [
                "",
                "## Next step",
                "",
                "Apply supabase/migrations/014_restore_score_constraints.sql in the Supabase",
                "SQL editor to tighten the CHECK constraints back to <= 25.",
            ]
    else:
        lines += [
            "## Next steps",
            "",
            "1. Review the corrections above.",
            "2. Run `python3 rescore_legacy.py --apply` to write them to Supabase.",
            "3. Apply supabase/migrations/014_restore_score_constraints.sql in the",
            "   Supabase SQL editor to restore the CHECK constraints to <= 25.",
        ]

    report = "\n".join(lines)
    print("\n" + report)

    if SAVE:
        _save(lines)


def _save(lines):
    path = "docs/RESCORE_LEGACY_REPORT.md"
    os.makedirs("docs", exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nReport saved to {path}")


if __name__ == "__main__":
    main()
