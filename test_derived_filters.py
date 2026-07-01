"""
test_derived_filters.py
Unit tests for GoldPan derived filter logic.

Run from the goldpan/ directory:
    python3 test_derived_filters.py

Does not connect to Google Sheets — all tests use in-memory fake evidence.
"""

import sys
import traceback
from derived.models import DishEvidence, FilterDefinition
from derived.registry import (
    _compute_no_beef_identified,
    FILTER_NO_BEEF_IDENTIFIED,
    BEEF_TERMS,
    AMBIGUOUS_MEAT_TERMS,
    NON_BEEF_QUALIFIERS,
    _compute_no_pork_identified,
    FILTER_NO_PORK_IDENTIFIED,
    PORK_TERMS,
    AMBIGUOUS_PORK_TERMS,
    NON_PORK_QUALIFIERS,
)


# ── Test helpers ──────────────────────────────────────────────────────────────

def _make_evidence(dish_id: str, dish_name: str, restaurant: str,
                   ingredients: list, restaurant_id: str = "R000") -> DishEvidence:
    """Build a minimal DishEvidence from a plain list of ingredient name strings."""
    rows = [
        {"Ingredient": ing, "Ingredient_Source": "menu"}
        for ing in ingredients
    ]
    return DishEvidence(
        dish_id=dish_id,
        dish_name=dish_name,
        restaurant=restaurant,
        restaurant_id=restaurant_id,
        location="Birmingham, AL",
        ingredients=rows,
        has_verified_ingredients=True,
        verified_sources=["menu"],
    )


PASSED = []
FAILED = []


def check(test_name: str, evidence: DishEvidence,
          expected_conclusion: str, expected_status: str):
    result = _compute_no_beef_identified(evidence, FILTER_NO_BEEF_IDENTIFIED)
    ok = (result.conclusion == expected_conclusion and result.status == expected_status)
    if ok:
        PASSED.append(test_name)
        print(f"  ✓  {test_name}")
    else:
        FAILED.append(test_name)
        print(f"  ✗  {test_name}")
        print(f"       expected  conclusion={expected_conclusion!r}  status={expected_status!r}")
        print(f"       got       conclusion={result.conclusion!r}  status={result.status!r}")
        print(f"       reasoning: {result.reasoning[:120]}...")


# ── Test cases ────────────────────────────────────────────────────────────────

print("\ntest_derived_filters.py")
print("=" * 60)

# ── Qualifier overrides beef term (the vegan beef fix) ────────────────────────

print("\n[1] Qualifier overrides BEEF_TERMS — should be No Beef Identified")

check(
    "vegan beef → No Beef Identified (D032 Hooker Fries scenario)",
    _make_evidence("D032", "Hooker Fries", "Slutty Vegan",
                   ["waffle fries", "vegan beef", "vegan cheese sauce", "jalapeños"]),
    expected_conclusion="No Beef Identified",
    expected_status="computed",
)

check(
    "plant-based beef → No Beef Identified",
    _make_evidence("T002", "Test Burger", "Test Kitchen",
                   ["lettuce", "plant-based beef patty", "tomato", "bun"]),
    expected_conclusion="No Beef Identified",
    expected_status="computed",
)

check(
    "impossible beef → No Beef Identified",
    _make_evidence("T003", "Impossible Plate", "Test Kitchen",
                   ["rice", "impossible beef crumble", "salsa"]),
    expected_conclusion="No Beef Identified",
    expected_status="computed",
)

check(
    "beyond beef → No Beef Identified",
    _make_evidence("T004", "Beyond Tacos", "Test Kitchen",
                   ["corn tortilla", "beyond beef", "pico de gallo"]),
    expected_conclusion="No Beef Identified",
    expected_status="computed",
)

check(
    "meatless beef → No Beef Identified",
    _make_evidence("T005", "Meatless Bowl", "Test Kitchen",
                   ["brown rice", "meatless beef crumble", "black beans"]),
    expected_conclusion="No Beef Identified",
    expected_status="computed",
)

# ── Unqualified beef terms — should remain Not Applicable ─────────────────────

print("\n[2] Unqualified BEEF_TERMS — should be Not Applicable")

check(
    "beef brisket → Not Applicable",
    _make_evidence("D111", "Brisket Panini", "Brick & Tin",
                   ["beef brisket", "provolone", "ciabatta"]),
    expected_conclusion="Not Applicable",
    expected_status="not_applicable",
)

check(
    "roast beef → Not Applicable",
    _make_evidence("D068", "Five Point Sandwich", "Adam and Eve Cafe",
                   ["roast beef", "swiss cheese", "pita bread"]),
    expected_conclusion="Not Applicable",
    expected_status="not_applicable",
)

check(
    "angus beef → Not Applicable",
    _make_evidence("T006", "Angus Burger", "Test Kitchen",
                   ["angus beef patty", "cheddar", "brioche bun"]),
    expected_conclusion="Not Applicable",
    expected_status="not_applicable",
)

check(
    "brisket (standalone) → Not Applicable",
    _make_evidence("T007", "Brisket Plate", "Test Kitchen",
                   ["smoked brisket", "coleslaw", "pickles"]),
    expected_conclusion="Not Applicable",
    expected_status="not_applicable",
)

check(
    "flank steak → Not Applicable",
    _make_evidence("D056", "Steak Tacos", "Test Kitchen",
                   ["flank steak", "salsa verde", "corn tortillas"]),
    expected_conclusion="Not Applicable",
    expected_status="not_applicable",
)

# ── Ambiguous terms — unresolved → Unknown ────────────────────────────────────

print("\n[3] Unresolved AMBIGUOUS_MEAT_TERMS — should be Unknown")

check(
    "meat sauce (unresolved) → Unknown",
    _make_evidence("T008", "Pasta", "Test Kitchen",
                   ["pasta", "meat sauce", "parmesan"]),
    expected_conclusion="Unknown",
    expected_status="unknown",
)

check(
    "meatballs (unresolved) → Unknown",
    _make_evidence("T009", "Spaghetti", "Test Kitchen",
                   ["spaghetti", "meatballs", "marinara"]),
    expected_conclusion="Unknown",
    expected_status="unknown",
)

check(
    "steak (unresolved) → Unknown",
    _make_evidence("T010", "Steak Bowl", "Test Kitchen",
                   ["rice", "steak", "peppers"]),
    expected_conclusion="Unknown",
    expected_status="unknown",
)

# ── Ambiguous terms — resolved by qualifier → No Beef Identified ──────────────

print("\n[4] AMBIGUOUS_MEAT_TERMS resolved by qualifier — should be No Beef Identified")

check(
    "turkey meatballs → No Beef Identified",
    _make_evidence("T011", "Turkey Meatball Sub", "Test Kitchen",
                   ["turkey meatballs", "marinara", "hoagie roll"]),
    expected_conclusion="No Beef Identified",
    expected_status="computed",
)

check(
    "chicken steak → No Beef Identified",
    _make_evidence("T012", "Chicken Steak Sandwich", "Test Kitchen",
                   ["chicken steak", "provolone", "peppers"]),
    expected_conclusion="No Beef Identified",
    expected_status="computed",
)

check(
    "vegan meatballs → No Beef Identified",
    _make_evidence("D077", "Vegan Meatball Sub", "Adam and Eve Cafe",
                   ["vegan meatballs", "marinara sauce", "vegan cheese", "pita bread"]),
    expected_conclusion="No Beef Identified",
    expected_status="computed",
)

# ── Clean dishes — No Beef Identified ────────────────────────────────────────

print("\n[5] Clean ingredient lists — should be No Beef Identified")

check(
    "all vegetables → No Beef Identified",
    _make_evidence("T013", "Garden Salad", "Test Kitchen",
                   ["romaine", "tomato", "cucumber", "red onion", "balsamic"]),
    expected_conclusion="No Beef Identified",
    expected_status="computed",
)

check(
    "chicken dish → No Beef Identified",
    _make_evidence("T014", "Chicken Caesar", "Test Kitchen",
                   ["grilled chicken", "romaine", "parmesan", "caesar dressing", "croutons"]),
    expected_conclusion="No Beef Identified",
    expected_status="computed",
)

check(
    "seafood dish → No Beef Identified",
    _make_evidence("T015", "Shrimp Tacos", "Test Kitchen",
                   ["grilled shrimp", "cabbage slaw", "corn tortilla", "lime crema"]),
    expected_conclusion="No Beef Identified",
    expected_status="computed",
)

# ── Mixed: qualifier resolves one, other is clean ────────────────────────────

print("\n[6] Mixed qualifier scenarios")

check(
    "beyond beef + real chicken → No Beef Identified",
    _make_evidence("T016", "Protein Bowl", "Test Kitchen",
                   ["beyond beef crumble", "grilled chicken", "quinoa", "roasted peppers"]),
    expected_conclusion="No Beef Identified",
    expected_status="computed",
)

check(
    "real beef + vegan beef in same dish → Not Applicable (real beef wins)",
    _make_evidence("T017", "Mixed Protein Bowl", "Test Kitchen",
                   ["beef tips", "vegan beef crumble", "rice"]),
    expected_conclusion="Not Applicable",
    expected_status="not_applicable",
)

# ── No Pork Identified tests ──────────────────────────────────────────────────

def check_pork(test_name: str, evidence: DishEvidence,
               expected_conclusion: str, expected_status: str):
    result = _compute_no_pork_identified(evidence, FILTER_NO_PORK_IDENTIFIED)
    ok = (result.conclusion == expected_conclusion and result.status == expected_status)
    if ok:
        PASSED.append(test_name)
        print(f"  ✓  {test_name}")
    else:
        FAILED.append(test_name)
        print(f"  ✗  {test_name}")
        print(f"       expected  conclusion={expected_conclusion!r}  status={expected_status!r}")
        print(f"       got       conclusion={result.conclusion!r}  status={result.status!r}")
        print(f"       reasoning: {result.reasoning[:120]}...")


print("\n[7] Unqualified PORK_TERMS — should be Not Applicable")

check_pork(
    "bacon → Not Applicable",
    _make_evidence("P001", "BLT", "Test Kitchen",
                   ["bacon", "lettuce", "tomato", "mayo", "sourdough"]),
    expected_conclusion="Not Applicable",
    expected_status="not_applicable",
)

check_pork(
    "prosciutto → Not Applicable",
    _make_evidence("P002", "Prosciutto Flatbread", "Test Kitchen",
                   ["prosciutto", "arugula", "parmesan", "flatbread"]),
    expected_conclusion="Not Applicable",
    expected_status="not_applicable",
)

check_pork(
    "carnitas → Not Applicable",
    _make_evidence("P003", "Carnitas Tacos", "Test Kitchen",
                   ["carnitas", "corn tortilla", "salsa verde", "cilantro"]),
    expected_conclusion="Not Applicable",
    expected_status="not_applicable",
)

check_pork(
    "pork belly → Not Applicable",
    _make_evidence("P004", "Pork Belly Ramen", "Test Kitchen",
                   ["ramen noodles", "pork belly", "soft-boiled egg", "soy broth"]),
    expected_conclusion="Not Applicable",
    expected_status="not_applicable",
)

check_pork(
    "lard → Not Applicable",
    _make_evidence("P005", "Flour Tortillas", "Test Kitchen",
                   ["flour", "lard", "salt", "water"]),
    expected_conclusion="Not Applicable",
    expected_status="not_applicable",
)

print("\n[8] Qualifier overrides PORK_TERMS — should be No Pork Identified")

check_pork(
    "turkey bacon → No Pork Identified",
    _make_evidence("P006", "Turkey BLT", "Test Kitchen",
                   ["turkey bacon", "lettuce", "tomato", "whole wheat bread"]),
    expected_conclusion="No Pork Identified",
    expected_status="computed",
)

check_pork(
    "vegan bacon → No Pork Identified",
    _make_evidence("P007", "Vegan Breakfast", "Test Kitchen",
                   ["vegan bacon", "scrambled tofu", "roasted potatoes"]),
    expected_conclusion="No Pork Identified",
    expected_status="computed",
)

print("\n[9] Unresolved AMBIGUOUS_PORK_TERMS — should be Unknown")

check_pork(
    "sausage (unresolved) → Unknown",
    _make_evidence("P008", "Sausage Pizza", "Test Kitchen",
                   ["pizza dough", "sausage", "mozzarella", "tomato sauce"]),
    expected_conclusion="Unknown",
    expected_status="unknown",
)

check_pork(
    "pepperoni (unresolved) → Unknown",
    _make_evidence("P009", "Pepperoni Pizza", "Test Kitchen",
                   ["pizza dough", "pepperoni", "mozzarella", "tomato sauce"]),
    expected_conclusion="Unknown",
    expected_status="unknown",
)

check_pork(
    "chorizo (unresolved) → Unknown",
    _make_evidence("P010", "Chorizo Bowl", "Test Kitchen",
                   ["rice", "chorizo", "black beans", "pico de gallo"]),
    expected_conclusion="Unknown",
    expected_status="unknown",
)

check_pork(
    "salami (unresolved) → Unknown",
    _make_evidence("P011", "Charcuterie", "Test Kitchen",
                   ["salami", "cheddar", "crackers", "grapes"]),
    expected_conclusion="Unknown",
    expected_status="unknown",
)

print("\n[10] AMBIGUOUS_PORK_TERMS resolved by qualifier — should be No Pork Identified")

check_pork(
    "turkey sausage → No Pork Identified",
    _make_evidence("P012", "Turkey Sausage Scramble", "Test Kitchen",
                   ["turkey sausage", "eggs", "bell peppers", "onions"]),
    expected_conclusion="No Pork Identified",
    expected_status="computed",
)

check_pork(
    "chicken chorizo → No Pork Identified",
    _make_evidence("P013", "Chicken Chorizo Tacos", "Test Kitchen",
                   ["chicken chorizo", "corn tortilla", "avocado", "lime"]),
    expected_conclusion="No Pork Identified",
    expected_status="computed",
)

check_pork(
    "beef pepperoni → No Pork Identified",
    _make_evidence("P014", "Beef Pepperoni Flatbread", "Test Kitchen",
                   ["flatbread", "beef pepperoni", "mozzarella", "marinara"]),
    expected_conclusion="No Pork Identified",
    expected_status="computed",
)

check_pork(
    "vegan chorizo → No Pork Identified",
    _make_evidence("P015", "Vegan Burrito", "Test Kitchen",
                   ["flour tortilla", "vegan chorizo", "rice", "black beans"]),
    expected_conclusion="No Pork Identified",
    expected_status="computed",
)

print("\n[11] Clean pork-free dishes — should be No Pork Identified")

check_pork(
    "all vegetables → No Pork Identified",
    _make_evidence("P016", "Garden Salad", "Test Kitchen",
                   ["romaine", "tomato", "cucumber", "red onion", "balsamic"]),
    expected_conclusion="No Pork Identified",
    expected_status="computed",
)

check_pork(
    "beef dish → No Pork Identified",
    _make_evidence("P017", "Beef Brisket Plate", "Test Kitchen",
                   ["beef brisket", "coleslaw", "pickles", "brioche bun"]),
    expected_conclusion="No Pork Identified",
    expected_status="computed",
)

check_pork(
    "chicken dish → No Pork Identified",
    _make_evidence("P018", "Grilled Chicken Sandwich", "Test Kitchen",
                   ["grilled chicken", "lettuce", "tomato", "brioche bun"]),
    expected_conclusion="No Pork Identified",
    expected_status="computed",
)

print("\n[12] Real pork + qualifier in same dish — pork wins")

check_pork(
    "bacon + turkey bacon in same dish → Not Applicable (real pork wins)",
    _make_evidence("P019", "Mixed Breakfast", "Test Kitchen",
                   ["bacon", "turkey bacon", "eggs", "toast"]),
    expected_conclusion="Not Applicable",
    expected_status="not_applicable",
)


# ── Summary ───────────────────────────────────────────────────────────────────

total = len(PASSED) + len(FAILED)
print(f"\n{'=' * 60}")
print(f"RESULTS:  {len(PASSED)} passed  /  {len(FAILED)} failed  /  {total} total")

if FAILED:
    print(f"\nFAILED:")
    for name in FAILED:
        print(f"  ✗  {name}")
    sys.exit(1)
else:
    print("All tests passed.")
    sys.exit(0)
