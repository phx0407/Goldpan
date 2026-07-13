# DEC000001 — Canonical Intake Packet State Machine

**Status:** draft — awaiting Founder approval
**Decision basis:** architectural_requirement, compliance_or_risk_control
**Decision dependencies:** none (this is a foundational record)
**Registry impact:** governs `intake.packet.*` namespace commands (CMD-series, see §3 below)

---

## 1. Competing versions, side by side

Four sources were checked. Blueprint §5b and §5i disagree with each other; the live DB and live API disagree with both and with each other in one place.

| Source | States (in order) | Notes |
|---|---|---|
| Blueprint §5b (State Machine Philosophy, lines 672-687) | `draft → in_progress → pending_review → in_review → approved → rejected → archived` | 7 states. Generic table covering multiple entity types, not intake-packet-specific. |
| Blueprint §5i (Data Lifecycle Standard, lines 1262-1421) | `draft → submitted → in_review → returned → approved → ingested → superseded → archived` | 8 states. Entity-specific table. States "packets are permanent audit records." Trust threshold = `approved`. |
| Live DB (`supabase/migrations/015_intake_packets.sql`, CHECK constraint) | `pending_review, returned, approved, ingested` | 4 states only. No `draft`, no `in_review`, no `rejected`, no `archived`, no `superseded`. |
| Live API (`api/routers/intake.py`) | Enforces: `submit_packet()` creates at `pending_review`; `approve_packet()` blocks if already `ingested`; `return_packet()` blocks if `ingested`, allows from `pending_review` **or** `approved`; `mark_ingested()` only from `approved` | Code permits an `approved → returned` transition that appears in no Blueprint version. |

**Corrective note on the source document:** `docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md` §22 claims Blueprint §5i "describes reopening" for intake packets. Direct inspection of §5i found no literal `reopen` state or transition — this appears to be an inference by that document's author, not a quoted Blueprint requirement. It is not carried forward as fact here.

## 2. Terminology and transition conflicts

- **`draft` exists in both Blueprint versions but not in the DB.** The DB's `pending_review` is the first state a packet can ever occupy — there is no code path to persist a packet before it is submitted for review. Whether pre-submission drafts should be persisted at all is an open question (see §7, assumptions).
- **`submitted` (§5i) vs `pending_review` (§5b, DB, API) name the same conceptual state** — packet has been created/submitted, awaiting a reviewer look. §5i's naming is closer to the entity's actual API verb (`submit_packet`); DB and API agree with §5b's terminology, not §5i's.
- **`in_review` exists in both Blueprint versions but has no DB or API representation.** There is no code state, no column value, and no endpoint that transitions a packet into a "someone is actively looking at this right now" state distinct from "queued for review." `pending_review` currently does double duty for both.
- **`rejected` (§5b) vs `returned` (§5i, DB, API).** These are not the same concept. §5b's `rejected` implies a terminal, non-recoverable outcome. §5i's and the live system's `returned` is explicitly a round-trip state — sent back to the canvasser with notes, implying resubmission. The DB has no `rejected` value at all; nothing in the live system supports a hard-reject outcome distinct from a returnable one.
- **`ingested` and `superseded` appear only in §5i and the DB (as `ingested`); §5b has neither.** `superseded` has no DB representation despite appearing in §5i — no CHECK constraint value, no code path sets it.
- **`archived` appears in both Blueprint versions but not in the DB/API.** Once a packet reaches `ingested`, there is no further code-level transition; it stays `ingested` permanently. Archival is unimplemented, not merely differently named.
- **The `approved → returned` transition in `return_packet()` matches no Blueprint version.** Both Blueprint tables treat `returned`/`rejected` as something that happens before approval, not after. This is a live-code behavior with no governing-document basis — evidence of reality, not evidence of correctness.

## 3. Phase 5 commands that depend on this decision

Per `docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md` §18-§20, the following command entries in the `intake.packet.*` namespace read or write `packet_status` and cannot be finalized (registry_status: approved) until this decision is made:

- `intake.packet.submit` — implemented (`submit_packet()`); sets initial status. Canonical model must confirm the initial-state name.
- `intake.packet.approve` — implemented (`approve_packet()`); canonical model must confirm allowed source states.
- `intake.packet.return` — implemented (`return_packet()`); canonical model must resolve whether `approved → returned` is legitimate or a bug to close.
- `intake.packet.ingest` — implemented (`mark_ingested()`); canonical model must confirm `approved` is the only valid source state (current code already enforces this — no conflict here).
- `intake.packet.resubmit` — **missing.** No endpoint exists to correct and resubmit a `returned` packet. Combined with the `UNIQUE(restaurant_external_id, canvass_date)` constraint on the table, a returned packet currently has **no working code path back into the queue**. This is a functional gap independent of which canonical model is chosen, and every candidate model below must specify how resubmission is meant to work.
- `intake.packet.archive` — future/missing. Cannot be built until `archived` (or an equivalent) is a real, canonical state.
- `intake.packet.supersede` — future/missing, same blocker.

## 4. Evaluation against the 9 criteria

Three candidate models are evaluated: **Candidate A** (adopt §5i as-is), **Candidate B** (adopt current DB/API as-is, formalized), **Candidate C** (revised canonical model combining elements).

| Criterion | §5b generic | §5i specific | Live DB/API | Notes |
|---|---|---|---|---|
| Operational clarity | Medium — generic table not written for this entity | High — purpose-built, most transitions map to real reviewer actions | Medium — 4 states force `pending_review` to mean two different things (queued and under active review) | §5i's clarity is real but incomplete (no resubmission) |
| Auditability | N/A — no audit-event mapping stated anywhere | High — "permanent audit records" stated explicitly | Low — no audit trigger exists on `intake_packets` (confirmed by grep of `006_triggers.sql`); no actor/timestamp/reason captured on status change beyond `reviewed_by`/`reviewed_at` | This is a real implementation gap regardless of which state model is chosen |
| Nontechnical usability | Low — abstract state names (`in_progress`) don't map to reviewer vocabulary | High — `returned`, `approved`, `ingested` match how a human reviewer already talks about packets | High — same vocabulary as §5i for the 4 states it has | §5i and live system agree here, which is a point in their favor |
| Evidence-boundary protection (§5 Blueprint) | Weak — doesn't distinguish "reviewed" from "trusted for downstream use" | Strong — explicit trust threshold at `approved`, matches Evidence Boundary doctrine | Strong — `mark_ingested()` is gated on `approved`, matching the same threshold in code | Live code already correctly implements §5i's trust-threshold rule; this is a point of genuine current-system correctness |
| Return/correction workflows | Unclear — `rejected` reads as terminal, no resubmission implied | Implied but not fully specified — `returned` implies correction but §5i doesn't detail the loop | **Broken** — `return_packet()` exists but nothing consumes a returned packet back into the pipeline | This is the single biggest concrete gap across all three sources and must be closed by whichever model is adopted |
| Archival/historical preservation | `archived` present, no detail | `archived` present, "permanent audit records" language, plus `superseded` for recanvass replacement | Absent — no archive state, no supersede state | Directly relevant to §5i design rule "archive over delete" and "recanvass refreshes, not replaces" |
| Implementation complexity to adopt | Low if chosen (already closest to nothing built) | Medium — requires adding `draft`, `in_review`, `superseded`, `archived` to the CHECK constraint and building transitions for each | Lowest — no schema change if adopted as-is, but formalizes an incomplete model | Complexity here is schema + endpoint work, not conceptual work |
| Migration risk | Low — no live data uses these state names beyond the 3 shared with DB | Low-medium — existing rows only use 4 of 8 states, so a superset migration is additive, not destructive | None — already live | Additive CHECK-constraint changes are low-risk; no existing row would become invalid under any of the three candidates |
| Compatibility with current data | High | High — current data is a strict subset of §5i's states | Trivially high | No candidate requires backfilling or reinterpreting existing `packet_status` values |

## 5. Recommendation

**Adopt Candidate C — a revised canonical model that takes §5i as its base (closest fit on auditability, usability, and evidence-boundary protection) and closes its two concrete gaps: resubmission and archival mechanics.**

Recommended canonical lifecycle:

```
draft → pending_review → in_review → returned → pending_review (resubmission loop)
                                    → approved → ingested → archived
                                    → approved → superseded (via recanvass)
```

Naming choice: `pending_review`, not `submitted` — matches the live API verb and existing DB values, minimizing rename churn, while still adopting §5i's fuller state set.

## 6. Nature of this recommendation

This **combines elements from multiple versions**: it takes §5i's full state set and trust-threshold philosophy, keeps §5b/DB/API naming for the shared states (`pending_review` over `submitted`), explicitly excludes §5b's `rejected` (no source shows a real terminal-reject use case distinct from `returned`, and introducing one is a scope decision the Founder should make separately if desired), and adds a defined resubmission transition that exists in no source document today. It does **not** simply adopt the live database as-is — the live implementation is missing three states (`draft`, `in_review`, `archived`/`superseded`) and one working transition (`returned → pending_review`) needed to satisfy Blueprint §5i's own stated design rules.

## 7. Assumptions

- Assumes "draft" should be a real, persisted state (a packet can exist before submission) rather than a purely client-side/pre-persistence concept. Alternative: keep packets ephemeral until submission and drop `draft` from the canonical model — listed as rejected alternative below.
- Assumes the `approved → returned` transition currently permitted by `return_packet()` is a bug relative to intended design, not an intentional "unapprove" feature, because no source document describes it. If it is intentional, this decision would need to be revisited before implementation.
- Assumes `rejected` (§5b) is not needed as a distinct terminal state separate from `returned`, since no source shows a workflow that requires a non-recoverable reject.

## 8. Alternatives rejected

- **Candidate A (adopt §5i verbatim):** rejected as the literal recommendation only because it doesn't specify the resubmission loop in enough detail to be implementable without further design — but it is the substantive basis for Candidate C, so this is a refinement, not a rejection of §5i's philosophy.
- **Candidate B (formalize live DB/API as the canonical model):** rejected. It would lock in known gaps (no audit trail, no resubmission, no archival) as permanent architecture rather than fixing them, and violates the explicit instruction that current implementation is evidence of reality, not proof of correct architecture.
- **Keep `rejected` as a §5b-style terminal state alongside `returned`:** rejected for this draft due to lack of evidence any workflow needs it; flagged as an open question for the Founder rather than silently decided either way (see §10).

## 9. Exact downstream changes this recommendation would require

**Blueprint (`docs/GOLDPAN_MASTER_OS_BLUEPRINT.md`):**
- §5i's Intake Packet lifecycle table: add explicit resubmission transition (`returned → pending_review`) and confirm `superseded` semantics point to the recanvass workflow.
- §5b's generic state machine table: either annotate that Intake Packet is an exception using its own §5i-derived table, or remove Intake Packet from any implied coverage by the generic table.

**Database (new migration, e.g. `01X_intake_packet_lifecycle_v2.sql`):**
- Alter `packet_status` CHECK constraint on `operations.intake_packets` to add: `draft`, `in_review`, `archived`, `superseded`.
- Remove the `UNIQUE(restaurant_external_id, canvass_date)` constraint or scope it to exclude `returned`/superseded rows, so a corrected resubmission for the same restaurant/date doesn't collide with the original.
- Add an audit trigger on `operations.intake_packets` status changes, consistent with the pattern already used for dishes/ingredients/allergen_disclosures in `006_triggers.sql`.

**API (`api/routers/intake.py`):**
- New endpoint: `resubmit_packet()` — accepts a `returned` packet's ID plus corrected `packet_data`, transitions to `pending_review`.
- `return_packet()`: remove `approved` as an allowed source state unless the Founder explicitly confirms `approved → returned` is intended (see §10).
- New endpoints: `archive_packet()` (from `ingested`) and `supersede_packet()` (from `approved`/`ingested`, triggered by a new canvass of the same restaurant).

**Frontend (`web/app/admin/`):**
- Intake queue view: add filter/tab for `in_review` (currently indistinguishable from `pending_review`), and a resubmission action on `returned` packets.
- Add archived/superseded views consistent with "archive over delete" — these records must remain visible, not disappear.

**Audit events:**
- Every new transition above must log actor, timestamp, and reason per Blueprint §5f.10 (Organizational Memory Principle) — currently unmet for any intake packet transition.

**Command Registry (`docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md`):**
- Update `intake.packet.return` implementation_status and note the source-state restriction change.
- Add new registry entries: `intake.packet.resubmit`, `intake.packet.archive`, `intake.packet.supersede` (currently listed as missing/future — this decision makes them buildable).
- Resolve §22's DEC000001 placeholder by referencing this file directly.

## 10. Risks, guardrails, validation criteria, revisit triggers

**Risks:**
- Removing `approved` as a valid source state for `return_packet()` could break an undocumented workflow if any current user relies on it — no usage telemetry was reviewed to confirm this, so this is a recommendation, not a verified-safe change.
- Expanding the CHECK constraint is additive and low-risk, but the resubmission uniqueness-constraint change touches data integrity and should be tested against existing rows before deployment.

**Guardrails:**
- No implementation should proceed until the Founder confirms or overrides the `approved → returned` assumption in §7.
- The resubmission endpoint must not allow a resubmitted packet to skip `pending_review`/`in_review` — it must re-enter the same review path as a first submission, not auto-approve.

**Validation criteria (for confirming this decision was correctly implemented):**
- Every `packet_status` value that exists in the DB after migration has at least one code path in and one code path out (except terminal states `ingested`→`archived` and `archived` itself).
- A `returned` packet can be corrected and resubmitted without violating the uniqueness constraint, and the original returned record is preserved (not overwritten), per "archive over delete."
- An audit trigger fires and records actor/timestamp/reason for every status transition.

**Revisit triggers:**
- If a real operational need for a hard, non-recoverable `rejected` state emerges (distinct from `returned`), this decision should be revisited to add it.
- If usage evidence shows `approved → returned` was an intentional, used feature, this decision's removal of that transition should be revisited before implementation.
