"""
validate_staging.py — GoldPan staging file validator.

Validates one or more staging JSON files before any write occurs.
Uses schema.py as the canonical source for required fields, ID patterns,
and allowed enum values.

Principle: Validate before write. A staging file that fails validation
must never reach upsert_dishes.py.

Severity levels:
  ERROR   — blocks the write; must be fixed before upsert
  WARNING — advisory; does not block, but should be reviewed

Exit codes:
  0  — validation passed (no ERRORs; warnings may be present)
  1  — validation failed (one or more ERRORs found)

Usage:
  python3 validate_staging.py                     # validates staging.json
  python3 validate_staging.py staging_chopt.json  # validates named file
  python3 validate_staging.py --all               # validates all staging_*.json files
"""

import json
import re
import sys

import glob
import os
from dataclasses import dataclass, field
from typing import Optional

from schema import (
    TRANSPARENCY_LEVELS,
    TRANSPARENCY_LEVEL_ALIASES,
    RESTAURANT_ID_PATTERN,
    DISH_ID_PATTERN,
    RECOGNIZED_DIETARY_TAGS,
    CANONICAL_ALLERGEN_FLAGS,
    ALLERGEN_FLAG_ALIASES,
    MACRO_ELIGIBLE_SOURCES,
)


# ── Validation result ─────────────────────────────────────────────────────────

@dataclass
class Finding:
    severity: str          # "ERROR" | "WARNING"
    location: str          # human-readable path (e.g. "dish D032 > ingredient 2")
    code:     str          # short machine-readable code (e.g. "MISSING_DISH_ID")
    message:  str          # full human-readable description


@dataclass
class ValidationResult:
    file_path:  str
    findings:   list = field(default_factory=list)

    def error(self, location: str, code: str, message: str):
        self.findings.append(Finding("ERROR", location, code, message))

    def warn(self, location: str, code: str, message: str):
        self.findings.append(Finding("WARNING", location, code, message))

    @property
    def errors(self):
        return [f for f in self.findings if f.severity == "ERROR"]

    @property
    def warnings(self):
        return [f for f in self.findings if f.severity == "WARNING"]

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0


# ── Validators ────────────────────────────────────────────────────────────────

def validate_top_level(data: dict, result: ValidationResult):
    """Validate restaurant-level required fields and formats."""

    # restaurant_id — required, must match R\d{3}
    rid = data.get("restaurant_id", "").strip()
    if not rid:
        result.error("top level", "MISSING_RESTAURANT_ID",
                     "restaurant_id is required.")
    elif not re.match(RESTAURANT_ID_PATTERN, rid):
        result.error("top level", "INVALID_RESTAURANT_ID",
                     f"restaurant_id {rid!r} does not match expected pattern "
                     f"(e.g. R001, R025). Pattern: {RESTAURANT_ID_PATTERN}")

    # dishes — required, must be a non-empty list
    dishes = data.get("dishes")
    if dishes is None:
        result.error("top level", "MISSING_DISHES",
                     "dishes array is required.")
    elif not isinstance(dishes, list):
        result.error("top level", "DISHES_NOT_ARRAY",
                     f"dishes must be a JSON array; got {type(dishes).__name__}.")
    elif len(dishes) == 0:
        result.warn("top level", "EMPTY_DISHES",
                    "dishes array is empty. Nothing will be written.")

    # restaurant_name — required for full staging; optional for ingredient patches
    rname = data.get("restaurant_name", "").strip()
    if not rname and not data.get("restaurant_note"):
        result.warn("top level", "MISSING_RESTAURANT_NAME",
                    "restaurant_name is missing. upsert_dishes.py will fail when "
                    "building ingredient rows.")

    # location — required for full staging (used in Ingredient Details rows)
    if not data.get("location", "").strip() and not data.get("restaurant_note"):
        result.warn("top level", "MISSING_LOCATION",
                    "location is missing. upsert_dishes.py will fail when building "
                    "ingredient rows (location is a required column).")


def _detect_scoring_model(dish: dict) -> str:
    """
    Detect which scoring model a dish uses.

    Returns:
      'additive'     — canonical: components 0-25, total == sum(components)
      'normalized'   — legacy: components 0-10, total ≈ round(sum/40*100)
      'unrecognized' — components 0-10 but total doesn't follow the formula
      'absent'       — scoring fields not present
    """
    comp_fields = ["core_clarity", "sauce_disclosure", "allergen_transparency", "prep_clarity"]
    if not all(f in dish for f in comp_fields) or "total_score" not in dish:
        return "absent"
    comps = [dish[f] for f in comp_fields]
    total = dish["total_score"]
    if not all(isinstance(c, (int, float)) for c in comps) or not isinstance(total, (int, float)):
        return "absent"
    if sum(comps) == total:
        return "additive"
    if max(comps) <= 10:
        norm = round(sum(comps) / 40 * 100)
        if abs(norm - total) <= 1:
            return "normalized"
        return "unrecognized"
    return "unrecognized"


def validate_dish(dish: dict, dish_idx: int, result: ValidationResult):
    """Validate one dish entry."""
    loc = f"dishes[{dish_idx}]"

    # dish_id — required, must match D\d{3}
    did = str(dish.get("dish_id", "")).strip()
    if not did:
        result.error(loc, "MISSING_DISH_ID",
                     "dish_id is required.")
        loc_label = loc
    elif not re.match(DISH_ID_PATTERN, did):
        result.error(f"{loc} ({did})", "INVALID_DISH_ID",
                     f"dish_id {did!r} does not match expected pattern "
                     f"(e.g. D001, D750). Pattern: {DISH_ID_PATTERN}")
        loc_label = f"{loc} ({did})"
    else:
        loc_label = f"{loc} ({did})"

    # dish_name — required
    dname = str(dish.get("dish_name", "")).strip()
    if not dname:
        result.error(loc_label, "MISSING_DISH_NAME",
                     "dish_name is required.")

    # menu_verified — must be boolean true (GP acquisition gate, per upsert_dishes.py)
    if dish.get("menu_verified") is not True:
        if "menu_verified" not in dish:
            result.error(loc_label, "MISSING_MENU_VERIFIED",
                         "menu_verified is missing. Every dish must have "
                         '"menu_verified": true — canvasser attestation that this dish '
                         "appears on the restaurant's current live menu. "
                         "(Use --force in upsert_dishes.py for legacy files only.)")
        else:
            result.error(loc_label, "MENU_VERIFIED_NOT_TRUE",
                         f"menu_verified is {dish['menu_verified']!r}, expected true. "
                         "Dish has not been confirmed on the current live menu.")

    # transparency_level / transparency_tier — must be a recognized value if present
    for field_name in ("transparency_level", "transparency_tier"):
        val = str(dish.get(field_name, "")).strip()
        if val:
            # Accept canonical values and known aliases
            if val not in TRANSPARENCY_LEVELS and val.lower() not in TRANSPARENCY_LEVEL_ALIASES:
                result.error(loc_label, "INVALID_TRANSPARENCY_LEVEL",
                             f"{field_name} {val!r} is not a recognized value. "
                             f"Valid values: {sorted(TRANSPARENCY_LEVELS)}")

    # ingredients — warn if missing (dish can exist without ingredients, but it
    # won't contribute to derived filter computation)
    ingredients = dish.get("ingredients")
    if ingredients is None:
        result.warn(loc_label, "NO_INGREDIENTS",
                    "No ingredients array. This dish will not contribute to derived "
                    "filter computation (GP-RULE-007 macro_dependent dependency cannot "
                    "be satisfied without an ingredient list).")
    elif not isinstance(ingredients, list):
        result.error(loc_label, "INGREDIENTS_NOT_ARRAY",
                     f"ingredients must be a JSON array; got {type(ingredients).__name__}.")
    elif len(ingredients) == 0:
        result.warn(loc_label, "EMPTY_INGREDIENTS",
                    "ingredients array is present but empty.")
    else:
        for i, ing in enumerate(ingredients):
            validate_ingredient(ing, i, did or str(dish_idx), result)

    # dietary_tags — warn on unrecognized values (vocabulary is open, just catches typos)
    tags = dish.get("dietary_tags", [])
    if isinstance(tags, list):
        for tag in tags:
            t = str(tag).strip().lower()
            if t and t not in RECOGNIZED_DIETARY_TAGS:
                result.warn(loc_label, "UNRECOGNIZED_DIETARY_TAG",
                            f"dietary_tag {tag!r} is not in the recognized tag vocabulary. "
                            f"If intentional, add it to RECOGNIZED_DIETARY_TAGS in schema.py.")

    # allergen_summary — advisory if missing
    if not str(dish.get("allergen_summary", "")).strip():
        result.warn(loc_label, "MISSING_ALLERGEN_SUMMARY",
                    "allergen_summary is missing. Customers rely on this for safety decisions.")

    # Score consistency — if any schema-A score field is present, all should be
    schema_a_fields = ["core_clarity", "sauce_disclosure", "allergen_transparency",
                       "prep_clarity", "total_score"]
    schema_b_fields = ["core_ingredient_score", "sauce_score", "prep_score",
                       "allergen_transparency_score", "transparency_score"]

    has_a = any(f in dish for f in schema_a_fields)
    has_b = any(f in dish for f in schema_b_fields)

    if has_a and has_b:
        result.warn(loc_label, "MIXED_SCORING_SCHEMAS",
                    "Dish has fields from both Schema A (core_clarity, total_score) and "
                    "Schema B (core_ingredient_score, transparency_score). "
                    "Use one schema consistently per restaurant.")

    if has_a:
        for f in schema_a_fields:
            val = dish.get(f)
            if val is None:
                result.warn(loc_label, "INCOMPLETE_SCORING",
                            f"Schema A score field {f!r} is missing. "
                            f"All five fields should be present: {schema_a_fields}")
                break
        # Detect and validate the scoring model.
        # Canonical model (GP scoring architecture): components on 0-25 scale,
        # total_score = sum(components). See docs/SCORING_ARCHITECTURE.md.
        model = _detect_scoring_model(dish)
        if model == "additive":
            pass  # canonical — no finding needed
        elif model == "normalized":
            result.warn(loc_label, "LEGACY_SCORING_FORMAT",
                        "Scoring uses the legacy normalized model: components appear to be "
                        "on a 0-10 scale, with total_score derived via "
                        "round(sum / 40 * 100). The canonical GoldPan model stores "
                        "components on a 0-25 scale with total_score = sum(components). "
                        "Run: python3 migrate_scoring.py to see the conversion plan.")
        elif model == "unrecognized":
            result.warn(loc_label, "UNRECOGNIZED_SCORING_MODEL",
                        "Component scores and total_score do not match any recognized "
                        "scoring formula (raw additive or normalized 0-10). "
                        "This dish requires manual review before scoring migration. "
                        "See docs/SCORING_ARCHITECTURE.md for the canonical model.")
        # Note: once all files have been migrated to 0-25 canonical scoring,
        # LEGACY_SCORING_FORMAT and UNRECOGNIZED_SCORING_MODEL should be upgraded
        # from WARNING to ERROR to enforce the canonical model going forward.


def validate_ingredient(ing, ing_idx: int, dish_ref: str, result: ValidationResult):
    """Validate one ingredient entry."""
    loc = f"dish {dish_ref} > ingredient[{ing_idx}]"

    # Handle string ingredients (legacy shorthand)
    if isinstance(ing, str):
        if not ing.strip():
            result.error(loc, "EMPTY_INGREDIENT_STRING",
                         "Ingredient is an empty string. Remove or replace with a named dict.")
        return

    if not isinstance(ing, dict):
        result.error(loc, "INGREDIENT_NOT_DICT",
                     f"Ingredient must be a JSON object or string; got {type(ing).__name__}.")
        return

    # name — required
    name = str(ing.get("name", "")).strip()
    if not name:
        result.error(loc, "MISSING_INGREDIENT_NAME",
                     "Ingredient name is required.")

    # allergen_flags — enforce canonical atomic allergen values.
    #
    # Parsing rules:
    #   1. Accept both array (["eggs", "milk"]) and comma-separated string ("wheat, eggs").
    #   2. Strip parenthetical qualifiers before matching: "tree nuts (almonds)" → "tree nuts".
    #      Parenthetical detail belongs in allergen_summary or a future allergen_note field.
    #   3. Check base token against CANONICAL_ALLERGEN_FLAGS (clean) and
    #      ALLERGEN_FLAG_ALIASES (non-canonical — warn with suggested replacement).
    #   4. Anything else: UNRECOGNIZED_ALLERGEN_FLAG warning.
    flags_raw = ing.get("allergen_flags", "")
    if isinstance(flags_raw, list):
        raw_tokens = [str(f).strip() for f in flags_raw if str(f).strip()]
    elif str(flags_raw).strip():
        raw_tokens = [t.strip() for t in str(flags_raw).split(",") if t.strip()]
    else:
        raw_tokens = []

    for token in raw_tokens:
        # Strip parenthetical qualifier: "tree nuts (almonds)" → "tree nuts"
        has_paren = bool(re.search(r"\(.*?\)", token))
        base = re.sub(r"\s*\(.*?\)", "", token).strip().lower()
        if not base:
            continue
        if base in CANONICAL_ALLERGEN_FLAGS:
            if has_paren:
                result.warn(loc, "ALLERGEN_PARENTHETICAL_DETAIL",
                            f"allergen_flag {token!r} contains parenthetical detail. "
                            f"Use the atomic form {base!r} as the flag value. "
                            f"Move the detail (e.g. specific nut variety, preparation) "
                            f"to allergen_summary or a future allergen_note field.")
        elif base in ALLERGEN_FLAG_ALIASES:
            canonical = ALLERGEN_FLAG_ALIASES[base]
            note = (" Review intent: if source means a non-wheat gluten source "
                    "(rye, barley), annotate in allergen_summary instead."
                    if base == "gluten" else "")
            result.warn(loc, "ALLERGEN_FLAG_NON_CANONICAL",
                        f"allergen_flag {token!r} is a non-canonical form. "
                        f"Use canonical form {canonical!r} instead.{note}")
        else:
            result.warn(loc, "UNRECOGNIZED_ALLERGEN_FLAG",
                        f"allergen_flag {token!r} (base: {base!r}) is not a recognized "
                        f"canonical allergen atom. Canonical values: "
                        f"{sorted(CANONICAL_ALLERGEN_FLAGS)}. "
                        f"If this is a valid allergen, add it to CANONICAL_ALLERGEN_FLAGS "
                        f"in schema.py.")


# ── File validator ────────────────────────────────────────────────────────────

def validate_file(file_path: str) -> ValidationResult:
    result = ValidationResult(file_path=file_path)

    # 1. Load and parse JSON
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        result.error("file", "FILE_NOT_FOUND",
                     f"File not found: {file_path}")
        return result
    except json.JSONDecodeError as e:
        result.error("file", "INVALID_JSON",
                     f"JSON parse error: {e}")
        return result

    if not isinstance(data, dict):
        result.error("file", "ROOT_NOT_OBJECT",
                     f"Staging file must be a JSON object at the root; got {type(data).__name__}.")
        return result

    # 2. Top-level validation
    validate_top_level(data, result)

    # 3. Dish-level validation
    dishes = data.get("dishes", [])
    if isinstance(dishes, list):
        seen_dish_ids = {}
        for i, dish in enumerate(dishes):
            if not isinstance(dish, dict):
                result.error(f"dishes[{i}]", "DISH_NOT_OBJECT",
                             f"Each dish must be a JSON object; got {type(dish).__name__}.")
                continue
            validate_dish(dish, i, result)

            # Duplicate dish_id check
            did = str(dish.get("dish_id", "")).strip()
            if did:
                if did in seen_dish_ids:
                    result.error(f"dishes[{i}] ({did})", "DUPLICATE_DISH_ID",
                                 f"dish_id {did!r} appears at both index {seen_dish_ids[did]} "
                                 f"and index {i}. Each dish must have a unique ID.")
                else:
                    seen_dish_ids[did] = i

    return result


# ── Report printer ────────────────────────────────────────────────────────────

def print_report(result: ValidationResult):
    fname = os.path.basename(result.file_path)
    status = "PASS" if result.passed else "FAIL"
    bar = "=" * 66

    print(f"\n{bar}")
    print(f"  {fname}  —  {status}")
    print(f"  {len(result.errors)} error(s)  /  {len(result.warnings)} warning(s)")
    print(bar)

    if not result.findings:
        print("  ✓  No issues found. File is ready for upsert_dishes.py.")
        return

    for f in result.findings:
        icon = "✗" if f.severity == "ERROR" else "⚠"
        print(f"\n  {icon}  [{f.severity}]  {f.code}")
        print(f"     Location : {f.location}")
        # Wrap message at ~70 chars
        words = f.message.split()
        line = "     Message  : "
        for w in words:
            if len(line) + len(w) + 1 > 72:
                print(line)
                line = "               " + w + " "
            else:
                line += w + " "
        print(line.rstrip())


def print_summary(results: list[ValidationResult]):
    total   = len(results)
    passed  = sum(1 for r in results if r.passed)
    failed  = total - passed
    errors  = sum(len(r.errors) for r in results)
    warnings = sum(len(r.warnings) for r in results)

    print(f"\n{'=' * 66}")
    print(f"  VALIDATION SUMMARY")
    print(f"  Files:    {total} total  /  {passed} passed  /  {failed} failed")
    print(f"  Findings: {errors} error(s)  /  {warnings} warning(s)")
    print(f"{'=' * 66}")

    if failed:
        print(f"\n  Files with errors:")
        for r in results:
            if not r.passed:
                print(f"    ✗  {os.path.basename(r.file_path)}  ({len(r.errors)} error(s))")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    validate_all = "--all" in args
    non_flag_args = [a for a in args if not a.startswith("--")]

    if validate_all:
        # Find all staging_*.json files in the current directory
        pattern = os.path.join(os.path.dirname(__file__) or ".", "staging*.json")
        files = sorted(glob.glob(pattern))
        if not files:
            print("No staging*.json files found.")
            sys.exit(0)
        print(f"Validating {len(files)} staging file(s)...")
    elif non_flag_args:
        files = non_flag_args
    else:
        files = ["staging.json"]

    results = []
    for fp in files:
        result = validate_file(fp)
        print_report(result)
        results.append(result)

    if len(results) > 1:
        print_summary(results)

    any_failed = any(not r.passed for r in results)
    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
