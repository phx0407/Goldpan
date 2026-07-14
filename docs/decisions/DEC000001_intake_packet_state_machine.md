# DEC000001 — Canonical Intake Packet State Machine

**Status:** draft v4 — ready for Founder approval (final targeted refinements to v3)
**Decision basis:** architectural_requirement, compliance_or_risk_control
**Decision dependencies:** none (foundational record)
**Registry impact:** governs `intake.packet.*` and `intake.review.*` namespace commands (see §3, §5.1)

**Revision note:** v3 is approved in direction. This revision makes eleven targeted refinements only — no candidate analysis is reopened and no new architecture is introduced except where required to resolve a direct contradiction: removing display-name snapshots from all actor fields (stable ID only), renaming `intake.packet.update` to `intake.packet.edit_payload` for precision, adding an explicit reviewer/submitter ownership boundary keyed to Blueprint roles, reinforcing that annotations are not payload mutations, stating that supersession is system-derived with no routine human-facing command, sharpening the definition of `rejected` with examples, and restating ingestion as a factual system outcome. Sections 1-3 carry forward from v3 with the command rename applied; §5 onward is revised.

---

## 1. Competing versions, side by side (unchanged from v3)

| Source | States (in order) | Notes |
|---|---|---|
| Blueprint §5b | `draft → in_progress → pending_review → in_review → approved → rejected → archived` | Generic table, not intake-packet-specific. |
| Blueprint §5i | `draft → submitted → in_review → returned → approved → ingested → superseded → archived` | Entity-specific. Trust threshold = `approved`. |
| Live DB (`015_intake_packets.sql`) | `pending_review, returned, approved, ingested` | 4 states. |
| Live API (`intake.py`) | `submit_packet()` → `pending_review`; `approve_packet()` blocks if `ingested`; `return_packet()` blocks if `ingested`, allows from `pending_review` **or** `approved`; `mark_ingested()` only from `approved` | The `approved → returned` path is addressed and closed in §5.9 (carried from v3, unchanged in v4). |

## 2. Terminology and transition conflicts (unchanged from v3)

Carried forward without change: `draft` present in both Blueprint versions, absent from DB; `submitted`/`pending_review` naming split; `in_review` present in both Blueprint versions with no DB/API representation; `rejected` (§5b) vs `returned` (§5i/DB/API) conceptually distinct; `ingested`/`superseded` only in §5i/DB; `archived` in both Blueprint versions, absent from DB/API.

## 3. Phase 5 commands that depend on this decision (command rename applied)

| Command | Registry status | This revision's treatment |
|---|---|---|
| `intake.packet.submit` (CMD000003, implemented) | unchanged | Sets initial status; no change. |
| `intake.review.approve` (CMD000005, implemented) | unchanged | Requires source state `in_review`, claimant-or-admin only. See §5.9 (carried from v3). |
| `intake.review.return` (CMD000006, implemented) | unchanged | Requires source state `in_review` **only** — `pending_review` and `approved` both excluded as valid sources. See §5.9 (carried from v3). |
| `intake.packet.mark_ingested` (CMD000007, implemented) | treatment carried from v3 | No longer an independent operator action under ordinary use. See §5.7. |
| `intake.packet.commit_ingest` (CMD000008, missing) | **becomes the sole path to `ingested`** | See §5.7. |
| `intake.packet.reject` (CMD000009, missing) | **adopted, with sharpened semantics** | See §5.6 (definition refined this revision). |
| `intake.packet.reopen` (CMD000010, missing) | **remains reserved and undefined** | This revision does not give it meaning. See §5.1, §5.5. |
| `intake.packet.archive` (CMD000011, missing) | unchanged in mechanism, tightened in policy | Sets `archived_at`. See §5.11 (carried from v3). |
| **New (renamed this revision):** `intake.packet.edit_payload` | not in registry today — Command Registry correction/addition requiring Founder approval | Replaces the v3 proposal `intake.packet.update`. Edits `packet_data` only, not packet metadata generally. See §5.1, §5.2. |
| **New:** `intake.packet.resubmit` | not in registry today — Command Registry correction/addition requiring Founder approval | Unchanged from v3. See §5.1. |
| **New:** `intake.review.claim`, `intake.review.release` | not in registry today | See §5.3-§5.4. |

Every command marked "new" above is flagged as a distinct namespace/behavior decision requiring its own line-item approval in §7, not silently bundled into "adopt DEC000001."

## 4. Blueprint roles governing this record

| Role | Permitted actions under this decision |
|---|---|
| **Intake Specialist** | May invoke `intake.packet.edit_payload` and `intake.packet.resubmit`. Owns `packet_data` while a packet is `returned`. |
| **Governance Reviewer** | May claim, release, return, approve, or reject a packet according to permissions in §5.3-§5.4 and §5.9. May add review notes, flags, and annotations. **May not mutate `packet_data` under any circumstance.** |

This decision uses these two existing Blueprint roles throughout and does not introduce a vague label such as "operator" where a defined role already applies.

## 5. Resolution of each targeted correction

### 5.1 Correction is not resubmission — `reopen` is not repurposed; the payload-edit command is renamed for precision

`intake.packet.reopen` (CMD000010) is not repurposed as the routine return-and-fix mechanism — that assumption, originally made in v2, remains withdrawn. "Reopen" describes something rarer: reactivating a packet already in a terminal or closed state (`ingested`, `rejected`, `archived`) for an exceptional, elevated correction — not the regular loop a reviewer performs.

**Two distinct commands, neither of which is `reopen`:**

- **`intake.packet.edit_payload`** (renamed this revision from `intake.packet.update` — the command changes `packet_data` specifically, not packet metadata generally) — edits `packet_data` while `packet_status = returned` only. Does not change `packet_status`. Writes a payload revision record (§5.8) capturing the prior payload, actor, reason, timestamp. **Restricted to the Intake Specialist role (§4).**
- **`intake.packet.resubmit`** — transitions `returned → pending_review`. Does not touch `packet_data`. Kept as a separate command from `edit_payload` so a payload edit can be saved without immediately re-queuing, and so the event log distinguishes "what changed" from "state moved." **Restricted to the Intake Specialist role (§4).**
- **`intake.packet.reopen`** — remains reserved and undefined by this decision, for a future exceptional reopening of a packet in a terminal/closed state. Not built as part of this decision. CMD000010's existing registry entry needs its own definition written before it can be marked buildable.

Both `edit_payload` and `resubmit` are flagged explicitly as Command Registry corrections/additions requiring their own Founder line-item approval (§7 item 2) — this decision recommends them but does not treat that recommendation as self-executing registry authority.

### 5.2 Payload mutation rights, with the reviewer/submitter boundary and annotation carve-out made explicit

**Governing rule:** Governance Reviewers do not correct Intake evidence. Reviewers identify issues, record reasoning, and return packets for correction. Only an authorized Intake Specialist may edit a returned packet's payload.

| `packet_status` | Payload (`packet_data`) | Notes |
|---|---|---|
| `pending_review` | Read-only | No command may alter payload in this state. |
| `in_review` | Read-only | Governance Reviewer annotations (notes, flags) are stored separately from `packet_data` — see reinforcement below. |
| `returned` | **Mutable, via `intake.packet.edit_payload` only, Intake Specialist role only** | Every edit produces a revision record (§5.8). A Governance Reviewer cannot call this command regardless of packet state. |
| `approved` | Immutable | No command may alter payload once approved. |
| `ingested` | Immutable | Permanent audit record, per Blueprint §5i. |
| `rejected` | Immutable | Terminal; no further edits of any kind. See §5.6 for the refined definition. |

**Reinforcement:** Review notes, review flags, assignments, and annotations are stored independently from `packet_data` and are not payload mutations. A Governance Reviewer's annotation activity never appears in `intake_packet_revisions` (§5.8) — only in `intake_packet_events`, as event metadata.

Any future command touching `packet_data` must be checked against this table, and against the role boundary in §4, before being added to the registry as buildable.

### 5.3 Claim identity — stable reference only, no display-name snapshot

v3 specified `claimed_by_user_id` plus an optional `claimed_by_display_name` snapshot. **The display-name snapshot is removed in this revision.** The canonical claim model carries only:

- `claimed_by_user_id` — a stable reference into whatever the current authentication/user model resolves to (e.g., a Supabase `auth.users` id or the operations-role user table already implied by `operations.current_user_role()` in the submissions migrations).
- `claimed_at`

Display names are resolved from the user directory at render time, not stored redundantly on the packet row. This decision does not have visibility into the exact current user/session model from the files inspected so far, and confirming the correct reference target remains a Founder/implementation question (§7 item 6), unchanged from v3.

**This same principle applies to every other actor field in this record** — release-override actor, reviewer-of-record in event history, archival actor — none of them carry a display-name snapshot; all resolve to a stable user ID only, with display names looked up at render time. This supersedes every place v3 mentioned a `_display_name` field.

### 5.4 Atomic claim — unchanged mechanism, display-name field removed from the statement

**The claim must be implemented as a single conditional update, not a read followed by a write:**

```sql
UPDATE operations.intake_packets
SET packet_status = 'in_review',
    claimed_by_user_id = :acting_user_id,
    claimed_at = now()
WHERE packet_id = :packet_id
  AND packet_status = 'pending_review'
  AND claimed_by_user_id IS NULL
RETURNING packet_id;
```

If this returns no row, the claim failed — either another reviewer already claimed it or the packet is no longer `pending_review` — and the caller is told exactly that, not given a false success.

### 5.5 Release and claim-clearing — tightened, designed against the future role model

- **`claim`**: `pending_review → in_review`, per §5.4.
- **`release`** (`intake.review.release`): `in_review → pending_review`, clears `claimed_by_user_id`/`claimed_at`. Allowed by the current claimant. An administrator override is also allowed, but **requires a reason**, logged to the event history (§5.8) distinctly from an ordinary self-release. This permission is designed against the Blueprint's future role model (any role authorized for administrative override of a claim), not hard-coded to the current admin-only implementation, so it does not need to be re-decided when the role model matures.
- **Decision commands clear the claim atomically as part of the same transition, not as a separate step:** `intake.review.return`, `intake.review.approve`, and `intake.packet.reject` each, in one operation, transition `packet_status` out of `in_review` **and** clear the claim fields **and** write the reviewer identity (stable user ID, per §5.3) into the append-only decision/event history — so the reviewer of record is never lost even though the live `claimed_by_user_id` field is cleared once the decision is made. The claim fields describe "who currently has this checked out," not "who last acted on it"; the latter lives permanently in the event log.

### 5.6 Supersession — system-derived, no routine human-facing command

Superseder determination uses **canonical restaurant identity and canvass chronology**, not ingestion order:

- **Identity:** two packets are compared for supersession only if they resolve to the same `restaurant_id` (preferred) or, if `restaurant_id` is null on either, the same `restaurant_external_id` — the canonical restaurant identity already used elsewhere in the schema (migration 015).
- **Chronology:** packet Q can supersede packet P only if `Q.canvass_date > P.canvass_date`, and both are `ingested`. Ingestion timestamp is not part of the comparison.
- **Determinism / single-hop chaining:** each packet's `superseded_by_packet_id` points to exactly one packet — its immediate chronological successor by canvass_date among `ingested` packets for the same restaurant identity. Full supersession history is reconstructed by walking the chain, not by fanning one packet out to all future ones.
- **Out-of-order ingestion:** the successor link is (re)computed at the moment any packet reaches `ingested`, in both directions, as described in v3 (unchanged mechanism).
- **Self-reference and cycles:** a `CHECK` constraint enforces `superseded_by_packet_id != packet_id`. Cycles are structurally excluded because canvass_date supplies a strict total order (ties broken by `submitted_at`).

**Explicitly stated this revision:** Supersession is a system-derived relationship based on canonical restaurant identity and canvass chronology. **No ordinary human-facing `supersede packet` command exists.** The system may recompute or repair the relationship through a restricted administrative reconciliation action, but manual supersession is not part of the routine Intake workflow. This decision does **not** add a routine `intake.packet.supersede` command, and none should be added to the registry as buildable without a separate Decision Record.

### 5.7 Ingestion status — system-controlled; `ingested` is a factual outcome, not a judgment

Per the Founder's instruction, carried from v3: `packet_status = ingested` may only be set after a successful durable evidence write through the governed `intake.packet.commit_ingest` workflow — never by an independent human action that merely flips a status flag.

`intake.packet.commit_ingest` performs the durable write and, only upon confirmed success, sets `packet_status = ingested` itself, atomically, as its own last step. `intake.packet.mark_ingested` (CMD000007) is **deprecated as an independent operator-facing action**. It may be retained only as a restricted, reason-required reconciliation tool for correcting drift between recorded status and actual evidence state — not as part of the ordinary workflow, and not usable by a Governance Reviewer as a substitute for `commit_ingest`.

**Stated explicitly this revision:** `ingested` is a factual system outcome — the record of a successful durable write — not a human judgment. No reviewer or operator action, on its own, can produce it.

### 5.8 Revisions vs. lifecycle events — two stores, actor fields use stable IDs only

Two append-only stores, unchanged in structure from v3, with the display-name column removed:

- **`operations.intake_packet_revisions`** — payload snapshots only. One row per payload-changing event (i.e., `intake.packet.edit_payload`). Columns: `revision_id`, `packet_id`, `prior_payload jsonb`, `actor_user_id`, `reason`, `created_at`.
- **`operations.intake_packet_events`** — lifecycle/audit trail. One row per state-changing, claim-changing, or annotation event: `claim`, `release` (self or admin-override, with reason if override), `return`, `resubmit`, `approve`, `reject`, `ingest`, `archive`, `supersede`, `annotate`. Columns: `event_id`, `packet_id`, `event_type`, `actor_user_id`, `reason` (nullable, required for override/return/reject), `metadata jsonb`, `created_at`.

All actor columns in both tables are stable user IDs only — no display-name snapshot column exists in either table, consistent with §5.3.

**Clarified this revision:** where `intake.packet.edit_payload` both updates `packet_data` on the packet row and inserts a row into `intake_packet_revisions`, these two writes must occur in one transaction where practical, so a payload change is never recorded without its corresponding revision snapshot, or vice versa.

### 5.9 `approved → returned` — closed (unchanged from v3)

`intake.review.return` is restricted to `in_review → returned` only — `pending_review` and `approved` are both excluded as valid source states, per §5.5's rule that decisions are made from `in_review`, requiring a claim first. A genuine need to reverse an already-approved packet must be proposed as its own, separately governed, elevated action — not folded back into ordinary `return`.

### 5.10 `rejected` — definition sharpened

**Refined definition:** `rejected` is a terminal review determination that the record is fundamentally invalid or inappropriate as an Intake Packet, and therefore must not enter the evidence-ingestion path.

**Examples** (illustrative, not exhaustive): wrong restaurant; duplicate or test packet; unsupported or unusable source package; policy-invalid submission; packet created in error.

This is distinct from `returned`, which is a correctable packet that may re-enter review after a fix. No amount of payload correction turns a rejected packet into a valid one — that is what makes it terminal rather than a data-quality problem.

**Mechanism (unchanged from v3):**
- `in_review → rejected` only — same precondition as approve/return (must be claimed).
- Reason is mandatory, not optional.
- Requires an explicit confirmation step in the UI, distinct from an ordinary return, given its terminality.
- Logged to `intake_packet_events` (§5.8) with full reason.
- Payload immutable; no ingestion possible.
- Reopening a rejected packet is not part of ordinary workflow — exceptional reopening only through a future restricted command and a separate Decision Record, not through this one.

### 5.11 Archival — policy clarified, not prescribed (unchanged from v3)

Archival removes a resolved packet from default operational views but never deletes it or changes its processing outcome. Archival may be manual or policy-driven. No automatic archival schedule is approved by this decision. `archived_at` (nullable) is the mechanism, with `archived_by_user_id` (stable ID, no display-name snapshot, per §5.3) recorded when archival is manual. When and by what policy archival happens is deliberately left open, to be decided operationally later.

## 6. Recommended canonical model (final, v4)

```text
pending_review
    ↓ claim
in_review
    ├── release → pending_review
    ├── return → returned
    │              ├── edit_payload
    │              │      status remains returned
    │              └── resubmit → pending_review
    ├── reject → rejected
    └── approve → approved
                     ↓ successful commit_ingest
                  ingested
```

`intake.packet.edit_payload` does not count as a state transition — `packet_status` remains `returned` throughout an edit; only `resubmit` moves the packet back to `pending_review`.

**Attributes and relationships, not statuses:**

```text
claimed_by_user_id
claimed_at

superseded_by_packet_id
archived_at
```

No `_display_name` field exists on any of these. Six `packet_status` values total: `pending_review`, `in_review`, `returned`, `approved`, `rejected`, `ingested`. `draft` remains excluded, per v2's finding, not revisited here.

**Append-only stores:** `intake_packet_revisions` (payload snapshots, `edit_payload` events only) and `intake_packet_events` (full lifecycle, claim, and annotation event log) — both keyed to stable `actor_user_id`, per §5.8.

## 7. Founder decisions required (final — policy choices only)

1. **Approve the six canonical statuses:** `pending_review`, `in_review`, `returned`, `approved`, `rejected`, `ingested`.
2. **Approve the discrete command model:** `intake.packet.edit_payload`, `intake.packet.resubmit`, `intake.review.claim`, `intake.review.release`, the existing `intake.review.approve`/`intake.review.return` commands (tightened per §5.9), `intake.packet.reject`, and `intake.packet.commit_ingest` as the sole ordinary path to `ingested`.
3. **Approve reserving `intake.packet.reopen` (CMD000010) for a future exceptional, restricted workflow** — undefined and unbuilt by this decision.
4. **Approve `superseded_by_packet_id` and `archived_at` as non-status attributes/relationships**, not statuses.
5. **Approve the role boundary that Governance Reviewers do not edit Intake evidence** — only an Intake Specialist may call `intake.packet.edit_payload`, per §4 and §5.2.
6. **Confirm the exact source of stable user identity** (`*_user_id`'s reference target) once the current authentication/user schema is inspected — this decision assumes such a model exists but does not have visibility into its exact shape from the files inspected.

## 8. Risks, guardrails, validation criteria, revisit triggers

**Risks:**
- Supersession's out-of-order-ingestion recomputation (§5.6) touches more than one row per ingestion event — should be implemented as a single transaction to avoid a partially-updated chain if it fails midway.
- Folding `mark_ingested` into `commit_ingest` (§5.7) removes a currently-working manual override; the restricted reconciliation-tool fallback must exist before the old path is removed.
- Removing display-name snapshots (§5.3, §5.8) means every UI surface showing claim/actor identity must perform a user-directory lookup at render time; any surface that assumed a stored display-name column needs to be identified before implementation.

**Guardrails:**
- No implementation proceeds until Founder decisions 1-6 above are made.
- `intake.packet.edit_payload` must refuse to run unless `packet_status = returned` **and** the caller holds the Intake Specialist role, per §5.2's mutation-rights table and §4's role table exactly.
- No command in the `intake.review.*` namespace may write to `packet_data`, per §5.2.

**Validation criteria:**
- The claim `UPDATE ... WHERE ... RETURNING` pattern in §5.4 is used verbatim (or an equivalent single-statement conditional mutation) — no read-then-write claim implementation is acceptable.
- Every packet's supersession chain (if any) resolves to exactly one predecessor and one successor at most, with no cycles, verifiable by a simple recursive query.
- No code path sets `packet_status = ingested` except `commit_ingest`'s own success branch.
- No table in this record contains a `_display_name` column.

**Revisit triggers:**
- If a real need for reversing an approved packet emerges, that becomes its own Decision Record (per §5.9), not a reopening of this one.
- If the admin-only reconciliation fallback for `mark_ingested` is used with any regularity, that is itself a signal worth investigating.
- If a routine need for manual supersession correction emerges beyond the restricted reconciliation action in §5.6, that is a signal to revisit this decision, not to quietly add a routine command.
