# DEC000001 — Canonical Intake Packet State Machine

**Status:** draft v2 — awaiting Founder approval (revised per Founder review of v1)
**Decision basis:** architectural_requirement, compliance_or_risk_control
**Decision dependencies:** none (foundational record)
**Registry impact:** governs `intake.packet.*` and `intake.review.*` namespace commands (see §3)

**Revision note:** v1 of this record proposed adding `draft`, `in_review`, `superseded`, and `archived` directly into `packet_status`, and proposed relaxing the `UNIQUE(restaurant_external_id, canvass_date)` constraint to support resubmission. Founder review identified that several of these moves added complexity or schema risk without a demonstrated operational need, and that the constraint change was unnecessary once resubmission is modeled correctly. This version replaces that analysis. Sections 1–3 (competing versions, terminology conflicts, dependent commands) carry forward from v1 largely unchanged; §4 onward is substantially revised.

---

## 1. Competing versions, side by side (unchanged from v1)

| Source | States (in order) | Notes |
|---|---|---|
| Blueprint §5b (State Machine Philosophy, lines 672-687) | `draft → in_progress → pending_review → in_review → approved → rejected → archived` | 7 states. Generic table covering multiple entity types, not intake-packet-specific. |
| Blueprint §5i (Data Lifecycle Standard, lines 1262-1421) | `draft → submitted → in_review → returned → approved → ingested → superseded → archived` | 8 states. Entity-specific table. States "packets are permanent audit records." Trust threshold = `approved`. |
| Live DB (`supabase/migrations/015_intake_packets.sql`, CHECK constraint) | `pending_review, returned, approved, ingested` | 4 states only. |
| Live API (`api/routers/intake.py`) | `submit_packet()` creates at `pending_review`; `approve_packet()` blocks if `ingested`; `return_packet()` blocks if `ingested`, allows from `pending_review` **or** `approved`; `mark_ingested()` only from `approved` | Code permits an `approved → returned` transition that appears in no Blueprint version. |

**Standing correction (from v1, still applies):** §22 of `docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md` claims Blueprint §5i "describes reopening." Direct inspection found no literal `reopen` state or transition in §5i. This is an inference by that document's author, not quoted Blueprint text.

**New finding this revision:** `docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md` §§17-21 independently list three commands relevant to this decision that were not addressed in v1:
- `intake.packet.reject` (CMD000009, `approval`, currently `missing`)
- `intake.packet.reopen` (CMD000010, `mutation`, currently `missing`)
- `intake.packet.archive` (CMD000011, `mutation`, currently `missing`)
- `intake.packet.commit_ingest` (CMD000008, `automated_job`, currently `missing`) — the actual durable evidence write (`ingest_packet.py --commit`), explicitly documented as distinct from `mark_ingested` (which only flips a status flag). This is relevant evidence for §5 below.

These are registry-level placeholders, not Blueprint requirements — they carry the same evidentiary weight as the rest of that draft document (i.e., none, until approved), but they are useful corroborating signal about what the framework's own author anticipated needing, and this revision reconciles its naming against them rather than inventing new command names in parallel.

## 2. Terminology and transition conflicts (unchanged from v1)

- `draft` exists in both Blueprint versions, not in the DB.
- `submitted` (§5i) and `pending_review` (§5b, DB, API) name the same conceptual state.
- `in_review` exists in both Blueprint versions, has no DB or API representation; `pending_review` currently does double duty for "queued" and "under active review."
- `rejected` (§5b) and `returned` (§5i, DB, API) are not the same concept — `rejected` implies terminal/non-recoverable, `returned` implies a correction round-trip.
- `ingested` and `superseded` appear only in §5i/DB (as `ingested`); §5b has neither.
- `archived` appears in both Blueprint versions, not in DB/API.
- The live `approved → returned` transition matches no Blueprint version.

## 3. Phase 5 commands that depend on this decision

Per the Command Registry inventory (§18-§21), with corrected naming per the Founder's instruction not to silently rename existing entries:

- `intake.packet.submit` (CMD000003, implemented) — sets initial status.
- `intake.review.approve` (CMD000005, implemented) — **existing namespace, not renamed.** Canonical model must confirm allowed source states.
- `intake.review.return` (CMD000006, implemented) — **existing namespace, not renamed.** Canonical model must resolve the `approved → returned` question.
- `intake.packet.mark_ingested` (CMD000007, implemented) — status flag only; no conflict, current code already restricts this to `approved` source.
- `intake.packet.commit_ingest` (CMD000008, missing) — the actual durable evidence write; relevant to §5's terminal-status analysis but not itself a `packet_status` value.
- `intake.packet.reject` (CMD000009, missing) — **open question, not adopted by default.** See §5.3.
- `intake.packet.reopen` (CMD000010, missing) — **proposed home for the resubmission mechanism.** See §5.1. This corrects v1, which invented a new `intake.packet.resubmit` command name instead of using the one the registry had already reserved.
- `intake.packet.archive` (CMD000011, missing) — **proposed to set a retention attribute, not a status transition.** See §5.2.
- **New, not currently in the registry:** `intake.review.claim`, `intake.review.release` — required only if `in_review` is adopted as a canonical status. See §5.4. Flagged per the Founder's instruction as a namespace addition requiring separate approval, not silently folded into this record.

## 4. Candidate models

Three candidates, replacing v1's Candidate A/B/C:

- **Candidate D (Founder's narrow model, §8 of review comments):** `pending_review → in_review → returned → pending_review` and `in_review → approved → ingested`. Five `packet_status` values. Supersession and archival modeled as relationships/attributes, not statuses. Resubmission is an in-place correction of the same row.
- **Candidate E (v1's model, carried forward for comparison only):** eight-value `packet_status` including `draft`, `superseded`, `archived` as statuses, plus a new packet row for resubmission via `revision_of_packet_id`.
- **Candidate F (status quo, formalized):** the current four DB values, no new capability.

## 5. Resolution of each architectural issue raised

### 5.1 Resubmission and uniqueness

Two models were evaluated, per the Founder's instruction:

- **Model A — correct and resubmit the same row.** A `returned` packet is corrected via `intake.packet.reopen`, which updates `packet_data` in place and moves `packet_status` back to `pending_review`. `packet_id` is stable throughout the packet's life. Because this is an `UPDATE`, not an `INSERT`, **the `UNIQUE(restaurant_external_id, canvass_date)` constraint is never touched and never needs to change.** History is preserved via an append-only revision table (§5.6), not via the constraint.
- **Model B — new row per revision.** Each correction creates a new packet row linked via `revision_of_packet_id`/`supersedes_packet_id`, requiring the uniqueness constraint to become revision-aware (e.g., unique on `(restaurant_external_id, canvass_date, revision_number)` or partial-unique on the latest revision only).

**Recommendation: Model A.** It is materially lower complexity — no constraint redesign, no new FK for revision chains, no "which row is canonical" query logic anywhere the packet is looked up by `packet_id`. Canonical packet identity is simply: one `packet_id` per canvassing run, full stop; corrections mutate that row's `packet_data` and are recorded in the revision table. Model B would only be justified if there were a demonstrated need to keep every historical `packet_data` payload independently queryable/joinable as its own row (e.g., for point-in-time evidence reconstruction at the row level) — no such need is evidenced in the current system. v1's recommendation to weaken the uniqueness constraint is withdrawn; it was an artifact of implicitly assuming Model B without evaluating Model A first.

### 5.2 Superseded — not a `packet_status` value

Agreed with the Founder's framing: a packet is a point-in-time audit artifact of one canvassing run. A later canvass superseding that packet's *evidence* is a fact about the relationship between two packets, not a change to the earlier packet's own processing history — the earlier packet was still correctly submitted, reviewed, approved, and ingested; none of that becomes false when a newer packet arrives.

**Recommendation:** do not add `superseded` to `packet_status`. Instead add a nullable relationship column, `superseded_by_packet_id uuid REFERENCES operations.intake_packets(packet_id)`, set on the *older* packet when a newer `ingested` packet exists for the same restaurant. This is system-computed at the time the newer packet reaches `ingested` (via `intake.packet.commit_ingest` or `mark_ingested`), not a separate human-invoked command — no new command surface is needed for it. `packet_status` on the older row remains `ingested` permanently, which is accurate: it was ingested, and still was, even though newer evidence now supersedes it downstream. This directly answers the Founder's question — `superseded` is not limited to an `ingested → superseded` transition because it was never a transition; it is a link between two independently terminal packets.

### 5.3 `draft` — excluded from the current lifecycle

Checked against actual Phase 5 operational reality: packets are produced by `intake_agent.py` as complete, structured JSON and handed to `submit_packet()` as a single atomic action. There is no packet-authoring UI in Master OS today, and no operator workflow that builds a packet incrementally inside the system. Nothing currently creates a packet in a not-yet-submitted, persisted state.

**Recommendation:** exclude `draft` from the Phase 5 `packet_status` enum. It is not evidenced by current operations, only by Blueprint prose describing a general-purpose state machine not written for this entity. If Master OS later grows an in-app packet-authoring capability, `draft` can be added then, against a real requirement, rather than spent now on a hypothetical one.

### 5.4 `in_review` — kept, with a minimal ownership mechanism scoped to Phase 5

`in_review` is retained in Candidate D because it answers a real question `pending_review` cannot: whether a packet is sitting untouched in the queue or is actively being looked at by someone right now. But per the Founder's instruction, it is not added as a bare label — a concrete mechanism is specified:

- **Claim:** new nullable columns on `operations.intake_packets`: `claimed_by text`, `claimed_at timestamptz`. `intake.review.claim` (new command) sets both and moves `packet_status` to `in_review`, guarded by `WHERE claimed_by IS NULL` so two reviewers cannot claim the same packet simultaneously.
- **Release:** `intake.review.release` (new command) clears both columns and returns `packet_status` to `pending_review`.
- **Reassignment:** for Phase 5, no separate reassign command — an admin releases, then claims (or another admin directly overwrites `claimed_by`/`claimed_at` via an admin-override path). All Phase 5 users are admin-role already (RLS is admin-only per migration 015), so a dedicated reassignment workflow with permission checks is not justified yet.
- **Stale-claim recovery:** manual for Phase 5 — any admin can release any packet regardless of who claimed it, since there is no multi-tenant permission boundary to protect against that today. An automated timeout (e.g., auto-release after N hours idle) is deferred as a future enhancement; no evidence of a stuck-claim problem exists yet to justify building it now.
- **Concurrency:** the `WHERE claimed_by IS NULL` guard on claim is a single-writer check, not row-level locking — sufficient at Phase 5's operational scale (a small internal review team, low packet volume) and consistent with the framework's existing tolerance for admin-trust rather than defense-in-depth (see RLS comment in migration 015: "No anon or authenticated policies: Intake OS is admin-only").

This is a genuine, if modest, scope addition beyond a status-label rename — two new columns, two new commands. It is called out explicitly in the Founder decision list (§10) rather than bundled silently into "add `in_review`."

### 5.5 `archived` — retention attribute, not a status

Per the Founder's suggestion: `ingested` already correctly marks the terminal point where a packet's evidence has been durably committed (via `intake.packet.commit_ingest`) — that is the actual trust/durability boundary, and it does not change when a packet is later archived. Archival is a visibility/retention concern: keeping old `ingested` packets out of the active queue view without deleting them, consistent with Blueprint's "archive over delete" design rule.

**Recommendation:** add `archived_at timestamptz` (nullable) to `operations.intake_packets`, not an `archived` status value. `intake.packet.archive` sets `archived_at = now()`; queue views default to `WHERE archived_at IS NULL`; nothing else changes. This is routine, not exceptional — likely triggered by a scheduled job (e.g., archive `ingested` packets older than N months) with a manual override available, though the exact trigger policy is an operational decision, not an architectural one, and is left open for the Founder or an operator to set. `ingested` remains sufficient as the permanent terminal processing status; `archived_at` layers retention semantics on top without duplicating or overloading it.

### 5.6 History preservation — corrected requirement

v1 stated a validation requirement that "the original returned record is preserved (not overwritten)." Under Model A (§5.1), the packet row *is* updated in place, so that literal requirement cannot hold and is withdrawn. The real requirement, restated:

The system must preserve, per packet, an append-only record of:
- the pre-return `packet_data` payload,
- the return decision, reason, reviewer, and timestamp,
- the corrected `packet_data` payload,
- the resubmission event (actor, timestamp),
- and every subsequent decision (approve, reject if adopted, ingest, archive).

**Recommendation:** a new table, `operations.intake_packet_revisions` (or equivalent), append-only, one row per state-changing event on a packet, storing `packet_id`, event type, actor, timestamp, reason (nullable), and a snapshot of `packet_data` at that point where the event changes the payload (return and resubmit events specifically). This also directly closes the standing audit-trigger gap noted in the framework memo and in v1 §4 (no audit trigger currently exists on `intake_packets`) — one mechanism serves both the audit requirement and the history-preservation requirement.

## 6. Recommended canonical model (Candidate D, refined)

```
packet_status:  pending_review → in_review → returned → pending_review (loop, same row)
                in_review → approved → ingested   (terminal)

Attributes, not statuses:
  claimed_by, claimed_at        — in_review ownership
  superseded_by_packet_id       — set on an older ingested packet by a newer one
  archived_at                   — retention marker, independent of packet_status
```

Five `packet_status` values total: `pending_review`, `in_review`, `returned`, `approved`, `ingested`. This is one value more than the live DB (`in_review` is the only addition to the status enum itself), plus three relationship/attribute columns and one new revision-history table — a materially smaller and lower-risk change than v1 proposed.

**`rejected` is deliberately left undecided, not silently excluded.** v1 dismissed it for lack of evidence. This revision found weak but real registry-level evidence (`intake.packet.reject`, CMD000009) that the framework's own author anticipated needing it. That is not strong enough evidence to adopt it outright (it is speculation within the same unapproved draft, not independent confirmation), but it is strong enough that omitting it should be a visible Founder choice, not an assumption. See §10.

## 7. Nature of this recommendation

This combines elements from multiple sources and from the Founder's own framing: it keeps `pending_review`/`returned`/`approved`/`ingested` naming from the live system (§5b/DB/API agreement), adds `in_review` from both Blueprint versions but only with a concrete ownership mechanism neither Blueprint version specifies, and explicitly declines to promote `draft`, `superseded`, or `archived` into `packet_status` — instead representing them as attributes/relationships, which no source document proposed in those terms but which better fits the evidence about how these concepts are actually used (point-in-time audit artifact, retention vs. processing, ownership vs. terminal state).

## 8. Assumptions

- Assumes `intake.packet.reopen` (CMD000010) is the correct namespace home for the resubmission action (payload correction + `returned → pending_review`), since the registry lists it as missing with no further definition. If the Founder intends `reopen` to mean something narrower (e.g., only unlocking the packet for viewing, not payload correction), this needs a different or additional command name — flagged as an open question, not assumed silently.
- Assumes Phase 5's admin-only, small-team operational context justifies the minimal (non-locking, manually-recoverable) claim mechanism in §5.4 rather than a fuller concurrency-control design.
- Assumes the archival trigger policy (age-based, manual, or both) is an operational parameter to be set later, not an architectural decision this record needs to fix.

## 9. Alternatives rejected

- **Candidate E (v1's model — 8-value status enum, revision-per-row via `revision_of_packet_id`):** rejected as higher complexity than necessary. Retained above only as a comparison point, per the Founder's request to evaluate it explicitly against the narrower model.
- **Candidate F (status quo, formalized):** rejected — leaves the queue-ownership ambiguity (`pending_review` meaning both "untouched" and "being worked") unresolved, and leaves the audit-trail gap open.
- **Automated stale-claim recovery (timers/expiry):** considered as part of §5.4, rejected for Phase 5 specifically for lack of evidence of need; not rejected permanently — listed as a revisit trigger in §10.

## 10. Exact downstream changes this recommendation would require

**Blueprint (`docs/GOLDPAN_MASTER_OS_BLUEPRINT.md`):**
- §5i's Intake Packet lifecycle table: revise to the 5-value `packet_status` set plus the three attribute columns, replacing the current 8-state table.
- §5b's generic state machine table: annotate that Intake Packet uses its own entity-specific model rather than the generic table, given the two now diverge more explicitly (no `draft`, no `rejected` by default, no `archived`-as-status).

**Database (new migration, e.g. `01X_intake_packet_lifecycle_v2.sql`):**
- Add `in_review` to the `packet_status` CHECK constraint. **No other status values added; the `UNIQUE(restaurant_external_id, canvass_date)` constraint is unchanged.**
- Add columns: `claimed_by text`, `claimed_at timestamptz`, `superseded_by_packet_id uuid REFERENCES operations.intake_packets(packet_id)`, `archived_at timestamptz`.
- Add new table `operations.intake_packet_revisions` (append-only), per §5.6.

**API (`api/routers/intake.py`):**
- New endpoints: `intake.packet.reopen` (correct payload, `returned → pending_review`, writes a revision record), `intake.review.claim`, `intake.review.release`, `intake.packet.archive` (sets `archived_at`).
- `intake.review.return`: remove `approved` as an allowed source state unless the Founder confirms it is intentional (carried forward from v1, unresolved — see Founder decisions below).
- `intake.packet.mark_ingested` / `intake.packet.commit_ingest`: on reaching `ingested`, check for and link any prior packet for the same restaurant via `superseded_by_packet_id`.
- `intake.packet.reject`: **not built** unless the Founder opts in — see §10 Founder decisions.

**Frontend (`web/app/admin/`):**
- Intake queue: add claim/release controls and an "in review by X" indicator; add a reopen/correct action on `returned` packets; default queue view filters out `archived_at IS NOT NULL` rows with an explicit "show archived" toggle.

**Audit events:**
- The `intake_packet_revisions` table serves as the audit record for payload-changing events; status-only transitions (claim/release/approve/return without payload change) should still log actor/timestamp/reason per §5f.10, either in the same table or a lighter-weight companion log — implementation detail, not an open architectural question.

**Command Registry (`docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md`):**
- Update `intake.review.return` implementation_status/notes for the source-state restriction.
- Update `intake.packet.reopen`, `intake.packet.archive` from `missing` to buildable, with the specific behavior defined above.
- Add two new registry entries not currently present: `intake.review.claim`, `intake.review.release`.
- Leave `intake.packet.reject` as `missing` pending the Founder decision below.

## 11. Founder decisions required (revised)

1. **Confirm Model A (correct-in-place resubmission) over Model B (new row per revision).** No constraint change follows from Model A; a constraint redesign follows from Model B.
2. **Confirm `superseded_by_packet_id` (relationship) over a `superseded` status value.**
3. **Confirm excluding `draft` from Phase 5**, reserved for a future packet-authoring capability if one is ever built.
4. **Confirm the minimal, non-locking `in_review` claim mechanism** (§5.4) is appropriate for Phase 5's scale, versus building fuller concurrency control now.
5. **Confirm `archived_at` (attribute) over an `archived` status value.**
6. **Decide on `rejected`/`intake.packet.reject`.** Not adopted by default in this revision; the registry's own placeholder (CMD000009) is the only evidence for it, which this record treats as insufficient to adopt unprompted. If the Founder wants a hard-terminal reject state, say so explicitly.
7. **Resolve the standing `approved → returned` question from v1** — is it a bug to close, or an intentional feature? Still unconfirmed.
8. **Confirm `intake.packet.reopen` is the correct name/semantics for the resubmission command**, or specify different intended behavior for that reserved name.

## 12. Risks, guardrails, validation criteria, revisit triggers

**Risks:**
- The claim mechanism's `WHERE claimed_by IS NULL` guard is a check-then-set, not a database-level atomic lock; under true concurrent requests there's a narrow race window. Acceptable at Phase 5's volume; would need a proper `SELECT ... FOR UPDATE` or equivalent if review volume/concurrency grows materially.
- Removing `approved` as a valid source state for `intake.review.return` could break an undocumented workflow if any current use relies on it — unverified, per v1's original note.

**Guardrails:**
- No implementation proceeds until Founder decisions 1-8 above are made.
- `intake.packet.reopen` must not allow a resubmitted packet to skip `pending_review`/`in_review` — it must re-enter the same review path as a first submission.

**Validation criteria:**
- Every `packet_status` value has at least one code path in and one code path out.
- A returned packet can be corrected and resubmitted with the same `packet_id`, without touching the uniqueness constraint, and its full history is reconstructable from `intake_packet_revisions`.
- `superseded_by_packet_id` is set automatically and correctly whenever a second packet for the same restaurant reaches `ingested`.

**Revisit triggers:**
- If claim contention becomes a real operational problem, revisit the concurrency model in §5.4.
- If a genuine hard-reject use case emerges, revisit decision 6.
- If Master OS grows in-app packet authoring, revisit decision 3.
