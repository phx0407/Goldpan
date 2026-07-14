# Phase 5 — Founder Approval Required

**Covers:** `REGISTRY_FRAMEWORK_APPROVAL_MEMO.md`, `DEC000001_intake_packet_state_machine.md`, `DEC000002_submission_state_machine.md`
**Purpose:** List the exact choices that need a Founder decision before any implementation work begins. Nothing below has been implemented — no DB, API, UI, Blueprint, or registry file has been modified as part of this round.

---

## From the Framework Approval Memo

1. **Decision Registry ID scheme.** Approve `DEC000001`-style sequential IDs, stored one-file-per-record at `docs/decisions/`, as the permanent rule (mirrors §7.1's `CMD`-ID rule). This is already in effect by virtue of this round's two files existing at that path with those IDs — approval formalizes what's already been done rather than requiring new action.
2. **Decision-basis categories.** No action needed yet — provisional approval converts to full approval automatically once DEC000001/DEC000002 are themselves approved, per the memo's own terms.
3. **Namespace ownership-transfer footnote.** Optional, non-blocking — approve or skip; can ride along with the next registry edit either way.

## From DEC000001 (Intake Packet) — revised in v4, ready for approval

v4 is a final targeted-refinement pass over v3 (display-name snapshots removed from all actor fields, `intake.packet.update` renamed to `intake.packet.edit_payload`, an explicit reviewer/submitter role boundary added, supersession confirmed as system-derived with no routine command, `rejected` given a sharpened definition). The six Founder decisions below (DEC000001 §7) are the complete, final list — nothing further is deferred to a future revision of this record.

4. **Approve the six canonical statuses:** `pending_review`, `in_review`, `returned`, `approved`, `rejected`, `ingested`.
5. **Approve the discrete command model:** `intake.packet.edit_payload`, `intake.packet.resubmit`, `intake.review.claim`, `intake.review.release`, the existing `intake.review.approve`/`intake.review.return` (tightened to require `in_review`), `intake.packet.reject`, and `intake.packet.commit_ingest` as the sole ordinary path to `ingested`.
6. **Approve reserving `intake.packet.reopen` (CMD000010) for a future exceptional, restricted workflow** — undefined and unbuilt by this decision.
7. **Approve `superseded_by_packet_id` and `archived_at` as non-status attributes/relationships**, not statuses — and confirm no routine `intake.packet.supersede` command is added (supersession stays system-derived, per DEC000001 §5.6).
8. **Approve the role boundary that Governance Reviewers do not edit Intake evidence** — only an Intake Specialist may call `intake.packet.edit_payload` (DEC000001 §4, §5.2).
9. **Confirm the exact source of stable user identity** for `*_user_id` fields once the current authentication/user schema is identified — this decision assumes one exists but doesn't have visibility into its exact shape. Shared with DEC000002 decision 13.

## From DEC000002 (Restaurant Update Submission) — revised in v3

v3 resolved most of v2's open questions mechanically (disposition naming and OS routing, claim mechanism mirroring DEC000001 v3, corrected parent-stays-returned resubmission chain, tightened archival eligibility, command split) rather than leaving them as Founder choices. What remains genuinely open:

10. **Confirm the disposition routing table (DEC000002 §5.2)** — in particular, that identity/contact changes route to the Blueprint's existing Identity Review Queue rather than being edited directly by the submission reviewer, closing the path the live schema comment currently implies is normal.
11. **Confirm `exception_escalation` routes to a Governance/Knowledge OS correction workflow that does not yet exist.** This decision creates the exit point (`submission.escalate_exception`) but does not design that workflow; a future decision must.
12. **Resolve the `resulting_intake_session` entity question (DEC000002 §5.9):** does downstream linkage need `resulting_intake_packet_id`, `resulting_intake_session_id`, or both? Requires input from whoever owns AI Usage OS cost/quality tracking, not just this decision's scope.
13. **Confirm the exact source of stable user identity** for `claimed_by_user_id`/`archived_by_user_id` — same open question as DEC000001 decision 8, shared across both records.
14. **Confirm no changes are made to `operations.partner_submissions`.** Its `converted` status and simpler single-target conversion (CRM/partner record) are treated as a genuinely different downstream shape from this entity's disposition-routed resolution, not an inconsistency to fix.

## Sequencing note (not a decision, just scope framing)

DEC000001 is now at v4 and, per its own revision note, ready for Founder approval — all mechanical corrections are resolved, leaving only the six true policy choices in decisions #4-9 above, with #9 (user-identity source) the one with the widest downstream blast radius since it also gates DEC000002. DEC000002's risk is concentrated in decisions #10 (closing the direct-evidence-edit path), #11 (exception-escalation workflow not yet designed), and #12 (resulting_intake_session entity question), since v3 resolved the disposition/routing model, claim mechanism, resubmission chain, and archival eligibility mechanically. DEC000002 still has zero live API/UI to break — per its migration-risk statement, this is "low live-application risk based on the inspected API and UI, subject to verifying existing rows, scripts, RLS policies, reports, and any manual consumers" not visible in this codebase inspection — not "zero risk" as v1 overstated. If the Founder wants to approve one record ahead of the other, DEC000002 is still the lower-risk one to greenlight first since no code depends on it yet.

---

No further action will be taken — no migration written, no endpoint changed, no UI touched, no registry status flipped to `approved` — until the choices above are resolved.
