# Phase 5 — Founder Approval Required

**Covers:** `REGISTRY_FRAMEWORK_APPROVAL_MEMO.md`, `DEC000001_intake_packet_state_machine.md`, `DEC000002_submission_state_machine.md`
**Purpose:** List the exact choices that need a Founder decision before any implementation work begins. Nothing below has been implemented — no DB, API, UI, Blueprint, or registry file has been modified as part of this round.

---

## From the Framework Approval Memo

1. **Decision Registry ID scheme.** Approve `DEC000001`-style sequential IDs, stored one-file-per-record at `docs/decisions/`, as the permanent rule (mirrors §7.1's `CMD`-ID rule). This is already in effect by virtue of this round's two files existing at that path with those IDs — approval formalizes what's already been done rather than requiring new action.
2. **Decision-basis categories.** No action needed yet — provisional approval converts to full approval automatically once DEC000001/DEC000002 are themselves approved, per the memo's own terms.
3. **Namespace ownership-transfer footnote.** Optional, non-blocking — approve or skip; can ride along with the next registry edit either way.

## From DEC000001 (Intake Packet) — revised in v3

v3 resolved most of v2's open questions mechanically (atomic claim implementation, stable user-id reference, two-store revision/event model, deterministic supersession, system-controlled ingestion) rather than leaving them as Founder choices. What remains genuinely open:

4. **Adopt `rejected` as a sixth `packet_status`**, terminal, mandatory-reason, confirmation-gated (§5.10 of DEC000001) — yes/no. No longer justified merely because the registry placeholder (CMD000009) exists; justified on its own operational grounds (terminally-invalid vs. correctable) — confirm this reasoning is acceptable.
5. **Confirm the two new commands `intake.packet.update` (payload correction while `returned`) and `intake.packet.resubmit` (`returned → pending_review`)**, and confirm `intake.packet.reopen` (CMD000010) is left undefined/reserved for a future exceptional action rather than repurposed as the resubmission mechanism (correcting v2's assumption).
6. **Confirm `intake.packet.mark_ingested` is deprecated as an independent operator action**, folded into `intake.packet.commit_ingest`, and retained (if at all) only as a restricted, reason-required admin reconciliation tool.
7. **Confirm the tightened precondition: `intake.review.return`, `.approve`, and `.reject` (if adopted) all require the packet to be `in_review` (claimed) first.** This fully closes `approved → returned` (and also removes `pending_review` as a direct source for `.return`) rather than treating it as a special case.
8. **Confirm the exact source of stable user identity** for `claimed_by_user_id` once the current authentication/user model is identified — this decision assumes one exists but doesn't have visibility into its exact shape.
9. **Confirm no automatic archival schedule is being approved now** — archival policy (manual, scheduled, or both) is deliberately left open for a later operational decision.

## From DEC000002 (Restaurant Update Submission) — revised in v2

10. **Confirm Model B (separate `review_status` + `conversion_status`/`conversion_type` dimensions) over Model A (single linear status through `converted`/`archived`).** Recommendation: Model B — the live schema's own column comment already treats "approved" and "downstream action taken" as separate moments; Model A would re-merge them.
11. **Confirm no changes are made to `operations.partner_submissions`.** Its `converted` status and simpler single-target conversion (CRM/partner record) are treated as a genuinely different downstream shape from this entity's two-path conversion (Intake session or direct evidence edit), not an inconsistency to fix.
12. **Confirm dropping `received` as a status**, relying on the existing `created_at` column as the receipt marker — no new column needed.
13. **Confirm archival as attributes (`archived_at`/`archived_by`/`archive_reason`)** rather than a `review_status` value, so a submission's final approved/rejected outcome survives archival.
14. **Confirm the linked-child-submission model for corrections** (`resubmission_of_submission_id`) rather than in-place editing or a same-row revision log — this respects the schema's existing "append-only for the submission row" comment.
15. **Decide whether to split the single registered `submission.restaurant_update.review` command** into discrete `claim`/`return`/`approve`/`reject` commands now, or keep it as one command and revisit later. Optional, not required by the state-machine decision itself.
16. **Confirm `conversion_type` values** (`intake_packet`, `identity_update`, `no_action`, `other`) correctly represent the two documented post-approval outcomes ("triggers an Intake session" / "directly edits evidence records"), or specify different values.
17. **Confirm whether `resulting_intake_session` should be retyped as a proper FK** to `operations.intake_packets`, or left as free text for now.

## Sequencing note (not a decision, just scope framing)

DEC000001's risk is now concentrated in decisions #4 (reject), #6 (deprecating `mark_ingested`), and #8 (user-identity source), since v3 resolved the claim mechanism, supersession, and history-store questions mechanically rather than leaving them open. DEC000002 has zero live API/UI to break — per its revised migration-risk statement, this is "low live-application risk based on the inspected API and UI, subject to verifying existing rows, scripts, RLS policies, reports, and any manual consumers" not visible in this codebase inspection — not "zero risk" as v1 overstated. If the Founder wants to approve one record ahead of the other, DEC000002 is still the lower-risk one to greenlight first since no code depends on it yet.

---

No further action will be taken — no migration written, no endpoint changed, no UI touched, no registry status flipped to `approved` — until the choices above are resolved.
