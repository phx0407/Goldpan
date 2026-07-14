# DEC000002 — Canonical Restaurant Update Submission State Machine

**Status:** final draft — ready for Founder approval (v4.1 mechanical and integrity correction pass over v4)
**Decision basis:** architectural_requirement, compliance_or_risk_control
**Decision dependencies:** none (foundational record, sibling to DEC000001)
**Registry impact:** governs `submission.restaurant_update.*` (including new `.resubmit`), `submission.convert_to_intake`, `submission.route_to_identity_review`, `submission.escalate_exception`, and the removal of `submission.close_no_action` as a standalone command (see §5.5)

**Revision note:** v4 is approved architecturally. This is a v4.1 mechanical and integrity correction pass only — no review/disposition model, routing boundary, ownership decision, or child-submission approach is reopened. Eleven corrections: (1) event actors corrected to `actor_type`/`actor_id`, mirroring DEC000001 v4.1 §5.8, so system-generated events no longer require a human user ID; (2) the resubmission-chain cycle-prevention claim is corrected — branching factor ≤ 1 alone does not prove acyclicity, so an explicit ancestry rule is added; (3) the previously-undefined child-resubmission creation is formalized as a discrete command, `submission.restaurant_update.resubmit`, added to §3 and §5.7; (4) each proposed downstream foreign key is labeled by implementation-status maturity rather than presented uniformly as ready; (5) the "one downstream object per disposition" contradiction between §5.4 and §6 is resolved; (6) a `failure_stage` field is added to distinguish where in the handoff sequence a failure occurred; (7) downstream-completion authority is specified more precisely; (8) `no_action` approval semantics are tightened; (9) archival of a `returned` parent is clarified against an in-flight child; (10) a full section-reference, terminology, and `_display_name`-remnant consistency pass; (11) status updated to reflect Founder-approval readiness. Sections 1-4 carry forward from v4 unchanged; §5 is amended in place; §6-§8 updated to match.

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
| `submission.restaurant_update.resubmit` (new this revision) | not in registry today — Command Registry correction/addition requiring Founder approval | Formalizes child-resubmission creation as a discrete command, previously only described narratively. See §5.7. |
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
- **`failed`** — handoff creation failed, or the downstream owning OS reported a terminal failure; requires retry or manual intervention. **`failure_stage` (added this revision)** records *where* in the sequence the failure occurred — `handoff_call` (the routing command's call to the downstream owning OS never succeeded), `local_write` (the downstream call succeeded but this record's own linkage write, §5.12 step 2/3, failed), or `downstream_terminal` (the downstream owning OS itself later reported a terminal failure after successfully accepting the handoff). This distinction matters operationally: a `handoff_call` failure is safely retryable with no risk of a duplicate downstream object; a `downstream_terminal` failure means a downstream object exists and any retry must address it there, not merely re-attempt the handoff.

**Completion-update mechanism, deliberately deferred:** whether the `in_progress → completed`/`failed` transition is event-driven (owning OS calls back), manually reconciled (a Restaurant Operations OS user checks and marks it), or system-polled (periodic status check against the owning OS) is an implementation-mechanism choice this decision does not make. **What is fixed by this decision is the authority rule, specified precisely this revision:**

1. Only the owning OS's own terminal signal — however delivered — may move a routed disposition out of `in_progress`. No routing command itself may set `completed` for `identity_review`, `intake_required`, or `exception_escalation`.
2. The owning OS's terminal signal must be capable of reporting **both** success and failure outcomes — a mechanism that can only signal success and silently never responds on failure does not satisfy this decision's guardrails (§8).
3. `downstream_completion_received` (§5.10) is the sole audit record of completion authority having been exercised. A Restaurant Operations OS user manually setting `disposition_status = completed` or `failed` without a corresponding `downstream_completion_received`/`disposition_handoff_failed` event is not an ordinary completion path — it is a manual override, requires a mandatory reason, and must be logged as such, distinctly from an authoritative downstream signal.
4. If ownership of the underlying work later moves between OSes after handoff (for example, Governance OS routing an approved exception internally to Knowledge OS per §5.2), only the OS holding sole ownership of that work **at the time of resolution** may issue the terminal signal back to this submission — an internal downstream handoff does not create two OSes with completion authority over the same submission.
5. A routed disposition has exactly one authoritative completion source at any given time; this decision does not define a mechanism for reconciling conflicting signals from more than one purported source, because §4's one-owner rule structurally prevents more than one from existing.

### 5.4 Disposition selection — atomic with approval, end to end

`submission.restaurant_update.approve` requires, as parameters:
- `disposition_type`
- approval notes/reason (required for reject; recommended, not decision-blocking, for approve unless a future policy tightens this)
- acting reviewer identity (the claimant, per §5.6)

**In one governed, atomic operation, `.approve`:**
1. Transitions `status`: `in_review → approved`.
2. Clears the active claim (`claimed_by_user_id`, `claimed_at`).
3. Writes the reviewer identity into append-only event history (§5.10, corrected reference this revision — was miscited to §5.9 in v4) — the claim fields are cleared, but the deciding reviewer is never lost.
4. Sets the derived initial `disposition_status`, per this table:

| `disposition_type` | Derived `disposition_status` |
|---|---|
| `no_action` | `completed` |
| `intake_required` | `pending` |
| `identity_review` | `pending` |
| `exception_escalation` | `pending` |

No approved submission may remain `disposition_status = unassessed` — the atomicity of step 4 with steps 1-3 guarantees this structurally, not just by convention.

**`no_action` tightened this revision:** because `no_action` reaches `disposition_status = completed` immediately, with no downstream workflow to later supply a record of *why* — the ordinary safety net for other dispositions (§5.10's `downstream_completion_received` event) never exists for this path. To prevent `no_action` from becoming an unexplained dead end, `.approve` with `disposition_type = no_action` requires `resolution_summary` (§5.11) as a **mandatory**, not merely recommended, parameter. This is the one case where `resolution_summary` is decision-blocking rather than optional, precisely because it is the only record this disposition will ever produce.

### 5.5 Routing commands — discrete handoffs, explicit preconditions and effects

**`submission.convert_to_intake`**
- Preconditions: `status = approved`; `disposition_type = intake_required`; `disposition_status ∈ {pending, failed}`.
- On success: creates or links the canonical Intake downstream object (per DEC000001, subject to that record's own open entity question — see §5.11 below, corrected reference this revision — was miscited to §5.6 in v4); sets `disposition_status = in_progress`; records the downstream linkage; emits an auditable handoff event (§5.10, corrected reference this revision — was miscited to §5.9 in v4).

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

**`submission.restaurant_update.resubmit` — formalized as a discrete command this revision.** Prior drafts described child-resubmission creation only narratively; it is now a first-class command in the registry proposal (§3), matching the treatment every other transition in this record already receives:

- **Preconditions:** the target row (`submission_id` supplied) has `status = returned`; `superseded_by_submission_id IS NULL` on that row (it is not already superseded by an earlier resubmission); the caller supplies the corrected `payload_json`/`description` for the new child.
- **Effects, in one transaction (per the atomicity requirement above):** creates a new submission row at `status = pending_review` with `resubmission_of_submission_id` set to the parent; sets `parent.superseded_by_submission_id` to the new child's ID; emits a `resubmit` event (§5.10) on the parent and an implicit creation record on the child.
- **Actor:** who may call `resubmit` is a separate, narrower question from who may claim/review a submission — this decision does not assume the original submitter and the resubmitting actor are the same identity, and does not restrict `resubmit` to a specific Blueprint role beyond noting it is not a Governance-side action (Governance's role in this record is reviewing, per §5.6, not resubmitting on the submitter's behalf). Which actor/role may call `resubmit` in practice is left to the Blueprint's existing submission-origination model, not redefined here.
- **Failure mode:** if the precondition check fails (row not `returned`, or already superseded), the command returns no row / an explicit precondition-failure error — never a silent no-op — mirroring the claim command's failure contract in §5.6.

### 5.8 Resubmission-chain validation — corrected to unambiguous conditions, cycle-prevention claim fixed

v3's validation sentence relied on an ambiguous condition (whether a row is both a child and is pointed to by its own parent) that middle nodes in any valid multi-revision chain would naturally satisfy, making it useless as a distinguishing check. **Replaced with conditions that directly prove a valid linear chain:**

- No submission may reference itself as parent or successor (`resubmission_of_submission_id != submission_id`, `superseded_by_submission_id != submission_id`).
- Each child has **at most one** parent (structural — `resubmission_of_submission_id` is a single nullable column, not a set).
- Each parent has **at most one** direct child (`UNIQUE` constraint on `resubmission_of_submission_id`, per §5.7).
- Parent and child must reference the **same canonical restaurant identity** (matching DEC000001 v4 §5.6's identity rule: same `restaurant_id`, or same `restaurant_external_id` if `restaurant_id` is null on either).
- Only rows with `superseded_by_submission_id IS NULL` are **active leaves**.
- Only active leaves may be claimed or reviewed — `submission.restaurant_update.claim` must reject any attempt against a row where `superseded_by_submission_id IS NOT NULL`.

**Cycle-prevention claim corrected this revision.** v4 stated that branching factor ≤ 1 at every node (the two `UNIQUE`/single-column constraints above) was sufficient on its own to prove the chain acyclic. **That claim is incorrect and is withdrawn.** A chain with branching factor exactly one at every node can still form a cycle — for example, three rows A → B → C → A, each satisfying "at most one parent" and "at most one child" individually, while the set as a whole loops. Branching-factor limits constrain shape (no forking, no merging) but do not by themselves exclude a ring.

**Corrected mechanism — `resubmit` (§5.7) must perform an ancestry check before creating a child:** at the moment `submission.restaurant_update.resubmit` runs, the command walks the proposed parent's own ancestry chain (via `resubmission_of_submission_id`, following it back one hop at a time) and rejects the operation if the parent's own chain of ancestors already contains the parent itself — i.e., if the chain is already malformed — or, more directly, the command simply refuses to link a new child whose creation would make any row reachable from itself by repeatedly following `resubmission_of_submission_id`. Since each `resubmit` call adds exactly one new leaf to exactly one existing chain and never rewires an existing link (§5.7's atomicity requirement — parent and child are fixed at creation and never edited afterward), this reduces to a simple, cheap check: **the new child's ID must not already appear anywhere in the parent's ancestor chain being walked** — which is trivially true for a freshly-generated ID, but the check exists as a structural guardrail (§8) in case of ID reuse, replay, or a future bulk-import path that does not go through ordinary `resubmit`. This is a strictly weaker and cheaper check than a general cycle detector precisely because insertion is append-only-at-the-leaf by construction; it is not a claim that the `UNIQUE` constraints alone were ever sufficient.

An equally acceptable alternative implementation, **not mutually exclusive with the above**, is a monotonic `chain_depth` integer set at creation (`0` for an original submission, `parent.chain_depth + 1` for each resubmission), with a `CHECK (superseded_by_submission_id IS NULL OR chain_depth < (SELECT chain_depth FROM ... WHERE submission_id = superseded_by_submission_id))`-style invariant enforced at write time — a strictly increasing depth along every link makes a cycle structurally impossible (a cycle would require some row's depth to be simultaneously less than and greater than another's). This decision recommends the ancestry-walk check as the lower-complexity Phase 5 mechanism, since chains are expected to stay short, but does not prohibit `chain_depth` as an implementation choice if it proves simpler to enforce at the database layer.

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

**Clarified this revision — `returned` parent eligibility does not depend on the child's own outcome.** A `returned` parent becomes archival-eligible the moment `superseded_by_submission_id IS NOT NULL` (i.e., the moment `resubmit`, §5.7, successfully links a child) — eligibility is driven purely by "has this row been superseded," not by whether the child submission has itself since reached a terminal state. This is deliberate: the parent's own row is permanently done (§5.7 — a `returned` row never moves again) the instant a child exists to carry the correction forward; waiting on the child's outcome would tie the parent's archival state to a different row's lifecycle for no integrity reason, since the parent's payload and audit history are preserved regardless (§5.9's archival-behavior guarantees below) and remain reachable by walking the chain from the active leaf. If the child is itself later `rejected` or generates a further resubmission chain, the original `returned` parent's own archival eligibility is unaffected either way — it was already earned by having a child at all.

**Archival behavior:**
- Removes the record from default operational views.
- Never changes the submission's review outcome.
- Never deletes payload or audit history.
- Requires an actor (`archived_by_user_id`, stable reference — no display-name snapshot, per §5.1) and a `archive_reason` for any manual archival.
- No automatic archival schedule is approved by this decision.

### 5.10 Append-only audit coverage — fully specified; event actors corrected to support system-generated events

**`operations.restaurant_update_submission_events`** (append-only), covering:

`claim`, `release`, `return`, `resubmit` (renamed from `child_resubmission_created` this revision to match the formalized command name in §5.7 — same event, one name), `approve`, `reject`, `disposition_selected`, `disposition_handoff_attempted`, `disposition_handoff_succeeded`, `disposition_handoff_failed`, `downstream_completion_received`, `archive`.

**Corrected this revision, mirroring DEC000001 v4.1 §5.8 exactly:** requiring a human `actor_user_id` on every row does not fit events that are system- or pipeline-derived rather than human-initiated — `disposition_handoff_attempted`/`_succeeded`/`_failed` (initiated by the routing command itself, §5.5), `downstream_completion_received` (a callback from the owning OS, §5.3), and any automated `archive` (if a policy-driven schedule is ever adopted — none is approved by this decision, §5.9). Corrected columns:

```text
event_id
submission_id
event_type
actor_type:   user | system | pipeline
actor_id:     stable user ID (actor_type = user) |
              service-account ID or system actor identifier (actor_type = system) |
              pipeline name or pipeline-run identifier (actor_type = pipeline)
prior and resulting status              (review status, where applicable)
prior and resulting disposition_status  (where applicable)
failure_stage    (nullable; set only on disposition_handoff_failed / downstream_completion_received-with-failure events, per §5.3)
reason           (nullable; required for return, reject, administrative release override, manual archive, no_action's mandatory resolution_summary is a separate field, not this one)
downstream entity reference, where applicable (per §5.11's linkage fields)
created_at
metadata jsonb   (event-specific detail)
```

`claim`, `release`, `return`, `resubmit`, `approve`, `reject` are always `actor_type = user` — these remain human-only actions per §5.6/§5.7, unchanged. `disposition_handoff_attempted`/`_succeeded`/`_failed` are `actor_type = system` (the routing command itself is the actor) under ordinary operation; `downstream_completion_received` is `actor_type = system` or `pipeline`, matching whatever identifies the calling owning OS's callback mechanism. **Human-only live ownership fields are unaffected by this correction:** `claimed_by_user_id` (§5.6) and `archived_by_user_id`, when archival is manual (§5.9), both stay user-ID-only, since claiming and manual archival are, by definition, human actions. The `actor_type`/`actor_id` correction applies to the `restaurant_update_submission_events` audit trail only, not to these submission-row ownership columns.

The original submission payload remains on the immutable row (§5.7) — a separate payload-revision table, analogous to DEC000001's `intake_packet_revisions`, is **not required for this entity**, since this entity's correction mechanism is a new child row, not an in-place edit.

### 5.11 Downstream linkage — explicit nullable foreign keys, labeled by implementation-status maturity, entity question left open

v3 left the `resulting_intake_session` entity question open rather than silently renaming it; this revision keeps that question open but defines the linkage *requirement* more precisely and picks a storage shape.

**Two options evaluated:**

- **A. Purpose-specific nullable foreign keys** — one nullable column per downstream entity type (`resulting_intake_packet_id`, `resulting_intake_session_id`, `identity_review_item_id`, `exception_request_id`). Since `disposition_type` already acts as the discriminator (exactly one of these is populated per submission, matching whichever disposition was selected), this option doesn't need a separate type column to disambiguate — the schema is self-documenting, each FK can carry its own real referential-integrity constraint to its target table, and no generic-table join is needed to answer "what did this submission link to."
- **B. A generic typed downstream-link table** (`submission_id`, `downstream_entity_type`, `downstream_entity_id`, `created_at`) — more extensible if a submission could someday link to more than one downstream object, or if new disposition types are added frequently, but `downstream_entity_id` cannot carry a real foreign-key constraint (it must reference multiple possible tables), pushing referential integrity into application code, and it requires a join plus a type-string match to retrieve what a purpose-specific column would give directly.

**Recommendation: Option A (explicit nullable foreign keys).** For Phase 5's scope — four known disposition types, one downstream object per submission by construction (§5.4's derived-status model assumes a single handoff per approved submission) — the generic table's extensibility isn't needed yet, and its loss of real FK constraints is a real cost, not a neutral tradeoff. This matches the instruction to prefer explicit foreign keys over a generic abstraction when two or three (here, four) explicit columns are clearer. If a genuine need for multiple simultaneous downstream links per submission emerges later, that is itself a signal to revisit this decision, not a reason to over-build now.

**"One downstream object per submission" contradiction resolved this revision.** v4 stated the one-object-per-submission rule in §5.4 while §6 listed *two* populated-looking FK columns for the `intake_required` path (`resulting_intake_packet_id` and `resulting_intake_session_id`), which read as two simultaneous links and contradicted §5.4. **Corrected statement:** `resulting_intake_packet_id` and `resulting_intake_session_id` are **mutually exclusive alternatives for the same single downstream object**, not two active links — exactly one of the four purpose-specific FK columns is ever populated per submission, and for the `intake_required` disposition specifically, which *one* of those two candidate columns is the correct one is not yet decided (that choice belongs to DEC000001, not this record — see entity question below). Until DEC000001 resolves it, both columns exist in the schema as candidates, but any given `intake_required` submission populates at most one of them, never both. §6 is corrected to state this explicitly.

**Each proposed FK labeled by implementation-status maturity this revision** (previously presented uniformly, as if all four were equally ready to build against):

- `resulting_intake_packet_id` — **existing target confirmed.** `operations.intake_packets` is a real, already-governed table per DEC000001; this FK can be built as soon as DEC000001's own entity question (which of packet/session is canonical for this handoff) resolves in its favor.
- `resulting_intake_session_id` — **target entity unresolved.** Whether a canonical "intake session" entity distinct from an intake packet exists, or should exist, is DEC000001's open question, not confirmed in any live schema inspected for this record. This column is a placeholder pending that resolution, not a ready FK.
- `identity_review_item_id` — **Blueprint-defined, not yet implemented.** The Blueprint narratively documents the Identity Review Queue and its `pending_restaurant_submission` status (§1, carried from v3), but no canonical Identity Review Queue table has been inspected in the live schema for this record. The destination is real in the Blueprint's governance model; the table to point this FK at is not yet confirmed to exist.
- `exception_request_id` — **future recommendation, no confirmed target.** No Governance OS exception-request entity has been inspected or confirmed to exist anywhere in scope for this record. This decision recommends the eventual shape of the link (a single nullable FK, per Option A) but cannot confirm what table it references; building `submission.escalate_exception` (§5.5) is blocked on Governance OS defining that entity, independent of this decision.

None of these four labels changes the storage-model recommendation (Option A) or the routing/ownership decisions in §5.2 — they clarify build-readiness, not policy.

**Entity question intentionally still open** (unchanged from v3, carried into this recommendation): whether `intake_required` should populate `resulting_intake_packet_id`, `resulting_intake_session_id`, or both, is not resolved here — that is DEC000001's own open question (DEC000001 §5.9, §7 item 9 shared reference), not something this decision can settle unilaterally. `resulting_intake_session` is **not** renamed until that is resolved. As stated above, "both" is not actually an available outcome under this decision's one-object rule — the open question is *which one*, not whether both could be simultaneously populated.

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

## 6. Recommended canonical model (final, v4.1)

```text
pending_review
    ↓ claim
in_review
    ├── release → pending_review
    ├── return → returned
    │              ↓ resubmit (§5.7 — formalized command this revision)
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
failed            (failure_stage: handoff_call | local_write | downstream_terminal — added this revision, §5.3)

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

resolution_summary   (mandatory when disposition_type = no_action, per §5.4's tightening this revision)

resulting_intake_packet_id      (nullable FK; existing target confirmed, §5.11)
resulting_intake_session_id     (nullable FK; target entity unresolved, §5.11)
identity_review_item_id         (nullable FK; Blueprint-defined, not yet implemented, §5.11)
exception_request_id            (nullable FK; future recommendation, no confirmed target, §5.11)
```

**Corrected this revision:** `resulting_intake_packet_id` and `resulting_intake_session_id` are mutually exclusive alternatives for the same single `intake_required` handoff, not two simultaneously populated links — at most one of the four FK columns above is ever populated per submission, consistent with §5.4's one-downstream-object rule. See §5.11 for the full correction.

No `_display_name` field exists on any of these, per §5.1.

## 7. Founder decisions required (final — policy choices only; unchanged in substance from v4, with the new `resubmit` command and the FK-maturity labeling flagged explicitly below as this revision's only additions)

1. **Approve the five review statuses:** `pending_review`, `in_review`, `returned`, `approved`, `rejected`.
2. **Approve the separate disposition model and its five statuses:** `unassessed`, `pending`, `in_progress`, `completed`, `failed` (with `failure_stage` as a sub-classification of `failed`, added this revision, §5.3), with the precise semantics in §5.3 (routing completion ≠ downstream-work completion).
3. **Approve the four disposition types and their one-owner routing boundaries:** `intake_required` (Intake OS), `identity_review` (Restaurant Operations OS), `no_action` (closes within Restaurant Operations OS's own `.approve`, `resolution_summary` mandatory per §5.4), `exception_escalation` (Governance OS, sole owner — §5.2).
4. **Approve immutable parent submissions with linked child resubmissions**, per §5.7-§5.8, including the corrected cycle-prevention mechanism (ancestry check at `resubmit` time, or the alternative `chain_depth` invariant) in §5.8.
5. **Approve splitting the broad review command into `claim`, `release`, `return`, `approve`, `reject`**, removing `submission.close_no_action` as a standalone command per §5.5, and **approve `submission.restaurant_update.resubmit` (new this revision) as a discrete formalized command**, per §5.7 — flagged as its own registry addition requiring line-item approval, consistent with how DEC000001 treats each new command.
6. **Approve archival as a separate attribute set**, with the eligibility rules in §5.9, including the clarification that a `returned` parent's archival eligibility depends only on having a linked child, not on that child's own outcome.
7. **Choose the downstream-link storage model:** explicit nullable foreign-key fields (recommended, §5.11) or a typed generic downstream-link table — and **approve labeling each of the four candidate FK columns by implementation-status maturity** (existing target confirmed / target entity unresolved / Blueprint-defined-not-implemented / future recommendation with no confirmed target), per §5.11, rather than presenting all four as uniformly build-ready.
8. **Confirm the exact source of stable user identity** for `claimed_by_user_id`/`archived_by_user_id` once the current authentication/user schema is inspected — same open question as DEC000001 §7 decision 9, shared across both records.
9. **Confirm that `operations.partner_submissions` remains outside the scope of this decision** — no changes proposed to it.

## 8. Risks, guardrails, validation criteria, revisit triggers

**Risks:**
- The completion-update mechanism (§5.3) is deliberately left as an implementation choice; if no owning OS ever reliably reports back, `in_progress` submissions could accumulate indefinitely with no path to `completed`/`failed` — the authority rule closes the "false completion" and "unauthorized completion" risks but does not by itself close the "stuck forever" risk, which implementation must address operationally.
- The idempotency guarantee in §5.12 depends on each downstream owning OS honoring the idempotency key on its own side; this decision can require it as a precondition but cannot enforce it from the submission side alone.
- Removing `submission.close_no_action` (§5.5) assumes no UI already depends on it as a separate step; if a UI mockup or in-flight implementation assumed a two-step no-action flow, that needs to be caught before build.
- Introducing `actor_type`/`actor_id` (§5.10, new this revision) means any existing code or mockup that assumed a single `actor_user_id` column on `restaurant_update_submission_events` must be updated before implementation; this is a pre-implementation correction, not a live migration risk, since no code has been built against this record yet.
- The `resubmit`-time ancestry check (§5.8) walks the parent's chain on every call; this is cheap for short chains but its cost is unbounded in theory if a chain ever grows very long — implementation should confirm expected chain lengths stay small, or add the `chain_depth` alternative if not.
- Three of the four downstream FK targets (`resulting_intake_session_id`, `identity_review_item_id`, `exception_request_id`) are not yet confirmed to exist as canonical entities (§5.11); building the corresponding routing commands (`route_to_identity_review`, `escalate_exception`) is blocked on those entities being defined elsewhere, independent of this decision's own readiness.

**Guardrails:**
- No implementation proceeds until Founder decisions 1-9 above are made.
- `submission.restaurant_update.approve` must reject any call that omits `disposition_type`, and must reject any `no_action` approval that omits `resolution_summary`, per §5.4's tightening.
- Each routing command must reject any call where its stated preconditions (§5.5) are not met, including the `disposition_status ∈ {pending, failed}` guard that prevents re-routing an already-`in_progress` or `completed` disposition.
- `submission.restaurant_update.claim` must reject any attempt against a non-active-leaf row, per §5.8.
- `submission.restaurant_update.resubmit` must reject any call where the target row is not `returned` or is already superseded, per §5.7, and must perform the ancestry check in §5.8 before linking the new child.
- Every row written to `restaurant_update_submission_events` must set both `actor_type` and `actor_id` — no row may carry a null `actor_type`, per §5.10.
- No routing command or manual action may set `disposition_status = completed`/`failed` on a routed disposition without a corresponding `downstream_completion_received`/`disposition_handoff_failed` event (or, for a manual override, a mandatory reason), per §5.3.

**Validation criteria:**
- No submission can reach `status = approved` with `disposition_status = unassessed`.
- No submission reaches `disposition_status = completed` for a routed disposition (`intake_required`, `identity_review`, `exception_escalation`) without a recorded `downstream_completion_received` event.
- Every `failed` disposition has a non-null `failure_stage`, per §5.3.
- Every resubmission chain has exactly one active leaf per original parent, verifiable via the conditions in §5.8, and no chain contains a cycle, verifiable by the ancestry-check logic (or `chain_depth` monotonicity, if that alternative is implemented) actually preventing one at write time — not merely by the branching-factor constraints alone.
- No submission with `disposition_status ∈ {pending, in_progress, failed}` appears in an archived state.
- No submission has more than one of the four downstream FK columns (§5.11, §6) populated simultaneously.
- No table in this record contains a `_display_name` column.

**Revisit triggers:**
- If the exception-escalation workflow is designed later and turns out to need its own richer status model, that becomes its own Decision Record, not a reopening of this one.
- If a submission is ever found needing more than one simultaneous downstream link, that is a signal to revisit §5.11's Option A recommendation, not a reason to have over-built Option B now.
- If `partner_submissions` is later found to need the same disposition separation, that is also a new, separate decision.
- If resubmission chains are ever observed growing long enough that the ancestry-check walk (§5.8) becomes a measurable cost, that is a signal to switch to the `chain_depth` alternative, not to relax the cycle-prevention guarantee.
