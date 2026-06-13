# Goldpan Data Rules

## Core

| Rule | Definition |
|------|-----------|
| System_Principle | Record what is known, preserve what is unknown, never guess |
| Data_Layers | Ingredient = reality, Dish = claims, Score = interpretation. Do not mix layers. Restaurant confirmation forks into reality (facts) and claims (conclusions). |

---

## Ingredient Rules

| Rule | Definition | Allowed Values |
|------|-----------|----------------|
| Ingredient_Inclusion | Only include ingredients explicitly listed on menu. Do not infer missing components. | — |
| Ingredient_Type_Definition | Standard = single, unprocessed item. Compound = anything created from multiple inputs (sauce, dressing, seasoned item, composite). | standard, compound |
| Ingredient_Source_Definition | Classify origin of ingredient. Unknown allowed if unclear. | plant-based, animal, dairy, seafood, neutral, unknown |
| Ingredient_Source_Rule | If unclear or composite → unknown. Do not force classification. | — |
| Allergen_Flags_Rule | If clearly present → label. If not stated → none. If unclear → unknown. No inference from typical recipes. | none, dairy, egg, wheat, soy, shellfish, tree nuts, unknown |
| Preparation_Rule | Only record if explicitly stated. Otherwise use none. | none, grilled, fried, baked, cooked, raw, fermented, pickled, etc. |
| Cut_Type_Rule | Only record if explicitly stated. Otherwise use none. | none, sliced, diced, shredded, crumbled, halved, etc. |
| Component_Role_Definition | Role of ingredient in dish. | base, protein, topping, sauce, garnish, sweetener |

---

## Dish Rules

| Rule | Definition | Allowed Values |
|------|-----------|----------------|
| Dietary_Tags_Rule | Only use explicit restaurant claims. Symbols count as claims. Allergens come from Allergen_Flags, not tags. | vegan, vegetarian, gluten-free, dairy-free, none |
| Controlled_Vocabulary | Dietary tags use one fixed list shared by form, database, and discover. No free text — out-of-list tags create dead data. | — |
| Tag_Logic | Multiple symbols = multiple tags. No symbol = none. | — |
| Tag_Source | Where dietary claim came from. Menu is default. | menu, confirmed |
| Verification_Status | Default = unconfirmed. | unconfirmed, restaurant-confirmed and unverified, verified |

---

## Unknown Rule

| Rule | Definition |
|------|-----------|
| Unknown_Principle | Unknown is preferred over incorrect data. Use for sauces, dressings, composite items. |
| Unknown_Usage | Use unknown when information is not explicitly stated. Do not guess or infer. |

---

## System Rules

| Rule | Definition |
|------|-----------|
| Source_Of_Truth | Discover reads only from the database. Nothing reaches a diner that is not in the database first. |
| Separation_Rule | Dish claims (conclusions) do not override ingredient data. |
| No_Override_Rule | Do not modify ingredient data to match a dietary tag or self-graded label. Disclosed composition and prep facts DO update reality (see Confirmation). |
| Speed_Rule | Target under 60 seconds per dish. If unsure → unknown and move on. |

---

## Confirmation Rules

| Rule | Definition |
|------|-----------|
| Dataset_Separation | Reality and Confirmation are two datasets, never merged. Reality = your analysis. Confirmation = restaurant input. |
| Provenance_Stamp | Every data point carries its source. | analysis-derived, restaurant-confirmed |
| Confirmation_Outranks_Canvass | For composition and prep facts, kitchen disclosure outranks a menu canvass. |
| Fact_Update_Rule | A disclosed composition or prep fact updates reality and recomputes the score. Stamped restaurant-confirmed and unverified. |
| Conclusion_Hold_Rule | A self-graded conclusion such as a dietary tag never moves the score and is validated against disclosed facts. The restaurant cannot grade itself. |
| Conflict_Resolution | Fact vs fact → provenance wins (kitchen over canvass), reality updates, score recomputes. Conclusion vs analysis → both held and flagged, score unchanged. |
| History_Preservation | When reality updates, the prior value and its source are kept in history. |
| Form_Write_Scope | Form writes the dish record (name, description, category, availability) and disclosed facts only. Never a score, never a conclusion into reality. |
| Absence_Rule | Leave-as-is and blank stay unconfirmed. An untouched field is never read as confirmed. |
| Field_Test | A form field must power a filter, feed the score, or surface in the detail panel, or it is cut. Prevents dead data. |

---

## Scoring Rules

### Internal Check (apply before every score)
> Would a reasonable customer feel like they had to guess?
> If yes → points drop. If no → points hold.
> This overrides all other considerations.

### Dimensions and Weights

| Dimension | Max Points | Tiers |
|-----------|-----------|-------|
| Core Ingredient Clarity | 25 | 25, 15, 5, 0 |
| Sauce & Seasoning Disclosure | 25 | 25, 15, 5, 0 |
| Allergen Transparency | 25 | 25, 15, 5, 0 |
| Prep Input Clarity | 25 | 25, 15, 5, 0 |
| **Total** | **100** | |

Partial points within a tier are not awarded. Use the Internal Check to resolve tier ambiguity.

### Allergen Default Rule
Allergen Transparency **defaults to 5** for all unconfirmed dishes. It can only rise above 5 through direct restaurant confirmation. This is the most conservative default because allergen uncertainty carries the highest personal risk.

### Score Tiers

| Score | Label | Meaning |
|-------|-------|---------|
| 85–100 | High Transparency | Full or near-full disclosure |
| 60–84 | Moderate Transparency | Strong disclosure with some gaps |
| 0–59 | Building Transparency | Incomplete disclosure |

Birmingham average: 44. Any dish above 44 scores above the current city baseline.

### Tier Anchors by Dimension

**Core Ingredient Clarity**
- 25 — All primary components named, no bundled groups, plain-language names
- 15 — Core components named, one ambiguous or bundled ingredient
- 5 — Multiple vague components, heavy reliance on inference
- 0 — Ingredients not disclosed, marketing language dominates

**Sauce & Seasoning Disclosure**
- 25 — Sauces named and described, OR optional/removable
- 15 — Sauce name provided, no ingredient list
- 5 — House sauce, signature glaze, proprietary blend
- 0 — Sauces integrated into prep, no disclosure, cannot be removed

**Allergen Transparency**
- 25 — Published allergen list, dish-level indicators, cross-contamination notes. Confirmed with restaurant.
- 15 — Some allergens disclosed, staff guidance available, inference still required
- 5 — No official documentation, risk inferred from listed ingredients (DEFAULT for all unconfirmed)
- 0 — No allergen information, staff guidance unclear

**Prep Input Clarity**
- 25 — Cooking method stated, oils disclosed, shared surfaces noted
- 15 — Cooking method stated, oil type unknown, shared surface unclear
- 5 — Method implied but not stated (name or cuisine norms)
- 0 — No prep details, high uncertainty

### Vague Language That Triggers Deductions

| Dimension | Examples |
|-----------|---------|
| Core | house sides, seasonal vegetables, chef selection, signature protein |
| Sauce | house sauce, signature glaze, chef seasoning, secret sauce, proprietary blend |
| Prep | cooked to order, prepared fresh, made in-house (without detail), finished with our blend |
| Allergen | may contain, prepared in a facility with, ask your server (without documented guidance) |

### Confirmation States

| State | Description |
|-------|-------------|
| Inferred | Scored from public menu only. Allergen defaults to 5. Starting state for every dish. |
| Claimed | Restaurant confirmed ingredients directly. Confirmed dimensions update. Allergen can rise above 5. |
| Verified | Full confirmation across all four dimensions. Goldpan Verified badge. |

---

## Philosophy

| Rule | Definition |
|------|-----------|
| Product_Principle | Clarity over completeness, truth over assumption. |
