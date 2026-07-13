# DEC000002 — Canonical Restaurant Update Submission State Machine

**Status:** draft v2 — awaiting Founder approval (revised per Founder review of v1)
**Decision basis:** architectural_requirement, compliance_or_risk_control
**Decision dependencies:** none (foundational record, sibling to DEC000001)
**Registry impact:** governs `submission.restaurant_update.*` and `submission.convert_to_intake` namespace commands (see §6)

**Revision note:** v1 proposed a single linear `packet_status`-style field running `received → pending_review → in_review → returned → approved → converted → archived`. Founder review identified that this conflates three genuinely different concerns — review outcome, downstream conversion outcome, and retention — into one field, and asked for a full re-evaluation using the actual `restaurant_update_submissions` schema (now read in full; v1 had only partially inspected it) rather than the earlier partial reading. This version replaces §4 onward; §1-§3 are retained with corrections noted inline.

---

## 1. Competing versions, side by side (corrected)

| Source | States (in order) | Notes |
|---|---|---|
| Blueprint §5b (generic) | `pending_review → in_review → approved → returned → rejected → converted` | 6 states, generic "Submission" row. |
| Blueprint §5i (Restaurant Update Submission table) | `received → pending_review → in_review → accepted → rejected → archived` | 6 states, entity-specific. Uses `accepted`, not `approved`; no `converted`. |
| Live DB — `operations.restaurant_update_submissions` (`011_submission_tables.sql`, full text now read) | `status` CHECK: `pending_review, in_review, approved, returned, rejected` (5 values) | **Correction from v1:** the table's own column comment states this explicitly: *"pending_review → in_review → approved / returned / rejected. approved does NOT automatically write to evidence — reviewer must take deliberate action (trigger Intake session or direct edit)."* This is significant and was under-weighted in v1: the schema's own documentation already treats "approved" and "what happens after approval" as two separate ideas, even though today they share no separate status field for the latter — the `resulting_intake_session`/`resulting_evidence_summary` columns are filled in as a second, later step after `approved` is reached, not as part of reaching it. |
| Live DB — `operations.partner_submissions` (sibling table, same migration) | `status` CHECK: `pending_review, in_review, approved, returned, rejected, converted` (6 values) | Has `converted`, plus `converted_action_id`/`converted_partner_id` — see §2 for why this is not strong evidence that `restaurant_update_submissions` should match it. |

No API or UI exists for either submissions table (confirmed: `api/main.py` mounts only `ai_usage`, `restaurants`, `business_development`, `intake`).

## 2. Sibling-table evidence, reassessed

v1 treated `partner_submissions`'s `converted` status as corroborating evidence that `restaurant_update_submissions` should adopt the same pattern. Having now read both table definitions in full, this is not a safe inference:

- **`partner_submissions` converts to exactly one kind of downstream object family**: a CRM action or partner record (`converted_action_id → operations.partner_actions`, `converted_partner_id → operations.partners`). Its "conversion" is a single, simple, one-shot linkage.
- **`restaurant_update_submissions` converts to one of two structurally different outcomes**: "(a) manually triggers an Intake session (records session ID here), OR (b) directly edits evidence records (records a JSON summary here)" — per the table's own comment. These are not the same kind of downstream action, and only one of them (Intake session) resembles what DEC000001 governs; the other (direct evidence edit) bypasses Intake entirely.
- The two tables also differ structurally beyond status: `restaurant_update_submissions` has `priority`, `dish_id`, `effective_date`, `attachment_*` fields with no `partner_submissions` equivalent, and links to `evidence.dishes`/`evidence.restaurants` rather than `operations.partners`.

**Conclusion:** the divergence between the two tables (partner_submissions has `converted`; restaurant_update_submissions does not) looks like it reflects a genuine difference in downstream complexity, not an oversight to be reconciled. This record does not recommend modifying `partner_submissions`, and does not treat its `converted` status as proof that `restaurant_update_submissions` needs an identical field. Whether `partner_submissions` needs its own review or archival attributes is out of scope here and not addressed by this decision.

## 3. Phase 5 commands that depend on this decision (corrected naming)

The Command Registry (`docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md` §20) already reserves specific names, which this revision preserves rather than replacing with an invented `restaurant.submission.*` family (v1's error):

- `submission.restaurant_update.view` (CMD000024, query, missing)
- `submission.restaurant_update.review` (CMD000025, approval, missing) — currently a single combined command; §6 evaluates splitting it.
- `submission.convert_to_intake` (CMD000026, workflow_trigger, missing) — already named and typed distinctly from the review commands, which independently corroborates separating review from conversion (§4): the registry's own author already modeled conversion as a different *kind* of command (`workflow_trigger`) than review (`approval`), before this decision was drafted.

## 4. Review outcome vs. conversion outcome — the central issue

Two models evaluated, per the Founder's framing:

**Model A — one linear status** (v1's model): `received → pending_review → in_review → returned → approved → converted → archived`. A submission's status keeps moving after approval to reflect what happened downstream.

**Model B — review outcome separated from conversion outcome:**

```
review_status:      pending_review | in_review | returned | approved | rejected

conversion_status:   not_required | pending | in_progress | completed | failed
conversion_type:      intake_packet | identity_update | no_action | other
resulting_intake_packet_id
resulting_evidence_summary
converted_at
converted_by
```

**Recommendation: Model B.** Reasons:

- **It matches what the schema already says, not just what it currently enforces.** The live column comment ("approved does NOT automatically write to evidence — reviewer must take deliberate action") already describes review and conversion as two separate moments; Model A would have to re-merge something the current design already keeps apart in practice, just not yet in a dedicated field.
- **An approved submission does not stop being approved if conversion fails or is retried.** Under Model A, "approved" is a transient waypoint that gets overwritten by `converted` — there is no way to represent "approved, conversion attempted and failed, will retry" without inventing extra states (`approved_conversion_failed`?) that don't belong in a review-outcome field. Under Model B, `review_status` stays `approved` permanently and `conversion_status` carries the retry history.
- **Two different downstream object types already exist for this entity** (Intake session vs. direct evidence edit — see §2). A single `converted` status cannot distinguish which happened; `conversion_type` can.
- **`not_required` is a real, common case.** Some approved submissions (e.g., a `contact_update`) may need no conversion at all — a direct edit made once and closed, not a workflow. Model A has no clean way to represent "approved, nothing further needed" other than jumping straight to a `converted` that didn't really convert anything, or leaving it stuck at `approved` forever, which is indistinguishable from "approved, conversion still pending."

## 5. `received` — evaluated against actual need

Checked directly against the schema: no `received` state exists anywhere in either submissions table, and the `pending_review` default comment reads "just arrived, nobody has looked" — meaning `pending_review` already serves as the receipt marker in the live system. No distinct validation, deduplication, routing, or security-screening stage exists between insertion and queue entry today.

**Recommendation:** do not add `received` as a status. Use `created_at` (already present on both tables) as the receipt timestamp — no new column is even needed, since `created_at` already means exactly this. If a future pre-queue stage (e.g., automated spam/dedup screening before a submission reaches a human queue) is built, a distinct state can be added then against a real requirement.

## 6. Archival — separated from review status

Confirmed via the schema: no `archived` state or column exists on either table today. Per the Founder's framing and consistent with the DEC000001 archival treatment:

**Recommendation:** add `archived_at timestamptz`, `archived_by text`, `archive_reason text` (all nullable) rather than an `archived` review_status value. The submission's final review outcome (`approved` or `rejected`) must remain visible after archival — an `archived` status would destroy that information unless duplicated elsewhere, which is unnecessary complexity. Archival only changes queue visibility (default views filter `WHERE archived_at IS NULL`); it does not change what the submission's outcome was.

## 7. Correction and resubmission behavior

This is resolved differently from DEC000001, because the evidence differs. `restaurant_update_submissions`'s own table comment states: *"Append-only for the submission row; only status and review fields are mutable."* This is an explicit design constraint already present in the schema — the original submitted `payload_json`/`description` is not meant to be edited after creation, unlike an Intake Packet's `packet_data`, which DEC000001 found no such constraint against.

**Recommendation:** a `returned` submission is corrected via a **linked child submission**, not an in-place edit and not an append-only revision-log-on-the-same-row. New column: `resubmission_of_submission_id uuid REFERENCES operations.restaurant_update_submissions(submission_id)`. The original row is never mutated beyond its status/review fields, fully honoring the existing "append-only for the submission row" comment; the corrected payload lives in a new row that references the one it corrects. This preserves, without any new audit table: the original payload (original row, untouched), the return reason/reviewer/timestamp (original row's `return_reason`/`reviewed_by`/`reviewed_at`), the corrected payload (child row), and the resubmission event (child row's `created_at` plus the `resubmission_of_submission_id` link). Every subsequent decision on the child row follows the same `review_status`/`conversion_status` model as any other submission.

## 8. Command namespace — preserved, with a separately-flagged discretization option

Per the Founder's instruction, existing registry names are not replaced:

- `submission.restaurant_update.view` (CMD000024) — unchanged.
- `submission.restaurant_update.review` (CMD000025) — currently registered as one combined `approval`-type command. **Separate recommendation, requiring its own approval, not bundled into this decision:** split into discrete actions — `submission.restaurant_update.claim`, `submission.restaurant_update.return`, `submission.restaurant_update.approve`, `submission.restaurant_update.reject` — mirroring the claim/return/approve pattern DEC000001 established for Intake Packets, for the same reason (an undifferentiated "review" command doesn't distinguish claiming a queue item from deciding it). This is presented as an option, not adopted by default, since the registry currently models it as a single command and changing that is a namespace decision distinct from the state-machine question this record is about.
- `submission.convert_to_intake` (CMD000026) — unchanged; this is the natural home for the conversion action described in §4, already typed as `workflow_trigger` rather than `approval` in the existing registry, consistent with Model B's separation.

## 9. Conversion guardrail (revised)

v1 implicitly assumed conversion tracking required a `converted` status. Revised requirements, independent of any specific field:

- A submission must reach `review_status = approved` before any conversion attempt may begin.
- `resulting_intake_packet_id` / `resulting_evidence_summary` / `converted_at` / `converted_by` are written only by the governed conversion workflow (`submission.convert_to_intake`), never directly by a reviewer action or any other code path.
- Where practical, downstream object creation and the linkage write should be atomic (e.g., a single transaction that both creates the Intake packet row and sets `resulting_intake_packet_id`), so a partial failure cannot leave a submission pointing at a downstream object that doesn't actually exist.
- A failed conversion attempt sets `conversion_status = failed` without altering `review_status` — the approval stands regardless of downstream success, and a retry simply re-attempts conversion against the still-`approved` submission.
- Every conversion attempt (success or failure) is audited — actor, timestamp, outcome — satisfying §5f.10 for this workflow specifically, not just at the review-decision level.

## 10. Recommended canonical model (Model B, refined)

```
review_status:        pending_review → in_review → returned → pending_review (new child row)
                       in_review → approved
                       in_review → rejected

conversion_status:     not_required | pending | in_progress | completed | failed
conversion_type:       intake_packet | identity_update | no_action | other

Attributes, not statuses:
  created_at                    — receipt marker (already exists; no new column)
  archived_at / archived_by / archive_reason
  resubmission_of_submission_id — links a corrected resubmission to the returned original
  resulting_intake_packet_id / resulting_evidence_summary / converted_at / converted_by
```

Five `review_status` values (unchanged from the live DB's 5-value `status` enum — this recommendation does not add or remove any review_status value, it only renames the field and adds the parallel conversion dimension). This is a smaller change to the review dimension than v1 proposed, and the added complexity (conversion_status/type, archival attributes, resubmission link) is additive rather than a redesign of the existing 5-state enum.

## 11. Nature of this recommendation

This combines elements from multiple sources: it keeps the live DB's exact 5-value review vocabulary (`pending_review, in_review, approved, returned, rejected` — matching neither §5b's nor §5i's naming exactly, since both include states the live schema doesn't need), and it introduces a conversion-outcome dimension that no source document proposes in these terms but that the live schema's own comments already imply conceptually. It explicitly does not adopt `partner_submissions`'s `converted` status pattern (§2), does not add `received` (§5), and does not add `archived` as a status (§6).

## 12. Assumptions

- Assumes the two documented post-approval outcomes ("triggers an Intake session" / "directly edits evidence records") are the right basis for `conversion_type`'s `intake_packet`/`identity_update` values; exact naming of `identity_update` vs. a more general "direct_edit" label is an open naming question, not an architectural one.
- Assumes `resubmission_of_submission_id` linking (§7) is preferred over building an append-only revision table like DEC000001's, specifically because this schema already declares itself row-append-only in a way Intake Packets do not.
- Assumes splitting `submission.restaurant_update.review` into discrete claim/return/approve/reject commands (§8) is desirable but treats it as optional, pending Founder input, since it wasn't asked for as a requirement, only evaluated as a candidate.

## 13. Alternatives rejected

- **Model A (single linear status through `converted`/`archived`):** rejected as the primary recommendation — conflates review outcome, conversion outcome, and retention into one field, contradicting the live schema's own comment separating "approved" from "deliberate action taken afterward." Retained above as the explicit comparison point requested.
- **Standardizing `partner_submissions` to match this decision:** rejected — no demonstrated need, and the two tables' downstream purposes differ enough (§2) that forced consistency could paper over a real distinction rather than fix an oversight.
- **In-place editing or same-row revision log for corrections (DEC000001's pattern):** rejected specifically for this entity, because `restaurant_update_submissions`'s own schema comment already declares the row append-only beyond status/review fields — a linked child-row model respects that existing constraint instead of overriding it.

## 14. Exact downstream changes this recommendation would require

**Blueprint (`docs/GOLDPAN_MASTER_OS_BLUEPRINT.md`):**
- §5i's Restaurant Update Submission lifecycle table: replace the single linear table with two parallel dimensions (review_status, conversion_status/type) plus the archival and resubmission attributes.
- §6 Workflow 2 ("Restaurant Update Submission"): confirm the 8-step workflow maps its "submission becomes evidence" step onto the new explicit conversion dimension rather than a status transition.

**Database (new migration, e.g. `01X_restaurant_submission_lifecycle_v2.sql`):**
- Rename `status` → `review_status` on `operations.restaurant_update_submissions` (no value changes — same 5 values).
- Add columns: `conversion_status text` (CHECK: `not_required, pending, in_progress, completed, failed`, default `not_required`), `conversion_type text` (CHECK: `intake_packet, identity_update, no_action, other`, nullable), `converted_at timestamptz`, `converted_by text`, `archived_at timestamptz`, `archived_by text`, `archive_reason text`, `resubmission_of_submission_id uuid REFERENCES operations.restaurant_update_submissions(submission_id)`.
- `resulting_intake_session`/`resulting_evidence_summary` (existing columns) are retained; consider renaming `resulting_intake_session` → `resulting_intake_packet_id` if it should be a typed FK to `operations.intake_packets(packet_id)` rather than free text — flagged as a data-typing improvement, not required by this decision.
- **No change to `partner_submissions`.**
- Add an audit trigger on `operations.restaurant_update_submissions`, consistent with the DEC000001 recommendation for `intake_packets`.

**API (new — none exists today):**
- Build the router implementing `submission.restaurant_update.view`, `submission.restaurant_update.review` (or its split form, per Founder decision), and `submission.convert_to_intake`, gated on `review_status = approved` before conversion per §9.

**Frontend (new — none exists today):**
- Build the submissions queue UI directly against `review_status`/`conversion_status` as two separate filterable dimensions from the start, avoiding a later split.

**Audit events:**
- Every review_status transition and every conversion attempt logged with actor/timestamp/reason/outcome per §5f.10 and §9.

**Command Registry (`docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md`):**
- Populate `submission.restaurant_update.view`, `submission.restaurant_update.review`, `submission.convert_to_intake` with this model as their governing basis.
- If the Founder approves splitting `.review` (§8), add `submission.restaurant_update.claim`, `.return`, `.approve`, `.reject` as new entries — a separate approval, not automatic.
- Resolve §22's DEC000002 placeholder by referencing this file directly.

## 15. Migration-risk statement (corrected)

v1 stated "zero live-behavior migration risk." Revised: **low live-application risk based on the inspected API and UI (no router is mounted, no frontend consumes this table), subject to verifying existing rows, any scripts, RLS policies, reports, or manual consumers not visible in this codebase inspection.** The RLS policies in `011_submission_tables.sql` reference `operations.current_user_role()` gating coordinator/admin access — this decision does not change those policies, but any implementation should re-verify they still apply correctly to the renamed/added columns before building the API.

## 16. Founder decisions required

1. **Confirm Model B (separate `review_status` + `conversion_status`/`conversion_type`) over Model A (single linear status through `converted`/`archived`).**
2. **Confirm no changes are made to `partner_submissions`** — its `converted` status and downstream linkage stay as-is, on the grounds that its conversion target (CRM/partner record) is simpler and structurally different from this entity's two conversion paths.
3. **Confirm dropping `received` as a status**, relying on existing `created_at` as the receipt marker.
4. **Confirm archival as attributes (`archived_at`/`archived_by`/`archive_reason`)** rather than a `review_status` value.
5. **Confirm the linked-child-submission model for corrections** (`resubmission_of_submission_id`), consistent with the schema's existing "append-only for the submission row" comment, rather than in-place editing or a same-row revision log.
6. **Decide whether to split `submission.restaurant_update.review`** into discrete `claim`/`return`/`approve`/`reject` commands now, or keep it as the single registered command and revisit later.
7. **Confirm `conversion_type` values** (`intake_packet`, `identity_update`, `no_action`, `other`) correctly represent the two documented post-approval outcomes, or specify different/additional values.
8. **Confirm whether `resulting_intake_session` should be retyped as a proper FK** (`resulting_intake_packet_id uuid REFERENCES operations.intake_packets`) as part of this migration, or left as free text for now.

## 17. Risks, guardrails, validation criteria, revisit triggers

**Risks:**
- Renaming `status` → `review_status` requires updating anything that queries the column by name — this codebase inspection found none (no API/UI), but per §15 this should be reverified rather than assumed safe.
- The child-row resubmission model means "the current version of a submission" requires following `resubmission_of_submission_id` chains rather than reading a single row — any future queue view must account for this (e.g., default to showing only rows with no submission pointing to them as the "latest," or an explicit `is_latest` flag).

**Guardrails:**
- No implementation proceeds until Founder decisions 1-8 above are made.
- `submission.convert_to_intake` must refuse to run against a submission whose `review_status` is not `approved`.

**Validation criteria:**
- Every `review_status` value has a defined entry/exit path; `conversion_status`/`conversion_type` are independently nullable/settable without disturbing `review_status`.
- A returned submission's correction chain is fully reconstructable via `resubmission_of_submission_id` without any row's original payload having been overwritten.
- `partner_submissions` remains untouched by this migration.

**Revisit triggers:**
- If `partner_submissions` is later found to need the same conversion-outcome separation (e.g., its CRM conversions start failing/retrying in ways that need tracking), revisit decision 2 as a new, separate decision — not a retroactive change to this one.
- If submission volume or queue-management needs grow, revisit decision 6 (splitting the review command) even if deferred now.
