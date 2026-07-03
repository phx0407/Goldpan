# GoldPan OS Architecture
**Version:** 1.0  
**Date:** 2026-07-03  
**Status:** Governing — all subsystem design decisions are subordinate to this document

---

## The Architectural Principle

> **Intake captures facts. Governance determines what those facts mean. Ask GoldPan™ explains what Governance concluded.**

GoldPan is composed of three operating systems with hard boundaries between them. Each OS owns a distinct responsibility. No OS may perform the work of another. When a subsystem or feature is being designed, the first question is always: **which OS does this belong to?**

---

## The Three Operating Systems

### Intake OS
**Responsibility: Collect rich, structured, evidence-backed facts about restaurants.**

The Intake OS answers questions about what was observed:
- What did the restaurant explicitly disclose?
- What dishes exist, as the restaurant named them?
- What ingredients were stated on the source?
- What preparation methods were described?
- What allergen information was provided, and in what form?
- What substitutions or modifications were disclosed?
- Where did each piece of information come from?
- When was it collected, and by whom?

The Intake OS produces a structured, sourced, provenance-tracked body of evidence. It does not evaluate that evidence. It does not draw dietary conclusions from it. It does not determine what filters apply to it. Its job is to maximize the richness, accuracy, and traceability of every fact that enters GoldPan.

**The Intake OS boundary:** The moment any subsystem asks "what does this evidence *mean* for a user's dietary needs?" it has crossed into Governance territory.

### Governance OS
**Responsibility: Evaluate evidence and determine what conclusions GoldPan can legitimately draw.**

The Governance OS answers questions about what the evidence supports:
- Given this evidence, what dietary conclusions are warranted?
- What remains unknown because the evidence is incomplete?
- What confidence level applies to each conclusion?
- Which GoldPan filters can be legitimately derived from the available evidence?
- Which conclusions must be withheld because the evidence is insufficient?
- What rules govern the derivation of each filter?
- Where does evidence fall short of the standard required for a conclusion?

The Governance OS is the single authority for dietary reasoning in GoldPan. It applies the Rules Registry, the confidence framework, and the derivation engine to the evidence Intake has collected. It determines what GoldPan knows, what GoldPan doesn't know, and what GoldPan can honestly say to a user.

**The Governance OS boundary:** The moment any subsystem asks "what new facts can we obtain from the restaurant?" it has crossed into Intake territory. Governance reasons over evidence; it does not collect it.

### Ask GoldPan™
**Responsibility: Explain GoldPan's conclusions to users in language they can act on.**

Ask GoldPan™ answers questions about how to communicate what GoldPan knows:
- What conclusion did Governance reach for this dish and this filter?
- How should that conclusion be explained to a user who asked about it?
- What uncertainty or qualification should accompany the explanation?
- How should `unknown` conclusions be communicated without misleading the user?
- What is the evidence basis for the explanation, in plain language?

Ask GoldPan™ does not collect evidence (Intake) and does not make dietary decisions (Governance). It translates Governance's conclusions into responses a user can understand and trust. When it references evidence, it is presenting what Governance evaluated — not forming new conclusions.

---

## Hard Boundaries

These boundaries are architectural constraints, not preferences. Violating them introduces one or more of the following failure modes:

**If Intake makes dietary conclusions:**
- Governance logic gets duplicated in the evidence collection layer
- The same evidence may produce different conclusions depending on which canvasser did the intake
- Governance can no longer be the single authority — it shares that authority with every canvasser who made an inference during evidence entry
- Evidence and conclusion become entangled, making it impossible to update reasoning rules without re-canvassing restaurants

**If Governance collects evidence:**
- The rules layer becomes a data collection layer, which undermines its integrity as a reasoning system
- Governance conclusions become dependent on the quality of ad hoc evidence gathering, rather than on structured Intake evidence
- The confirmation process — a core Intake function — loses its formal structure

**If Ask GoldPan™ reasons independently:**
- The AI explanation layer produces conclusions that bypass Governance's rules and confidence framework
- Users receive explanations that are inconsistent with GoldPan's sourced conclusions
- Ask GoldPan™ effectively becomes a second Governance system, creating the same duplication problem

---

## How the Three Systems Interact

```
Restaurant
    ↓
INTAKE OS
  Canvassers collect dishes, ingredients, allergen disclosures,
  preparation methods, substitutions, sourcing — all with
  provenance tracking. No dietary conclusions are drawn.
    ↓
Evidence System (GDL, Allergen_Disclosures, Menu Source Registry)
    ↓
GOVERNANCE OS
  Derivation engine applies Rules Registry to stated evidence.
  Confidence framework assigns certainty to conclusions.
  Filter results are computed. Unknown conclusions are identified.
    ↓
Conclusions System (derived filter results, confidence levels,
  unknown flags, restaurant evidence tier)
    ↓
ASK GOLDPAN™
  AI explanation layer interprets Governance conclusions for users.
  Uncertainty and unknown conclusions are explained honestly.
  Evidence basis is cited. No new dietary conclusions are formed.
    ↓
User
```

The flow is unidirectional. Intake feeds Governance. Governance feeds Ask GoldPan™. No layer reasons backward into the layer above it.

---

## What Each OS Owns

### Intake OS owns:

- Restaurant lifecycle management (prospect → published → recanvassing)
- Coverage criteria and qualification decisions
- Source identification, tiering, and documentation (Menu Source Registry)
- Dish capture and the General Dish List (GDL)
- Ingredient row entry — stated ingredients only, at source-specified specificity
- Allergen disclosure recording — verbatim, with source reference
- Preparation method and substitution documentation
- Source provenance tracking (who collected what, when, from where)
- Freshness management (when evidence needs to be re-examined)
- Confirmation and canvasser outreach (obtaining evidence not yet publicly available)
- Quality assurance of evidence before it enters the production system
- AI-assisted extraction (AI helps canvassers extract facts from sources — it does not reason about what those facts mean)

### Governance OS owns:

- The dietary filter taxonomy (what filters GoldPan offers users)
- The Rules Registry (what evidence is required to derive each filter conclusion)
- The derivation engine (applying rules to evidence to produce conclusions)
- The confidence framework (what evidence quality produces what confidence level)
- The `unknown` policy (when a filter result cannot be determined)
- Scoring and certainty communication
- Allergen flag interpretation (translating stated allergen disclosures into filter-relevant conclusions)
- Dietary tag assignment and Tag_Source (the act of saying "this dish is [vegan]" is a Governance act)
- Conclusion publication standards (what must be true before a conclusion is shown to users)
- Evidence sufficiency standards per filter (how much evidence does Governance require before it will conclude?)

### Ask GoldPan™ owns:

- The system prompt and response framework for AI explanations
- Governing language standards (how uncertainty is communicated)
- The packet format that conveys Governance conclusions to the AI layer
- User-facing explanation of evidence quality and confidence
- The logic for what to say when Governance concluded `unknown`

---

## Existing Governance OS Components

The Governance OS is partially built. Several documents and systems already exist within it:

| Component | Location | Status |
|-----------|----------|--------|
| Rules Registry | `docs/RULES_REGISTRY.md` | Active |
| Scoring Architecture | `docs/SCORING_ARCHITECTURE.md` | Active |
| Evidence Architecture | `docs/EVIDENCE_ARCHITECTURE.md` | Active — may need revision to reflect this boundary |
| Derivation engine | `compute.py` (or pipeline equivalent) | Active |
| Pipeline orchestrator | `docs/PIPELINE_ORCHESTRATOR_DESIGN.md` | Active |
| Allergen architecture | `docs/ALLERGEN_ARCHITECTURE.md` | Active |

These documents define Governance logic. They should be reviewed and, where necessary, updated to ensure they do not contain Intake responsibilities (such as evidence collection protocols or canvasser-facing instructions).

---

## The Guiding Principle

> **Intake captures facts. Governance determines what those facts mean.**

This principle has a corollary for every design decision:

- If you are deciding what to write down → Intake
- If you are deciding what that written evidence supports → Governance
- If you are deciding how to explain what it supports to a user → Ask GoldPan™

When a feature or subsystem spans more than one OS, it must be split at the boundary. The Intake portion lives in the Intake OS. The Governance portion lives in the Governance OS. They interact through the evidence system — not through shared logic or shared responsibility.

---

## Implications for the Intake OS

The Intake OS, defined under this architecture, becomes a richness-maximization system. Its single goal is to produce the fullest, most accurate, best-sourced body of evidence possible for every restaurant it canvasses.

Intake does not need to worry about what conclusions Governance will draw from its evidence. Intake's job is to make the evidence as complete and faithful as possible. Governance will reason over whatever Intake provides.

This means:
- Intake canvassers are freed from dietary reasoning — they are evidence collectors
- Intake quality is measured by richness, source fidelity, and provenance — not by how many filters get derived
- A Tier 3 restaurant where Intake captures every stated ingredient and disclosure has done its job correctly, even if Governance produces many `unknown` conclusions from that evidence
- The completeness of Intake evidence directly determines the ceiling of what Governance can conclude — but that relationship flows one way

**Intake's ambition:** For every restaurant in GoldPan, produce the richest, most faithful, most thoroughly sourced body of evidence that the restaurant's public presence and confirmation interactions make possible.

---

## Implications for the Governance OS

The Governance OS, under this architecture, becomes the single reasoning authority. Every dietary conclusion that GoldPan presents to a user originates here.

This gives Governance a precise scope:
- It reasons over evidence Intake has collected — it does not collect evidence itself
- It maintains the rules that define what evidence supports what conclusions
- When evidence is insufficient, it produces `unknown` — not an approximation
- It is the only place in GoldPan where dietary judgments are made

The Governance OS will need a formal design document equivalent to what the Intake OS has. That document is forthcoming.

---

## Open Questions

1. **Evidence Architecture review** — `EVIDENCE_ARCHITECTURE.md` was written before this boundary was formally established. It should be reviewed to confirm that evidence schema definitions (what fields exist and what they mean) are correctly assigned to either Intake or Governance responsibility.
2. **Allergen_Flags field** — In the current schema, `Allergen_Flags` on ingredient rows straddles the boundary. In Intake, these flags record what the source stated about allergen presence. In Governance, they drive filter conclusions. The field may need to be split: an Intake-owned field for "what the source stated" and a Governance-owned field for "what this implies for filters."
3. **Governance OS design document** — The Governance OS needs a formal architecture document defining its scope, components, and design principles. This is the next major design work after the Intake OS is complete.
