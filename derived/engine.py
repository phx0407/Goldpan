"""
derived/engine.py
GoldPan derived filter evaluation engine.

Responsibilities:
  1. Assemble DishEvidence from raw Ingredient Details rows
  2. Gate 0: Check Recanvass_Status (GP-RULE-008 v1.1) — the freshness gate
  3. Gate 1: Check dependency type (GP-RULE-007)
  4. Gate 2: Apply GP-RULE-001 materiality test (inside compute_fn)
  5. Call the filter's compute_fn if all gates pass
  6. Post-compute: apply confidence cap for overdue evidence (GP-RULE-009)
  7. Return a structured Unknown with explanation if any gate fails

Contract:
  - The engine reads only Recanvass_Status (the synthesized verdict).
  - It does not read Source_Check_Status or any raw freshness detail.
  - freshness.py synthesizes the signal; the engine consumes it.
  - GP-RULE-009 handles confidence degradation post-compute.

The engine branches on dependency_type and recanvass_status, never on filter
identity or source-check details. No special-case logic per individual filter.
"""

from __future__ import annotations
from collections import defaultdict
from typing import TYPE_CHECKING

from .models import DerivedConclusion, DishEvidence, FilterDefinition
from schema import MACRO_ELIGIBLE_SOURCES

if TYPE_CHECKING:
    from freshness import FreshnessRecord


# ── Evidence assembly ─────────────────────────────────────────────────────────

def build_dish_evidence(
    dish_id: str,
    dish_name: str,
    restaurant: str,
    restaurant_id: str,
    location: str,
    ingredient_rows: list[dict],
    last_updated: str = "",
) -> DishEvidence:
    """
    Assemble a DishEvidence object from raw Ingredient Details rows.

    Determines has_verified_ingredients by checking whether at least one
    ingredient row has Ingredient_Source in the MACRO_ELIGIBLE_SOURCES set.
    Builds human-readable verified_sources strings for use in evidence_used
    fields of DerivedConclusion objects.
    """
    skip = {"building transparency", "ingredient detail pending confirmation", "none", ""}
    active_rows = [
        r for r in ingredient_rows
        if str(r.get("Ingredient", "")).strip().lower() not in skip
    ]

    verified_rows = [
        r for r in active_rows
        if str(r.get("Ingredient_Source", "")).strip().lower() in MACRO_ELIGIBLE_SOURCES
    ]
    has_verified = len(verified_rows) > 0

    sources: list[str] = []
    if has_verified:
        # Summarize unique source values and produce a single readable string
        unique_src: dict[str, int] = defaultdict(int)
        for r in verified_rows:
            unique_src[str(r.get("Ingredient_Source", "")).strip().lower()] += 1
        src_summary = ", ".join(
            f"{src} ({cnt} ingredient{'s' if cnt != 1 else ''})"
            for src, cnt in sorted(unique_src.items())
        )
        when = f", last updated {last_updated}" if last_updated else ""
        sources.append(
            f"Verified ingredient list — {restaurant}{when}. "
            f"Source(s): {src_summary}. "
            f"{len(active_rows)} ingredient(s) disclosed."
        )
    elif active_rows:
        unverified_srcs = set(
            str(r.get("Ingredient_Source", "")).strip() or "blank"
            for r in active_rows
        )
        sources.append(
            f"Ingredient list present for {restaurant} "
            f"({len(active_rows)} ingredient(s)) but source provenance is unverified. "
            f"Ingredient_Source value(s): {', '.join(sorted(unverified_srcs))}. "
            f"Evidence quality: insufficient for macro_dependent filters."
        )
    else:
        sources.append(
            f"No ingredient data available for {dish_name} ({dish_id}) at {restaurant}."
        )

    return DishEvidence(
        dish_id=dish_id,
        dish_name=dish_name,
        restaurant=restaurant,
        restaurant_id=restaurant_id,
        location=location,
        ingredients=active_rows,
        has_verified_ingredients=has_verified,
        verified_sources=sources,
    )


# ── Dependency checker ────────────────────────────────────────────────────────

def check_dependency(
    filter_def: FilterDefinition,
    evidence: DishEvidence,
) -> tuple[bool, str]:
    """
    Returns (can_compute: bool, reason: str).

    Implements GP-RULE-007 (Filter Evidence Dependency Rule v1.0).
    Branches on filter_def.dependency_type — never on filter identity.
    """
    dep = filter_def.dependency_type

    if dep == "macro_dependent":
        if not evidence.ingredients:
            return False, (
                "No ingredient data exists for this dish. "
                "A verified primary ingredient list is required for macro_dependent filters "
                "(GP-RULE-001, Material Evidence Rule v1.1)."
            )
        if not evidence.has_verified_ingredients:
            return False, (
                f"Ingredient list present ({len(evidence.ingredients)} ingredient(s)) "
                f"but no ingredient has a verified Ingredient_Source "
                f"(expected: {sorted(MACRO_ELIGIBLE_SOURCES)}). "
                f"Evidence quality is insufficient for a macro_dependent filter. "
                f"Run backfill_enrichment.py --apply to populate Ingredient_Source, "
                f"or canvass this dish from the live menu."
            )
        return True, (
            f"Verified primary ingredient list available — "
            f"{len(evidence.ingredients)} ingredient(s)."
        )

    if dep == "mixed_dependent":
        return False, (
            "mixed_dependent filters require verified primary ingredient disclosures "
            "plus at least one additional evidence type (e.g. preparation method, "
            "dietary certification). This dependency type is not yet implemented. "
            "Define the additional evidence check when implementing the first "
            "mixed_dependent filter."
        )

    if dep == "micro_dependent":
        return False, (
            "micro_dependent filters require explicit official allergen or "
            "micro-ingredient documentation for this specific dish "
            "(GP-RULE-003, Undisclosed Ingredient Rule v1.1). "
            "Verified primary ingredient disclosure alone is insufficient."
        )

    if dep == "restaurant_claim_dependent":
        return False, (
            "restaurant_claim_dependent filters require an explicit, verified "
            "restaurant claim recorded for this dish "
            "(GP-RULE-004, Supporting Documents Rule v1.0). "
            "Verified primary ingredient disclosure alone is insufficient."
        )

    return False, (
        f"Unknown dependency_type '{dep}'. "
        f"Valid types: macro_dependent, mixed_dependent, micro_dependent, "
        f"restaurant_claim_dependent. Update the filter definition in registry.py."
    )


# ── Filter runner ─────────────────────────────────────────────────────────────

def run_filter(
    filter_def: FilterDefinition,
    evidence: DishEvidence,
    freshness_map: dict | None = None,
) -> DerivedConclusion:
    """
    Run one filter for one dish.

    Gate 0 — Freshness (GP-RULE-008 v1.1):
        Read Recanvass_Status from freshness_map.
        needs_review / unknown → suppress all conclusions, return Unknown.
        overdue → proceed, then cap confidence to "likely" post-compute (GP-RULE-009).
        current / due_soon → proceed normally.

    Gate 1 — Dependency type (GP-RULE-007):
        Check whether available evidence satisfies the filter's dependency.

    Gate 2 — Materiality test (GP-RULE-001):
        Applied inside compute_fn.

    Post-compute — Confidence cap (GP-RULE-009):
        If Recanvass_Status is "overdue", cap confidence at "likely".

    The engine reads only Recanvass_Status. It does not inspect
    Source_Check_Status or any other raw freshness detail.
    freshness.py synthesizes the signal; this engine consumes it.
    """
    # ── Gate 0 — Freshness (GP-RULE-008 v1.1) ────────────────────────────────
    fm = freshness_map or {}
    rec = fm.get(evidence.restaurant_id)
    recanvass_status = rec.status if rec else "unknown"

    if recanvass_status in ("needs_review", "unknown"):
        trigger_detail = (
            ("; ".join(rec.triggers[:2]) if rec and rec.triggers else "freshness record missing")
        )
        return DerivedConclusion(
            conclusion="Unknown",
            evidence_used=[],
            reasoning=(
                f"Derived conclusion suppressed by freshness gate (GP-RULE-008 v1.1). "
                f"Recanvass_Status: '{recanvass_status}'. "
                f"Reason: {trigger_detail}. "
                f"Conclusions for this restaurant's dishes are suppressed until "
                f"the recanvass review is resolved."
            ),
            limitations=(
                "All derived conclusions are suppressed for this restaurant's dishes "
                "until Recanvass_Status returns to 'current', 'due_soon', or 'overdue'. "
                + filter_def.standard_limitations
            ),
            rule_ids=["GP-RULE-008"],
            confidence="unknown",
            status="unknown",
        )

    # ── Gate 1 — Dependency type (GP-RULE-007) ────────────────────────────────
    can_compute, dep_reason = check_dependency(filter_def, evidence)

    if not can_compute:
        return DerivedConclusion(
            conclusion="Unknown",
            evidence_used=evidence.verified_sources,
            reasoning=(
                f"Per GP-RULE-007 (Filter Evidence Dependency Rule v1.0), this filter "
                f"declared dependency type '{filter_def.dependency_type}'. "
                f"Dependency check: {dep_reason}"
            ),
            limitations=filter_def.standard_limitations,
            rule_ids=filter_def.rule_ids,
            confidence="unknown",
            status="unknown",
        )

    # ── Gate 2 + Compute (GP-RULE-001, filter-specific logic) ─────────────────
    result = filter_def.compute_fn(evidence, filter_def)

    # ── Post-compute: Confidence cap (GP-RULE-009) ────────────────────────────
    if recanvass_status == "overdue" and result.confidence == "verified":
        days_overdue  = rec.days_overdue  if rec else "?"
        last_canvassed = rec.last_canvassed if rec else "unknown"
        window        = rec.recanvass_window if rec else "?"
        result.confidence = "likely"
        result.reasoning += (
            f" Evidence quality supports 'verified', but Recanvass_Status is 'overdue' "
            f"(last canvassed: {last_canvassed}, {days_overdue} days past the "
            f"{window}-day recanvass window). Per GP-RULE-009 (Stale Evidence "
            f"Confidence Degradation Rule v1.0), confidence is capped at 'likely'."
        )
        if "GP-RULE-009" not in result.rule_ids:
            result.rule_ids = list(result.rule_ids) + ["GP-RULE-009"]

    elif recanvass_status == "due_soon" and rec:
        staleness_note = (
            f" Note: This restaurant's menu data is approaching its scheduled "
            f"recanvass date (last canvassed: {rec.last_canvassed}, "
            f"{rec.days_remaining} days remaining in the {rec.recanvass_window}-day window)."
        )
        result.limitations = (result.limitations or "") + staleness_note
        if "GP-RULE-008" not in result.rule_ids:
            result.rule_ids = list(result.rule_ids) + ["GP-RULE-008"]

    return result


def run_all_filters(
    evidence: DishEvidence,
    registry: dict[str, FilterDefinition],
    freshness_map: dict | None = None,
) -> dict[str, DerivedConclusion]:
    """
    Run every registered filter for one dish.

    freshness_map: {restaurant_id: FreshnessRecord} — produced by freshness.py
    and passed in by compute_derived_filters.py. Pass None (or omit) to skip
    the freshness gate (e.g. in unit tests that don't need freshness).

    Returns {slug: DerivedConclusion}.
    """
    return {
        slug: run_filter(fdef, evidence, freshness_map)
        for slug, fdef in registry.items()
    }
