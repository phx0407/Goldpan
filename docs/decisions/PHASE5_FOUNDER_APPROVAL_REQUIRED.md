# Phase 5 — Founder Approval Required

**Covers:** `REGISTRY_FRAMEWORK_APPROVAL_MEMO.md`, `DEC000001_intake_packet_state_machine.md`, `DEC000002_submission_state_machine.md`
**Purpose:** List the exact choices that need a Founder decision before any implementation work begins. Nothing below has been implemented — no DB, API, UI, Blueprint, or registry file has been modified as part of this round.

---

## From the Framework Approval Memo

1. **Decision Registry ID scheme.** Approve `DEC000001`-style sequential IDs, stored one-file-per-record at `docs/decisions/`, as the permanent rule (mirrors §7.1's `CMD`-ID rule). This is already in effect by virtue of this round's two files existing at that path with those IDs — approval formalizes what's already been done rather than requiring new action.
2. **Decision-basis categories.** No action needed yet — provisional approval converts to full approval automatically once DEC000001/DEC000002 are themselves approved, per the memo's own terms.
3. **Namespace ownership-transfer footnote.** Optional, non-blocking — approve or skip; can ride along with the next registry edit either way.

## From DEC000001 (Intake Packet) — revised in v2

4. **Confirm Model A (correct-and-resubmit the same packet row) over Model B (new row per revision via `revision_of_packet_id`).** Model A requires no change to `UNIQUE(restaurant_external_id, canvass_date)`; Model B would require a revision-aware constraint redesign. Recommendation: Model A.
5. **Confirm `superseded_by_packet_id` (a relationship column) over a `superseded` packet_status value.** Recommendation: relationship column — a packet's own processing status shouldn't change just because a later canvass supersedes its evidence downstream.
6. **Confirm excluding `draft` from the Phase 5 lifecycle.** No current operator workflow authors packets incrementally inside Master OS; recommendation is to exclude it now and add it later only if a real packet-authoring capability is built.
7. **Confirm the minimal, non-locking `in_review` claim mechanism** (`claimed_by`/`claimed_at` columns, check-then-set guard, manual stale-claim recovery, no reassignment workflow) is right-sized for Phase 5's small admin-only review team, versus building fuller concurrency control now.
8. **Confirm `archived_at` (a retention attribute) over an `archived` packet_status value.** `ingested` remains the terminal processing status; `archived_at` only affects queue visibility.
9. **Decide on `rejected` / `intake.packet.reject`.** Not adopted by default — the only evidence for it is the registry's own placeholder entry (CMD000009), which this record treats as insufficient on its own. Say so explicitly if a hard-terminal reject state is wanted.
10. **Resolve the `approved → returned` question** (carried over from v1, still open). Live code allows it; no Blueprint source supports it. Confirm bug-to-close vs. intentional feature.
11. **Confirm `intake.packet.reopen` (existing registry placeholder, CMD000010) is the correct name/semantics for the resubmission command**, or specify different intended behavior.

## From DEC000002 (Restaurant Update Submission) — revised in v2

12. **Confirm Model B (separate `review_status` + `conversion_status`/`conversion_type` dimensions) over Model A (single linear status through `converted`/`archived`).** Recommendation: Model B — the live schema's own column comment already treats "approved" and "downstream action taken" as separate moments; Model A would re-merge them.
13. **Confirm no changes are made to `operations.partner_submissions`.** Its `converted` status and simpler single-target conversion (CRM/partner record) are treated as a genuinely different downstream shape from this entity's two-path conversion (Intake session or direct evidence edit), not an inconsistency to fix.
14. **Confirm dropping `received` as a status**, relying on the existing `created_at` column as the receipt marker — no new column needed.
15. **Confirm archival as attributes (`archived_at`/`archived_by`/`archive_reason`)** rather than a `review_status` value, so a submission's final approved/rejected outcome survives archival.
16. **Confirm the linked-child-submission model for corrections** (`resubmission_of_submission_id`) rather than in-place editing or a same-row revision log — this respects the schema's existing "append-only for the submission row" comment.
17. **Decide whether to split the single registered `submission.restaurant_update.review` command** into discrete `claim`/`return`/`approve`/`reject` commands now, or keep it as one command and revisit later. Optional, not required by the state-machine decision itself.
18. **Confirm `conversion_type` values** (`intake_packet`, `identity_update`, `no_action`, `other`) correctly represent the two documented post-approval outcomes ("triggers an Intake session" / "directly edits evidence records"), or specify different values.
19. **Confirm whether `resulting_intake_session` should be retyped as a proper FK** to `operations.intake_packets`, or left as free text for now.

## Sequencing note (not a decision, just scope framing)

DEC000001's risk is concentrated in decisions #7 (claim mechanism scope), #9 (reject), and #10 (`approved → returned`), since #4/#5/#6/#8 no longer require any constraint or schema risk beyond simple additive columns. DEC000002 has zero live API/UI to break — per its revised migration-risk statement, this is "low live-application risk based on the inspected API and UI, subject to verifying existing rows, scripts, RLS policies, reports, and any manual consumers" not visible in this codebase inspection — not "zero risk" as v1 overstated. If the Founder wants to approve one record ahead of the other, DEC000002 is still the lower-risk one to greenlight first since no code depends on it yet.

---

No further action will be taken — no migration written, no endpoint changed, no UI touched, no registry status flipped to `approved` — until the choices above are resolved.
