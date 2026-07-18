# DEC000002 Implementation Gap Map

**Purpose:** ground the implementation pass in what actually exists on disk before writing migration or API code. This is a comparison document, not a design document — it does not reopen DEC000002. Every "gap" below is a difference between the Founder-approved v4.2 model (`docs/decisions/DEC000002_submission_state_machine.md`, **approved 2026-07-18**) and the schema that predated it (`supabase/migrations/011_submission_tables.sql`). No API or UI exists yet for either submissions table, per DEC000002 §1 — this pass is schema-first, mirroring the DEC000001 build order (gap map → migration → RPCs → API → UI).

Scope: `operations.restaurant_update_submissions` only. `operations.partner_submissions` is explicitly out of scope (DEC000002 §7 item 9, §2) — no change proposed to it here.

**Status update (2026-07-18):** both items flagged in §"Two flagged items" below were ruled on by Brad and are built and committed:

- `supabase/migrations/021_submission_state_machine.sql` — all schema gaps in §1 and the new table in §2 closed. Downstream event-reference judgment call resolved as **(b) metadata jsonb**, per Founder ruling, not the four-mirrored-column option.
- `supabase/migrations/022_submission_review_rpcs.sql` — `operations.resubmit_restaurant_update_submission` built (mechanics + state transition), per Founder ruling: build now, withhold both the API endpoint and invocation authority (no `GRANT EXECUTE` issued to any role — see the migration's own header for why an explicit `REVOKE ALL ... FROM PUBLIC` was required). `.claim/.release/.return/.approve/.reject/.convert_to_intake` remain unbuilt — see §3 below, unchanged from this gap map's original recommendation.

Both files (plus their `.validate.sql` companions) are committed to the repository as `109fc2ba150fa81299bd384b690486d0dee6a640` (`feat(submissions): add state machine and resubmit RPC`). DEC000002 itself was formally approved by the Founder on 2026-07-18, as drafted in v4.2, with the resubmit invocation-authority carve-out (§7 item 5) explicitly preserved — see `docs/decisions/DEC000002_submission_state_machine.md` header and `docs/decisions/PHASE5_FOUNDER_APPROVAL_REQUIRED.md`. Neither migration has been executed against a live database — that step, and the command-handler/API/UI layers below it, remain the genuine open work (§3).

---

## 0. Identity source — already resolved, reused from DEC000001

DEC000002 §7 item 8 names this "the same open question as DEC000001 §7 decision 9." It is not open — `DEC000001_IMPLEMENTATION_GAP_MAP.md` §0 already resolved it for the whole schema:

- `operations.users` (migration 004): `user_id uuid PRIMARY KEY`, `role` constrained to `canvasser | reviewer | coordinator | admin`.
- `operations.current_user_id()` / `operations.current_user_role()` (migration 005): read `sub`/`user_role` off `request.jwt.claims`.

**Resolved, no new decision needed:** `claimed_by_user_id`, `archived_by_user_id`, and `actor_id` (when `actor_type = user`) on the submission side all become `uuid REFERENCES operations.users(user_id)`, same as the Intake Packet side.

**Same open flag carried over, not re-litigated:** the API-authentication mechanism gap noted in the DEC000001 gap map (§0 — shared-key admin auth vs. `current_user_id()` reading a per-user JWT that will be empty under service-role calls) applies identically here once an API layer is built for submissions. Not a schema blocker for this migration; flagged again only so it isn't rediscovered as if new.

---

## 1. Schema gaps — `operations.restaurant_update_submissions` (migration 011 → new migration)

| Item | Current (011) | Approved (DEC000002 v4.2) | Gap |
|---|---|---|---|
| `status` values | `pending_review, in_review, approved, returned, rejected` (5) | Same 5 values (§7 item 1, §6) | **No gap.** Matches exactly — no `CHECK` change needed. |
| Claim fields | none | `claimed_by_user_id uuid REFERENCES operations.users(user_id)`, `claimed_at timestamptz` (§5.6) | Missing entirely. |
| Resubmission chain | none | `resubmission_of_submission_id uuid REFERENCES operations.restaurant_update_submissions(submission_id)`, `superseded_by_submission_id uuid REFERENCES operations.restaurant_update_submissions(submission_id)`, `CHECK (resubmission_of_submission_id != submission_id)`, `CHECK (superseded_by_submission_id != submission_id)`, partial `UNIQUE (resubmission_of_submission_id) WHERE resubmission_of_submission_id IS NOT NULL` (at most one direct child per parent, §5.7-§5.8) | Missing entirely. |
| Archival | none | `archived_at timestamptz`, `archived_by_user_id uuid REFERENCES operations.users(user_id)`, `archive_reason text` (§5.9) | Missing entirely. |
| `resolution_summary` | none | `text`, mandatory when `disposition_type = no_action` (enforced at the RPC layer, not a bare `CHECK`, since it's conditional on another column — §5.4) | Missing entirely. |
| Disposition model | none | `disposition_type text CHECK (... IN (intake_required, identity_review, no_action, exception_escalation))`, `disposition_status text CHECK (... IN (unassessed, pending, in_progress, completed, failed)) DEFAULT 'unassessed'`, `failure_stage text CHECK (... IN (handoff_call, local_write, downstream_terminal) OR failure_stage IS NULL)` (§5.3-§5.4, §6) | Missing entirely. |
| `resulting_intake_session` | `text`, free-text, no FK — own comment calls it a placeholder | Demoted explicitly by DEC000002 §5.11 to `resulting_intake_session_id`: **non-canonical**, optional, no confirmed target, excluded from cardinality rules | Rename/retype. Since no real "intake session" entity exists anywhere in the schema (§5.11's own finding), the cleanest carry-forward is renaming the column to `resulting_intake_session_id` and leaving it a plain nullable `text` or `uuid` with **no FK constraint** — there is nothing to reference yet. Recommend `uuid`, nullable, no FK, matching the "someday-FK-shaped placeholder" DEC000002 describes, rather than continuing as loose free text. |
| `resulting_intake_packet_id` | none | `uuid REFERENCES operations.intake_packets(packet_id)` — **canonical, ready to build** (§5.11) | Missing entirely. This is the one canonical downstream FK that can be built now — `operations.intake_packets` is real and DEC000001-governed. |
| `identity_review_item_id` | none | Canonical nullable FK for `identity_review` — **Blueprint-defined, target table not yet implemented** (§5.11) | Add as plain `uuid`, nullable, **no FK constraint** — there is no `identity_review_queue`-shaped table anywhere in migrations 001-020 to point at yet. |
| `exception_request_id` | none | Canonical nullable FK for `exception_escalation` — **future recommendation, no confirmed target** (§5.11) | Same treatment: plain nullable `uuid`, no FK. |
| `reviewed_by` / `reviewed_at` | `text` free-text / `timestamptz` | Reviewer identity is written into the append-only event log as part of `.approve`/`.reject`/`.return` (§5.4 step 3, §5.10) | Same pattern as the DEC000001 gap map's treatment of Intake's `reviewed_by`: likely redundant once the events table exists, since the event log becomes the reviewer-of-record. Not required to remove for correctness; flagging for a keep-or-drop call rather than deciding silently. Recommend keeping the columns as a cheap denormalized "last reviewer" convenience read, but treating the event log as authoritative. |
| `resulting_evidence_summary` | `jsonb` | Not part of the DEC000002 model at all | DEC000002 doesn't mention this field and doesn't contradict it either — it predates the decision record and isn't superseded by anything in it. Recommend leaving it in place (harmless, potentially still useful for the `identity_review`/direct-edit paths), distinct from the new mandatory `resolution_summary` field, which serves a different, DEC000002-specified purpose (§5.4). Flagging so it isn't mistaken for something DEC000002 requires or forbids. |
| Display-name snapshots | none exist (`reviewed_by` is free text, not a snapshot pattern) | No `_display_name` column permitted anywhere (§5.1, §8 validation criteria) | **No gap** — none were ever added to this table. Confirming explicitly since DEC000001 v3 had this exact problem and DEC000002 v3 mirrored it before removal; migration 011 predates both drafts and never picked up the pattern. |

## 2. New table required (§5.10)

Does not exist today.

**`operations.restaurant_update_submission_events`** — append-only audit trail, covering `claim, release, return, resubmit, approve, reject, disposition_selected, disposition_handoff_attempted, disposition_handoff_succeeded, disposition_handoff_failed, downstream_completion_received, archive`:

```
event_id                 uuid PK
submission_id             uuid REFERENCES operations.restaurant_update_submissions(submission_id)
event_type                text CHECK (...)
actor_type                text CHECK (user|system|pipeline)
actor_id                  text  -- user_id (uuid, as text) | service-account/system id | pipeline name/run id
initiating_actor_type      text CHECK (user|system|pipeline) NULL
initiating_actor_id        text NULL
downstream_caller_id       text NULL  -- downstream_completion_received only
prior_status / resulting_status                       text NULL
prior_disposition_status / resulting_disposition_status text NULL
failure_stage              text NULL
reason                     text NULL
created_at                 timestamptz NOT NULL DEFAULT now()
metadata                   jsonb
```

**One open design point, not resolved by DEC000002 itself, flagging rather than deciding silently:** §5.10 lists "downstream entity reference, where applicable" as its own line item in the event schema, separate from `metadata`. DEC000001's `intake_packet_events` table didn't need this (Intake Packets don't fan out to multiple downstream object types). Two ways to satisfy it here:

- **(a)** Four more nullable, unconstrained reference columns on the events table mirroring the submission row's own four (`resulting_intake_packet_id`, `resulting_intake_session_id`, `identity_review_item_id`, `exception_request_id`) — consistent with Option A's philosophy of purpose-specific columns over generic ones, but doubles the placeholder-FK surface across two tables.
- **(b)** Fold the downstream reference into the existing `metadata jsonb` column on `disposition_handoff_succeeded` / `downstream_completion_received` events only — the event row doesn't need referential-integrity enforcement (that's the submission row's job via its real FK), only a record of what happened.

**Recommend (b)** — simpler, and the events table is an audit log, not a place that needs its own FK constraints to do its job. Flagging for confirmation before writing the `CREATE TABLE`, since it's a genuine judgment call DEC000002's text doesn't pin down.

`claim, release, return, resubmit, approve, reject` are always `actor_type = user` with `initiating_actor_*` left null, per §5.10. `disposition_handoff_*` events set `actor_type = system` plus `initiating_actor_type = user` when a human invoked the routing command (the ordinary case today). `downstream_completion_received` sets `actor_type = system|pipeline` and populates `downstream_caller_id`.

## 3. Command-by-command gap (per §3's final command set)

| Command | DB | Buildable now? | Gap classification |
|---|---|---|---|
| `submission.restaurant_update.view` (CMD000024) | ✅ | — | No change. |
| `.claim` | needs claim columns | ✅ | Full build — mirrors `intake.review.claim` exactly: atomic `pending_review → in_review`, `claimed_by_user_id IS NULL` guard. |
| `.release` | needs claim columns | ✅ | Full build — mirrors `intake.review.release`. |
| `.return` | ✅ (`return_reason` reusable) | ✅ | Needs the atomic claim-clear + event-write wrapper; reason already mandatory in practice via `return_reason`. |
| `.approve` | needs disposition columns | ✅ | Full build — single RPC per §5.4: status flip, claim clear, reviewer event, derive `disposition_status` from `disposition_type`, reject any call missing `disposition_type`, reject `no_action` missing `resolution_summary`. |
| `.reject` | ✅ (status already has `rejected`) | ✅ | Full build — status flip + claim clear + mandatory-reason event, mirrors `intake.packet.reject`. |
| `.resubmit` | ✅ (021) | ✅ **built (022)** | Per DEC000002 §5.7/§7 item 5, **the record approves the command's design and mechanics as ready to build, but explicitly withholds approval of who may invoke it** — registry status stays `draft` regardless of the Founder's 2026-07-18 approval of the rest of the record. Built per Founder ruling: `operations.resubmit_restaurant_update_submission` exists in `022_submission_review_rpcs.sql` (atomic parent/child creation, two cross-referenced `resubmit` events), but **no `GRANT EXECUTE` was issued to any role** and `PUBLIC`'s default grant was explicitly `REVOKE`d — not even `service_role` can call it yet, so no API endpoint can be wired to it. Registry status remains `draft`, unchanged, until the separate invocation-authority decision (§7 item 5) lands. |
| `submission.convert_to_intake` (CMD000026) | needs `resulting_intake_packet_id` + disposition columns | ✅ | Full build — target (`operations.intake_packets`) is real and DEC000001-governed; §5.11 calls this the one canonical, ready-to-build FK. |
| `submission.route_to_identity_review` | needs `identity_review_item_id` (no-FK placeholder) | ❌ blocked | DEC000002 §5.11 itself states no Identity Review Queue table has been inspected in the live schema — it's a real Blueprint-governed destination but not yet an implemented entity. The column can be added now (nullable, no FK, per §1 above) but the RPC has nothing real to route to. **Not part of this migration's deliverable** — building the destination table is Restaurant Operations OS's own separate work, outside DEC000002's scope to originate. |
| `submission.escalate_exception` | needs `exception_request_id` (no-FK placeholder) | ❌ blocked | Same shape — Governance OS's exception-request entity is not confirmed to exist anywhere in scope. Column added, RPC not built here. |
| `submission.close_no_action` | — | — | Removed as a standalone command per §5.5 — folded into `.approve`'s completion logic; nothing to build separately. |

## 4. Role enforcement — no new gap beyond DEC000001's existing one

DEC000002 doesn't introduce a distinct role model for submissions — reviewing/claiming here is a "coordinator" action per migration 011's existing RLS (`operations.current_user_role() IN ('coordinator', 'admin')`), which already lines up with DEC000001's Governance Reviewer mapping recommendation (`reviewer`/`coordinator` treated as the reviewing role). No new role value needed; carrying forward the same mapping already flagged (not silently decided) in the DEC000001 gap map §4.

## 5. Not in scope for this pass (confirmed correctly excluded)

- `operations.partner_submissions` — explicitly out of scope (§7 item 9).
- Identity Review Queue table build — belongs to Restaurant Operations OS, referenced but not originated by this decision (§5.11).
- Governance OS exception-request entity — belongs to Governance OS, same treatment (§5.11).
- `resubmit`'s invocation-authority decision — explicitly deferred by DEC000002 itself (§5.7, §7 item 5); not decided here.
- API (FastAPI routers) and UI layer — sequenced after the migration + RPCs land, mirroring how Intake OS was built (schema/RPC migrations first, endpoints second).
- Task #46 (`commit_ingest`) and DEC000003 Track B — separate, already-sequenced work; untouched by this pass.

---

**Two flagged items — resolved by Founder ruling during the build, and now covered by the formal DEC000002 approval as well (originally posed below, kept for the record):**

1. **§2 — event-table downstream reference:** ruled **(b) metadata jsonb** — no four mirrored FK-shaped columns added to the events table. Built as ruled in `021_submission_state_machine.sql`.
2. **§3 `.resubmit` — sequencing:** ruled **build the RPC/mechanics now, withhold the API endpoint and invocation authority** — not held back entirely. Built as ruled in `022_submission_review_rpcs.sql`; `GRANT EXECUTE` deliberately not issued to any role. This withholding is independent of DEC000002's own 2026-07-18 approval — the invocation-authority carve-out (§7 item 5) is a permanent feature of the approved record, not a temporary pre-approval condition.

Everything else above (the FK-correction-style items — `resulting_intake_session_id` retyping, the two no-FK placeholder columns, `reviewed_by`/`resulting_evidence_summary` treatment) was a direct, unambiguous read of the approved v4.2 text and DEC000001 precedent, not a ruling request — built as originally described, matching `021_submission_state_machine.sql`.

**Remaining genuine gaps, unchanged by the 2026-07-18 approval** (approval formalized the policy and confirmed what's built; it did not itself build anything new): the command-handler layer for `.claim/.release/.return/.approve/.reject/.convert_to_intake` (§3 — schema/state-transition support exists in 021, but no RPCs beyond `.resubmit` exist yet); `.route_to_identity_review`/`.escalate_exception`, blocked on destination entities that don't exist elsewhere in the OS (§3, §5); the API and UI layers for all of the above (§5); execution of 021/022 against a live database (still outstanding — committed to the repo, not yet run); and the deferred `.resubmit` invocation-authority decision itself (§7 item 5, §5 above).

**New item surfaced while building 022, not previously flagged here:** `.resubmit`'s actor validation intentionally has **no role check at all** (unlike every other RPC precedent in `019_intake_edit_resubmit_reject_archive_rpcs.sql`, which all gate on a specific `operations.users.role`). DEC000002 §5.7 states plainly that "no actor category or role is defined for `resubmit` by this decision" — so `022`'s function only requires an active `operations.users` row, nothing more. This is not itself the deferred invocation-authority decision (§7 item 5) — when that decision lands, it may add a role check here that doesn't exist today. Flagging so this absence isn't later mistaken for "any active user was approved to resubmit."
