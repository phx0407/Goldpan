# GoldPan Transparency Scoring Architecture

**Status:** Canonical — active standard  
**Established:** 2026-03-13 (original four-dimension model)  
**Confirmed:** 2026-06-29 (canonical model formalized; migration path defined)

---

## Philosophy

GoldPan does not judge restaurants. GoldPan does not judge food quality.

GoldPan measures one thing only:

> **How much verified information is available so a reasonable customer does not have to guess?**

The transparency score answers the question: "If a customer wanted to know what is in this dish, how far would verified information take them before they had to guess?"

A high score does not mean the food is better. It means more verified information is disclosed, so customers can make informed decisions without assumptions.

A low score does not mean the restaurant is bad. It means less verified information is currently available in GoldPan's database — which may reflect limited disclosure, pending canvassing, or dishes with inherently fewer disclosable components.

---

## Canonical Scoring Model

The canonical model has four independent dimensions. Each measures one question about customer-facing disclosure.

| Dimension | Field | Scale | Guiding question |
|---|---|---|---|
| Core Ingredient Clarity | `core_clarity` | 0–25 | Can a customer identify the primary ingredients without guessing? |
| Sauce & Seasoning Disclosure | `sauce_disclosure` | 0–25 | Are sauces, dressings, and seasonings named or described? |
| Allergen Transparency | `allergen_transparency` | 0–25 | Are allergens explicitly disclosed from a verifiable source? |
| Preparation Input Clarity | `prep_clarity` | 0–25 | Are preparation methods and inputs disclosed? |
| **Total Score** | `total_score` | **0–100** | **Sum of the four component scores** |

### The fundamental rule

```
total_score = core_clarity + sauce_disclosure + allergen_transparency + prep_clarity
```

No hidden normalization. No weighting. The total is always the direct sum of its components. A canvasser — or any reader — can verify the total by inspection.

### Why this model

The scoring system should be as transparent as the restaurants it evaluates. A transparency measurement tool that requires hidden math to understand its own totals would be architecturally inconsistent with its purpose.

Four dimensions × 25 points = 100 points total. Every component's contribution to the total is visible and auditable.

---

## Scoring Each Dimension

Each dimension is scored on a 0–25 scale. The score represents the depth and reliability of customer-facing disclosure for that dimension — not the quality of the food.

**0–5 (Minimal):** Little or no disclosure. Customer must guess or contact the restaurant.  
**6–12 (Partial):** Some disclosure, but significant gaps remain.  
**13–18 (Moderate):** Most key information is disclosed, with some ambiguity.  
**19–25 (Strong):** Disclosure is specific, verifiable, and leaves little for the customer to guess.

Scores are assigned per dish per restaurant visit. They reflect what is available on the current live menu and any supporting documents (allergen guides, nutrition documents) at canvass time.

---

## What Does Not Affect the Score

The following do not affect transparency scores:

- Food quality or taste
- Price or value
- Preparation technique sophistication
- Restaurant ambiance or service
- Whether ingredients are locally sourced, organic, or sustainably produced
- Menu popularity

These are quality or preference dimensions. GoldPan does not measure them.

---

## Transparency Levels

| Score range | Level | Meaning |
|---|---|---|
| 75–100 | High Transparency | Strong disclosure across most dimensions |
| 45–74 | Moderate Transparency | Meaningful disclosure with notable gaps |
| 0–44 | Building Transparency | Limited disclosure; significant guessing required |

The level label is derived from `total_score`. It is a customer-facing summary, not a grade.

---

## Legacy Scoring Formats

Two legacy scoring models exist in older staging files and must be migrated.

### Legacy Model A — Normalized (0-10 components)

Some files store component scores on a 0–10 scale with total derived via:

```
total_score = round(sum(components) / 40 × 100)
```

**Detection:** components ≤ 10, total ≈ round(sum/40×100)  
**Migration:** Convert each component with `floor(x × 2.5 + 0.5)`, set total = sum(new components)  
**Tool:** `python3 migrate_scoring.py`

Conversion table (0–10 → 0–25):

| Legacy | Canonical |
|---|---|
| 0 | 0 |
| 1 | 3 |
| 2 | 5 |
| 3 | 8 |
| 4 | 10 |
| 5 | 13 |
| 6 | 15 |
| 7 | 18 |
| 8 | 20 |
| 9 | 23 |
| 10 | 25 |

### Legacy Model B — Unrecognized (independent total)

Some dishes have 0–10 components where the total does not follow the normalized formula. The total appears to have been independently assessed rather than computed from components.

**Detection:** components ≤ 10, total ≠ round(sum/40×100)  
**Migration:** Cannot be auto-migrated safely. Requires the original canvasser to re-score components on the 0–25 scale so that total = sum(components).  
**Tool:** `python3 migrate_scoring.py` identifies and flags these dishes for manual review.

---

## Validator Behavior

`validate_staging.py` enforces the canonical model.

| Condition | Finding | Severity |
|---|---|---|
| `total_score == sum(components)`, components ≤ 25 | None (canonical) | — |
| Normalized legacy model detected | `LEGACY_SCORING_FORMAT` | WARNING |
| Unrecognized model detected | `UNRECOGNIZED_SCORING_MODEL` | WARNING |
| Both Schema A and Schema B fields present | `MIXED_SCORING_SCHEMAS` | WARNING |

**Migration path:** Once all legacy files have been migrated via `migrate_scoring.py`, upgrade `LEGACY_SCORING_FORMAT` and `UNRECOGNIZED_SCORING_MODEL` from WARNING to ERROR in `validate_staging.py`. At that point, the canonical model is fully enforced and no exceptions remain.

---

## Files Currently Requiring Migration

As of 2026-06-29:

| Status | Files |
|---|---|
| Canonical (additive 0-25) | staging.json, staging_battery.json, staging_blueroot_addendum.json, staging_cayococo.json, staging_eastwest.json, staging_elis.json, staging_essential_dinner_backup.json, staging_frothymonkey.json, staging_wasabijuans.json, staging_woodencity.json, staging_yomamas.json |
| Normalized (auto-migratable) | staging_chopnfresh.json, staging_chopt.json, staging_cleaneatz.json, staging_sluttyvegan.json, staging_sohosocial.json + partial abhieatery, bahaburger, emmysquared, urbancookhouse |
| Unrecognized (manual review) | ~57 dishes across staging_abhieatery.json, staging_bahaburger.json, staging_emmysquared_pizzas.json, staging_urbancookhouse.json |
| No scoring (ingredient patches) | staging_blueroot.json, staging_rr_ingredients.json |

Run `python3 migrate_scoring.py` for the full dry-run report.

---

## Future Research

### Fixed evidence bands (post-canvassing)

**Logged:** 2026-06-29

After sufficient canvassing data and evaluator experience, evaluate whether component scores should be constrained to fixed evidence bands rather than the current continuous 0–25 scale.

Proposed band structure: **0, 5, 15, 25**

Rationale: Evaluators with calibrated experience may converge on a small number of meaningful disclosure states per dimension (none, minimal, partial, full) rather than using the full continuous range. Fixed bands would reduce inter-evaluator variance, make scoring fully auditable by inspection, and prevent scores from drifting in ambiguous mid-range territory.

This is a research question, not a current requirement. It should be revisited once:
- At least 100 dishes have been scored by more than one evaluator
- Score distribution data is available to identify natural clustering
- The trade-off between granularity and consistency is empirically measurable

Adoption would require a migration step to snap existing continuous scores to the nearest band.
