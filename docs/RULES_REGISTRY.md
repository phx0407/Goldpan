# GoldPan Rules Registry

**Status:** Active policy  
**Last updated:** 2026-06-30 (GP-RULE-014/015/016 — Allergen Evidence, Knowledge, and Communication rules)  
**Maintained by:** GoldPan data architecture

---

## Purpose

This registry defines the named, versioned business rules that govern every derived conclusion GoldPan computes. No derived filter may reference vague or implicit logic. Every conclusion must cite a specific Rule ID from this registry.

The registry serves three audiences:

- **Developers** — defines the logic boundaries each derived filter computation must respect
- **Validators** — provides the audit trail for reviewing computed conclusions
- **Future customer-facing interfaces** — the source of "Why?" and "How was this determined?" explanations

Rules are versioned. When a rule changes, the version increments and the last-updated date is recorded. Existing derived conclusions that cite an older rule version remain valid under that version until recomputed.

---

## Rule Categories

The registry is organized into four categories. Rule IDs are assigned sequentially regardless of category — numbers reflect the order rules were added, not their category. Each rule's header identifies its category.

**General Knowledge Rules** govern the computation model that applies to all derived conclusions — evidence requirements, materiality, absence reasoning, inference prohibition, explanation requirements, and dependency types. These rules are the foundation every domain-specific knowledge rule builds on.

**Domain-Specific Knowledge Rules** govern how GoldPan computes conclusions within a particular evidence domain (allergens, dietary certifications, preparation methods, etc.). They depend on the general knowledge rules and add domain-specific constraints — filter families, confidence ceilings, conflict handling, and governing principles unique to that domain.

**Evidence Rules** govern the Evidence System — what may be recorded, how it must be attributed, what sources are trusted, how conflicts in acquisition are resolved, and how provenance is maintained. Evidence rules never govern computation; they govern the facts that computation draws from.

**Communication Rules** govern how GoldPan presents conclusions to customers — label standards, mandatory limitations language, structural separation between evidence and knowledge, and what GoldPan may and may not imply through its presentation.

| Category | Current rules |
|---|---|
| General Knowledge | GP-RULE-001, 002, 003, 004, 005, 006, 007, 008, 009 |
| Evidence | GP-RULE-010, 011, 012, 013, 014 |
| Domain-Specific Knowledge | GP-RULE-015 |
| Communication | GP-RULE-016 |

When adding a new rule, identify its category before assigning an ID. The category shapes the rule's scope, what it may and may not govern, and which existing rules it depends on.

---

## Rule Index

| Rule ID | Category | Rule Name | Version | Last Updated |
|---|---|---|---|---|
| GP-RULE-001 | General Knowledge | Material Evidence Rule | 1.1 | 2026-06-28 |
| GP-RULE-002 | General Knowledge | Disclosed Absence Rule | 1.1 | 2026-06-28 |
| GP-RULE-003 | General Knowledge | Undisclosed Ingredient Rule | 1.1 | 2026-06-28 |
| GP-RULE-004 | General Knowledge | Supporting Documents Rule | 1.0 | 2026-06-28 |
| GP-RULE-005 | General Knowledge | No Unsupported Inference Rule | 1.0 | 2026-06-28 |
| GP-RULE-006 | General Knowledge | Derived Filter Explanation Rule | 1.0 | 2026-06-28 |
| GP-RULE-007 | General Knowledge | Filter Evidence Dependency Rule | 1.0 | 2026-06-28 |
| GP-RULE-008 | General Knowledge | Data Freshness Rule | 1.1 | 2026-06-29 |
| GP-RULE-009 | General Knowledge | Stale Evidence Confidence Degradation Rule | 1.0 | 2026-06-28 |
| GP-RULE-010 | Evidence | Source Authority Hierarchy Rule | 1.0 | 2026-06-28 |
| GP-RULE-011 | Evidence | Evidence Provenance Rule | 1.0 | 2026-06-28 |
| GP-RULE-012 | Evidence | Acquisition Conflict Resolution Rule | 1.0 | 2026-06-28 |
| GP-RULE-013 | Evidence | Dietary Tag Provenance Rule | 1.0 | 2026-06-30 |
| GP-RULE-014 | Evidence | Allergen Evidence Rule | 1.0 | 2026-06-30 |
| GP-RULE-015 | Domain-Specific Knowledge | Allergen Knowledge Rule | 1.0 | 2026-06-30 |
| GP-RULE-016 | Communication | Allergen Communication Rule | 1.0 | 2026-06-30 |

---

## GP-RULE-001 — Material Evidence Rule

**Category:** General Knowledge  
**Version:** 1.1  
**Last updated:** 2026-06-28  
**Changelog:** v1.1 — Replaced binary "sufficient evidence" threshold with the materiality test: could missing evidence change this conclusion?

### Purpose

Governs when GoldPan has enough verified evidence to compute a derived conclusion. All other rules depend on this one being satisfied first.

The governing question is not "Is the ingredient list complete?" The governing question is:

> **Could the missing evidence materially change this conclusion?**

If the answer is **no** — meaning gaps in disclosure would not plausibly flip the conclusion — GoldPan may compute the conclusion from available verified evidence.

If the answer is **yes** — meaning missing ingredients could reasonably change the result — GoldPan must return `Unknown` and document what additional evidence would be required.

This framing allows GoldPan to be useful with real-world data, which is rarely complete, while remaining honest about the limits of what verified evidence supports.

### Evidence Required

Verified ingredient data for the dish from at least one of the following in descending order of authority:

1. Direct restaurant confirmation (staff, official documentation)
2. Official allergen or nutrition PDF published by the restaurant
3. Live restaurant menu (website or in-person)
4. Restaurant's official website

Third-party aggregators (Yelp, DoorDash, Google, etc.) do not satisfy this rule.

### What This Rule Allows GoldPan to Compute

Derived conclusions where the verified evidence reliably supports the conclusion and gaps in disclosure would not plausibly change it. Both positive conclusions ("Contains Dairy") and absence conclusions ("No Beef Identified") may be computed when the materiality test is satisfied.

### What This Rule Does Not Allow GoldPan to Compute

- Conclusions about dishes with no verified ingredient data at all
- Conclusions where a plausible undisclosed ingredient could flip the result
- Conclusions derived from assumed, inferred, or category-level knowledge rather than verified disclosure
- Conclusions that require evidence the filter's declared dependency type (see GP-RULE-007) demands but the available evidence does not supply

### Standard Limitation Language

> This conclusion is based on verified ingredient disclosures obtained from [source] on [date]. It reflects what the available evidence reliably supports. Where gaps in disclosure could plausibly change the result, GoldPan returns Unknown rather than computing a conclusion.

### Example: Applies

A dish's verified ingredient list contains 8 ingredients from the live menu: chicken, romaine, parmesan, croutons, caesar dressing, black pepper, lemon juice, olive oil. GoldPan is computing "No Beef Identified." Even if one or two additional garnish ingredients were undisclosed, none would plausibly be beef. The materiality test passes. GoldPan may compute.

### Example: Does Not Apply

A dish has only a name ("House Special") and a price. No ingredient data exists. The materiality test cannot be applied because no evidence exists. GoldPan returns `Unknown` and flags the dish as requiring ingredient verification.

### Example: Borderline — Must Return Unknown

A dish lists only two ingredients: "house sauce" and "protein." Both are compound or category-level terms. Missing evidence (what protein? what is in the house sauce?) could plausibly include beef, pork, tree nuts, or allergens. The materiality test fails. GoldPan returns `Unknown` for any ingredient-dependent filter on this dish.

---

## GP-RULE-002 — Disclosed Absence Rule

**Category:** General Knowledge  
**Version:** 1.1  
**Last updated:** 2026-06-28  
**Changelog:** v1.1 — Renamed from "Macro Absence Rule." Reframed around reasoning from absence vs. the macro/micro distinction. Clarified that explicitly disclosed micro ingredients are valid evidence.

### Purpose

Governs when GoldPan may conclude that a specific ingredient or allergen is absent from a dish. The key distinction is not macro vs. micro — it is about the **expectation of disclosure**.

Primary ingredients are typically expected to be disclosed on a restaurant menu. Their absence from a verified ingredient list can therefore support an absence conclusion. When a restaurant lists 10 primary ingredients and beef is not among them, the absence of beef from the list is informative.

Micro ingredients (processing aids, trace additives, sub-components of compound ingredients) are often not disclosed even when present. Their absence from a disclosed list is generally not informative — it is expected whether or not they are present.

The rule, precisely stated: **GoldPan may reason from absence only when absence from the disclosed list is informative given the disclosure norms for that type of ingredient.**

This rule produces "No [X] Identified" conclusions — not "[X]-Free" claims. "No Beef Identified" is a statement about what is disclosed. "Beef-Free" is a safety claim that extends beyond disclosed ingredients. GoldPan computes the former, never the latter.

Note: if a restaurant explicitly discloses a micro ingredient (soy lecithin, sesame oil, xanthan gum, etc.), that disclosure is valid verified evidence and should be treated as such. This rule concerns reasoning from *absence* of disclosure, not from *presence*.

### Evidence Required

- GP-RULE-001 (Material Evidence Rule) must be satisfied first; the materiality test must pass
- A verified ingredient list for the dish from an authoritative source
- The target ingredient must not appear anywhere in the verified disclosed list
- The target ingredient must be of a type where disclosure is expected (i.e., absence is informative)

### What This Rule Allows GoldPan to Compute

"No [X] Identified" conclusions for ingredients where disclosure is expected and the materiality test passes — meaning that if [X] were present, it would typically appear in the disclosed list.

### What This Rule Does Not Allow GoldPan to Compute

- "[X]-Free" claims — these are safety guarantees beyond the scope of any disclosed ingredient list
- Absence conclusions for ingredients whose omission from a list is routine regardless of presence (trace additives, processing aids, cross-contact sources)
- Absence conclusions for sub-components of undisclosed compound ingredients
- Absence conclusions where the materiality test fails (missing evidence could plausibly include the target ingredient)

### Standard Limitation Language

> "No [X] Identified" means the verified disclosed ingredient list for this dish does not contain [X]. This is not a claim that the dish is [X]-free. It does not address undisclosed compound ingredient components, micro ingredients, processing aids, cross-contact, or preparation variations. Diners with dietary restrictions or allergies should contact the restaurant directly.

### Example: Applies

A verified ingredient list contains: pasta, marinara sauce, basil, olive oil, garlic, parmesan. Beef is not listed. Beef is a primary ingredient that would typically be disclosed if present. The materiality test passes. GoldPan may conclude: "No Beef Identified."

### Example: Applies (explicitly disclosed micro ingredient)

A verified ingredient list explicitly includes "soy lecithin." GoldPan may treat soy lecithin as a verified present ingredient and use it as evidence for a "Contains Soy" conclusion — even though it is a micro ingredient. Explicit disclosure makes it verified evidence regardless of ingredient size.

### Example: Does Not Apply

A dish contains "caesar dressing" in its verified ingredient list. GoldPan cannot conclude "No Anchovies Identified." Caesar dressing is a compound ingredient whose sub-components are not disclosed. Anchovies are commonly present in caesar dressing but not expected to be explicitly listed as a sub-component on a restaurant menu. The absence of "anchovies" from the macro list does not establish their absence from the compound ingredient.

---

## GP-RULE-003 — Undisclosed Ingredient Rule

**Category:** General Knowledge  
**Version:** 1.1  
**Last updated:** 2026-06-28  
**Changelog:** v1.1 — Renamed from "Micro Absence Rule." Reframed around disclosure norms rather than ingredient scale. Clarified that this rule governs absence reasoning only, not presence claims from explicit disclosures.

### Purpose

Establishes that GoldPan cannot reason from the *absence* of a micro ingredient disclosure to conclude that the ingredient is absent. This rule is the complement of GP-RULE-002: where GP-RULE-002 says absence reasoning is valid when disclosure is expected, this rule says absence reasoning is invalid when disclosure is not expected.

Micro ingredients — processing aids, trace additives, sub-components of compound ingredients, cross-contact sources — are routinely not disclosed on restaurant menus even when present. The fact that a restaurant's ingredient list does not mention "xanthan gum" is not evidence that xanthan gum is absent. It is simply normal menu disclosure practice.

This rule does not restrict GoldPan from using *explicitly disclosed* micro ingredients as evidence. If a restaurant discloses "contains soy lecithin," that disclosure is verified evidence of presence. This rule only restricts reasoning from *absence* of micro ingredient disclosure.

### Evidence Required to Override This Rule

To make any micro-ingredient absence claim, GoldPan requires explicit documentation that specifically addresses the micro ingredient for that dish:

1. Official allergen guide that explicitly lists the dish and confirms absence of the allergen
2. Official nutrition document that discloses compound ingredient sub-components
3. Direct written restaurant confirmation addressing the specific micro ingredient or cross-contact question

A verified primary ingredient list alone does not satisfy this requirement.

### What This Rule Allows GoldPan to Compute

A "Micro-Level Confirmed" signal (distinct from a macro absence conclusion) when official documentation explicitly confirms absence of a micro ingredient or allergen for the specific dish.

### What This Rule Does Not Allow GoldPan to Compute

- Absence claims for micro ingredients based solely on their omission from a disclosed ingredient list
- Cross-contact absence claims without explicit kitchen practice documentation from the restaurant
- Sub-component absence claims for compound ingredients (e.g., "caesar dressing probably doesn't contain anchovies")
- Processing aid absence claims

### Standard Limitation Language

> GoldPan does not make claims about micro ingredients, undisclosed compound ingredient components, processing aids, cross-contact, or trace allergens for this dish unless explicitly documented by the restaurant. Diners with serious dietary restrictions or food allergies should contact the restaurant directly and should not rely on this information as a safety guarantee.

### Example: Applies

A restaurant's official allergen guide PDF explicitly states that a specific dish contains no peanuts and is prepared in a peanut-free environment. GoldPan cites this as a Micro-Level Confirmed source and may note peanut absence for that dish at the micro level.

### Example: Does Not Apply

A dish's verified primary ingredient list does not mention soy. GoldPan may not conclude "No Soy Identified" if the dish contains compound ingredients (sauces, dressings, marinades) that commonly contain soy derivatives. The absence of "soy" at the disclosed level does not establish its absence at the micro level. GP-RULE-002 may permit "No Soy Identified as a Primary Ingredient" — this rule prevents extending that to a soy-absence claim at all levels.

---

## GP-RULE-004 — Supporting Documents Rule

**Category:** General Knowledge  
**Version:** 1.0  
**Last updated:** 2026-06-28

### Purpose

Defines how GoldPan uses official supporting documents — allergen guides, nutrition PDFs, official website ingredient disclosures — as evidence sources that can strengthen or supplement conclusions. A supporting document can elevate a conclusion from "based on primary ingredient disclosure" to "confirmed by official documentation," but only when the document explicitly addresses the specific dish and claim.

### Evidence Required

- A specific, identifiable document published or confirmed by the restaurant
- The document must explicitly address the dish in question (not just a general statement about the restaurant's practices)
- The document must be current (dated or verifiably up to date)
- The document must be accessible and citable (URL, PDF filename, or direct confirmation reference)

### What This Rule Allows GoldPan to Compute

- Citing a supporting document as the evidence source for a verified claim
- Attributing a higher evidence tier to a conclusion when official documentation exists
- Strengthening a "No [X] Identified" conclusion to a "Confirmed by official allergen guide" conclusion when the document explicitly addresses the dish

### What This Rule Does Not Allow GoldPan to Compute

- Conclusions inferred from the document's general tone or context
- Conclusions about dishes not explicitly named in the document
- Conclusions that go beyond what the document actually states
- Treating a third-party aggregator's allergen data as a "supporting document" — only restaurant-published or restaurant-confirmed documents qualify

### Standard Limitation Language

> This conclusion is supported by [document name/URL], published by [restaurant]. GoldPan's conclusion reflects what that document states about this dish at the time of last verification ([date]). Restaurant menus and allergen guides change — diners should confirm with the restaurant before relying on this information.

### Example: Applies

Emmy Squared publishes an allergen guide PDF on their website listing each menu item and its allergens. GoldPan obtains and records this document. A dish listed in the PDF with "Contains: Dairy, Wheat" produces allergen conclusions citing the PDF as the evidence source.

### Example: Does Not Apply

A restaurant's website has a general statement: "We do our best to accommodate dietary needs." This statement does not constitute a supporting document for any specific dish's allergen status. GoldPan may not cite it as evidence for any derived conclusion.

---

## GP-RULE-005 — No Unsupported Inference Rule

**Category:** General Knowledge  
**Version:** 1.0  
**Last updated:** 2026-06-28

### Purpose

Prohibits GoldPan from computing derived conclusions through inference, extrapolation, assumption, or general knowledge about ingredient categories, cuisine types, or restaurant practices. Every conclusion must be traceable to a specific verified source. This rule has no exceptions and cannot be overridden by convenience, completeness targets, or user preference.

This rule is the foundation of GoldPan's trustworthiness. A conclusion with uncertain evidence is worse than no conclusion, because it presents uncertainty as fact.

### Evidence Required

This rule does not define evidence requirements — it defines a prohibition. No amount of contextual evidence permits inference. The appropriate response when verified evidence does not support a conclusion is to not compute the conclusion, and to document why.

### What This Rule Allows GoldPan to Compute

Nothing via inference. Only conclusions that can be directly traced to a verified source through one of the other rules in this registry.

### What This Rule Does Not Allow GoldPan to Compute

- "This dish is probably vegetarian because it's at an Italian restaurant"
- "This ingredient is likely gluten-free because it's a vegetable"
- "This dish probably doesn't contain peanuts because peanuts aren't common in this cuisine"
- "We can assume this dish is Active because the restaurant is still open"
- Ingredient types, cut types, preparations, or component roles derived from ingredient names alone
- Allergen flags derived from ingredient category assumptions rather than verified sources

### Standard Limitation Language

> GoldPan does not infer, estimate, or extrapolate conclusions beyond what verified sources explicitly support. Where verified evidence is insufficient to compute a conclusion, GoldPan reports the gap rather than filling it with an assumption.

### Example: Applies

A dish's ingredient list includes "grilled chicken breast." No preparation method is stated on the menu beyond the word "grilled." GoldPan records Preparation = "grilled" and Ingredient_Type = Unknown (the menu reviewed but Ingredient_Type was not stated). GoldPan does not infer "protein" for the chicken's Ingredient_Type based on general knowledge.

### Example: Does Not Apply

A reviewer attempts to set Ingredient_Type = "protein" for "chicken breast" because "everyone knows chicken is a protein." This violates the No Unsupported Inference Rule. Ingredient_Type may only be set from a verified source or left as Unknown pending review.

---

## GP-RULE-006 — Derived Filter Explanation Rule

**Category:** General Knowledge  
**Version:** 1.0  
**Last updated:** 2026-06-28

### Purpose

Requires that every derived filter GoldPan computes be accompanied by a structured four-part explanation. The explanation is not optional and is not a user interface feature — it is part of the evidence architecture. It provides the audit trail, supports debugging and validation, and enables future customer-facing "Why?" interactions.

A derived conclusion without an explanation is an architectural violation, regardless of whether the conclusion itself is correct.

### Evidence Required

The four-part explanation must be produced at the time the conclusion is computed, using the same verified evidence that produced the conclusion. It cannot be added retroactively without recomputing the conclusion.

The four required components are:

**1. Conclusion**  
The computed result, expressed as a specific, bounded statement.  
Examples: "No Beef Identified", "Grilled", "Vegetarian", "High Transparency"

**2. Evidence Used**  
The specific verified source(s) that supported the conclusion.  
Examples: "Verified ingredient list from live menu (adamandevecafe.com, June 27 2026)", "Official allergen guide PDF (Emmy Squared, accessed June 2026)"

**3. Reasoning**  
The named GoldPan business rule that produced the conclusion, expressed in plain language. Must cite the Rule ID.  
Example: "No disclosed primary ingredients contain beef. Per GP-RULE-002 (Macro Absence Rule), GoldPan concludes 'No Beef Identified.'"

**4. Limitations**  
The documented boundaries of the conclusion, drawn from the standard limitation language of the cited rule(s).  
Example: "'No Beef Identified' means the verified primary ingredient list does not contain beef. This is not a beef-free claim. It does not address micro ingredients, compound ingredient components, cross-contact, or preparation variations."

### What This Rule Allows GoldPan to Compute

Any derived conclusion that has a complete four-part explanation as described above.

### What This Rule Does Not Allow GoldPan to Compute

- Derived conclusions without a complete four-part explanation
- Explanations that reference vague logic ("the system computed this") rather than a named Rule ID
- Explanations produced separately from the conclusion and attached later
- Reasoning that cites logic hardcoded in a script without a corresponding named rule in this registry

### Standard Limitation Language

*(This rule's limitation language is the four-part explanation requirement itself. Each explanation's Limitations field is drawn from the standard limitation language of the rule(s) cited in the Reasoning field.)*

### Example: Applies

GoldPan computes a "No Pork Identified" filter for a dish and produces:

```
Conclusion:  "No Pork Identified"
Evidence:    Verified ingredient list from live menu (Brick & Tin, June 27 2026).
             Ingredients: spinach, romaine, champagne vinaigrette.
Reasoning:   No disclosed primary ingredient contains pork. Per GP-RULE-002
             (Macro Absence Rule v1.0), GoldPan concludes "No Pork Identified."
Limitations: "No Pork Identified" means the verified primary ingredient list does
             not contain pork. This is not a pork-free claim. It does not address
             micro ingredients, compound ingredient components, processing aids,
             cross-contact, or preparation variations. Diners with dietary
             restrictions should contact the restaurant directly.
```

### Example: Does Not Apply

A script computes "No Pork Identified" for a dish and stores only the boolean `true` with no explanation object. This violates the Derived Filter Explanation Rule, regardless of whether the conclusion is correct.

---

## GP-RULE-007 — Filter Evidence Dependency Rule

**Category:** General Knowledge  
**Version:** 1.0  
**Last updated:** 2026-06-28

### Purpose

Establishes that every derived filter must declare the type of evidence it depends upon, and that the GoldPan evaluation engine must use that declaration — not hardcoded per-filter logic — to determine whether sufficient verified evidence exists to compute a result or whether `Unknown` must be returned.

This rule decouples filter logic from evidence sufficiency logic. A filter knows what it computes. The engine knows whether the available evidence meets the filter's declared dependency. Neither should embed the other's responsibility.

### Evidence Dependency Types

Each filter must declare exactly one of the following dependency types:

**`macro_dependent`**  
The filter can be computed from verified primary ingredient disclosures alone, provided GP-RULE-001's materiality test passes. The filter does not require explicit micro-ingredient documentation.  
Examples: "No Beef Identified," "No Pork Identified," "Contains Dairy"

**`mixed_dependent`**  
The filter requires verified primary ingredient disclosures plus at least one additional contextual evidence type — such as preparation method, dietary certification, or cross-category reasoning across multiple ingredients.  
Examples: "Vegetarian" (requires verifying both that no meat is present and that preparation practices are disclosed or assumed per GP-RULE-001), "Grilled" (requires preparation method disclosure)

**`micro_dependent`**  
The filter can only be computed when official micro-ingredient documentation exists for the dish (as defined in GP-RULE-003). Primary ingredient disclosure alone is insufficient.  
Examples: "Sesame-Free (Micro-Level Confirmed)," "Prepared in a Peanut-Free Environment"

**`restaurant_claim_dependent`**  
The filter can only be computed when the restaurant has made an explicit, direct claim that GoldPan has recorded as verified evidence. General menus do not satisfy this dependency.  
Examples: "Certified Gluten-Free," "Certified Vegan," "Kosher," "Halal"

### Engine Behavior

When the evaluation engine computes a derived filter for a dish:

1. Read the filter's declared dependency type.
2. Check the available verified evidence against that dependency type.
3. If the evidence meets the dependency: apply the relevant rule(s) and compute the conclusion.
4. If the evidence does not meet the dependency: return `Unknown`. Record which evidence type is missing in the explanation's Limitations field.

The engine must not contain special-case branches for individual filters. The only branching is on dependency type.

### What This Rule Allows the Engine to Compute

Any derived conclusion for a filter whose declared dependency type is satisfied by the available verified evidence for that dish.

### What This Rule Does Not Allow the Engine to Compute

- Results for filters whose declared dependency type is not satisfied, even if a human reviewer believes the conclusion is probably correct
- Results based on evidence types lower in authority than the filter's declared dependency (e.g., using primary ingredient disclosure to satisfy a `restaurant_claim_dependent` filter)
- Results using undeclared evidence sources not covered by the filter's dependency type

### Standard Limitation Language

*(Produced by the engine when dependency is not met)*  
> This filter requires [dependency type] evidence. Available verified evidence for this dish does not meet that requirement. Result: Unknown. To resolve: [specific evidence needed].

### Example: Applies

Filter: "No Beef Identified" — declared dependency: `macro_dependent`  
Available evidence: verified primary ingredient list from live menu  
Engine check: `macro_dependent` ← verified primary ingredient list ✓  
GP-RULE-001 materiality test: passes (beef not plausibly in undisclosed gaps)  
Engine computes: "No Beef Identified" via GP-RULE-002

### Example: Does Not Apply — Dependency Not Met

Filter: "Certified Gluten-Free" — declared dependency: `restaurant_claim_dependent`  
Available evidence: verified primary ingredient list (no gluten-containing ingredients identified)  
Engine check: `restaurant_claim_dependent` ← verified primary ingredient list ✗  
Engine returns: `Unknown`  
Reason recorded: "Certified Gluten-Free requires explicit restaurant certification. A verified ingredient list alone does not satisfy this dependency."

### Example: Does Not Apply — Mixed Dependency Partially Met

Filter: "Vegetarian" — declared dependency: `mixed_dependent`  
Available evidence: verified primary ingredient list (no meat identified) but preparation method undisclosed  
Engine check: primary ingredient evidence ✓ | preparation evidence ✗  
Engine returns: `Unknown`  
Reason recorded: "Vegetarian filter requires both primary ingredient verification and preparation method disclosure. Preparation method is not verified for this dish."

---

## GP-RULE-008 — Data Freshness Rule

**Category:** General Knowledge  
**Version:** 1.0  
**Version:** 1.1  
**Last updated:** 2026-06-29  
**Changelog:** v1.1 — Added two-track freshness architecture (Source Check Track + Recanvass Track). Added `Source_Check_Status` field. Defined independent tier windows for each track. Clarified that the engine only reads `Recanvass_Status` (the synthesized verdict); source check escalation is pre-computed by `check_freshness.py`. Recanvass windows tightened to 30/90/180 days; due_soon lead reduced to 14 days.  
**See also:** `docs/RECANVASSING_POLICY.md`, `docs/FRESHNESS_IMPLEMENTATION_PLAN.md`

### Purpose

Establishes that a derived conclusion is only valid while its evidence source is reasonably current. Evidence quality (is the data correct as of canvass time?) and evidence freshness (is the data still correct today?) are independent properties. Both are required for a fully trustworthy derived conclusion.

A dish that passes all validation checks may still have stale data if the restaurant has changed its menu since the last canvass. Validation proves internal consistency. Recanvassing proves external freshness. GoldPan requires both.

### Two-Track Freshness Architecture

GoldPan maintains two independent but related freshness tracks:

**Track A — Public Source Check**  
Automated monitoring of public sources (website, menu page, PDFs). Detects whether anything *appears* to have changed. Never modifies GoldPan evidence. Output: `Source_Check_Status` in the Menu Source Registry.

**Track B — Full Recanvass**  
Human-driven evidence acquisition. Updates ingredients, scores, claims, and derived conclusions. Always triggered by a reason (scheduled window, source check flagging changes, forced flag). Output: updated staging files, `Recanvass_Status` recomputed.

**Principle:** Check often. Recanvass when evidence requires it.

### Tier Windows

| Tier | Source Check Window | Recanvass Window | Typical use |
|---|---|---|---|
| 1 | 7 days | 30 days | High-change restaurants |
| 2 | 14 days | 90 days | Standard (default) |
| 3 | 30 days | 180 days | Stable menus |

### Source_Check_Status Values

| Value | Meaning | Effect on Recanvass_Status |
|---|---|---|
| `ok` | Source reachable; no changes detected | None |
| `changed` | Content appears to have changed | Escalates to `needs_review` |
| `unreachable` | 404 / error / timeout | Escalates to `needs_review` |
| `overdue` | Source check window expired | Noted in report; no direct effect |
| `unknown` | Never checked | Treated as a trigger → `needs_review` |

### Recanvass_Status Values and Meanings

| Status | Meaning |
|---|---|
| `current` | Last canvass within the recanvass window; no active triggers. Full confidence. |
| `due_soon` | Within 14 days of the recanvass window boundary. Evidence still fresh; recanvass should be scheduled. |
| `overdue` | Past the recanvass window; no active triggers. Evidence may no longer reflect the current menu. |
| `needs_review` | A trigger is active (see trigger catalog in `docs/FRESHNESS_IMPLEMENTATION_PLAN.md`). Data freshness cannot be established. |

### Engine Behavior Required by This Rule

The engine reads only `Recanvass_Status` — the synthesized verdict computed by `check_freshness.py`. It does not read `Source_Check_Status` directly. This decouples the engine from the source of the freshness signal.

`Recanvass_Status` must be checked as Gate 0 — before the dependency-type check (GP-RULE-007) and before the materiality test (GP-RULE-001):

```
if Recanvass_Status in ("needs_review", "unknown"):
    return Unknown  ← all derived conclusions suppressed
elif Recanvass_Status == "overdue":
    proceed, but cap confidence at "likely" (see GP-RULE-009)
elif Recanvass_Status in ("current", "due_soon"):
    proceed normally
```

### What This Rule Requires

- The pipeline must compute `Recanvass_Status` for every active restaurant at the start of every run
- `Recanvass_Status` must be recomputed from source data (dates, tier, triggers, `Source_Check_Status`) — it must not be read from a stored value without recomputing
- `Source_Check_Status = "changed"` or `"unreachable"` must escalate `Recanvass_Status` to `"needs_review"` before the engine is called
- Every derived conclusion must include the freshness context (`Recanvass_Status`, `Source_Check_Status`, `last_canvassed`) so the explanation object can note staleness conditions
- A `needs_review` status must be logged in the pipeline report and resolved before full-confidence results can be served for that restaurant's dishes

### What This Rule Does Not Cover

This rule governs whether GoldPan's records are current relative to the restaurant's publicly available menu sources. It does not govern:
- Kitchen practices, cross-contact, or preparation variations not stated on the menu
- Ingredient changes made but not yet published by the restaurant
- Supply chain changes not disclosed in the menu

Those limitations are covered by GP-RULE-002 and GP-RULE-003.

### Standard Limitation Language

*(Added to derived conclusions when Recanvass_Status is not `current`)*

> **due_soon:** "Note: This restaurant's menu data is approaching its scheduled recanvass date (last canvassed: [Last_Canvassed], [N] days remaining). Results reflect verified data as of that date."

> **overdue:** "Warning: This restaurant's menu data is past its scheduled recanvass window ([N] days overdue). Results are shown with reduced confidence. Last verified: [Last_Canvassed]. Diners should confirm current menu details with the restaurant directly."

> **needs_review:** *(Result is Unknown — conclusion is suppressed, not caveated)*

---

## GP-RULE-009 — Stale Evidence Confidence Degradation Rule

**Category:** General Knowledge  
**Version:** 1.0  
**Last updated:** 2026-06-28  
**Depends on:** GP-RULE-008  
**See also:** `docs/RECANVASSING_POLICY.md`

### Purpose

Specifies the exact confidence outcomes that each `Recanvass_Status` value produces for derived filter conclusions. This rule translates the freshness signal defined in GP-RULE-008 into the confidence field of the `DerivedConclusion` object.

Confidence in a derived conclusion has two independent components: evidence quality (covered by GP-RULE-001 through GP-RULE-007) and evidence freshness (covered by this rule). The final confidence assigned to any conclusion is the minimum of what evidence quality and evidence freshness each independently support.

### Confidence Mapping

| `Recanvass_Status` | Maximum confidence allowed | Effect |
|---|---|---|
| `current` | `verified` | No change to evidence-quality confidence |
| `due_soon` | `verified` | No change; staleness caveat added to limitations only |
| `overdue` | `likely` | Confidence capped at `likely` regardless of evidence quality |
| `needs_review` | `unknown` | Conclusion suppressed; all results return `unknown` |

These are **maximum** values. A conclusion whose evidence quality already produces `likely` or `unknown` is not upgraded by a `current` recanvass status. The degradation is one-directional: staleness can only reduce confidence, never increase it.

**Examples:**

- Dish with strong evidence + `current` status → `verified` (unaffected)
- Dish with strong evidence + `overdue` status → `likely` (capped by staleness)
- Dish with ambiguous evidence (`likely`) + `current` status → `likely` (not upgraded)
- Dish with ambiguous evidence (`likely`) + `overdue` status → `likely` (already degraded)
- Dish with strong evidence + `needs_review` status → `unknown` (suppressed)

### What This Rule Requires

- The confidence field of every `DerivedConclusion` must reflect both evidence quality and evidence freshness
- The engine must apply staleness degradation after computing the evidence-quality confidence
- The `limitations` field of the explanation must include the appropriate staleness caveat language from GP-RULE-008 when confidence is degraded
- A confidence value of `likely` due to staleness must be distinguishable from `likely` due to evidence quality in the explanation — the reasoning field must cite this rule (GP-RULE-009) when staleness is the cause

### What This Rule Does Not Allow

- Serving `verified` confidence for dishes at restaurants with `overdue` or `needs_review` status
- Silently degrading confidence without documenting the staleness reason in the explanation
- Treating a manually updated `Last_Canvassed` date (without a corresponding confirmed `Menu_Changed = no` or new staging file) as proof of freshness

### Standard Reasoning Language

*(Used in the DerivedConclusion `reasoning` field when staleness affects confidence)*

> "Evidence quality supports [original confidence] for this conclusion. However, this restaurant's `Recanvass_Status` is `overdue` (last canvassed: [date], [N] days past the [window]-day recanvass window). Per GP-RULE-009 (Stale Evidence Confidence Degradation Rule), confidence is capped at `likely`."

---

---

## GP-RULE-010 — Source Authority Hierarchy Rule

**Version:** 1.0  
**Last updated:** 2026-06-28  
**Category:** Evidence  
**Layer:** Evidence Acquisition  
**See also:** `docs/EVIDENCE_ARCHITECTURE.md`

### Purpose

Defines the canonical hierarchy of trusted acquisition sources. Every piece of evidence that enters GoldPan must come from a source within this hierarchy. Sources below the minimum threshold are rejected at the acquisition boundary — they may not be used to create, enrich, or correct any GoldPan record.

This rule governs three questions for each source:

1. **Trust tier** — how authoritative is this source relative to others?
2. **Authorized operations** — which database actions may this source initiate? (create, enrich, correct)
3. **Quality eligibility** — which evidence dependency types (GP-RULE-007) does this source satisfy?

### Source Authority Tiers

---

**Tier 1 — Direct Restaurant Authority**

The restaurant is speaking in its own voice, with specific intent to communicate a fact about a specific dish or ingredient.

| Source | Provenance value | Description |
|---|---|---|
| Direct restaurant confirmation | `restaurant_confirmation` | Written or documented verbal confirmation from restaurant staff or ownership, addressed to a specific claim about a specific dish |
| Official allergen guide | `allergen_guide` | Allergen document published by the restaurant and verifiable as current — lists individual dishes explicitly |
| Official nutrition document | `nutrition_document` | Nutrition PDF or page published by the restaurant — lists macronutrients or ingredients per dish |

**What Tier 1 authorizes:**
- Enrich any existing dish's fields
- Correct any previously recorded value with appropriate review (see GP-RULE-012)
- Satisfy `restaurant_claim_dependent` and `micro_dependent` evidence requirements (GP-RULE-007)
- Satisfy `macro_dependent` evidence requirements

**What Tier 1 does not authorize:**
- Create a new dish (dish creation requires a live menu source — see Tier 2)
- Override a more recent Tier 1 source without human review

---

**Tier 2 — Official Published Menu**

The restaurant's menu as published in an authoritative, restaurant-controlled channel. This is the required source for dish creation and the most common source for primary ingredient evidence.

| Source | Provenance value | Description |
|---|---|---|
| Live restaurant menu — official website | `menu` | Menu page on the restaurant's own domain, verified as current at time of canvass |
| Live restaurant menu — in-person | `menu` | Physical menu reviewed during an in-person canvass |
| Official restaurant website (non-menu) | `website` | Other pages on the restaurant's official website — about page, ingredient sourcing statements, dietary information outside the menu |

**What Tier 2 authorizes:**
- Create new dishes (live menu only — `menu` provenance required; `website` alone does not authorize creation)
- Enrich existing dishes with ingredient, preparation, and dietary data found on the menu
- Satisfy `macro_dependent` evidence requirements for primary ingredient disclosure

**What Tier 2 does not authorize:**
- Satisfy `restaurant_claim_dependent` requirements (explicit certification claims require Tier 1 confirmation)
- Satisfy `micro_dependent` requirements (micro-ingredient confirmation requires Tier 1 documentation)
- Override a Tier 1 source without human review

---

**Tier 3 — Restaurant-Managed Ordering Platform**

An ordering platform where the restaurant controls and maintains its own menu listing. Treated as a secondary menu source — lower authority than the restaurant's own website because the platform intermediates the relationship.

| Source | Provenance value | Description |
|---|---|---|
| Restaurant-managed ordering platform | `ordering_platform` | DoorDash, Uber Eats, Toast, Square, or similar — only when the restaurant is confirmed to manage its own menu content on the platform |

**What Tier 3 authorizes:**
- Create new dishes, with the additional requirement that a canvasser notes the platform was the verified source and the restaurant manages it directly
- Enrich existing dishes with ingredient data
- Satisfy `macro_dependent` evidence requirements

**What Tier 3 does not authorize:**
- Satisfy `restaurant_claim_dependent` or `micro_dependent` requirements
- Override any Tier 1 or Tier 2 source (Tier 3 conflicts trigger review, not auto-override — see GP-RULE-012)

**Important:** A Tier 3 source is only valid when GoldPan has confirmed that the restaurant manages its own menu on the platform. If the platform's content is auto-generated or managed by the platform, the source is rejected.

---

**Tier 4 — Restaurant-Answered Customer Communication**

Evidence from a specific exchange in which a restaurant staff member directly answered a question from a customer or canvasser. Not a published document — a direct communication.

| Source | Provenance value | Description |
|---|---|---|
| Restaurant-answered question | `restaurant_qa` | A specific question asked to restaurant staff and answered, with the exchange documented |

**What Tier 4 authorizes:**
- Enrich a specific field for a specific dish, scoped to the exact claim the restaurant addressed
- Supplement a Tier 2 or Tier 3 record with specific detail not stated on the menu
- Satisfy `macro_dependent` requirements for the specific claim addressed

**What Tier 4 does not authorize:**
- Create new dishes
- Satisfy `restaurant_claim_dependent` requirements without corroborating documentation
- Override Tier 1, 2, or 3 records without human review

**Important:** Tier 4 evidence is narrow. A restaurant staff member saying "I believe that dish is gluten-free" is not Tier 1 confirmation — it is a Tier 4 belief statement. To rise to Tier 1, the restaurant must produce documented confirmation (written, from management, addressing the specific claim).

---

**Rejected — Below Acquisition Threshold**

Sources below this threshold may not enter GoldPan as evidence. They may be used by a canvasser to locate official sources, but may not themselves be cited as the basis for any GoldPan record.

| Source | Why rejected |
|---|---|
| Third-party aggregators (Yelp, Google, TripAdvisor) | Content is user-generated or platform-generated; restaurant does not control accuracy |
| Social media posts | Not a controlled channel; not representative of current menu policy |
| Food review websites | Editorial, not operational |
| Second-hand reports (e.g., "a friend said") | Not verifiable, not restaurant-sourced |
| Platform-generated menu content | Not managed by the restaurant; accuracy not guaranteed |

### The MACRO_ELIGIBLE_SOURCES Constant

GP-RULE-007 defines `macro_dependent` as the evidence dependency type satisfied by verified primary ingredient disclosures from an authoritative source. The specific sources that satisfy `macro_dependent` requirements are:

```
MACRO_ELIGIBLE_SOURCES = {
    "menu",
    "website",
    "pdf",                  # legacy catch-all — maps to allergen_guide or nutrition_document
    "allergen_guide",
    "nutrition_document",
    "restaurant_confirmation",
    "ordering_platform",
    "restaurant_qa",
}
```

This constant — `MACRO_ELIGIBLE_SOURCES` — is the authoritative definition of what the engine considers sufficient to satisfy a `macro_dependent` filter dependency. It is defined in `schema.py` and imported by `derived/engine.py`. The engine must not define its own trust list.

**Migration note:** The current engine constant `VERIFIED_SOURCES = {"menu", "pdf", "website", "restaurant_confirmation"}` is the predecessor of `MACRO_ELIGIBLE_SOURCES`. It must be replaced by the `schema.py` import as part of the schema module implementation (see `docs/ARCHITECTURAL_HEALTH_REVIEW.md` Finding 3). Until migration is complete, the engine's `VERIFIED_SOURCES` and `schema.MACRO_ELIGIBLE_SOURCES` must be kept in sync.

**Why the name changed:** `VERIFIED_SOURCES` implied these sources are verified. They are not verified by the constant — they are trusted acquisition channels whose evidence is eligible to satisfy quality requirements. `MACRO_ELIGIBLE_SOURCES` describes what the constant actually governs: eligibility for macro_dependent evidence dependency satisfaction.

**The `pdf` legacy value:** The provenance value `"pdf"` is a legacy catch-all that was used before `allergen_guide` and `nutrition_document` were defined as distinct types. A PDF could be Tier 1 (official allergen guide) or Tier 2 (generic menu PDF). Until a schema migration disambiguates existing `pdf` records, `"pdf"` maps to `MACRO_ELIGIBLE_SOURCES` membership. Future canvassing should use `allergen_guide` or `nutrition_document` as appropriate.

### Standard Limitation Language

> This evidence was acquired from [source type] ([Tier N]). The source authority tier determines the operations this evidence may authorize and the quality dependency types it may satisfy (per GP-RULE-010). A lower-tier source cannot override a higher-tier source without human review (per GP-RULE-012).

### Example: Applies — Tier hierarchy respected

GoldPan has `Ingredient_Source = "menu"` (Tier 2) for a dish's allergen data. A restaurant then provides a direct written confirmation (Tier 1) adding a specific allergen not stated on the menu. The Tier 1 source enriches the existing Tier 2 record. Both are recorded with their respective provenance. The Tier 1 confirmation takes precedence for the specific claim it addressed.

### Example: Applies — Rejected source handled correctly

A canvasser finds allergen information on Yelp. The source is below the acquisition threshold. The canvasser uses the Yelp listing to locate the restaurant's official website, then cites the official website as the source. Yelp is not recorded as evidence. Only the official website is cited.

### Example: Does Not Apply — Below-threshold source entered as evidence

A dish record cites `Ingredient_Source = "yelp"` or similar. This violates GP-RULE-010. The record must be flagged and re-canvassed from an eligible source. The below-threshold value must not be used to satisfy any quality dependency.

---

## GP-RULE-011 — Evidence Provenance Rule

**Version:** 1.0  
**Last updated:** 2026-06-28  
**Category:** Evidence  
**Layer:** Evidence Acquisition  
**Depends on:** GP-RULE-010  
**See also:** `docs/EVIDENCE_ARCHITECTURE.md`

### Purpose

Every fact recorded in GoldPan that is used as input to the rules engine must carry complete provenance — where it came from, when it was collected, and what it applies to. Provenance is not optional metadata. It is a first-class data requirement. Evidence without complete provenance cannot be used to compute any derived conclusion.

This rule defines what "complete provenance" means and what fields must be present for each piece of evidence. It closes the architectural gap where evidence enters GoldPan but its origin becomes untraceable downstream.

### Required Provenance Fields

Every evidence item used by the rules engine must record all four of the following:

---

**1. `source_type`**  
The acquisition channel, using a canonical provenance value from GP-RULE-010's authority hierarchy.

Valid values: `menu`, `website`, `allergen_guide`, `nutrition_document`, `restaurant_confirmation`, `ordering_platform`, `restaurant_qa`, `pdf` (legacy)

Currently stored in: `Ingredient_Source` column (Ingredient Details)  
Gap: `Ingredient_Source` captures this field at the ingredient-row level. ✓

---

**2. `source_reference`**  
A specific, locatable reference to the source — not a category but a specific instance.

| Source type | Required reference |
|---|---|
| `menu` | URL of the menu page canvassed, as it appeared on the canvass date |
| `website` | URL of the specific page |
| `allergen_guide` | URL or filename of the document |
| `nutrition_document` | URL or filename of the document |
| `restaurant_confirmation` | Description of the exchange: medium (email/call/in-person), date, who confirmed |
| `ordering_platform` | URL of the restaurant's page on the platform |
| `restaurant_qa` | Description of the question asked, medium, date, restaurant representative if known |
| `pdf` (legacy) | Filename or URL |

Currently stored in: the Menu Source Registry, at the restaurant level. **Gap: not stored at the ingredient-row level.** A single restaurant may have multiple menu sources across its canvassing history, and individual ingredient rows do not currently carry the specific URL from which each fact was obtained.

---

**3. `acquired_date`**  
The ISO 8601 date (YYYY-MM-DD) on which the canvasser obtained the evidence from the source.

Currently stored in: `Last_Canvassed` (Menu Source Registry, restaurant-level). **Gap: not stored at the ingredient-row level.** The existing `Version` field and the `last_updated` concept are partial stand-ins, but neither is a reliable per-ingredient acquisition date.

---

**4. `scope`**  
What the evidence applies to. Evidence must not be used to support conclusions outside its scope.

| Value | Meaning | Example |
|---|---|---|
| `dish` | The evidence applies to this dish as a whole (e.g., an allergen confirmed for the entire dish) | Allergen guide entry for a specific dish |
| `ingredient` | The evidence applies to a specific ingredient within the dish | Menu description of a specific component |
| `restaurant` | The evidence applies to all dishes at this restaurant (e.g., a kitchen-wide practice) | "All dishes prepared in a nut-free kitchen" |
| `menu` | The evidence applies to all dishes on this menu at the time of canvass | A menu-wide "no MSG" claim |

Currently stored in: not captured systematically. **Gap: scope is implicit, not recorded.**

### Current Implementation State

| Provenance field | Currently captured | Where | Gap |
|---|---|---|---|
| `source_type` | Yes | `Ingredient_Source` (ingredient row) | Partially — legacy `"pdf"` is ambiguous; `ordering_platform` and `restaurant_qa` values do not yet exist |
| `source_reference` | Partially | Menu Source Registry (restaurant level only) | Not at ingredient level |
| `acquired_date` | Partially | `Last_Canvassed` (restaurant level only) | Not at ingredient level |
| `scope` | No | — | Not captured anywhere |

This rule defines the target state. The current implementation captures `source_type` and partially captures `source_reference` and `acquired_date` at the restaurant level. Full provenance at the ingredient level is the goal for the schema evolution path.

### Minimum Viable Provenance (Current State)

Until ingredient-level `source_reference`, `acquired_date`, and `scope` are implemented, the minimum viable provenance requirement for engine use is:

- `Ingredient_Source` (source_type) must be a canonical value from GP-RULE-010's authority hierarchy
- The restaurant must have a valid entry in the Menu Source Registry with a recorded `Last_Canvassed` date
- The `Ingredient_Source` value must be in `MACRO_ELIGIBLE_SOURCES` (GP-RULE-010) for the evidence to satisfy any quality dependency

This minimum satisfies current derived filter computation. The full provenance requirement governs the target architecture and must be implemented as part of the schema evolution tracked in `docs/ARCHITECTURAL_HEALTH_REVIEW.md`.

### What This Rule Requires of the Engine

The engine must not compute a derived conclusion for any dish where:
- `Ingredient_Source` is blank or `"unknown"` for any ingredient cited as evidence
- `Ingredient_Source` is a value not in `MACRO_ELIGIBLE_SOURCES` for ingredients cited in a `macro_dependent` filter
- The restaurant has no `Last_Canvassed` date in the Menu Source Registry

These are the minimum provenance checks the engine can currently perform. As the schema evolves to capture full provenance, the engine's provenance checks must expand accordingly.

### What This Rule Does Not Require (Yet)

- Ingredient-level `source_reference` URLs (required in future schema)
- Ingredient-level `acquired_date` (required in future schema)
- Explicit `scope` values (required in future schema)

### Standard Limitation Language

> Evidence provenance for this conclusion: [source_type] acquired [acquired_date] from [source_reference], applying to [scope]. Provenance completeness: [full / minimum viable]. Derived conclusions computed under minimum viable provenance may be revised when full provenance is recorded.

### Example: Applies — Full provenance

An ingredient row has:
- `Ingredient_Source = "allergen_guide"` (source_type ✓)
- The Menu Source Registry records `source_url = "https://emmysquared.com/allergen-guide.pdf"` and `Last_Canvassed = 2026-06-27` (source_reference and acquired_date ✓ at restaurant level)

The engine has sufficient provenance to compute a derived conclusion citing this evidence.

### Example: Does Not Apply — Missing source_type

An ingredient row has `Ingredient_Source = ""` (blank). The engine cannot determine the acquisition channel. This evidence fails the minimum viable provenance check and must not be cited in any derived conclusion. The dish should return `Unknown` for filters that depend on this ingredient's data.

### Example: Does Not Apply — Below-threshold source_type

An ingredient row has `Ingredient_Source = "unknown"` — written by the old `upsert_dishes.py` before the source-field fix (documented in `BACKFILL_RELIABILITY_REPORT.md`). `"unknown"` is not in `MACRO_ELIGIBLE_SOURCES`. The engine treats this as a provenance failure. This is the root cause of the 673-dish `Unknown` result that triggered the backfill reliability investigation.

---

## GP-RULE-012 — Acquisition Conflict Resolution Rule

**Version:** 1.0  
**Last updated:** 2026-06-28  
**Category:** Evidence  
**Layer:** Evidence Acquisition  
**Depends on:** GP-RULE-010, GP-RULE-011  
**See also:** `docs/EVIDENCE_ARCHITECTURE.md`

### Purpose

Defines what GoldPan does when two acquisition sources disagree about the same fact. Conflicts arise when a restaurant updates its menu, when a direct confirmation contradicts a published document, when two staff members give different answers, or when a stale record has not been updated since a menu change.

Without a conflict resolution rule, GoldPan faces a choice between two bad options: silently keeping whichever value was recorded first (stale wins by inertia) or silently overwriting with whatever was seen last (recency wins without judgment). Neither is acceptable. This rule defines the governed alternative.

### Resolution Principles

Conflicts are resolved in priority order. Apply the first principle whose conditions are met.

---

**Principle 1 — Higher authority tier wins**

When two sources of different tiers make conflicting claims about the same fact, the higher-tier source governs.

| Higher tier | Lower tier | Resolution |
|---|---|---|
| Tier 1 (restaurant confirmation) | Tier 2 (menu) | Tier 1 governs the specific claim it addressed |
| Tier 1 (allergen guide) | Tier 3 (ordering platform) | Tier 1 governs |
| Tier 2 (official menu) | Tier 3 (ordering platform) | Tier 2 governs |
| Tier 2 (official menu) | Tier 4 (restaurant Q&A) | Tier 2 governs as the primary record; Tier 4 may supplement for claims not addressed by Tier 2 |

**Caveat — freshness override (see Principle 2):** A lower-tier source that is significantly more recent than a higher-tier source does not automatically lose. When the higher-tier source is stale (its restaurant is `overdue` or `needs_review`), Principle 2 applies alongside Principle 1.

---

**Principle 2 — More recent evidence wins among equal tiers**

When two sources of equal tier conflict, the more recently acquired evidence governs, provided the acquisition dates differ by more than 30 days. A difference of 30 days or less is within the margin of canvassing variation and does not automatically favor the newer source — human review is required.

| Condition | Resolution |
|---|---|
| Equal tier, date difference > 30 days | More recent source governs |
| Equal tier, date difference ≤ 30 days | Flag for human review; do not auto-resolve |
| Equal tier, same acquisition date | Flag as a genuine conflict; do not auto-resolve |

---

**Principle 3 — More specific evidence wins for its scope**

A Tier 4 restaurant Q&A that addresses a specific claim ("Does this dish contain sesame?") governs that specific claim even if the Tier 2 menu does not address it. Specificity governs within scope; it does not override the general record outside scope.

A dish-scoped confirmation governs that dish. A restaurant-scoped statement (e.g., "we never use peanuts") governs the restaurant but is weaker than a dish-level allergen guide entry for a specific dish.

---

**Principle 4 — Stale evidence does not override fresh evidence without review**

A higher-tier source that is stale (`Recanvass_Status = overdue` or `needs_review` for its restaurant) does not automatically win over a lower-tier source that is current.

| Scenario | Resolution |
|---|---|
| Stale Tier 1 vs. current Tier 2 | Flag for human review; serve the current Tier 2 value with freshness caveat |
| Stale Tier 2 vs. current Tier 3 | Flag for human review; note the conflict in the dish record |
| Any stale source vs. direct customer-reported discrepancy | Flag restaurant for `needs_review` immediately |

A stale source being overridden by a fresher one of any tier is a signal that the database may need recanvassing, not just conflict resolution. The conflict itself triggers the freshness review.

---

**Principle 5 — Equal-tier, comparable-date conflicts require human review**

When two sources of equal tier, with acquisition dates within 30 days, disagree about the same fact, no automatic resolution is applied. The field is set to `Unknown`, the conflict is logged in the dish record, and the conflict is surfaced in the next database validation run. The dish is not removed from the application — it is served with reduced confidence pending resolution.

This principle is especially important for allergen data. An unresolved allergen conflict must never be silently resolved in favor of either source, because either resolution could be wrong and the consequences are safety-relevant.

### Corrective Acquisition

A restaurant correction is a Tier 1 acquisition event — the restaurant is directly correcting a GoldPan record. Corrections are not auto-applied. The following process is required:

1. Record the correction with full provenance (GP-RULE-011): source_type = `restaurant_confirmation`, source_reference describes the medium and date, scope specifies which dish and field.
2. Identify the field being corrected and its current value and source.
3. Apply Principles 1–4 to determine whether the correction governs.
4. If the correction governs: update the field, log the prior value and the correction event in `Recanvass_Notes`, update `Last_Canvassed` if the correction constitutes a full data review.
5. If the correction conflicts with another Tier 1 source: apply Principle 5 — flag for human review, do not auto-apply.
6. For allergen-related corrections: always require human confirmation before applying, regardless of tier.

### What This Rule Does Not Allow

- Silent overwrites — any conflict resolution that changes a recorded value must be logged with the prior value, the new value, the source that won, and the resolution principle applied
- Auto-applying corrections to allergen or safety-relevant fields without human review
- Treating a recency signal alone (new source) as sufficient to override a verified higher-tier source
- Resolving equal-tier, comparable-date conflicts by defaulting to either source

### Standard Limitation Language

> A conflict between acquisition sources was detected for [field] on [dish_id]. Resolution applied: [Principle N — description]. Prior value: [value] ([source_type], [acquired_date]). Current value: [value] ([source_type], [acquired_date]). If you believe this resolution is incorrect, contact GoldPan to initiate a source review.

*(This limitation is added to any derived conclusion where the underlying evidence was affected by a conflict resolution.)*

### Example: Applies — Higher tier wins

GoldPan records `allergen_flags = "none"` for a dish, sourced from `Ingredient_Source = "menu"` (Tier 2). Emmy Squared provides a direct written allergen confirmation (Tier 1) stating the dish contains dairy. Principle 1 applies: Tier 1 governs the specific claim. The allergen field is updated to `"dairy"`, the correction is logged with full provenance, and the prior value and resolution principle are recorded in Recanvass_Notes.

### Example: Applies — Stale high-tier yields to review

GoldPan has a Tier 1 restaurant confirmation from 2025-01-10 stating a dish has no peanuts. The restaurant's `Recanvass_Status` is `overdue` — the data is 18 months old. A canvasser's new Tier 2 menu canvass shows the dish now includes a peanut sauce. Principle 4 applies: the stale Tier 1 source does not automatically override the current Tier 2 source. The conflict is flagged for human review. The dish is served with `confidence = "unknown"` on the allergen claim until resolved.

### Example: Does Not Apply — Silent overwrite

A script re-upserts a dish from a new staging file and silently overwrites `Ingredient_Source`, `allergen_flags`, and `Ingredient_Type` without logging the prior values or checking whether a higher-tier source previously set those values. This violates GP-RULE-012. Any script that writes to enrichment fields must check the current value's provenance before overwriting and must log any conflict according to the principles in this rule.

---

## GP-RULE-013 — Dietary Tag Provenance Rule

**Version:** 1.0
**Last Updated:** 2026-06-30
**Category:** Evidence
**Scope:** Goldpan Dish Level Data (Tag_Source field), dishes.json, API and consumer output
**Depends on:** GP-RULE-006 (Derived Filter Explanation Rule), GP-RULE-011 (Evidence Provenance Rule)

### Purpose

GoldPan records two categories of dietary information that are fundamentally different in nature and must not be conflated:

1. **Restaurant-disclosed dietary attributes** — The restaurant explicitly discloses that a dish meets a dietary standard (e.g., "Vegan", "Gluten-Free") on their menu, website, or official materials. This is a restaurant claim. GoldPan records it; the restaurant is accountable for its accuracy.

2. **GoldPan-derived dietary conclusions** — GoldPan analyzes a verified primary ingredient list and concludes that a dish meets a dietary standard (e.g., no beef identified from ingredient review). This is a GoldPan inference. GoldPan is accountable for the reasoning, evidence used, confidence level, and limitations.

These two categories carry different evidence standards, different accountability, and must be surfaced differently to consumers. Conflating them — or leaving the source undisclosed — violates the evidence integrity that GoldPan's transparency mission requires.

### Requirements

**R1 — Tag_Source is required for all dietary tags**
Every dish row in Goldpan Dish Level Data that contains a non-empty `Dietary_Tags` value must have a corresponding non-empty `Tag_Source` value. A blank `Tag_Source` with a non-blank `Dietary_Tags` is a data quality warning. GoldPan cannot vouch for undocumented tag provenance.

**R2 — Canonical Tag_Source values**
`Tag_Source` must be one of the following canonical values:

| Value | Meaning |
|---|---|
| `restaurant_disclosed` | The restaurant explicitly discloses this dietary attribute on their menu, website, or official materials. GoldPan records it as a restaurant claim. |
| `goldpan_inferred` | GoldPan derived this dietary attribute from ingredient analysis during canvassing. This tag is pending migration to the derived_filters layer (see R4). |

**R3 — Restaurant-disclosed tags remain in the tags field**
`restaurant_disclosed` dietary tags are legitimate restaurant claims and may remain in the `Dietary_Tags` / `tags` field indefinitely. They must always be accompanied by `Tag_Source = "restaurant_disclosed"` so consumers and downstream systems can identify their origin.

**R4 — GoldPan-inferred tags must migrate to derived_filters**
Any tag with `Tag_Source = "goldpan_inferred"` is a derived dietary conclusion that was recorded in the tags field before the derived_filters architecture existed. These tags must eventually be formalized as `restaurant_claim_dependent` or `macro_dependent` derived filters (per GP-RULE-006 and GP-RULE-007) with:
- A declared conclusion and confidence level
- Evidence_used citations
- Reasoning that cites the specific evidence supporting the conclusion
- Standard limitations language
- Applicable rule_ids

Until migration is complete, `goldpan_inferred` tags are surfaced as-is but flagged in the data quality layer.

**R5 — Consumer-facing output must distinguish tag provenance**
Consumer-facing output (dishes.json, API responses, UI) must expose `tag_source` alongside dietary tags. Consumers must be able to distinguish:
- "This restaurant says this dish is vegan" (restaurant_disclosed)
- "GoldPan concludes no beef was identified from the verified ingredient list" (derived_filter conclusion)

These are not equivalent claims and must not be presented as equivalent.

**R6 — Blank Tag_Source is a data quality warning, not an error**
A blank `Tag_Source` does not block the pipeline. It is recorded as a WARNING in `validate_database.py` and must be resolved before a dish's dietary tags are considered complete. Tags with no source are treated as unverified restaurant data.

### Migration Path

Phase 1 (current): Pull `Tag_Source` through to `dishes.json`. Blank Tag_Source generates validation warnings.

Phase 2: Audit all `Dietary_Tags` rows. Classify each as `restaurant_disclosed` or `goldpan_inferred`. Populate `Tag_Source`.

Phase 3: Implement `restaurant_claim_dependent` derived filters for common dietary attributes (vegan, vegetarian, gluten-free). These use verified restaurant claims as their evidence source.

Phase 4: Migrate `goldpan_inferred` tags into the appropriate derived filter. Remove from `Dietary_Tags`. Consumer output reflects two distinct evidence layers.

### Standard Limitation Language

For `restaurant_disclosed` tags:
> This dietary attribute (e.g., "Vegan") was disclosed by the restaurant on their menu or official materials. GoldPan records this as a restaurant claim. GoldPan has not independently verified all ingredients for compliance with this dietary standard. Contact the restaurant to confirm before dining.

For `goldpan_inferred` tags (pending migration):
> This dietary attribute was inferred by GoldPan from ingredient analysis during canvassing. It is pending formalization as a derived filter conclusion with full evidence documentation. Treat with the same caution as a GoldPan-derived conclusion.

### Example: Applies — Restaurant discloses dietary tag

Kale Me Crazy labels a bowl "Vegan" on their in-store menu. The canvasser records `Dietary_Tags = "vegan"` and `Tag_Source = "restaurant_disclosed"`. This is a restaurant claim. GoldPan records it faithfully. The consumer sees: *"Kale Me Crazy labels this dish as Vegan."*

### Example: Applies — GoldPan infers tag from ingredients

During canvassing, a canvasser reviews the ingredient list for a Real & Rosemary salad and determines no animal products are present. They record `Dietary_Tags = "vegan"` but `Tag_Source` is left blank. This violates R1. A validation warning is issued. The canvasser must classify the tag as either `restaurant_disclosed` (if the restaurant labels the dish vegan) or `goldpan_inferred` (if GoldPan derived it from ingredients). If `goldpan_inferred`, the conclusion should eventually be formalized as a derived filter.

### Example: Does Not Apply

A dish with no `Dietary_Tags` value. No Tag_Source required. Rule does not trigger.

---

## GP-RULE-014 — Allergen Evidence Rule

**Version:** 1.0  
**Last updated:** 2026-06-30  
**Layer:** Evidence System  
**Depends on:** GP-RULE-010 (Source Authority Hierarchy Rule), GP-RULE-011 (Evidence Provenance Rule)  
**See also:** `docs/ALLERGEN_ARCHITECTURE.md`, `docs/GOLDPAN_PHILOSOPHY.md`

### Purpose

Governs how GoldPan records allergen evidence in the Evidence System. Defines canonical allergen vocabulary, disclosure status values, source tier requirements, provenance fields, and validation requirements for the `Allergen_Disclosures` tab and the `Allergen_Flags` ingredient-row field.

This rule governs only the Evidence System — what may be recorded and how it must be attributed. It does not govern how the Knowledge System computes from allergen evidence (GP-RULE-015) or how allergen information is communicated to customers (GP-RULE-016).

### Canonical Allergen Vocabulary

GoldPan tracks the nine FDA-mandated major food allergens. Each has a canonical machine-readable slug:

| Canonical slug | Human label | Accepted aliases |
|---|---|---|
| `milk` | Milk / Dairy | `dairy` |
| `eggs` | Eggs | `egg` |
| `fish` | Fish | — |
| `shellfish` | Shellfish | — |
| `tree_nuts` | Tree Nuts | `tree nuts` |
| `peanuts` | Peanuts | `peanut` |
| `wheat` | Wheat | `gluten` (see note) |
| `soy` | Soy / Soybeans | `soybeans`, `soybean` |
| `sesame` | Sesame | — |

**On `gluten` vs `wheat`:** The FDA major allergen is wheat. Gluten is the protein. A non-wheat gluten source (rye, barley) does not satisfy a wheat allergen disclosure. If a source says "gluten-free" without specifying wheat, the canvasser must confirm intent before recording. The alias maps to `wheat` only when wheat is the confirmed source.

Special flags permitted on `Allergen_Flags` ingredient rows (not on `Allergen_Disclosures`):

| Flag | Meaning |
|---|---|
| `none` | No allergens identified for this ingredient |
| `unknown` | Allergen status not determinable at canvass time |

### Allergen_Disclosures — Disclosure Status Values

The `Allergen_Disclosures` tab records what restaurants explicitly communicate about allergen status. Three values are permitted:

| Status | Meaning | Evidence required |
|---|---|---|
| `contains` | Restaurant or allergen documentation confirms this allergen is present | Any tier source explicitly stating the allergen is present |
| `may_contain` | Restaurant explicitly disclosed cross-contact or shared-equipment risk | Restaurant must have explicitly stated the risk — not inferred from absence of a `free_from` claim |
| `free_from` | Restaurant explicitly stated this dish or menu is free from this allergen | Source tier and confidence requirements apply (see below) |

`free_from` is an internal canonical status. It is not consumer-facing language. Consumer presentation is governed by GP-RULE-016.

### Source Tier Requirements by Status

| Status | Confidence | Required source tier | Required `Source_Type` values |
|---|---|---|---|
| `contains` | `declared` or `verified` | Any eligible tier | Any canonical value from GP-RULE-010 |
| `may_contain` | `declared` or `verified` | Any eligible tier | Any canonical value from GP-RULE-010 |
| `free_from` | `verified` | Tier 1 only | `allergen_guide`, `nutrition_document`, `restaurant_confirmation` |
| `free_from` | `declared` | Tier 2 | `menu`, `website` |

A `free_from` row with a Tier 2 source may not be recorded with `verified` confidence. If a canvasser observes a restaurant stating "gluten-free" on their menu, the evidence is real and valuable — but it is `declared`, not `verified`. Only an official allergen guide, nutrition document, or direct written confirmation produces `verified` confidence.

### Allergen_Disclosures — Scope Values

| Scope | Meaning | `Dish_ID` field |
|---|---|---|
| `dish` | Evidence applies to this dish specifically | Required — must be a valid Dish_ID |
| `restaurant` | Restaurant-wide claim applies to all dishes at this restaurant | Blank |

A restaurant-scoped `may_contain` claim escalates every dish at that restaurant unless overridden by a dish-scoped `free_from` with `verified` confidence from a Tier 1 source. Restaurant-scoped claims are weaker than dish-scoped claims when they conflict on a specific dish.

### Allergen_Flags — Ingredient-Row Evidence

Each ingredient row in Ingredient Details may carry one or more canonical allergen slugs in the `Allergen_Flags` field. These represent the canvasser's documented observation of which allergens are present in that ingredient, based on the ingredient's known identity and the source it was acquired from.

`Allergen_Flags` are Evidence System records. They are not Knowledge System conclusions. A canvasser recording `milk` on a parmesan row is recording an observable property of that ingredient based on its disclosed identity — this is evidence capture, not a governed computation.

`none` and `unknown` are permitted on ingredient rows. They may not co-exist with other allergen slugs in the same `Allergen_Flags` value.

### Provenance Requirements

Every `Allergen_Disclosures` row must carry complete provenance (GP-RULE-011):

| Field | Requirement |
|---|---|
| `Source_Type` | Canonical provenance value from GP-RULE-010 hierarchy |
| `Source_Reference` | Specific URL, document name, or exchange description — not a category |
| `Source_Date` | ISO 8601 date evidence was obtained |
| `Scope` | `dish` or `restaurant` |

A row without complete provenance cannot be used as input to the Knowledge System.

### The One-Way Boundary

No Knowledge System conclusion may be recorded as evidence in the `Allergen_Disclosures` tab or in the `Allergen_Flags` column. Evidence flows into the Knowledge System; Knowledge System outputs flow to consumer-facing interfaces. The boundary is one-way in both directions.

Per `docs/GOLDPAN_PHILOSOPHY.md`: if it was computed by GoldPan's rules, it belongs in the Knowledge System, not the Evidence System.

### Validation Requirements

**`Allergen_Flags` (Ingredient Details):**
- All values must be canonical allergen slugs or `none` / `unknown`
- Multi-value fields: comma-separated, no spaces around commas
- `none` and `unknown` may not co-exist with other slugs in the same field

**`Allergen_Disclosures` tab:**
- `Allergen` must be a canonical allergen slug — not `none` or `unknown` (those are ingredient-row only)
- `Disclosure_Status` must be in `{contains, may_contain, free_from}`
- `free_from` with confidence `verified` requires `Source_Type` in `{allergen_guide, nutrition_document, restaurant_confirmation}`
- `Source_Type` must be a canonical provenance value from GP-RULE-010
- `Source_Date` must be present and parseable as ISO 8601
- `scope = dish` rows: `Dish_ID` must be present and exist in Goldpan Dish Level Data
- `scope = restaurant` rows: `Dish_ID` must be blank
- Duplicate rows (same `Dish_ID` + `Allergen` + `Disclosure_Status`) generate a validation warning

### Standard Limitation Language

> Allergen evidence recorded under GP-RULE-014 represents what the restaurant disclosed as of `Source_Date` via `Source_Type`. GoldPan records this evidence faithfully. It does not verify kitchen practices, preparation variations, or supply chain changes. Evidence may not reflect menu updates made after `Source_Date`.

### Example: Applies

A canvasser reads Emmy Squared's official allergen guide PDF. The guide explicitly lists a dish as containing dairy and wheat. The canvasser records two rows in `Allergen_Disclosures`: one for `milk` (`contains`, `allergen_guide`, Tier 1, `verified`, `scope = dish`) and one for `wheat` (`contains`, `allergen_guide`, Tier 1, `verified`, `scope = dish`). The canvasser also records a `free_from` row for `peanuts` because the guide explicitly confirms no peanuts. All three rows carry `Source_Reference` pointing to the PDF URL and `Source_Date` of the canvass date.

### Example: Does Not Apply

A canvasser notes that a dish's ingredient list does not include any wheat-containing ingredients. They record `free_from` for wheat in `Allergen_Disclosures`. This violates GP-RULE-014. The absence of wheat in the ingredient list is not a restaurant disclosure — it is the basis for a GoldPan Ingredient Analysis conclusion (GP-RULE-015). No `free_from` row may be created from ingredient analysis.

---

## GP-RULE-015 — Allergen Knowledge Rule

**Version:** 1.0  
**Last updated:** 2026-06-30  
**Layer:** Knowledge System  
**Depends on:** GP-RULE-001 (Material Evidence Rule), GP-RULE-002 (Disclosed Absence Rule), GP-RULE-003 (Undisclosed Ingredient Rule), GP-RULE-007 (Filter Evidence Dependency Rule), GP-RULE-014 (Allergen Evidence Rule)  
**See also:** `docs/ALLERGEN_ARCHITECTURE.md`, `docs/GOLDPAN_PHILOSOPHY.md`

### Purpose

Governs how GoldPan computes allergen-related conclusions from Evidence System inputs. Defines the GoldPan Ingredient Analysis filter family, evidence dependency requirements, confidence ceilings, corroboration handling, conflict handling, and required explanation fields.

This rule governs only the Knowledge System. It does not govern how allergen evidence is recorded (GP-RULE-014) or how conclusions are communicated to customers (GP-RULE-016).

### Governing Principle

> **The absence of identified ingredients is not evidence of allergen absence.**

GoldPan can observe that a disclosed ingredient list does not contain a specific allergen. It cannot conclude from that observation that the dish is free from that allergen. Cross-contact, compound ingredient sub-components, processing aids, preparation variations, and undisclosed ingredients all exist outside what a primary ingredient list captures.

This principle is non-negotiable. It applies to every allergen conclusion the Knowledge System computes and to every consumer-facing label that surfaces one.

### GoldPan Ingredient Analysis — Filter Family

GoldPan registers one derived filter per FDA allergen. All nine use the same engine, the same dependency type, and the same explanation schema as No Beef Identified and No Pork Identified:

| Filter name | Target allergen | Dependency type |
|---|---|---|
| No Wheat Ingredients Identified | `wheat` | `macro_dependent` |
| No Milk Ingredients Identified | `milk` | `macro_dependent` |
| No Egg Ingredients Identified | `eggs` | `macro_dependent` |
| No Soy Ingredients Identified | `soy` | `macro_dependent` |
| No Peanut Ingredients Identified | `peanuts` | `macro_dependent` |
| No Tree Nut Ingredients Identified | `tree_nuts` | `macro_dependent` |
| No Fish Ingredients Identified | `fish` | `macro_dependent` |
| No Shellfish Ingredients Identified | `shellfish` | `macro_dependent` |
| No Sesame Ingredients Identified | `sesame` | `macro_dependent` |

No new engine logic is required. These filters are registered in `FILTER_REGISTRY` exactly as No Beef Identified and No Pork Identified are registered.

### Engine Behavior

For each allergen filter applied to a dish:

- If any ingredient row carries the target allergen slug in `Allergen_Flags` → conclusion: `not_applicable` (the allergen IS identified; the "No X" filter does not apply)
- If no ingredient row carries the target allergen slug AND the materiality test passes (GP-RULE-001) → conclusion: "No [X] Ingredients Identified" (computed)
- If dependency not met (no macro-eligible ingredient rows per GP-RULE-007) → `unknown`

The materiality test (GP-RULE-001) applies: if the undisclosed portions of the ingredient list could plausibly contain the allergen, the test fails and the filter returns `unknown`.

### Confidence

All GoldPan Ingredient Analysis conclusions have a confidence ceiling of `inferred`. No Ingredient Analysis conclusion may be assigned `verified` or `declared` confidence regardless of source quality. These confidence levels are reserved for Restaurant Allergen Disclosures (GP-RULE-014), where the restaurant — not GoldPan — is making the claim.

Confidence is further subject to freshness degradation per GP-RULE-009. Staleness reduces confidence; it is never upgraded by corroboration.

### Corroboration

When a Restaurant Allergen Disclosure (Evidence System) and a GoldPan Ingredient Analysis conclusion (Knowledge System) point in the same direction for the same dish and allergen:

- The restaurant disclosure is the primary conclusion
- The Ingredient Analysis conclusion is surfaced as independent supporting evidence, explicitly labeled as GoldPan's analysis
- The systems remain structurally separate — this is not a confidence upgrade and does not merge conclusions
- Both limitation sets remain in full
- Consumer presentation is governed by GP-RULE-016

Corroboration is a communication signal, not a data merge.

### Conflicts

When the two systems produce contradictory signals for the same dish and allergen:

| Restaurant Disclosure | Ingredient Analysis | Resolution |
|---|---|---|
| `free_from` | Allergen found (not_applicable) | **Conflict — never auto-resolve.** Flag for human review. Serve `unknown` for this allergen pending resolution. Per GP-RULE-012 Principle 5: allergen conflicts require human review. |
| `contains` | No allergen found (computed) | **Conflict.** The disclosure takes precedence for allergen presence. Flag because ingredient analysis failed to identify an allergen that is disclosed as present. |
| `may_contain` | No allergen found (computed) | Not a conflict. Cross-contact risk exists that ingredient analysis cannot detect. Both conclusions are surfaced. |

Allergen conflicts must be logged in validation output and may not be silently resolved in favor of either source.

### Required Explanation Fields

Every Knowledge System allergen conclusion must carry a complete explanation (per GP-RULE-006):

| Field | Requirement |
|---|---|
| `conclusion` | The specific conclusion: "No [X] Ingredients Identified" or `not_applicable` or `unknown` |
| `evidence_used` | Which ingredient rows contributed, their `Allergen_Flags`, and the macro-eligible `Ingredient_Source` values |
| `confidence` | `inferred` (ceiling), subject to GP-RULE-009 degradation |
| `reasoning` | Cites GP-RULE-015 and the governing absence rule (GP-RULE-002) or dependency failure reason |
| `limitations` | Full standard limitations language from GP-RULE-016 — mandatory, non-waivable |
| `rule_ids` | Minimum: `[GP-RULE-001, GP-RULE-002, GP-RULE-007, GP-RULE-014, GP-RULE-015, GP-RULE-016]` |

A conclusion without a complete explanation is an architectural violation per GP-RULE-006.

### What This Rule Does Not Allow

- Computing a `free_from` or allergen-absence conclusion from ingredient analysis alone. Ingredient analysis produces "No [X] Ingredients Identified" — not "[X]-free."
- Assigning `verified` or `declared` confidence to any Ingredient Analysis conclusion.
- Auto-resolving a conflict between a Restaurant Disclosure and an Ingredient Analysis conclusion.
- Omitting the governing principle from the reasoning field of any computed conclusion.

### Standard Reasoning Language

*(Used in the `reasoning` field of computed Ingredient Analysis conclusions)*

> "No [X] allergen flags identified in the verified disclosed ingredient list for this dish. Per GP-RULE-002 (Disclosed Absence Rule), absence from the disclosed primary ingredient list is informative when disclosure is expected and the materiality test (GP-RULE-001) passes. Per the governing principle of GP-RULE-015: this conclusion reflects what the disclosed evidence supports. It is not a claim that the dish is [X]-free."

### Example: Applies

A dish has 6 verified ingredient rows sourced from `menu`. None carry `wheat` in `Allergen_Flags`. The materiality test passes — the undisclosed portions of the ingredient list would not plausibly include wheat for this type of dish. The engine concludes: "No Wheat Ingredients Identified." Confidence: `inferred`. The full GP-RULE-016 limitations are included. Rule IDs cited include GP-RULE-001, GP-RULE-002, GP-RULE-007, GP-RULE-014, GP-RULE-015, GP-RULE-016.

### Example: Does Not Apply

A dish has a Restaurant Allergen Disclosure with `free_from: wheat` (verified, from an allergen guide). The Knowledge System reads this disclosure. It does not re-derive it — the `free_from` status is Evidence System output, not a Knowledge System computation. The engine surfaces it to the consumer with appropriate attribution per GP-RULE-016. This rule does not govern that pathway.

---

## GP-RULE-016 — Allergen Communication Rule

**Version:** 1.0  
**Last updated:** 2026-06-30  
**Layer:** Communication  
**Depends on:** GP-RULE-006 (Derived Filter Explanation Rule), GP-RULE-014 (Allergen Evidence Rule), GP-RULE-015 (Allergen Knowledge Rule)  
**See also:** `docs/ALLERGEN_ARCHITECTURE.md`, `docs/GOLDPAN_PHILOSOPHY.md`

### Purpose

Governs how GoldPan presents allergen information to customers. Ensures GoldPan never overstates certainty, never conflates restaurant disclosures with GoldPan-derived conclusions, and always communicates appropriate limitations. This rule applies to all consumer-facing output surfaces — `dishes.json`, API responses, and UI.

The communication layer exists to enforce the Evidence/Knowledge distinction at the point of customer contact. A correct computation presented incorrectly violates GoldPan's transparency commitment just as surely as an incorrect computation would.

### Structural Separation Requirement

Restaurant Allergen Disclosures and GoldPan Ingredient Analysis conclusions must be structurally and visually distinct in all consumer-facing output. They may not appear under a shared heading, in a merged field, or in a format that implies they carry the same type of authority or the same meaning.

This separation is architectural, not stylistic. It reflects the fact that these are different types of claims made by different parties with different accountability.

### Consumer-Facing Label Standards

**Restaurant Allergen Disclosures** — labels reflect the source and confidence, not the internal `free_from` enum:

| Internal status | Confidence | Source | Consumer label |
|---|---|---|---|
| `free_from` | `verified` | `allergen_guide` | "Restaurant allergen guide: [allergen]-free" |
| `free_from` | `verified` | `nutrition_document` | "Restaurant nutrition document: [allergen]-free" |
| `free_from` | `verified` | `restaurant_confirmation` | "Restaurant confirmed: [allergen]-free" |
| `free_from` | `declared` | `menu` or `website` | "Restaurant disclosed: [allergen]-free" |
| `contains` | any | any | "Contains: [allergen]" |
| `may_contain` | any | any, `scope = dish` | "Cross-contact risk: [allergen] (restaurant-disclosed)" |
| `may_contain` | any | any, `scope = restaurant` | "Kitchen cross-contact risk: [allergen] (restaurant-disclosed)" |

The internal status value `free_from` must never appear in consumer output. Consumer labels reflect the source and confidence; they use the restaurant's own language wherever known.

**GoldPan Ingredient Analysis conclusions** — one fixed label:

> "No [allergen] ingredients identified from disclosed ingredients."

This label is fixed. It may not be shortened, softened, reworded, or made conditional in consumer output.

### Mandatory Limitations Language (Ingredient Analysis)

Every GoldPan Ingredient Analysis conclusion must display the following limitations in full on every consumer-facing output surface. This language is non-waivable:

> "No [X] Ingredients Identified" means the verified disclosed primary ingredient list for this dish does not contain [X] or [X]-derived ingredients as explicitly listed. This is not a claim that the dish is [X]-free. It does not address undisclosed compound ingredient components, micro ingredients, processing aids, cross-contact risk, shared equipment, preparation variations, or ingredients added or changed since last canvass. Diners with [X] allergies or intolerances must contact the restaurant directly before dining.

This language may not be omitted, shortened, paraphrased, or made conditional. Its presence is required regardless of confidence level, source quality, or corroboration.

### Restaurant Disclosure Limitation Language

Every Restaurant Allergen Disclosure must include the following limitation:

> Allergen information is disclosed by the restaurant. GoldPan records restaurant claims faithfully but cannot verify kitchen practices, preparation variations, supply chain changes, or menu updates made after the last canvass date. Diners with food allergies should contact the restaurant directly to confirm current allergen status before dining.

### Corroboration Display

When both systems produce compatible conclusions for the same allergen, the Restaurant Allergen Disclosure is the primary conclusion. The Ingredient Analysis conclusion is displayed as independent supporting evidence, explicitly labeled as GoldPan's analysis. Both limitation sets remain in full.

Example display:
> "Restaurant disclosed: gluten-free.  
> GoldPan ingredient analysis: No wheat ingredients identified from disclosed ingredients.  
> [Full Ingredient Analysis limitations]"

The restaurant claim is not elevated by corroboration. The Ingredient Analysis conclusion is not presented as confirmation. They are independent conclusions that happen to be compatible.

### Internal Confidence Values Are Not Consumer-Facing

The internal confidence model uses the terms `inferred`, `declared`, `verified`, and `unknown`. These values govern the engine, the validator, and the rules. They are never surfaced directly to consumers.

`inferred` is the accurate internal description of how a Knowledge System conclusion was reached — governed rules applied to disclosed evidence. But to a consumer, "inferred" reads as "guess," which understates what GoldPan actually did.

Consumer-facing surfaces must use translated language governed by this rule — the fixed label, the source-aware restaurant disclosure labels, and the limitations paragraph. The raw confidence token never appears in consumer output. When the product team implements allergen UI, they are implementing a translation from internal confidence tier to governed consumer language — not exposing a data field.

Future consumer-facing signals (badges, section headers, or trust indicators such as "GoldPan Analysis" or "Based on Disclosed Ingredients") should communicate the method, not the confidence token. The specific language is a product decision. The constraint is this rule: whatever language is used, it must not misrepresent the type of evidence or the certainty of the conclusion.

### What This Rule Prohibits

- Presenting an Ingredient Analysis conclusion using language that implies it is a restaurant disclosure (e.g., "This dish is gluten-free")
- Presenting a restaurant disclosure as GoldPan-verified
- Omitting or condensing the mandatory Ingredient Analysis limitations on any output surface
- Merging disclosure and analysis data into a single "allergen status" field in consumer output
- Displaying `free_from` as a consumer label
- Upgrading an Ingredient Analysis conclusion to `verified` or `declared` confidence in presentation
- Displaying corroboration in a way that implies the two conclusions are the same type of claim
- Surfacing the raw confidence token (`inferred`, `declared`, `verified`, `unknown`) directly in consumer output

### Relationship to GP-RULE-015

The mandatory limitations language defined in this rule is incorporated by reference in the `limitations` field of every GP-RULE-015 explanation object. Any implementation that cites GP-RULE-015 in a derived conclusion must also implement GP-RULE-016's communication requirements on every surface that renders that conclusion.

### Standard Limitation Language Reference

*(The full text of both limitation language blocks is defined above. Implementations must reproduce the full text — not a summary, not a link, not a conditional variant.)*

### Example: Applies

GoldPan computes "No Wheat Ingredients Identified" for a dish. The consumer-facing output displays: the fixed label, the evidence summary, and the full limitations paragraph in complete, unmodified form. The output is in a section clearly labeled as GoldPan ingredient analysis, separate from any restaurant disclosures for the same dish. The internal confidence value (`inferred`) does not appear in consumer output — the fixed label and limitations paragraph carry the appropriate epistemic weight for the consumer.

### Example: Does Not Apply — Violation

A developer displays "No wheat detected — likely gluten-free" in the UI. This violates GP-RULE-016 on three counts: it uses non-standard label language, it omits mandatory limitations, and it implies a certainty ("likely gluten-free") that exceeds what the evidence supports.

---

## Adding Rules to This Registry

New rules may be added when a recurring derived computation pattern requires documented governance. To add a rule:

1. Assign the next sequential Rule ID (GP-RULE-007, etc.)
2. Define all fields from the template above
3. Set Version = 1.0 and Last Updated = today
4. Add the rule to the Rule Index table at the top of this document
5. Reference the rule in any derived filter explanation that uses it

Rules may be updated (incrementing the version) but not deleted. Retired rules are marked with a **Deprecated** note and a reference to the rule that supersedes them.
