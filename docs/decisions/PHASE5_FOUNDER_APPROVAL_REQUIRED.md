# Phase 5 — Founder Approval Required

**Covers:** `REGISTRY_FRAMEWORK_APPROVAL_MEMO.md`, `DEC000001_intake_packet_state_machine.md`, `DEC000002_submission_state_machine.md`
**Purpose:** List the exact choices that need a Founder decision before any implementation work begins. Nothing below has been implemented — no DB, API, UI, Blueprint, or registry file has been modified as part of this round.

---

## From the Framework Approval Memo

1. **Decision Registry ID scheme.** Approve `DEC000001`-style sequential IDs, stored one-file-per-record at `docs/decisions/`, as the permanent rule (mirrors §7.1's `CMD`-ID rule). This is already in effect by virtue of this round's two files existing at that path with those IDs — approval formalizes what's already been done rather than requiring new action.
2. **Decision-basis categories.** No action needed yet — provisional approval converts to full approval automatically once DEC000001/DEC000002 are themselves approved, per the memo's own terms.
3. **Namespace ownership-transfer footnote.** Optional, non-blocking — approve or skip; can ride along with the next registry edit either way.

## From DEC000001 (Intake Packet)

4. **Adopt the recommended canonical lifecycle:** `draft → pending_review → in_review → returned → pending_review (resubmit) → approved → ingested → archived`, plus `approved → superseded` via recanvass. Yes/no, or request changes.
5. **Resolve the `approved → returned` question.** Live code (`return_packet()`) currently allows this transition; no Blueprint source supports it. Confirm: is this a bug to close, or an intentional "unapprove" feature to formally document? The recommendation assumes it's a bug — this needs explicit confirmation before the API change in DEC000001 §9 is made.
6. **Confirm whether a hard-terminal `rejected` state (distinct from the recoverable `returned`) is needed.** The recommendation omits it for lack of evidence of need. If Founder knows of a real use case, say so now — cheaper to add before implementation than after.
7. **Confirm `draft` should be a persisted state** (a packet can exist in the DB before submission), not just a client-side/pre-persistence concept. The recommendation assumes yes.

## From DEC000002 (Restaurant Update Submission)

8. **Adopt the recommended canonical lifecycle:** `received → pending_review → in_review → returned → pending_review (resubmit) → rejected (terminal)`, and `approved → converted → archived`. Yes/no, or request changes.
9. **Confirm the `approved`/`converted` naming choice over §5i's `accepted`/no-`converted`.** The recommendation weights two live DB tables plus §5b over the single-source §5i wording — confirm this reasoning is acceptable.
10. **Confirm whether `partner_submissions`'s existing divergence from `restaurant_update_submissions`** (it already has `converted`, the other doesn't) was intentional or an oversight. This affects whether the same migration should touch both tables or just one.
11. **Confirm whether `received` is worth persisting as distinct from `pending_review`,** or whether it should be dropped from the canonical model as redundant.

## Sequencing note (not a decision, just scope framing)

DEC000001 has live behavior to migrate (existing packets, working endpoints) — its risk is concentrated in the `approved → returned` and resubmission-loop changes (#5, #7 above). DEC000002 has zero live API/UI to break — its main risk is building against an unconfirmed model later, not breaking anything now (#9-11 above). If the Founder wants to approve one record ahead of the other, DEC000002 is the lower-risk one to greenlight first since no code depends on it yet.

---

No further action will be taken — no migration written, no endpoint changed, no UI touched, no registry status flipped to `approved` — until the choices above are resolved.
