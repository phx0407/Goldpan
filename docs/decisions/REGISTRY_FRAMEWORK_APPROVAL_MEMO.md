# Registry Framework Approval Memo

**Reviews:** `docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md`, §7–§15
**Purpose:** Give the framework (not the Phase 5 inventory) a go/no-go per element, so Decision Records and future command entries have a stable spec to write against.
**Scope discipline:** identifies only concrete problems that would block the framework from serving Phase 5 accurately. No redesign.

---

## Verdict summary

| # | Element | Verdict |
|---|---|---|
| 1 | Registry ID format (`CMD000001`) | **Approve as written** |
| 2 | Command namespace format (`<owning_os>.<entity>.<verb>`) | **Approve as written** |
| 3 | Registry statuses (draft / under_review / approved / deprecated / superseded / archived) | **Approve as written** |
| 4 | Implementation statuses (implemented / partial / missing / future / recommendation) | **Approve as written** |
| 5 | Evidence classifications (E0–E4) | **Approve as written** |
| 6 | Decision-basis categories | **Approve provisionally** |
| 7 | Decision dependency fields | **Revise before approval** |
| 8 | Flat, version-controlled storage (not a DB table) | **Approve as written** |

---

## 1. Registry ID format — Approve as written

`CMD000001`, sequential, never reused. No ambiguity, no collision risk at Phase 5 scale (~30 records), matches the existing `R000001` / `PKT000001` pattern already live in Blueprint §5c. Nothing to fix.

## 2. Command namespace format — Approve as written

`<owning_os>.<entity>.<verb>` is already in production use as literal API/handler vocabulary (`intake.packet.submit` reads directly against `submit_packet()` in `api/routers/intake.py`). One boundary worth stating explicitly rather than leaving implicit: the spec doesn't define what happens when a command's `owning_os` changes after publication (ownership transfer is explicitly allowed under Blueprint §5i design rule 1). Recommend a one-line addition — "a namespace's `<owning_os>` segment is fixed at registration; an ownership transfer supersedes the command under a new namespace rather than mutating the old one in place" — but this is a clarifying footnote, not a blocker. Approving as written; footnote can ride along with the next registry edit.

## 3. Registry statuses — Approve as written

Six values, mutually exclusive, cover the real lifecycle a registry record needs (draft through archived). No gap found against how the Phase 5 inventory actually uses status today.

## 4. Implementation statuses — Approve as written

Five values, and the framework's own §8.2 example (`registry_status: approved` + `implementation_status: missing`) is exactly the pattern needed for Phase 5's ~19 missing/partial commands — approved-but-unbuilt is a real and common state in this inventory, not a hypothetical.

## 5. Evidence classifications (E0–E4) — Approve as written

The standard is coherent and its five rules (§9) are strict enough to prevent the failure mode it's designed to prevent — Blueprint prose being mistaken for shipped code. This memo and the two Decision Records below were produced under this standard as a live test: every claim in them cites either a file/route (E1) or a Blueprint section (E2), and every place the two disagree is flagged rather than silently resolved. The standard held up under actual use — no revision needed.

## 6. Decision-basis categories — Approve provisionally

The seven categories (`observed_need`, `architectural_requirement`, `implementation_constraint`, `operational_judgment`, `experiment`, `strategic_bet`, `compliance_or_risk_control`) are usable and non-overlapping. Provisional rather than unconditional because they haven't yet been exercised against a real decision — DEC000001 and DEC000002 below are the first live test. If either draft finds a basis that doesn't fit cleanly into one of the seven (for instance, a decision made *because a prior decision already implied it* — decision-driven-by-decision, not by the underlying operational reality), the category list should be revisited then. Recommend converting to full approval once DEC000001/DEC000002 are themselves approved and the categories have been shown to fit.

## 7. Decision dependency fields — Revise before approval

This is the one concrete problem. §13 specifies `decision_dependencies` as a list of Decision Registry IDs (`DEC000014`, `DEC000027` in the worked example) — but no Decision Record exists yet anywhere in the repo, and no ID-assignment rule is defined for the Decision Registry itself (no equivalent of §7.1's "sequential, never reused" rule, stated anywhere for `DEC`-prefixed IDs). The Command Registry framework quietly assumes a sibling registry that doesn't exist yet, with no stated ID scheme.

This matters concretely, right now: DEC000001 and DEC000002 below are about to become the first two records in that registry, and they need a home and a numbering rule before they can be correctly referenced from any command's `decision_dependencies` field later. Recommend, as part of approving this element:
- Adopt the same ID rule as §7.1: `DEC000001`, sequential, never reused.
- Storage location: `docs/decisions/`, one file per record (this memo already assumes and uses that path for the two drafts below — flagging it here so the assumption is visible rather than silently baked in).
- No other change needed — the field itself (a list of ID strings on a command record) is fine as specified.

## 8. Flat, version-controlled storage — Approve as written

Confirmed appropriate by direct evidence, not just the framework's own reasoning: `docs/GOLDPAN_COMMAND_REGISTRY_PHASE5.md` has already been through one full edit-and-commit cycle this session (checkpointed at `470f99c`) with zero tooling beyond `git`. At 30 commands and growing slowly, a DB-backed registry app would be solving a problem that git already solves for free. Revisit only when/if the registry needs to *drive* runtime UI (Blueprint §7b), exactly as the framework already states.

---

## Net effect

7 of 8 elements need no change. One (`decision_dependencies`) needs a minimal, mechanical fix — adopt a Decision Registry ID rule and a storage path — before it can be used correctly, and that fix is applied below by DEC000001/DEC000002 simply existing at `docs/decisions/DEC000001_*.md` / `DEC000002_*.md` with sequential IDs. No part of the framework requires redesign.
