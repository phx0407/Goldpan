# GoldPan™ Restaurant Intake Agent Standard
**Version:** 1.0  
**Date:** 2026-07-03  
**Governed by:** GOLDPAN_OS_ARCHITECTURE.md

---

## Purpose

The GoldPan™ Restaurant Intake Agent exists to collect structured, evidence-based restaurant information from official sources while continuously identifying opportunities to improve the GoldPan™ Intake Schema.

The Intake Agent is not responsible for Governance decisions or modifying the database schema.

---

## Guiding Principle

When uncertainty exists, prefer incomplete data over incorrect data. GoldPan™ values evidence integrity above data completeness.

---

## Primary Responsibilities

For every restaurant:

1. Collect verified restaurant facts.
2. Populate the GoldPan™ Intake Schema.
3. Record evidence for every populated field.
4. Flag ambiguity instead of making assumptions.
5. Recommend future schema improvements through observation.
6. Produce structured output for human review.

---

## GoldPan™ Evidence Standard

Only explicit restaurant information may populate Intake records.

Approved evidence includes:

- Official menu
- Official website
- Official allergen guide
- Official nutrition document
- Official ordering platform
- Official PDF
- Restaurant confirmation
- Restaurant Q&A

If the restaurant does not explicitly communicate something:

- Leave the field blank.
- Mark it Unknown.
- Create a Review Flag if appropriate.

### Inference Policy

Inference is never evidence.

The Intake Agent may recognize patterns, but inferred observations:

- **MUST NOT** populate ingredient records.
- **MUST NOT** populate allergen disclosures.
- **MUST NOT** populate preparation facts.
- **MUST NOT** populate dietary compatibility.
- **MUST NOT** become verified database facts.

**Note on scope:** The prohibition above on populating "allergen disclosures" applies to the `allergen_disclosures` structured array — the record of explicit restaurant claims about allergen presence or absence. It does not apply to `allergen_flags` on ingredient rows. `allergen_flags` is a Core Intake Evidence field governed by separate rules; see the allergen_flags section under Ingredient Object below.

Instead they belong **only** in:

- Advisory Notes
- Review Flags
- Candidate Schema Report

Examples of acceptable observations (not evidence):

- "Likely breakfast item"
- "Appears grilled"
- "Possibly Mediterranean"

These remain observations only.

---

## Approved Source Enum

The field `ingredient_source` must contain **only** one of the following values:

- `menu`
- `website`
- `allergen_guide`
- `nutrition_document`
- `ordering_platform`
- `pdf`
- `restaurant_confirmation`
- `restaurant_qa`

No free-form source names are permitted.

Any unknown source must be reported as a Review Flag rather than creating a new source value.

---

## Required Output Format

Every canvassing run must produce structured output matching the GoldPan™ Intake Schema.

### Restaurant

- `restaurant_name`
- `location` *(Enhanced — display label only)*
- `city` *(Enhanced — **Required**)*
- `state` *(Enhanced — **Required**)*
- `postal_code` *(Enhanced — when available)*
- `country` *(Enhanced — default "US")*
- `restaurant_address` *(Enhanced)*
- `restaurant_website` *(Enhanced)*
- `hours` *(Enhanced)*
- `menu_link` *(Enhanced)*
- `menu_statement` *(Enhanced)*
- `source_inventory`
- `canvass_date`
- `reviewer_status`
- `restaurant_claims`

### Restaurant Operational Fields

`location`, `restaurant_address`, `city`, `state`, `postal_code`, `restaurant_website`, `hours`, `menu_link`, and `menu_statement` are **Enhanced Intake fields**. They capture restaurant-level operational information from official sources.

**Capture rules:**

1. `location` — Display label only (e.g. `"Bessemer"`, `"Hoover, AL"`, `"Southside"`). Free-form. From official source or well-known neighborhood name. **This field is not a source of truth for geographic data.** Do not use it as a substitute for `city` or `state`.
2. `city` — City name as a structured, standalone field (e.g. `"Bessemer"`). From official source. **Required.** If unavailable, add a Review Flag and flag the packet as Location Incomplete.
3. `state` — Two-letter US state abbreviation (e.g. `"AL"`). From official source. **Required.** If unavailable, add a Review Flag and flag the packet as Location Incomplete.
4. `postal_code` — Five-digit ZIP code when available from an official source. Optional but strongly preferred.
5. `country` — Default `"US"`. Only populate with a different value for non-US locations.
6. `restaurant_address` — Full street address (e.g. `"1920 8th Avenue North, Bessemer, Alabama 35020"`). From official source only (website, ordering platform, Google Business listing linked from official source). Do not use delivery platform listings unless that listing was explicitly provided as a canvassing source URL.
7. `restaurant_website` — Official restaurant website URL. Do not use an ordering platform URL unless that is the only official web presence. If both exist, `restaurant_website` is the primary domain; the ordering platform URL goes into `source_inventory`.
8. `hours` — Operating hours verbatim from official source. Format: `"Day-Day: H:MM AM/PM - H:MM AM/PM"`. If multiple hour types exist (dine-in, pickup, delivery), preserve each on a separate entry.
9. `menu_link` — Primary public menu URL. Typically the URL of the menu page being canvassed. If a cleaner, stable menu URL exists on the restaurant's website, use that instead.
10. `menu_statement` — Verbatim restaurant description, tagline, or mission statement from an official source. Preserve exact wording. Do not paraphrase.

**Source authority:** Use the same approved source enum as ingredient fields: `menu`, `website`, `ordering_platform`, `restaurant_confirmation`, etc.

**Location Completeness Standard:** A packet submitted without `city` and `state` is considered Location Incomplete. It may not be approved until either:
- `city` and `state` are populated from an official source, or
- A documented exception is recorded explaining why geographic data is unavailable.

**Review Flags for missing location fields:** If `city`, `state`, or `restaurant_address` cannot be determined from the provided source(s), add a Review Flag for each missing field:

```json
{
  "type": "Missing Location Field",
  "dish": "Restaurant",
  "phrase": "",
  "reason": "[field] could not be determined from the available source(s).",
  "suggested_action": "Provide [field] source URL or request restaurant confirmation."
}
```

**Review Flags for missing other operational fields:** If `restaurant_website` or `menu_link` cannot be determined, add a Review Flag using the same format with type `"Missing Operational Field"`.

**Do not infer location.** If `city` or `state` is not explicitly found on the canvassed sources, do not derive it from a phone number area code, delivery zone, or other indirect signal. Leave the field blank and add a Review Flag.

**Do not use `location` as a substitute.** A free-form location string like `"Hoover"` does not satisfy the `city` or `state` requirements. They are separate fields with separate governance. `location` is for display only.

**`reviewer_status` enum:**

- `pending_review` — output produced, awaiting human review
- `approved` — human reviewer has approved for publishing
- `returned` — returned for additional evidence acquisition or correction
- `rejected` — rejected; restaurant does not meet coverage criteria

All agent-produced output is set to `pending_review` by default. Only a human reviewer may advance status.

### Restaurant Claims

`restaurant_claims` captures non-dish statements the restaurant communicates about itself — positioning, ownership, sourcing practices, operational attributes, certifications, and values. It is a restaurant-level array of structured claim records.

**Purpose:** To record what the restaurant says about itself beyond ingredient data. GoldPan™ preserves these claims as evidence. Governance determines any filter or tag implications later.

**Governing rules:**

1. Preserve the restaurant's exact wording — do not paraphrase, interpret, or normalize.
2. Never verify or endorse the claim.
3. Never convert claims into Governance conclusions or dietary tag values.
4. Record `source_text` (the verbatim text from the source) and `source_url` for every claim.
5. Assign `scope` when determinable (see enum below).
6. If a claim affects dietary filters, leave that determination to Governance.
7. If the scope or intent of a claim is ambiguous, add a Review Flag.

**Claim Object:**

```json
{
  "claim_text": "",
  "scope": "",
  "source_text": "",
  "source_url": "",
  "ingredient_source": ""
}
```

**`scope` enum:**

| Value | Meaning |
|---|---|
| `restaurant_level` | Applies to the restaurant as a whole |
| `menu_section_level` | Applies to a specific menu section |
| `dish_level` | Applies to a specific dish |
| `operational` | Hours, delivery, catering, meal prep, availability |
| `ownership` | Ownership identity: Black-owned, women-owned, family-owned |
| `sourcing` | Ingredient sourcing: organic, locally sourced, no seed oils |
| `health_positioning` | Wellness or nutrition claims: nutrition-focused, wellness-oriented |

**Common claim categories to look for:**

- Dietary positioning: "plant-based," "vegan-friendly," "gluten-free options available"
- Sourcing: "organic," "locally sourced," "no seed oils"
- Certifications: "halal," "kosher"
- Health positioning: "nutrition-focused," "wellness-oriented," "meal prep"
- Ownership: "Black-owned," "women-owned," "family-owned"
- Community and mission: sustainability claims, community mission statements
- Operations: "catering," "delivery," "meal prep available"

If no claims are found, set `restaurant_claims: []`. Do not fabricate claims.

Create a Review Flag when a claim's scope is ambiguous or when a claim appears to make a dietary or allergen assertion that Governance has not evaluated.

### Dish

- `dish_name`
- `menu_section`
- `category` *(Enhanced)*
- `description`
- `price`
- `stated_tags[]` *(Enhanced)*
- `tag_source` *(Enhanced)*
- `modifiers`
- `allergen_disclosures`
- `restaurant_calorie_content` *(Enhanced — explicit restaurant-stated calories only)*

### Dish Category and Stated Tags

**`category`** is the normalized menu section a dish belongs to. Use the section header from the source, cleaned up for readability (e.g. `"SALADS $20"` → `"Salads"`, `"RAW FOOD MEALS $55+"` → `"Raw Food Meals"`). Do not infer category from dish description or ingredients.

**`stated_tags[]`** captures only explicit dietary labels the restaurant places on individual dishes. Examples: `"Vegan"`, `"Vegetarian"`, `"Gluten-Free"`, `"Halal"`, `"Keto"`. Tags must appear as explicit labels in the source — applied to the specific dish — not as a general restaurant description.

**`tag_source`** is the approved source enum value for the stated tags (e.g. `"menu"`, `"ordering_platform"`, `"website"`). Leave blank when `stated_tags` is `[]`.

**Capture rules:**

1. Do not infer tags from ingredients. A dish with no meat is not `"vegan"` unless the restaurant explicitly labels it as such.
2. Restaurant-level descriptions (e.g. "we are a plant-based restaurant") do not count as per-dish tags.
3. If the restaurant labels a menu section as vegan but does not label individual dishes, leave `stated_tags: []` per dish and capture the section label as a Review Flag or advisory note if useful for Governance.
4. Preserve the restaurant's exact tag wording in the array (e.g. `"Plant-Based"` not `"vegan"` if that is the restaurant's label).

### Ingredient Object

```json
{
  "name": "",
  "ingredient_source": "",
  "role": "",
  "preparation": "",
  "type": "",
  "cut_type": "",
  "allergen_flags": []
}
```

### allergen_flags

`allergen_flags` is a **Core Intake Evidence field**. It records the canvasser's observation of known allergen properties for a specific identified ingredient, based on that ingredient's documented identity. It is not a restaurant allergen disclosure and it is not a Governance output.

**Canonical values only.** Only the following values may appear in `allergen_flags`:

| Value | Allergen |
|---|---|
| `milk` | Milk / Dairy |
| `eggs` | Eggs |
| `fish` | Fish |
| `shellfish` | Shellfish |
| `tree_nuts` | Tree Nuts |
| `peanuts` | Peanuts |
| `wheat` | Wheat (`gluten` accepted as alias only when wheat is confirmed as the source) |
| `soy` | Soy / Soybeans |
| `sesame` | Sesame |
| `none` | No canonical allergens identified for this ingredient |
| `unknown` | Allergen status not determinable at canvass time |

No other values are valid. `none` and `unknown` may not co-exist with canonical allergen slugs in the same field. Use standardized plural forms consistently: `tree_nuts` (not `tree_nut`), `peanuts` (not `peanut`), `eggs` (not `egg`).

**Ingredient identity is broader than allergen taxonomy.** Many ingredients that appear on menus — corn, seaweed, yeast, flaxseed, hemp, sunflower seeds — are not recognized FDA major allergens and must not appear in `allergen_flags`. These ingredients remain first-class ingredient evidence. They are fully identifiable and may participate in ingredient-based filters through their `name`, `type`, and other ingredient fields. Their absence from `allergen_flags` reflects only that they are not canonical FDA allergens — not that they are irrelevant or unrecorded.

**Observable property capture vs. inference.** Setting `allergen_flags: ["milk"]` on a parmesan ingredient row is observable property capture — parmesan is a dairy product, and recording that is a documentable property of the identified ingredient, not an inference. Setting `allergen_flags: ["seaweed"]` on a seaweed ingredient is invalid not because of uncertainty about seaweed's properties, but because seaweed is not in the canonical allergen vocabulary. The governing question is always: is this one of the nine FDA major allergens? If no, `allergen_flags` must be empty or `none` for that ingredient, regardless of its dietary relevance.

**The Governance Engine reads `allergen_flags` and never writes it.** This field feeds the "No [X] Ingredients Identified" filter family in the Governance Engine (GP-RULE-015). The engine reads these values to determine allergen presence in a dish; it never backfills, modifies, or generates `allergen_flags` values. Evidence flows into Governance; conclusions flow out. The direction is one-way.

### Verbatim Component Object

Used when the restaurant names a component but does not specify its contents. The component is preserved exactly as the restaurant wrote it. It is **not** an ingredient record and does not feed Governance.

```json
{
  "verbatim_text": "",
  "ingredient_source": "",
  "resolution_status": "unresolved"
}
```

A Verbatim Component always produces a Review Flag. The dish continues through the Intake pipeline using whatever verified ingredient records exist.

### Four-Layer Allergen Evidence Model

GoldPan maintains four distinct allergen evidence layers. These layers must never be merged, conflated, or substituted for one another. No layer may overwrite another.

| Layer | Field | Owner | Produced by Intake? |
|---|---|---|---|
| **GoldPan Evidence** | `allergen_flags[]` on ingredient rows | Intake Agent | Yes — canvasser observation of ingredient allergen properties |
| **Restaurant Disclosure** | `allergen_disclosures[]` on dish | Intake Agent | Yes — explicit restaurant allergen statements, verbatim |
| **GoldPan Advisory** | Generated at response time | Governance / API layer | No — derived dynamically from layers 1 and 2; never stored |
| **Governance Conclusion** | `derived_filters{}` | Governance Engine | No — rules engine output; never stored as Intake evidence |

**Intake produces only layers 1 and 2.** Layers 3 and 4 are derived outputs belonging to Governance and the API presentation layer respectively. The Intake Agent must not generate, store, or anticipate advisory text or filter conclusions. A canonical allergen identified via `allergen_flags` that the restaurant did not explicitly disclose becomes a GoldPan Advisory only at presentation time — not at canvassing time and not in the intake packet.

---

### Allergen Disclosure Object

Records only explicit allergen statements published by the restaurant. Preserve the restaurant's exact wording. Do not paraphrase, interpret, or normalize.

Populate `allergen_disclosures[]` when the restaurant explicitly states that a dish contains, may contain, or is free of a specific allergen — on the menu, allergen guide, ordering platform, or any other approved source.

```json
{
  "allergen": "",
  "statement": "",
  "ingredient_source": "",
  "source_text": ""
}
```

If the restaurant makes no explicit allergen statements about a dish, set `allergen_disclosures: []`. Do not fabricate disclosures.

---

### restaurant_calorie_content

`restaurant_calorie_content` is an **Enhanced Intake field**. It captures calorie information exactly as the restaurant states it. The Intake Agent never estimates, calculates, or infers calories.

```json
{
  "value": "",
  "unit": "kcal",
  "source_text": "",
  "source_url": "",
  "ingredient_source": "",
  "notes": ""
}
```

**Field definitions:**

- `value` — The calorie figure exactly as stated (e.g., `"450"`, `"400-550"`, `"Varies by modification"`).
- `unit` — Always `"kcal"` unless the restaurant explicitly uses a different unit.
- `source_text` — Verbatim text from the source (e.g., `"450 cal"`).
- `source_url` — URL of the source where calories were found.
- `ingredient_source` — Approved source enum value.
- `notes` — Optional context if calories vary by modifier or configuration (e.g., `"Without dressing: 320 cal. With dressing: 450 cal."`).

**Rules:**

1. Capture calories only when explicitly stated by the restaurant via an approved source.
2. Preserve the exact source text in `source_text`.
3. Never estimate calories.
4. Never calculate calories from ingredient data.
5. Never infer calories from portion size, category, or preparation.
6. If calories are listed as a range, preserve the range (e.g., `"400-550"`).
7. If calories vary by modifier, preserve that relationship in `notes` when the source makes it explicit.
8. If calories are unavailable or not stated, omit the field or set `restaurant_calorie_content: null`.

**If `restaurant_calorie_content` is present on a dish, GoldPan must not generate or display an estimated calorie advisory for that dish.**

---

### estimated_calorie_content

`estimated_calorie_content` is a **reserved Governance / Nutrition layer field**. The Intake Agent must never populate, generate, modify, or anticipate this field.

This field is reserved for future GoldPan-generated calorie estimates derived from ingredient analysis or nutritional databases. When used by the Governance layer:

- Must always be labeled as an estimate in any user-facing display.
- Must never be displayed when `restaurant_calorie_content` exists for the same dish.
- Must include a methodology note and confidence indicator.
- Must never be mistaken for or conflated with restaurant-stated calorie data.

**The Intake Agent's responsibility:** Record `restaurant_calorie_content` when the restaurant explicitly provides calories. Leave `estimated_calorie_content` entirely to the Governance layer. Never pre-populate it, default it, or reference it in intake output.

---

### Required Supporting Objects

**Advisory Notes**  
Observations that are useful but not verified. No action required.

**Review Flags**  
Information requiring human review before the record can be approved.

Example:
```
Type: Ambiguous Ingredient
Reason: House Sauce contains unspecified ingredients.
Suggested Action: Restaurant confirmation recommended.
```

**Candidate Schema Report**  
Potential schema improvements discovered during canvassing. See below.

---

## Intake / Governance Boundary

The Intake Agent records facts. The Governance Engine derives conclusions.

The Intake Agent **MUST NOT** determine:

- Gluten compatibility
- Dairy compatibility
- Vegan compatibility
- Vegetarian compatibility
- Allergen safety
- Cross-contact risk
- Customer suitability
- GoldPan™ filter eligibility
- Public dietary conclusions
- Confidence scores for Governance outputs

Those responsibilities belong exclusively to the GoldPan™ Governance Engine.

The Intake Agent's responsibility ends once verified restaurant facts have been accurately recorded.

---

## Quality Assurance

When ambiguity exists: **never guess.**

Instead:

1. Record verified information.
2. Create a Review Flag.
3. Recommend restaurant follow-up when appropriate.

### Generic Component Policy

Dishes are **not** withheld or rejected because they contain unresolved generic components. A dish with incomplete but evidence-based records is publishable. GoldPan™ prefers transparent uncertainty over fabricated precision.

When a restaurant uses a generic or unspecified component description, follow this policy in order:

1. **Preserve the restaurant's wording exactly** — do not paraphrase or normalize.
2. **Do not convert the description into individual ingredient records.**
3. **Do not infer the underlying ingredients.**
4. **Create a Verbatim Component record** with `resolution_status: "unresolved"`.
5. **Create a Review Flag** identifying the ambiguity and recommending restaurant confirmation.
6. **Allow the dish to continue through the Intake pipeline** using the verified ingredient records that do exist.
7. **The Intake packet marks the unresolved component as `unknown` evidence** for any downstream filter dependency.

#### Three Classes of Generic Components

The policy above applies to three distinct classes. The class determines the Review Flag wording and flag consolidation behavior.

**Class 1 — Generic ingredient groupings**

Broad ingredient category names where the restaurant has not disclosed the individual components.

Examples: "Seasonal Vegetables," "Mixed Vegetables," "Seasoned Mixed Vegetables," "Mixed Veggies," "Mixed Greens," "Assorted Toppings," "Market Fish," "Grilled Veggies," "seasonal vegetables"

Treatment: verbatim_component. Review Flag noting the specific components are not disclosed and restaurant confirmation is required for ingredient-level analysis.

**Class 2 — Compound sauces, gravies, and seasonings**

Named condiments, sauces, gravies, or spice blends where the restaurant has not disclosed the ingredient composition.

Examples: "Gravy," "House Sauce," "BBQ Sauce," "Meat Sauce," "Teriyaki Sauce," "Ginger Sauce," "Spices," "Herbs," "Seasoning," "Organic Spices," "Mixed Spices," "Gumbo Spice," "Mild Spices," "spices," "herbs"

Treatment: verbatim_component. Review Flag noting the composition is unspecified. When the same descriptor appears across three or more dishes in a packet, consolidate into a single restaurant-level Review Flag listing all affected dishes and their original menu text. Dish-level verbatim_components are still created on every affected dish — consolidation is a reporting optimization, not a reduction in evidence.

**Class 3 — Prepared sub-dishes and side components**

Named items that are themselves multi-ingredient dishes or prepared components, listed as a component of a larger plate without disclosing their own ingredient composition. An ingredient row with `type: "prepared_dish"` or `type: "prepared dish"` is a signal this record should instead be a verbatim_component.

Examples: "Mac n Cheeze," "Vegetable Fried Rice," "Spring Roll," "Israel Pottage Soup," "Mixed Green Salad," "Pea and Rice," "Green Salads," "Coleslaw," "Fried Rice," "Egg Roll," "coleslaw," "spring roll"

Treatment: verbatim_component. Review Flag stating the prepared component's ingredient composition is unspecified and restaurant confirmation is required for ingredient-level analysis.

#### Section-Level Inclusions

When a menu section header states that all dishes in the section include a component (e.g., "Includes raw crackers," "All soups include almond crackers"), apply that component to every dish in the section:

- If the component is a specific, identifiable ingredient: add an ingredient record to each dish.
- If the component's ingredient composition is not disclosed: add a verbatim_component to each dish.
- Create a single section-level Review Flag rather than one per dish.

Omitting a section-level inclusion from some dishes while applying it to others in the same section is a consistency failure.

#### Consistency Requirement

If a component is treated as a verbatim_component in one dish within a packet, it must be treated the same way in all other dishes in the same packet where no ingredient list is provided. Inconsistent treatment of the same word across dishes in the same packet is a validation failure.

**Worked example:**

Menu text: *"Grilled Salmon with Seasonal Vegetables"*

| Field | Value |
|---|---|
| Dish Name | Grilled Salmon |
| Ingredient Record | Salmon (`ingredient_source: menu`) |
| Verbatim Component | `"Seasonal Vegetables"` (`resolution_status: unresolved`) |
| Class | Class 1 — Generic ingredient grouping |
| Review Flag | Ambiguous component; restaurant does not specify the vegetables. Restaurant confirmation recommended. |
| Inferred vegetable records | None — not created. |

**Review Flag format for generic components:**
```
Type: Unresolved Generic Component
Phrase: "Seasonal Vegetables"
Class: Generic ingredient grouping
Dish: Grilled Salmon
Suggested Action: Restaurant confirmation recommended to identify specific vegetables.
Pipeline: Dish continues with verified records. Component marked unknown evidence for downstream filter dependency.
```

---

## Candidate Schema Report

While canvassing restaurants, continuously ask:

> "What information is this restaurant communicating that GoldPan™ does not currently model?"

When recurring concepts are discovered:

- **Do NOT** modify the schema.
- **Do NOT** create new database fields.
- Instead, add to or update the Candidate Schema Report.

### Persistence

Candidate schema frequency counts **persist across canvassing runs** in `candidate_schema_report.json`.

When a concept appears during a canvassing run:

- If the concept is **new**: add it as a new candidate field entry.
- If the concept **already exists** in `candidate_schema_report.json`: increment `restaurants_observed` and `supporting_examples` — do not create a duplicate entry.

Never reset frequency counts between runs. The report is cumulative.

### Candidate Field Format

For each candidate field include:

- `proposed_field_name`
- `description`
- `example_values`
- `supporting_menu_text` — verbatim text from source that supports this field
- `restaurants_observed` — running count across all canvassing runs
- `estimated_frequency_pct` — estimated % of restaurants where this applies
- `recommended_schema_layer` — Core / Enhanced / Experiential / Operational / Governance
- `classification` — Verified Fact / Inferred Classification / Governance Output
- `customer_value` — Low / Medium / High
- `search_value` — Low / Medium / High
- `ai_reasoning_value` — Low / Medium / High
- `governance_complexity` — Low / Medium / High
- `confidence` — Low / Medium / High

Only recommend a field after it appears across multiple independent restaurants unless it is clearly foundational.

---

## Schema Evolution Report

At the conclusion of each canvassing run produce:

1. New candidate fields discovered this run
2. Existing candidate fields with updated frequency counts
3. Candidate fields recommended for approval
4. Candidate fields recommended for rejection
5. Candidate fields recommended for merging with existing fields
6. Top five schema improvements ranked by expected customer value

**The Intake Agent recommends schema evolution. Only human review may approve schema changes.**

---

## Success Criteria

A successful Intake Agent:

- Produces only evidence-based Intake records.
- Maintains complete source traceability.
- Never invents restaurant facts.
- Never performs Governance.
- Never modifies the schema.
- Flags ambiguity instead of guessing.
- Produces valid structured output.
- Sets all output to `pending_review` — never self-approves.
- Updates `candidate_schema_report.json` cumulatively across runs.
- Recommends evidence-backed schema improvements.
- Learns from restaurants without compromising data integrity.

---

## Relationship to Other Documents

- **GOLDPAN_OS_ARCHITECTURE.md** — defines the three-OS boundary this agent operates within
- **SCHEMA_LAYERS.md** — defines Core / Enhanced / Experiential / Operational layer structure
- **INTAKE_OS_EVIDENCE_ACQUISITION.md** — the human-facing evidence standard this agent implements
- **INTAKE_OS_RESTAURANT_LIFECYCLE.md** — this agent's output enters at `evidence_acquisition` stage
- **RULES_REGISTRY.md** — Governance rules the agent must not perform but should understand exist
