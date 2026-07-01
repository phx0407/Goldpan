"""
derived/registry.py
GoldPan filter registry.

Defines each named filter, its evidence dependency, and its compute function.
Adding a new filter: define a FilterDefinition + compute_fn, then add it to
FILTER_REGISTRY. No changes to the engine are required.

Current filters:
  no-beef-identified                   (macro_dependent)  — GP-RULE-001..007
  no-pork-identified                   (macro_dependent)  — GP-RULE-001..007
  no-wheat-ingredients-identified      (macro_dependent)  — GP-RULE-001..007, 014..016
  no-milk-ingredients-identified       (macro_dependent)  — GP-RULE-001..007, 014..016
  no-egg-ingredients-identified        (macro_dependent)  — GP-RULE-001..007, 014..016
  no-soy-ingredients-identified        (macro_dependent)  — GP-RULE-001..007, 014..016
  no-sesame-ingredients-identified     (macro_dependent)  — GP-RULE-001..007, 014..016
  no-peanut-ingredients-identified     (macro_dependent)  — GP-RULE-001..007, 014..016
  no-tree-nut-ingredients-identified   (macro_dependent)  — GP-RULE-001..007, 014..016
  no-fish-ingredients-identified       (macro_dependent)  — GP-RULE-001..007, 014..016
  no-shellfish-ingredients-identified  (macro_dependent)  — GP-RULE-001..007, 014..016

Allergen filter architecture (GP-RULE-014, GP-RULE-015, GP-RULE-016):
  Allergen filters use Allergen_Flags (Evidence System field) as read-only input.
  The engine never writes or backfills Allergen_Flags.
  Blank Allergen_Flags = absence of evidence → Unknown (not absence of allergen).
  "none" = canvasser explicitly recorded no allergen flags → contributes to computed result.
  Confidence ceiling for all allergen filter outcomes: "inferred" (GP-RULE-015).
  Consumer-facing label for computed results governed by GP-RULE-016 (not this file).
"""

from __future__ import annotations
from .models import DerivedConclusion, DishEvidence, FilterDefinition


# ── Beef detection vocabulary ─────────────────────────────────────────────────
#
# Design principle (GP-RULE-001 materiality test): err toward Unknown rather
# than false confidence. A wrong "No Beef Identified" is worse than an honest
# "Unknown." When in doubt, the ingredient goes in AMBIGUOUS_MEAT_TERMS.
#
# BEEF_TERMS
#   Substrings that unambiguously indicate beef presence in an ingredient name.
#   Match → beef IS present → filter returns "Not Applicable."
#
# AMBIGUOUS_MEAT_TERMS
#   Substrings that could plausibly include beef but aren't definitive.
#   Match (without a resolving qualifier) → materiality test fails → "Unknown."
#
# NON_BEEF_QUALIFIERS
#   If an AMBIGUOUS_MEAT_TERMS match also contains one of these in the same
#   ingredient name, the ambiguity resolves to non-beef and the ingredient is
#   treated as clear. e.g. "turkey meatballs" → not ambiguous.

BEEF_TERMS: frozenset = frozenset([
    "beef",
    "ground beef",
    "beef patty",
    "beef brisket",
    "beef tenderloin",
    "beef burger",
    "brisket",          # almost always beef; "chicken brisket" is too rare to hedge
    "ribeye",
    "rib-eye",
    "rib eye",
    "sirloin",
    "filet mignon",
    "flank steak",
    "chuck",            # as a standalone or in "chuck roast", "chuck steak"
    "wagyu",
    "short rib",
    "short ribs",
    "skirt steak",
    "hanger steak",
    "new york strip",
    "t-bone",
    "porterhouse",
    "tri-tip",
    "corned beef",
    "beef tallow",
    "oxtail",
    "veal",             # veal is beef (calf)
])

AMBIGUOUS_MEAT_TERMS: frozenset = frozenset([
    "meat",             # unqualified — could be any animal
    "protein",          # unqualified — too generic to classify
    "meat sauce",       # commonly beef-based; no way to confirm without disclosure
    "bolognese",        # traditionally beef; veg variants exist
    "ragu",             # often beef
    "meatball",         # could be beef, pork, turkey, or mixed
    "meatballs",
    "steak",            # typically beef but "tuna steak", "swordfish steak" exist
    "pastrami",         # traditionally beef; turkey and vegan variants common enough
    "braised meat",
    "slow-cooked meat",
    "house meat",
    "mixed meat",
    "smoked meat",      # could be brisket (beef) or pulled pork
])

NON_BEEF_QUALIFIERS: frozenset = frozenset([
    "turkey", "chicken", "pork", "lamb", "fish", "tuna", "salmon",
    "swordfish", "vegan", "vegetarian", "plant-based", "impossible",
    "beyond", "tofu", "meatless",
])


def _name(row: dict) -> str:
    """Normalized ingredient name from a raw Ingredient Details row."""
    return str(row.get("Ingredient", "")).strip().lower()


def _matches_any(text: str, terms: frozenset) -> bool:
    """True if text contains any term as a substring."""
    return any(t in text for t in terms)


def _resolved_by_qualifier(name: str) -> bool:
    """
    True if name contains an AMBIGUOUS_MEAT_TERMS hit that is resolved to
    non-beef by the presence of a NON_BEEF_QUALIFIER in the same ingredient name.
    e.g. "turkey meatballs" → True (safe); "meatballs" → False (still ambiguous).
    """
    return _matches_any(name, NON_BEEF_QUALIFIERS)


# ── No Beef Identified — compute function ─────────────────────────────────────

def _compute_no_beef_identified(
    evidence: DishEvidence,
    filter_def: FilterDefinition,
) -> DerivedConclusion:
    """
    Compute "No Beef Identified" for one dish.

    Outcome matrix:
      Beef term found AND no qualifier     → "Not Applicable" (beef IS present)
      Beef term found BUT qualifier present→ treat as clear (e.g. "vegan beef")
      Ambiguous term found (unresolved)    → "Unknown" (materiality test fails)
      Ambiguous term found + qualifier     → treat as clear (e.g. "turkey meatballs")
      No beef or unresolved ambiguity      → "No Beef Identified"

    Qualifier resolution applies to BOTH BEEF_TERMS and AMBIGUOUS_MEAT_TERMS hits.
    A NON_BEEF_QUALIFIER in the same ingredient string overrides a beef-term match.
    Examples that resolve to clear (non-beef):
      "vegan beef", "plant-based beef", "impossible beef", "beyond beef", "meatless beef"
    Examples that remain beef:
      "beef", "roast beef", "angus beef", "beef brisket", "brisket"

    Cites:
      GP-RULE-001 (Material Evidence Rule v1.1)    — materiality test
      GP-RULE-002 (Disclosed Absence Rule v1.1)    — reasoning from absence
      GP-RULE-006 (Derived Filter Explanation Rule) — explanation structure
      GP-RULE-007 (Filter Evidence Dependency Rule) — dependency check (done in engine)
    """
    beef_found      = []
    ambiguous_found = []

    for row in evidence.ingredients:
        name = _name(row)
        if not name:
            continue
        raw = row.get("Ingredient", name)

        if _matches_any(name, BEEF_TERMS):
            if _resolved_by_qualifier(name):
                continue   # "vegan beef", "plant-based beef" etc — not beef
            beef_found.append(raw)
            continue   # unqualified beef term — definitive

        if _matches_any(name, AMBIGUOUS_MEAT_TERMS):
            if not _resolved_by_qualifier(name):
                ambiguous_found.append(raw)

    # ── Beef IS present → Not Applicable ─────────────────────────────────────
    if beef_found:
        return DerivedConclusion(
            conclusion="Not Applicable",
            evidence_used=evidence.verified_sources,
            reasoning=(
                f"Beef ingredient(s) identified in the verified ingredient list: "
                f"{', '.join(repr(i) for i in beef_found)}. "
                f"The 'No Beef Identified' filter does not apply to dishes that contain beef."
            ),
            limitations=filter_def.standard_limitations,
            rule_ids=filter_def.rule_ids,
            confidence="verified",
            status="not_applicable",
        )

    # ── Ambiguous compound ingredient(s) → Unknown ────────────────────────────
    if ambiguous_found:
        return DerivedConclusion(
            conclusion="Unknown",
            evidence_used=evidence.verified_sources,
            reasoning=(
                f"Per GP-RULE-001 (Material Evidence Rule v1.1), GoldPan applies the "
                f"materiality test: could missing evidence change this conclusion? "
                f"The following ingredient(s) are ambiguous and could plausibly contain beef: "
                f"{', '.join(repr(i) for i in ambiguous_found)}. "
                f"Absence from the disclosed list is not informative for these terms "
                f"(per GP-RULE-002, Disclosed Absence Rule v1.1 — absence is only "
                f"informative when disclosure is expected). "
                f"The materiality test fails. GoldPan returns Unknown."
            ),
            limitations=filter_def.standard_limitations,
            rule_ids=filter_def.rule_ids,
            confidence="unknown",
            status="unknown",
        )

    # ── No beef or unresolved ambiguity → No Beef Identified ─────────────────
    disclosed = [row.get("Ingredient", "") for row in evidence.ingredients if row.get("Ingredient")]
    return DerivedConclusion(
        conclusion="No Beef Identified",
        evidence_used=evidence.verified_sources,
        reasoning=(
            f"No disclosed primary ingredient contains beef or a beef-derived ingredient. "
            f"Verified ingredient list contains {len(disclosed)} ingredient(s): "
            f"{', '.join(disclosed[:10])}{'...' if len(disclosed) > 10 else ''}. "
            f"Per GP-RULE-002 (Disclosed Absence Rule v1.1), beef is a primary ingredient "
            f"expected to be disclosed when present — its absence from the verified list "
            f"is informative. "
            f"Per GP-RULE-001 (Material Evidence Rule v1.1), the materiality test passes: "
            f"no plausible gap in the disclosed list would introduce beef. "
            f"GoldPan concludes: No Beef Identified."
        ),
        limitations=filter_def.standard_limitations,
        rule_ids=filter_def.rule_ids,
        confidence="verified",
        status="computed",
    )


# ── Pork detection vocabulary ─────────────────────────────────────────────────
#
# Same design principles as beef vocabulary above.
#
# PORK_TERMS
#   Substrings that unambiguously indicate pork presence.
#   Match → pork IS present → filter returns "Not Applicable."
#
# AMBIGUOUS_PORK_TERMS
#   Substrings that could plausibly include pork but aren't definitive.
#   Match (without a resolving qualifier) → materiality test fails → "Unknown."
#
# NON_PORK_QUALIFIERS
#   If an AMBIGUOUS_PORK_TERMS match also contains one of these, the ambiguity
#   resolves to non-pork. e.g. "turkey sausage" → not ambiguous.
#   Note: "beef" is a non-pork qualifier (beef chorizo is not pork).

PORK_TERMS: frozenset = frozenset([
    "pork",
    "ham",
    "bacon",
    "prosciutto",
    "pancetta",
    "lard",
    "pork belly",
    "pork chop",
    "pork loin",
    "pork ribs",
    "pork shoulder",
    "pork tenderloin",
    "pulled pork",
    "carnitas",         # pork by definition in culinary usage
    "guanciale",
    "mortadella",
    "capicola",
    "capocollo",
    "spare rib",
    "spare ribs",
    "baby back rib",
    "baby back ribs",
    "pork rind",
    "chicharron",
    "chicharrón",
    "lardo",            # Italian cured pork fat
    "coppa",            # Italian cured pork neck
    "lonza",            # Italian cured pork loin
    "speck",            # Italian smoked prosciutto
    "sopressata",
    "soppressata",
])

AMBIGUOUS_PORK_TERMS: frozenset = frozenset([
    "sausage",          # could be chicken, turkey, beef, or pork
    "pepperoni",        # typically pork/beef but turkey pepperoni common
    "salami",           # could be turkey or beef
    "chorizo",          # beef chorizo exists (Mexican-style)
    "bratwurst",        # could be chicken or turkey bratwurst
    "kielbasa",         # turkey kielbasa common
    "andouille",        # chicken andouille common in health-focused menus
    "meatball",         # often contains pork; could be turkey or beef
    "meatballs",
    "meat sauce",       # often contains pork; could be all-beef
    "bolognese",        # traditional recipe uses pork; veg variants exist
    "ragu",             # often mixed pork and beef
    "meat",             # unqualified — could be any animal
    "protein",          # unqualified — too generic to classify
    "braised meat",
    "slow-cooked meat",
    "house meat",
    "mixed meat",
    "smoked meat",      # could be pulled pork, brisket, or other
])

NON_PORK_QUALIFIERS: frozenset = frozenset([
    "turkey", "chicken", "beef", "lamb", "fish", "tuna", "salmon",
    "swordfish", "vegan", "vegetarian", "plant-based", "impossible",
    "beyond", "tofu", "meatless",
])


def _compute_no_pork_identified(
    evidence: DishEvidence,
    filter_def: FilterDefinition,
) -> DerivedConclusion:
    """
    Compute "No Pork Identified" for one dish.

    Outcome matrix mirrors no-beef-identified:
      Pork term found AND no qualifier     → "Not Applicable" (pork IS present)
      Pork term found BUT qualifier present→ treat as clear (e.g. "turkey sausage")
      Ambiguous term found (unresolved)    → "Unknown" (materiality test fails)
      Ambiguous term found + qualifier     → treat as clear
      No pork or unresolved ambiguity      → "No Pork Identified"

    Qualifier resolution applies to BOTH PORK_TERMS and AMBIGUOUS_PORK_TERMS hits.
    A NON_PORK_QUALIFIER in the same ingredient string overrides a pork-term match.
    Examples that resolve to clear (non-pork):
      "turkey sausage", "chicken chorizo", "beef pepperoni", "vegan pepperoni"
    Examples that remain pork:
      "bacon", "prosciutto", "pork belly", "carnitas", "lard"

    Cites:
      GP-RULE-001 (Material Evidence Rule v1.1)    — materiality test
      GP-RULE-002 (Disclosed Absence Rule v1.1)    — reasoning from absence
      GP-RULE-006 (Derived Filter Explanation Rule) — explanation structure
      GP-RULE-007 (Filter Evidence Dependency Rule) — dependency check (done in engine)
    """
    pork_found      = []
    ambiguous_found = []

    for row in evidence.ingredients:
        name = _name(row)
        if not name:
            continue
        raw = row.get("Ingredient", name)

        if _matches_any(name, PORK_TERMS):
            if any(q in name for q in NON_PORK_QUALIFIERS):
                continue   # "turkey bacon substitute" etc — not pork
            pork_found.append(raw)
            continue

        if _matches_any(name, AMBIGUOUS_PORK_TERMS):
            if not any(q in name for q in NON_PORK_QUALIFIERS):
                ambiguous_found.append(raw)

    # ── Pork IS present → Not Applicable ─────────────────────────────────────
    if pork_found:
        return DerivedConclusion(
            conclusion="Not Applicable",
            evidence_used=evidence.verified_sources,
            reasoning=(
                f"Pork ingredient(s) identified in the verified ingredient list: "
                f"{', '.join(repr(i) for i in pork_found)}. "
                f"The 'No Pork Identified' filter does not apply to dishes that contain pork."
            ),
            limitations=filter_def.standard_limitations,
            rule_ids=filter_def.rule_ids,
            confidence="verified",
            status="not_applicable",
        )

    # ── Ambiguous compound ingredient(s) → Unknown ────────────────────────────
    if ambiguous_found:
        return DerivedConclusion(
            conclusion="Unknown",
            evidence_used=evidence.verified_sources,
            reasoning=(
                f"Per GP-RULE-001 (Material Evidence Rule v1.1), GoldPan applies the "
                f"materiality test: could missing evidence change this conclusion? "
                f"The following ingredient(s) are ambiguous and could plausibly contain pork: "
                f"{', '.join(repr(i) for i in ambiguous_found)}. "
                f"Absence from the disclosed list is not informative for these terms "
                f"(per GP-RULE-002, Disclosed Absence Rule v1.1 — absence is only "
                f"informative when disclosure is expected). "
                f"The materiality test fails. GoldPan returns Unknown."
            ),
            limitations=filter_def.standard_limitations,
            rule_ids=filter_def.rule_ids,
            confidence="unknown",
            status="unknown",
        )

    # ── No pork or unresolved ambiguity → No Pork Identified ─────────────────
    disclosed = [row.get("Ingredient", "") for row in evidence.ingredients if row.get("Ingredient")]
    return DerivedConclusion(
        conclusion="No Pork Identified",
        evidence_used=evidence.verified_sources,
        reasoning=(
            f"No disclosed primary ingredient contains pork or a pork-derived ingredient. "
            f"Verified ingredient list contains {len(disclosed)} ingredient(s): "
            f"{', '.join(disclosed[:10])}{'...' if len(disclosed) > 10 else ''}. "
            f"Per GP-RULE-002 (Disclosed Absence Rule v1.1), pork is a primary ingredient "
            f"expected to be disclosed when present — its absence from the verified list "
            f"is informative. "
            f"Per GP-RULE-001 (Material Evidence Rule v1.1), the materiality test passes: "
            f"no plausible gap in the disclosed list would introduce pork. "
            f"GoldPan concludes: No Pork Identified."
        ),
        limitations=filter_def.standard_limitations,
        rule_ids=filter_def.rule_ids,
        confidence="verified",
        status="computed",
    )


# ── Allergen detection (GP-RULE-014, GP-RULE-015, GP-RULE-016) ───────────────
#
# Allergen filters read Allergen_Flags from ingredient rows (Evidence System).
# They never write to Allergen_Flags. They never backfill Allergen_Flags.
#
# Evidence contract (enforced here, documented in ALLERGEN_ARCHITECTURE.md):
#   Blank Allergen_Flags → absence of evidence → Unknown
#   "none"               → canvasser confirmed no allergen flags for this ingredient
#   "unknown"            → canvasser could not determine allergen status → Unknown
#   Any matching flag    → allergen IS present → Not Applicable
#   All non-blank, non-unknown, none matching → No [X] Ingredients Identified
#
# Confidence ceiling: "inferred" for all non-Unknown outcomes (GP-RULE-015).
# This ceiling is enforced in the compute function, not by the engine.
# The engine's GP-RULE-009 post-compute cap only reduces "verified" → "likely"
# and does not affect allergen filters that return "inferred".
#
# ALLERGEN_FLAG_LOOKUP
#   Maps each canonical allergen slug to the set of Allergen_Flags values that
#   signal presence of that allergen, including canonical forms and common aliases.
#   Sourced from schema.py CANONICAL_ALLERGEN_FLAGS and ALLERGEN_FLAG_ALIASES.
#   Defined here inline to keep compute logic self-contained in this module.

ALLERGEN_FLAG_LOOKUP: dict[str, frozenset] = {
    "wheat":     frozenset(["wheat", "gluten"]),
    "milk":      frozenset(["milk", "dairy"]),
    "eggs":      frozenset(["eggs", "egg"]),
    "soy":       frozenset(["soy", "soybeans", "soybean"]),
    "sesame":    frozenset(["sesame"]),
    "peanuts":   frozenset(["peanuts", "peanut"]),
    "tree_nuts": frozenset(["tree_nuts", "tree nuts", "tree nut"]),
    "fish":      frozenset(["fish"]),
    "shellfish": frozenset(["shellfish"]),
}

# Rule IDs cited by every allergen filter.
_ALLERGEN_RULE_IDS: list = [
    "GP-RULE-001",   # Material Evidence Rule — materiality test
    "GP-RULE-002",   # Disclosed Absence Rule — reasoning from absence
    "GP-RULE-006",   # Derived Filter Explanation Rule — explanation structure
    "GP-RULE-007",   # Filter Evidence Dependency Rule — dependency check (engine)
    "GP-RULE-014",   # Allergen Evidence Rule — Allergen_Flags as read-only evidence
    "GP-RULE-015",   # Allergen Knowledge Rule — confidence ceiling, governing principle
    "GP-RULE-016",   # Allergen Communication Rule — consumer label + limitations
]


def _parse_allergen_flags(flag_str: str) -> set:
    """
    Parse a comma-separated Allergen_Flags string into a set of normalized tokens.

    Returns an empty set for blank input — callers must treat blank as
    absence of evidence, not as confirmed absence of allergen.
    """
    if not flag_str:
        return set()
    return {token.strip().lower() for token in flag_str.split(",") if token.strip()}


def _allergen_limitations(display_name: str) -> str:
    """
    Standard limitations text for allergen-elimination filters (GP-RULE-016).
    This is the mandatory non-waivable language. It must appear in full on
    every consumer-facing output surface. Do not shorten or paraphrase.
    """
    dn = display_name
    dl = display_name.lower()
    return (
        f'"No {dn} Ingredients Identified" means the verified disclosed primary '
        f"ingredient list for this dish does not contain {dl} or {dl}-derived "
        f"ingredients as explicitly listed by the restaurant. This is not a claim "
        f"that the dish is {dl}-free. It does not address undisclosed compound "
        f"ingredient components, micro ingredients, processing aids, cross-contact "
        f"risk, shared equipment, preparation variations, or ingredients added or "
        f"changed since last canvass. Diners with {dl} allergies or intolerances "
        f"must contact the restaurant directly before dining. (GP-RULE-016)"
    )


def _make_allergen_compute_fn(display_name: str, presence_flags: frozenset):
    """
    Factory: returns a compute_fn for an allergen-elimination filter.

    The returned function is a valid (DishEvidence, FilterDefinition) → DerivedConclusion
    callable that can be passed directly to FilterDefinition.compute_fn.

    Evidence reads (read-only, never written by engine):
      row["Allergen_Flags"] — comma-separated flag string on each ingredient row.

    Outcome matrix:
      Any flag matches presence_flags   → Not Applicable (allergen IS present), confidence=inferred
      Any flag is blank                 → Unknown (absence of evidence, not absence of allergen)
      Any flag is "unknown"             → Unknown (canvasser could not determine status)
      All flags populated, none match   → "No {display_name} Ingredients Identified", confidence=inferred

    Confidence ceiling: "inferred" throughout (GP-RULE-015).
    The engine's GP-RULE-009 cap does not reduce "inferred" further.
    """
    dn = display_name

    def _compute(evidence: DishEvidence, filter_def: FilterDefinition) -> DerivedConclusion:
        allergen_found:   list = []   # ingredients with a matching allergen flag
        unprocessed:      list = []   # ingredients with blank Allergen_Flags
        status_unknown:   list = []   # ingredients with Allergen_Flags = "unknown"

        for row in evidence.ingredients:
            raw_name  = row.get("Ingredient", "")
            flag_str  = str(row.get("Allergen_Flags", "")).strip()

            if not flag_str:
                # Blank = absence of evidence.
                # GP-RULE-014 invariant: engine must never convert blank to "none".
                unprocessed.append(raw_name)
                continue

            flags = _parse_allergen_flags(flag_str)

            if "unknown" in flags:
                # Canvasser explicitly recorded that allergen status is unknown.
                # Semantically equivalent to blank for the materiality test.
                status_unknown.append(raw_name)
                continue

            if flags & presence_flags:
                # At least one flag on this ingredient matches the target allergen.
                allergen_found.append(raw_name)
                # Don't break — continue to discover all flagged ingredients
                # for complete reasoning output.

        # ── Allergen IS present → Not Applicable ──────────────────────────────
        if allergen_found:
            return DerivedConclusion(
                conclusion="Not Applicable",
                evidence_used=evidence.verified_sources,
                reasoning=(
                    f"{dn} identified via Allergen_Flags on the following disclosed "
                    f"ingredient(s): {', '.join(repr(i) for i in allergen_found)}. "
                    f"The 'No {dn} Ingredients Identified' filter does not apply to "
                    f"dishes where {dn.lower()} has been identified in the ingredient list. "
                    f"Allergen_Flags are canvasser-recorded Evidence System observations "
                    f"(GP-RULE-014). Confidence ceiling: inferred (GP-RULE-015)."
                ),
                limitations=filter_def.standard_limitations,
                rule_ids=filter_def.rule_ids,
                confidence="inferred",
                status="not_applicable",
            )

        # ── Blank or unknown Allergen_Flags → Unknown ─────────────────────────
        # Materiality test (GP-RULE-001): could unprocessed ingredients introduce
        # this allergen? We cannot know. Absence of a flag is not absence of allergen.
        if unprocessed or status_unknown:
            parts = []
            if unprocessed:
                parts.append(
                    f"{len(unprocessed)} ingredient(s) have no Allergen_Flags recorded "
                    f"(blank = absence of evidence, not confirmed absence of {dn.lower()}: "
                    f"{', '.join(repr(i) for i in unprocessed[:5])}"
                    f"{'...' if len(unprocessed) > 5 else ''})"
                )
            if status_unknown:
                parts.append(
                    f"{len(status_unknown)} ingredient(s) have Allergen_Flags = 'unknown' "
                    f"(canvasser could not determine allergen status at canvass time: "
                    f"{', '.join(repr(i) for i in status_unknown[:5])}"
                    f"{'...' if len(status_unknown) > 5 else ''})"
                )
            return DerivedConclusion(
                conclusion="Unknown",
                evidence_used=evidence.verified_sources,
                reasoning=(
                    f"Per GP-RULE-001 (Material Evidence Rule v1.1), the materiality test "
                    f"fails: could unprocessed ingredient evidence introduce {dn.lower()}? "
                    f"Yes — {'. '.join(parts)}. "
                    f"GoldPan cannot conclude allergen status when any ingredient's "
                    f"Allergen_Flags are unprocessed or unknown. "
                    f"Governing principle (GP-RULE-015): 'The absence of identified "
                    f"ingredients is not evidence of allergen absence.' "
                    f"GoldPan returns Unknown."
                ),
                limitations=filter_def.standard_limitations,
                rule_ids=filter_def.rule_ids,
                confidence="unknown",
                status="unknown",
            )

        # ── All flags assessed, none match → No [X] Ingredients Identified ────
        disclosed = [
            row.get("Ingredient", "")
            for row in evidence.ingredients
            if row.get("Ingredient")
        ]
        return DerivedConclusion(
            conclusion=f"No {dn} Ingredients Identified",
            evidence_used=evidence.verified_sources,
            reasoning=(
                f"All {len(evidence.ingredients)} ingredient(s) in the disclosed "
                f"primary ingredient list carry explicit Allergen_Flags values — "
                f"none indicate {dn.lower()}. "
                f"Disclosed ingredients: "
                f"{', '.join(disclosed[:10])}{'...' if len(disclosed) > 10 else ''}. "
                f"Allergen_Flags were set by canvassers during acquisition and are "
                f"read here as Evidence System observations (GP-RULE-014). "
                f"Per GP-RULE-002 (Disclosed Absence Rule v1.1), allergen absence is "
                f"informative when all ingredient evidence has been assessed. "
                f"Governing principle (GP-RULE-015): 'The absence of identified "
                f"ingredients is not evidence of allergen absence.' This conclusion "
                f"reflects what the disclosed ingredient list contains, not whether "
                f"the dish is {dn.lower()}-free. "
                f"Confidence ceiling: inferred (GP-RULE-015). "
                f"GoldPan concludes: No {dn} Ingredients Identified."
            ),
            limitations=filter_def.standard_limitations,
            rule_ids=filter_def.rule_ids,
            confidence="inferred",
            status="computed",
        )

    _compute.__name__ = f"_compute_no_{display_name.lower().replace(' ', '_')}_ingredients_identified"
    return _compute


# ── Allergen FilterDefinition instances ───────────────────────────────────────
#
# Each allergen filter is generated from a spec tuple:
#   (filter_slug, display_name, allergen_slug_key)
# where allergen_slug_key indexes into ALLERGEN_FLAG_LOOKUP.
#
# All nine are macro_dependent — same evidence requirement as No Beef / No Pork.
# Confidence ceiling "inferred" is enforced inside each compute function.

_ALLERGEN_SPECS: list = [
    # (filter_slug,                         display_name,  flag_lookup_key)
    ("no-wheat-ingredients-identified",     "Wheat",       "wheat"),
    ("no-milk-ingredients-identified",      "Milk",        "milk"),
    ("no-egg-ingredients-identified",       "Egg",         "eggs"),
    ("no-soy-ingredients-identified",       "Soy",         "soy"),
    ("no-sesame-ingredients-identified",    "Sesame",      "sesame"),
    ("no-peanut-ingredients-identified",    "Peanut",      "peanuts"),
    ("no-tree-nut-ingredients-identified",  "Tree Nut",    "tree_nuts"),
    ("no-fish-ingredients-identified",      "Fish",        "fish"),
    ("no-shellfish-ingredients-identified", "Shellfish",   "shellfish"),
]

_ALLERGEN_FILTER_DEFS: dict[str, FilterDefinition] = {}
for _slug, _display, _lookup_key in _ALLERGEN_SPECS:
    _presence_flags = ALLERGEN_FLAG_LOOKUP[_lookup_key]
    _ALLERGEN_FILTER_DEFS[_slug] = FilterDefinition(
        name=f"No {_display} Ingredients Identified",
        slug=_slug,
        dependency_type="macro_dependent",
        rule_ids=_ALLERGEN_RULE_IDS,
        description=(
            f"Concludes 'No {_display} Ingredients Identified' when all verified primary "
            f"ingredient rows carry explicit Allergen_Flags and none indicate {_display.lower()}. "
            f"Returns Unknown when any ingredient has blank or 'unknown' Allergen_Flags "
            f"(absence of evidence is not evidence of absence, per GP-RULE-015). "
            f"Returns Not Applicable when {_display.lower()} is identified in any ingredient flag. "
            f"Confidence ceiling: inferred (GP-RULE-015). Uses Allergen_Flags as read-only "
            f"Evidence System evidence — engine never writes or backfills Allergen_Flags (GP-RULE-014)."
        ),
        standard_limitations=_allergen_limitations(_display),
        compute_fn=_make_allergen_compute_fn(_display, _presence_flags),
    )


# ── Filter Registry ───────────────────────────────────────────────────────────

FILTER_NO_BEEF_IDENTIFIED = FilterDefinition(
    name="No Beef Identified",
    slug="no-beef-identified",
    dependency_type="macro_dependent",
    rule_ids=["GP-RULE-001", "GP-RULE-002", "GP-RULE-006", "GP-RULE-007"],
    description=(
        "Concludes 'No Beef Identified' when the verified primary ingredient list "
        "contains no beef or beef-derived ingredients and no unresolved ambiguous "
        "meat terms. Returns Unknown when evidence is insufficient or when ambiguous "
        "compound ingredients could plausibly contain beef. Returns Not Applicable "
        "when beef is identified in the ingredient list."
    ),
    standard_limitations=(
        '"No Beef Identified" means the verified primary ingredient list for this dish '
        "does not contain beef or beef-derived ingredients. This is not a beef-free claim. "
        "It does not address micro ingredients, compound ingredient sub-components, "
        "processing aids, cross-contact practices, or preparation variations. "
        "Diners with dietary restrictions should contact the restaurant directly."
    ),
    compute_fn=_compute_no_beef_identified,
)

FILTER_NO_PORK_IDENTIFIED = FilterDefinition(
    name="No Pork Identified",
    slug="no-pork-identified",
    dependency_type="macro_dependent",
    rule_ids=["GP-RULE-001", "GP-RULE-002", "GP-RULE-006", "GP-RULE-007"],
    description=(
        "Concludes 'No Pork Identified' when the verified primary ingredient list "
        "contains no pork or pork-derived ingredients and no unresolved ambiguous "
        "terms. Returns Unknown when evidence is insufficient or when ambiguous "
        "compound ingredients could plausibly contain pork. Returns Not Applicable "
        "when pork is identified in the ingredient list."
    ),
    standard_limitations=(
        '"No Pork Identified" means the verified primary ingredient list for this dish '
        "does not contain pork or pork-derived ingredients. This is not a pork-free claim. "
        "It does not address micro ingredients, compound ingredient sub-components, "
        "processing aids, cross-contact practices, or preparation variations. "
        "Diners with dietary restrictions should contact the restaurant directly."
    ),
    compute_fn=_compute_no_pork_identified,
)

# Add future filters here. The engine reads this dict and iterates it.
# No engine changes required when adding a new filter.
FILTER_REGISTRY: dict[str, FilterDefinition] = {
    FILTER_NO_BEEF_IDENTIFIED.slug: FILTER_NO_BEEF_IDENTIFIED,
    FILTER_NO_PORK_IDENTIFIED.slug: FILTER_NO_PORK_IDENTIFIED,
    # Allergen-elimination filters (GP-RULE-014, GP-RULE-015, GP-RULE-016)
    # All macro_dependent. Confidence ceiling: inferred. Engine reads Allergen_Flags;
    # never writes or backfills. Blank Allergen_Flags = Unknown, not absence of allergen.
    **_ALLERGEN_FILTER_DEFS,
}
