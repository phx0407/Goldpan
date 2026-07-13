# DEC000001 — Canonical Intake Packet State Machine

**Status:** draft v3 — awaiting Founder approval (revised per targeted Founder corrections to v2)
**Decision basis:** architectural_requirement, compliance_or_risk_control
**Decision dependencies:** none (foundational record)
**Registry impact:** governs `intake.packet.*` and `intake.review.*` namespace commands (see §3, §5.1)

**Revision note:** v2's broader candidate analysis (§4, Candidates D/E/F) is not reopened here, per instruction. This revision makes eleven targeted corrections within that already-approved-in-principle direction: separating payload correction from resubmission, defining payload mutation rights explicitly, hardening the claim mechanism (stable identity, atomic operation, defined release rules), making supersession deterministic, making ingestion system-controlled, splitting revisions from lifecycle events, clarifying archival policy, defining `rejected` on its own operational merits, and closing `approved → returned`. Sections 1-3 carry forward from v2 with corrections noted inline; §5 onward is rewritten.

---

## 1. Competing versions, side by side (unchanged from v2)

| Source | States (in order) | Notes |
|---|---|---|
| Blueprint §5b | `draft → in_progress → pending_review → in_review → approved → rejected → archived` | Generic table, not intake-packet-specific. |
| Blueprint §5i | `draft → submitted → in_review → returned → approved → ingested → superseded → archived` | Entity-specific. Trust threshold = `approved`. |
| Live DB (`015_intake_packets.sql`) | `pending_review, returned, approved, ingested` | 4 states. |
| Live API (`intake.py`) | `submit_packet()` → `pending_review`; `approve_packet()` blocks if `ingested`; `return_packet()` blocks if `ingested`, allows from `pending_review` **or** `approved`; `mark_ingested()` only from `approved` | The `approved → returned` path is addressed and closed in §5.9 below. |

## 2. Terminology and transition conflicts (unchanged from v2)

Carried forward without change: `draft` present in both Blueprint versions, absent from DB; `submitted`/`pending_review` naming split; `in_review` present in both Blueprint versions with no DB/API representation; `rejected` (§5b) vs `returned` (§5i/DB/API) conceptually distinct; `ingested`/`superseded` only in §5i/DB; `archived` in both Blueprint versions, absent from DB/API.

## 3. Phase 5 commands that depend on this decision (corrected)

| Command | Registry status | This revision's treatment |
|---|---|---|
| `intake.packet.submit` (CMD000003, implemented) | unchanged | Sets initial status; no change. |
| `intake.review.approve` (CMD000005, implemented) | unchanged | Now requires source state `in_review`, claimant-or-admin only. See §5.9. |
| `intake.review.return` (CMD000006, implemented) | unchanged | Now requires source state `in_review` **only** — `pending_review` and `approved` both removed as valid sources. See §5.9. |
| `intake.packet.mark_ingested` (CMD000007, implemented) | **treatment revised** | No longer an independent operator action under ordinary use. See §5.7. |
| `intake.packet.commit_ingest` (CMD000008, missing) | **becomes the sole path to `ingested`** | See §5.7. |
| `intake.packet.reject` (CMD000009, missing) | **adopted, with defined semantics** | See §5.10 — no longer left open; justified on its own operational grounds, not because the placeholder exists. |
| `intake.packet.reopen` (CMD000010, missing) | **correction required — this revision does not treat its existing label as governing** | v2 assumed this placeholder was the natural home for resubmission. That assumption is withdrawn. See §5.1. |
| `intake.packet.archive` (CMD000011, missing) | unchanged in mechanism, tightened in policy | Sets `archived_at`. See §5.11. |
| **New:** `intake.packet.update` | not in registry today | New command, proposed. See §5.1. |
| **New:** `intake.packet.resubmit` | not in registry today | New command, proposed. See §5.1. |
| **New:** `intake.review.claim`, `intake.review.release` | not in registry today | See §5.3-§5.5. |

Every command marked "new" or "treatment revised" above is flagged as a distinct namespace/behavior decision requiring its own line-item approval in §10, not silently bundled into "adopt DEC000001."

## 5. Resolution of each targeted correction

### 5.1 Correction is not resubmission — `reopen` is not repurposed

v2's error: it treated `intake.packet.reopen` (CMD000010) as the natural home for "correct the payload and send it back to the queue" solely because the placeholder already existed with that name. On reflection, "reopen" more naturally describes something different and rarer — reactivating a packet that is already in a terminal or closed state (`ingested`, `rejected`, or `archived`) for an exceptional, elevated correction, not the routine return-and-fix loop a reviewer performs regularly.

**Revised recommendation:** two distinct commands, neither of which is `reopen`:

- **`intake.packet.update`** — edits `packet_data` while `packet_status = returned` only. Does not change `packet_status`. Writes a payload revision record (§5.8) capturing the prior payload, actor, reason, timestamp.
- **`intake.packet.resubmit`** — transitions `returned → pending_review`. Does not touch `packet_data`. Requires that the packet is not mid-edit (no specific lock needed, since `update` and `resubmit` are typically called in sequence by the same operator, but they remain separate operations so a payload edit can be saved without immediately re-queuing, and so the event log distinguishes "what changed" from "state moved").
- **`intake.packet.reopen`** — reserved, undefined by this decision, for a future exceptional reopening of a packet in a terminal/closed state (`ingested`, `rejected`, `archived`). Not built as part of this decision. The Command Registry's existing CMD000010 entry needs its own definition written before it can be marked buildable — this decision explicitly does not supply that definition, and flags CMD000010 as requiring correction/clarification rather than adopting its current bare label as authoritative.

This is a genuinely new pair of commands, not a renaming of anything existing — flagged for separate Founder sign-off in §10.

### 5.2 Payload mutation rights (new — not present in v2)

| `packet_status` | Payload (`packet_data`) | Notes |
|---|---|---|
| `pending_review` | Read-only | No command may alter payload in this state. |
| `in_review` | Read-only | Reviewer annotations (notes, flags) are stored separately from `packet_data` — they are not payload mutations. |
| `returned` | **Mutable, via `intake.packet.update` only** | Only an authorized Intake operator; every edit produces a revision record (§5.8). |
| `approved` | Immutable | No command may alter payload once approved. |
| `ingested` | Immutable | Permanent audit record, per Blueprint §5i. |
| `rejected` (if adopted, §5.10) | Immutable | Terminal; no further edits of any kind. |

Any future command touching `packet_data` must be checked against this table before being added to the registry as buildable.

### 5.3 Claim identity — stable reference, not free text

v2 specified `claimed_by text`. Revised: **`claimed_by_user_id`** (a stable reference into whatever the current authentication/user model resolves to — e.g., a Supabase `auth.users` id or the operations-role user table already implied by `operations.current_user_role()` in the submissions migrations), plus an optional **`claimed_by_display_name`** snapshot for display purposes only (not authoritative — if a user's display name changes later, historical claim records don't need to be rewritten). Free text is not acceptable as the actor-of-record for a claim; this decision does not have visibility into the exact current user/session model from the files inspected so far, and flags confirming the correct reference target as a Founder/implementation question rather than assuming one.

### 5.4 Atomic claim — corrected characterization

v2 described the claim guard as "check-then-set... a narrow race window." That characterization is withdrawn as imprecise. **The claim must be implemented as a single conditional update, not a read followed by a write:**

```sql
UPDATE operations.intake_packets
SET packet_status = 'in_review',
    claimed_by_user_id = :acting_user_id,
    claimed_by_display_name = :acting_user_display_name,
    claimed_at = now()
WHERE packet_id = :packet_id
  AND packet_status = 'pending_review'
  AND claimed_by_user_id IS NULL
RETURNING packet_id;
```

If this returns no row, the claim failed — either another reviewer already claimed it or the packet is no longer `pending_review` — and the caller is told exactly that, not given a false success. Implemented this way, there is no race window to characterize as a risk; the risk section in v2 attributing this to inherent check-then-set behavior was a modeling error, not a real property of the recommended design.

### 5.5 Release and claim-clearing — tightened

- **`claim`**: `pending_review → in_review`, per §5.4.
- **`release`** (`intake.review.release`): `in_review → pending_review`, clears `claimed_by_user_id`/`claimed_by_display_name`/`claimed_at`. Allowed by the current claimant. An administrator override is also allowed, but **requires a reason**, logged to the event history (§5.8) distinctly from an ordinary self-release.
- **Decision commands clear the claim atomically as part of the same transition, not as a separate step:** `intake.review.return`, `intake.review.approve`, and `intake.packet.reject` (if adopted) each, in one operation, transition `packet_status` out of `in_review` **and** clear the claim fields **and** write the reviewer identity into the append-only decision/event history — so the reviewer of record is never lost even though the live `claimed_by_user_id` field is cleared once the decision is made. The claim fields describe "who currently has this checked out," not "who last acted on it"; the latter lives permanently in the event log.

### 5.6 Supersession — made deterministic

Superseder determination uses **canonical restaurant identity and canvass chronology**, not ingestion order (which can differ from canvass order — a delayed review of an earlier canvass can cause it to be ingested after a later canvass's packet):

- **Identity:** two packets are compared for supersession only if they resolve to the same `restaurant_id` (preferred) or, if `restaurant_id` is null on either, the same `restaurant_external_id`. This is the canonical restaurant identity already used elsewhere in the schema (migration 015).
- **Chronology:** packet Q can supersede packet P only if `Q.canvass_date > P.canvass_date`, and both are `ingested`. Ingestion timestamp is not part of the comparison.
- **Determinism / single-hop chaining:** each packet's `superseded_by_packet_id` points to exactly one packet — its immediate chronological successor by canvass_date among `ingested` packets for the same restaurant identity, not to every later packet. Full supersession history for a restaurant is reconstructed by walking the chain (`P1.superseded_by_packet_id → P2`, `P2.superseded_by_packet_id → P3`, ...), not by fanning one packet out to all future ones.
- **Out-of-order ingestion:** the successor link is (re)computed at the moment any packet reaches `ingested`, in both directions: (a) when packet X is ingested, find the nearest earlier-canvass `ingested` packet P for the same restaurant with no closer successor already linked, and set `P.superseded_by_packet_id = X` if X's canvass_date is closer to P's than whatever P currently points to (handles a late-arriving, chronologically-earlier packet being ingested after a later one already exists); (b) also check whether an already-`ingested`, later-canvass packet already exists that should supersede X itself, and set `X.superseded_by_packet_id` accordingly if so.
- **Self-reference and cycles:** a `CHECK` constraint enforces `superseded_by_packet_id != packet_id`. Cycles are structurally excluded because a packet may only be pointed to by an earlier-canvass packet and may only point to a later-canvass packet — canvass_date supplies a strict total order (ties broken by `submitted_at`), so no cycle can form.

### 5.7 Ingestion status — system-controlled

Per the Founder's instruction: `packet_status = ingested` may only be set after a successful durable evidence write through the governed `intake.packet.commit_ingest` workflow — never by an independent human action that merely flips a status flag while evidence may or may not have actually been written.

**Recommendation: absorb `mark_ingested` into `commit_ingest`.** `intake.packet.commit_ingest` performs the durable write and, only upon confirmed success, sets `packet_status = ingested` itself, atomically, as its own last step. The currently-implemented `intake.packet.mark_ingested` (CMD000007) is **deprecated as an independent operator-facing action** — it currently allows a human to set `ingested` with no evidence-write guarantee behind it, which is exactly the defect this correction closes. It may be retained only as a restricted, admin-only, reason-required reconciliation tool for correcting drift between recorded status and actual evidence state (e.g., after a manual out-of-band fix) — not as part of the ordinary operator workflow.

### 5.8 Revisions vs. lifecycle events — two stores, not one undefined table

v2's single `intake_packet_revisions` table conflated two different kinds of record with different shapes and different write frequency. Revised recommendation (Model A — two append-only stores):

- **`operations.intake_packet_revisions`** — payload snapshots only. One row per payload-changing event (i.e., `intake.packet.update`). Columns: `revision_id`, `packet_id`, `prior_payload jsonb`, `actor`, `reason`, `created_at`. This table stays small in row count (only correction events) but each row is heavy (a full JSON snapshot).
- **`operations.intake_packet_events`** — lifecycle/audit trail. One row per state-changing or claim-changing event: `claim`, `release` (self or admin-override, with reason if override), `return`, `resubmit`, `approve`, `reject` (if adopted), `ingest`, `archive`, `supersede`. Columns: `event_id`, `packet_id`, `event_type`, `actor` (`claimed_by_user_id` or acting reviewer), `reason` (nullable, required for override/return/reject), `metadata jsonb` (event-specific detail, e.g. which packet superseded which), `created_at`. This table is high-frequency but each row is light.

This directly closes the standing audit-trigger gap (no trigger exists today on `intake_packets`) and gives each event type an explicit, queryable home rather than an ambiguous shared table.

### 5.9 `approved → returned` — closed

Per the Founder's instruction, this transition is treated as an implementation defect, not a feature to formally adopt. **`intake.review.return` is restricted to `in_review → returned` only** — `pending_review` and `approved` are both removed as valid source states (removing `pending_review` as a source is a further tightening beyond v2, made necessary by §5.5's rule that decisions are made from `in_review`, requiring a claim first). If a genuine need for reversing an already-approved packet is later identified, it must be proposed and approved as its own, separately governed, elevated action (e.g., a future `intake.review.reverse_approval` requiring admin role and mandatory reason) — not folded back into ordinary `return`.

### 5.10 `rejected` — adopted on its own merits

v2 left this an open question because the only evidence was the registry's own placeholder (CMD000009). This revision evaluates it directly, independent of that placeholder:

**Distinction:** `returned` is a correctable packet that may re-enter review after a fix. `rejected` is a **terminal** determination that the packet is not actionable at all — not a data-quality problem to fix, but the wrong kind of submission entirely (e.g., wrong restaurant, spam/test data, duplicate of an already-ingested packet, policy violation). No amount of payload correction turns a rejected packet into a valid one; that operationally distinguishes it from `returned` in a way `returned` alone cannot represent, which is the real justification — not the existence of CMD000009.

**If adopted (recommended):**
- `in_review → rejected` only — same precondition as approve/return (must be claimed).
- Reason is mandatory, not optional.
- Requires an explicit confirmation step in the UI (distinct click/dialog from an ordinary return) given its terminality.
- Logged to `intake_packet_events` (§5.8) with full reason.
- A rejected packet can never reach `ingested`.
- Reopening a rejected packet is not part of ordinary workflow — only through the same separately-governed exceptional action referenced in §5.1/§5.9 (`intake.packet.reopen`, still undefined by this decision).

### 5.11 Archival — policy clarified, not prescribed

Restated precisely, per instruction: **archival removes a resolved packet from default operational views but never deletes it or changes its processing outcome. Archival may be manual or policy-driven. No automatic archival schedule is approved by this decision.** `archived_at` (nullable) is the mechanism; when and by what policy it gets set is deliberately left open, to be decided operationally later, not implied here.

## 6. Recommended canonical model (final, v3)

```
packet_status:  pending_review → in_review (claim)
                in_review → pending_review (release)
                in_review → returned (return; reason required)
                returned → returned (payload update, via intake.packet.update — no status change)
                returned → pending_review (resubmit)
                in_review → approved (approve)
                in_review → rejected (reject, if adopted; reason + confirmation required)
                approved → ingested (system-set only, via commit_ingest)

Attributes/relationships, not statuses:
  claimed_by_user_id, claimed_by_display_name, claimed_at   — in_review ownership
  superseded_by_packet_id                                   — deterministic, single-hop, canvass-chronology based
  archived_at                                                — retention marker, policy undefined by this decision

Append-only stores:
  intake_packet_revisions   — payload snapshots (update events only)
  intake_packet_events      — full lifecycle/claim event log
```

Five `packet_status` values if `rejected` is adopted (`pending_review`, `in_review`, `returned`, `approved`, `ingested`, `rejected` — six, correcting the count), four if not. `draft` remains excluded (v2's finding stands, not revisited here since it wasn't part of this correction round).

## 7. Founder decisions required (shortened — true policy choices only)

Mechanical/architectural corrections above (atomic claim implementation, stable user-id reference, two-store revision/event model, deterministic supersession algorithm, system-controlled ingestion) are treated as resolved by this revision and are not re-listed as open questions. What remains genuinely open:

1. **Adopt `rejected` as a sixth status**, with the terminal, mandatory-reason, confirmation-gated semantics in §5.10 — yes/no.
2. **Confirm `intake.packet.update` / `intake.packet.resubmit` as two new commands**, and confirm `intake.packet.reopen` (CMD000010) is left undefined and reserved for a future exceptional action rather than given any meaning by this decision.
3. **Confirm `intake.packet.mark_ingested` is deprecated as an independent operator action** and folded into `commit_ingest`, retained only as a restricted admin reconciliation tool if at all.
4. **Confirm the claim/decision precondition tightening**: `intake.review.return`, `.approve`, and `.reject` (if adopted) all require the packet to be `in_review` (claimed) first — closing `approved → returned` entirely rather than special-casing it.
5. **Confirm the exact source of stable user identity** (`claimed_by_user_id`'s reference target) once the current authentication/user model is identified — this decision assumes such a model exists but does not have visibility into its exact shape from the files inspected.
6. **Confirm no automatic archival schedule is being approved now** — archival policy (manual, scheduled, or both) is left for a later operational decision, not fixed here.

## 8. Risks, guardrails, validation criteria, revisit triggers

**Risks:**
- Supersession's out-of-order-ingestion recomputation (§5.6) touches more than one row per ingestion event — should be implemented as a single transaction to avoid a partially-updated chain if it fails midway.
- Folding `mark_ingested` into `commit_ingest` (§5.7) removes a currently-working manual override; the restricted reconciliation-tool fallback must exist before the old path is removed, to avoid leaving no recovery mechanism for legitimate drift-correction cases.

**Guardrails:**
- No implementation proceeds until Founder decisions 1-6 above are made.
- `intake.packet.update` must refuse to run unless `packet_status = returned`, per §5.2's mutation-rights table exactly.

**Validation criteria:**
- The claim `UPDATE ... WHERE ... RETURNING` pattern in §5.4 is used verbatim (or an equivalent single-statement conditional mutation) — no read-then-write claim implementation is acceptable.
- Every packet's supersession chain (if any) resolves to exactly one predecessor and one successor at most, with no cycles, verifiable by a simple recursive query.
- No code path sets `packet_status = ingested` except `commit_ingest`'s own success branch.

**Revisit triggers:**
- If a real need for reversing an approved packet emerges, that becomes its own Decision Record (per §5.9), not a reopening of this one.
- If the admin-only reconciliation fallback for `mark_ingested` is used with any regularity, that is itself a signal worth investigating — it would mean evidence-write failures are more common than assumed.
