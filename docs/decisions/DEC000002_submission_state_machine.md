# DEC000002 — Canonical Restaurant Update Submission State Machine

**Status:** draft v3 — awaiting Founder approval (revised per targeted Founder corrections to v2)
**Decision basis:** architectural_requirement, compliance_or_risk_control
**Decision dependencies:** none (foundational record, sibling to DEC000001)
**Registry impact:** governs `submission.restaurant_update.*`, `submission.convert_to_intake`, and new routing commands (see §5.5)

**Revision note:** v2's core separation of review outcome from downstream processing is retained and not reopened. This revision makes ten targeted corrections: keeping the physical `status` column rather than renaming it, replacing "conversion" with the broader "disposition" concept and reconciling it against actual OS ownership boundaries, correcting the resubmission lifecycle (parent does not return to `pending_review`), tightening archival eligibility, resolving the claim mechanism to match DEC000001 v3's pattern, and leaving the `resulting_intake_session` entity question genuinely open rather than silently renaming it. Sections 1-3 carry forward with corrections noted inline; §5 onward is rewritten.

---

## 1. Competing versions, side by side (unchanged from v2)

| Source | States (in order) | Notes |
|---|---|---|
| Blueprint §5b (generic) | `pending_review → in_review → approved → returned → rejected → converted` | Generic "Submission" row. |
| Blueprint §5i (Restaurant Update Submission table) | `received → pending_review → in_review → accepted → rejected → archived` | Uses `accepted`, not `approved`; no `converted`. |
| Live DB — `operations.restaurant_update_submissions` | `status` CHECK: `pending_review, in_review, approved, returned, rejected` | Column comment: *"approved does NOT automatically write to evidence — reviewer must take deliberate action (trigger Intake session or direct edit)."* Treated in this revision as E1 evidence of prior implementation intent, not as governing authority over the Blueprint's evidence boundary — see §5.3. |
| Live DB — `operations.partner_submissions` (sibling) | `status` CHECK includes `converted` | Not treated as binding precedent for this table — finding unchanged from v2 §2. |

No API or UI exists for either submissions table.

**New finding this revision:** the Blueprint independently documents a real, already-governed routing destination for restaurant-submitted identity/contact changes — the **Identity Review Queue**, part of Restaurant Operations OS: *"Restaurant-submitted changes land in pending review. No restaurant-submitted value writes directly to evidence.restaurants. The submission enters the Identity Review Queue with status `pending_restaurant_submission`."* (Blueprint, Identity/Enrichment section). This is E2 evidence — a governing Blueprint requirement, not an inference — and it directly informs the disposition-routing model in §5.2.

## 2. Sibling-table evidence (unchanged from v2)

`partner_submissions`'s `converted` status and single-target CRM conversion remain treated as a different downstream shape from this entity's multi-path resolution, not binding precedent. No change to `partner_submissions` is recommended by this decision.

## 3. Phase 5 commands that depend on this decision (expanded)

| Command | Registry status | This revision's treatment |
|---|---|---|
| `submission.restaurant_update.view` (CMD000024, missing) | unchanged | No change. |
| `submission.restaurant_update.review` (CMD000025, missing, currently one combined command) | **split, adopted outright** | See §5.5 — no longer left optional as in v2; this revision recommends the split as the registry correction itself. |
| `submission.convert_to_intake` (CMD000026, missing) | **scope narrowed** | Handles the `intake_required` disposition only, not all post-approval outcomes. See §5.2, §5.5. |
| **New:** `submission.restaurant_update.claim`, `.release`, `.return`, `.approve`, `.reject` | not in registry today | Replace the single `.review` entry. See §5.5, §5.6. |
| **New:** `submission.route_to_identity_review` | not in registry today | Missing/future — routes to the Blueprint's existing Identity Review Queue. See §5.2, §5.5. |
| **New:** `submission.close_no_action` | not in registry today | Missing/future. See §5.2, §5.5. |
| **New:** `submission.escalate_exception` | not in registry today | Missing/future — routes to a Governance/Knowledge OS correction workflow, not a direct evidence edit. See §5.2, §5.5. |

## 5. Resolution of each targeted correction

### 5.1 Column naming — no physical rename

v2 recommended renaming `status` → `review_status`. This revision withdraws that recommendation for Phase 5. **The existing physical column name `status` is retained**; "review status" is used only as the conceptual/documentation label for what that column represents (to distinguish it from the new disposition dimension). A physical rename adds migration churn (every existing query, RLS policy reference, and report using `status` would need updating) with no compatibility or clarity benefit strong enough to justify it — the column's meaning is already unambiguous once a separate `disposition_status` exists alongside it. Revisit only if a concrete conflict or confusion is later demonstrated.

### 5.2 "Conversion" replaced with "disposition" — and reconciled against OS ownership

v2's `conversion_status`/`conversion_type` implied a single downstream action shape (data gets converted into something). The actual post-approval outcomes are broader and cross OS boundaries differently. Renamed dimension:

```
disposition_status:   unassessed | pending | in_progress | completed | failed
disposition_type:     intake_required | identity_review | no_action | exception_escalation
```

**Routing rules, reconciled against the Blueprint's evidence boundary (§5.3 below) and OS ownership model:**

| `disposition_type` | Routes to | Owning OS | Command | Governing basis |
|---|---|---|---|---|
| `intake_required` | Creates/links an Intake Packet | Intake OS (governed by DEC000001) | `submission.convert_to_intake` | Blueprint §6 Workflow 2: food/menu/evidence-adjacent changes must pass through Intake, not direct edit. |
| `identity_review` | Enters the existing Identity Review Queue | Restaurant Operations OS | `submission.route_to_identity_review` | Blueprint, Identity/Enrichment section (E2, quoted in §1) — this pathway already exists and is already governed; this decision routes into it rather than inventing a new one. |
| `no_action` | Closes immediately, no cross-OS handoff | Restaurant Operations OS (the reviewing coordinator's own scope) | `submission.close_no_action` | No further action needed; requires a documented reason so "no action" is distinguishable from "forgotten." |
| `exception_escalation` | A separately governed correction workflow | Governance OS / Knowledge OS | `submission.escalate_exception` | Reserved for cases that don't fit ordinary Intake or Identity Review routing — not a bypass, a distinct escalation with its own (not-yet-defined) governance. |

This table is the direct answer to why these four values, rather than v2's `intake_packet`/`identity_update`/`no_action`/`other`, better preserve ownership boundaries: each value now maps to exactly one owning OS and one already-or-newly-named command, rather than leaving "what actually happens and who's responsible" implicit in a status label.

### 5.3 The live schema comment vs. the Blueprint evidence boundary — reconciled

The current `restaurant_update_submissions` column comment describes an approved submission as being able to, at a reviewer's discretion, "directly edit evidence records." v2 preserved this option (via a `direct_edit`/`identity_update` disposition type) without checking it against governing Blueprint text. This revision does check it, and finds a conflict:

- Blueprint: submitted data is a candidate evidence only; restaurant submissions do not write directly to production evidence (§6 Workflow 2: *"No restaurant submission writes directly to production evidence"*); food/menu changes route through Intake and Governance; each OS mutates only its own owned data (Restaurant Operations OS does not own `evidence.*`).
- Live schema comment: describes a coordinator directly editing evidence as one of two normal outcomes of approval.

**Resolution:** the schema comment is treated as **E1 evidence of prior implementation intent** — real signal about what the system's authors previously assumed — but it does **not** carry governing authority over the Blueprint's evidence boundary, which is more specific and more recently reasoned about in this analysis. The "direct edit" path is **not preserved automatically**. Instead:
- Food/menu/evidence-adjacent changes route to Intake (`intake_required`).
- Identity/contact/info changes route to the existing Identity Review Queue (`identity_review`) rather than being edited directly by the submission's reviewer.
- Genuinely actionless submissions close with a reason (`no_action`).
- Any submission that seems to need a direct evidence correction outside these paths is not given one by this workflow — it is escalated (`exception_escalation`) to a separately governed Knowledge/Governance correction workflow, which is out of scope to design here and must be its own future decision.

This is the most consequential correction in this revision: it closes a path that the live schema currently implies is normal but that does not hold up against the Blueprint's own evidence-boundary rules once actually checked.

### 5.4 Disposition selection required at approval

An approved submission must not be left with an undefined next action. **The approval command (`submission.restaurant_update.approve`) requires `disposition_type` as a parameter** — it cannot be called without one. The system then derives the initial `disposition_status`:

- `disposition_type = no_action` → `disposition_status = completed` immediately (the "action" was the decision itself, plus the mandatory reason).
- `disposition_type ∈ {intake_required, identity_review, exception_escalation}` → `disposition_status = pending` (routed, not yet resolved).

Before approval, `disposition_status = unassessed` (not `not_required` as in v2 — "unassessed" more accurately says "no disposition decision has been made yet," whereas "not_required" could be misread as an assessment that concluded nothing was needed, which is a `no_action` outcome, not a pre-approval default). This directly closes the Founder's concern: an approved-but-unrouted submission is impossible under this model, and `unassessed` is visually and semantically distinct from `completed`, so it cannot be mistaken for resolved work.

### 5.5 Command impacts, expanded

- `submission.convert_to_intake` — **scope narrowed** to the `intake_required` disposition only. It must refuse to run against any submission whose `disposition_type` is not `intake_required`.
- `submission.route_to_identity_review` — new, missing/future. Places the submission's relevant fields into the existing Identity Review Queue (Restaurant Operations OS), per §5.2.
- `submission.close_no_action` — new, missing/future. Sets `disposition_status = completed` with the mandatory reason already captured at approval time; effectively a formality/finalization step, not a separate decision.
- `submission.escalate_exception` — new, missing/future. Hands off to Governance/Knowledge OS; this decision does not define that workflow's internals, only that this is the correct exit point from the submission lifecycle for cases that don't fit the other three.
- `submission.restaurant_update.review` (CMD000025) — **split, adopted as the registry correction itself** (not left optional): replaced by `submission.restaurant_update.claim`, `.release`, `.return`, `.approve`, `.reject`. Per the Founder's instruction, this is recommended directly rather than presented as an optional Founder choice, mirroring DEC000001 v3's treatment of mechanical corrections.

### 5.6 Claim ownership for `in_review`

Defined identically in structure to DEC000001 v3's mechanism, applied to this entity:

- **Claim** (`submission.restaurant_update.claim`): one atomic conditional update — `pending_review → in_review`, requires `claimed_by_user_id IS NULL`, sets `claimed_by_user_id`, optional `claimed_by_display_name` snapshot, `claimed_at`. Returns no row (claim fails, caller told plainly) if already claimed or state changed.
- **Release** (`submission.restaurant_update.release`): `in_review → pending_review`, clears claim fields. Allowed by the current claimant; administrator override allowed with a required reason.
- **Decision commands clear the claim atomically as part of the same transition:** `.return`, `.approve`, `.reject` each, in one operation, move `status` out of `in_review`, clear the claim fields, and write the reviewer identity into append-only decision history — consistent with DEC000001 v3 §5.5's rule that the claim fields describe current ownership, not historical record; the historical reviewer of record lives permanently in the audit/event log, not in the (now-cleared) claim fields.
- Same open question as DEC000001 §7 Founder decision 8: the exact reference target for `claimed_by_user_id` depends on identifying the current authentication/user model, not assumed here.

### 5.7 Resubmission lifecycle — corrected

v2 stated a returned submission transitions `returned → pending_review` (same row). This is wrong for this entity, for the same reason DEC000001 v3 recommended in-place correction for packets but not here: `restaurant_update_submissions`'s own schema comment declares the row append-only beyond status/review fields, and once `status = returned` is reached that is the row's final state.

**Corrected model:**

```
parent:  in_review → returned    (terminal for the parent row — it never moves again)
child:   created fresh at pending_review
         child.resubmission_of_submission_id = parent.submission_id
```

**Linear-chain rules:**
- Each replacement (child) references exactly one parent via `resubmission_of_submission_id`.
- Each parent may have **at most one** direct replacement — enforced via a `UNIQUE` constraint on `resubmission_of_submission_id` (excluding nulls), preventing branching (two different corrected versions of the same returned submission).
- Only the newest leaf in a chain is "active" for review; earlier links are superseded but remain queryable.
- Original payloads are immutable at every link — no row's `payload_json`/`description` is ever edited in place, consistent with the schema's append-only comment.
- Obsolete parents are excluded from default active-review queue views but are not archived automatically (archival is a separate, explicit action — see §5.8) and remain fully queryable for audit.

**`superseded_by_submission_id`:** recommended, added to make the active chain explicit and queryable in one direction without requiring a join to find "is there a child." Set on the parent at the moment a child is created (`parent.superseded_by_submission_id = child.submission_id`), atomically with the child's creation. This also structurally prevents branching at the database level if paired with the `UNIQUE` constraint above — an attempt to create a second child would violate uniqueness on `resubmission_of_submission_id`.

### 5.8 Archival eligibility — tightened

Archival must never hide unresolved work. **Eligible for archival:**
- `rejected` submissions (terminal, nothing pending).
- `approved` submissions with `disposition_status = completed`.
- `returned` parent submissions that already have a replacement child (`superseded_by_submission_id IS NOT NULL`) — the parent is historical, not active.

**Not eligible for archival:** `pending_review`, `in_review` (actively claimed or queued), and `approved` submissions with `disposition_status` of `pending`, `in_progress`, or `failed` — these represent unresolved or in-flight work and must remain in active views regardless of age.

**Actor reference, corrected to match DEC000001 v3's standard:** `archived_by_user_id` (stable reference), optional `archived_by_display_name` snapshot, `archived_at`, `archive_reason`. No `archived_by text` free-text field, correcting the same class of issue DEC000001 v3 fixed for claims.

### 5.9 Downstream linkage entity — left open, not silently renamed

v2 recommended renaming `resulting_intake_session` → `resulting_intake_packet_id` without checking what entity it should actually reference. Checked this revision: the schema defines **two distinct entities** that could plausibly be meant —

- `evidence.intake_sessions` (`session_id`) — a log of AI/human intake runs, used by AI Usage OS for cost/quality attribution (migration `002_evidence_tables.sql`).
- `operations.intake_packets` (`packet_id`) — the structured, reviewable artifact governed by DEC000001.

These are not currently linked to each other in the schema (no `session_id` column exists on `intake_packets`). The column name `resulting_intake_session` could historically have meant either, and this decision does not have enough information to resolve which was intended, or whether both should be captured.

**Recommendation: do not rename the column until this is resolved.** The operationally load-bearing link for this decision's purposes — since it is what `submission.convert_to_intake` produces and what a reviewer would actually want to trace to — is most likely the **Intake Packet** (`operations.intake_packets.packet_id`), since that is the entity with its own review/approve/reject lifecycle (DEC000001) that a routed submission would flow into. Whether a separate `resulting_intake_session_id` should also be captured for cost/quality attribution is a related but distinct schema question, deferred to whoever owns AI Usage OS's cost-tracking requirements — flagged as an open question in §7, not decided here.

**Idempotency requirement, independent of the entity question:** the downstream-processing workflow (`submission.convert_to_intake`, and by extension `.route_to_identity_review`/`.escalate_exception`) must be idempotent. A retry (e.g., after a transient failure) must not create a duplicate downstream record. `submission_id` should serve as, or contribute to, the idempotency key for whatever downstream creation call is made. A failed attempt sets `disposition_status = failed` without altering the `status = approved` review outcome — the approval stands regardless of downstream failure, matching DEC000001 v3's parallel rule for packet ingestion. Every attempt (success or failure) is audited — actor/system, timestamp, outcome.

### 5.10 `resulting_evidence_summary` — renamed to a neutral term

The current name implies the submission itself directly produced evidence, which §5.3 explicitly closes as a normal path. **Recommendation: rename to `resolution_summary` (jsonb).** It holds a structured/human-readable note applicable across all four disposition types — not just intake-routed ones — e.g. `no_action`'s documented reason, `identity_review`'s routing note, `exception_escalation`'s escalation note, or `intake_required`'s downstream-linkage confirmation. This keeps the field meaningful even for dispositions that never touch `evidence.*` at all.

## 6. Recommended canonical model (final, v3)

```
status (conceptually "review status"; column name unchanged):
    pending_review → in_review (claim)
    in_review → pending_review (release)
    in_review → returned (return; reason required; terminal for this row)
    in_review → approved (approve; disposition_type required)
    in_review → rejected (reject; reason required)

disposition_status:  unassessed | pending | in_progress | completed | failed
disposition_type:    intake_required | identity_review | no_action | exception_escalation

Resubmission (separate rows, not a status loop):
    parent.status = returned (permanent)
    child.status = pending_review
    child.resubmission_of_submission_id = parent.submission_id
    parent.superseded_by_submission_id = child.submission_id

Attributes/relationships, not statuses:
    claimed_by_user_id, claimed_by_display_name, claimed_at
    archived_at, archived_by_user_id, archived_by_display_name, archive_reason
    resolution_summary (renamed from resulting_evidence_summary)
    resulting_intake_packet_id (entity question open — see §5.9; do not rename resulting_intake_session yet)
```

## 7. Founder decisions required (concise — true policy choices only)

Mechanical/architectural corrections above (disposition naming and OS routing, claim mechanism, resubmission chain model, archival eligibility rules, command split) are treated as resolved by this revision, not re-listed as open questions. What remains genuinely open:

1. **Confirm the disposition routing table in §5.2** — in particular, that identity/contact changes should route to the Blueprint's existing Identity Review Queue rather than being edited directly by the submission reviewer, closing the path the live schema comment currently implies is normal.
2. **Confirm `exception_escalation` routes to a Governance/Knowledge OS correction workflow that does not yet exist** — this decision creates the exit point (`submission.escalate_exception`) but does not design that workflow; a future decision must.
3. **Resolve the `resulting_intake_session` entity question** (§5.9): does downstream linkage need `resulting_intake_packet_id`, `resulting_intake_session_id`, or both? Requires input from whoever owns AI Usage OS cost/quality tracking, not just this decision's scope.
4. **Confirm the exact source of stable user identity** for `claimed_by_user_id`/`archived_by_user_id` — same open question as DEC000001 §7 decision 5, shared across both records.
5. **Confirm no changes to `operations.partner_submissions`** (carried forward from v2, unchanged).

## 8. Risks, guardrails, validation criteria, revisit triggers

**Risks:**
- Closing the "direct evidence edit" path (§5.3) removes a capability the live schema comment currently implies coordinators have, even though no code has ever exercised it (no API exists). If any manual, out-of-band process currently relies on that comment as documentation for a real practice, this should be surfaced before implementation.
- The resubmission chain (§5.7) requires queue views to correctly show only leaf (non-superseded) submissions as "active" — an oversight here could either hide corrected resubmissions or double-count a parent and its child.

**Guardrails:**
- No implementation proceeds until Founder decisions 1-5 above are made.
- `submission.restaurant_update.approve` must reject any call that omits `disposition_type`.
- `submission.convert_to_intake` must reject any submission whose `disposition_type != intake_required`.

**Validation criteria:**
- No submission can reach `status = approved` with `disposition_status = unassessed` — the approve command's atomicity guarantees this.
- Every resubmission chain has exactly one active leaf per original parent, verifiable by checking no submission both has a non-null `resubmission_of_submission_id` and is pointed to by another submission's `superseded_by_submission_id` other than its own direct parent.
- No submission with `disposition_status ∈ {pending, in_progress, failed}` appears in an archived state.

**Revisit triggers:**
- If the exception-escalation workflow is designed later and turns out to need its own richer status model, that becomes its own Decision Record, not a reopening of this one.
- If `partner_submissions` is later found to need the same disposition separation, that is also a new, separate decision (per v2 §13, unchanged).
