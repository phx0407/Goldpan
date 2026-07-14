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

## From DEC000002 (Restaurant Update Submission) — revised in v4, ready for approval

v4 is a final targeted-refinement pass over v3 (display-name snapshots removed, `exception_escalation` given a single owner, `disposition_status` semantics sharpened to distinguish routing completion from downstream-work completion, routing commands defined as discrete handoffs, `submission.close_no_action` removed as a redundant standalone command, downstream linkage resolved to explicit nullable foreign keys, resubmission-chain validation corrected, archival and audit coverage fully specified, idempotency strengthened to a defined failure-safe sequence). The nine Founder decisions below (DEC000002 §7) are the complete, final list.

10. **Approve the five review statuses:** `pending_review`, `in_review`, `returned`, `approved`, `rejected`.
11. **Approve the separate disposition model and its five statuses** (`unassessed`, `pending`, `in_progress`, `completed`, `failed`), with routing completion distinguished from downstream-work completion (DEC000002 §5.3).
12. **Approve the four disposition types and their one-owner routing boundaries** — in particular, that `exception_escalation` is owned solely by Governance OS (not jointly with Knowledge OS), and that identity/contact changes route to the Blueprint's existing Identity Review Queue rather than being edited directly by the submission reviewer (DEC000002 §5.2).
13. **Approve immutable parent submissions with linked child resubmissions** (DEC000002 §5.7-§5.8).
14. **Approve splitting the broad review command into `claim`/`release`/`return`/`approve`/`reject`, and removing `submission.close_no_action` as a standalone command** (DEC000002 §5.5).
15. **Approve archival as a separate attribute set**, with the eligibility rules in DEC000002 §5.9.
16. **Choose the downstream-link storage model:** explicit nullable foreign-key fields (recommended, DEC000002 §5.11) or a typed generic downstream-link table.
17. **Confirm the exact source of stable user identity** for `claimed_by_user_id`/`archived_by_user_id` — same open question as DEC000001 decision 9, shared across both records.
18. **Confirm that `operations.partner_submissions` remains outside the scope of this decision** — no changes proposed to it.

## Sequencing note (not a decision, just scope framing)

Both records are now at v4 and, per their own revision notes, ready for Founder approval — all mechanical corrections are resolved in both, leaving only the true policy choices in decisions #4-9 (DEC000001) and #10-18 (DEC000002) above. Decision #9/#17 (stable user-identity source) is shared across both records and has the widest downstream blast radius, since every claim/archival actor field in both decisions depends on it. DEC000002's remaining risk is concentrated in #12 (exception-escalation routes to a Governance OS workflow not yet designed) and #16 (downstream-link storage model choice), since v4 resolved the disposition/routing model, ownership boundary, resubmission chain, archival eligibility, and idempotency sequence mechanically. DEC000002 still has zero live API/UI to break — per its migration-risk statement, this is "low live-application risk based on the inspected API and UI, subject to verifying existing rows, scripts, RLS policies, reports, and any manual consumers" not visible in this codebase inspection — not "zero risk" as v1 overstated. If the Founder wants to approve one record ahead of the other, DEC000002 is still the lower-risk one to greenlight first since no code depends on it yet.

---

No further action will be taken — no migration written, no endpoint changed, no UI touched, no registry status flipped to `approved` — until the choices above are resolved.
