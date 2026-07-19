# GoldPan™ Corrections File Schema
**Version:** 1.0  
**Date:** 2026-07-04  
**Governed by:** GOLDPAN_OS_ARCHITECTURE.md

---

## Purpose

A `_corrections.json` file is written by a human reviewer when returning an intake packet.
It records structured corrections — what the agent produced, what it should have produced,
and why — in a form that `rule_extractor.py` can group into candidate intake rules.

Corrections never modify the packet directly. They feed the Rule Learning subsystem only.

---

## File Naming Convention

```
{packet_stem}_corrections.json
```

Example: `good_health_to_be_hail_2026-07-04_corrections.json`

The file lives in the same directory as the packet it corrects (`intake_packets/`).

---

## Top-Level Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `$schema` | string | Yes | Always `"goldpan-corrections-v1"` |
| `domain` | string enum | Yes | Which GoldPan OS produced the packet. See Domain Enum. |
| `packet_ref` | string | Yes | Filename of the packet being corrected |
| `restaurant_name` | string | Yes | Restaurant name (for human readability) |
| `reviewer` | string | Yes | Who performed the review |
| `review_date` | ISO date | Yes | Date of review (YYYY-MM-DD) |
| `reviewer_status` | string enum | Yes | `returned` or `approved_with_corrections` |
| `corrections` | array | Yes | One or more Correction objects |

### Domain Enum

- `intake` — Restaurant Intake OS
- `biz_dev` — Business Development OS (future)
- `customer_support` — Customer Support OS (future)
- `operations` — Restaurant Operations OS (future)

---

## Correction Object

Each item in `corrections` represents a single discrete error.

| Field | Type | Required | Description |
|---|---|---|---|
| `correction_id` | string | Yes | Unique within file. Format: `C001`, `C002`, … |
| `rule_type` | string enum | Yes | Category of rule this correction supports. See Rule Type Enum. |
| `trigger_key` | string | Yes | Normalized slug used for grouping. Snake_case. No spaces. |
| `trigger_pattern` | string | Yes | Human-readable description of what triggers this error |
| `dish` | string | No | Dish name where error occurred. Use `"restaurant_level"` for packet-wide errors. |
| `menu_text` | string | Yes | Verbatim source text that caused the error |
| `wrong_output` | WrongOutput | Yes | What the agent produced |
| `correct_output` | CorrectOutput | Yes | What it should have produced |
| `reason` | string | Yes | Reviewer explanation in plain English |
| `proposed_rule_text_draft` | string | No | Draft rule text for the Intake Standard. Human-editable before approval. |
| `target_section` | string | Yes | Which section of INTAKE_AGENT_STANDARD.md this rule belongs in |
| `safety_critical` | boolean | Yes | `true` if allergen or food safety related. Promotes at 1 observation instead of 2 restaurants. |

### WrongOutput Object

```json
{
  "field": "ingredients[].allergen_flags",
  "value": ["seaweed"]
}
```

`field` uses dot/bracket notation to identify the location in the packet structure.

### CorrectOutput Object

```json
{
  "field": "ingredients[].allergen_flags",
  "value": []
}
```

---

## Rule Type Enum

| Value | Governs | Standard Section |
|---|---|---|
| `verbatim_component_trigger` | When to use verbatim_component vs. ingredient record | Generic Component Policy |
| `allergen_flag_constraint` | When allergen_flags may and may not be set | Inference Policy |
| `ingredient_classification` | How to assign `type`, `role`, `preparation` | Ingredient Object |
| `section_propagation` | How section-level facts apply to individual dishes | Quality Assurance |
| `consistency_rule` | Same treatment for the same input across a packet | Quality Assurance |
| `flag_batching` | When to consolidate vs. create individual Review Flags | Required Supporting Objects |

---

## Promotion Thresholds (applied by rule_extractor.py)

| Condition | Promotion |
|---|---|
| `safety_critical: true` AND `times_observed >= 1` | `draft` → `ready_for_review` |
| `safety_critical: false` AND `restaurants_observed >= 2` | `draft` → `ready_for_review` |
| Otherwise | Remains `draft` |

Human approval is mandatory before any candidate rule advances beyond `ready_for_review`.

---

## Promotion Status Lifecycle

```
draft → ready_for_review → approved → merged
                        ↘ rejected
```

The extractor never downgrades a status. `approved`, `rejected`, and `merged` are terminal.

---

## Example File (abbreviated)

```json
{
  "$schema": "goldpan-corrections-v1",
  "domain": "intake",
  "packet_ref": "example_restaurant_2026-07-04.json",
  "restaurant_name": "Example Restaurant",
  "reviewer": "human",
  "review_date": "2026-07-04",
  "reviewer_status": "returned",
  "corrections": [
    {
      "correction_id": "C001",
      "rule_type": "allergen_flag_constraint",
      "trigger_key": "inferred_non_major_allergen",
      "trigger_pattern": "Allergen flag set from ingredient category, not restaurant disclosure",
      "dish": "Plant Based Tuna on Lettuce",
      "menu_text": "Seaweed",
      "wrong_output": {
        "field": "ingredients[name=Seaweed].allergen_flags",
        "value": ["seaweed"]
      },
      "correct_output": {
        "field": "ingredients[name=Seaweed].allergen_flags",
        "value": []
      },
      "reason": "Seaweed is not a recognized major allergen. allergen_flags must reflect only explicit restaurant disclosure, not ingredient category membership.",
      "proposed_rule_text_draft": "Do not set allergen_flags based on ingredient category. Only the following may be flagged, and only when explicitly disclosed: gluten, tree_nuts, peanuts, soy, dairy, shellfish, fish, eggs, sesame.",
      "target_section": "GoldPan™ Evidence Standard / Inference Policy",
      "safety_critical": true
    }
  ]
}
```

---

## Relationship to Other Documents

- **INTAKE_AGENT_STANDARD.md** — the Standard that approved rules are eventually merged into
- **rule_extractor.py** — reads corrections files and maintains `candidate_rules.json`
- **candidate_rules.json** — accumulates candidate rules pending human approval
- **GOLDPAN_OS_ARCHITECTURE.md** — defines the OS boundary this subsystem operates within
