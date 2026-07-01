"""
schema.py — GoldPan governed schema constants.

This module is the single source of truth for constants that cross architectural
layer boundaries. No layer may define its own copy of a constant defined here.

Constants defined here are governed by the GoldPan Rules Registry
(docs/RULES_REGISTRY.md). Changes require a rule version increment.

Current contents:

  Source / provenance:
    MACRO_ELIGIBLE_SOURCES              — GP-RULE-010 (Source Authority Hierarchy Rule v1.0)
    CANONICAL_PROVENANCE_VALUES         — GP-RULE-010 / GP-RULE-011

  Filter dependencies:
    DEPENDENCY_TYPES                    — GP-RULE-007 (Filter Evidence Dependency Rule v1.0)

  Transparency:
    TRANSPARENCY_LEVELS                 — transparency scoring vocabulary
    TRANSPARENCY_LEVEL_ALIASES          — legacy aliases → canonical forms

  ID format patterns:
    RESTAURANT_ID_PATTERN               — regex for Restaurant_ID (R + 3 digits)
    DISH_ID_PATTERN                     — regex for Dish_ID (D + 3 digits)

  Dietary tags:
    RECOGNIZED_DIETARY_TAGS             — open vocabulary; used for typo detection

  Allergen flags (Ingredient Details tab):
    CANONICAL_ALLERGEN_FLAGS            — valid Allergen_Flags values on ingredient rows
    ALLERGEN_FLAG_ALIASES               — non-canonical forms → canonical suggestion
    RECOGNIZED_ALLERGEN_FLAGS           — DEPRECATED alias for CANONICAL_ALLERGEN_FLAGS

  Allergen disclosures (Allergen_Disclosures tab):
    ALLERGEN_CANONICAL_SLUGS            — GP-RULE-014 (Allergen Evidence Rule v1.0)
    ALLERGEN_SLUG_ALIASES               — GP-RULE-014 (Allergen Evidence Rule v1.0)
    ALLERGEN_DISCLOSURE_STATUSES        — GP-RULE-014 (Allergen Evidence Rule v1.0)
    ALLERGEN_DISCLOSURE_SCOPES          — GP-RULE-014 (Allergen Evidence Rule v1.0)
    ALLERGEN_FREE_FROM_ELIGIBLE_SOURCES — GP-RULE-014 (Allergen Evidence Rule v1.0)
"""

from __future__ import annotations


# ── MACRO_ELIGIBLE_SOURCES ────────────────────────────────────────────────────
#
# Governed by: GP-RULE-010 (Source Authority Hierarchy Rule v1.0)
# Layer:       Acquisition → Quality bridge
# Used by:     derived/engine.py (dependency check for macro_dependent filters)
#
# The set of Ingredient_Source values whose evidence satisfies the
# macro_dependent evidence dependency type (GP-RULE-007).
#
# A source in this set is an eligible acquisition channel — meaning evidence
# acquired through it may satisfy quality requirements. Membership here does
# not imply the evidence is verified; it implies the channel is authorized.
#
# Replaces the anonymous engine constant VERIFIED_SOURCES (deprecated).
# Reason for rename: "VERIFIED_SOURCES" implied these sources are verified.
# They are trusted acquisition channels whose evidence is eligible to satisfy
# quality requirements. The new name describes what the constant governs.
#
# Tier mapping (per GP-RULE-010):
#   Tier 1 (highest): restaurant_confirmation, allergen_guide, nutrition_document
#   Tier 2:           menu, website
#   Tier 3:           ordering_platform
#   Tier 4:           restaurant_qa
#   pdf:              legacy catch-all; maps to allergen_guide or nutrition_document
#                     depending on document type. Keep in set until schema migration
#                     disambiguates existing pdf records.
#
# Below-threshold sources NOT in this set (GP-RULE-010 §Rejected Sources):
#   "yelp", "google", "tripadvisor", "doordash", "grubhub",
#   "unknown", "social_media", "review_site", "" (blank)

MACRO_ELIGIBLE_SOURCES: frozenset = frozenset([
    # Tier 1 — Highest authority
    "restaurant_confirmation",
    "allergen_guide",
    "nutrition_document",
    # Tier 2 — Primary canvassing
    "menu",
    "website",
    # Tier 3 — Restaurant-managed ordering
    "ordering_platform",
    # Tier 4 — Restaurant-answered Q&A
    "restaurant_qa",
    # Legacy
    "pdf",      # catch-all pre-dating allergen_guide / nutrition_document split
])


# ── DEPENDENCY_TYPES ──────────────────────────────────────────────────────────
#
# Governed by: GP-RULE-007 (Filter Evidence Dependency Rule v1.0)
# Used by:     derived/engine.py (validates FilterDefinition.dependency_type)
#
# Valid values for FilterDefinition.dependency_type.
# Any dependency_type not in this set is a configuration error.

DEPENDENCY_TYPES: frozenset = frozenset([
    "macro_dependent",            # verified primary ingredient list required
    "mixed_dependent",            # primary ingredients + additional context
    "micro_dependent",            # official allergen/micro documentation required
    "restaurant_claim_dependent", # explicit restaurant claim required
])


# ── TRANSPARENCY_LEVELS ───────────────────────────────────────────────────────
#
# Governed by: Transparency Scoring tab; used by upsert_dishes.py and validators
#
# Valid values for the transparency_level (Schema A) and transparency_tier
# (Schema B) fields. Any other value is a configuration error.

TRANSPARENCY_LEVELS: frozenset = frozenset([
    "High Transparency",
    "Moderate Transparency",
    "Building Transparency",
])

# Legacy aliases accepted during validation (map → canonical form)
TRANSPARENCY_LEVEL_ALIASES: dict = {
    "high":     "High Transparency",
    "moderate": "Moderate Transparency",
    "building": "Building Transparency",
}


# ── ID FORMAT PATTERNS ────────────────────────────────────────────────────────
#
# Restaurant IDs: R + zero-padded three digits  (e.g. R001, R025)
# Dish IDs:       D + zero-padded three digits  (e.g. D001, D750)

RESTAURANT_ID_PATTERN: str = r"^R\d{3}$"
DISH_ID_PATTERN:        str = r"^D\d{3}$"


# ── RECOGNIZED DIETARY TAGS ───────────────────────────────────────────────────
#
# The canonical tag vocabulary used by fetch_dishes.py and the front-end.
# Tags not in this set are accepted with a WARNING (vocabulary is open);
# they are listed here to catch typos in common tags.

RECOGNIZED_DIETARY_TAGS: frozenset = frozenset([
    "vegan", "vegetarian", "gluten-free", "dairy-free", "nut-free",
    "high-protein", "keto-friendly", "paleo-friendly", "halal", "kosher",
    "low-carb", "whole30", "low-calorie",
])


# ── CANONICAL ALLERGEN FLAGS ──────────────────────────────────────────────────
#
# Allergen flags must be atomic, machine-readable values. Free-text detail
# (e.g. "(almonds)", "(grits)", "(cheese option)") must not appear inside the
# flag itself — it belongs in allergen_summary or a future allergen_note field.
#
# Design rule: one concept, one token. No compound strings, no parentheticals.
#
# CANONICAL_ALLERGEN_FLAGS
#   Atomic values that generate no validator warning.
#   Both "milk" and "dairy" are accepted as equivalent canonical forms.
#   Both "tree_nuts" (machine-readable) and "tree nuts" (human-readable) accepted.
#   "unknown" is a valid value when allergen status was not determinable at canvass.
#
# ALLERGEN_FLAG_ALIASES
#   Non-canonical forms that are understood but should be replaced.
#   Validator generates ALLERGEN_FLAG_NON_CANONICAL warning with the suggestion.
#   "gluten" maps to "wheat" — gluten is the protein, wheat is the FDA allergen.
#   Verify intent before applying: if the source means a non-wheat gluten source
#   (rye, barley), annotate in allergen_summary instead.

CANONICAL_ALLERGEN_FLAGS: frozenset = frozenset([
    "wheat",
    "milk", "dairy",      # milk is FDA canonical; dairy accepted as equivalent
    "eggs",
    "soy",
    "sesame",
    "peanuts",
    "tree_nuts", "tree nuts",   # both forms accepted; tree_nuts preferred for new files
    "fish",
    "shellfish",
    "unknown",            # allergen status not determined at canvass time
    "none",               # no allergens identified
])

ALLERGEN_FLAG_ALIASES: dict = {
    # key: form seen in data  →  value: canonical form to suggest
    "egg":      "eggs",
    "soybeans": "soy",
    "soybean":  "soy",
    "peanut":   "peanuts",
    "tree nut": "tree_nuts",
    "gluten":   "wheat",    # FDA allergen = wheat; review if source means rye/barley
}

# DEPRECATED — no longer imported anywhere in this codebase. Use CANONICAL_ALLERGEN_FLAGS.
# Retained as a safety alias in case external callers reference it.
RECOGNIZED_ALLERGEN_FLAGS: frozenset = CANONICAL_ALLERGEN_FLAGS


# ── CANONICAL_PROVENANCE_VALUES ───────────────────────────────────────────────
#
# Governed by: GP-RULE-010 (Source Authority Hierarchy Rule v1.0)
#              GP-RULE-011 (Evidence Provenance Rule v1.0)
# Used by:     backfill_enrichment.py, validate_database.py, future validators
#
# The complete set of recognized Ingredient_Source values.
# Values in MACRO_ELIGIBLE_SOURCES are a subset of this set.
# Values in this set but not in MACRO_ELIGIBLE_SOURCES are recognized but
# do not satisfy macro_dependent quality requirements.

CANONICAL_PROVENANCE_VALUES: frozenset = MACRO_ELIGIBLE_SOURCES | frozenset([
    # Not macro_eligible but recognized:
    # (none currently — reserved for future below-threshold recognized sources
    #  such as field_canvasser_observation before verification is complete)
])


# ── ALLERGEN_CANONICAL_SLUGS ──────────────────────────────────────────────────
#
# Governed by: GP-RULE-014 (Allergen Evidence Rule v1.0)
# Used by:     Allergen_Disclosures tab validator, derived/registry.py (allergen filters)
#
# The nine FDA major food allergens as canonical slug values.
# These are the only permitted Allergen values in the Allergen_Disclosures tab.
# Slugs are lowercase with underscores — consistent with machine-readable style
# used elsewhere in the Evidence System.
#
# Relationship to CANONICAL_ALLERGEN_FLAGS:
#   CANONICAL_ALLERGEN_FLAGS — used on ingredient rows (Ingredient Details tab)
#     to flag which allergens a given ingredient may contain. Includes "unknown"
#     and "none" as valid flag values for canvass outcomes.
#   ALLERGEN_CANONICAL_SLUGS — used in the Allergen_Disclosures tab to identify
#     which allergen a restaurant disclosure applies to. Never includes "unknown"
#     or "none" — every disclosure row must specify a concrete allergen.
#   The sets are related but not identical. Do not conflate them.

ALLERGEN_CANONICAL_SLUGS: frozenset = frozenset([
    "wheat",
    "milk",
    "eggs",
    "soy",
    "sesame",
    "peanuts",
    "tree_nuts",
    "fish",
    "shellfish",
])

# ALLERGEN_SLUG_ALIASES
#   Non-canonical → canonical allergen slug mapping.
#   Used by the Allergen_Disclosures validator to suggest corrections.
#   "dairy" → "milk": dairy is common shorthand; milk is the FDA allergen slug.
#   "gluten" → "wheat": gluten is the protein; wheat is the FDA allergen.
#     Verify before applying — if the source means rye or barley gluten,
#     record as "wheat" only if wheat is confirmed; otherwise flag for review.

ALLERGEN_SLUG_ALIASES: dict = {
    "dairy":     "milk",
    "egg":       "eggs",
    "soybeans":  "soy",
    "soybean":   "soy",
    "peanut":    "peanuts",
    "tree nut":  "tree_nuts",
    "tree nuts": "tree_nuts",
    "gluten":    "wheat",
}


# ── ALLERGEN_DISCLOSURE_STATUSES ──────────────────────────────────────────────
#
# Governed by: GP-RULE-014 (Allergen Evidence Rule v1.0)
# Used by:     Allergen_Disclosures tab validator
#
# Valid values for the Disclosure_Status field in the Allergen_Disclosures tab.
# These are internal canonical values — consumer-facing labels are governed
# separately by GP-RULE-016 (Allergen Communication Rule v1.0).
#
# contains     — restaurant explicitly states the dish contains this allergen.
#                Evidence: confirms presence. Never used as a safety claim.
#
# may_contain  — restaurant states cross-contamination risk exists.
#                Evidence: confirms risk disclosure. Weaker than contains.
#
# free_from    — restaurant explicitly states the dish is free from this allergen.
#                INTERNAL ONLY. Consumer-facing label is determined by GP-RULE-016
#                based on Source_Type tier. Never expose "free_from" to consumers.
#                Tier 1 source (allergen_guide, nutrition_document,
#                restaurant_confirmation) → "verified" confidence tier.
#                Tier 2 source (menu, website) → "declared" confidence tier.

ALLERGEN_DISCLOSURE_STATUSES: frozenset = frozenset([
    "contains",
    "may_contain",
    "free_from",
])


# ── ALLERGEN_DISCLOSURE_SCOPES ────────────────────────────────────────────────
#
# Governed by: GP-RULE-014 (Allergen Evidence Rule v1.0)
# Used by:     Allergen_Disclosures tab validator
#
# Valid values for the Scope field in the Allergen_Disclosures tab.
# Scope determines whether a disclosure applies to a specific dish or to
# the restaurant as a whole (e.g., "our kitchen handles tree nuts").
#
# dish       — disclosure applies to a specific Dish_ID. Dish_ID required.
# restaurant — disclosure applies to the restaurant broadly. Dish_ID must be blank.

ALLERGEN_DISCLOSURE_SCOPES: frozenset = frozenset([
    "dish",
    "restaurant",
])


# ── ALLERGEN_FREE_FROM_ELIGIBLE_SOURCES ───────────────────────────────────────
#
# Governed by: GP-RULE-014 (Allergen Evidence Rule v1.0)
# Used by:     validate_database.py (Allergen Disclosures tab validator)
#
# The subset of MACRO_ELIGIBLE_SOURCES whose evidence may support a
# `free_from` Disclosure_Status. This is a STRICTER requirement than the
# general macro_dependent evidence dependency.
#
# Tier 1 (verified confidence):
#   allergen_guide, nutrition_document, restaurant_confirmation
# Tier 2 (declared confidence):
#   menu, website
#
# Tier 3+ (ordering_platform, restaurant_qa, pdf) are MACRO_ELIGIBLE but
# are NOT eligible for `free_from` disclosures. A restaurant's ordering
# platform listing or a canvasser Q&A does not constitute a sufficient
# basis for recording a restaurant's allergen-free claim.
#
# `contains` and `may_contain` disclosures may use any MACRO_ELIGIBLE_SOURCE.
# Only `free_from` requires a source in this set.

ALLERGEN_FREE_FROM_ELIGIBLE_SOURCES: frozenset = frozenset([
    # Tier 1 — verified confidence
    "allergen_guide",
    "nutrition_document",
    "restaurant_confirmation",
    # Tier 2 — declared confidence
    "menu",
    "website",
])
