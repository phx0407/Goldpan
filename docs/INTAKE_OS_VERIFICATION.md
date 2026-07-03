# GoldPan Intake OS — Verification
**Version:** 1.0  
**Date:** 2026-07-03  
**Lifecycle Stage:** `verification` — begins when a canvasser marks evidence acquisition complete; ends when a spot-check passes with no uncorrected errors and `validate_database.py` passes with no ERRORS  
**Governed by:** INTAKE_OS_RESTAURANT_LIFECYCLE.md, GOLDPAN_OS_ARCHITECTURE.md

---

## Purpose

Verification answers one question: **does what GoldPan recorded accurately reflect what the source says?**

Evidence Acquisition produces a body of evidence. Verification independently confirms that the evidence was transcribed faithfully — that dish names match the source, ingredient rows contain only what the source stated, allergen disclosures represent what the restaurant actually published, and every record has a traceable source reference.

Verification is not an evaluation of whether the evidence is sufficient or what conclusions it supports. That is QA Review. Verification is narrower: it checks source fidelity. A verified restaurant is one where GoldPan can be confident its records accurately reflect the sources that were canvassed.

---

## What Verification Is — and Is Not

**Is:**
- An independent, source-matched check on a random sample of dish records
- Confirmation that source URLs and documents are still accessible
- A check that allergen disclosures are accurately represented
- A check that every record has a source reference
- Correction of transcription errors found during the check

**Is not:**
- A re-canvassing of the source looking for missed dishes (completeness was an Evidence Acquisition responsibility)
- An evaluation of whether the evidence supports dietary conclusions (that is Governance, triggered by QA Review)
- A pipeline run or filter derivation check (that happens in QA Review)
- A contact with the restaurant or any external confirmation process
- A judgment about whether the restaurant has disclosed enough information

---

## Who Verifies

Verification is ideally performed by a reviewer who did not perform evidence acquisition for this restaurant. Fresh eyes catch normalization errors — places where the canvasser read something, mentally corrected it, and transcribed their correction rather than the source.

When a separate reviewer is not available, the canvasser performs a second pass with a minimum 48-hour gap between evidence acquisition and self-verification. The gap matters: a canvasser who verifies their own work immediately will re-read what they intended to write, not what they actually wrote.

The verifier's role is not adversarial. They are a quality partner, not an auditor. When they find an error, the goal is accurate correction — not blame assignment.

---

## The Spot-Check Protocol

### Sample Size

The verifier checks a random sample of dish records from the GDL. The sample size is determined by the total dish count:

| Total dishes | Minimum sample |
|---|---|
| 1–10 dishes | All dishes (100%) |
| 11–30 dishes | 6 dishes or 25%, whichever is larger |
| 31–75 dishes | 20% of dishes, minimum 8 |
| 76+ dishes | 15% of dishes, minimum 15 |

**Random selection is mandatory.** The verifier does not select dishes they recognize, suspect, or find interesting. A random number generator or systematic interval (every Nth dish in order of Dish_ID) is acceptable. Cherry-picking — selecting only dishes the verifier is confident about — defeats the purpose.

### What to Check Per Dish

For each sampled dish, the verifier opens the original source and compares directly:

**1. Dish name**  
Does the name in GoldPan match the source exactly? Trivial formatting differences (capitalization, punctuation) are acceptable; substantive differences are discrepancies.

**2. Dish description**  
Does the description in GoldPan match the source? Look for paraphrasing, expansion, or compression — any text that differs from the source verbatim.

**3. Ingredient rows**  
Check in both directions:
- Does every ingredient row correspond to something the source actually states? (Addition error — most serious)
- Does the source name any ingredient that has no corresponding row? (Omission error)

Ingredient rows must reflect the source's specificity: "olive oil" is wrong if the source says "extra-virgin olive oil." "Pasta" is wrong if the source says "gluten-free penne."

**4. Source reference**  
Is the correct `Source_ID` recorded on the dish and ingredient rows? Does the referenced source actually contain this dish?

**5. Dietary disclosure labels**  
If the source carries a dietary label for this dish (V, VG, GF, Halal, etc.), is that label recorded as a disclosure in the evidence system? If the source carries no label, is there any dietary classification asserted in the record that has no source basis?

---

## Source Verification

Before or alongside the spot-check, the verifier confirms that every source in the Menu Source Registry is still accessible.

For each source:
- Confirm the URL resolves and returns the expected content
- Confirm the content is the menu (not a homepage, a 404, or a paywall)
- Confirm the source still contains the dishes it was documented as containing

**If a source is no longer accessible:**
Update the source record `Status` to `inactive` and record today's date. Assess whether the evidence that came from this source can still be verified (e.g., a cached copy exists, a PDF was archived). If not, flag the affected dishes — their evidence cannot be verified and should be noted in the Lifecycle_Events log.

A restaurant where the primary source has gone offline cannot complete verification until an alternative source is found or the evidence is flagged as unverifiable. This is a freshness management issue and should trigger `recanvass_status = needs_review`.

---

## Allergen Disclosure Verification

Every Allergen_Disclosures record is verified against its source — this is not sampled. All allergen disclosures are checked because they carry safety implications.

For each Allergen_Disclosures record:
- Open the source at the referenced URL
- Confirm the disclosure text accurately represents what the source says
- Confirm the scope is correctly recorded (dish-level vs. kitchen-wide vs. certification)
- Confirm the source was accessible at the recorded date

Allergen disclosure errors are the most serious category of discrepancy. A disclosure that overstates what the restaurant said is a safety risk. A disclosure that understates what the restaurant said is an evidence gap. Both require immediate correction before verification can pass.

---

## Discrepancy Handling

### Minor Discrepancy
Formatting differences, minor transcription errors, capitalization inconsistencies that do not change meaning.

**Action:** Correct in place. Note the correction in the dish record's Notes field with date and verifier name. Does not block verification.

### Substantive Discrepancy
An ingredient row that doesn't correspond to the source. A dish description that has been paraphrased or expanded. An allergen disclosure that misrepresents the source. A dietary label recorded without a source basis.

**Action:** Correct the record. Flag the dish for canvasser awareness. If the error reflects a pattern (multiple dishes with the same type of error), the verifier expands the sample to assess scope.

### Addition Error
An ingredient, allergen flag, or dietary assertion that appears in GoldPan but has no basis in the source. This is the most serious error category because it introduces information into GoldPan that the restaurant never provided.

**Action:** Remove the unsourced content immediately. Flag for canvasser review. The canvasser must confirm whether the addition was intentional (and if so, provide a source) or an error. If intentional without a source, it violates the Intake standard and must be removed regardless.

### Missing Source Reference
A dish record, ingredient row, or allergen disclosure with no source reference.

**Action:** Identify the correct source and add the reference. If the correct source cannot be determined, the record must be flagged as unverifiable and held until the source can be confirmed.

---

## Error Rate Thresholds

The verifier evaluates the overall error rate across the sampled dishes to determine whether isolated corrections are sufficient or whether a broader review is needed.

| Error rate in sample | Action |
|---|---|
| 0 errors | Pass — proceed to exit gate |
| 1–2 errors, same dish | Correct and pass |
| Errors across 2+ dishes | Expand sample by 10%; if errors continue, escalate to canvasser for full review of all dishes |
| Addition errors in any dish | Mandatory expansion — check all dishes from the same source section |
| >25% of sampled dishes have errors | Full re-entry required — evidence acquisition must be repeated |

**Full re-entry** means the canvasser returns to `evidence_acquisition` status, clears all dish and ingredient records for the restaurant, and re-enters from scratch. Verification cannot patch a fundamentally unreliable entry. The Lifecycle_Events log records the return transition with the reason.

---

## Verification Record

When verification is complete, the verifier writes a Lifecycle_Events row recording:
- `From_Status`: verification
- `To_Status`: qa_review (if passed) or evidence_acquisition (if failed)
- `Actor`: verifier name
- `Event_Date`: today's date
- `Notes`: dishes sampled, discrepancies found, corrections made, pass/fail determination

For restaurants where no discrepancies were found, the Notes can be brief: "Verified [N] dishes against [source name]. No discrepancies. Pass."

For restaurants where corrections were made, each correction should be summarized: "Dish D042: ingredient row for 'butter' removed — not stated in source. Dish D047: description updated to match source verbatim. Pass with corrections."

---

## Exit Gate

Verification is complete when all of the following are true:

- [ ] Random sample selected and documented (minimum per dish count table above)
- [ ] All sampled dishes compared directly against their source — dish name, description, ingredient rows, source reference, dietary disclosures
- [ ] All Allergen_Disclosures records verified against source (100%, not sampled)
- [ ] All source URLs confirmed accessible
- [ ] All discrepancies corrected or, if unresolvable, documented and escalated
- [ ] Error rate is within acceptable threshold (no full re-entry required)
- [ ] `validate_database.py` passes with no ERRORS
- [ ] Lifecycle_Events row written for `verification → qa_review` transition

---

## Special Situations

**Source has changed since evidence acquisition:** If the source has been updated and now differs from what the canvasser recorded, this is not a verification error — it is a freshness event. Update the source record's `Date_Last_Verified` to today. Flag the changed sections for recanvassing. Do not correct evidence to match the new source during verification — that is a recanvassing task.

**Source is in a language the verifier does not read:** The verifier should not verify evidence from a source they cannot read. Assign a different verifier or bring in translation support. Verification by someone who cannot confirm source fidelity is not verification.

**Canvasser and verifier disagree on a discrepancy:** The verifier's reading of the source governs during verification. If the canvasser believes the verifier is wrong, the dispute is resolved by a third reader of the source — not by deferring to the canvasser's original entry.

**Restaurant has very few dishes (under 5):** All dishes are verified. The minimum sample is 100% when total dishes are 10 or fewer.

---

## Relationship to Other Intake OS Documents

- **INTAKE_OS_EVIDENCE_ACQUISITION.md** — produces the evidence this stage verifies; any violation of Evidence Acquisition standards found during verification is a discrepancy
- **INTAKE_OS_RESTAURANT_LIFECYCLE.md** — this document governs Stage 5 (`verification`)
- **INTAKE_OS_QA_REVIEW.md** _(forthcoming)_ — the next stage; receives verified evidence and runs the full pipeline before publishing
- **GOLDPAN_OS_ARCHITECTURE.md** — verification is an Intake OS function; it confirms source fidelity, not dietary conclusions
