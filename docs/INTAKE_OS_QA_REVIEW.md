# GoldPan Intake OS — QA Review
**Version:** 1.0  
**Date:** 2026-07-03  
**Lifecycle Stage:** `qa_review` — begins when Verification passes; ends when the pipeline runs cleanly, derived conclusions are reviewed and approved, and the restaurant is cleared for publishing  
**Governed by:** INTAKE_OS_RESTAURANT_LIFECYCLE.md, GOLDPAN_OS_ARCHITECTURE.md

---

## Purpose

QA Review is the final gate between the evidence system and the live GoldPan product. It is the last human checkpoint before a restaurant's dishes are published to users.

Where Verification asked "did the canvasser accurately record what the source says?", QA Review asks a different question: **"given the evidence in the system, does the pipeline produce conclusions that are honest, defensible, and ready for users to see?"**

QA Review is where the Intake OS hands off to the Governance OS. The QA reviewer runs the full pipeline, inspects what Governance derived from Intake's evidence, and makes a judgment: is this restaurant ready to publish?

---

## What QA Review Is — and Is Not

**Is:**
- A full end-to-end pipeline run
- A review of derived filter conclusions for reasonableness and defensibility
- A check that `unknown` conclusions are genuinely unknown — not missed evidence
- A check that confidence levels reflect the actual evidence quality
- A freshness record update before publishing
- A human approval decision

**Is not:**
- Additional evidence collection (that is Intake)
- Dietary reasoning from scratch (that is Governance — the pipeline does this)
- A repeat of the Verification spot-check (that is already done)
- A guarantee that every conclusion is correct — QA approves that conclusions are defensible given available evidence

---

## Who Performs QA Review

QA Review is ideally performed by someone other than the original canvasser. The reviewer brings fresh judgment to the question of whether the conclusions make sense — someone who hasn't been immersed in this restaurant's evidence is better positioned to see what a user will see.

When a separate reviewer is not available, the canvasser performs QA with a minimum 24-hour gap after completing Verification.

The QA reviewer must have enough familiarity with GoldPan's Governance rules to evaluate whether derived conclusions are reasonable. They are not just checking that the pipeline ran — they are checking that what the pipeline produced makes sense.

---

## QA Review Workflow

### Step 1 — Run the Full Pipeline

Execute the pipeline end-to-end for this restaurant:

```
validate → backfill → compute → fetch
```

The pipeline must complete with no ERRORS. Warnings should be reviewed — if a warning reflects a genuine evidence gap, note it. If a warning is a known acceptable condition, document that it was reviewed.

If the pipeline produces ERRORS: do not proceed. Return the restaurant to `verification` status, write a Lifecycle_Events row with the error, and resolve the issue before re-running.

### Step 2 — Review Derived Filter Conclusions

Open the pipeline output for this restaurant and review every derived filter conclusion.

For each conclusion, the QA reviewer asks three questions:

**"Does this conclusion make sense given the evidence?"**  
A dish tagged `vegan` should have only plant-based stated ingredients. A dish tagged `gluten-conscious` should have a restaurant disclosure supporting it. If a conclusion doesn't follow from the evidence, it is a pipeline or rules error — flag it, do not approve it.

**"Is this conclusion honest about what GoldPan knows?"**  
A `verified` confidence level requires evidence that justifies it. An `inferred` confidence level requires ingredient rows that support the derivation. If the confidence level overstates the evidence quality, it must be corrected before publishing.

**"Is every `unknown` conclusion genuinely unknown?"**  
`unknown` means the evidence doesn't support a conclusion — not that the canvasser didn't look. For each `unknown`, the reviewer considers: is there evidence available in the source that should have been captured? If so, the restaurant goes back to `evidence_acquisition`. If the `unknown` reflects the true state of available evidence, it is correct and can be published.

### Step 3 — Review `unknown` Conclusions for Missed Evidence

`unknown` conclusions are the most important thing to review carefully. They determine what users cannot learn from this restaurant's GoldPan record.

For each `unknown` conclusion the reviewer considers important:
- Open the primary source
- Check whether the information needed to resolve the `unknown` is actually available in the source and was missed during evidence acquisition
- If yes: return to `evidence_acquisition` for that specific gap
- If no: the `unknown` is correct — document that it was reviewed in the QA notes

Do not resolve `unknown` conclusions by reasoning or inference. If the source doesn't support a conclusion, `unknown` is the correct answer. The goal is not to eliminate `unknown` — it is to ensure that every `unknown` is genuinely unknown and not a missed opportunity to capture available evidence.

### Step 4 — Update Freshness Record

Before approving for publication, update the restaurant's freshness record:

- `recanvass_status` → `current`
- `last_canvassed` → today's date

This ensures the freshness system starts tracking from the correct baseline. A restaurant published without a current freshness record will immediately appear overdue.

### Step 5 — QA Approval Decision

The QA reviewer makes one of three decisions:

**Approve** — pipeline output is clean, conclusions are defensible, `unknown` conclusions are genuinely unknown, freshness record is updated. Restaurant is cleared for publishing.

**Approve with notes** — pipeline output is acceptable but the reviewer has observations that should inform future recanvassing (e.g., "three key allergen filters are unknown — priority for confirmation call"). Approved for publishing; notes recorded in Restaurant_Registry.

**Return** — pipeline output contains conclusions that are not defensible, evidence gaps that should have been captured, or errors that must be resolved. Restaurant returns to the appropriate stage with a documented reason.

---

## Publishing

When QA approval is recorded, the restaurant transitions from `qa_review` to `published`:

- Pipeline output is deployed — `dishes.json` is updated, site reflects the new data
- Restaurant_Registry `Lifecycle_Status` updated to `published`
- Restaurant_Registry `Published_Date` set to today (first publication only)
- Lifecycle_Events row written for `qa_review → published` transition
- Freshness system begins monitoring from today's `last_canvassed` date

**Publishing is not a separate manual step.** A passed QA review means the pipeline output from Step 1 is already the correct output. Deploy it.

---

## What QA Review Does Not Produce

QA Review does not produce new evidence. If the reviewer notices during pipeline review that evidence is missing or weak, the response is to return the restaurant to the appropriate Intake stage — not to add evidence during QA. The pipeline output reflects whatever evidence Intake collected. QA evaluates that output; it does not modify the evidence system.

---

## Exit Gate

QA Review is complete when all of the following are true:

- [ ] Pipeline ran end-to-end with no ERRORS
- [ ] All derived filter conclusions reviewed for reasonableness and defensibility
- [ ] All `unknown` conclusions reviewed — genuinely unknown or returned for evidence acquisition
- [ ] Confidence levels reviewed — no overstated confidence
- [ ] Freshness record updated: `recanvass_status = current`, `last_canvassed = today`
- [ ] QA approval decision recorded
- [ ] Lifecycle_Events row written for `qa_review → published` (or return transition)

---

## Special Situations

**Pipeline produces a conclusion that seems wrong but technically follows the rules:** The QA reviewer does not override the pipeline's Governance logic. If a conclusion follows from the rules but seems wrong, that is a Rules Registry issue — flag it for Governance review. Do not block publication over a rules disagreement unless the conclusion is actively misleading to users.

**Restaurant has many `unknown` conclusions:** This is not a QA failure. A restaurant with thin evidence will have many `unknown` conclusions. QA's job is to confirm those `unknown` results are accurate, not to eliminate them. A published restaurant with many `unknown` conclusions is still valuable — its Discovery Value and whatever stated evidence exists serve users who would never find it otherwise.

**QA reviewer disagrees with canvasser's evidence interpretation:** The evidence system records what the source says. If the reviewer believes a canvasser entered something incorrectly, that is a Verification failure that should have been caught earlier. Return to `verification` with a documented reason rather than correcting evidence during QA.

**Restaurant being re-published after recanvassing:** The same QA Review process applies. The reviewer looks at the updated pipeline output and confirms it reflects the current evidence state. The `Published_Date` is not updated on re-publication — only `last_canvassed` changes.

---

## Relationship to Other Intake OS Documents

- **INTAKE_OS_VERIFICATION.md** — the preceding stage; QA Review receives verified evidence
- **INTAKE_OS_RESTAURANT_LIFECYCLE.md** — this document governs Stage 6 (`qa_review`) and Stage 7 (`published`)
- **INTAKE_OS_RESTAURANT_REGISTRY.md** — QA approval updates `Lifecycle_Status`, `Published_Date`, `Recanvass_Status`, and `Last_Canvassed`
- **GOLDPAN_OS_ARCHITECTURE.md** — QA Review is where Intake hands off to Governance; the pipeline run in Step 1 is a Governance OS execution over Intake evidence
- **RULES_REGISTRY.md** — the rules the pipeline applies; QA reviewers must be familiar with them to evaluate derived conclusions
- **RECANVASSING_POLICY.md** — governs what happens after `published`; QA sets the freshness baseline that the recanvassing policy monitors
