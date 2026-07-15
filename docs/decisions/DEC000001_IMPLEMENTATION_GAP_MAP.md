# DEC000001 Implementation Gap Map

**Purpose:** ground the implementation pass in what actually exists on disk before writing migration or API code. This is a comparison document, not a design document — it does not reopen DEC000001. Every "gap" below is a difference between the approved v4.1 model (Founder-approved 2026-07-13) and the current schema (`supabase/migrations/015_intake_packets.sql`) / API (`api/routers/intake.py`).

---

## 0. Identity source — resolved

DEC000001 §7 item 6 deferred confirming "the exact canonical user/auth table that `*_user_id` resolves to." That table already exists and does not need to be invented:

- `operations.users` (migration 004): `user_id uuid PRIMARY KEY` — mirrors Supabase Auth (`auth.users.id`), `role` constrained to `canvasser | reviewer | coordinator | admin`.
- `operations.current_user_id()` / `operations.current_user_role()` (migration 005): SQL functions reading `sub` / `user_role` off `request.jwt.claims` — i.e., a per-user Supabase Auth JWT.

**Resolved:** every `*_user_id` field this decision requires (`claimed_by_user_id`, `archived_by_user_id`, `actor_id` when `actor_type = user`) should be `uuid REFERENCES operations.users(user_id)`. No new identity model, no new Decision Record.

**Flagging, not silently deciding:** the existing admin endpoints (`intake.py`, and every other router) authenticate via a single shared `X-Admin-Key` header (`api/deps.py`), not a per-user Supabase Auth session. `operations.current_user_id()` reads `request.jwt.claims`, which will be empty under service-role/shared-key calls — it will not resolve an acting user automatically. This means the API layer has no current mechanism to know *which* `operations.users` row is acting on a claim/approve/return/reject/archive call.

This is an API-authentication mechanism question, not an architectural one — DEC000001 defines what the `*_user_id` fields mean, not how a FastAPI request authenticates. Proposed pragmatic fix, consistent with the existing shared-key pattern rather than inventing a new auth architecture: add a required `X-User-Id` header (validated against `operations.users`, must be `is_active`) to every `intake.review.*` / `intake.packet.*` write endpoint, until real per-user Supabase Auth sessions are wired into these admin routes. This is called out explicitly rather than embedded silently, per your instruction — flag it now; will proceed with this approach for the migration/API work unless you want something different.

---

## 1. Schema gaps — `operations.intake_packets` (migration 015 → new migration 016)

| Item | Current (015) | Approved (DEC000001) | Gap |
|---|---|---|---|
| `packet_status` values | `pending_review, returned, approved, ingested` (4) | `pending_review, in_review, returned, approved, rejected, ingested` (6, §6) | Missing `in_review`, `rejected`. `CHECK` constraint needs updating. |
| Claim fields | none | `claimed_by_user_id uuid REFERENCES operations.users(user_id)`, `claimed_at timestamptz` (§5.3-§5.4) | Missing entirely. |
| Supersession | none | `superseded_by_packet_id uuid REFERENCES operations.intake_packets(packet_id)`, `CHECK (superseded_by_packet_id != packet_id)`, partial unique `UNIQUE (superseded_by_packet_id) WHERE superseded_by_packet_id IS NOT NULL` (§5.6) | Missing entirely. |
| Archival | none | `archived_at timestamptz`, `archived_by_user_id uuid REFERENCES operations.users(user_id)` (non-status attributes, §5.11) | Missing entirely. |
| `reviewed_by` | `text` (free-text, no FK) | Stable user ID only, per §5.3's blanket rule extended to every actor field | Wrong type — needs to become `uuid REFERENCES operations.users(user_id)`, or be retired in favor of the event log's `actor_id` (event log is the permanent reviewer-of-record per §5.5, so `reviewed_by` may be redundant once `intake_packet_events` exists). |
| `return_reason` | `text`, nullable | Reason is mandatory on return (carried behavior) and on reject (§5.10, new) | Existing column reusable for `return`; `reject` needs its own mandatory reason path (event log `reason` column, §5.8, satisfies this — no new packet-row column needed). |

## 2. New tables required (§5.8)

Neither exists today.

**`operations.intake_packet_revisions`** — payload snapshots, `edit_payload` events only:
`revision_id, packet_id, prior_payload jsonb, actor_user_id uuid REFERENCES operations.users(user_id), reason, created_at`. Always human-authored — `actor_user_id`, not `actor_type`/`actor_id`.

**`operations.intake_packet_events`** — full lifecycle/claim/annotation audit trail:
`event_id, packet_id, event_type, actor_type (user|system|pipeline), actor_id, reason (nullable, required for override/return/reject), metadata jsonb, created_at`. Every row must set both `actor_type` and `actor_id` (§8 guardrail) — no null `actor_type`.

## 3. Command-by-command gap (Registry CMD IDs per §3)

| Command | DB | API | Gap classification |
|---|---|---|---|
| `intake.packet.submit` (CMD000003) | ✅ | ✅ (`submit_packet`) | None — no change needed. |
| `intake.review.claim` (new) | needs claim columns | ❌ no endpoint | Full build — API gap + schema gap. |
| `intake.review.release` (new) | needs claim columns | ❌ no endpoint | Full build. |
| `intake.review.approve` (CMD000005) | ✅ (status col) | ⚠️ exists (`approve_packet`), but allows approval from **any** non-ingested status — no `in_review`/claimant check | Known, already-flagged drift (Command Registry §18) — fix now as part of this pass, not deferred (the CMD000005/006 item Brad deferred is the *live gating* behavior generally; this migration is exactly where §5.9's `in_review`-only precondition gets implemented). |
| `intake.review.return` (CMD000006) | ✅ | ⚠️ exists (`return_packet`), allows return from `pending_review` **or** `approved` — §5.9 requires `in_review` only, both those excluded | Same as above — tighten in this pass. |
| `intake.packet.reject` (CMD000009) | needs `rejected` status | ❌ no endpoint | Full build. |
| `intake.packet.mark_ingested` (CMD000007) | ✅ | ✅ (`mark_ingested`) — currently the *only* ingestion path | Needs demotion: keep only as restricted/reason-required reconciliation, not the ordinary path. |
| `intake.packet.commit_ingest` (CMD000008) | n/a — this command *is* the durable write + status flip | ❌ does not exist | Full build — this becomes the sole ordinary path to `ingested`, per §5.7. Note: this repo's actual durable-write logic lives in `ingest_packet.py` (external script), not in the API — needs a design decision on whether `commit_ingest` is an API endpoint that shells out / calls the same logic, or the existing external-script flow wrapped with a governed status flip. Flagging this now: this is an implementation-sequencing detail, not a DEC000001 reopening, since §5.7 specifies the *rule* (durable write and status flip must be atomic and system-controlled) but not the specific code path. |
| `intake.packet.reopen` (CMD000010) | n/a | n/a | Correctly out of scope — remains reserved/undefined per §5.1, §7 item 3. Not building this. |
| `intake.packet.edit_payload` (new) | needs `returned`-only mutability + revisions table | ❌ no endpoint | Full build. |
| `intake.packet.resubmit` (new) | needs `returned`/`pending_review` transition | ❌ no endpoint | Full build. |
| `intake.packet.archive` (new) | needs `archived_at`/`archived_by_user_id` | ❌ no endpoint | Full build. |

## 4. Role enforcement gap

DEC000001 §4 requires a Governance Reviewer / Intake Specialist role boundary (reviewers never mutate `packet_data`; only Intake Specialists call `edit_payload`/`resubmit`). `operations.users.role` currently only has `canvasser | reviewer | coordinator | admin` (migration 004) — no `Governance Reviewer` or `Intake Specialist` role value exists in that enum yet. This needs either a mapping decision (e.g., `reviewer` role = Governance Reviewer; a new role value or a separate `is_intake_specialist` flag for Intake Specialist) or a schema addition. **Flagging, not deciding silently:** recommend mapping `operations.users.role = 'reviewer'` → Governance Reviewer and `'canvasser'` → Intake Specialist for now, since those are the closest existing semantic matches and no new Decision Record is needed to make that mapping — but calling it out explicitly since DEC000001 doesn't itself specify the mapping against this particular users table (it named the Blueprint roles abstractly, per §4's own text: "does not introduce a vague label... where a defined role already applies").

## 5. Not in scope for this pass (confirmed correctly excluded)

- DEC000002 / Submission build — explicitly deferred by Brad's instruction until Intake is stable.
- `resubmit` invocation-authority-style deferrals don't apply here (that's a DEC000002 item) — DEC000001's `resubmit`/`edit_payload` already have defined actors (§4), no deferral.
- Broader Blueprint consistency sweep — documentation maintenance, tracked separately, not a blocker.

---

**Next step (per your instruction, step 2 of the implementation order):** write migration `016_intake_packet_state_machine.sql` covering §1-§2 above, pending your confirmation of the two flagged items — the `X-User-Id` header approach (§0) and the role-mapping recommendation (§4) — since both affect every subsequent endpoint.
