# DEC000002 — Canonical Restaurant Update Submission State Machine

**Status:** draft — awaiting Founder approval
**Decision basis:** architectural_requirement, compliance_or_risk_control
**Decision dependencies:** none (foundational record, sibling to DEC000001)
**Registry impact:** governs `*.submission.*` namespace commands (CMD-series, see §3 below)

---

## 1. Competing versions, side by side

Four data points were checked — one more than for DEC000001, because a sibling DB table provides internal corroborating evidence not present for intake packets.

| Source | States (in order) | Notes |
|---|---|---|
| Blueprint §5b (generic State Machine Philosophy) | `pending_review → in_review → approved → returned → rejected → converted` | 6 states, generic "Submission" row, not entity-specific. |
| Blueprint §5i (Data Lifecycle Standard, Restaurant Update Submission table) | `received → pending_review → in_review → accepted → rejected → archived` | 6 states, entity-specific. Trust threshold = `accepted`. Uses `accepted`, not `approved`; has no `converted`. |
| Live DB — `operations.restaurant_update_submissions` (`011_submission_tables.sql`) | CHECK allows: `pending_review, in_review, approved, returned, rejected` | 5 states. No `received`, no `accepted` (uses `approved` instead), no `converted`, no `archived`. Has two extra columns — `resulting_intake_session` (text) and `resulting_evidence_summary` (jsonb) — that function as a de facto conversion audit trail in place of a `converted` status value. |
| Live DB — `operations.partner_submissions` (sibling table, same migration) | CHECK allows: `pending_review, in_review, approved, returned, rejected, converted` | 6 states — matches §5b almost exactly, including `converted`, which `restaurant_update_submissions` lacks. Used here as corroborating internal-consistency evidence: the codebase itself is inconsistent about whether "converted" belongs in this family of workflows. |

No API or UI exists for either submissions table (confirmed: no submissions router is mounted in `api/main.py`, which only mounts `ai_usage`, `restaurants`, `business_development`, `intake`). This is a materially different starting condition from DEC000001: there is no live behavior to reconcile against, only schema. Migration and behavioral risk are correspondingly lower for this decision.

## 2. Terminology and transition conflicts

- **`received` (§5i) vs implicit creation-only state elsewhere.** §5i is the only source with an explicit initial "the submission exists but hasn't been triaged yet" state. §5b, and both DB tables, start directly at `pending_review`. Whether "received" is a meaningfully distinct moment from "pending_review" (e.g., automated intake vs. queued for a human) is unresolved by any source.
- **`accepted` (§5i) vs `approved` (§5b, both DB tables).** Both DB tables agree with §5b's naming, not §5i's. §5i is the outlier here, unlike in DEC000001 where §5i's naming was closer to the live system.
- **`converted` (§5b, `partner_submissions`) is absent from §5i and from `restaurant_update_submissions`.** This is the sharpest conflict in this record. §5i replaces the concept with a trust-threshold-at-`accepted` model plus (implicitly) whatever happens after acceptance being tracked elsewhere. The live `restaurant_update_submissions` table doesn't have a `converted` status value, but it does have `resulting_intake_session` and `resulting_evidence_summary` columns — meaning the *information* `converted` would represent (that a submission was turned into something else) is captured as data rather than as a state. `partner_submissions`, built in the same migration, takes the opposite approach and uses a `converted` status value instead. This is a genuine internal inconsistency in the current codebase, not just a Blueprint-vs-DB conflict.
- **`archived` (§5i) is absent from both DB tables and from §5b.** Same gap pattern as DEC000001 — Blueprint's archival philosophy (§5i design rule "archive over delete") is not implemented for either submission table.
- **`rejected` is present in all four sources** — this is the one state with no conflict at all across every version.

## 3. Phase 5 commands that depend on this decision

Per `docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md` §20-§21, the `*.submission.*` namespace is entirely in **missing/future** status — no command in this family is implemented, because no API or UI exists yet. This decision is a precondition for building any of them:

- `restaurant.submission.receive` (or `.submit`) — future/missing.
- `restaurant.submission.review` — future/missing.
- `restaurant.submission.accept` (or `.approve`) — future/missing; naming depends on this decision.
- `restaurant.submission.return` — future/missing.
- `restaurant.submission.reject` — future/missing.
- `restaurant.submission.convert` — future/missing; whether this exists as a distinct command at all depends on whether `converted` survives as a canonical state (see §5-6).
- `restaurant.submission.archive` — future/missing.

Because none of these are implemented, this decision has zero live-behavior migration risk — unlike DEC000001, adopting a canonical model here breaks no running code and requires no data backfill beyond whatever rows already exist in `restaurant_update_submissions` (which use only the 5 already-live states, all of which survive under every candidate below).

## 4. Evaluation against the 9 criteria

Three candidates: **Candidate A** (adopt §5i as-is), **Candidate B** (adopt §5b/DB `converted`-based model as-is), **Candidate C** (revised canonical model).

| Criterion | §5b / DB-style (`approved`, `converted`) | §5i (`accepted`, no `converted`, `archived`) | Notes |
|---|---|---|---|
| Operational clarity | High — `converted` clearly marks "this became an intake run/evidence," distinct from mere approval | Medium — `accepted` alone doesn't say what happened next; that information is implicit unless captured elsewhere | Blueprint Workflow 2 (§6) itself says "no restaurant submission writes directly to production evidence" — implying a visible conversion step is operationally meaningful, favoring `converted` |
| Auditability | Medium — a `converted` status value is a first-class, queryable audit fact | Medium — §5i has no trigger implemented either; and without a `converted` state, "did this get converted and when" must live in a separate column or table, which `restaurant_update_submissions` already half-does via `resulting_intake_session`/`resulting_evidence_summary` | Neither Blueprint version has an implemented audit trigger; this is a gap regardless of which is chosen |
| Nontechnical usability | High — "converted" is intuitive to a reviewer ("this became a real update") | Medium — "accepted" alone leaves a reviewer asking "then what?" | |
| Evidence-boundary protection (§5 Blueprint) | Strong if paired with the existing `resulting_evidence_summary` column, which already exists precisely to trace a submission to what it produced | Strong in principle (trust threshold at `accepted`) but weaker in practice without an explicit terminal marker for "this is now reflected in evidence" | The Evidence Boundary doctrine (§5) requires traceability from submitted data to what it becomes — a `converted` state plus the existing `resulting_*` columns directly serves that requirement |
| Return/correction workflows | `returned` present in all sources; no conflict | Same | Not a differentiator between candidates |
| Archival/historical preservation | Absent from DB-style model as written; would need to be added | Present (`archived`) | Point in favor of incorporating §5i's `archived`, regardless of which naming wins on `approved`/`accepted` |
| Implementation complexity | Low — closest to the schema already live in `restaurant_update_submissions`, and exactly matches `partner_submissions` | Medium — requires renaming `approved`→`accepted` (a live column value rename) and adding `received`, `archived` | Because no API/UI consumes these values yet, a rename is cheap now and will only get more expensive the longer it waits |
| Migration risk | Very low — no behavior depends on this today | Low — same, but a rename is one extra step over a pure addition | |
| Compatibility with current data | High | High — existing rows use `pending_review`/`in_review`/`approved`/`returned`/`rejected`, all of which map 1:1 or via simple rename to §5i's set | |

## 5. Recommendation

**Adopt Candidate C — a revised canonical model that uses §5i's fuller state set and archival philosophy, but keeps `approved`/`converted` naming from §5b and the live DB (both `restaurant_update_submissions` and `partner_submissions` agree on this naming, which is stronger corroborating evidence than §5i's single-source `accepted`), and formalizes the existing `resulting_intake_session`/`resulting_evidence_summary` columns as the data payload of the `converted` state rather than discarding them.**

Recommended canonical lifecycle:

```
received → pending_review → in_review → returned → pending_review (resubmission loop)
                                        → rejected (terminal)
                                        → approved → converted → archived
```

Naming choices: `approved` over `accepted` (matches both live DB tables, not just one Blueprint section); `converted` retained as a real state (matches `partner_submissions` and §5b, and gives the trust-boundary crossing a first-class, queryable moment consistent with Workflow 2's "no submission writes directly to production evidence" language); `received` and `archived` adopted from §5i (neither conflicts with anything live, since no live code enforces the current 5-state CHECK constraint through any API).

## 6. Nature of this recommendation

This **combines elements from multiple versions**, and in one respect **resolves an internal inconsistency within the live codebase itself** (the `partner_submissions`/`restaurant_update_submissions` mismatch on `converted`), rather than choosing one Blueprint section over the other outright. It does not adopt §5i verbatim (drops `accepted` naming in favor of the two-source-corroborated `approved`), and it does not adopt the live `restaurant_update_submissions` schema verbatim either (adds `received`, `archived`, and `converted`, none of which are in that table's current CHECK constraint).

## 7. Assumptions

- Assumes `restaurant_update_submissions` lacking `converted` was an oversight or an earlier-stage schema relative to `partner_submissions`, not an intentional design divergence — no commit history or design doc was reviewed to confirm this either way, so this is treated as an open question for the Founder rather than a settled fact.
- Assumes `received` is worth persisting as distinct from `pending_review` (e.g., to timestamp intake separately from triage) — if the Founder judges these are operationally identical, `received` can be dropped from the canonical model with no other change required.
- Assumes the existing `resulting_intake_session`/`resulting_evidence_summary` columns should be preserved and paired with the new `converted` status value (populated when the status transitions to `converted`) rather than replaced.

## 8. Alternatives rejected

- **Candidate A (adopt §5i verbatim, including `accepted`, no `converted`):** rejected as the literal model because it's the only one of the four sources using `accepted`, while two independent live tables and one Blueprint section agree on `approved`/`converted` — weight of corroborating evidence favors the latter naming.
- **Candidate B (formalize `restaurant_update_submissions` exactly as it stands today, no changes):** rejected. It would leave the table permanently inconsistent with its own sibling `partner_submissions` table, and would leave §5i's archival requirement unimplemented with no plan to close it.
- **Drop `converted` entirely and rely solely on the `resulting_*` columns:** considered, since §5i doesn't use a `converted` status value. Rejected because a status value gives conversion state a place in every status-scoped query (queue views, indexes, RLS policies) that a nullable payload column doesn't provide as cleanly, and because `partner_submissions` already establishes this as the working pattern elsewhere in the same codebase.

## 9. Exact downstream changes this recommendation would require

**Blueprint (`docs/GOLDPAN_MASTER_OS_BLUEPRINT.md`):**
- §5i's Restaurant Update Submission lifecycle table: rename `accepted` → `approved` to match the canonical model, and add `converted` between `approved` and `archived`.
- §6 Workflow 2 ("Restaurant Update Submission," 8 steps): confirm the step that currently says a submission becomes evidence maps onto the new explicit `converted` state.

**Database (new migration, e.g. `01X_restaurant_submission_lifecycle_v2.sql`):**
- Alter `packet_status`-equivalent CHECK constraint on `operations.restaurant_update_submissions` to add: `received`, `converted`, `archived`.
- No rename of existing values is required (the table already uses `approved`, not `accepted`) — this is a purely additive migration, the lowest-risk of any change across both decision records.
- Consider whether `partner_submissions` should also gain `received`/`archived` for consistency — noted as a related but separate decision, not required for this record to be actionable.
- Add an audit trigger on `operations.restaurant_update_submissions`, matching the pattern recommended for `intake_packets` in DEC000001 §9 and the existing pattern in `006_triggers.sql`.

**API (new — none exists today):**
- Build `api/routers/submissions.py` (or similar) implementing the command set in §3, gated on the canonical states from §5 rather than the current 5-value constraint.
- Mount the new router in `api/main.py`.

**Frontend (new — none exists today):**
- Build the submissions queue/review UI in `web/app/admin/` using the canonical states as its source of truth from the start, avoiding the need for a later rename that DEC000001 had to account for on the intake-packet side.

**Audit events:**
- Every transition, including `received` (if adopted) and `converted`, must log actor, timestamp, and reason per §5f.10.

**Command Registry (`docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md`):**
- Populate the `*.submission.*` command entries (currently future/missing) with this canonical state model as their governing basis.
- Resolve §22's DEC000002 placeholder by referencing this file directly.

## 10. Risks, guardrails, validation criteria, revisit triggers

**Risks:**
- Because no API/UI exists yet, there is no risk of breaking live behavior — the primary risk is instead building the new submissions API against the *wrong* canonical model if this decision is approved with the `received`/`converted` assumptions unconfirmed.
- The `partner_submissions` inconsistency flagged in §7 is treated here as likely-oversight; if it was actually intentional (e.g., partner submissions and restaurant-update submissions are meant to have genuinely different lifecycles), that should be confirmed before this migration also touches `partner_submissions`.

**Guardrails:**
- Do not build the submissions API/UI until this record is approved — there is no existing behavior forcing urgency, so there's no reason to build against an unconfirmed model.
- The `converted` transition should be the only status change permitted to write to `resulting_intake_session`/`resulting_evidence_summary`, keeping the evidence-boundary trace and the state transition atomic.

**Validation criteria:**
- `restaurant_update_submissions` and `partner_submissions` use a consistent status vocabulary after migration, or any remaining divergence is explicitly justified in a follow-up note.
- Every canonical state has a defined entry and exit path before the submissions API is built (avoiding the "implemented but unreachable state" pattern found in DEC000001's `in_review`).

**Revisit triggers:**
- If Founder confirms `received` and `pending_review` should be merged, simplify the canonical model accordingly before the migration is written — cheap to change now, more disruptive after the API is built.
- If a future need arises for `partner_submissions` to diverge intentionally from `restaurant_update_submissions`, this record's assumption of shared vocabulary should be revisited.
