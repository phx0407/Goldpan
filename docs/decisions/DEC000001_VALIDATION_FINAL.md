# DEC000001 Approval Propagation — Corrected Final Validation Report

**Supersedes:** `DEC000001_PHASE3_VALIDATION.md` and `DEC000001_PHASE4_VALIDATION.md`. Both are retained on disk for audit trail but the corrections below (all in the Phase 3 document's prose — no registry data was wrong) mean this file is the authoritative validation record.

**Scope:** the full documentation propagation of DEC000001 across `docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md`, `docs/decisions/DEC000001_CANONICAL_INTAKE_PACKET_STATE_MACHINE.md`, `docs/decisions/PHASE5_FOUNDER_APPROVAL_REQUIRED.md`, and `docs/GOLDPAN_MASTER_OS_BLUEPRINT.md`, as captured in `docs/decisions/DEC000001_APPROVAL_PROPAGATION.diff`. **DEC000001 itself was not reopened at any point in this correction pass.**

---

## Four explicit confirmations requested

**1. Final command types.**

- **CMD000008** (`intake.packet.commit_ingest`) — final type is **`automated_job`**. Reason: DEC000001 §5.7 defines this command's *role* (the sole ordinary path to `ingested`) but does not redefine its *type*. Once invoked, it performs a durable write and an atomic status transition without continuous human interaction after invocation — this matches §6's `automated_job` definition, not `workflow_trigger` (which requires a human-invoked multi-step operational process) and not `mutation` (which the Phase 2 round had incorrectly introduced with no Founder basis). `automated_job` is confirmed as the v0.1 original value, restored.
- **CMD000028** (`governance.pipeline.run`) — final type is **`automated_job`**, unchanged from v0.1. It was not separately approved to become anything else. DEC000001 governs the Intake namespace only and has no authority over Governance-namespace command types; the `workflow_trigger` value that appeared in the Phase 2 round was incidental drift, not a decision, and has been reverted.

**2. CMD000024-CMD000030 corrected.** The Phase 3 validation document's prose incorrectly grouped CMD000024-030 together as "DEC000002-derived." The registry table itself (`GOLDPAN_COMMAND_REGISTRY_PHASE5.md` §17) was never wrong — a fresh grep confirms no occurrence of "CMD000024-030" or "024-030" anywhere in the registry file. The error was confined to three sentences in the Phase 3 validation report, corrected below:

- **Actual DEC000002-dependent provisional commands:** CMD000024, CMD000025, CMD000026, and CMD000035-CMD000042. All eleven carry `draft` status and an explicit "Pending DEC000002 approval" Notes qualifier in the registry table.
- **CMD000027-CMD000030** (`governance.result.view`, `governance.pipeline.run`, `knowledge.evidence.view`, `audit.log.view`) are Governance, Knowledge, and Audit namespace commands with no relationship to DEC000002 (which concerns only the Submission/`submission.*` namespace). Their registry Notes read "Unchanged" — they remain `draft` carried forward from the v0.1 baseline, for reasons unrelated to and independent of DEC000002's approval status. They are not blocked on DEC000002 and were never represented as such in the registry table itself.

Corrected passages:

- *Decision-authority audit:* "Only DEC000001 content is reflected as `approved` anywhere in the three files. Every DEC000002-derived row/entry (CMD000024-026, CMD000035-042, the CMD000025 note) is marked `draft` with an explicit 'Pending DEC000002 approval' qualifier. CMD000027-030 are also `draft`, but as pre-existing Governance/Knowledge/Audit-namespace entries unrelated to DEC000002 — their draft status has no dependency on DEC000002's approval. CMD000025 is not marked `superseded` — DEC000001 §7 item 6 and the mirrored PHASE5_FOUNDER item 9 are split into an approved architectural rule versus a deferred implementation dependency, and Founder decisions 1-5 (DEC000001 §7) are unchanged from the previously approved v4.1 text."
- *Remaining unresolved issues:* "DEC000002 remains unapproved. Nothing under it — CMD000024-026, CMD000035-042, and `submission.*` commands generally — may move past `draft` until the Founder approves it separately. (CMD000027-030 are separately `draft` for unrelated Governance/Knowledge/Audit reasons and are not gated on DEC000002.)"
- *No-unapproved-decision-propagated confirmation:* "DEC000002 is not approved, and no DEC000002 content has been written into any document as if it were approved. Every DEC000002-derived entry (CMD000024-026, CMD000035-042) across all four files carries `draft` status and an explicit 'pending DEC000002 approval' qualifier. CMD000027-030's `draft` status is not attributed to DEC000002 anywhere in the registry or this report. Only DEC000001's six already-Founder-approved items (§7 items 1-5 unchanged, item 6 split into an approved rule plus a still-open dependency) are reflected as approved."

**3. Blueprint-lag statement — confirmed removed.** The Command Registry's §22 "RESOLVED — Canonical Intake Packet State Machine" paragraph no longer claims the Blueprint update is pending. Final replacement sentence, verified on disk at line 575:

> "The Blueprint §5b and §5i Intake Packet sections were updated in the same documentation propagation pass to reference and reflect DEC000001. DEC000001 remains the governing authority if later wording drift occurs."

A full-file grep for `Blueprint.{0,80}(pending|lag|still contain|not yet updated|requires? a documentation update)` returns only this line and one unrelated Review-Flags line (line 581) — no residual stale-pending language exists anywhere in the file.

**4. Blueprint §5b non-linear fix — confirmed.** Line 680 no longer presents the six Intake Packet states as one linear arrow chain. Exact final row, verified on disk:

> `| Intake Packet | pending_review → in_review; in_review → returned \| approved \| rejected; returned → pending_review; approved → ingested *(canonical model per DEC000001, approved 2026-07-13 — not a single linear sequence; see the branching transitions above and §5i below for full detail — `superseded_by_packet_id` and `archived_at` are non-status attributes, not lifecycle states; see `docs/decisions/DEC000001_CANONICAL_INTAKE_PACKET_STATE_MACHINE.md`)* |`

This uses the branching notation (`;` separates transition groups, `|` separates alternative destinations from a single source), matching the actual DEC000001 state machine: `pending_review → in_review`, `in_review → returned | approved | rejected`, `returned → pending_review`, `approved → ingested`. It is not a false single-path sequence. §5i's detailed per-entity table (lines ~1345-1366) is unchanged, as instructed.

---

## Full corrected checklist

**Controlled-vocabulary audit — PASS.** Every `registry_status` value is one of the six approved enum values; every `implementation_status` value is one of the approved set. No compound tokens remain in any status field.

**Table-shape audit — PASS.** §17 is a uniform 7-column table across all 42 rows. CMD000037 is split into three Registry IDs (037/038/039 = `.return`/`.approve`/`.reject`); CMD038-040 renumbered to CMD040-042 with no ID reused or skipped.

**Decision-authority audit — PASS (corrected).** See item 2 above for the corrected CMD000024-030 grouping. Only DEC000001 content is reflected as `approved`; DEC000002-derived rows are exactly CMD000024-026 and CMD000035-042, each `draft` with an explicit qualifier.

**Evidence audit — PASS.** CMD000025's Notes cite CMD000035-CMD000039 as the proposed replacement set. CMD000008 and CMD000028 Type values are now both explicitly justified against §6's enum (see confirmation 1 above), closing the gap where the Phase 3 audit checked CMD008-011 generically without stating CMD000008's and CMD000028's final types explicitly.

**Cross-reference audit — PASS.** DEC000001 §7 item 6's citation corrected to "§5.3, §5.8" only. Blueprint §5b/§5i edits checked line-by-line against the file on disk.

**Namespace-governance-vs-approval audit — PASS.** DEC000001 governs the Intake Packet lifecycle, permissions, evidence boundaries, and transition semantics; it does not by itself approve every command in the `intake.*` namespace. §17's Approval-authority note splits every `approved` row into its actual basis (Registry-framework-original vs. DEC000001 §7-decision), and no row is marked `approved` solely because its namespace is `intake.*`.

## Remaining unresolved issues (corrected)

- DEC000001 §7 item 6 / PHASE5_FOUNDER item 9's deferred dependency — the canonical user/auth table `*_user_id` resolves to — is still unconfirmed. Blocks implementation only, not documentation.
- DEC000002 remains unapproved. Nothing under it — CMD000024-026, CMD000035-042, `submission.*` commands generally — may move past `draft` until the Founder approves it separately. CMD000027-030 are separately `draft` for unrelated reasons and are not gated on DEC000002.
- No other Blueprint section has been swept for stale pre-DEC000001 state language outside the two edited locations (confirmed by grep to be the only two `DEC000001`/`DEC000002` mentions in the file).
- CMD000005/CMD000006's known drift (live approve/return gating doesn't yet enforce claim-first per DEC000001 §5.9) is documented in §18 notes but not fixed — remediation scoped to CMD000031/CMD000032 implementation, not this documentation round.

## Documentation-only confirmation

No database migration, API endpoint, or UI code was written, changed, or touched in this or any prior round of this correction pass. `git status` confirms only the Command Registry, DEC000001 (renamed, Phase 2 only, untouched since), the Founder approval tracker, and the Blueprint (two locations only) were modified. No `git commit` has been made.

## No-unapproved-decision-propagated confirmation (corrected)

See item 2 above. DEC000002 is not approved and no DEC000002 content is written into any document as approved. Every DEC000002-derived entry (CMD000024-026, CMD000035-042) carries `draft` with an explicit qualifier; CMD000027-030's `draft` status is never attributed to DEC000002.

---

**Status: all checks pass with corrections applied. DEC000001 was not reopened. No `git commit` has been made. Awaiting Founder confirmation before staging/committing.**
