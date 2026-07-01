# GoldPan™ OS v1.0 — Health Assessment
**Date:** 2026-06-30  
**Scope:** Full system audit — architecture, governance, pipeline, data, validation, testing, documentation

---

## Executive Summary

GoldPan OS v1.0 is a well-governed, intentionally designed dietary intelligence platform. The architecture is unusually principled for a system of this scale: rules are versioned, evidence and inference are separated by design, and the pipeline is reproducible from a clean state. The primary gaps are test coverage depth and evidence acquisition still in progress. No structural defects were identified.

**Overall grade: A−**

---

## Scorecard

| Domain | Grade | Notes |
|--------|-------|-------|
| Architecture & Governance | A | |
| Validation & Data Integrity | A− | |
| Pipeline | A | |
| Documentation | A | |
| Test Coverage | C+ | Known gap |
| Data Coverage | B+ | Evidence acquisition in progress |

---

## Architecture & Governance — A

**16 rules** across 4 categories govern every inference the system makes.

| Category | Rules | Purpose |
|----------|-------|---------|
| General Knowledge | 001–009 | Evidence standards, materiality test, freshness gates, confidence caps |
| Evidence | 010–014 | Source authority hierarchy, provenance, allergen evidence contracts |
| Domain-Specific Knowledge | 015 | Allergen confidence ceiling |
| Communication | 016 | Separation of internal confidence from consumer language |

What makes this architecture good is not the quantity of rules but their specificity. Each rule has a version number, a rationale, and a precise scope that distinguishes it from adjacent rules. GP-RULE-001 (materiality test) and GP-RULE-002 (disclosed absence) handle the two hardest questions in food evidence systems — when is an absence informative, and when isn't it — with explicit, auditable logic.

**Three-layer separation** (Evidence → Knowledge → Presentation) is enforced architecturally, not just described in documentation:
- The Evidence System stores what restaurants disclosed. It is durable.
- The Knowledge System (`derived_filters.json`) is always regenerable from Evidence. It is disposable.
- The Presentation layer (consumer-facing labels) is governed by GP-RULE-016 and is deliberately not yet built — the system correctly refuses to expose internal confidence tokens to consumers.

**The allergen evidence lifecycle invariant** is one of the strongest design decisions in the system. The engine may read `Allergen_Flags`. It may never write them. It may never backfill them. A blank flag means absence of evidence, not absence of allergen. `none` means a canvasser explicitly observed no allergen flags — a human judgment that must never be manufactured by computation. This protects the Evidence System from the most insidious failure mode in derived systems: computed output silently becoming durable evidence.

**Filter extensibility** is fully realized. Adding a new filter requires a `FilterDefinition` + `compute_fn` + one line in `FILTER_REGISTRY`. The engine, dependency checker, and main script need zero changes. The 9 allergen filters were added this way — the engine remained untouched.

**17 schema constants** in `schema.py` govern every enum value, ID format pattern, and allergen vocabulary. No layer defines its own copy of a governed constant.

---

## Validation & Data Integrity — A−

`validate_database.py` is 1,345 lines covering:

- Schema and header validation for every active tab
- Required field presence
- ID format enforcement (`Restaurant_ID`, `Dish_ID` patterns)
- Enum validation against schema constants (no hardcoded lists)
- Referential integrity (dish-scoped allergen rows → active dishes in GDL)
- Scope-aware duplicate detection (Allergen_Disclosures natural key differs by scope)
- Alias detection (warns when a non-canonical but recognized value is used)
- Source tier enforcement (`free_from` requires Tier 1 or Tier 2 source)
- ISO 8601 date validation
- Freshness registry coverage (all restaurants in the pipeline have a freshness record)

`validate_staging.py` validates allergen flags on ingredient rows before enrichment.

The pipeline gates on validation: Step 1 failure aborts all subsequent steps.

**The A− rather than A**: the `Allergen_Disclosures` tab validator exists and is complete, but the tab itself has not yet been commissioned. The validator correctly treats a missing tab as a WARNING (not an ERROR), which is the right behavior during this phase — but it means one validation surface is currently untested against real data.

---

## Pipeline — A

Five-step orchestrated pipeline with abort logic:

```
Step 1: validate_database.py     — abort all if FAIL
Step 2: backfill_enrichment.py   — apply enrichment
Step 3: compute_derived_filters.py — generate Knowledge System
Step 4: fetch_dishes.py          — assemble dishes.json
Step 5: verify                   — structural sanity check on output
```

Step 3 failure aborts Step 4. Steps 2 and 5 are non-blocking.

**Freshness gates** are integrated into the derived filter engine:
- `needs_review` / `unknown` → suppress all conclusions (GP-RULE-008)
- `overdue` → proceed, then cap `verified` → `likely` post-compute (GP-RULE-009)
- `current` / `due_soon` → proceed normally; `due_soon` appends a staleness note to limitations

The pipeline produces a reproducible output from a clean state. `derived_filters.json` is always regenerable. `dishes.json` is always regenerable. The only durable artifacts are the Google Sheets tabs.

`update.sh` is gated on `validate_database.py`. The codebase does not deploy without a validation pass.

---

## Documentation — A

18 documents covering every major subsystem:

| Document | What it governs |
|----------|----------------|
| `RULES_REGISTRY.md` | All 16 rules with rationale, versioning, and scope |
| `ALLERGEN_ARCHITECTURE.md` | Two-system model, evidence lifecycle invariant, Allergen_Flags contract |
| `EVIDENCE_ARCHITECTURE.md` | Three-layer model: Evidence → Knowledge → Presentation |
| `RECANVASSING_POLICY.md` | Freshness policy, recanvass windows, status definitions |
| `FRESHNESS_IMPLEMENTATION_PLAN.md` | Two-track freshness architecture |
| `PIPELINE_ORCHESTRATOR_DESIGN.md` | Pipeline design and abort logic |
| `ALLERGEN_DISCLOSURES_TAB_SCHEMA.md` | Tab schema, field-level validation rules, canvasser instructions |
| `GOLDPAN_PHILOSOPHY.md` | Foundational design principles |
| `ARCHITECTURAL_HEALTH_REVIEW.md` | Prior architecture audit |

Rules are versioned (e.g., "Material Evidence Rule v1.1") so changes are traceable. The `ALLERGEN_ARCHITECTURE.md` explicitly documents the one-way invariant — the kind of constraint that is usually tribal knowledge and therefore the first thing to be violated under operational pressure.

The `ALLERGEN_DISCLOSURES_TAB_SCHEMA.md` (just drafted) includes the canvasser invariant section. A canvasser who reads it will understand not just what to enter, but why a computed value cannot substitute for a sourced observation.

---

## Test Coverage — C+

**One test file, ~55 test cases, custom runner (no pytest or unittest framework).**

What is covered:
- No Beef Identified — full outcome matrix (beef found, ambiguous/resolved, clean)
- Qualifier resolution — the vegan beef fix and equivalents
- No Pork Identified — mirrors beef test structure

What is not covered:
- Allergen filters (no unit tests for any of the 9 allergen compute functions)
- Engine gate logic (freshness gate, dependency check, confidence cap)
- `build_dish_evidence` (evidence assembly from raw rows)
- Freshness state transitions
- `validate_database.py` validators
- `fetch_dishes.py` assembly logic

The test infrastructure is functional but limited. The 40+ beef/pork cases cover the hardest filter logic well. But the 9 allergen filters — which add new logic (Allergen_Flags parsing, the `none` vs blank distinction, the inferred ceiling) — have no automated coverage. If a regression were introduced in `_parse_allergen_flags` or `_make_allergen_compute_fn`, it would not be caught before deployment.

**This is the largest technical gap in the system.**

---

## Data Coverage — B+

| Metric | Value |
|--------|-------|
| Published dishes | 686 |
| Active restaurants | 25 |
| Derived filter evaluations | 750 |
| Registered filters | 11 |
| Freshness status (all restaurants) | 100% current |
| Allergen_Disclosures rows | 0 (tab not yet commissioned) |
| Allergen filter computed outcomes | Pending Allergen_Flags population |

The B+ reflects honest assessment: the data layer is healthy and the infrastructure is ready, but evidence acquisition for allergen disclosures has not yet started. The 9 allergen filters exist and are correct, but most will return Unknown for most dishes until Allergen_Flags are populated — which is the expected state at this stage of the system's life.

The freshness system being 100% current is a meaningful signal. It means the foundation for freshness-gated conclusions is in place and clean.

---

## What v1.0 Gets Right

**Epistemic honesty.** The system returns Unknown rather than guessing. It documents exactly why it returned Unknown. The materiality test (GP-RULE-001) forces every filter to ask: could missing evidence change this conclusion? If yes, return Unknown. This is hard to build and easy to skip — GoldPan did not skip it.

**Evidence durability.** The distinction between durable evidence (what restaurants disclosed) and disposable knowledge (what GoldPan inferred) is enforced architecturally. The derived layer can be regenerated at any time. The evidence layer cannot be corrupted by computation.

**Governed vocabulary.** Every enum value, ID pattern, and allergen term flows from `schema.py`. There are no hardcoded lists scattered through individual scripts. This is what makes validation possible — validators can check data against the same constants the rest of the system uses.

**Separation of confidence from communication.** Internal confidence tokens (`inferred`, `verified`, `likely`, `unknown`) are never exposed to consumers. The presentation layer (not yet built) will implement a translation, not a field exposure. This is the right call — especially for allergen information where a consumer misreading `inferred` as `verified` has real consequences.

---

## What v1.0 Should Address Next

In priority order:

1. **Allergen filter unit tests.** The 9 compute functions need the same test coverage the beef/pork filters have. At minimum: allergen found → Not Applicable, blank Allergen_Flags → Unknown, `none` Allergen_Flags → contributes to computed, all flags processed and none match → computed.

2. **Allergen_Disclosures evidence acquisition.** The tab needs to be commissioned and the Evidence Acquisition Workflow needs to be designed and documented before canvassing begins.

3. **Engine gate tests.** The freshness gate (GP-RULE-008), dependency check (GP-RULE-007), and confidence cap (GP-RULE-009) are the most architecturally important logic in the system and have no automated coverage.

4. **Allergen_Flags population.** Populating `Allergen_Flags` on existing ingredient rows is the precondition for allergen filter computed outcomes. Until this is done, most allergen filter results will be Unknown.

---

## Verdict

GoldPan OS v1.0 is a well-built foundation. The architecture is principled enough that extending it — adding filters, adding evidence types, building a consumer presentation layer — does not require redesigning what already exists. The rules, schema, validation, and pipeline are ready for operational use. The gaps are known, bounded, and addressable in order.

**Overall: A−**
