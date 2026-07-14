# DEC000002 — Canonical Restaurant Update Submission State Machine

**Status:** draft v4 — ready for Founder approval (final targeted refinements to v3)
**Decision basis:** architectural_requirement, compliance_or_risk_control
**Decision dependencies:** none (foundational record, sibling to DEC000001)
**Registry impact:** governs `submission.restaurant_update.*`, `submission.convert_to_intake`, `submission.route_to_identity_review`, `submission.escalate_exception`, and the removal of `submission.close_no_action` as a standalone command (see §5.5)

**Revision note:** v3 is approved in direction, including its core separation of review status from disposition. This revision makes eleven targeted refinements only — the broader linear-status-vs-separate-disposition comparison is not reopened. Refinements: removing display-name snapshots from all actor fields (matching DEC000001 v4), giving `exception_escalation` a single owner rather than two, distinguishing routing completion from downstream-work completion in the `disposition_status` definitions, making disposition selection atomic with approval explicit end-to-end, defining each routing command as a discrete handoff with preconditions and effects, resolving downstream linkage to explicit nullable foreign keys, tightening the resubmission-chain validation rule to unambiguous conditions, precisely defining archival eligibility, specifying full append-only audit event coverage, and strengthening idempotency to a defined failure-safe sequence rather than a claim of full atomicity. Sections 1-3 carry forward from v3 unchanged; §5 onward is rewritten.

---

## 1. Competing versions, side by side (unchanged from v3)

| Source | States (in order) | Notes |
|---|---|---|
| Blueprint §5b (generic) | `pending_review → in_review → approved → returned → rejected → converted` | Generic "Submission" row. |
| Blueprint §5i (Restaurant Update Submission table) | `received → pending_review → in_review → accepted → rejected → archived` | Uses `accepted`, not `approved`; no `converted`. |
| Live DB — `operations.restaurant_update_submissions` | `status` CHECK: `pending_review, in_review, approved, returned, rejected` | Column comment: *"approved does NOT automatically write to evidence — reviewer must take deliberate action (trigger Intake session or direct edit)."* Treated as E1 evidence of prior implementation intent, not governing authority over the Blueprint's evidence boundary — see DEC000002 v3 §5.3, unchanged this revision. |
| Live DB — `operations.partner_submissions` (sibling) | `status` CHECK includes `converted` | Not treated as binding precedent for this table — unchanged from v2/v3. |

No API or UI exists for either submissions table.

**Carried from v3:** the Blueprint independently documents a real, already-governed routing destination for restaurant-submitted identity/contact changes — the **Identity Review Queue**, part of Restaurant Operations OS: *"Restaurant-submitted changes land in pending review. No restaurant-submitted value writes directly to evidence.restaurants. The submission enters the Identity Review Queue with status `pending_restaurant_submission`."* (Blueprint, Identity/Enrichment section).

## 2. Sibling-table evidence (unchanged from v3)

`partner_submissions`'s `converted` status and single-target CRM conversion remain treated as a different downstream shape from this entity's multi-path resolution, not binding precedent. No change to `partner_submissions` is recommended by this decision (confirmed again in §7 item 9).

## 3. Phase 5 commands that depend on this decision (final command set)

| Command | Registry status | This revision's treatment |
|---|---|---|
| `submission.restaurant_update.view` (CMD000024, missing) | unchanged | No change. |
| `submission.restaurant_update.claim`, `.release`, `.return`, `.approve`, `.reject` | not in registry today | Replace the single `.review` entry (CMD000025), per v3 §5.5, unchanged this revision. `.approve` tightened per §5.4 below. |
| `submission.convert_to_intake` (CMD000026, missing) | preconditions tightened | Handles the `intake_required` disposition only. See §5.5. |
| `submission.route_to_identity_review` | not in registry today | Preconditions/effects defined. See §5.5. |
| `submission.escalate_exception` | not in registry today | Preconditions/effects defined; single owner clarified. See §5.2, §5.5. |
| `submission.close_no_action` | **removed as a standalone command this revision** | Folded into `.approve`'s internal completion logic. See §5.5. |

## 4. Blueprint role/ownership note (new — supports §5.2)

Per the Blueprint's one-owner-per-entity rule, this record identifies exactly one owning OS at each stage of a submission's life: **Restaurant Operations OS** owns the submission row itself, end to end, regardless of disposition. Downstream objects created by routing are owned by whichever OS the disposition hands off to (Intake OS, Restaurant Operations OS's own Identity Review Queue, or Governance OS's exception-request record) — never jointly.

## 5. Resolution of each targeted correction

### 5.1 Display-name snapshots removed

v3 (mirroring DEC000001 v3) included `claimed_by_display_name` and `archived_by_display_name` snapshot fields. **Both are removed in this revision.** The canonical model carries only stable references:

- `claimed_by_user_id`, `claimed_at`
- `archived_by_user_id`, `archived_at`

Display names are resolved from the user directory at render time, matching DEC000001 v4 §5.3 exactly. No table in this record contains a `_display_name` column.

### 5.2 One owner per disposition — `exception_escalation` corrected

v3's routing table listed `exception_escalation`'s owning OS as "Governance OS / Knowledge OS," which conflicts with the Blueprint's one-owner rule. **Corrected:**

- `submission.escalate_exception` creates an exception request **owned solely by Governance OS**.
- Governance OS may, at its own discretion and through its own workflow, later route an approved correction action to Knowledge OS — that handoff is internal to Governance's process, not a joint ownership of the exception record.
- The submission row itself remains owned by Restaurant Operations OS throughout, per §4 — escalating a disposition does not transfer ownership of the submission.
- Knowledge OS does not jointly own the exception request at any point visible to this decision.

Revised routing table:

| `disposition_type` | Routes to | Owning OS (sole) | Command |
|---|---|---|---|
| `intake_required` | Intake Packet | Intake OS (DEC000001) | `submission.convert_to_intake` |
| `identity_review` | Identity Review Queue | Restaurant Operations OS | `submission.route_to_identity_review` |
| `no_action` | No handoff | Restaurant Operations OS (closes within `.approve` itself) | none — see §5.5 |
| `exception_escalation` | Exception request | Governance OS | `submission.escalate_exception` |

### 5.3 `disposition_status` — routing completion vs. downstream-work completion

v3 left `in_progress`/`completed` under-specified enough that "a downstream record was created" could be misread as "done." This revision defines each value precisely:

- **`unassessed`** — no disposition selected yet (pre-approval default).
- **`pending`** — disposition selected at approval; downstream handoff not yet created.
- **`in_progress`** — downstream record or queue item has been created and linked, but the owning OS has not yet reported a terminal outcome. **A submission does not reach `completed` merely because a downstream record was created** — `identity_review`, `intake_required`, and `exception_escalation` all pass through `in_progress` and stay there until the owning OS reports resolution.
- **`completed`** — either the downstream workflow reports a terminal successful outcome (owning OS confirms resolution), or `disposition_type = no_action` was approved (no downstream workflow exists to wait on).
- **`failed`** — handoff creation failed, or the downstream owning OS reported a terminal failure; requires retry or manual intervention.

**Completion-update mechanism, deliberately deferred:** whether the `in_progress → completed`/`failed` transition is event-driven (owning OS calls back), manually reconciled (a Restaurant Operations OS user checks and marks it), or system-polled (periodic status check against the owning OS) is an implementation-mechanism choice this decision does not make. **What is fixed by this decision is the semantic rule**: only the owning OS's own terminal signal — however delivered — may move a routed disposition out of `in_progress`. No routing command itself may set `completed` for `identity_review`, `intake_required`, or `exception_escalation`.

### 5.4 Disposition selection — atomic with approval, end to end

`submission.restaurant_update.approve` requires, as parameters:
- `disposition_type`
- approval notes/reason (required for reject; recommended, not decision-blocking, for approve unless a future policy tightens this)
- acting reviewer identity (the claimant, per §5.6)

**In one governed, atomic operation, `.approve`:**
1. Transitions `status`: `in_review → approved`.
2. Clears the active claim (`claimed_by_user_id`, `claimed_at`).
3. Writes the reviewer identity into append-only event history (§5.9) — the claim fields are cleared, but the deciding reviewer is never lost.
4. Sets the derived initial `disposition_status`, per this table:

| `disposition_type` | Derived `disposition_status` |
|---|---|
| `no_action` | `completed` |
| `intake_required` | `pending` |
| `identity_review` | `pending` |
| `exception_escalation` | `pending` |

No approved submission may remain `disposition_status = unassessed` — the atomicity of step 4 with steps 1-3 guarantees this structurally, not just by convention.

### 5.5 Routing commands — discrete handoffs, explicit preconditions and effects

**`submission.convert_to_intake`**
- Preconditions: `status = approved`; `disposition_type = intake_required`; `disposition_status ∈ {pending, failed}`.
- On success: creates or links the canonical Intake downstream object (per DEC000001, subject to that record's own open entity question — see §5.6 below); sets `disposition_status = in_progress`; records the downstream linkage; emits an auditable handoff event (§5.9).

**`submission.route_to_identity_review`**
- Preconditions: `status = approved`; `disposition_type = identity_review`; `disposition_status ∈ {pending, failed}`.
- On success: creates or links an Identity Review Queue item, owned by Restaurant Operations OS (§5.2); sets `disposition_status = in_progress`; records the downstream linkage; emits an auditable handoff event.

**`submission.escalate_exception`**
- Preconditions: `status = approved`; `disposition_type = exception_escalation`; `disposition_status ∈ {pending, failed}`.
- On success: creates or links a Governance-owned exception request (§5.2); sets `disposition_status = in_progress`; records the downstream linkage; emits an auditable handoff event.

**`submission.close_no_action` — removed as a standalone command.** Because `.approve` with `disposition_type = no_action` already sets `disposition_status = completed` in the same atomic operation (§5.4), a separate second command would force a redundant second click to finish a disposition that is already finished. This revision removes it from the registry proposal entirely rather than merely deprecating it — there is no operator-facing gap it would fill. If an internal system hook is ever needed at that moment (e.g., to fire a notification), it lives inside `.approve`'s own transaction, not as a separately invocable command.

All three retained routing commands (`convert_to_intake`, `route_to_identity_review`, `escalate_exception`) share the same precondition shape and the same three-part success effect (create/link → set `in_progress` → audit), differing only in which downstream object and owning OS they target.

### 5.6 Claim ownership for `in_review` (display-name field removed, otherwise unchanged from v3)

- **Claim** (`submission.restaurant_update.claim`): atomic conditional update, `pending_review → in_review`, requires `claimed_by_user_id IS NULL`, sets `claimed_by_user_id`, `claimed_at`. Returns no row if already claimed or state changed.
- **Release** (`submission.restaurant_update.release`): `in_review → pending_review`, clears claim fields. Allowed by the current claimant; administrator override allowed with a required reason.
- **Decision commands clear the claim atomically as part of the same transition:** `.return`, `.approve`, `.reject` each, in one operation, move `status` out of `in_review`, clear the claim fields, and write the reviewer identity into append-only event history.
- Same open question as DEC000001 §7 decision 9: the exact reference target for `claimed_by_user_id` depends on identifying the current authentication/user model.

### 5.7 Resubmission lifecycle — immutable parent, atomic child creation

Unchanged in model from v3, restated precisely per instruction:

- Parent remains `returned` (terminal for that row — it never moves again).
- Child is created fresh at `pending_review`, containing the corrected payload.
- Parent payload is immutable — no row's `payload_json`/`description` is ever edited in place.
- Child references exactly one parent, via `resubmission_of_submission_id`.
- Each parent may have **at most one** direct child — enforced via a `UNIQUE` constraint on `resubmission_of_submission_id` (excluding nulls).
- Only the newest leaf in a chain is eligible for active review.

**Atomicity requirement:** the creation of the child row and the assignment of both `child.resubmission_of_submission_id` and `parent.superseded_by_submission_id` must occur in a single transaction. A partial write (child created but parent not marked superseded, or vice versa) would break the chain's integrity guarantees in §5.8.

### 5.8 Resubmission-chain validation — corrected to unambiguous conditions

v3's validation sentence relied on an ambiguous condition (whether a row is both a child and is pointed to by its own parent) that middle nodes in any valid multi-revision chain would naturally satisfy, making it useless as a distinguishing check. **Replaced with conditions that directly prove a valid linear chain:**

- No submission may reference itself as parent or successor (`resubmission_of_submission_id != submission_id`, `superseded_by_submission_id != submission_id`).
- Each child has **at most one** parent (structural — `resubmission_of_submission_id` is a single nullable column, not a set).
- Each parent has **at most one** direct child (`UNIQUE` constraint on `resubmission_of_submission_id`, per §5.7).
- Parent and child must reference the **same canonical restaurant identity** (matching DEC000001 v4 §5.6's identity rule: same `restaurant_id`, or same `restaurant_external_id` if `restaurant_id` is null on either).
- Cycles are prohibited — provable because the two constraints above force a strict tree with branching factor ≤ 1 at every node, which cannot contain a cycle.
- Only rows with `superseded_by_submission_id IS NULL` are **active leaves**.
- Only active leaves may be claimed or reviewed — `submission.restaurant_update.claim` must reject any attempt against a row where `superseded_by_submission_id IS NOT NULL`.

### 5.9 Archival — eligibility defined precisely

**Eligible for archival:**
- `rejected` submissions.
- `approved` submissions with `disposition_status = completed`.
- `returned` parent submissions that already have a replacement child (`superseded_by_submission_id IS NOT NULL`).

**Not eligible for archival:**
- `pending_review`.
- `in_review`.
- `approved` submissions with `disposition_status ∈ {pending, in_progress, failed}`.
- `returned` submissions still awaiting a corrected child (`superseded_by_submission_id IS NULL`) — **unless a separate, future abandonment decision defines terms for archiving an uncorrected return**, which this decision does not attempt.

**Archival behavior:**
- Removes the record from default operational views.
- Never changes the submission's review outcome.
- Never deletes payload or audit history.
- Requires an actor (`archived_by_user_id`, stable reference — no display-name snapshot, per §5.1) and a `archive_reason` for any manual archival.
- No automatic archival schedule is approved by this decision.

### 5.10 Append-only audit coverage — fully specified

**`operations.restaurant_update_submission_events`** (append-only), covering:

`claim`, `release`, `return`, `child_resubmission_created`, `approve`, `reject`, `disposition_selected`, `disposition_handoff_attempted`, `disposition_handoff_succeeded`, `disposition_handoff_failed`, `downstream_completion_received`, `archive`.

Each event row contains:
- `submission_id`
- `event_type`
- `actor_user_id` (or a system identifier for automated events — e.g., a downstream-callback-driven `downstream_completion_received`)
- prior and resulting `status` (review status), where applicable
- prior and resulting `disposition_status`, where applicable
- `reason` (nullable; required for `return`, `reject`, administrative `release` override, manual `archive`)
- downstream entity reference, where applicable (per §5.11's linkage fields)
- `created_at`
- `metadata jsonb` (event-specific detail)

The original submission payload remains on the immutable row (§5.7) — a separate payload-revision table, analogous to DEC000001's `intake_packet_revisions`, is **not required for this entity**, since this entity's correction mechanism is a new child row, not an in-place edit.

### 5.11 Downstream linkage — explicit nullable foreign keys, entity question left open

v3 left the `resulting_intake_session` entity question open rather than silently renaming it; this revision keeps that question open but defines the linkage *requirement* more precisely and picks a storage shape.

**Two options evaluated:**

- **A. Purpose-specific nullable foreign keys** — one nullable column per downstream entity type (`resulting_intake_packet_id`, `resulting_intake_session_id`, `identity_review_item_id`, `exception_request_id`). Since `disposition_type` already acts as the discriminator (exactly one of these is populated per submission, matching whichever disposition was selected), this option doesn't need a separate type column to disambiguate — the schema is self-documenting, each FK can carry its own real referential-integrity constraint to its target table, and no generic-table join is needed to answer "what did this submission link to."
- **B. A generic typed downstream-link table** (`submission_id`, `downstream_entity_type`, `downstream_entity_id`, `created_at`) — more extensible if a submission could someday link to more than one downstream object, or if new disposition types are added frequently, but `downstream_entity_id` cannot carry a real foreign-key constraint (it must reference multiple possible tables), pushing referential integrity into application code, and it requires a join plus a type-string match to retrieve what a purpose-specific column would give directly.

**Recommendation: Option A (explicit nullable foreign keys).** For Phase 5's scope — four known disposition types, one downstream object per submission by construction (§5.4's derived-status model assumes a single handoff per approved submission) — the generic table's extensibility isn't needed yet, and its loss of real FK constraints is a real cost, not a neutral tradeoff. This matches the instruction to prefer explicit foreign keys over a generic abstraction when two or three (here, four) explicit columns are clearer. If a genuine need for multiple simultaneous downstream links per submission emerges later, that is itself a signal to revisit this decision, not a reason to over-build now.

**Entity question intentionally still open** (unchanged from v3, carried into this recommendation): whether `intake_required` should populate `resulting_intake_packet_id`, `resulting_intake_session_id`, or both, is not resolved here — that is DEC000001's own open question (DEC000001 §5.9, §7 item 9 shared reference), not something this decision can settle unilaterally. `resulting_intake_session` is **not** renamed until that is resolved.

`resolution_summary` (renamed from `resulting_evidence_summary` in v3, unchanged this revision) remains the structured/human-readable disposition note, populated regardless of which downstream link field is used.

### 5.12 Idempotency — strengthened to a defined failure-safe sequence

v3 stated idempotency as a requirement without a concrete mechanism; this revision defines one, while explicitly not overclaiming cross-service atomicity that cannot actually be guaranteed:

- **Idempotency key:** `submission_id` combined with `disposition_type` (a submission can only ever be routed once per its single selected disposition, so this pair is sufficient and stable across retries).
- **Failure-safe sequence** (not claimed to be atomic across the network boundary to the owning OS, which would be an unenforceable guarantee):
  1. The routing command calls the downstream owning OS's creation/handoff endpoint, passing the idempotency key.
  2. If the downstream call succeeds, the routing command writes the downstream linkage (§5.11) and sets `disposition_status = in_progress` in one local transaction.
  3. If the downstream call succeeds but the local write in step 2 fails (e.g., a crash between the two), a retry of the routing command must, using the same idempotency key, have the downstream owning OS **return or reuse the already-created object** rather than create a duplicate — this is a requirement on the downstream owning OS's own idempotent-handling contract, not something this submission-side decision can enforce unilaterally, but it is a precondition this decision requires before any routing command is built.
  4. If the downstream call itself fails, `disposition_status = failed` is set locally; `status = approved` is preserved unchanged — the approval stands regardless of downstream failure.
  5. Every attempt, successful or failed, is audited (`disposition_handoff_attempted`/`_succeeded`/`_failed`, per §5.10), including timestamps, so repeated retries are individually visible even though they share one idempotency key.

## 6. Recommended canonical model (final, v4)

```text
pending_review
    ↓ claim
in_review
    ├── release → pending_review
    ├── return → returned
    │              ↓ corrected child created
    │          child starts pending_review
    ├── reject → rejected
    └── approve + select disposition → approved
                                           ↓
                                disposition processed separately
```

**Disposition model:**

```text
disposition_status:
unassessed
pending
in_progress
completed
failed

disposition_type:
intake_required
identity_review
no_action
exception_escalation
```

**Relationships and attributes, not statuses:**

```text
claimed_by_user_id
claimed_at

resubmission_of_submission_id
superseded_by_submission_id

archived_at
archived_by_user_id
archive_reason

resolution_summary

resulting_intake_packet_id      (nullable FK; entity question re: intake_required open, §5.11)
resulting_intake_session_id     (nullable FK; entity question re: intake_required open, §5.11)
identity_review_item_id         (nullable FK)
exception_request_id            (nullable FK)
```

No `_display_name` field exists on any of these, per §5.1.

## 7. Founder decisions required (final — policy choices only)

1. **Approve the five review statuses:** `pending_review`, `in_review`, `returned`, `approved`, `rejected`.
2. **Approve the separate disposition model and its five statuses:** `unassessed`, `pending`, `in_progress`, `completed`, `failed`, with the precise semantics in §5.3 (routing completion ≠ downstream-work completion).
3. **Approve the four disposition types and their one-owner routing boundaries:** `intake_required` (Intake OS), `identity_review` (Restaurant Operations OS), `no_action` (closes within Restaurant Operations OS's own `.approve`), `exception_escalation` (Governance OS, sole owner — §5.2).
4. **Approve immutable parent submissions with linked child resubmissions**, per §5.7-§5.8.
5. **Approve splitting the broad review command into `claim`, `release`, `return`, `approve`, `reject`**, and removing `submission.close_no_action` as a standalone command per §5.5.
6. **Approve archival as a separate attribute set**, with the eligibility rules in §5.9.
7. **Choose the downstream-link storage model:** explicit nullable foreign-key fields (recommended, §5.11) or a typed generic downstream-link table.
8. **Confirm the exact source of stable user identity** for `claimed_by_user_id`/`archived_by_user_id` once the current authentication/user schema is inspected — same open question as DEC000001 §7 decision 9, shared across both records.
9. **Confirm that `operations.partner_submissions` remains outside the scope of this decision** — no changes proposed to it.

## 8. Risks, guardrails, validation criteria, revisit triggers

**Risks:**
- The completion-update mechanism (§5.3) is deliberately left as an implementation choice; if no owning OS ever reliably reports back, `in_progress` submissions could accumulate indefinitely with no path to `completed`/`failed` — the semantic rule closes the "false completion" risk but does not by itself close the "stuck forever" risk, which implementation must address operationally.
- The idempotency guarantee in §5.12 depends on each downstream owning OS honoring the idempotency key on its own side; this decision can require it as a precondition but cannot enforce it from the submission side alone.
- Removing `submission.close_no_action` (§5.5) assumes no UI already depends on it as a separate step; if a UI mockup or in-flight implementation assumed a two-step no-action flow, that needs to be caught before build.

**Guardrails:**
- No implementation proceeds until Founder decisions 1-9 above are made.
- `submission.restaurant_update.approve` must reject any call that omits `disposition_type`.
- Each routing command must reject any call where its stated preconditions (§5.5) are not met, including the `disposition_status ∈ {pending, failed}` guard that prevents re-routing an already-`in_progress` or `completed` disposition.
- `submission.restaurant_update.claim` must reject any attempt against a non-active-leaf row, per §5.8.

**Validation criteria:**
- No submission can reach `status = approved` with `disposition_status = unassessed`.
- No submission reaches `disposition_status = completed` for a routed disposition (`intake_required`, `identity_review`, `exception_escalation`) without a recorded `downstream_completion_received` event.
- Every resubmission chain has exactly one active leaf per original parent, verifiable via the conditions in §5.8.
- No submission with `disposition_status ∈ {pending, in_progress, failed}` appears in an archived state.
- No table in this record contains a `_display_name` column.

**Revisit triggers:**
- If the exception-escalation workflow is designed later and turns out to need its own richer status model, that becomes its own Decision Record, not a reopening of this one.
- If a submission is ever found needing more than one simultaneous downstream link, that is a signal to revisit §5.11's Option A recommendation, not a reason to have over-built Option B now.
- If `partner_submissions` is later found to need the same disposition separation, that is also a new, separate decision.
