# DEC000002 — Canonical Restaurant Update Submission State Machine

**Status:** approved — Founder approved (v4.2, as drafted), with one carve-out — see Founder approval note below
**Approval date:** 2026-07-18
**Decision basis:** architectural_requirement, compliance_or_risk_control
**Decision dependencies:** none (foundational record, sibling to DEC000001) — see §5.11 for the resolved intake-handoff target, which required no new decision dependency
**Registry impact:** governs `submission.restaurant_update.*` (including new `.resubmit` — its registry status remains `draft`, not `approved`, per the carve-out below and §5.7/§7 item 5), `submission.convert_to_intake`, `submission.route_to_identity_review`, `submission.escalate_exception`, and the removal of `submission.close_no_action` as a standalone command (see §5.5)

**Founder approval note:** approved as drafted in v4.2 — all nine §7 decisions are approved without modification, including item 5's own explicit limit: approving item 5 authorizes `submission.restaurant_update.resubmit`'s existence, model, and mechanics only; it does **not** approve who may invoke it. Per §5.7 and §7 item 5, `resubmit`'s registry status stays `draft` until a separate role/portal-origin decision resolves invocation authority — that limit is preserved by this approval, not lifted by it. Implementation evidence: `supabase/migrations/021_submission_state_machine.sql` (schema, disposition model, resubmission-chain integrity triggers, append-only event table) and `supabase/migrations/022_submission_review_rpcs.sql` (the `resubmit` RPC, built with mechanics only — no `GRANT EXECUTE` issued to any role, consistent with invocation authority remaining undecided) are committed as of `109fc2ba150fa81299bd384b690486d0dee6a640`. The `.claim`/`.release`/`.return`/`.approve`/`.reject`/`.convert_to_intake`/`.route_to_identity_review`/`.escalate_exception` command handlers are approved in model but not yet built — see `docs/decisions/DEC000002_IMPLEMENTATION_GAP_MAP.md` and `docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md` §17 for current build status.

**Revision note (v4.2, carried forward from the pre-approval draft):** v4 was accepted in direction during review — not Founder-approved as architecture at that time. v4.1 was a mechanical/integrity pass; v4.2 was a narrow consistency correction pass only — no review/disposition model, routing boundary, ownership decision, or child-resubmission approach was reopened by it. Seven corrections were made in v4.2: (1) §5.8's ineffective ancestry-ID check is withdrawn and replaced with the actual structural guarantee — `resubmit` always creates a brand-new row and never rewires an existing chain, so no cycle can form by construction; the inaccurate cross-row `CHECK`-constraint example is removed and replaced with a note that any cross-row chain-depth invariant needs a trigger, deferred constraint trigger, or application-level transactional validation, not a plain `CHECK`. (2) The packet-vs-session handoff target is resolved to `operations.intake_packets` as the canonical downstream object — DEC000001 does not in fact contain this open question, so attributing it there is corrected; `resulting_intake_session_id` becomes an optional, non-canonical secondary technical reference. (3) Downstream FK cardinality is corrected from "exactly one of four always populated" to conditional rules keyed on `disposition_type`/`disposition_status`/`failure_stage`. (4) `local_write` failure recording is specified as a separate recovery-transaction responsibility, since the failed linkage transaction cannot record its own rollback. (5) Audit events now distinguish the initiating actor from the executing actor and the downstream owning OS's callback identity, rather than collapsing a human-initiated handoff into `actor_type = system` alone. (6) `resubmit`'s invocation authority is explicitly deferred — its registry entry stays `draft`, not `approved`, until a separate role/portal-origin decision resolves who may call it; this limit survives Founder approval of the rest of the record, per the Founder approval note above. (7) "v4 is approved architecturally" is corrected to "v4 was accepted in direction during review," matching the record's status at the time (prior to this Founder approval). Sections 1-4 carry forward unchanged; §5.7, §5.8, §5.10, §5.11 are amended in place; §6-§8 updated to match.

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
| `submission.restaurant_update.resubmit` (new v4) | not in registry today — proposed at `draft`, not `approved`, pending a separate invocation-authority decision (corrected this revision — see §5.7, §7 item 5) | Formalizes child-resubmission creation as a discrete command, previously only described narratively. Command model and mechanics are ready to build; who may invoke it is not yet defined. See §5.7. |
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
- **`failed`** — handoff creation failed, or the downstream owning OS reported a terminal failure; requires retry or manual intervention. **`failure_stage`** records *where* in the sequence the failure occurred — `handoff_call` (the routing command's call to the downstream owning OS never succeeded), `local_write` (the downstream call succeeded but this record's own linkage write, §5.12 step 2/3, failed), or `downstream_terminal` (the downstream owning OS itself later reported a terminal failure after successfully accepting the handoff). This distinction matters operationally: a `handoff_call` failure is safely retryable with no risk of a duplicate downstream object; a `downstream_terminal` failure means a downstream object exists and any retry must address it there, not merely re-attempt the handoff. **`local_write` recordability (corrected this revision, mechanism specified in §5.12 step 3a):** because the local linkage write and the `disposition_status` update are part of the same failed, rolled-back transaction, that transaction cannot also record its own failure — a rolled-back transaction leaves no trace. Recording a `local_write` failure is therefore necessarily the responsibility of a **separate recovery transaction**, run by the orchestration layer, not an implied side-effect of the failed write itself.

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
- On success: creates or links the canonical Intake downstream object, `operations.intake_packets` (resolved this revision — see §5.11 below; not an open DEC000001 question, corrected); sets `disposition_status = in_progress`; records the downstream linkage in `resulting_intake_packet_id`; emits an auditable handoff event (§5.10).

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
- **Actor — invocation authority explicitly deferred, not left vague (corrected this revision):** this decision does not assume the original submitter and the resubmitting actor are the same identity, and confirms `resubmit` is not a Governance-side action (Governance's role in this record is reviewing, per §5.6, not resubmitting on the submitter's behalf). Beyond that exclusion, **no actor category or role is defined for `resubmit` by this decision.** A formalized command cannot carry undefined invocation authority as an `approved` registry entry: `submission.restaurant_update.resubmit`'s registry status **remains `draft`** regardless of this record's own approval, and **cannot move to `approved` until a separate, explicit role/portal-origin decision** defines which actor categories (submitter, any authenticated portal user, an administrator, etc.) may invoke it. This decision approves the command's *existence, model, and mechanics* (§5.7-§5.8) as ready to build against once that separate authorization decision is made — it does not, and cannot, approve who may call it.
- **Failure mode:** if the precondition check fails (row not `returned`, or already superseded), the command returns no row / an explicit precondition-failure error — never a silent no-op — mirroring the claim command's failure contract in §5.6.

### 5.8 Resubmission-chain validation — structural cycle-prevention corrected to an actual guarantee

**Structural invariants (unchanged from v3/v4):**

- No submission may reference itself as parent or successor (`resubmission_of_submission_id != submission_id`, `superseded_by_submission_id != submission_id`).
- Each child has **at most one** parent (structural — `resubmission_of_submission_id` is a single nullable column, not a set).
- Each parent has **at most one** direct child (`UNIQUE` constraint on `resubmission_of_submission_id`, per §5.7).
- Parent and child must reference the **same canonical restaurant identity** (matching DEC000001 v4 §5.6's identity rule: same `restaurant_id`, or same `restaurant_external_id` if `restaurant_id` is null on either).
- Only rows with `superseded_by_submission_id IS NULL` are **active leaves**.
- Only active leaves may be claimed or reviewed — `submission.restaurant_update.claim` must reject any attempt against a row where `superseded_by_submission_id IS NOT NULL`.

**Branching-factor limits alone do not prove acyclicity (unchanged finding from v4.1, restated).** A chain with branching factor exactly one at every node can still form a cycle — for example, three rows A → B → C → A, each individually satisfying "at most one parent" and "at most one child," while the set as a whole loops. Branching-factor limits constrain shape (no forking, no merging) but do not by themselves exclude a ring.

**Corrected this revision — the v4.1 "ancestry-ID check" is withdrawn as ineffective and replaced with the actual structural guarantee.** v4.1 proposed checking that "the new child's ID must not already appear in the parent's ancestor chain" before linking a resubmission. That check is vacuous: the child's ID is freshly generated by `resubmit` at the moment of creation, so it cannot, by construction, already appear anywhere in any existing chain — the check would always pass and catches nothing. It is withdrawn, not merely weakened.

**The real guarantee against cycles is structural, not a runtime check, and rests on five rules `resubmit` and every other command must honor:**

1. `submission.restaurant_update.resubmit` **must create a brand-new submission row** for the child. It may never attach an existing submission row as the child of a resubmission.
2. `resubmission_of_submission_id` (on the child) and `superseded_by_submission_id` (on the parent) are **immutable once written by the child-creation transaction** — no command, routine or administrative, may later change either value on an existing row.
3. **No routine command may rewire an existing chain** — there is no operation in this decision's command set (§3, §5.5-§5.7) that reassigns a submission's parent or child link after creation.
4. **Parent and child linkage is created atomically**, in the single transaction described in §5.7 (child row insert + parent's `superseded_by_submission_id` update, together or not at all).
5. Because every link is created exactly once, always points from a pre-existing row (the parent) to a row that did not exist until that same transaction (the child), and is never rewritten afterward, **a cycle cannot form through the ordinary `resubmit` path by construction** — a new row cannot be its own ancestor, and no existing row can be retargeted into forming a loop, because nothing ever retargets an existing row's links at all.

**Existing or imported rows are validated separately, not by this mechanism.** The construction argument above holds only for rows created through `resubmit` under these five rules. Any submission rows created outside that path — a bulk import, a data migration, a manual database correction, or legacy pre-DEC000002 data — are not covered by an insertion-time guarantee they never went through, and **must be validated by a separate, explicit integrity check** (e.g., a one-time or periodic recursive-chain walk across all rows) before being treated as trustworthy. This decision requires that separate check but does not specify its implementation.

**No `CHECK`-constraint example is given, and the prior one is withdrawn as inaccurate.** v4.1 illustrated a `chain_depth` alternative with a PostgreSQL `CHECK` constraint containing a cross-row subquery. **PostgreSQL `CHECK` constraints may only reference columns of the row being written — a cross-row subquery in a `CHECK` is not valid and would be rejected by the database.** That example is removed. If a monotonic `chain_depth` invariant is implemented as a defense-in-depth measure alongside the structural guarantee above, enforcing it against other rows requires one of: a `BEFORE INSERT` trigger, a deferred constraint trigger, or application-level transactional validation performed within the same transaction that writes the child row — **not** an ordinary `CHECK` constraint. This decision does not mandate `chain_depth` (the five-rule structural guarantee above is sufficient for every submission created through the governed `resubmit` command), but if it is added, it must be enforced by one of these three mechanisms.

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
actor_type:              user | system | pipeline   — the executing actor: what actually performed this event's action
actor_id:                stable user ID (actor_type = user) |
                          service-account ID or system actor identifier (actor_type = system) |
                          pipeline name or pipeline-run identifier (actor_type = pipeline)
initiating_actor_type:    user | system | pipeline | null   (added this revision — see below)
initiating_actor_id:      nullable, same typing as actor_id — the actor who requested this event, when distinct from actor_id
downstream_caller_id:     nullable text (added this revision) — for downstream_completion_received only: the downstream owning OS's own callback/service identity reporting completion, distinct from this side's actor_id
prior and resulting status              (review status, where applicable)
prior and resulting disposition_status  (where applicable)
failure_stage    (nullable; set only on disposition_handoff_failed / downstream_completion_received-with-failure events, per §5.3)
reason           (nullable; required for return, reject, administrative release override, manual archive, no_action's mandatory resolution_summary is a separate field, not this one)
downstream entity reference, where applicable (per §5.11's linkage fields)
created_at
metadata jsonb   (event-specific detail)
```

`claim`, `release`, `return`, `resubmit`, `approve`, `reject` are always `actor_type = user` with `initiating_actor_type`/`initiating_actor_id` left null — these remain human-only actions per §5.6/§5.7, and the human who executed the action is also, definitionally, the one who requested it, so a separate initiating-actor pair adds nothing for these event types.

**Corrected this revision — handoff events preserve both who requested and what executed, rather than collapsing to `actor_type = system` alone.** `disposition_handoff_attempted`/`_succeeded`/`_failed` are recorded with `actor_type = system` (the routing command's own execution context is what actually performed the handoff call) **and**, whenever a human explicitly invoked the routing command (the ordinary case today, since no automated post-approval trigger is currently defined by this decision), `initiating_actor_type = user` / `initiating_actor_id = <that user's stable ID>` is also recorded on the same event row. If a routing command is ever invoked by an automated process rather than a human, `initiating_actor_type` is set to `system`/`pipeline` accordingly, or left null only if there genuinely is no distinct initiator to record. This lets the audit trail answer both "who requested this handoff?" (`initiating_actor_id`) and "what executed it?" (`actor_id`) as two separate questions, rather than only the second.

`downstream_completion_received` is recorded with `actor_type = system` or `pipeline` (this side's own processing of the inbound callback) and **`downstream_caller_id` populated with the owning OS's own callback identity** (added this revision) — the identifier the downstream OS uses to identify itself when it reports completion, which is not the same thing as this side's generic `actor_id` and must not be conflated with it.

**Human-only live ownership fields are unaffected by this correction:** `claimed_by_user_id` (§5.6) and `archived_by_user_id`, when archival is manual (§5.9), both stay user-ID-only, since claiming and manual archival are, by definition, human actions. The `actor_type`/`actor_id`/`initiating_actor_*`/`downstream_caller_id` correction applies to the `restaurant_update_submission_events` audit trail only, not to these submission-row ownership columns.

The original submission payload remains on the immutable row (§5.7) — a separate payload-revision table, analogous to DEC000001's `intake_packet_revisions`, is **not required for this entity**, since this entity's correction mechanism is a new child row, not an in-place edit.

### 5.11 Downstream linkage — resolved canonical target, explicit nullable foreign keys, conditional cardinality

**Corrected this revision — the packet-vs-session handoff target is resolved, not an open DEC000001 question.** v4/v4.1 stated that whether `intake_required` should populate `resulting_intake_packet_id`, `resulting_intake_session_id`, or which of the two is canonical, was "DEC000001's own open question." **That attribution is incorrect and is withdrawn: DEC000001 (`docs/decisions/DEC000001_CANONICAL_INTAKE_PACKET_STATE_MACHINE.md`, Founder-approved 2026-07-13) does not contain this question anywhere in its text** — it governs the Intake Packet lifecycle itself, not the Submission-side handoff-target choice. A fresh inspection of the live schema confirms only one real table exists: `operations.intake_packets` (migration 015, governed by DEC000001). No `intake_session` table exists anywhere in the schema. The only trace of "session" on the submission side is a free-text, non-FK column, `resulting_intake_session` (migration 011, `operations.restaurant_update_submissions`), documented in that migration's own comment as "`intake_session_id` if approval triggered Intake" — i.e. a placeholder, never a confirmed entity.

**Resolution:** the canonical downstream object for the `intake_required` disposition is **`operations.intake_packets`**, referenced via `resulting_intake_packet_id`. `resulting_intake_session_id` is retained in the schema only as an **optional, non-canonical secondary technical reference** — populated only if and when a distinct "intake session" concept is separately defined and confirmed to exist as its own entity (which would itself be a new, narrow decision or amendment, not assumed here). Until then, `resulting_intake_session_id` stays null on every row and carries no referential-integrity requirement. This resolution required no new Decision Record (e.g. no `DEC000003`) because the live schema already supplies an unambiguous answer — there was no genuine architectural fork to decide, only a mis-citation to correct.

**Two storage-shape options evaluated (unchanged from v3/v4):**

- **A. Purpose-specific nullable foreign keys** — one nullable column per downstream entity type (`resulting_intake_packet_id`, `resulting_intake_session_id`, `identity_review_item_id`, `exception_request_id`). Since `disposition_type` already acts as the discriminator, this option doesn't need a separate type column to disambiguate, each FK can carry its own real referential-integrity constraint, and no generic-table join is needed to answer "what did this submission link to."
- **B. A generic typed downstream-link table** (`submission_id`, `downstream_entity_type`, `downstream_entity_id`, `created_at`) — more extensible but `downstream_entity_id` cannot carry a real foreign-key constraint, pushing referential integrity into application code, and requires a join plus a type-string match to retrieve what a purpose-specific column would give directly.

**Recommendation: Option A, unchanged.** For Phase 5's scope, the generic table's extensibility isn't needed yet, and its loss of real FK constraints is a real cost, not a neutral tradeoff.

**Each FK's build-readiness, updated this revision:**

- `resulting_intake_packet_id` — **canonical, existing target confirmed, ready to build.** `operations.intake_packets` is real, already governed by DEC000001, and is now the sole `intake_required` handoff target — no longer waiting on any open question.
- `resulting_intake_session_id` — **non-canonical, optional secondary reference, no confirmed target.** Not counted as a "canonical downstream FK" for the cardinality rules below. Left null unless a future, separate decision defines a real intake-session entity for it to reference.
- `identity_review_item_id` — **Blueprint-defined, not yet implemented.** The Blueprint narratively documents the Identity Review Queue and its `pending_restaurant_submission` status (§1), but no canonical Identity Review Queue table has been inspected in the live schema. The destination is real in the Blueprint's governance model; the table to point this FK at is not yet confirmed to exist.
- `exception_request_id` — **future recommendation, no confirmed target.** No Governance OS exception-request entity has been inspected or confirmed to exist anywhere in scope for this record. Building `submission.escalate_exception` (§5.5) is blocked on Governance OS defining that entity, independent of this decision.

None of these labels changes the storage-model recommendation (Option A) or the routing/ownership decisions in §5.2 — they clarify build-readiness, not policy.

**Downstream FK cardinality — corrected this revision from "exactly one of four always populated" to conditional rules keyed on disposition state (see §5.3, §5.4 for the referenced states):**

| Condition | Canonical downstream FK state |
|---|---|
| `disposition_type = no_action` | Zero canonical downstream FK columns populated — there is no downstream object for `no_action` (§5.4, §5.5). |
| Routed disposition (`intake_required`, `identity_review`, `exception_escalation`), `disposition_status = pending` (handoff not yet attempted or not yet succeeded) | Zero canonical downstream FK columns populated. |
| Routed disposition, `disposition_status ∈ {in_progress, completed}` (handoff succeeded) | Exactly one canonical downstream FK populated — the one matching the selected `disposition_type` (`resulting_intake_packet_id`, `identity_review_item_id`, or `exception_request_id`). |
| Routed disposition, `disposition_status = failed`, `failure_stage = handoff_call` (the downstream call itself never succeeded, §5.3) | Zero canonical downstream FK columns populated — nothing was created downstream to link to. |
| Routed disposition, `disposition_status = failed`, `failure_stage = local_write` (downstream call succeeded, this side's linkage write failed, §5.3, §5.12 below) | The downstream object **may already exist**, but the canonical local FK column **may be absent** (null) until reconciliation completes and records it — this is a permitted, expected inconsistency window, not a violation. |
| Any state | **No submission may have more than one canonical downstream FK column populated simultaneously.** `resulting_intake_session_id` is excluded from this count, per its non-canonical status above. |

This table supersedes the single "exactly one of four" sentence from v4/v4.1 everywhere it appeared (§5.11, §6, guardrails, validation criteria — all corrected in this revision).

`resolution_summary` (unchanged) remains the structured/human-readable disposition note, populated regardless of which downstream link field is used.

### 5.12 Idempotency — strengthened to a defined failure-safe sequence

v3 stated idempotency as a requirement without a concrete mechanism; this revision defines one, while explicitly not overclaiming cross-service atomicity that cannot actually be guaranteed:

- **Idempotency key:** `submission_id` combined with `disposition_type` (a submission can only ever be routed once per its single selected disposition, so this pair is sufficient and stable across retries).
- **Failure-safe sequence** (not claimed to be atomic across the network boundary to the owning OS, which would be an unenforceable guarantee):
  1. The routing command calls the downstream owning OS's creation/handoff endpoint, passing the idempotency key.
  2. If the downstream call succeeds, the routing command writes the downstream linkage (§5.11) and sets `disposition_status = in_progress` in one local transaction.
  3. If the downstream call succeeds but the local write in step 2 fails (e.g., a crash or error between the two), two distinct requirements apply, corrected and separated this revision:
     a. **Recording the failure (corrected this revision):** the failed local write's own transaction rolled back and recorded nothing — it cannot record its own failure. A **separate recovery transaction**, run by the orchestration layer (not nested inside, or dependent on, the failed transaction), must detect this condition and write `disposition_status = failed`, `failure_stage = local_write`, and the attempt's metadata (downstream object reference if known, timestamp, error detail) as its own independent write. This recovery transaction is what makes the `local_write` failure state in §5.11's cardinality table observable at all — without it, the submission would be silently stuck with no record of what happened.
     b. **Retrying safely:** a retry of the routing command must, using the same idempotency key, have the downstream owning OS **return or reuse the already-created object** rather than create a duplicate — this is a requirement on the downstream owning OS's own idempotent-handling contract, not something this submission-side decision can enforce unilaterally, but it is a precondition this decision requires before any routing command is built.
  4. If the downstream call itself fails, `disposition_status = failed` is set locally; `status = approved` is preserved unchanged — the approval stands regardless of downstream failure.
  5. Every attempt, successful or failed, is audited (`disposition_handoff_attempted`/`_succeeded`/`_failed`, per §5.10), including timestamps, so repeated retries are individually visible even though they share one idempotency key.

## 6. Recommended canonical model (final, v4.2)

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

resubmission_of_submission_id   (immutable once set by the resubmit transaction, §5.8)
superseded_by_submission_id     (immutable once set by the resubmit transaction, §5.8)

archived_at
archived_by_user_id
archive_reason

resolution_summary   (mandatory when disposition_type = no_action, per §5.4)

resulting_intake_packet_id      (canonical nullable FK for intake_required; existing target confirmed, §5.11)
resulting_intake_session_id     (non-canonical, optional secondary technical reference; no confirmed target; not counted in cardinality rules, §5.11)
identity_review_item_id         (canonical nullable FK for identity_review; Blueprint-defined, not yet implemented, §5.11)
exception_request_id            (canonical nullable FK for exception_escalation; future recommendation, no confirmed target, §5.11)
```

**Corrected this revision:** the packet-vs-session handoff target is resolved — `resulting_intake_packet_id` is the sole canonical FK for `intake_required`; `resulting_intake_session_id` is a non-canonical optional field excluded from the cardinality count. Cardinality is no longer "at most one of four always" but the conditional table in §5.11: zero canonical FKs populated for `no_action` and for any routed disposition still `pending` or `failed` with `failure_stage = handoff_call`; exactly one canonical FK populated once a handoff succeeds (`in_progress`/`completed`); the downstream object may exist without its local FK recorded yet during the `failed`/`local_write` reconciliation window. See §5.11 for the full correction.

No `_display_name` field exists on any of these, per §5.1.

## 7. Founder decisions — approved 2026-07-18 (final v4.2 policy choices; unchanged in substance from v4, with the new `resubmit` command and the FK-maturity labeling flagged explicitly below as v4.2's only additions)

1. **Approved — the five review statuses:** `pending_review`, `in_review`, `returned`, `approved`, `rejected`.
2. **Approved — the separate disposition model and its five statuses:** `unassessed`, `pending`, `in_progress`, `completed`, `failed` (with `failure_stage` as a sub-classification of `failed`, added in v4.2, §5.3), with the precise semantics in §5.3 (routing completion ≠ downstream-work completion).
3. **Approved — the four disposition types and their one-owner routing boundaries:** `intake_required` (Intake OS), `identity_review` (Restaurant Operations OS), `no_action` (closes within Restaurant Operations OS's own `.approve`, `resolution_summary` mandatory per §5.4), `exception_escalation` (Governance OS, sole owner — §5.2).
4. **Approved — immutable parent submissions with linked child resubmissions**, per §5.7-§5.8, including the corrected cycle-prevention mechanism (the structural, construction-based guarantee — new-row-only creation, immutable linkage, no rewiring, atomic linkage — replacing the withdrawn ancestry-ID check) in §5.8.
5. **Approved, with an explicit carve-out — splitting the broad review command into `claim`, `release`, `return`, `approve`, `reject`**, removing `submission.close_no_action` as a standalone command per §5.5, and **approving `submission.restaurant_update.resubmit`'s existence, model, and mechanics as a discrete formalized command**, per §5.7. **This approval authorizes `resubmit`'s design only — its registry status stays `draft` (not `approved`) until a separate role/portal-origin decision resolves invocation authority, per §5.7.** This carve-out is not diminished by the overall Founder approval of this record (see Founder approval note, header).
6. **Approved — archival as a separate attribute set**, with the eligibility rules in §5.9, including the clarification that a `returned` parent's archival eligibility depends only on having a linked child, not on that child's own outcome.
7. **Approved — explicit nullable foreign-key fields (Option A) as the downstream-link storage model**, per §5.11, and **the resolved canonical/non-canonical FK labeling**: `resulting_intake_packet_id` canonical and ready to build; `resulting_intake_session_id` non-canonical, optional, and excluded from cardinality rules; `identity_review_item_id` Blueprint-defined but not yet implemented; `exception_request_id` a future recommendation with no confirmed target — per §5.11, rather than uniformly build-ready or four competing candidates.
8. **Stable user identity — approved rule vs. deferred dependency, same split as DEC000001 §7 item 9:**
   - **Approved architectural rule** (already established via §5.1, §5.6): `claimed_by_user_id`, `archived_by_user_id`, and `actor_id` (when `actor_type = user`) must reference a stable user identifier, never a display-name snapshot.
   - **Still open — deferred implementation dependency:** the exact canonical user/auth table these fields resolve to — same open question as DEC000001 §7 item 9, shared across both records. Per `docs/decisions/DEC000001_IMPLEMENTATION_GAP_MAP.md` §0, this has since been resolved for the schema (`operations.users`, migration 004) and migrations 021/022 build against it; this item is retained here for the decision record's own completeness, not because the dependency is still unresolved in the schema.
9. **Approved — `operations.partner_submissions` remains outside the scope of this decision** — no changes proposed to it.

## 8. Risks, guardrails, validation criteria, revisit triggers

**Risks:**
- The completion-update mechanism (§5.3) is deliberately left as an implementation choice; if no owning OS ever reliably reports back, `in_progress` submissions could accumulate indefinitely with no path to `completed`/`failed` — the authority rule closes the "false completion" and "unauthorized completion" risks but does not by itself close the "stuck forever" risk, which implementation must address operationally.
- The idempotency guarantee in §5.12 depends on each downstream owning OS honoring the idempotency key on its own side; this decision can require it as a precondition but cannot enforce it from the submission side alone.
- Removing `submission.close_no_action` (§5.5) assumes no UI already depends on it as a separate step; if a UI mockup or in-flight implementation assumed a two-step no-action flow, that needs to be caught before build.
- Introducing `actor_type`/`actor_id` (§5.10, new this revision) means any existing code or mockup that assumed a single `actor_user_id` column on `restaurant_update_submission_events` must be updated before implementation; this is a pre-implementation correction, not a live migration risk, since no code has been built against this record yet.
- The cycle-prevention guarantee in §5.8 (corrected this revision) holds only for rows created through `resubmit` itself; it is a construction argument, not a runtime check, so it says nothing about rows entering the table by other means. Bulk import, migration, or manual correction can still introduce a malformed chain or a cycle, and must be validated separately (§5.8) — that separate validation mechanism is not yet specified and is an implementation gap, not a documentation one.
- The `local_write` recovery-transaction requirement (§5.3, §5.12, corrected this revision) depends on the orchestration layer reliably detecting and catching the local-write failure after a successful downstream call; if that detection itself fails silently, the submission can be left in an inconsistent state (downstream object exists, no local record, no recorded `failed`/`local_write` disposition) with no automatic path to reconciliation — implementation must add monitoring for this gap, not just the recovery-transaction mechanism itself.
- Two of the three non-canonical/not-yet-implemented downstream FK targets (`identity_review_item_id`, `exception_request_id`) are not yet confirmed to exist as canonical entities (§5.11); building the corresponding routing commands (`route_to_identity_review`, `escalate_exception`) is blocked on those entities being defined elsewhere, independent of this decision's own readiness.

**Guardrails:**
- Founder decisions 1-9 above are approved (2026-07-18); implementation of the schema and resubmit mechanics has proceeded on that basis (`021_submission_state_machine.sql`, `022_submission_review_rpcs.sql`). Item 5's carve-out still applies: no command handler or API endpoint may grant invocation authority over `resubmit` until the separate role/portal-origin decision it requires is made.
- `submission.restaurant_update.approve` must reject any call that omits `disposition_type`, and must reject any `no_action` approval that omits `resolution_summary`, per §5.4's tightening.
- Each routing command must reject any call where its stated preconditions (§5.5) are not met, including the `disposition_status ∈ {pending, failed}` guard that prevents re-routing an already-`in_progress` or `completed` disposition.
- `submission.restaurant_update.claim` must reject any attempt against a non-active-leaf row, per §5.8.
- `submission.restaurant_update.resubmit` must reject any call where the target row is not `returned` or is already superseded, per §5.7; must always create a brand-new child row and never attach an existing submission row as the child; and must create the parent-child linkage atomically, per §5.8 (corrected this revision). `resubmission_of_submission_id` and `superseded_by_submission_id` must be immutable after the child-creation transaction, and no routine command may rewire an existing chain.
- `resubmit` remains `draft` in the Command Registry regardless of Founder approval of its design (§7 item 5); it must not be promoted to `approved` until a separate role/portal-origin decision defines its invocation authority, per §5.7 (corrected this revision).
- Every row written to `restaurant_update_submission_events` must set both `actor_type` and `actor_id` — no row may carry a null `actor_type`, per §5.10. When a human initiates a system/pipeline-executed handoff, the event must also set `initiating_actor_type`/`initiating_actor_id` alongside the executing `actor_type`/`actor_id`, per §5.10 (corrected this revision).
- No routing command or manual action may set `disposition_status = completed`/`failed` on a routed disposition without a corresponding `downstream_completion_received`/`disposition_handoff_failed` event (or, for a manual override, a mandatory reason), per §5.3.
- When a downstream call succeeds but the local linkage write fails, the orchestration layer must not attempt to record `disposition_status = failed`/`failure_stage = local_write` inside the failed transaction itself; it must be recorded by a separate recovery transaction, per §5.3, §5.12 (corrected this revision).

**Validation criteria:**
- No submission can reach `status = approved` with `disposition_status = unassessed`.
- No submission reaches `disposition_status = completed` for a routed disposition (`intake_required`, `identity_review`, `exception_escalation`) without a recorded `downstream_completion_received` event.
- Every `failed` disposition has a non-null `failure_stage`, per §5.3.
- Every resubmission chain has exactly one active leaf per original parent, verifiable via the conditions in §5.8, and no chain created through `resubmit` contains a cycle — guaranteed by construction (new-row-only creation, immutable linkage, no rewiring, atomic linkage), not by a runtime ancestry check, per §5.8 (corrected this revision). Chains containing rows introduced by bulk import, migration, or manual correction require the separate validation mechanism noted in §5.8 and are not covered by this construction guarantee.
- No submission with `disposition_status ∈ {pending, in_progress, failed}` appears in an archived state.
- No submission has more than one canonical downstream FK column (§5.11, §6) populated simultaneously; `resulting_intake_session_id` is non-canonical and excluded from this count. Cardinality otherwise follows the conditional table in §5.11: zero canonical FKs for `no_action`, zero for any routed disposition still `pending` or `failed`/`handoff_call`, exactly one canonical FK once a handoff succeeds (`in_progress`/`completed`), and possibly zero with the downstream object already existing during the `failed`/`local_write` reconciliation window (corrected this revision).
- Every `disposition_status = failed`/`failure_stage = local_write` row is recorded by a separate recovery transaction, not by the failed linkage transaction itself, per §5.3, §5.12 (corrected this revision).
- Every handoff event initiated by a human but executed by a system/pipeline actor sets both the initiating and executing actor fields, per §5.10 (corrected this revision).
- No table in this record contains a `_display_name` column.

**Revisit triggers:**
- If the exception-escalation workflow is designed later and turns out to need its own richer status model, that becomes its own Decision Record, not a reopening of this one.
- If a submission is ever found needing more than one simultaneous downstream link, that is a signal to revisit §5.11's Option A recommendation, not a reason to have over-built Option B now.
- If `partner_submissions` is later found to need the same disposition separation, that is also a new, separate decision.
- If rows are ever introduced into the resubmission chain outside of `resubmit` (bulk import, migration, manual correction) at meaningful volume, that is a signal to formally specify the separate validation mechanism referenced in §5.8, not a reason to relax the construction-based cycle-prevention guarantee for `resubmit`-created rows.
- If the role/portal-origin decision resolving `resubmit`'s invocation authority (§5.7, §7 item 5) is not made before implementation is otherwise ready to proceed, that blocks only `resubmit`'s own registry promotion to `approved` — it is not a reason to reopen or delay the rest of this decision.
