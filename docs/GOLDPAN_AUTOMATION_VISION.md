# GoldPan Automation Vision

*Living architectural reference. Update as the platform evolves.*

---

## Mission

GoldPan should eventually become an autonomous restaurant transparency platform capable of discovering, validating, organizing, and maintaining high-quality menu information at scale.

The goal is not simply automation.
**The goal is trusted automation.**

Every automation should increase confidence in the database, not reduce it.

---

## Engineering Philosophy

Every automation should follow these principles:

- **Verify before writing.**
- **Stage before upsert.**
- **Validate before deployment.**
- **Never guess when authoritative data exists.**
- **Search the system before asking.**
- **Preserve database integrity above speed.**
- **Produce clear reports** explaining what was discovered, changed, and validated.

---

## Permanent Engineering Principles

These principles were established through operational experience and are binding on all future pipeline work. See `docs/SCHEMA_AUDIT.md` and `docs/ARCHITECTURAL_HEALTH_REVIEW.md` for the findings that produced them.

### 1. One Field, One Meaning

Every field in the GoldPan data model has exactly one canonical meaning. A field must never be reused to store a semantically different concept simply because the data type fits.

*Example violation (fixed):* `Ingredient_Source` was storing food ingredient origin ("house-made", "grass-fed") instead of its canonical meaning — how GoldPan obtained the information (menu, pdf, website, restaurant confirmation).

*Implication:* When a new concept needs to be recorded, define a new field. Do not overload an existing one. See `docs/SCHEMA_AUDIT.md` for the current field inventory and known violations.

### 2. Two-Level Write Verification

Every write operation must have two independent verification steps before reporting success.

**Level 1 — Data Verification:** Confirm that the intended values were actually written. Re-read the targeted cells after writing. Report rows targeted, rows updated, values before, values after. Report FAIL if any expected value is not present.

**Level 2 — Behavioral Verification:** Confirm that downstream system behavior changed as expected. Check derived filter counts, enrichment counts, or validation counts after the write. If the write was correct, observable behavior should change. If behavior is unchanged, investigate before declaring success.

*Implication:* A script must not print "Done" or "✓" until both levels pass.

### 3. Never Trust Existing Values Blindly

A non-blank value is not automatically a correct value. Validation must distinguish between:

- **Blank** — field has not been processed
- **Valid** — field contains a verified, schema-compliant value
- **Invalid** — field contains a value that violates the schema or canonical enum
- **Deprecated** — field contains a value from a superseded schema version
- **Semantically incorrect** — field contains a value that is syntactically valid but conceptually wrong (e.g., food origin stored in a data provenance field)

Repair scripts must be capable of correcting semantically incorrect values, not only blank ones. The "never overwrite" rule applies to *verified correct values*, not to all non-blank values.

### 4. Every Derived Result Must Be Explainable

Every derived filter must produce a four-part explanation: Conclusion, Evidence Used, Reasoning (citing a named Rule ID), and Limitations. This explanation is architectural — it exists whether or not it is displayed to the customer. See `docs/RULES_REGISTRY.md`.

### 5. The Rules Registry Is the Source of Truth

Business rules live in `docs/RULES_REGISTRY.md`. Python implements those rules — it does not invent new ones. When logic changes, update the Rules Registry first. Then update the implementation to match. The Rules Registry version is cited in every derived conclusion.

### 6. Filter Logic Must Remain Dependency-Driven

The evaluation engine branches on dependency type (`macro_dependent`, `mixed_dependent`, `micro_dependent`, `restaurant_claim_dependent`) — never on filter identity. Adding a new filter requires only a new `FilterDefinition` and `compute_fn`. No engine changes. See `derived/engine.py` and `docs/RULES_REGISTRY.md` GP-RULE-007.

### 7. Evidence Before Convenience

GoldPan computes every conclusion that available verified evidence reliably supports. It does not compute conclusions where missing evidence could materially change the result. `Unknown` is a valid, honest result. False certainty is a data integrity violation. See `docs/RULES_REGISTRY.md` GP-RULE-001.

### 8. The Pipeline Must Explain and Validate Itself

Every pipeline stage — from onboarding to derived filters — should produce a self-documenting report explaining what was found, what changed, and whether the outcome matched expectations. Manual inspection should not be required to determine whether a pipeline run succeeded. See `docs/BACKFILL_RELIABILITY_REPORT.md` for the findings that established this requirement.

---

## Foundational Principles

### Source of Truth

Every meaningful piece of data in GoldPan should have an identifiable authoritative source. Whenever practical, record where the data came from and when it was last verified. Source provenance is a first-class concept throughout the platform.

*Implication:* Data without a traceable source is a candidate for flagging, not a candidate for trust.

### Verified Richness

Data quality means verified richness, not artificial completeness. A blank field is not a failure — it is an honest acknowledgment that the source did not support that value. A field filled by inference or guessing is a data integrity violation.

Enrichment fields (Cut_Type, Preparation, Ingredient_Type, Component_Role, Allergen_Flags, Ingredient_Source) must only be populated from verified sources: live menu, official allergen/nutrition PDFs, restaurant website, or direct restaurant confirmation.

Blank means unprocessed — it is a completeness gap, not an acceptable final state. After a row has been reviewed, every enrichment field must contain a verified value, `None` (not applicable), `Unknown` (reviewed but undetermined), or `N/A` (field doesn't apply). Do not leave fields blank after review just to avoid guessing — the right reviewed response to uncertainty is `Unknown`, not empty.

*Implication:* A row with `Unknown` across its enrichment fields is more trustworthy than a blank row, because it records that sources were examined. See `docs/INGREDIENT_ENRICHMENT_RULES.md`.

*Implication:* The system should never fill fields by inference. Completeness gaps (blanks) are tracked separately via `analyze_enrichment.py` and reported as non-blocking metrics — not validation errors.

### Evidence-Dependent Computing

GoldPan computes conclusions when available verified evidence reliably supports them — not only when evidence is complete. The governing question is not "Is the ingredient list complete?" It is: **"Could missing evidence materially change this conclusion?"**

If no plausible gap in the verified data would flip the result, GoldPan computes. If missing evidence could reasonably change the outcome, GoldPan returns `Unknown` and documents what additional evidence is needed.

This principle applies across all derived filters. Filters are not created equal in what they require. A filter that concludes "No Beef Identified" depends on primary ingredient disclosure. A filter that concludes "Certified Gluten-Free" depends on an explicit restaurant claim. A filter that concludes preparation method depends on menu-stated preparation detail. Each filter declares its evidence dependency type; the evaluation engine checks it.

**Reasoning from absence is governed by disclosure norms, not ingredient scale.** Primary ingredients are expected to be disclosed — their absence from a verified list is informative. Micro ingredients (processing aids, trace additives, compound sub-components) are routinely not disclosed even when present — their absence from a list is not informative. GoldPan may reason from absence only where absence is informative. Explicitly disclosed micro ingredients are always valid verified evidence regardless of scale.

*Implication:* Every derived filter must declare its evidence dependency type (`macro_dependent`, `mixed_dependent`, `micro_dependent`, or `restaurant_claim_dependent`). The evaluation engine uses this declaration to decide whether to compute or return Unknown. No special-case logic per filter. See `docs/RULES_REGISTRY.md` GP-RULE-001 and GP-RULE-007.

### Explainable Conclusions

GoldPan does not only compute derived conclusions — it must always be able to explain them. Every derived filter (No Beef Identified, Vegetarian, High Transparency, etc.) is accompanied by a four-part explanation: Conclusion, Evidence Used, Reasoning, and Limitations.

The reasoning field cites a specific named rule from the GoldPan Rules Registry (`docs/RULES_REGISTRY.md`). No derived conclusion may reference vague or implicit logic. This explanation exists whether or not it is displayed to the customer — it is the audit trail.

*Implication:* A derived conclusion without a complete explanation object is an architectural violation. See `docs/RULES_REGISTRY.md` for the full rules and `docs/DERIVED_FILTER_EXPLANATION_RULE.md` (forthcoming) for the explanation schema.

### System First

Before asking a human to answer a factual question, exhaust the system first. Search the database, documentation, staging files, generated data, registry, and codebase. Human input should be reserved for ambiguity, missing evidence, or business decisions — not because the system didn't investigate thoroughly.

*Implication:* If the answer exists somewhere in the system, the system should find it.

---

## Near-Term Goal: Repeatable Onboarding Pipeline

The first milestone is a repeatable pipeline where the inputs are:

- Restaurant name
- Restaurant website

And GoldPan can automatically:

1. **Verify** official menu sources.
2. **Audit** all available official sources.
3. **Extract** the current live menu.
4. **Generate** staging data.
5. **Enrich** dishes using official nutrition/allergen resources.
6. **Validate** all data.
7. **Produce** a dry-run report.
8. **Wait** for approval.
9. **Upsert** into the database.
10. **Build** the application.
11. **Produce** a Database Health Report.

This pipeline is also the architectural foundation for the long-term goal. If it is built correctly, autonomous market canvassing is this pipeline running at scale.

---

## Long-Term Goal: Autonomous Market Intelligence

Eventually GoldPan should be capable of intelligently canvassing an entire market:

- Discover restaurants that meet defined criteria.
- Locate official menu sources.
- Monitor menu changes.
- Detect new and removed dishes.
- Refresh transparency information.
- Produce candidate restaurants for onboarding.
- Recommend priorities based on coverage and customer value.

The system should **investigate first, validate second, and ask for human decisions only when business judgment is required.**

---

## Key Architectural Decisions

These decisions should be made explicitly and early, as they underpin everything above.

### Staging Layer
`dishes.json` and `restaurants.json` are currently the live database. A proper staging/diff layer is needed so the pipeline can produce "what would change" before anything is written. No write should be the first action the system takes.

### Source Provenance
Every data point should carry metadata: which URL it came from, when it was retrieved, and what confidence level was assigned. This is foundational for both validation and long-term change monitoring.

### Confidence Scoring
As the system becomes more autonomous, each data point needs a confidence signal. Human review should be focused on low-confidence items, not routine operations.

### Human Judgment Layer
The system makes every factual determination it can. It surfaces to a human only when:
- A business decision is required (e.g., is this restaurant worth onboarding?)
- Evidence is genuinely missing or ambiguous
- Confidence falls below a defined threshold

---

## Summary

The objective is to build a system that becomes more reliable and more autonomous over time while remaining trustworthy. Reliability and autonomy are not in tension with trust — they are built on it.

**Trusted automation built on verification, validation, traceability, and repeatable systems.**
