# GoldPan™ Command Registry — Governing Specification, Phase 5 Inventory, Evidence Standard, and Registry Integration Model

**Version:** 0.2
**Status:** Draft Architectural Standard
**Companion to:** `GOLDPAN_MASTER_OS_BLUEPRINT.md`
**Current scope:** Expanded Phase 5 — Intake OS
**Governing decisions:** `DEC000001` (`docs/decisions/DEC000001_CANONICAL_INTAKE_PACKET_STATE_MACHINE.md`) — **approved 2026-07-13** — governs lifecycle-dependent states, permissions, evidence boundaries, and transition semantics for every `intake.packet.*`/`intake.review.*` command below. It does **not** automatically approve the existence or complete metadata (command type, evidence level, etc.) of every command in those namespaces — each command still requires its own valid registry status and evidence basis, per the Registry framework or an explicit Founder-approved decision. `DEC000002` (`docs/decisions/DEC000002_submission_state_machine.md`) — **approved 2026-07-18** — governs lifecycle-dependent states, permissions, and transition semantics for every `submission.*` command below on the same terms as DEC000001 above.
**Primary objective:** Make routine GoldPan™ Master OS operations discoverable, understandable, and executable by trained nontechnical operators without requiring source code, terminal access, direct database access, API clients, or repeated Claude assistance.

---

## 1. Purpose

The GoldPan™ Command Registry defines the operational capabilities available — or intended to become available — through Master OS.

The registry is a metadata and governance layer. It does not replace application code, APIs, workflows, or user interfaces. It describes what operational capabilities exist, who owns them, who may invoke them, what conditions govern them, how they are implemented, and what decisions justify them.

The Command Registry exists to reduce dependence on:

- founder memory
- developer knowledge
- undocumented scripts
- terminal commands
- direct database operations
- one-off AI guidance
- scattered implementation notes

The Command Registry supports the broader Master OS mission: **turn founder knowledge into durable operational infrastructure.**

---

## 2. Scope

This document contains four connected layers:

1. Command Registry governing specification
2. Evidence and implementation classification standard
3. Expanded Phase 5 command inventory
4. Registry integration model linking commands to decisions, workflows, modules, rules, screens, APIs, tables, and audit history

This document is intentionally broader than a simple list of buttons. It establishes the structure needed for Master OS to gradually become GoldPan's operational memory.

---

## 3. Current Boundaries

The Command Registry is **not** currently:

- a slash-command interface
- a natural-language command palette
- an AI agent tool registry
- a dynamic UI-generation system
- a database-backed registry application
- the future global command bar described in Blueprint §7b

Those systems may eventually consume the registry. They are not the registry itself.

At the current stage, the registry should remain a version-controlled structured document, with an optional YAML or JSON companion file for machine-readable use.

---

## 4. Core Principle

A command represents a human-understandable operational capability. A command may map to:

- a backend handler
- an API endpoint
- a workflow trigger
- a state transition
- an approval action
- a query
- a navigation action
- an automated job
- a restricted administrative operation

Registering a command does not mean the command is implemented. The registry must distinguish clearly between what exists, what the Blueprint requires, what is planned, what is missing, and what is merely recommended.

---

## 5. What a Command Is

> A registered, human-understandable operational capability, invokable through Master OS, that maps to an existing or future backend handler, workflow action, query, state transition, approval, navigation action, automated job, or restricted administrative action.

A command is a *record about a capability*. It is not the capability's code. The same command may eventually have multiple implementations, such as an API route, a button, a scheduled job, an internal automation, or an AI-assisted interface. The command remains stable even if its implementation changes.

---

## 6. Command Types

| Type | Meaning |
|---|---|
| `mutation` | Changes entity data without necessarily changing lifecycle state. |
| `approval` | Records a reviewer decision that gates downstream changes. |
| `query` | Retrieves information without side effects. |
| `navigation` | Opens a screen, entity, queue, or cross-system view. |
| `workflow_trigger` | Starts a multi-step operational process. |
| `automated_job` | Runs without continuous human interaction after invocation. |
| `restricted_administrative_action` | Elevated action outside normal operator permissions. |

Commands must not be confused with lifecycle states, system events, workflows, UI controls, or implementation handlers. A command may cause a lifecycle transition and emit an event, but those concepts remain distinct.

---

## 7. Registry Identity Model

Every command should have two identifiers.

### 7.1 Registry ID

Human-readable registry reference, e.g. `CMD000001`. Registry IDs are assigned sequentially and never reused.

### 7.2 Command Namespace

Stable semantic identifier, e.g. `intake.packet.submit`, following:

```
<owning_os>.<entity>.<verb>
```

Examples: `intake.packet.submit`, `intake.review.approve`, `restaurant.lifecycle.publish`, `submission.convert_to_intake`, `governance.pipeline.run`.

The registry ID identifies the registry record. The namespace identifies the operational capability. Namespaces should not be renamed after approval — if terminology changes materially, the prior command should be deprecated and superseded.

---

## 8. Registry Record Status

Registry status is distinct from implementation status.

### 8.1 Registry Status

| Status | Meaning |
|---|---|
| `draft` | Proposed record under development. |
| `under_review` | Being evaluated for approval. |
| `approved` | Accepted as part of GoldPan's operational architecture. |
| `deprecated` | Still referenced but should not be used for new work. |
| `superseded` | Replaced by another approved command. |
| `archived` | Retained only for organizational history. |

### 8.2 Implementation Status

| Status | Meaning |
|---|---|
| `implemented` | Fully usable through an approved Master OS path. |
| `partial` | Some implementation exists, but the command is incomplete or unreliable. |
| `missing` | Required but no usable implementation exists. |
| `future` | Blueprint-defined but assigned to a later phase. |
| `recommendation` | Proposed capability not yet approved by the Blueprint or a Decision Record. |

A command may be `registry_status: approved` and `implementation_status: missing` at the same time — that means GoldPan has approved the capability as necessary, but it has not yet been built.

---

## 9. Evidence Classification Standard

Every claim about GoldPan architecture, implementation, workflow, command, or feature must be classified.

| Level | Meaning | Required support |
|---|---|---|
| E1 — Implemented | Exists in the active repository or database. | Exact file, route, function, component, migration, table, or test. |
| E2 — Governing | Explicitly defined in a governing architecture or policy document. | Exact document version and section. |
| E3 — Planned | Documented in an approved specification, roadmap, issue, or design document. | Exact document or task reference. |
| E4 — Proposed | New recommendation or idea. | Must remain clearly labeled as proposed. |
| E0 — Unsupported / Unknown | No reliable supporting evidence was found. | State what was searched and what remains unknown. |

Rules:

1. E2 does not imply E1.
2. E3 does not imply approval.
3. E4 must never be presented as current architecture.
4. Confidence does not replace evidence.
5. If no evidence exists, preserve the result as unknown.

---

## 10. Decision Basis Standard

Every meaningful architectural or operational recommendation should state why it exists. Approved decision-basis categories:

- `observed_need`
- `architectural_requirement`
- `implementation_constraint`
- `operational_judgment`
- `experiment`
- `strategic_bet`
- `compliance_or_risk_control`

A decision may have more than one basis, e.g.:

```
Decision Basis:
- observed_need
- architectural_requirement
- compliance_or_risk_control
```

---

## 11. Facts, Assumptions, Inferences, Recommendations, and Decisions

GoldPan analysis must distinguish among:

- **Fact** — directly supported by repository evidence, database evidence, or governing documentation.
- **Assumption** — believed likely but not verified.
- **Inference** — a conclusion logically derived from one or more facts.
- **Recommendation** — a proposed future action or design.
- **Decision** — an approved choice that now governs future work.

Example:

```
Fact: Phase 5 includes packet review, review flags, approvals, and submission review.
Fact: No command registry architecture currently exists in the repository.
Inference: A registry specification must be established before commands can be consistently implemented.
Recommendation: Adopt stable command namespaces and registry IDs.
Decision: Pending Founder approval.
```

AI-generated reasoning must not silently become policy.

---

## 12. Command Record Schema

| Field | Required | Purpose |
|---|---|---|
| `registry_id` | Always | Stable human-readable registry reference. |
| `command_id` | Always | Stable namespaced capability identifier. |
| `registry_status` | Always | Draft, approved, deprecated, etc. |
| `name` | Always | Operator-facing command name. |
| `description` | Always | Plain-language explanation. |
| `owning_os` | Always | Sole OS module owning the underlying data or handler. |
| `supporting_os` | Optional | Modules read, invoked, or notified. |
| `command_type` | Always | One of the approved command types. |
| `primary_entity_type` | Always | Entity acted upon. |
| `allowed_roles` | Always | Roles authorized to invoke the command. |
| `required_permission` | When gated | Fine-grained permission. |
| `required_inputs` | When applicable | Required operator or runtime inputs. |
| `preconditions` | When applicable | Conditions required before execution. |
| `allowed_from_states` | When applicable | Explicit allowable lifecycle states. |
| `resulting_state` | When applicable | Lifecycle state after success. |
| `deterministic_validation` | When applicable | Software-enforced validation rules. |
| `approval_required` | Always | Whether another role must approve. |
| `approval_role` | When applicable | Required approver role. |
| `confirmation_required` | Always | Whether UI confirmation is required. |
| `reason_required` | Always | Whether the actor must provide a reason. |
| `risk_level` | Always | Low, medium, high, or critical. |
| `audit_required` | Always | Whether append-only audit logging is required. |
| `emitted_events` | When applicable | Structured events emitted after execution. |
| `rollback_policy` | Always | None, manual, compensating, or automatic. |
| `implementation_status` | Always | Implemented, partial, missing, future, or recommendation. |
| `implementation_version` | Optional | Current implementation version or migration reference. |
| `handler_reference` | When implemented | Exact API, function, route, job, or component. |
| `ui_locations` | When operator-facing | Screens or components where the command is available. |
| `build_phase` | Always | Relevant Blueprint phase. |
| `blueprint_references` | Always | Exact sections supporting the command. |
| `decision_dependencies` | When available | Decision Registry IDs governing the command. |
| `workflow_dependencies` | When available | Related Workflow Registry IDs. |
| `rule_dependencies` | When available | Related Governance Rule IDs. |
| `related_commands` | Optional | Commands that precede, follow, or compensate for this command. |
| `related_tables` | Optional | Tables read or mutated. |
| `related_apis` | Optional | APIs supporting execution. |
| `related_screens` | Optional | Screens exposing the command. |
| `related_agents` | Optional | AI agents permitted to assist. |
| `evidence_level` | Always | E0 through E4. |
| `notes` | Optional | Conflicts, limitations, technical debt, or migration notes. |

---

## 13. Decision Registry Integration

The Command Registry must not store complete architectural reasoning inside every command record. Commands should reference the Decision Records that justify them, e.g.:

```
decision_dependencies:
- DEC000014
- DEC000027
```

A future operator should be able to trace: **Command → Decision → Reasoning → Blueprint section → Workflow → Handler → Audit history.**

This provides organizational memory without duplicating reasoning across multiple records. The Decision Registry should eventually answer:

- Why does this command exist?
- Why is this command owned by this OS?
- Why is approval required?
- Why is this lifecycle transition allowed?
- Why is this role permitted or blocked?
- Why is this command manual rather than automated?

---

## 14. Registry Relationship Model

Commands should eventually connect to the following registries and system objects: Decisions, Workflows, Rules, Modules, Roles, States, Entities, Screens, APIs, Tables, Agents, Prompts, Events, Notifications, Audit records.

Example relationship view:

```
Command: Submit Intake Packet
Registry ID: CMD000003
Related Module: Intake OS
Related Workflow: Restaurant Intake
Related Decisions:
  DEC000014 — Intake Packet State Machine
  DEC000021 — Human Review Requirement
Related Rules:
  Evidence Boundary
  No Inference as Evidence
Related Screen: /admin/intake/submit
Related API: POST /admin/intake/submit
Related Table: operations.intake_packets
Related Events: intake.packet.submitted
Related Audit: Packet submission mutation record
```

The long-term Master OS architecture should treat these as connected knowledge objects rather than isolated documents.

---

## 15. Storage Recommendation

At the current stage, the Command Registry should remain version controlled, human readable, auditable through Git history, and easy to update alongside implementation changes.

Recommended structure:

```
docs/registry/
  COMMAND_REGISTRY.md
  command_registry.yaml
  decisions/
  workflows/
```

The Markdown document is the readable governing artifact. The YAML or JSON file may become the structured source used later by command bars, permissions systems, dynamic forms, documentation generators, audit tools, or AI agents.

Do not create a dedicated Command Registry database table in Phase 5 unless the registry must dynamically drive runtime behavior.

---

## 16. Phase 5 Scope

Phase 5 in the Blueprint is Intake OS UI. The expanded Phase 5 Command Registry should cover: intake queue, packet submission, JSON upload and paste, packet validation, packet review, review flags, approvals, returns, rejections, reopening, archival, submission review, restaurant and source linking, evidence ingestion handoff, governance handoff, publication-readiness handoff, audit visibility, and cross-system navigation required to complete Intake work.

The registry may include minimum handoff commands owned by Restaurant Operations OS, Knowledge OS, Governance OS, and Operations OS.

It must **not** expand into full Phase 6 Governance implementation, Analytics, Finance, portals, identity enrichment, or global command-bar development.

---

## 17. Phase 5 Command Inventory Summary

| # | Registry ID | Command ID | Type | Registry status | Implementation status | Notes |
|---|---|---|---|---|---|---|
| 1 | CMD000001 | `intake.queue.view` | query | approved | implemented | |
| 2 | CMD000002 | `intake.packet.view` | query | approved | implemented | |
| 3 | CMD000003 | `intake.packet.submit` | mutation | approved | implemented | |
| 4 | CMD000004 | `intake.packet.validate` | query | approved | partial | |
| 5 | CMD000005 | `intake.review.approve` | approval | approved | implemented | See §18 note — source-state gating drifts from DEC000001 §5.9. |
| 6 | CMD000006 | `intake.review.return` | approval | approved | implemented | See §18 note — source-state gating drifts from DEC000001 §5.9. |
| 7 | CMD000007 | `intake.packet.mark_ingested` | mutation | approved | implemented | Legacy path only — see §18 note. Planned deprecation once `commit_ingest` (CMD000008) is implemented, per DEC000001 §5.7. |
| 8 | CMD000008 | `intake.packet.commit_ingest` | automated_job | approved | missing | Type restored to `automated_job` (v0.1 original) — DEC000001 §5.7 does not redefine this command's type, only its role as the sole ordinary path to `ingested`. Once invoked it performs the durable write and status transition without continuous human interaction, matching the `automated_job` definition in §6; it was not reclassified as `mutation` by any Founder decision. |
| 9 | CMD000009 | `intake.packet.reject` | approval | approved | partial | RPC (migration 019) + API route + UI now exist — see §20. Live migration-execution status against the production database is unconfirmed from this session. |
| 10 | CMD000010 | `intake.packet.reopen` | restricted_administrative_action | draft | missing | Reserved for a future exceptional, restricted workflow — undefined and unbuilt by this decision; not to be built as a routine command. Per DEC000001 §5.1, §7 item 3. |
| 11 | CMD000011 | `intake.packet.archive` | mutation | approved | partial | RPC (migration 019) + API route + UI now exist — see §20. Live migration-execution status against the production database is unconfirmed from this session. |
| 12 | CMD000012 | `intake.review_flag.view` | query | draft | partial | Unchanged. |
| 13 | CMD000013 | `intake.review_flag.resolve` | mutation | draft | missing | Unchanged. |
| 14 | CMD000014 | `intake.candidate_schema.view` | query | draft | missing | Unchanged. |
| 15 | CMD000015 | `intake.send_to_governance` | workflow_trigger | draft | missing | Unchanged. |
| 16 | CMD000016 | `restaurant.view` | query | approved | implemented | |
| 17 | CMD000017 | `restaurant.intake.open` | navigation | approved | partial | |
| 18 | CMD000018 | `restaurant.intake.start` | workflow_trigger | draft | missing | |
| 19 | CMD000019 | `restaurant.lifecycle.publish` | mutation | approved | implemented | |
| 20 | CMD000020 | `restaurant.lifecycle.unpublish` | mutation | approved | implemented | |
| 21 | CMD000021 | `restaurant.lifecycle.advance_to_qa` | mutation | approved | implemented | |
| 22 | CMD000022 | `restaurant.lifecycle.advance_to_verification` | mutation | approved | implemented | |
| 23 | CMD000023 | `restaurant.lifecycle.recanvass` | mutation | approved | implemented | |
| 24 | CMD000024 | `submission.restaurant_update.view` | query | approved | missing | DEC000002 approved 2026-07-18. No query handler or router exists yet. |
| 25 | CMD000025 | `submission.restaurant_update.review` | approval | superseded | missing | Superseded by CMD000035-CMD000039 now that DEC000002 §5.5's discrete-command split is approved (2026-07-18). Not to be built as a compound command. |
| 26 | CMD000026 | `submission.convert_to_intake` | workflow_trigger | approved | missing | DEC000002 approved 2026-07-18 (§5.5, §7 item 3). Preconditions tightened per §5.5. Target (`operations.intake_packets`) is real and the FK exists (`resulting_intake_packet_id`, migration 021) — no RPC/handler built yet. |
| 27 | CMD000027 | `governance.result.view` | query | draft | missing | Unchanged. |
| 28 | CMD000028 | `governance.pipeline.run` | automated_job | draft | missing | Unchanged. Type restored to `automated_job` (v0.1 original) — DEC000001 governs the Intake namespace only and does not authorize changes to Governance command types; the earlier `workflow_trigger` value in this table was an incidental drift, not a decision. |
| 29 | CMD000029 | `knowledge.evidence.view` | query | draft | partial | Unchanged. |
| 30 | CMD000030 | `audit.log.view` | query | draft | missing | Unchanged. |
| 31 | CMD000031 | `intake.review.claim` | mutation | approved | partial | RPC (migration 018) + API route + UI now exist — see §20. Live migration-execution status against the production database is unconfirmed from this session. |
| 32 | CMD000032 | `intake.review.release` | mutation | approved | partial | RPC (migration 018) + API route + UI now exist — see §20. Live migration-execution status against the production database is unconfirmed from this session. |
| 33 | CMD000033 | `intake.packet.edit_payload` | mutation | approved | partial | RPC (migration 019) + API route + UI now exist — see §20. Live migration-execution status against the production database is unconfirmed from this session. |
| 34 | CMD000034 | `intake.packet.resubmit` | mutation | approved | partial | RPC (migration 019) + API route + UI now exist — see §20. Live migration-execution status against the production database is unconfirmed from this session. |
| 35 | CMD000035 | `submission.restaurant_update.claim` | mutation | approved | missing | DEC000002 approved 2026-07-18 (§5.6). Replaces part of former CMD000025. Schema (`claimed_by_user_id`, `claimed_at`) built in migration 021; no RPC. |
| 36 | CMD000036 | `submission.restaurant_update.release` | mutation | approved | missing | DEC000002 approved 2026-07-18 (§5.6). Replaces part of former CMD000025. Schema built in migration 021; no RPC. |
| 37 | CMD000037 | `submission.restaurant_update.return` | approval | approved | missing | DEC000002 approved 2026-07-18 (§5.5). Replaces part of former CMD000025. No RPC built. |
| 38 | CMD000038 | `submission.restaurant_update.approve` | approval | approved | missing | DEC000002 approved 2026-07-18 (§5.5). Replaces part of former CMD000025. Disposition-model schema (`disposition_type`, `disposition_status`, `resolution_summary`) built in migration 021; no RPC. |
| 39 | CMD000039 | `submission.restaurant_update.reject` | approval | approved | missing | DEC000002 approved 2026-07-18 (§5.5). Replaces part of former CMD000025. No RPC built. |
| 40 | CMD000040 | `submission.restaurant_update.resubmit` | mutation | draft | partial | DEC000002 §7 item 5 approves the command's existence, model, and mechanics only (2026-07-18) — invocation authority is explicitly withheld pending a separate role/portal-origin decision (§5.7). Registry status stays `draft` by the decision's own terms, not by oversight. Built in `022_submission_review_rpcs.sql` (`operations.resubmit_restaurant_update_submission`) with atomic parent/child creation and event logging, but **no `GRANT EXECUTE` was issued to any role** (`PUBLIC` explicitly revoked) — the function exists and is correct but cannot be invoked by anyone, including `service_role`. Classified `partial`, not `implemented`, on that basis. |
| 41 | CMD000041 | `submission.route_to_identity_review` | workflow_trigger | approved | missing | DEC000002 approved 2026-07-18 (§5.5, §7 item 3). Placeholder FK (`identity_review_item_id`, unconstrained) built in migration 021. Blocked on the Identity Review Queue table, which does not yet exist anywhere in the schema — building the destination is Restaurant Operations OS's own separate work, per DEC000002 §5.11. |
| 42 | CMD000042 | `submission.escalate_exception` | workflow_trigger | approved | missing | DEC000002 approved 2026-07-18 (§5.11, §7 item 3). Placeholder FK (`exception_request_id`, unconstrained) built in migration 021. Blocked on a Governance OS exception-request entity, not yet confirmed to exist anywhere in scope, per DEC000002 §5.11. |

**Registry-status legend note:** as of 2026-07-18, DEC000002 is approved and every `submission.*` command above (CMD000024, CMD000026, CMD000035-CMD000039, CMD000041, CMD000042) carries `registry_status: approved` on that basis, with two named exceptions: CMD000025 is `superseded` (replaced by the discrete claim/release/return/approve/reject split), and CMD000040 (`resubmit`) stays `draft` by DEC000002's own explicit carve-out (§7 item 5) — approval of the record does not extend to who may invoke `resubmit`. `registry_status: approved` above reflects only that each command's design is Founder-approved; see the `implementation_status` column and §20 for whether a handler actually exists.

**Approval-authority note (namespace governance is not the same as command approval):** DEC000001 governs the Intake Packet lifecycle, permissions, evidence boundaries, and transition semantics — it does not by itself approve every command in the `intake.*` namespace. `approved` rows in this table rest on two distinct bases, and neither is conflated with the other:
- **CMD000001-CMD000004, CMD000016-CMD000023** (query/navigation/mutation commands with no open lifecycle-state or permission question) are `approved` on the Registry framework's own basis — already implemented, in production use, and not subject to any disputed policy choice. Their approval predates and is independent of DEC000001.
- **CMD000005-CMD000011, CMD000031-CMD000034** are `approved` specifically because DEC000001 §7 makes an explicit Founder decision reaching each one's lifecycle dependency, permission boundary, or command model (items 1-5, approved 2026-07-13) — see each row's Notes or full §20 record for the specific DEC000001 citation. CMD000010 remains `draft` despite being in this set, since DEC000001 §7 item 3 explicitly reserves it rather than approving it.
- **CMD000024, CMD000026, CMD000035-CMD000039, CMD000041, CMD000042** are `approved` specifically because DEC000002 §7 makes an explicit Founder decision reaching each one's lifecycle dependency, permission boundary, or command model (items 1-9, approved 2026-07-18) — see each row's Notes above for the specific DEC000002 citation. CMD000025 is `superseded`, not `approved` or `draft`, since DEC000002 §5.5 replaces it outright rather than reserving or approving it as-is. CMD000040 (`resubmit`) remains `draft` despite being in this set, since DEC000002 §7 item 5 explicitly withholds approval of its invocation authority.

No row in this table is marked `approved` solely because its namespace is `intake.*` or `submission.*`; each has its own citation above.

---

## 18. Implemented Commands

**CMD000001 — View Intake Queue**
`command_id: intake.queue.view` · `owning_os: Intake OS` · `command_type: query` · `implementation_status: implemented` · `evidence_level: E1`
Implementation: `GET /admin/intake` → `get_intake_queue()` in `api/routers/intake.py`. UI: `web/app/admin/intake/page.tsx`. Supports optional status filtering.

**CMD000002 — View Intake Packet**
`command_id: intake.packet.view` · `owning_os: Intake OS` · `command_type: query` · `implementation_status: implemented` · `evidence_level: E1`
Implementation: `GET /admin/intake/{packet_id}` → `get_intake_packet()` in `api/routers/intake.py`. UI: `web/app/admin/intake/[id]/page.tsx`.

**CMD000003 — Submit Intake Packet**
`command_id: intake.packet.submit` · `owning_os: Intake OS` · `supporting_os: [Restaurant Operations OS]` · `command_type: mutation` · `implementation_status: implemented` · `evidence_level: E1`
Implementation: `POST /admin/intake/submit` → `submit_packet()` in `api/routers/intake.py`. UI: `web/app/admin/intake/submit/page.tsx`, `web/app/admin/intake/submit/actions.ts`, `submitIntakePacket()` in `web/lib/api.ts`. Supports both JSON file upload and JSON paste — two input modes of one command, not separate commands. The route resolves the restaurant from the external restaurant ID and enforces duplicate packet protection based on restaurant and canvass date.

**CMD000005 — Approve Intake Packet**
`command_id: intake.review.approve` · `owning_os: Intake OS` · `command_type: approval` · `implementation_status: implemented` · `evidence_level: E1`
Implementation: `POST /admin/intake/{packet_id}/approve` → `approve_packet()` in `api/routers/intake.py`, calling `operations.approve_intake_packet` (migration 017), which enforces `packet_status = in_review AND claimed_by_user_id IS NOT NULL` at the database layer regardless of what any caller sends. UI: `web/app/admin/intake/[id]/page.tsx` now gates the Approve control on the same precondition (`in_review` + claimed) rather than `pending_review`/`returned`.
**§18 note — source-state gating drift closed:** the drift previously recorded here (UI permitted approval from `pending_review`/`returned`, ahead of the claim/release model) is closed now that `intake.review.claim`/`.release` (CMD000031/CMD000032) have UI support — see §20. The RPC-level precondition was never actually loose; only the UI's button-visibility logic was. Confirming this end-to-end against a live database, with a real claimant, remains outstanding validation (see the accompanying report's validation section).

**CMD000006 — Return Intake Packet**
`command_id: intake.review.return` · `owning_os: Intake OS` · `command_type: approval` · `implementation_status: implemented` · `evidence_level: E1`
Implementation: `POST /admin/intake/{packet_id}/return` → `return_packet()` in `api/routers/intake.py`, calling `operations.return_intake_packet` (migration 017), which enforces `packet_status = in_review AND claimed_by_user_id IS NOT NULL` at the database layer. Requires a reason; optional reviewer notes. UI: `web/app/admin/intake/[id]/page.tsx` now gates the Return control on `in_review` + claimed.
**§18 note — source-state gating drift closed:** the drift previously recorded here (UI permitted return from `pending_review`/`approved`, and silently no-op'd on a blank reason instead of surfacing an error) is closed. The UI now gates on `in_review` + claimed and surfaces a visible error banner on a blank reason rather than swallowing the submission. Same outstanding end-to-end validation caveat as CMD000005 above.
**§18 note — authorization, corrected 2026-07-16 (Founder/CEO governance clarification; not claimant-only without exception):** ordinary use of `intake.review.return` is claimant-only, same as before. It is **not** claimant-only *without exception*: the Founder/CEO, acting as the company's active operator during GoldPan's early stage, may also override-return a packet they did not claim, provided they supply a non-blank reason; the override is logged distinctly from an ordinary self-return (DEC000001 §5.5). Today this authority is exercised through the existing `admin` database role — documented as the *current implementation adapter* for Founder/CEO authority, not a standing grant of override authority to every future administrator-tier account. Each written event records both `actor_role` (the literal DB role) and `authority_basis` (`governance_reviewer` or `founder_ceo_override`), so the audit trail distinguishes the technical role from the organizational authority it stands for. See DEC000001 §5.5 and migration `017_intake_review_decision_rpcs.sql`.
**§18 note — authorization, corrected 2026-07-16 (Founder/CEO governance clarification; not claimant-only without exception):** ordinary use of `intake.review.return` is claimant-only, same as before. It is **not** claimant-only *without exception*: the Founder/CEO, acting as the company's active operator during GoldPan's early stage, may also override-return a packet they did not claim, provided they supply a non-blank reason; the override is logged distinctly from an ordinary self-return (DEC000001 §5.5). Today this authority is exercised through the existing `admin` database role — documented as the *current implementation adapter* for Founder/CEO authority, not a standing grant of override authority to every future administrator-tier account. Each written event records both `actor_role` (the literal DB role) and `authority_basis` (`governance_reviewer` or `founder_ceo_override`), so the audit trail distinguishes the technical role from the organizational authority it stands for. See DEC000001 §5.5 and migration `017_intake_review_decision_rpcs.sql`.

**CMD000007 — Mark Intake Packet Ingested**
`command_id: intake.packet.mark_ingested` · `owning_os: Intake OS` · `command_type: mutation` · `registry_status: approved` · `implementation_status: implemented` · `evidence_level: E1`
Implementation: `POST /admin/intake/{packet_id}/ingest` → `mark_ingested()` in `api/routers/intake.py`. Requires packet status `approved`, sets status to `ingested`, records ingestion timestamp. Legacy path only. **Important:** this command currently marks the packet as ingested but does not perform the actual evidence write — the real ingestion operation remains separate and missing from Master OS (see CMD000008).
**§18 note — planned deprecation (DEC000001 §5.7):** `intake.packet.commit_ingest` (CMD000008) becomes the sole ordinary path to `ingested` — it performs the durable write and, only on confirmed success, sets `packet_status = ingested` atomically as its own last step. Once CMD000008 is implemented, `mark_ingested` should be retained only as a restricted, reason-required reconciliation tool for correcting drift between recorded status and actual evidence state — not exposed as a routine operator command, and not usable by a Governance Reviewer as a substitute for `commit_ingest`. Registry status remains plain `approved` for now — the deprecation is approved in principle but not yet executed, since the legacy path remains the only working ingestion trigger until CMD000008 ships. It will move to `deprecated` once CMD000008 is implemented and the reconciliation-only restriction is enforced.

**CMD000016 — View Restaurant**
`command_id: restaurant.view` · `owning_os: Restaurant Operations OS` · `command_type: query` · `implementation_status: implemented` · `evidence_level: E1`
Implementation: `fetchRestaurantDetail()` in `web/lib/api.ts`. UI: `web/app/admin/restaurants/[id]/page.tsx`.

**CMD000019–CMD000023 — Restaurant Lifecycle Commands**
`restaurant.lifecycle.publish`, `.unpublish`, `.advance_to_qa`, `.advance_to_verification`, `.recanvass` — share one handler: `PATCH /admin/restaurants/{external_id}/lifecycle` → `lifecycle_action()` in `api/routers/restaurants.py`. The backend uses `_LIFECYCLE_TRANSITIONS` to validate allowed transitions — an existing implementation pattern that closely matches the future registry structure.

---

## 19. Partially Implemented Commands

**CMD000004 — Validate Intake Packet**
Validation currently exists only in the frontend submit form (`web/app/admin/intake/submit/page.tsx`): required `restaurant`, `dishes`, `evidence_score`, `agent_metadata` keys; `dishes` must be an array. Limitations: no standalone validation endpoint, no server-side validation equivalent, backend submission trusts the payload after frontend validation, command cannot be independently invoked or audited.
`implementation_status: partial` · `evidence_level: E1`

**CMD000012 — View Review Flags**
Review flags are displayed inside the packet detail screen (`web/app/admin/intake/[id]/page.tsx`). Limitations: no dedicated flag table, no stable flag ID, no flag lifecycle, no dedicated review-flags queue, no query endpoint — flags exist as JSON array elements inside packet data.
`implementation_status: partial` · `evidence_level: E1`

**CMD000017 — Open Restaurant Intake**
The restaurant detail page (`web/app/admin/restaurants/[id]/page.tsx`) includes an Intake OS link. Limitation: the link opens the generic Intake queue rather than showing intake records scoped to the selected restaurant.
`implementation_status: partial` · `evidence_level: E1`

**CMD000029 — View Knowledge Evidence**
Evidence and dish information is visible indirectly through the Restaurant Master Page. The Knowledge OS page itself (`web/app/admin/knowledge/page.tsx`) remains a placeholder.
`implementation_status: partial` · `evidence_level: E1`

---

## 20. Required Missing Commands

**CMD000008 — Commit Intake Evidence** (`intake.packet.commit_ingest`)
Purpose: perform the actual durable write of approved packet evidence. Current reality: `ingest_packet.py --commit` writes packet data to Google Sheets; no API or Master OS UI exposes this operation. Must remain distinct from `intake.packet.mark_ingested`, since marking a status is not the same as writing evidence.
`command_type: automated_job` (v0.1 original, unchanged by DEC000001 — see §17 Notes) · `implementation_status: missing` · `evidence_level: E1` (for current CLI existence) / `E2` (for Blueprint-required ingestion flow)

**CMD000009 — Reject Intake Packet**
DEC000001 §5.10 defines `rejected` precisely: a terminal review determination that the record is fundamentally invalid or inappropriate as an Intake Packet (wrong restaurant, duplicate/test packet, unsupported source package, policy-invalid submission, packet created in error), distinct from the correctable `returned` state. Mechanism per §5.10: `in_review → rejected` only (must be claimed first, same precondition as approve/return); reason mandatory; logged to `intake_packet_events` (§5.8) with full reason; payload becomes immutable; no ingestion possible; reopening a rejected packet is out of scope for this command and remains reserved to a future, separately-decided exceptional workflow (see CMD000010). **Authorization (added 2026-07-16, Founder/CEO governance correction, DEC000001 §5.10):** ordinary use is claimant-only; the Founder/CEO may additionally perform an exceptional rejection override through the current `admin` role adapter, with a non-blank reason, logged distinctly (`actor_role: admin`, `authority_basis: founder_ceo_override`, `override: true`, prior claimant ID) — `admin` is the current technical adapter for Founder/CEO authority, not a standing grant to every future Administrator. Ordinary claimant rejection logs `authority_basis: governance_reviewer`, `override: false`. Implementation now spans all three layers: the RPC (`operations.reject_intake_packet`, migration 019), the API route (`POST /admin/intake/{packet_id}/reject` → `reject_packet()` in `api/routers/intake.py`), and the UI (Reject form, gated on `in_review` + claimed, in `web/app/admin/intake/[id]/page.tsx`).
`allowed_roles: Governance Reviewer (current claimant only); Founder/CEO via the admin adapter (non-claimant override, reason required)` · `implementation_status: partial` (RPC + API + UI code complete; live migration-execution status against the production database and end-to-end validation are unconfirmed from this session) · `evidence_level: E2` (Blueprint requirement) / now backed by DEC000001 §5.10 for the precise definition

**CMD000010 — Reopen Intake Packet**
No endpoint or supported lifecycle state currently exists. **Reserved and undefined per DEC000001 §5.1 and §7 item 3 — not to be built as a routine command.** DEC000001 explicitly declines to repurpose `reopen` as the ordinary return-and-fix mechanism (that role belongs to `intake.packet.edit_payload` + `intake.packet.resubmit`, CMD000033/CMD000034). `reopen` is reserved for a rarer, future, exceptional case — reactivating a packet already in a terminal or closed state (`ingested`, `rejected`, `archived`) for an elevated correction outside the ordinary review loop. This decision gives it no mechanism, preconditions, or resulting state; it must not be implemented, and CMD000010's registry entry must not be marked buildable, until a separate Decision Record defines it.
`implementation_status: missing` · `evidence_level: E2`

**CMD000011 — Archive Intake Packet**
`command_id: intake.packet.archive` · `owning_os: Intake OS` · `allowed_from_states: rejected, ingested` (DEC000001 §5.11 explicit allow-list) · `resulting_state: unchanged (archived_at/archived_by_user_id set; not a packet_status value)`
Implementation now spans all three layers: the RPC (`operations.archive_intake_packet`, migration 019), the API route (`POST /admin/intake/{packet_id}/archive` → `archive_packet()` in `api/routers/intake.py`), and the UI (Archive form, gated on `rejected`/`ingested`, in `web/app/admin/intake/[id]/page.tsx`). **Authorization (added 2026-07-16, Founder/CEO governance correction, DEC000001 §5.11 — replaces the prior "no specific role named" interpretation):** a Governance Reviewer may manually archive an eligible `rejected` packet only, and may not archive an `ingested` packet; the Founder/CEO, via the current `admin` role adapter, may manually archive either an eligible `rejected` or `ingested` packet; Intake Specialists and all other actors may not archive, regardless of status. `admin` is the current technical adapter for Founder/CEO authority here, not a standing grant to every future Administrator. Every manual archive requires a non-blank reason and preserves `actor_role`, `authority_basis` (`governance_reviewer` or `founder_ceo_override`), the eligible source status, and the reason in `intake_packet_events` (§5.8). Automated or policy-driven archival remains out of scope of this command.
`allowed_roles: Governance Reviewer (rejected only); Founder/CEO via the admin adapter (rejected or ingested)` · `implementation_status: partial` (RPC + API + UI code complete; live migration-execution status against the production database and end-to-end validation are unconfirmed from this session; the RPC writes `archived_at`/`archived_by_user_id` but neither field is exposed on `IntakePacketRow`/`IntakePacketDetail`, so the UI cannot yet display archive provenance) · `evidence_level: E2` · `audit_required: true` · `reason_required: true` · `decision_dependencies: DEC000001`

**CMD000013 — Resolve Review Flag**
No stable review-flag identity currently exists. A data-model change is required before this command can be implemented reliably. Required minimum flag attributes: `flag_id`, `packet_id`, `flag_type`, `status`, `severity`, `created_at`, `resolved_at`, `resolved_by`, `resolution_reason`.
`implementation_status: missing` · `evidence_level: E2`

**CMD000014 — View Candidate Schema Reports**
Current candidate schema output exists as a file artifact (`candidate_schema_report.json`) rather than a Master OS entity. No API or UI exposes it.
`implementation_status: missing` · `evidence_level: E2`

**CMD000015 — Send Intake to Governance**
Blueprint §3.4 lists "Send to Governance." No handler, queue, API, or UI currently performs the handoff. Governance remains a separate manual pipeline operation.
`implementation_status: missing` · `evidence_level: E2`

**CMD000018 — Start Intake from Restaurant**
Blueprint-defined in Restaurant Operations and Business Development. No route or UI currently starts Intake from a selected restaurant or partner record. Packets originate from the standalone intake submission screen.
`implementation_status: missing` · `evidence_level: E2`

**CMD000031 — Claim Intake Packet for Review**
`command_id: intake.review.claim` · `owning_os: Intake OS` · `command_type: mutation` · `registry_status: approved` · `implementation_status: partial` · `evidence_level: E2`
`allowed_roles: Governance Reviewer` · `allowed_from_states: pending_review` · `resulting_state: in_review`
DEC000001 §5.3-§5.5. Purpose: establishes exclusive review ownership before a decision command (`approve`/`return`/`reject`) may be invoked. Implemented as a single conditional update inside `operations.claim_intake_packet` (migration 018), not a read-then-write, matching DEC000001 §5.4's canonical form:
```sql
UPDATE operations.intake_packets
SET packet_status = 'in_review', claimed_by_user_id = :acting_user_id, claimed_at = now()
WHERE packet_id = :packet_id AND packet_status = 'pending_review' AND claimed_by_user_id IS NULL
RETURNING packet_id;
```
A zero-row result means the claim failed (already claimed, or no longer `pending_review`) and is reported to the caller as an explicit failure, not a false success. Sets `claimed_by_user_id` (stable user ID only, no display-name snapshot, per §5.3) and `claimed_at`. Emits a `claim` event (`actor_type: user`) to `intake_packet_events`, per §5.8. API route: `POST /admin/intake/{packet_id}/claim` → `claim_packet()` in `api/routers/intake.py`. UI: Claim control in `web/app/admin/intake/[id]/page.tsx`, gated on `pending_review` and unclaimed.
**Known deviation from a literal reading of the driving instruction:** the RPC accepts `pending_review` only, not `returned` — a `returned` packet's re-entry path to claimability is Edit Payload (optional) → Resubmit → `pending_review` → Claim. The UI follows the RPC rather than presenting a Claim control on `returned` packets that would always fail with a 409.
`audit_required: true` · `reason_required: false` · `decision_dependencies: DEC000001` · `implementation_status: partial` (RPC + API + UI code complete; live migration-execution status against the production database and end-to-end validation are unconfirmed from this session)

**CMD000032 — Release Claimed Intake Packet**
`command_id: intake.review.release` · `owning_os: Intake OS` · `command_type: mutation` · `registry_status: approved` · `implementation_status: partial` · `evidence_level: E2`
`allowed_roles: Governance Reviewer (self-release); any role authorized for administrative claim override (admin-override release)` · `allowed_from_states: in_review` · `resulting_state: pending_review`
DEC000001 §5.5. Purpose: returns a claimed packet to the unclaimed pool without recording a review decision. Clears `claimed_by_user_id`/`claimed_at`. Self-release by the current claimant requires no reason. Admin-override release **requires a reason**, logged distinctly from an ordinary self-release, per DEC000001 §5.5 — the permission is designed against the Blueprint's future role model (any role authorized for administrative claim override), not hard-coded to the current admin-only implementation. Emits a `release` event (`actor_type: user`, `reason` populated only for override) to `intake_packet_events`, per §5.8. Implementation now spans all three layers: the RPC (`operations.release_intake_packet`, migration 018), the API route (`POST /admin/intake/{packet_id}/release` → `release_packet()` in `api/routers/intake.py`), and the UI (Release control, gated on `in_review` + claimed, in `web/app/admin/intake/[id]/page.tsx`).
`audit_required: true` · `reason_required: conditionally (required for admin-override release only)` · `decision_dependencies: DEC000001` · `implementation_status: partial` (RPC + API + UI code complete; live migration-execution status against the production database and end-to-end validation are unconfirmed from this session)

**CMD000033 — Edit Intake Packet Payload**
`command_id: intake.packet.edit_payload` · `owning_os: Intake OS` · `command_type: mutation` · `registry_status: approved` · `implementation_status: partial` · `evidence_level: E2`
`allowed_roles: Intake Specialist only — a Governance Reviewer may not call this command under any circumstance (DEC000001 §4, §5.2)` · `allowed_from_states: returned` · `resulting_state: returned (unchanged — this is not a lifecycle transition)`
DEC000001 §5.1-§5.2. Purpose: edits `packet_data` while `packet_status = returned`, replacing the earlier `intake.packet.update` naming from v3 with a name precise about what it mutates (payload, not packet metadata generally). Every payload table in DEC000001 §5.2 gates this command to `returned` only — `pending_review`, `in_review`, `approved`, `ingested`, and `rejected` are all read-only/immutable to this command. Writes a payload revision record to `operations.intake_packet_revisions` (`revision_id`, `packet_id`, `prior_payload jsonb`, `actor_user_id`, `reason`, `created_at`) — always human-initiated, per §5.8. The packet-row update and the revision-table insert occur in one transaction inside `operations.edit_intake_packet_payload` (migration 019). API route: `POST /admin/intake/{packet_id}/edit_payload` → `edit_packet_payload()` in `api/routers/intake.py`. UI: a raw JSON textarea (pre-filled with the current `packet_data`) plus a required reason field, gated on `returned`, in `web/app/admin/intake/[id]/page.tsx` — client-side `JSON.parse` validation prevents malformed JSON from being submitted, but there is no structured field-level editor yet.
`audit_required: true` · `reason_required: true` · `decision_dependencies: DEC000001` · `related_tables: operations.intake_packets, operations.intake_packet_revisions` · `implementation_status: partial` (RPC + API + UI code complete; live migration-execution status against the production database and end-to-end validation are unconfirmed from this session)

**CMD000034 — Resubmit Intake Packet**
`command_id: intake.packet.resubmit` · `owning_os: Intake OS` · `command_type: mutation` · `registry_status: approved` · `implementation_status: partial` · `evidence_level: E2`
`allowed_roles: Intake Specialist only` · `allowed_from_states: returned` · `resulting_state: pending_review`
DEC000001 §5.1. Purpose: transitions `returned → pending_review` to re-queue a corrected packet for review. Does not touch `packet_data` — kept as a separate command from `edit_payload` (CMD000033) so a payload edit can be saved without immediately re-queuing, and so the event log distinguishes "what changed" from "state moved," per DEC000001 §5.1. Emits a `resubmit` event (`actor_type: user`) to `intake_packet_events`, per §5.8. Implementation now spans all three layers: the RPC (`operations.resubmit_intake_packet`, migration 019), the API route (`POST /admin/intake/{packet_id}/resubmit` → `resubmit_packet()` in `api/routers/intake.py`), and the UI (Resubmit control, gated on `returned`, in `web/app/admin/intake/[id]/page.tsx`).
`audit_required: true` · `reason_required: false` · `decision_dependencies: DEC000001` · `implementation_status: partial` (RPC + API + UI code complete; live migration-execution status against the production database and end-to-end validation are unconfirmed from this session)

**CMD000024 — View Restaurant Update Submission**
`command_id: submission.restaurant_update.view` · `owning_os: Restaurant Operations OS` · `command_type: query` · `registry_status: approved` · `implementation_status: missing` · `evidence_level: E1` (schema) / `E2` (required workflow)
DEC000002 approved 2026-07-18. The database schema exists (`operations.restaurant_update_submissions`, migration 021's full canonical model). No mounted router or UI exists.

**CMD000025 — Review Restaurant Update Submission**
`command_id: submission.restaurant_update.review` · `owning_os: Restaurant Operations OS` · `command_type: approval` · `registry_status: superseded` · `implementation_status: missing` · `evidence_level: E1` (schema) / `E2` (workflow)
**Superseded 2026-07-18.** DEC000002 §5.5's discrete-command replacement — `.claim`, `.release`, `.return`, `.approve`, `.reject` (CMD000035-CMD000039), mirroring the Intake OS claim/decision model in DEC000001 — is now Founder-approved. CMD000025 is retained in this table for traceability only; it is not to be built as a compound command.

**CMD000026 — Convert Submission to Intake**
`command_id: submission.convert_to_intake` · `owning_os: Intake OS` · `command_type: workflow_trigger` · `registry_status: approved` · `implementation_status: missing` · `evidence_level: E1` (schema readiness) / `E2` (workflow requirement)
`allowed_from_states: status = approved, disposition_type = intake_required, disposition_status ∈ {pending, failed}` · `resulting_state: disposition_status = in_progress`
DEC000002 approved 2026-07-18 (§5.5). Preconditions tightened per §5.5. Migration 021 built the canonical target FK, `resulting_intake_packet_id uuid REFERENCES operations.intake_packets(packet_id)` — the one downstream FK confirmed ready to build (§5.11) — but no RPC or handler connects submission approval to Intake packet creation yet. On success this command must set `disposition_status = in_progress`, record the linkage, and emit a `disposition_handoff_*` audit event (§5.10) once built.
`audit_required: true` · `decision_dependencies: DEC000002, DEC000001` · `related_tables: operations.restaurant_update_submissions, operations.intake_packets`

**CMD000035 — Claim Restaurant Update Submission for Review**
`command_id: submission.restaurant_update.claim` · `owning_os: Restaurant Operations OS` · `command_type: mutation` · `registry_status: approved` · `implementation_status: missing` · `evidence_level: E2`
`allowed_from_states: pending_review, claimed_by_user_id IS NULL` · `resulting_state: in_review`
DEC000002 approved 2026-07-18 (§5.6). Mirrors `intake.review.claim`'s atomic conditional-update pattern — a zero-row result means the claim failed and must be reported as an explicit failure, not a silent no-op. Schema built in migration 021 (`claimed_by_user_id`, `claimed_at`); no RPC.
`audit_required: true` · `reason_required: false` · `decision_dependencies: DEC000002`

**CMD000036 — Release Claimed Restaurant Update Submission**
`command_id: submission.restaurant_update.release` · `owning_os: Restaurant Operations OS` · `command_type: mutation` · `registry_status: approved` · `implementation_status: missing` · `evidence_level: E2`
`allowed_from_states: in_review` · `resulting_state: pending_review`
DEC000002 approved 2026-07-18 (§5.6). Self-release by the current claimant requires no reason; administrator-override release requires a reason, logged distinctly. Schema built in migration 021; no RPC.
`audit_required: true` · `reason_required: conditionally (required for admin-override release only)` · `decision_dependencies: DEC000002`

**CMD000037 — Return Restaurant Update Submission**
`command_id: submission.restaurant_update.return` · `owning_os: Restaurant Operations OS` · `command_type: approval` · `registry_status: approved` · `implementation_status: missing` · `evidence_level: E2`
`allowed_from_states: in_review` · `resulting_state: returned`
DEC000002 approved 2026-07-18 (§5.5). Clears the active claim and writes the reviewer identity into append-only event history (§5.10, `operations.restaurant_update_submission_events`, built in migration 021) atomically with the transition. No RPC built.
`audit_required: true` · `reason_required: true` · `decision_dependencies: DEC000002`

**CMD000038 — Approve Restaurant Update Submission**
`command_id: submission.restaurant_update.approve` · `owning_os: Restaurant Operations OS` · `command_type: approval` · `registry_status: approved` · `implementation_status: missing` · `evidence_level: E2`
`allowed_from_states: in_review` · `resulting_state: approved`
DEC000002 approved 2026-07-18 (§5.4, §5.5). Requires `disposition_type` and rejects `no_action` approvals missing `resolution_summary` — this is decision-blocking, per §5.4. Must, in one atomic operation, transition status, clear the claim, write the reviewer event, and derive the initial `disposition_status` from `disposition_type`. Disposition-model schema (`disposition_type`, `disposition_status`, `failure_stage`, `resolution_summary`) built in migration 021; no RPC.
`audit_required: true` · `reason_required: recommended, mandatory only for no_action (resolution_summary)` · `decision_dependencies: DEC000002`

**CMD000039 — Reject Restaurant Update Submission**
`command_id: submission.restaurant_update.reject` · `owning_os: Restaurant Operations OS` · `command_type: approval` · `registry_status: approved` · `implementation_status: missing` · `evidence_level: E2`
`allowed_from_states: in_review` · `resulting_state: rejected`
DEC000002 approved 2026-07-18 (§5.5). Mirrors `intake.packet.reject` — status flip, claim clear, mandatory-reason event. No RPC built.
`audit_required: true` · `reason_required: true` · `decision_dependencies: DEC000002`

**CMD000040 — Resubmit Restaurant Update Submission**
`command_id: submission.restaurant_update.resubmit` · `owning_os: Restaurant Operations OS` · `command_type: mutation` · `registry_status: draft` · `implementation_status: partial` · `evidence_level: E1` (built) 
`allowed_from_states: returned, superseded_by_submission_id IS NULL` · `resulting_state: parent → returned (unchanged, superseded_by_submission_id set); child created at pending_review`
**DEC000002 §7 item 5 approves this command's existence, model, and mechanics only (2026-07-18) — not who may invoke it.** Registry status stays `draft` by the decision's own explicit terms (§5.7), not by oversight; it cannot move to `approved` until a separate role/portal-origin decision resolves invocation authority. Built in `022_submission_review_rpcs.sql` as `operations.resubmit_restaurant_update_submission(p_submission_id uuid, p_actor_user_id uuid, p_payload_json jsonb DEFAULT NULL, p_description text DEFAULT NULL) RETURNS operations.restaurant_update_submissions` — atomic parent/child creation with `resubmission_of_submission_id`/`superseded_by_submission_id` linkage and cross-referenced `resubmit` events on both rows, per §5.7-§5.8. **No `GRANT EXECUTE` was issued to any role**, and `PUBLIC`'s default grant was explicitly `REVOKE`d — not even `service_role` can call it. Classified `partial`: the function is correctly built, but as a *command* (something callable) it does not yet function, since no actor has invocation authority. No API endpoint exists or can be wired to it until that authority is granted.
`audit_required: true` · `reason_required: false` · `decision_dependencies: DEC000002`

**CMD000041 — Route Restaurant Update Submission to Identity Review**
`command_id: submission.route_to_identity_review` · `owning_os: Restaurant Operations OS` · `command_type: workflow_trigger` · `registry_status: approved` · `implementation_status: missing` · `evidence_level: E2`
`allowed_from_states: status = approved, disposition_type = identity_review, disposition_status ∈ {pending, failed}` · `resulting_state: disposition_status = in_progress`
DEC000002 approved 2026-07-18 (§5.5, §7 item 3). Migration 021 built the placeholder FK (`identity_review_item_id uuid`, unconstrained). **Blocked:** no Identity Review Queue table has been inspected anywhere in the live schema — the destination is real in the Blueprint's governance model (`pending_restaurant_submission` status, referenced in the Blueprint's Identity/Enrichment section) but not yet an implemented entity. Building that destination table is Restaurant Operations OS's own separate work, outside DEC000002's scope to originate, per §5.11.
`audit_required: true` · `decision_dependencies: DEC000002` · `related_tables: operations.restaurant_update_submissions`

**CMD000042 — Escalate Restaurant Update Submission Exception**
`command_id: submission.escalate_exception` · `owning_os: Governance OS` · `command_type: workflow_trigger` · `registry_status: approved` · `implementation_status: missing` · `evidence_level: E2`
`allowed_from_states: status = approved, disposition_type = exception_escalation, disposition_status ∈ {pending, failed}` · `resulting_state: disposition_status = in_progress`
DEC000002 approved 2026-07-18 (§5.11, §7 item 3). Sole owner is Governance OS (not jointly Knowledge OS), per §5.2. Migration 021 built the placeholder FK (`exception_request_id uuid`, unconstrained). **Blocked:** no Governance OS exception-request entity has been inspected or confirmed to exist anywhere in scope — building `submission.escalate_exception` is blocked on Governance OS defining that entity, independent of this decision, per §5.11.
`audit_required: true` · `decision_dependencies: DEC000002` · `related_tables: operations.restaurant_update_submissions`

**CMD000027 — View Governance Result**
Governance UI is not yet built. Current Governance page is a placeholder.
`implementation_status: missing` · `evidence_level: E2` · `build_phase: Phase 6`

**CMD000028 — Run Governance Pipeline**
Governance processing currently requires manual Python execution. No Master OS command exists.
`implementation_status: missing` · `evidence_level: E1` (current manual pipeline) / `E2` (intended workflow)

**CMD000030 — View Audit Log**
The database audit table exists. No API or UI exposes it.
`implementation_status: missing` · `evidence_level: E1` (schema) / `E2` (Blueprint requirement)

---

## 21. Future Blueprint-Defined Commands

Explicitly outside the Phase 5 implementation scope:

- **Identity Enrichment** — Blueprint §5g places this after Phase 5. Potential future command: `restaurant.identity.enrich`.
- **Restaurant Identity Update System** — Blueprint §5h places this after Phase 5. Potential future commands: `restaurant.identity.candidate.accept`, `restaurant.identity.candidate.reject`, `restaurant.identity.conflict.resolve`.
- **Global Command Bar** — Blueprint §7b is a future consumer of the registry, not part of this Phase 5 implementation.
- **Full Governance Command Set** — Phase 6 may eventually include `governance.rule.create`, `governance.rule.update`, `governance.conflict.review`, `governance.outcome.override`, `governance.unknown.resolve`. These should not be implemented during Phase 5 unless required for a narrow Intake handoff.

---

## 22. State-Machine Conflicts Requiring Decision Records

These are architecture decisions, not ordinary coding tasks. Each should become a Decision Registry record.

**RESOLVED — Canonical Intake Packet State Machine (see DEC000001)**
Blueprint §5b and §5i previously described different Intake Packet lifecycles, and the database supported only a 4-state subset (`pending_review`, `returned`, `approved`, `ingested`) against Blueprint language listing up to eight (`draft`, `in_progress`, `submitted`, `in_review`, `rejected`, `archived`, `superseded`, plus the shared ones). **DEC000001 (`docs/decisions/DEC000001_CANONICAL_INTAKE_PACKET_STATE_MACHINE.md`) was Founder-approved 2026-07-13** and resolves this conflict. The canonical model is six `packet_status` values — `pending_review`, `in_review`, `returned`, `approved`, `rejected`, `ingested` — with `superseded_by_packet_id` and `archived_at` reclassified as non-status attributes/relationships rather than lifecycle states (DEC000001 §6, §7 item 4). `draft` is excluded from the canonical model, carried forward from an earlier finding not revisited by this decision. Commands may now publish definitive `allowed_from_states`/`resulting_state` values against this model — see §17's updated inventory and the CMD000031-CMD000034 full records in §20 above. The Blueprint §5b and §5i Intake Packet sections were updated in the same documentation propagation pass to reference and reflect DEC000001. DEC000001 remains the governing authority if later wording drift occurs.

**RESOLVED — Canonical Restaurant Update Submission State Machine (see DEC000002)**
Blueprint §5b, Blueprint §5i, and migration 011 previously contained different Submission lifecycle definitions, and no disposition/routing model existed anywhere. **DEC000002 (`docs/decisions/DEC000002_submission_state_machine.md`) was Founder-approved 2026-07-18** and resolves this conflict. The canonical model is the same five `status` values migration 011 already had (`pending_review`, `in_review`, `returned`, `approved`, `rejected`), plus a separate disposition model (`disposition_type`, `disposition_status`, `failure_stage`) that did not exist before, plus claim, resubmission-chain, archival, and downstream-linkage attributes (DEC000002 §5.1-§5.11). Built in `supabase/migrations/021_submission_state_machine.sql` and `022_submission_review_rpcs.sql` (committed `109fc2ba150fa81299bd384b690486d0dee6a640`) — schema, integrity triggers, append-only event table, and the `resubmit` RPC (mechanics only, no invocation authority granted, per §7 item 5). Command handlers for `.claim`/`.release`/`.return`/`.approve`/`.reject`/`.convert_to_intake` remain unbuilt — see §17's updated inventory and §20 above. The Blueprint §5i Restaurant Update Submission section was updated in the same documentation propagation pass to reference and reflect DEC000002. DEC000002 remains the governing authority if later wording drift occurs.

**DECISION REQUIRED — Intake Ingestion Destination**
The Blueprint implies Intake evidence flows into Supabase-backed Knowledge OS evidence tables. The current process writes to Google Sheets and later synchronizes generated files.
Required Decision Record — Title: *Canonical Intake Evidence Ingestion Architecture* — Suggested ID: **DEC000003**.
The decision must establish whether Phase 5 should preserve the Sheets-first pipeline, wrap it as a Master OS command, transition to direct Supabase ingestion, or operate temporarily in dual mode.

**DECISION REQUIRED — Review Flag Entity Model**
Blueprint navigation treats Review Flags as a first-class operational queue. The current implementation stores flags as packet JSON array elements.
Required Decision Record — Title: *Review Flag Persistence and Lifecycle Model* — Suggested ID: **DEC000004**.

---

## 23. Confirmed Correctness and Audit Gaps

**Lifecycle Note Is Discarded**
The restaurant lifecycle request accepts a `note`. The handler does not persist it. This creates the appearance of an audit reason without actually preserving the reason.
Required action: persist the note in an append-only audit record, or stop presenting the field as durable until fixed.
Suggested command metadata: `audit_required: true`, `implementation_status: partial`, `notes: audit reason currently discarded`.

**Intake Packets Lack Append-Only Review History**
Intake review data currently lives in mutable packet columns. A packet that is returned, approved, and reconsidered may overwrite prior review context.
Required minimum audit coverage: `actor`, `actor_role`, `action`, `previous_state`, `new_state`, `reason`, `reviewer_notes`, `timestamp`, `source`, `human_or_ai`.
This should be addressed before Intake review is considered fully production-governed.

---

## 24. Recommended Phase 5 Implementation Order

**Priority 1 — Approve the Registry Framework**
Approve registry ID format, command namespace format, evidence levels, registry status, implementation status, and decision dependency model. No UI build is required for this step.

**Priority 2 — Create the Decision Registry Foundation**
Create Decision Records for: (1) Canonical Intake Packet State Machine — **done, DEC000001, approved 2026-07-13**; (2) Canonical Submission State Machine — **done, DEC000002, approved 2026-07-18**; (3) Canonical Intake Evidence Ingestion Architecture (DEC000003, still required); (4) Review Flag Entity Model (DEC000004, still required). Priorities 1 and 2 are now approved for both Intake and Submission; the remaining decisions unblock reliable command definitions elsewhere.

**Priority 3 — Fix Silent Audit Failures**
Address the discarded restaurant lifecycle note and the missing Intake packet audit trail — trust and organizational-memory issues.

**Priority 4 — Build Submission Review**
Implement `submission.restaurant_update.view`, `.claim`, `.release`, `.return`, `.approve`, `.reject` (CMD000024, CMD000035-CMD000039 — replacing the retired compound `.review`), and `submission.convert_to_intake` (CMD000026). The schema and disposition model already exist (migration 021), and `resubmit`'s mechanics are already built (migration 022, invocation authority still withheld) — command handlers are the remaining, highest-leverage Phase 5 gap.

**Priority 5 — Expose Actual Ingestion**
Implement `intake.packet.commit_ingest` — the most important remaining operation that requires leaving Master OS. The command should clearly distinguish preview, commit, success, partial failure, and rollback or compensating action.

**Priority 6 — Complete Restaurant-to-Intake Handoff**
Implement `restaurant.intake.start` and `restaurant.intake.open`. The Intake page should be scoped to the selected restaurant when entered from a Restaurant Master Page or BD record.

**Priority 7 — Make Review Flags First-Class**
After the Review Flag Entity Model decision is approved: create stable flag identity, add flag status, expose a review queue, support resolve, dismiss, reopen, and escalation.

**Priority 8 — Preserve Later-Phase Scope**
Do not pull forward Identity Enrichment, full Governance UI, Analytics, Finance, portals, global command bar, or AI agent registry. The registry may document future commands without making them Phase 5 build obligations.

---

## 25. Phase 5 Completion Standard

Expanded Phase 5 is operationally complete when a trained nontechnical operator can perform the following entirely through Master OS:

1. Open a restaurant.
2. Start or resume Intake.
3. Link approved sources.
4. Upload or paste an Intake packet.
5. Validate the packet.
6. Correct validation issues.
7. Submit the packet.
8. Review flags.
9. Claim or begin review.
10. Return, reject, approve, reopen, or archive according to the canonical state machine.
11. Preserve reviewer reasoning and audit history.
12. Review restaurant update submissions.
13. Convert approved submissions into Intake work.
14. Commit approved evidence through the canonical ingestion path.
15. Trigger or queue Governance.
16. View resulting Governance status.
17. View evidence provenance.
18. Evaluate publication readiness.
19. Navigate between Restaurant, Intake, Knowledge, Governance, BD, and Audit records.
20. Understand why any action is blocked and what must happen next.

The operator should not need source code, terminal access, direct Supabase access, Postman, undocumented scripts, or repeated Claude instruction.

---

## 26. Governance Rule for Future Commands

Every new operational feature should answer:

1. What command does this implement?
2. Which OS owns it?
3. Which Decision Record authorizes it?
4. Which Workflow uses it?
5. Which roles may invoke it?
6. What states allow it?
7. What validation applies?
8. What audit record is produced?
9. What event is emitted?
10. How can an operator understand failure or blockage?

No implementation should silently create a new operational capability without either registering a new command or updating an existing command's implementation record.

---

## 27. Organizational Knowledge Architecture

The Command Registry is one component of a larger Master OS knowledge architecture. Master OS may eventually contain:

- Decision Registry — why choices were made
- Command Registry — what the system can do
- Workflow Registry — how work moves
- Rule Registry — how deterministic conclusions are produced
- Module Registry — which systems own what
- Role Registry — who may decide and operate
- State Registry — allowed lifecycle states
- Entity Registry — canonical business objects
- Agent Registry — AI capabilities and limits
- Prompt Registry — AI prompt versions
- API Registry — implementation interfaces
- Schema Registry — data contracts
- Notification Registry — event delivery behavior
- Feature Registry — feature flags and rollout state

These should not all be built immediately — they deserve a governed home in Master OS when they become operationally necessary. Current recommended priority: (1) Decision Registry, (2) Command Registry, (3) Workflow Registry, (4) Rule Registry, (5) additional registries only when operational value is clear.

---

## 28. Guiding Principle

GoldPan™ should be built according to the same evidence standards it applies to food transparency. That means: do not infer implementation, do not confuse recommendations with architecture, preserve uncertainty, record why decisions were made, preserve provenance, require review where truth is affected, and make every important change understandable to a future employee.

---

## 29. Final Architectural Position

The Command Registry is viable and should be adopted now. The registry itself should remain lightweight. The greater priority is not building a large registry application — the priority is establishing durable organizational structure:

**Blueprint → Decisions → Workflows → Commands → Implementations → Events → Audit History**

This is how Master OS reduces dependence on founder memory, developer knowledge, and external AI assistance while preserving the reasoning that makes GoldPan trustworthy.
