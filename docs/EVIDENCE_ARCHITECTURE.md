# GoldPan Evidence Architecture

**Status:** Active architectural reference  
**Last updated:** 2026-06-28

---

## Three-Layer Model

GoldPan's knowledge pipeline rests on three distinct architectural layers. Each has a single responsibility. Each asks a different question. No layer may be collapsed into another without creating the exact conflation problems the architecture was designed to prevent.

```
┌─────────────────────────────────────────────────┐
│           EVIDENCE ACQUISITION                  │
│   "Where did this evidence come from?"          │
│   Intake layer. Governs how evidence enters.    │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│           EVIDENCE QUALITY                      │
│   "Is this evidence sufficient to support       │
│    a conclusion?"                               │
│   Governed by GP-RULE-001 through GP-RULE-007   │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│           EVIDENCE FRESHNESS                    │
│   "Can GoldPan still rely on this evidence      │
│    today?"                                      │
│   Governed by GP-RULE-008 and GP-RULE-009       │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│           DERIVED KNOWLEDGE                     │
│   "What conclusions does the verified,          │
│    fresh evidence support?"                     │
│   Governed by the filter registry and engine    │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│           CUSTOMER EXPERIENCE                   │
│   Filters, confidence indicators, freshness     │
│   labels, limitation disclosures                │
└─────────────────────────────────────────────────┘
```

A conclusion only reaches customers after passing through all four upstream layers. Skipping or conflating layers produces either false confidence or unnecessary suppression of valid knowledge.

---

## Layer 1 — Evidence Acquisition

**Single responsibility:** Govern how new evidence enters the GoldPan database.

**The question this layer answers:** "Where did this evidence come from?"

This is the intake layer. It is not a health metric and not a freshness signal. Acquisition defines the recognized channels through which evidence enters, ensures each piece of evidence has a traceable provenance, and categorizes the acquisition event so downstream layers can assess quality and freshness appropriately.

### Current acquisition sources

| Source | Type | Provenance value |
|---|---|---|
| Restaurant website — live menu | Primary | `menu` |
| Menu PDF published by restaurant | Primary | `pdf` |
| Restaurant official website (non-menu pages) | Primary | `website` |
| Direct restaurant confirmation | Primary | `restaurant_confirmation` |
| Official allergen guide published by restaurant | Supporting | `allergen_guide` |
| Official nutrition document | Supporting | `nutrition_document` |
| Restaurant-answered customer question | Supporting | `restaurant_qa` |
| Restaurant correction of GoldPan record | Corrective | `restaurant_correction` |

### Future acquisition sources (planned)

| Source | Type |
|---|---|
| Menu API integration (restaurant's own API) | Primary |
| Third-party API (with restaurant verification) | Verified secondary |
| Supplier certification data | Certification |
| Third-party dietary certification body | Certification |
| Field canvasser observation (in-person) | Primary |

### What Acquisition is not

A restaurant correction is an **acquisition event** — new evidence is entering the system. Whether that correction is trustworthy is a Quality question. Whether it is still current is a Freshness question. Modeling it as a freshness event would conflate the intake of new evidence with the staleness of existing evidence.

A customer question answered by the restaurant is an **acquisition event** — it produces new evidence that enters through a recognized channel (`restaurant_qa`). It is not a recanvass event and does not update `Last_Canvassed`. It may update allergen data for a specific dish if the restaurant's answer is authoritative and verifiable.

Recanvassing is also an acquisition event — it produces new evidence from existing sources, or confirms that existing evidence remains accurate (`Menu_Changed = no`). This is why recanvassing belongs architecturally to Acquisition, even though its scheduling and status tracking live in the Freshness layer. The Freshness layer governs *when* recanvassing must occur. The Acquisition layer governs *what happens* when it does.

### Acquisition rules — now formalized

Evidence Quality has GP-RULE-001 through GP-RULE-007. Evidence Freshness has GP-RULE-008 and GP-RULE-009. Evidence Acquisition is governed by GP-RULE-010 through GP-RULE-012 (added 2026-06-28).

| Rule ID | Rule Name | What it governs |
|---|---|---|
| GP-RULE-010 | Source Authority Hierarchy Rule | Five trust tiers; authorized operations per tier; `MACRO_ELIGIBLE_SOURCES` definition |
| GP-RULE-011 | Evidence Provenance Rule | Required provenance fields; minimum viable provenance; full provenance target |
| GP-RULE-012 | Acquisition Conflict Resolution Rule | Five resolution principles; corrective acquisition process; no silent overwrites |

The informal governance that existed before formalization (`menu_verified: true` gate, `Ingredient_Source` field, partial GP-RULE-004 overlap) remains in place and is now understood as a partial implementation of GP-RULE-010 and GP-RULE-011. Full implementation requires the schema evolution work described in `docs/ARCHITECTURAL_HEALTH_REVIEW.md` Finding 3.

---

## Layer 2 — Evidence Quality

**Single responsibility:** Determine whether available evidence is sufficient to support a specific derived conclusion.

**The question this layer answers:** "Is this evidence sufficient to support this conclusion?"

Evidence that enters through the Acquisition layer is not automatically trustworthy or sufficient. Quality assessment applies the materiality test, verifies that the evidence type matches the filter's dependency requirements, and ensures that reasoning from absence is only performed when absence is informative.

### Governing rules

| Rule ID | Rule Name | Role in Quality |
|---|---|---|
| GP-RULE-001 | Material Evidence Rule | Core sufficiency test: could missing evidence change this conclusion? |
| GP-RULE-002 | Disclosed Absence Rule | When is absent evidence informative? |
| GP-RULE-003 | Undisclosed Ingredient Rule | When is absent evidence NOT informative? |
| GP-RULE-004 | Supporting Documents Rule | What additional evidence can strengthen a conclusion? |
| GP-RULE-005 | No Unsupported Inference Rule | Hard prohibition on inference and assumption |
| GP-RULE-006 | Derived Filter Explanation Rule | Every conclusion must be explainable |
| GP-RULE-007 | Filter Evidence Dependency Rule | Each filter declares what type of evidence it requires |

### The bridge between Acquisition and Quality

Acquisition provenance is the key input Quality uses to assess trustworthiness. `Ingredient_Source = "menu"` tells Quality that the ingredient was verified from a live menu — which satisfies the `macro_dependent` evidence requirement in GP-RULE-007. `Ingredient_Source = "unknown"` tells Quality that provenance is unestablished — which causes GP-RULE-007's dependency check to fail.

This is why `Ingredient_Source` is architecturally an Acquisition field (it records how the evidence entered) but has direct Quality consequences (it determines whether the evidence satisfies a dependency). The field belongs to Acquisition; its Quality implications are specified in GP-RULE-007.

`VERIFIED_SOURCES = {"menu", "pdf", "website", "restaurant_confirmation"}` in the engine is the explicit bridge: it maps Acquisition provenance values to the Quality-layer concept of "verified." This constant should be understood as the Quality filter on Acquisition sources — sources inside this set satisfy macro_dependent quality requirements; sources outside it do not.

---

## Layer 3 — Evidence Freshness

**Single responsibility:** Determine whether evidence that was verified at acquisition time is still connected to the current real-world restaurant menu.

**The question this layer answers:** "Can GoldPan still rely on this evidence today?"

Freshness does not re-evaluate evidence quality. A verified ingredient row does not become lower quality because time has passed — it was accurately documented at canvass time. Freshness asks whether the real world has changed since the evidence was collected.

A dish can have high-quality, verified evidence and still be stale. A dish can be freshly canvassed and still have low-quality evidence. Freshness and quality are independent.

### Governing rules

| Rule ID | Rule Name | Role in Freshness |
|---|---|---|
| GP-RULE-008 | Data Freshness Rule | Establishes that freshness is required alongside quality; defines Recanvass_Status semantics |
| GP-RULE-009 | Stale Evidence Confidence Degradation Rule | Maps Recanvass_Status to confidence outcomes |

### Key distinction: Recanvassing vs. new acquisition

Recanvassing a restaurant that is `overdue` is a Freshness-layer concern — the Freshness layer is signaling that the existing evidence needs external validation. But when the canvasser goes and performs the recanvass, they are performing an Acquisition-layer action: collecting new evidence (or confirming that existing evidence is still current). The Freshness layer tracks the obligation; the Acquisition layer fulfills it.

This means `Last_Canvassed` is a Freshness tracking field, but the staging file produced by the recanvass is an Acquisition artifact. Both are required for the cycle to be complete.

---

## Layer 4 — Derived Knowledge

**Single responsibility:** Compute conclusions that verified, fresh evidence reliably supports, with full explainability.

**The question this layer answers:** "What does the evidence tell us about this dish?"

The Rules Engine only computes conclusions after all three upstream layers have been satisfied:
1. Acquisition has established provenance
2. Quality has confirmed sufficiency
3. Freshness has confirmed currency

If any layer fails, the appropriate response is documented Unknown — not a suppressed result, not a blank, not a guess. A documented Unknown is honest and traceable. An undocumented blank is neither.

The engine's three-gate sequence enforces this:
```
Gate 0 — Freshness:     check Recanvass_Status (GP-RULE-008)
Gate 1 — Dependency:    check dependency type (GP-RULE-007)
Gate 2 — Materiality:   apply materiality test (GP-RULE-001)
Compute:                run filter logic (filter registry)
Explain:                produce four-part explanation (GP-RULE-006)
```

---

## Layer 5 — Customer Experience

**Single responsibility:** Surface derived knowledge in a way that is honest about evidence quality, freshness, and the boundaries of each conclusion.

**What customers should see:**

- Derived filter results with appropriate confidence indicators
- "Last verified: [date]" for each restaurant's data
- Honest limitation language — "No Beef Identified" is not "Beef-Free"
- Suppressed conclusions replaced with "Verification in progress" (not blank, not hidden)
- A public-facing explanation of what GoldPan verifies and what it does not

Customer experience is the delivery layer. Its outputs are only as trustworthy as what the upstream layers produced. No customer-facing feature should present a conclusion whose layer history cannot be traced.

---

## Implications for Existing Architecture

### What needs recategorization

**`Ingredient_Source` field:**  
Currently documented in `SCHEMA_AUDIT.md` as a data provenance field. It should be understood as an Acquisition provenance field — it records how the evidence entered the system. Its Quality implications are derived (via VERIFIED_SOURCES), not inherent to the field itself.

**GP-RULE-004 (Supporting Documents Rule):**  
This rule partially governs Acquisition (what sources may enter as supporting evidence) and partially governs Quality (what conclusions those sources can support). When Acquisition rules are formally defined, GP-RULE-004 should be reviewed and potentially split: one acquisition rule defining the source authority hierarchy, and the existing quality rule governing what conclusions supporting sources can strengthen.

**Restaurant confirmations and customer Q&A:**  
Previously treated as freshness signals or verification events. Per this architecture, they are Acquisition events. A restaurant confirming an allergen is entering new evidence. A restaurant answering a customer's question is entering new evidence. These should be modeled in the Acquisition layer with their own provenance type (`restaurant_confirmation`, `restaurant_qa`) and subject to acquisition-layer conflict resolution rules when they contradict existing data.

**`recanvass_report.md` files:**  
A recanvass report documents an Acquisition event (what evidence was collected or re-confirmed) but is stored and tracked by the Freshness layer (it updates `Last_Canvassed` and `Recanvass_Status`). Both are correct — the report spans layers because recanvassing spans layers.

### What is cleanly separated

| Concept | Layer |
|---|---|
| `Ingredient_Source` values | Acquisition |
| `VERIFIED_SOURCES` constant | Acquisition → Quality bridge |
| `Last_Canvassed`, `Recanvass_Status` | Freshness |
| Materiality test | Quality |
| Dependency types | Quality |
| Derived filter conclusions | Derived Knowledge |
| Confidence indicators | Customer Experience |
| `menu_verified: true` gate | Acquisition |
| Staging file production | Acquisition |
| Backfill enrichment | Quality (filling in what verified sources support) |
| `compute_derived_filters.py` | Derived Knowledge |
| `fetch_dishes.py` output | Customer Experience delivery |

---

## Acquisition Layer — Rule Summary

GP-RULE-010 through GP-RULE-012 formally govern the Acquisition layer. All three evidence layers now have complete rule coverage.

| Layer | Rules | Status |
|---|---|---|
| Acquisition | GP-RULE-010, GP-RULE-011, GP-RULE-012 | Formalized 2026-06-28 |
| Quality | GP-RULE-001 through GP-RULE-007 | Active |
| Freshness | GP-RULE-008, GP-RULE-009 | Active |

**Remaining implementation gap:** Full provenance at the ingredient level (`source_reference`, `acquired_date`, `scope` per ingredient row) is not yet captured in the schema. GP-RULE-011 defines this as the target state and specifies minimum viable provenance for the current implementation. The schema evolution work is tracked in `docs/ARCHITECTURAL_HEALTH_REVIEW.md` Finding 3 and will require new columns in Ingredient Details.

**VERIFIED_SOURCES → MACRO_ELIGIBLE_SOURCES:** The anonymous engine constant `VERIFIED_SOURCES` in `derived/engine.py` is superseded by `MACRO_ELIGIBLE_SOURCES` as defined in GP-RULE-010. The constant must be moved to `schema.py` and imported by the engine. Until migration is complete, the two must be kept in sync.
