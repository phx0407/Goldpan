# DEC000001 — Canonical Intake Packet State Machine

**Status:** approved — Founder approved
**Approval date:** 2026-07-13
**Decision basis:** architectural_requirement, compliance_or_risk_control
**Decision dependencies:** none (foundational record)
**Registry impact:** governs `intake.packet.*` and `intake.review.*` namespace commands (see §3, §5.1)

**Revision note:** v4 is approved architecturally. v4.1 was a mechanical correction pass only — no lifecycle, command, role, or evidence-boundary decision was reopened. Four corrections: (1) the event model now distinguishes `actor_type` (`user`/`system`/`pipeline`) and `actor_id` rather than requiring a user ID on system-generated events, aligned with the Blueprint's existing lifecycle-event actor standard; (2) the single-hop supersession chain rule is backed by an explicit enforcement mechanism (partial unique constraint), not just a descriptive statement; (3) archival eligibility is stated as an explicit two-value allow-list (`rejected`, `ingested`) rather than the vaguer "resolved packet" language; (4) a document-wide reference and terminology consistency pass — every miscited section reference to the `rejected` definition (§3's command table and §5.2's payload-mutation table both pointed to §5.6, the supersession section, instead of §5.10) is corrected, both places `claim`/`release` permissions were cited (§3's command table and §4's role table) are extended to include §5.5 where `release` is actually defined, and the canonical six-status count is reverified. Sections 1, 2, and 4 carry forward from v4 unchanged; §3 has two corrected section references (noted inline); §5.6, §5.8, and §5.11 are amended in place; §6-§8 carry forward with the corresponding cross-references and validation criteria updated to match.

**Founder approval note:** approved subject to one non-substantive wording correction in §5.6's supersession section — the prior statement that canvass-date ties are broken by `submitted_at` is replaced with the precise structural basis for cycle-exclusion (every supersession link points from an earlier to a strictly later `canvass_date`, and the existing restaurant + canvass-date uniqueness rule already makes a tie-breaking rule unnecessary for the canonical chain). This is a wording correction only — it does not change §5.6's mechanism, the six canonical statuses, or any of the §7 Founder decisions, all of which are approved as drafted in v4.1.

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
| `intake.review.return` (CMD000006, implemented) | claimant-or-admin override added 2026-07-16 | Requires source state `in_review` **only** — `pending_review` and `approved` both excluded as valid sources (§5.9, carried from v3). Ordinary use is claimant-only; a Founder/CEO administrator-override is permitted with a non-blank reason, logged distinctly — corrected 2026-07-16 (Founder/CEO governance clarification), see §5.5. Not claimant-only without exception. |
| `intake.packet.mark_ingested` (CMD000007, implemented) | treatment carried from v3 | No longer an independent operator action under ordinary use. See §5.7. |
| `intake.packet.commit_ingest` (CMD000008, missing) | **becomes the sole path to `ingested`** | See §5.7. |
| `intake.packet.reject` (CMD000009, missing) | **adopted, with sharpened semantics** | See §5.10 (definition refined in v4; corrected reference this revision — was miscited to §5.6 in v4). |
| `intake.packet.reopen` (CMD000010, missing) | **remains reserved and undefined** | This revision does not give it meaning. See §5.1. |
| `intake.packet.archive` (CMD000011, missing) | unchanged in mechanism, tightened in policy | Sets `archived_at`. See §5.11 (carried from v3). |
| **New (renamed this revision):** `intake.packet.edit_payload` | not in registry today — Command Registry correction/addition requiring Founder approval | Replaces the v3 proposal `intake.packet.update`. Edits `packet_data` only, not packet metadata generally. See §5.1, §5.2. |
| **New:** `intake.packet.resubmit` | not in registry today — Command Registry correction/addition requiring Founder approval | Unchanged from v3. See §5.1. |
| **New:** `intake.review.claim`, `intake.review.release` | not in registry today | See §5.3-§5.5 (corrected this revision — release is defined in §5.5, not covered by the §5.3-§5.4 range alone). |

Every command marked "new" above is flagged as a distinct namespace/behavior decision requiring its own line-item approval in §7, not silently bundled into "adopt DEC000001."

## 4. Blueprint roles governing this record

| Role | Permitted actions under this decision |
|---|---|
| **Intake Specialist** | May invoke `intake.packet.edit_payload` and `intake.packet.resubmit`. Owns `packet_data` while a packet is `returned`. |
| **Governance Reviewer** | May claim, release, return, approve, or reject a packet according to permissions in §5.3-§5.5 and §5.9 (corrected this revision — was miscited to §5.3-§5.4 in v4, omitting §5.5 where release is defined). May add review notes, flags, and annotations. **May not mutate `packet_data` under any circumstance.** |

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
| `rejected` | Immutable | Terminal; no further edits of any kind. See §5.10 for the refined definition (corrected reference this revision — was miscited to §5.6 in v4). |

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
- **Authorization for `intake.review.return` and `intake.review.approve` (corrected 2026-07-16, per Founder/CEO governance clarification):** ordinary use of both decision commands is **claimant-only** — only the reviewer currently holding the claim may approve or return the packet. The Founder/CEO, in their capacity as the active operator of the company during GoldPan's early operating stage, may also perform or override either of these claimant-restricted operations — including `return`, which previously had no override path at all and is the one case this correction actually changes; `approve` already permitted an administrator override in the implementation this decision governs. An override by anyone other than the current claimant requires Administrator authority and a non-blank reason, and is logged distinctly from an ordinary self-action in the event history (§5.8). Do not read this bullet as granting unrestricted override authority to every future holder of an administrator-tier database role: the `admin` role is documented here as the **current implementation adapter** through which Founder/CEO authority happens to be exercised today, not as the permanent organizational authority model — GoldPan has no distinct Founder/CEO identity in its schema yet (see the corresponding note in migration 017's header). To keep the technical role and the organizational authority basis distinguishable in the audit trail itself, every event these commands write records **both**: `actor_role` (the actor's literal database role — `reviewer` or `admin`) and `authority_basis` (`governance_reviewer` for ordinary reviewer action, or `founder_ceo_override` for an action taken through the current admin adapter). This same `actor_role`/`authority_basis` pair is also written for `intake.review.claim` and `intake.review.release` (§5.4-§5.5 above), for consistency across all four claim/decision commands.

### 5.6 Supersession — system-derived, no routine human-facing command

Superseder determination uses **canonical restaurant identity and canvass chronology**, not ingestion order:

- **Identity:** two packets are compared for supersession only if they resolve to the same `restaurant_id` (preferred) or, if `restaurant_id` is null on either, the same `restaurant_external_id` — the canonical restaurant identity already used elsewhere in the schema (migration 015).
- **Chronology:** packet Q can supersede packet P only if `Q.canvass_date > P.canvass_date`, and both are `ingested`. Ingestion timestamp is not part of the comparison.
- **Determinism / single-hop chaining:** each packet's `superseded_by_packet_id` points to exactly one packet — its immediate chronological successor by canvass_date among `ingested` packets for the same restaurant identity. Full supersession history is reconstructed by walking the chain, not by fanning one packet out to all future ones.
- **Out-of-order ingestion:** the successor link is (re)computed at the moment any packet reaches `ingested`, in both directions, as described in v3 (unchanged mechanism).
- **Self-reference and cycles:** a `CHECK` constraint enforces `superseded_by_packet_id != packet_id`. Cycles are structurally excluded because every supersession link must point from an earlier `canvass_date` to a strictly later `canvass_date`. The existing uniqueness rule for restaurant and canvass date means a tie-breaking rule is not needed for the canonical supersession chain.

**Single-hop enforcement, made explicit this revision (mechanical correction — the rule itself is unchanged from v4, only its enforcement mechanism is now stated):**
- Each packet may point to **at most one** successor via `superseded_by_packet_id` — trivially true, since it is a single nullable column, not a set.
- Each packet may be referenced as the successor of **at most one** immediate predecessor — enforced via a **partial unique constraint**: `UNIQUE (superseded_by_packet_id) WHERE superseded_by_packet_id IS NOT NULL`. Without this constraint, nothing would stop two different predecessor packets from both pointing to the same successor, which would break the single-hop chain model.
- `superseded_by_packet_id` is null, or points to an `ingested` packet for the same canonical restaurant identity with a strictly later `canvass_date` — this referential-validity rule cannot be expressed as a simple `CHECK` constraint (it requires comparing two rows), so it is enforced by the recomputation logic described above and verified operationally per §8's validation criteria, not by a database constraint alone.
- Self-reference and cycles are prohibited, per the existing `CHECK` constraint and the canvass-chronology total order, respectively.

Together, the partial unique constraint and the single-column self-reference `CHECK` structurally guarantee at most one predecessor and at most one successor per packet — the rule was already stated in v4; this revision adds the concrete mechanism that actually enforces it.

**Explicitly stated (carried from v4, unchanged):** Supersession is a system-derived relationship based on canonical restaurant identity and canvass chronology. **No ordinary human-facing `supersede packet` command exists.** The system may recompute or repair the relationship through a restricted administrative reconciliation action, but manual supersession is not part of the routine Intake workflow. This decision does **not** add a routine `intake.packet.supersede` command, and none should be added to the registry as buildable without a separate Decision Record.

### 5.7 Ingestion status — system-controlled; `ingested` is a factual outcome, not a judgment

Per the Founder's instruction, carried from v3: `packet_status = ingested` may only be set after a successful durable evidence write through the governed `intake.packet.commit_ingest` workflow — never by an independent human action that merely flips a status flag.

`intake.packet.commit_ingest` performs the durable write and, only upon confirmed success, sets `packet_status = ingested` itself, atomically, as its own last step. `intake.packet.mark_ingested` (CMD000007) is **deprecated as an independent operator-facing action**. It may be retained only as a restricted, reason-required reconciliation tool for correcting drift between recorded status and actual evidence state — not as part of the ordinary workflow, and not usable by a Governance Reviewer as a substitute for `commit_ingest`.

**Stated explicitly this revision:** `ingested` is a factual system outcome — the record of a successful durable write — not a human judgment. No reviewer or operator action, on its own, can produce it.

### 5.8 Revisions vs. lifecycle events — two stores; event actors corrected to support system-generated events

Two append-only stores, unchanged in count and purpose from v4:

- **`operations.intake_packet_revisions`** — payload snapshots only. One row per payload-changing event (i.e., `intake.packet.edit_payload`, always human-initiated by an Intake Specialist — never system-generated). Columns: `revision_id`, `packet_id`, `prior_payload jsonb`, `actor_user_id`, `reason`, `created_at`. Unchanged this revision — `actor_user_id` remains correct here because payload edits are, by definition (§5.2, §4), always performed by an authorized human role, never by the system.
- **`operations.intake_packet_events`** — lifecycle/audit trail. One row per state-changing, claim-changing, or annotation event: `claim`, `release` (self or admin-override, with reason if override), `return`, `resubmit`, `approve`, `reject`, `ingest`, `archive`, `supersede`, `annotate`.

**Corrected this revision:** v4's `intake_packet_events` required an `actor_user_id` on every row, which does not fit events that are system- or pipeline-derived rather than human-initiated — `ingest` (set by `commit_ingest`'s own success branch, §5.7), `supersede` (system-computed, §5.6), automated `archive` (if a policy-driven schedule is ever adopted, §5.11 — none is approved by this decision), and any restricted reconciliation operation. Requiring a human user ID on these events was a modeling gap, not a deliberate policy choice, and conflicted with the Blueprint's own lifecycle-event standard, which already distinguishes user, system, and pipeline actors. Corrected columns:

```text
event_id
packet_id
event_type
actor_type:   user | system | pipeline
actor_id:     stable user ID (actor_type = user) |
              service-account ID or system actor identifier (actor_type = system) |
              pipeline name or pipeline-run identifier (actor_type = pipeline)
reason        (nullable; required for override/return/reject)
metadata jsonb
created_at
```

`claim`, `release`, `return`, `resubmit`, `approve`, `reject`, and `annotate` are always `actor_type = user` — these remain human-only actions per §4 and §5.2, unchanged. `ingest` and `supersede` are `actor_type = system` (or `pipeline`, if the durable-write or recompute step is itself attributed to a named pipeline run rather than a generic system actor) under ordinary operation. This does not weaken §5.7's rule that `ingested` is a factual system outcome — it corrects how that system-initiated event is recorded, not who or what may cause it.

**Human-only live ownership fields are unaffected by this correction and remain exactly as in v4:** `claimed_by_user_id` (§5.3) and `archived_by_user_id`, when archival is manual (§5.11) — both stay user-ID-only, since claiming and manual archival are, by definition, human actions. The `actor_type`/`actor_id` correction applies to the `intake_packet_events` audit trail only, not to these packet-row ownership columns.

**Clarified (carried from v4, unchanged):** where `intake.packet.edit_payload` both updates `packet_data` on the packet row and inserts a row into `intake_packet_revisions`, these two writes must occur in one transaction where practical, so a payload change is never recorded without its corresponding revision snapshot, or vice versa.

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

### 5.11 Archival — eligibility stated as an explicit allow-list

**Corrected this revision:** v4 described archival as removing "a resolved packet" from default views without stating precisely which statuses qualify as resolved. Replaced with an explicit rule:

**Eligible for archival:**
- `rejected`
- `ingested`

**Not eligible for archival:**
- `pending_review`
- `in_review`
- `returned`
- `approved`

Archival must never hide unfinished work or an approved packet whose ingestion has not yet completed — an `approved` packet is not archivable until it reaches `ingested` via `commit_ingest` (§5.7); there is no path from `approved` directly to archived.

**Retained, unchanged from v4:**
- Archival is a non-status attribute, not a `packet_status` value.
- No automatic archival schedule is approved by this decision — archival may be manual or, if a policy-driven schedule is adopted later, system-initiated (in which case the corresponding event, per §5.8, is recorded with `actor_type = system`).
- Manual archival requires an authorized actor (`archived_by_user_id`, stable ID only, per §5.3 and §5.8) and a reason.
- Archival never changes the packet's processing outcome, deletes its payload, or deletes its event/revision history.

## 6. Recommended canonical model (final, v4.1)

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

No `_display_name` field exists on any of these. Six `packet_status` values total, reverified this revision: `pending_review`, `in_review`, `returned`, `approved`, `rejected`, `ingested`. `draft` remains excluded, per v2's finding, not revisited here.

**Append-only stores:** `intake_packet_revisions` (payload snapshots, `edit_payload` events only — keyed to stable `actor_user_id`, always human, per §5.8) and `intake_packet_events` (full lifecycle, claim, and annotation event log — keyed to `actor_type` + `actor_id` to support human, system, and pipeline actors, per §5.8's correction this revision).

**Archival eligibility (reverified this revision, §5.11):** eligible only from `rejected` or `ingested`; not eligible from `pending_review`, `in_review`, `returned`, or `approved`.

## 7. Founder decisions — approved 2026-07-13 (all six items below approved as drafted; no item reopened by the §5.6 wording correction)

1. **Approve the six canonical statuses:** `pending_review`, `in_review`, `returned`, `approved`, `rejected`, `ingested`.
2. **Approve the discrete command model:** `intake.packet.edit_payload`, `intake.packet.resubmit`, `intake.review.claim`, `intake.review.release`, the existing `intake.review.approve`/`intake.review.return` commands (tightened per §5.9), `intake.packet.reject`, and `intake.packet.commit_ingest` as the sole ordinary path to `ingested`.
3. **Approve reserving `intake.packet.reopen` (CMD000010) for a future exceptional, restricted workflow** — undefined and unbuilt by this decision.
4. **Approve `superseded_by_packet_id` and `archived_at` as non-status attributes/relationships**, not statuses.
5. **Approve the role boundary that Governance Reviewers do not edit Intake evidence** — only an Intake Specialist may call `intake.packet.edit_payload`, per §4 and §5.2.
6. **Stable user identity — approved rule vs. deferred dependency:**
   - **Approved architectural rule** (already established via §5.3, §5.8): every `*_user_id` field (`claimed_by_user_id`, `archived_by_user_id`, `actor_user_id`, and `actor_id` when `actor_type = user`) must reference a stable user identifier, never a display-name snapshot.
   - **Deferred implementation dependency** (not yet resolved): the exact canonical user/auth table that `*_user_id` resolves to is unconfirmed — this decision assumes such a table exists but does not have visibility into its exact shape from the files inspected. This must be confirmed, by inspecting the current authentication/user schema, before implementing any command that writes a `*_user_id` field.

## 8. Risks, guardrails, validation criteria, revisit triggers

**Risks:**
- Supersession's out-of-order-ingestion recomputation (§5.6) touches more than one row per ingestion event — should be implemented as a single transaction to avoid a partially-updated chain if it fails midway.
- Folding `mark_ingested` into `commit_ingest` (§5.7) removes a currently-working manual override; the restricted reconciliation-tool fallback must exist before the old path is removed.
- Removing display-name snapshots (§5.3, §5.8) means every UI surface showing claim/actor identity must perform a user-directory lookup at render time; any surface that assumed a stored display-name column needs to be identified before implementation.
- Introducing `actor_type`/`actor_id` (§5.8, new this revision) means any existing code or mockup that assumed a single `actor_user_id` column on `intake_packet_events` must be updated before implementation; this is a pre-implementation correction, not a live migration risk, since no code has been built against this record yet.

**Guardrails:**
- No implementation proceeds until Founder decisions 1-5 above are made, together with item 6's approved architectural rule. Any command implementation that writes a `*_user_id` field must additionally wait for item 6's deferred implementation dependency (confirmation of the canonical user/auth table) to be resolved.
- `intake.packet.edit_payload` must refuse to run unless `packet_status = returned` **and** the caller holds the Intake Specialist role, per §5.2's mutation-rights table and §4's role table exactly.
- No command in the `intake.review.*` namespace may write to `packet_data`, per §5.2.
- Every row written to `intake_packet_events` must set both `actor_type` and `actor_id` — no row may carry a null `actor_type`, per §5.8.
- `intake.packet.archive`, when called manually, must refuse to run unless `packet_status ∈ {rejected, ingested}`, per §5.11's explicit allow-list.

**Validation criteria:**
- The claim `UPDATE ... WHERE ... RETURNING` pattern in §5.4 is used verbatim (or an equivalent single-statement conditional mutation) — no read-then-write claim implementation is acceptable.
- Every packet's supersession chain (if any) resolves to exactly one predecessor and one successor at most, with no cycles, verifiable by a simple recursive query, and the partial unique constraint on `superseded_by_packet_id` (§5.6) exists in the schema.
- No code path sets `packet_status = ingested` except `commit_ingest`'s own success branch, and that event is recorded with `actor_type = system` (or `pipeline`), not `actor_type = user`.
- No table in this record contains a `_display_name` column.
- No archived packet has `packet_status` outside `{rejected, ingested}`.

**Revisit triggers:**
- If a real need for reversing an approved packet emerges, that becomes its own Decision Record (per §5.9), not a reopening of this one.
- If the admin-only reconciliation fallback for `mark_ingested` is used with any regularity, that is itself a signal worth investigating.
- If a routine need for manual supersession correction emerges beyond the restricted reconciliation action in §5.6, that is a signal to revisit this decision, not to quietly add a routine command.
