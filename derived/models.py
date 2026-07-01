"""
derived/models.py
GoldPan derived filter data models.

DerivedConclusion — the four-part explanation object required by GP-RULE-006
                    (Derived Filter Explanation Rule).
DishEvidence      — the verified evidence available for one dish; used by the
                    dependency checker (GP-RULE-007) to decide whether to compute.
FilterDefinition  — declares a filter's name, slug, evidence dependency type,
                    citing rules, and compute function.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, List


@dataclass
class DerivedConclusion:
    """
    The structured result of one derived filter for one dish.
    Required by GP-RULE-006 (Derived Filter Explanation Rule v1.0).

    Every filter result — whether computed, unknown, or not applicable —
    must carry all four explanation components. A conclusion without
    an explanation object is an architectural violation.

    Possible (conclusion, status, confidence) combinations:
      ("No Beef Identified", "computed",        "verified")   — conclusion reached
      ("Unknown",            "unknown",          "unknown")    — insufficient evidence
      ("Not Applicable",     "not_applicable",   "verified")   — filter doesn't apply (beef IS present)
    """
    conclusion:   str         # e.g. "No Beef Identified" | "Unknown" | "Not Applicable"
    evidence_used: List[str]  # Specific verified sources that supported this conclusion
    reasoning:    str         # Named rule(s) + plain-language explanation
    limitations:  str         # Boundaries of the conclusion (from rule standard language)
    rule_ids:     List[str]   # Rule IDs cited, e.g. ["GP-RULE-001", "GP-RULE-002"]
    confidence:   str         # "verified" | "unknown" | "not_applicable"
    status:       str         # "computed" | "unknown" | "not_applicable"

    def to_dict(self) -> dict:
        return {
            "conclusion":    self.conclusion,
            "evidence_used": self.evidence_used,
            "reasoning":     self.reasoning,
            "limitations":   self.limitations,
            "rule_ids":      self.rule_ids,
            "confidence":    self.confidence,
            "status":        self.status,
        }


@dataclass
class DishEvidence:
    """
    The verified evidence available for one dish at compute time.

    The dependency checker in engine.py reads this to decide whether the
    available evidence satisfies a filter's declared dependency type
    (GP-RULE-007, Filter Evidence Dependency Rule v1.0).

    restaurant_id is used by the engine to look up the restaurant's
    FreshnessRecord in the freshness_map passed to run_filter / run_all_filters.
    """
    dish_id:                  str
    dish_name:                str
    restaurant:               str
    restaurant_id:            str          # ← used for freshness gate (GP-RULE-008)
    location:                 str
    ingredients:              List[dict]   # Raw rows from Ingredient Details
    has_verified_ingredients: bool         # True if ≥1 ingredient has a verified Ingredient_Source
    verified_sources:         List[str]    # Human-readable source descriptions for evidence_used


@dataclass
class FilterDefinition:
    """
    Declares a derived filter and its evidence dependency.

    The engine uses dependency_type — not hardcoded per-filter logic — to
    determine whether available evidence is sufficient to compute a result.
    Per GP-RULE-007 (Filter Evidence Dependency Rule v1.0).

    dependency_type values:
      "macro_dependent"             — verified primary ingredient list required
      "mixed_dependent"             — primary ingredients + additional context required
      "micro_dependent"             — official allergen/micro documentation required
      "restaurant_claim_dependent"  — explicit restaurant claim required
    """
    name:                str           # "No Beef Identified"
    slug:                str           # "no-beef-identified"
    dependency_type:     str           # one of the four types above
    rule_ids:            List[str]     # Rules invoked when computing this filter
    description:         str           # What this filter computes
    standard_limitations: str          # Standard limitation language for all conclusions
    compute_fn:          Callable      # (DishEvidence, FilterDefinition) → DerivedConclusion
