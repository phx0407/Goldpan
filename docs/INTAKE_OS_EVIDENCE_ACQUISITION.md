# GoldPan Intake OS — Evidence Acquisition
**Version:** 3.0  
**Date:** 2026-07-03  
**Supersedes:** v2.0 (same date) — removed all Governance responsibilities; Intake now captures facts only; dietary reasoning belongs to the Governance OS  
**Lifecycle Stage:** `evidence_acquisition` — begins when onboarding is complete and the source map is in place; ends when all dishes from identified sources are entered and `validate_database.py` passes with no ERRORS  
**Governed by:** GOLDPAN_COVERAGE_PHILOSOPHY.md, EVIDENCE_ARCHITECTURE.md, INTAKE_OS_RESTAURANT_LIFECYCLE.md

---

## The Governing Standards

**Standard 1: If it is not in the source, it is not in GoldPan.**

Every fact that enters GoldPan's evidence system must be traceable to a specific source. A canvasser who adds an ingredient because it is typically present in a dish type has not captured evidence — they have contaminated the evidence with an assumption. Downstream, Governance cannot distinguish that assumption from a sourced fact, and will reason over it as if it were real. This is how bad conclusions are produced.

**Standard 2: Intake captures facts. Governance determines what they mean.**

The Evidence Acquisition stage does not produce dietary conclusions, filter assignments, or confidence levels. Those are Governance responsibilities. Intake's responsibility is to produce the richest, most faithful, best-sourced body of evidence possible. What that evidence *means* for a user's dietary needs is determined later, by the Governance OS.

A canvasser who has faithfully captured every stated ingredient, every allergen disclosure, every preparation method the restaurant described — and made no assumptions about what those facts imply — has done their job correctly. Even if many of a restaurant's filter results are `unknown` because the evidence is thin, that is an accurate outcome. Governance will say `unknown`. That is honest and correct.

Intake's ambition is richness, accuracy, and provenance. Not conclusions.

---

## What Evidence Acquisition Is — and Is Not

**Is:** Reading documented sources and transcribing what those sources explicitly state into GoldPan's evidence system.

**Is not:**
- Applying culinary knowledge to fill in what the source didn't say
- Inferring ingredients from dish type or cuisine category
- Asserting dietary conclusions that go beyond the stated evidence
- Running the pipeline or computing derived filters (that happens in qa_review)

The canvasser's role in this stage is precision transcription. A canvasser who adds "egg" to a Caesar salad because Caesar dressing typically contains egg has not captured evidence — they have introduced an assumption into a system that cannot distinguish it from fact. That assumption may propagate into a dietary conclusion that is wrong, and a user may be harmed by it.

---

## The Role of AI in Evidence Acquisition

AI may assist with three things during evidence acquisition:

1. **Extraction** — reading a source and identifying which text corresponds to dish names, descriptions, and stated ingredients
2. **Organization** — structuring extracted content into GoldPan's schema (dish names, ingredient rows, source references)
3. **Flagging uncertainty** — identifying places where the source text is ambiguous, where an ingredient name may have multiple interpretations, or where the canvasser should verify before entering

AI may not:
- Generate ingredient rows from culinary knowledge ("this dish conventionally contains X")
- Apply food science to infer allergen presence from an ingredient name ("soy sauce likely contains wheat")
- Assert any dietary conclusion that is not explicitly supported by the source text

When AI assists with extraction, a human canvasser reviews every extracted row before it enters the evidence system. The canvasser is the accountable actor. AI output is a draft, not a record.

---

## Workflow Overview

1. **Confirm source access** — Verify every source documented in onboarding is still accessible
2. **Read the full source** — Read the entire primary source before entering any data
3. **Enter dishes** — Create GDL records for every dish on the menu, working through the source in order
4. **Enter stated ingredient rows** — For each dish, enter only what the source explicitly states
5. **Record all disclosures** — Enter allergen disclosures, preparation statements, substitution options, and any other dietary-relevant information the restaurant published — verbatim, with source reference
6. **Record stated allergen relationships** — Where the source identifies allergen presence on specific ingredients or dishes, record that statement in the evidence system
7. **Run validation** — Execute `validate_database.py` and resolve all ERRORS before exiting

**Note on dietary tags and filter conclusions:** These are not produced during Evidence Acquisition. Dietary tag assignment, filter derivation, and confidence scoring are Governance OS responsibilities. They occur after Intake is complete, when the derivation engine processes the evidence Intake has collected. See GOLDPAN_OS_ARCHITECTURE.md.

---

## Step 1 — Confirm Source Access

Before entering any data, verify that each source documented in the Menu Source Registry is still accessible at the recorded URL. If a source is no longer accessible, update its `Status` to `inactive` and determine whether an alternative exists. If the primary source is inaccessible with no alternative, do not begin evidence entry — return to `onboarding` status and flag for coordinator review.

---

## Step 2 — Read the Full Source Before Entry Begins

Read the entire primary source before creating any GDL record. Menu-level context that applies to all dishes often appears at the top or bottom of a menu — not beside the dishes it affects.

Common examples:
- "All our dishes are prepared in a kitchen that handles tree nuts and peanuts"
- "Items marked (GF) are prepared in a shared kitchen — not suitable for celiac disease"
- "We cook exclusively with avocado oil"
- "All our meats are Halal-certified"

Record any menu-level disclosures in the Restaurant_Registry Notes field before beginning dish entry. These are restaurant-level evidence and apply to the entire menu. They become the basis for kitchen-wide Allergen_Disclosures records and inform allergen flag decisions across all dishes.

---

## Step 3 — Dish Entry Standards

Create one GDL record for each dish on the primary source. Work through the source in order from top to bottom. Do not skip dishes and do not cherry-pick high-signal items.

### What Counts as a Dish

| Scenario | Guidance |
|----------|----------|
| Size variants ("Small / Large Caesar Salad") | One dish record; note variants in description |
| Same dish, meaningfully different proteins ("Burger — Beef / Turkey / Veggie") | Separate records; dietary profiles differ |
| Customizable bowls | One record for the base; note customization options in description |
| Modifiers that affect dietary profile ("Add grilled chicken") | Note in description; separate dish only if the restaurant presents it as standalone |
| Beverages, sides, sauces | Enter if itemized; a named sauce with stated ingredients is worth capturing |

### Dish Name
Transcribe the name exactly as it appears on the source. Do not correct spelling errors, expand abbreviations, or normalize formatting. If the source has a typo, enter it with the typo and note the discrepancy.

### Dish Description
Transcribe verbatim. If no description exists, enter `[no description provided]`. Do not paraphrase, summarize, or expand beyond what the source says.

### Source Reference
Every dish record must reference its source (`Source_ID` from the Menu Source Registry). No source reference, no record.

### Dish_ID
Generated by the ID assignment system. Never typed manually.

---

## Step 4 — Ingredient Row Standards

For each dish, create ingredient rows for what the source explicitly states. Nothing else.

### The Standard: Stated Only

An ingredient enters GoldPan when the source names it — in the dish description, the ingredient list, the allergen guide, or any other documented source element.

An ingredient does not enter GoldPan because:
- It is conventionally part of the dish
- The cuisine type typically uses it
- The canvasser knows from cooking experience that it is likely present
- A similar dish at another restaurant contained it

These are all culinary assumptions. None of them is evidence.

### What "Stated" Means

The source named it. The standard for "named" is the source text itself — not what the canvasser believes the source is implying.

| Source says | Enter | Do not enter |
|-------------|-------|--------------|
| "grilled chicken with lemon butter, mashed potatoes, broccoli" | chicken, lemon, butter, potato, broccoli | garlic (not stated), milk in potatoes (not stated), herbs (not stated) |
| "Caesar salad" | nothing — no ingredients stated | romaine, Parmesan, egg, croutons, anchovy (all culinary assumptions) |
| "Caesar salad with romaine, Parmesan, house-made dressing" | romaine, Parmesan, dressing (unspecified) | egg, anchovy, lemon (not stated — even though common in Caesar dressing) |
| "pasta carbonara" | pasta (type unspecified), carbonara (preparation style) | egg, Parmesan, guanciale, black pepper (culinary knowledge — not evidence) |
| "pasta carbonara (contains egg, Parmesan, pancetta)" | pasta, egg, Parmesan, pancetta | black pepper (not stated) |

### Ingredient Specificity

Enter the specificity the source provides — no more, no less.

| Source says | Enter |
|-------------|-------|
| "oil" | oil |
| "olive oil" | olive oil |
| "extra-virgin olive oil" | extra-virgin olive oil |
| "pasta" | pasta |
| "wheat pasta" | wheat pasta |
| "gluten-free pasta" | gluten-free pasta |

Do not collapse ("extra-virgin olive oil" → "fat") or expand ("pasta" → "wheat pasta"). The source says what it says.

### When the Source is Ambiguous

If the source text is genuinely ambiguous about an ingredient, the canvasser makes the most conservative interpretation and records the ambiguity in the ingredient row Notes field. Conservative means: the interpretation that makes fewer claims about the ingredient, not the interpretation that adds more information.

*Example:* "house sauce" — enter "house sauce (unspecified)" and note the ambiguity. Do not speculate about the sauce's composition.

### Ingredient_ID
Generated by the ID assignment system. Never typed manually.

---

## Step 5 — Allergen Disclosure Standards

If the restaurant publishes any form of allergen information, create Allergen_Disclosures records. This is a separate system from ingredient rows — disclosures are what the restaurant explicitly said about allergens, recorded verbatim or with explicit attribution.

### What Qualifies

- A formal allergen guide (PDF or web page listing allergens by dish)
- Dish-level allergen notation on the menu ("contains: milk, wheat, soy")
- A kitchen-wide allergen statement ("our kitchen handles all major allergens")
- A cross-contamination disclaimer ("prepared in a facility that also processes tree nuts")
- A certification statement with allergen implications ("Kosher-certified under Rabbi X's supervision")

### Entry Requirements

Each Allergen_Disclosures record must contain:
- `Restaurant_ID` and (if dish-specific) `Dish_ID`
- The disclosure text verbatim or paraphrased with explicit attribution
- `Source_ID` referencing where the disclosure was found
- URL and date retrieved
- Disclosure type: kitchen-wide / dish-level / certification / other

### What Does Not Qualify

Community-reported allergen information, review site user comments, and information not sourced to the restaurant or a documented authorized third-party platform does not qualify. Note it in Restaurant_Registry Notes if worth preserving, but do not enter it as a disclosure record.

---

## Step 6 — Recording Stated Allergen Relationships

Where the source states that a specific dish or ingredient involves a specific allergen, that statement is recorded in the evidence system. This is an Intake act: recording what the restaurant said, not determining what it means for a user's safety.

### What Intake Records

**Ingredient-level allergen statements:** If the source names an ingredient that the restaurant has associated with an allergen — in an allergen guide, a dish-level disclosure, or an explicit ingredient statement — record that association in the evidence system with a source reference.

*Example:* Restaurant's allergen guide states "Carbonara contains egg and dairy." Intake records: egg → stated allergen presence for this dish; dairy → stated allergen presence for this dish. Source: allergen guide URL, date retrieved.

**Kitchen-level allergen statements:** If the restaurant has disclosed kitchen-wide allergen handling ("prepared in a facility that handles tree nuts"), record this in the Allergen_Disclosures system as a kitchen-level disclosure.

**Cross-contamination disclosures:** Record verbatim in Allergen_Disclosures with source reference. Cross-contamination is a kitchen-level statement, not an ingredient-level fact.

### What Intake Does Not Determine

Intake does not determine:
- Whether a stated allergen relationship makes a dish unsafe for a user
- Whether the absence of an allergen disclosure means the allergen is absent
- What filter conclusions should result from a stated allergen relationship

Those are Governance determinations. Intake's job is to record what the restaurant stated, faithfully and with full provenance.

### Source Reference Requirement

Every allergen relationship entered in the evidence system must reference its source. An allergen statement without a source reference does not enter GoldPan. If the allergen information came from an allergen guide, the guide URL and retrieval date are required. If it came from a dish-level menu notation, the source notation is recorded verbatim.

### Stated Silence Is Not Absence

If a source does not mention an allergen, Intake records nothing — not the presence, not the absence. Silence in the source is silence in the evidence system. The Governance OS determines what `unknown` means for filter results; Intake does not need to decide.

---

## Step 7 — Dietary Disclosures (Stated Classifications Only)

Where the restaurant has explicitly classified a dish with a dietary label — in a menu section, on a dish tag, or in formal disclosure language — Intake records that classification verbatim as a disclosure fact.

This is a narrow Intake responsibility: recording what the restaurant said about its own food. The canvasser is not evaluating whether the claim is accurate, whether it meets GoldPan's definition of the filter category, or whether it should appear in user-facing filter results. Those are Governance determinations.

**What Intake records here:**
- The restaurant labeled this dish "(V)" on the menu → record: "restaurant stated: vegetarian"
- The restaurant lists this dish on a page titled "Gluten-Free Menu" → record: "restaurant stated: gluten-free"
- The restaurant states "all our meats are Halal-certified" → record: "restaurant stated: Halal-certified (kitchen-wide)"

**What Intake does not determine:**
- Whether "restaurant stated: gluten-free" means the dish meets GoldPan's gluten-free filter standard
- Whether the restaurant's self-identification as Halal is sufficient for the Halal filter without certification documentation
- Whether a "(V)" label means vegan or vegetarian by GoldPan's definitions
- What confidence level attaches to these claims

Those determinations belong to the Governance OS. Intake's job is to record the statement faithfully with its source. Governance evaluates the statement against its rules.

---

## The Intake Boundary

Intake's job is collection, not interpretation. The following are concrete examples of where the boundary falls — what Intake records, and what it leaves for Governance.

**Ingredients:** Intake records what the source names. "Carbonara" does not evidence egg and Parmesan — those are standard recipe assumptions, not source statements. If the source doesn't name an ingredient, there is no ingredient row. Governance will produce `unknown` for filter conclusions that depend on evidence Intake did not receive. That is the correct outcome.

**Allergens:** Intake records what the restaurant stated. If the source says "contains egg," Intake records "restaurant stated: contains egg." If the source says nothing about allergens, Intake says nothing — no entry, no flag, no assertion. Silence is not evidence of absence. What that silence means for a user's safety is a Governance determination.

**Preparation method:** Intake records at the specificity the source provides. "Grilled in olive oil" → recorded. "Grilled" (no oil specified) → "grilled" is recorded; oil type is not. Nothing is added to close the gap.

**Dietary classifications:** Intake records what the restaurant labeled. Whether a "(V)" label satisfies GoldPan's vegetarian filter standard, or whether a "gluten-free" claim is sufficient for the gluten-conscious filter without kitchen verification, are Governance questions.

**Cross-contamination:** Intake records the restaurant's disclosure verbatim. Whether that disclosure warrants suppressing a dish from a filter result is a Governance question.

**Certification:** Intake records certifications when they appear in a source. It does not infer certification from practice. A restaurant that operates in a Halal or Kosher manner is not certified unless the source documents it.

**In every case:** Intake records what the source says. What that means for a user's dietary needs is Governance's answer to give.

---

## Advisory Notes (Non-Evidence Observations)

Canvassers may observe things during evidence acquisition that are worth preserving but do not meet the evidence standard. These observations belong in the dish or restaurant Notes field — not in ingredient rows, allergen flags, or dietary tags.

Advisory notes serve one purpose: **informing the confirmation strategy**. They help the canvasser or a subsequent reviewer know which questions to ask when contacting the restaurant.

Examples of appropriate advisory notes:
- "Dish name suggests egg-based preparation — confirm whether egg is used"
- "No allergen guide found; restaurant has several dishes that may contain tree nuts — priority for confirmation call"
- "Menu describes scratch cooking approach — likely strong candidate for ingredient-level disclosure upon outreach"

Examples of what does not belong in advisory notes:
- Conclusions ("this dish is probably vegan")
- Allergen assessments ("likely contains dairy")
- Anything that could be misread as evidence

Advisory notes are visible only to canvassers and reviewers. They never appear in user-facing output and they never feed the derivation pipeline.

---

## Completeness Standard

Every dish from the primary source must be entered. Evidence acquisition is not selective. A canvasser does not choose the high-signal dishes and omit the rest.

**Secondary sources:** If a secondary source contains dishes not on the primary source, those dishes may be entered with the secondary source referenced. Note the source in the dish record.

**Incomplete menus:** If the canvasser believes the source is incomplete (only shows lunch when the restaurant serves dinner), record the incompleteness in Restaurant_Registry Notes and flag it. Do not speculate about what else might be on the menu.

---

## Exit Gate

Evidence acquisition is complete when all of the following are true:

- [ ] Every dish from the primary source is entered with a source reference
- [ ] Ingredient rows exist for every dish containing only stated ingredients
- [ ] Allergen_Disclosures records exist for every allergen disclosure found in any source
- [ ] All allergen flags are sourced — no flag exists without a source reference in the same row
- [ ] Every dietary tag has a recorded Tag_Source
- [ ] No tag carries a dietary conclusion that exceeds what the evidence supports
- [ ] `validate_database.py` passes with no ERRORS
- [ ] Lifecycle_Events row written for `evidence_acquisition → verification` transition

---

## Special Situations

**Dish with no description:** Enter the dish name. Leave description as `[no description provided]`. Create no ingredient rows — the dish name alone is not sufficient evidence of any ingredient.

**Source contradicts itself:** (e.g., allergen guide says dish is gluten-free; ingredient section lists an item that contains gluten.) Document both as found. Note the conflict explicitly. Do not resolve the contradiction by choosing one side. Flag for verification — the conflict must be resolved before the restaurant exits `verification`.

**Restaurant has allergen guide but it conflicts with the menu:** Record both disclosures as-is. Flag the conflict in Allergen_Disclosures Notes. This is a verification-stage issue, not an evidence acquisition issue. The canvasser's job is to capture what the sources say, accurately and completely.

**Dish available with dietary modification ("can be made vegan"):** Enter the dish as listed. Note the modification in the description. Do not create a tag for the modification unless the restaurant presents the modified version as a distinct, independently labeled menu item.

**AI-assisted extraction:** When AI output is used to draft dish records or ingredient rows, the canvasser must review every row before it is committed. The canvasser confirms: (1) the dish name and description match the source, (2) ingredient rows contain only stated ingredients, and (3) no culinary assumptions have been added. AI output that includes inferred ingredients must be edited — not accepted.

---

## Relationship to Other Documents

**Intake OS:**
- **INTAKE_OS_RESTAURANT_ONBOARDING.md** — produces the source map this stage works from
- **INTAKE_OS_RESTAURANT_LIFECYCLE.md** — this document governs Stage 4 (`evidence_acquisition`)
- **INTAKE_OS_VERIFICATION.md** _(forthcoming)_ — spot-checks the evidence collected here before it moves to QA

**Governance OS:**
- **GOLDPAN_OS_ARCHITECTURE.md** — defines the boundary between Intake and Governance; all reasoning over the evidence collected here belongs to the Governance OS
- **EVIDENCE_ARCHITECTURE.md** — defines the schema this workflow populates; may need review to confirm Intake and Governance fields are correctly separated
- **RULES_REGISTRY.md** — Governance rules that determine what conclusions can be drawn from the evidence Intake collects
- **SCORING_ARCHITECTURE.md** — the confidence framework Governance applies to Intake evidence
