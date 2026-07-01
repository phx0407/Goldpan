# Allergen_Disclosures Tab — Schema Reference

**Status:** Draft for review  
**Governed by:** GP-RULE-014 (Allergen Evidence Rule v1.0)  
**System:** Evidence System (System A) — restaurant-provided allergen disclosures only

---

## Purpose

The Allergen_Disclosures tab is the canonical store for allergen information that
restaurants have explicitly disclosed. Every row in this tab must be traceable to a
specific source document, restaurant communication, or canvasser observation.

**This tab is not produced by GoldPan's ingredient analysis engine.** It is populated
exclusively by human canvassers working from primary sources. The derived filter engine
reads from this tab but never writes to it.

---

## Column Headers (in order)

| # | Column | Required | Type |
|---|--------|----------|------|
| 1 | `Restaurant_ID` | Required | Enum (ID format) |
| 2 | `Restaurant_Name` | Required | Free text |
| 3 | `Dish_ID` | Conditional | Enum (ID format) |
| 4 | `Dish_Name` | Conditional | Free text |
| 5 | `Allergen` | Required | Enum |
| 6 | `Disclosure_Status` | Required | Enum |
| 7 | `Source_Type` | Required | Enum |
| 8 | `Source_Reference` | Required | Free text |
| 9 | `Source_Date` | Required | Date (ISO 8601) |
| 10 | `Scope` | Required | Enum |
| 11 | `Notes` | Optional | Free text |

---

## Field Definitions and Validation Rules

---

### 1. `Restaurant_ID`
**Required.** The GoldPan-assigned identifier for the restaurant.

- Format: `R` followed by exactly 3 digits (e.g., `R001`, `R025`)
- Must match a Restaurant_ID in the Menu Source Registry
- Any ID that does not match this pattern is a validation error

---

### 2. `Restaurant_Name`
**Required.** The restaurant's display name, for human readability.

- Free text; no format constraint
- Must be consistent with the name in the Menu Source Registry
- Does not affect processing — Restaurant_ID is the authoritative key

---

### 3. `Dish_ID`
**Conditional.** Required when `Scope = dish`. Must be blank when `Scope = restaurant`.

- Format: `D` followed by exactly 3 digits (e.g., `D032`, `D150`)
- Must match an active Dish_ID in the Goldpan Dish Level Data tab
- Validation errors:
  - Present when `Scope = restaurant` → error (scope conflict)
  - Blank when `Scope = dish` → error (dish scope requires a Dish_ID)
  - Does not match a known active Dish_ID → error (referential integrity)

---

### 4. `Dish_Name`
**Conditional.** Required when `Scope = dish`. Must be blank when `Scope = restaurant`.

- Free text; for human readability only
- Must be consistent with the Dish_Name in Goldpan Dish Level Data
- Does not affect processing — Dish_ID is the authoritative key

---

### 5. `Allergen`
**Required.** The allergen this disclosure applies to.

Valid values (the nine FDA major food allergens):

| Value | Allergen |
|-------|----------|
| `wheat` | Wheat |
| `milk` | Milk / Dairy |
| `eggs` | Eggs |
| `soy` | Soy |
| `sesame` | Sesame |
| `peanuts` | Peanuts |
| `tree_nuts` | Tree Nuts |
| `fish` | Fish |
| `shellfish` | Shellfish |

- Aliases that will generate a warning (use canonical form instead):

  | Entered | Use instead |
  |---------|-------------|
  | `dairy` | `milk` |
  | `egg` | `eggs` |
  | `soybean` / `soybeans` | `soy` |
  | `peanut` | `peanuts` |
  | `tree nut` / `tree nuts` | `tree_nuts` |
  | `gluten` | `wheat` (verify: means wheat specifically, not rye/barley) |

- Any value not in the canonical set and not a known alias is a validation error

---

### 6. `Disclosure_Status`
**Required.** The type of allergen claim the restaurant made.

| Value | Meaning |
|-------|---------|
| `contains` | Restaurant explicitly states this dish contains this allergen |
| `may_contain` | Restaurant states cross-contamination risk exists |
| `free_from` | Restaurant explicitly states this dish is free from this allergen |

Rules:
- `free_from` requires `Source_Type` to be in the Tier 1 or Tier 2 set (see Source_Type below). A `free_from` row with a Tier 3+ source is a validation error.
- `contains` and `may_contain` may use any macro-eligible source type
- **`free_from` is an internal Evidence System value.** It is never displayed to consumers as-is. The consumer-facing label is determined by the presentation layer based on source tier, per GP-RULE-016.

---

### 7. `Source_Type`
**Required.** The type of source from which this disclosure was obtained.

All macro-eligible source types are valid for `contains` and `may_contain`:

| Value | Description | Eligible for `free_from`? |
|-------|-------------|--------------------------|
| `allergen_guide` | Official allergen guide published by the restaurant | ✓ Tier 1 |
| `nutrition_document` | Official nutrition/ingredient document | ✓ Tier 1 |
| `restaurant_confirmation` | Direct confirmation from restaurant staff or management | ✓ Tier 1 |
| `menu` | Printed or in-store menu | ✓ Tier 2 |
| `website` | Restaurant's own website | ✓ Tier 2 |
| `ordering_platform` | Restaurant-managed online ordering platform | ✗ Tier 3 |
| `restaurant_qa` | Canvasser Q&A with restaurant | ✗ Tier 4 |
| `pdf` | Legacy PDF source (pre-dating allergen_guide / nutrition_document split) | ✗ Legacy |

Validation errors:
- Value not in the recognized source type list → error
- `Disclosure_Status = free_from` with a Tier 3 or legacy source → error

---

### 8. `Source_Reference`
**Required.** A specific, traceable citation for the disclosure.

- Free text, but must be specific enough to locate the source
- Examples:
  - URL: `https://restaurant.com/allergen-guide`
  - Document name: `Spring 2025 Allergen Guide (PDF, received 2025-03-15)`
  - Email reference: `Email from manager J. Smith, 2025-04-02`
  - Menu reference: `Printed menu, Table 4, visited 2025-05-10`
- "Restaurant website" or "menu" alone is insufficient — include the date and enough detail to re-locate the source
- No format constraint enforced by validator, but canvassers should follow the examples above

---

### 9. `Source_Date`
**Required.** The date the source was accessed or the disclosure was received.

- Format: ISO 8601 date — `YYYY-MM-DD` (e.g., `2025-03-15`)
- Must be a valid calendar date
- Must not be in the future
- This is the date of the source, not the date the row was entered

---

### 10. `Scope`
**Required.** Whether this disclosure applies to a specific dish or to the restaurant broadly.

| Value | Meaning | Dish_ID / Dish_Name |
|-------|---------|---------------------|
| `dish` | Disclosure applies to a specific dish | Required |
| `restaurant` | Disclosure applies to the restaurant as a whole (e.g., "our kitchen handles tree nuts") | Must be blank |

- Restaurant-scope disclosures are applied to all active dishes for that restaurant during fetch
- Dish-scope and restaurant-scope rows form different natural keys for duplicate detection (see below)

---

### 11. `Notes`
**Optional.** Canvasser notes, caveats, or context that do not belong in any structured field.

- Free text; no format constraint
- Examples of appropriate use:
  - "Allergen guide covers all menu items except seasonal specials"
  - "Staff confirmed verbally; written confirmation pending"
  - "Page 3 of PDF"
- Do not put source citation details here — those belong in `Source_Reference`

---

## Duplicate Detection

Two rows are duplicates based on `Scope`:

| Scope | Natural key |
|-------|-------------|
| `dish` | `(Dish_ID, Allergen, Disclosure_Status)` |
| `restaurant` | `(Restaurant_ID, Allergen, Disclosure_Status)` |

If the same allergen + disclosure status is recorded twice for the same dish (or restaurant), the second row is a validation error. If a restaurant updates a disclosure, the old row should be removed (or annotated in Notes) before the new row is added.

---

## Example Rows

### Example 1 — Dish-scoped disclosure (`free_from`)

| Field | Value |
|-------|-------|
| `Restaurant_ID` | `R012` |
| `Restaurant_Name` | `Example Kitchen` |
| `Dish_ID` | `D047` |
| `Dish_Name` | `Grilled Salmon Bowl` |
| `Allergen` | `wheat` |
| `Disclosure_Status` | `free_from` |
| `Source_Type` | `allergen_guide` |
| `Source_Reference` | `https://examplekitchen.com/allergen-guide (accessed 2025-06-01)` |
| `Source_Date` | `2025-06-01` |
| `Scope` | `dish` |
| `Notes` | `Guide lists all bowls; confirmed D047 specifically` |

### Example 2 — Restaurant-scoped disclosure (`contains`)

| Field | Value |
|-------|-------|
| `Restaurant_ID` | `R007` |
| `Restaurant_Name` | `Noodle House` |
| `Dish_ID` | *(blank)* |
| `Dish_Name` | *(blank)* |
| `Allergen` | `tree_nuts` |
| `Disclosure_Status` | `contains` |
| `Source_Type` | `website` |
| `Source_Reference` | `https://noodlehouse.com/allergens — "Our kitchen uses tree nuts in several dishes" (accessed 2025-05-20)` |
| `Source_Date` | `2025-05-20` |
| `Scope` | `restaurant` |
| `Notes` | `Broad kitchen notice; not dish-specific` |

---

## Canvasser Notes

### What you MAY enter

- Any disclosure that originates from a restaurant-provided source (guide, menu,
  website, email, verbal confirmation)
- A restaurant-scope row for a kitchen-wide allergen notice that applies broadly
- A dish-scope row for a disclosure that the restaurant makes about a specific dish
- A `free_from` disclosure if you have a Tier 1 or Tier 2 source (see Source_Type table)

### What you may NOT enter

- Inferences drawn from an ingredient list ("this dish has no wheat-containing
  ingredients, therefore I'll add a free_from row") — this is ingredient analysis,
  not a restaurant disclosure
- A `free_from` row sourced from `ordering_platform`, `restaurant_qa`, or `pdf`
- A row for a dish that is not active in the Goldpan Dish Level Data tab
- Allergen aliases instead of canonical slugs (e.g., enter `milk`, not `dairy`;
  `tree_nuts`, not `tree nuts`)
- Future dates in `Source_Date`
- Multiple rows with the same natural key (same dish + allergen + disclosure_status,
  or same restaurant + allergen + disclosure_status for restaurant-scope)

### When in doubt

- Record what the restaurant actually said, not your interpretation of it
- Use `Notes` for caveats, not for structured data
- If a source is ambiguous about whether it applies to the whole restaurant or a
  specific dish, default to the narrower scope (dish) and note the ambiguity

---

## Invariant: Ingredient Analysis Never Creates Rows Here

**The GoldPan derived filter engine reads this tab. It never writes to it.**

GoldPan's ingredient analysis (System B — Knowledge System) produces conclusions
about whether identified ingredients suggest the presence or absence of allergens.
Those conclusions live in `derived_filters.json` and flow into the `derived_filters`
field of each dish in `dishes.json`.

They do not create, modify, or backfill rows in the Allergen_Disclosures tab.

A row in this tab is a record of what a restaurant disclosed. A derived filter
conclusion is a record of what GoldPan inferred from ingredient evidence. These are
different things, governed by different rules, and stored in different places.

Mixing them would corrupt the Evidence System by converting computed output into
durable evidence — a violation of GP-RULE-014 and the evidence lifecycle invariant
documented in ALLERGEN_ARCHITECTURE.md.

---

## Governing Rules

| Rule | Name |
|------|------|
| GP-RULE-001 | Material Evidence Rule v1.1 |
| GP-RULE-006 | Derived Filter Explanation Rule v1.0 |
| GP-RULE-007 | Filter Evidence Dependency Rule v1.0 |
| GP-RULE-010 | Source Authority Hierarchy Rule v1.0 |
| GP-RULE-014 | Allergen Evidence Rule v1.0 |
| GP-RULE-015 | Allergen Confidence Ceiling Rule v1.0 |
| GP-RULE-016 | Allergen Communication Rule v1.0 |
