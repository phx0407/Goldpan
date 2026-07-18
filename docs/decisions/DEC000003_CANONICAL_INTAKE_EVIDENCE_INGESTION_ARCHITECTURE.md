# DEC000003 — Canonical Intake Evidence Ingestion Architecture

**Status:** approved — Founder approved 2026-07-16 (policy and semantics layer only). No schema, RPC, or application code implementing this decision has been written or executed.
**Approval date:** 2026-07-16
**Decision basis:** architectural_requirement, compliance_or_risk_control (allergen-disclosure fidelity is food-safety-adjacent)
**Decision dependencies:** DEC000001 §5.7 (interpreted and operationalized by this record, not amended — see §2 below); sibling to DEC000002; does not resolve `intake.packet.reopen` (CMD000010), which DEC000001 line 38 and §5.9 reserve as separate, future governance work — see §5 below.
**Registry impact:** governs the precondition and failure-behavior contract for `intake.packet.commit_ingest` (the sole path from `approved` to `ingested`, per DEC000001 §5.5); establishes a new governed action, **Evidence Disposition**, that is not yet a named Command Registry entry (no command name or CMD ID is assigned by this record — flagged as an open item in the accompanying report); does not add, remove, or rename any `packet_status` value and does not touch `intake.packet.reopen`'s registry status (`CMD000010`, reserved/undefined).

**Founder approval note:** approved as ruled during the 2026-07-16 Founder review session, which resolved all six blocking decisions previously open in the DEC000003 groundwork document (`docs/decisions/DEC000003_INTAKE_EVIDENCE_SCHEMA_GAP_MAP.md`, hereafter "the gap map"). This record formalizes those six rulings — and the DEC000001 §5.7 non-amendment ruling that preceded them the same day — into a canonical Decision Record matching the structure of DEC000001 and DEC000002, so the Command Registry, Blueprint, and Founder Approval tracker can cite a single governing document the same way they already cite those two records. **This record does not itself contain the additive schema migration design, the `commit_ingest` implementation, the approve-RPC precondition SQL, or the review-UI controls** — all of that remains unbuilt and is tracked in the gap map (§8 migration design, §10 file-by-file remediation map, §12 sequencing plan, §14 non-blocking technical debt). The gap map remains the authoritative technical/implementation reference for this decision; this record is the authoritative policy reference. Formalized as a standalone canonical record 2026-07-18, from content the Founder had already ruled on 2026-07-16 — no policy choice was reopened, changed, or reinterpreted in the course of formalizing it.

**Relationship to the gap map:** the gap map is retained in full, unedited in substance, as the supporting technical document for this decision — it contains the schema-gap-by-schema-gap analysis (§1-§8), the upstream Intake-model remediation map for allergen disclosures (§10), the sequencing plan (§12), and non-blocking technical debt (§14), none of which this record duplicates. Where this record and the gap map both describe the same ruling (the six §13 decisions, the DEC000001 §5.7 interpretation, the Evidence Disposition mechanism, the reopen invariant, and the existing-packet remediation paths), this record is the governing citation; the gap map is retained for full rationale, alternatives considered, and cross-reference continuity.

---

## 1. Scope

This decision establishes the **policy and semantics layer** for how `intake.packet.commit_ingest` (DEC000001's sole ordinary path from `approved` to `ingested`) must behave with respect to evidence completeness, precondition failure, and the disposition of evidence that cannot be classified. It does not, by itself, build or authorize building any of the following — each remains future work, gated on separate authorization, per the gap map §12:

- The additive `evidence.*` schema migration (gap map §8, working title `020_intake_evidence_schema_extension.sql`).
- The `commit_ingest` transaction itself.
- The new approve-RPC precondition (`operations.approve_intake_packet`, migration 017) that must be extended per §10 item 3 of the gap map.
- The Evidence Disposition mechanism's schema, API, or audit-event implementation (§4 below defines the policy; nothing has been built).
- The narrowly-scoped Intake OS review-UI controls authorized in principle by Decision 3 (§7 item 3 below; gap map §10 item 5).
- `intake.packet.reopen` (CMD000010) itself — explicitly out of scope; see §5.

## 2. DEC000001 §5.7 — interpreted, not amended

**Ruling (Founder, 2026-07-16):** DEC000001 §5.7's "durable write succeeds" criterion for the `approved → ingested` transition is **not amended**. This record resolves what had been an open interpretive question — whether §5.7 should be relaxed to a per-evidence-category success definition — by rejecting that relaxation and holding the strict reading:

> A packet may reach `ingested` only when every approved, ingestion-bound evidence element has been durably and faithfully persisted in its canonical Postgres destination. There is no category-level exception, no skip-and-log path to `ingested`, and no `partially_ingested` state.

This makes an incomplete allergen disclosure (missing `disclosure_status` and/or `scope`) a **precondition failure** that `commit_ingest` must detect and refuse to proceed past — not a design problem for `commit_ingest` to route around. See §3 for the transaction boundary this implies, and §4 for the Evidence Disposition mechanism that gives a disclosure a way to be resolved without being force-classified or silently dropped.

## 3. Transaction boundary and failure behavior

**`commit_ingest` is a single all-or-nothing transaction.** Per §2, either every approved, ingestion-bound evidence element (after excluding anything validly resolved by an Evidence Disposition, §4) is durably persisted and the packet transitions to `ingested`, or nothing is persisted and the packet remains `approved`. There is no partial-success outcome and no `partially_ingested` status.

**Precondition scope (Founder clarification, 2026-07-16):** the completeness precondition evaluates only evidence entries that actually exist in `packet_data` — it is not a completeness requirement over dishes or over any other entity.

- A dish with zero `allergen_disclosures[]` entries has no allergen-disclosure validation requirement at all — absence is never itself a blocking condition.
- A packet with zero allergen disclosures anywhere passes the precondition automatically.
- A present disclosure passes if it carries a valid `disclosure_status` and `scope` (per the existing `evidence.allergen_disclosures` CHECK constraints), or if it instead carries an approved Evidence Disposition (§4) that removes it from the ingestion-bound set.
- Only a present disclosure that is **neither** validly classified **nor** validly dispositioned blocks the transaction.

**Failure behavior:** the completeness precondition is checked **before any durable evidence write begins** — symmetrical with the `approved`/`archived`/`already-ingested` preconditions already specified for `commit_ingest`. On failure:

- `commit_ingest` fails the whole call with SQLSTATE `GP422` (Founder decision, 2026-07-16 — reuses the existing validation/content-failure category already established across migrations 017-019: `GP403` authorization, `GP404` not found, `GP409` state conflict, `GP422` validation/content failure; not a newly minted code).
- The packet remains at `packet_status = 'approved'` — unchanged, not rolled forward, not rolled back to something else. Because nothing was written, this is not a transactional-rollback scenario; it is a precondition check that runs before any write.
- Do not infer or default `disclosure_status` or `scope` under any circumstances (no defaulting `scope='dish'` from packet nesting, no defaulting `disclosure_status` from statement-text heuristics).
- Do not skip the affected rows and mark the packet `ingested` anyway. Do not introduce a `partially_ingested` or equivalent intermediate status.
- The error/result must identify, per affected packet: `evidence_type: "allergen_disclosure"`; `missing_fields` (which of `disclosure_status`/`scope`, or both, are absent, per record); affected dish or restaurant context (dish external ID + name, or restaurant-level if `dish_id` is absent); `blocked_count` (present, unclassified-and-undispositioned entries only — dishes without any disclosure entries are never counted, listed, or cited as a cause); and `corrective_action_required` (a human-readable pointer to disclosure classification, an Evidence Disposition, or — if `packet_data` itself must change — a governed reopen, per §5).

**Calorie evidence is optional, never inferred (Founder ruling, 2026-07-16):** calories are optional evidence, not a required property of every dish. "Required for faithful ingestion" for calorie data means *if a calorie object is present in the approved packet, it must be persisted faithfully* — it does not mean every dish must have one. A dish with no approved calorie object must ingest successfully with all calorie-related columns left null. Absence of calorie information must never block packet approval or `commit_ingest`, and `commit_ingest` must never infer, estimate, or fabricate a calorie value through this path. Restaurant-published calorie data persisted here must remain a distinct record from any future GoldPan-estimated calorie model.

## 4. Evidence Disposition mechanism

**Ruling (Founder, 2026-07-16):** rejected silently dropping unclassifiable disclosures via `edit_payload`, and rejected forcing every disclosure into one of the three `disclosure_status` CHECK values with no escape path. Editing evidence and determining the disposition of evidence are different governance actions and must remain distinct. The governing model:

- **Captured evidence is never silently removed.** A disclosure that enters an approved packet stays in `packet_data` and in the audit history regardless of what happens next.
- A reviewer (or, per §6's "b1" path, an authorized administrator) may determine that a captured disclosure is **not suitable for canonical evidence**. This determination is a governed act, not a data edit.
- Every disposition must be recorded with the acting `actor_id`/`actor_type`, the authority basis for the action, a timestamp, and a **required, non-blank reason**. No disposition may be entered without a reason.
- `commit_ingest` (§3) treats a validly-dispositioned disclosure the same way it treats a validly-classified one for precondition purposes — excluded from the ingestion-bound set because governance decided it shouldn't ingest, not because it was deleted from history.
- The original captured disclosure (`statement`, `source_text`, etc.) is preserved unchanged for historical and audit purposes, exactly as captured.
- **Extensibility (Founder refinement, 2026-07-16):** the mechanism is not defined around a single permanent disposition value. Today's implementation may only require one value (`excluded`), but the model must not assume that will always be the only valid disposition — the disposition value must be designed to accept future values without a structural rework.

**Integration with DEC000001:** Evidence Disposition is a new, narrow governance action scoped to captured evidence within a packet. It does not change `packet_status`, does not create a new Intake Packet lifecycle state, and does not touch DEC000001's state machine (§5.1-§5.9) directly. It is closest in kind to DEC000001 §5.8's append-only audit stores — a disposition record is itself an auditable event, not a packet mutation. This determination requires only this record (and its eventual implementation), not a DEC000001 amendment and not a new standalone Decision Record.

## 5. Approved-packet correction invariant (reopen relationship — not a reopen design)

**Governing invariant (Founder, 2026-07-16): an approved packet may not be edited silently or in place.** Any change to approved `packet_data` requires a formal reopen workflow with complete audit history. Evidence Disposition (§4), applied to an already-`approved` packet, does **not** require reopening, because it never changes `packet_data` — it only adds a disposition record. Any remediation that requires changing `packet_data` itself on an already-`approved` packet must instead use the governed `intake.packet.reopen` command.

**What this record does not do:** per explicit instruction, `intake.packet.reopen` is **not defined by this record.** DEC000001 line 38 already flags `intake.packet.reopen` (CMD000010) as "reserved and undefined," and DEC000001 §5.9 states that reversing an approved packet "must be proposed as its own, separately governed, elevated action." This ruling confirms `intake.packet.reopen` as the intended vehicle for `packet_data` corrections on approved packets, and records the minimum shape that command must eventually satisfy (preserves the original approval and its full audit history; requires a non-blank reason, an authorized actor, and its own distinct `intake_packet_events` event type; returns the packet to an editable/reviewable state that must pass through ordinary review and approval again — not a shortcut back to `approved`). It is anticipated future work, not something this decision resolves. Nothing here should be read as `reopen`'s governing specification, and DEC000001 is not reopened, amended, or reinterpreted by this statement.

## 6. Existing-packet remediation — two distinct paths

Applies to already-`approved` packets found to contain an allergen disclosure that is present, unclassified, and undispositioned (gap map §11). No live-database query has been run to scope the actual volume of affected packets — that query is separate future work (gap map §12 step 4), not resolved by this record.

**Path b1 — Evidence Disposition backfill (approved for immediate use).** An authorized administrator may resolve an unclassifiable disclosure on an already-`approved` packet by recording an Evidence Disposition (§4) — without mutating `packet_data` and without changing `packet_status`. Available once §4 is built; does not require the reopen workflow because nothing about the packet's content changes.

**Path b2 — direct administrative edit to `packet_data` (not approved).** Editing an already-approved packet's `packet_data` directly, without reopening it, is **not approved.** Any remediation that genuinely requires changing the packet's content must go through the governed `intake.packet.reopen` workflow (§5): non-blank reason, authorized actor, distinct audit event, and a full pass back through ordinary review and approval before the packet can reach `approved` again.

**Why both paths exist:** this ruling explicitly rejects an architecture that implies an approval can never be corrected — real approvals may later need to be reversed because of error, newly discovered evidence, or an incomplete review, and that possibility is preserved via `reopen`, not foreclosed. The two remediation shapes stay structurally distinct: a disposition never touches packet content; a reopen always does, and always re-enters full review.

## 7. Founder decisions — approved 2026-07-16, presented and ruled in this priority order

1. **Unclassifiable disclosures.** Rejected silent drop and forced classification. Ruling: the Evidence Disposition mechanism (§4) — captured evidence is never silently removed; a reviewer may record an extensible, audited disposition (actor, authority basis, timestamp, required non-blank reason) that excludes a disclosure from the ingestion-bound set without deleting it.
2. **Existing-packet remediation approach.** Superseded the original return-for-correction / administrative-backfill / hybrid framing. Ruling: an approved packet may not be edited silently or in place (§5); split into path b1 (Evidence Disposition backfill, no reopen required) and path b2 (any `packet_data` change requires the governed `reopen` workflow) — see §6.
3. **UI-authorization timing.** Ruling: authorize only the minimum Intake OS review-UI controls required to support the new approval semantics — disclosure classification and the Evidence Disposition control — now, ahead of the broader Intake lifecycle UI redesign's formal start. All other lifecycle UI work (six-state workflow presentation, queue behavior, action visibility, `canApprove` gate cleanup) remains separate, later scope. Nothing has been built under this authorization yet.
4. **Migration 020 sequencing.** Ruling: the additive schema migration (gap map §8, working title `020_intake_evidence_schema_extension.sql`) may be written, reviewed, and executed independently of the allergen-disclosure remediation work — it is decoupled and carries no dependency. Executing it does not by itself satisfy this decision's precondition requirements for `commit_ingest`, which remain gated on §3-§4 being built. Not yet written.
5. **SQLSTATE code.** Ruling: the completeness precondition (§3) reuses `GP422` (validation/content failure), consistent with the existing four-code taxonomy (`GP403`/`GP404`/`GP409`/`GP422`) established across migrations 017-019, rather than minting a new code.
6. **Discretionary defensive columns.** Ruling: a defensive fidelity copy of the exact approved calorie-evidence fragment (`calorie_raw_fragment`, nullable `jsonb`) is approved as part of the migration-020 design, mirroring the same defensive-fragment pattern proposed for dish modifiers. All calorie-related columns must remain nullable; absence of calorie evidence must never block approval or ingestion; `commit_ingest` must never infer, estimate, or fabricate a calorie value (see §3).

## 8. Risks, guardrails, validation criteria, revisit triggers

**Risks:**
- This record resolves policy and semantics only. Until the migration-020 schema, the approve-RPC precondition, the Evidence Disposition schema/API, and `commit_ingest` itself are built, the strict §2/§3 reading has no enforcement mechanism — an `edit_payload` or a manual DB write could still produce an `approved` packet with an unresolved disclosure today. This record does not itself close that gap; it specifies what the eventual enforcement must do.
- The Evidence Disposition mechanism (§4) depends on the same `actor_id`/stable-user-identity dependency already flagged as open in DEC000001 §7 item 9 / DEC000002 §7 item 8 — resolved for the schema (`operations.users`), but the API-authentication mechanism for identifying the acting user on admin-key-authenticated requests remains a separate, already-flagged open item (`DEC000001_IMPLEMENTATION_GAP_MAP.md` §0).
- `intake.packet.reopen` remaining undefined (§5) means path b2 (§6) is not currently executable — any already-`approved` packet whose remediation requires a `packet_data` change is blocked until `reopen` is separately designed and built.

**Guardrails:**
- No implementation of §3's precondition, §4's Evidence Disposition mechanism, or migration 020 may proceed without separate authorization to write SQL/code, per standing instruction (gap map §12).
- `commit_ingest` must never mark a packet `ingested` while any present, unclassified, undispositioned allergen disclosure exists in `packet_data` (§2, §3).
- No command or endpoint may default or infer `disclosure_status` or `scope` under any circumstances (§3).
- No mechanism may treat Evidence Disposition as equivalent to editing `packet_data`, and no mechanism may treat a `packet_data` edit on an approved packet as achievable without the (future) `reopen` command (§5, §6).
- Every Evidence Disposition record must carry a non-blank reason; a disposition without one must be rejected once the mechanism is built (§4).

**Validation criteria (for the eventual implementation, not yet built):**
- No packet reaches `ingested` with a present, unclassified, undispositioned allergen disclosure remaining in `packet_data`.
- Every `commit_ingest` precondition failure returns `GP422` with the full structured payload specified in §3, and leaves `packet_status` unchanged.
- Every dish with zero `allergen_disclosures[]` entries never appears in a precondition failure's `blocked_count` or context list.
- Every dish with no approved calorie object ingests successfully with all calorie-related columns null.
- No disposition record exists with a blank or null reason.

**Revisit triggers:**
- If a second disposition value beyond `excluded` is ever needed, that is expected and accommodated by §4's extensibility requirement — not a reason to reopen this record.
- If `intake.packet.reopen`'s eventual design conflicts with any assumption in §5 or §6, that is `reopen`'s own separate governance work to resolve, per DEC000001 §5.9 — not automatically a reopening of this record, unless the conflict is with §5's stated minimum shape itself.
- If the live-database scoping query (gap map §12 step 4) finds a material volume of already-approved packets needing path b2, that may accelerate the priority of designing `reopen`, but does not by itself change any ruling in this record.

---

## Changelog

- **2026-07-16** — Founder review session resolves all six blocking decisions (§7 above) and the DEC000001 §5.7 interpretation (§2), recorded contemporaneously in the gap map (`DEC000003_INTAKE_EVIDENCE_SCHEMA_GAP_MAP.md`).
- **2026-07-18** — This canonical Decision Record extracted and formalized from the gap map's §9, §9a, §9b, §10 item 8, §11, and §13, matching the DEC000001/DEC000002 canonical-record structure. No policy choice changed in the extraction. Propagated into `docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md`, `docs/GOLDPAN_MASTER_OS_BLUEPRINT.md`, and `docs/decisions/PHASE5_FOUNDER_APPROVAL_REQUIRED.md`. The gap map's own status banner updated to point here as the governing citation while remaining the technical/implementation reference. No SQL, migration, or application code was written or executed as part of this formalization.
