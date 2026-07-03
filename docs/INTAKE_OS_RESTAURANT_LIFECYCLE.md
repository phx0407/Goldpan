# GoldPan Intake OS — Restaurant Lifecycle
**Version:** 1.0  
**Date:** 2026-07-03  
**Scope:** Defines the complete lifecycle of a restaurant in the GoldPan system, from prospect identification through publication and ongoing maintenance. This document is the foundation of the GoldPan Intake OS.

---

## Purpose

The Restaurant Lifecycle governs how a restaurant enters, moves through, and is maintained within GoldPan. Every subsystem of the Intake OS — Restaurant Onboarding, Evidence Acquisition, Dish Capture, Verification, Freshness Management, Quality Assurance, AI-Assisted Extraction, and the Publishing Pipeline — operates within the structure this lifecycle defines.

The lifecycle exists to answer one question at any moment: **what is the current state of this restaurant's knowledge, and what is the next required action?**

---

## Design Principles

**State is always known.** Every restaurant in GoldPan has an explicit lifecycle status at all times. "We haven't gotten to it yet" is not a valid state — that is `prospect`. Ambiguity is a data quality failure.

**Transitions are governed, not ad hoc.** A restaurant advances through the lifecycle only when defined conditions are met. No restaurant moves to `published` without a completed QA pass. No restaurant moves to `recanvassing` without a freshness trigger.

**The lifecycle is the audit trail.** Every state change is recorded with a timestamp and actor. A canvasser, a QA reviewer, and the pipeline itself are all actors. This makes the lifecycle queryable: who touched this restaurant, when, and what did they do?

**A human is always accountable.** Automation may assist at any stage, but a human is the accountable actor for every state transition that introduces or modifies evidence. The system may flag, extract, and propose — it does not decide.

---

## Lifecycle Stages

### 1. `prospect`
A restaurant has been identified as a candidate for GoldPan coverage but has not yet been evaluated or approved.

**How a restaurant enters this stage:**
- Customer request via GoldPan contact channel
- Canvasser discovery during field research
- Strategic market expansion (e.g., "cover all vegan-friendly restaurants in Avondale")
- Partner referral

**What is known at this stage:**
- Restaurant name
- General location (neighborhood or address)
- Source of the prospect (who identified it and why)

**What is NOT required:**
- Menu URL
- Dish data
- Any verified evidence

**Required actions before transition:**
- Prospect is reviewed against GoldPan coverage criteria (see Coverage Policy)
- Decision: `qualified` or `rejected`

---

### 2. `qualified`
The restaurant has been evaluated and approved for GoldPan canvassing. It is in the queue but active work has not begun.

**Transition from `prospect`:**
- Restaurant meets coverage criteria (location, menu accessibility, relevance to GoldPan users)
- A Restaurant_ID is assigned via `next_id.py`
- A Freshness Registry record is created with `recanvass_status = needs_review`
- A Menu Source Registry record is created (source URL TBD or known)

**What the system contains at this stage:**
- Restaurant_ID
- Restaurant name and location
- Prospect source record
- Empty or stub records in Freshness and Menu Source registries

**Waiting condition:**
- Canvasser capacity. `qualified` is the holding state for restaurants that are approved but not yet assigned.

---

### 3. `onboarding`
A canvasser has been assigned and is actively setting up the restaurant in the GoldPan system.

**Transition from `qualified`:**
- Canvasser assignment confirmed
- Onboarding checklist initiated (see Restaurant Onboarding subsystem)

**Required actions in this stage:**
- Identify and document all primary menu sources (website, PDF, third-party platform)
- Identify whether the restaurant publishes an allergen guide or ingredient-level disclosure
- Determine source tier for each source (Tier 1 / Tier 2 / Tier 3)
- Record source URLs and access method in Menu Source Registry
- Confirm restaurant is currently operating (not closed or seasonal)

**Exit condition:**
- All source records are complete
- At least one Tier 1 or Tier 2 source is documented, OR a decision is made to proceed with Tier 3 only (noted in limitations)

---

### 4. `evidence_acquisition`
The canvasser is actively collecting and recording evidence from identified sources.

**Transition from `onboarding`:**
- Source records are complete
- Canvasser begins reading and transcribing evidence into GoldPan

**What happens at this stage:**
- Dishes are entered into the GDL (General Dish List) with Dish_IDs assigned
- Ingredient rows are created for each dish with sources documented
- Allergen_Disclosures rows are created where the restaurant has published explicit allergen information
- Allergen_Flags are populated on ingredient rows where the canvasser identifies allergen presence
- `Tag_Source` values are assigned for dietary tags

**Governed constraints active at this stage:**
- No evidence may be entered without a source reference
- Allergen_Flags may only be set by a canvasser with a source — the engine may never write them
- `none` in Allergen_Flags means the canvasser explicitly observed no allergen flags — it is not a default
- All ID values must be generated by `next_id.py`, never manually typed

**Exit condition:**
- All dishes from the identified source(s) have been entered
- All available allergen disclosures have been recorded
- `validate_database.py` passes with no ERRORS (WARNINGs acceptable)

---

### 5. `verification`
Evidence has been entered and is under review for accuracy, completeness, and source fidelity.

**Transition from `evidence_acquisition`:**
- Canvasser marks evidence entry as complete
- Verification is assigned (may be the same canvasser on a second pass, or a separate reviewer)

**What happens at this stage:**
- Spot-check: 20% of dish entries are compared against the source document
- Source references are confirmed accessible (URL resolves, PDF is attached or archived)
- Allergen disclosures are checked against the original source for accuracy
- Any discrepancies are corrected or flagged with a note

**Exit condition:**
- Spot-check passes with no uncorrected errors
- `validate_database.py` passes with no ERRORS

---

### 6. `qa_review`
A final quality pass before publishing. This is the last gate between the Evidence System and the live GoldPan product.

**Transition from `verification`:**
- Verification is marked complete
- QA reviewer assigned (ideally not the original canvasser)

**What happens at this stage:**
- Pipeline is run end-to-end: `validate → backfill → compute → fetch`
- Derived filters are reviewed for the restaurant's dishes — do conclusions make sense given the evidence?
- `Unknown` conclusions are reviewed: is the evidence genuinely absent, or was it missed?
- Confidence levels are reviewed: are `inferred` conclusions defensible from the ingredient list?
- Freshness record is updated: `recanvass_status = current`, `last_canvassed = [date]`

**Exit condition:**
- Pipeline passes with no ERRORS
- QA reviewer approves
- Freshness record is set to `current`

---

### 7. `published`
The restaurant's dishes are live in `dishes.json` and visible on GoldPan.

**Transition from `qa_review`:**
- QA approval recorded
- Pipeline output deployed (dishes.json updated, site reflects new data)
- Restaurant status in GoldPan system set to `active`

**What is true of a published restaurant:**
- All dishes meet GoldPan evidence standards
- All derived filter conclusions are either computed or explicitly `unknown` with a documented reason
- Freshness record shows `current` status
- At least one source is documented and verified accessible

**This is a stable state, not an end state.** A published restaurant re-enters the lifecycle via freshness triggers.

---

### 8. `recanvassing`
A published restaurant has been flagged by the freshness system as requiring evidence review and update.

**Transition from `published`:**
- Triggered by freshness policy (see RECANVASSING_POLICY.md):
  - `due_soon`: flagged, scheduled for next canvassing cycle
  - `overdue`: elevated priority, conclusions begin degrading (verified → likely)
  - `needs_review`: urgent, may be temporarily suppressed from AI responses

**What happens at this stage:**
- Canvasser is assigned to re-examine the restaurant's sources
- Changes to menu, ingredients, or allergen disclosures are identified
- Evidence is updated, added, or retired as appropriate
- If no changes are found: freshness record is confirmed and reset to `current`
- If changes are found: affected dishes re-enter `evidence_acquisition` → `verification` → `qa_review`

**Exit condition:**
- All evidence is current
- `validate_database.py` passes
- Pipeline re-run, output updated
- Freshness record reset: `recanvass_status = current`, `last_canvassed = [date]`

---

### 9. `suspended`
A published restaurant is temporarily removed from active GoldPan coverage due to external conditions.

**Triggers:**
- Restaurant temporarily closed (renovation, seasonal closure)
- Primary source inaccessible (website down, menu removed)
- Evidence integrity concern identified post-publication

**What happens at this stage:**
- Dishes are marked inactive in the GDL
- Dishes are excluded from `dishes.json` output
- A suspension reason and expected resolution date are recorded
- Dishes are NOT deleted — evidence is preserved

**Exit condition:**
- Condition resolves → restaurant returns to `recanvassing` for a full evidence refresh before re-publishing

---

### 10. `deactivated`
A restaurant is permanently removed from GoldPan coverage.

**Triggers:**
- Restaurant has permanently closed
- Restaurant is outside GoldPan's current coverage scope
- Evidence cannot be maintained to GoldPan standards (e.g., no accessible sources)

**What happens at this stage:**
- All dishes marked inactive
- Restaurant record archived with deactivation reason and date
- Evidence records preserved in full — GoldPan does not delete evidence, even for deactivated restaurants
- Deactivation is logged as a lifecycle event

**This state is permanent.** A closed restaurant that reopens under new ownership is a new `prospect`, not a reactivation of the old record.

---

## Lifecycle State Diagram

```
                    ┌─────────────┐
                    │   prospect  │ ◄── customer request / canvasser discovery
                    └──────┬──────┘
                           │ approved
                    ┌──────▼──────┐
                    │  qualified  │ ◄── holding queue
                    └──────┬──────┘
                           │ canvasser assigned
                    ┌──────▼──────┐
                    │  onboarding │
                    └──────┬──────┘
                           │ sources documented
               ┌───────────▼────────────┐
               │  evidence_acquisition  │
               └───────────┬────────────┘
                           │ entry complete
                    ┌──────▼──────┐
                    │ verification│
                    └──────┬──────┘
                           │ spot-check passes
                    ┌──────▼──────┐
                    │  qa_review  │
                    └──────┬──────┘
                           │ QA approved
                    ┌──────▼──────┐
            ┌──────►│  published  │◄──────────────┐
            │       └──────┬──────┘               │
            │              │ freshness trigger     │
            │       ┌──────▼──────┐               │
            └───────│recanvassing │               │
            (clean) └──────┬──────┘               │
                           │ changes found         │
                           └───────────────────────┘
                           (re-enter evidence_acquisition)

          ┌─────────────────┐          ┌──────────────┐
          │   suspended     │◄── temp  │  deactivated │◄── permanent
          └────────┬────────┘          └──────────────┘
                   │ resolved
                   └──► recanvassing
```

---

## Lifecycle Actors

| Actor | Role |
|-------|------|
| Canvasser | Performs evidence acquisition, dish capture, initial verification |
| QA Reviewer | Performs verification spot-check and QA review |
| Pipeline | Runs validation, derivation, and output generation |
| Freshness System | Monitors recanvass_status and triggers recanvassing |
| GoldPan System | Assigns IDs, enforces schema, maintains audit trail |

---

## What This Document Does Not Cover

Each of the following is a separate Intake OS subsystem document, designed to operate within this lifecycle:

- **Restaurant Onboarding** — checklist, source documentation, ID assignment
- **Evidence Acquisition** — canvasser workflow, source access protocols, entry standards
- **Dish Capture** — GDL entry, ingredient row standards, ID sequencing
- **Verification** — spot-check protocol, discrepancy handling
- **Freshness Management** — recanvass triggers, priority queuing, status transitions
- **Quality Assurance** — pipeline review, filter conclusion review, approval workflow
- **AI-Assisted Extraction** — AI role in evidence extraction, human review requirements
- **Publishing Pipeline** — pipeline execution, output validation, deployment

---

## Open Questions

1. **Coverage criteria** — What explicit criteria qualify a restaurant for GoldPan coverage? (Location radius, cuisine type, menu accessibility threshold, minimum dish count?)
2. **Canvasser capacity model** — How many restaurants can one canvasser onboard per week? This determines the qualified queue depth and expected time-to-published.
3. **Lifecycle tracking location** — Where does lifecycle status live? Currently implicit (not stored in any GoldPan tab). Should this be a `Restaurant_Registry` tab in the database?
4. **Recanvassing frequency** — The RECANVASSING_POLICY.md defines freshness windows but not a canvassing cycle cadence. Should recanvassing be scheduled (e.g., quarterly) or purely reactive to freshness status?
5. **Suspension vs. deactivation authority** — Who has the authority to suspend or deactivate a restaurant? Should this require a second reviewer?
