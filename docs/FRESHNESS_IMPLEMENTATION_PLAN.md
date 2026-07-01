# GoldPan Freshness Implementation Plan

**Status:** Design-complete — ready for implementation  
**Date:** 2026-06-29 (revised — two-track architecture)  
**Supersedes:** 2026-06-28 draft (single-track design)  
**Prerequisite reading:** `docs/RECANVASSING_POLICY.md`, `docs/RULES_REGISTRY.md` (GP-RULE-008 v1.1, GP-RULE-009)

---

## Governing Principle

> Internal validation is not enough. GoldPan is only healthy when the database is both internally consistent and externally fresh.

Evidence quality and evidence freshness are independent axes. Both are required for fully trustworthy derived conclusions.

---

## Two-Track Freshness Architecture

GoldPan distinguishes two fundamentally different activities:

### Track A — Public Source Check

**Purpose:** Determine whether anything publicly available *appears* to have changed since the last canvass. This is automated monitoring, not evidence collection.

Source checks detect:
- Source URL reachable / unreachable (404, redirect, timeout)
- Menu page reachable
- PDF changed (content hash or modified date)
- HTML structure changed (new dishes, removed dishes, ingredient wording)
- Hours changed

**Critical constraint:** A source check never modifies GoldPan evidence. It has exactly one output: `Source_Check_Status`. It is a signal, not an update.

**Who runs it:** `check_sources.py` (future automated script) or manual canvasser review.

**Output field:** `Source_Check_Status` in the Menu Source Registry.

### Track B — Full Recanvass

**Purpose:** Collect, verify, and integrate new evidence into GoldPan. This is the evidence acquisition event.

A full recanvass includes:
- Reviewing current menu from authoritative source
- Updating ingredients in staging file
- Updating transparency scores
- Updating restaurant claims
- Recomputing derived filters
- Publishing new evidence via `upsert_dishes.py`

**Critical constraint:** A full recanvass is always triggered by a reason — either a scheduled window expiry or a source check that flagged changes. It is never automatic. It is always human-verified.

**Who runs it:** Canvasser.

**Output field:** `Recanvass_Status` in the Menu Source Registry (computed from `Last_Canvassed` + triggers).

### How the tracks relate

Source checks feed recanvass priority. They do not bypass it.

```
Source_Check_Status = "ok"           → no effect on Recanvass_Status
Source_Check_Status = "changed"      → escalates to needs_recanvass (Recanvass_Status)
Source_Check_Status = "unreachable"  → escalates to needs_recanvass (Recanvass_Status)
Source_Check_Status = "overdue"      → noted in health report; does not change Recanvass_Status
```

The derived filter engine only reads `Recanvass_Status`. It is the synthesized verdict. The engine does not need to know whether a `needs_review` status came from a source change, a forced flag, or window expiry — the gate behavior is identical.

---

## Authoritative Freshness Fields (Menu Source Registry)

| Field | Track | Set by | Meaning |
|---|---|---|---|
| `Recanvass_Tier` | Both | Manual at onboarding | Controls both check and recanvass windows |
| `Last_Canvassed` | Recanvass | Canvasser | Date of last full evidence acquisition |
| `Last_Source_Check` | Source check | `check_sources.py` or canvasser | Date source was last confirmed live and inspected |
| `Source_Check_Status` | Source check | `check_sources.py` or canvasser | `ok` / `changed` / `unreachable` / `overdue` / `unknown` |
| `Menu_Changed` | Recanvass | Canvasser | `yes` / `no` / `unknown` — set after recanvass |
| `Change_Type` | Recanvass | Canvasser | Comma-separated: `new_dishes`, `removed_dishes`, `ingredient_change`, `score_change`, `hours_change`, `source_changed` |
| `Recanvass_Status` | Recanvass | `check_freshness.py` | `current` / `due_soon` / `overdue` / `needs_review` — computed, never manually set |
| `Status_Computed_Date` | Recanvass | `check_freshness.py` | When `Recanvass_Status` was last computed (detects stale snapshots) |
| `Forced_Recanvass_Flag` | Recanvass | Manual or system | `yes` / blank — forces `needs_review` immediately |
| `Recanvass_Notes` | Both | Canvasser | Free text; must reference recanvass report filename |

**Protecting computed fields:**  
`Recanvass_Status` and `Status_Computed_Date` should be annotated in the sheet:
> **COMPUTED — do not edit manually. Recomputed by check_freshness.py on each pipeline run.**

---

## Tier Windows

Tier controls two independent cadences: how often to check sources and how often to fully recanvass.

| Tier | Source Check Window | Recanvass Window | Typical use |
|---|---|---|---|
| 1 | 7 days | 30 days | High-change restaurants (specials-heavy, seasonal, frequent menu updates) |
| 2 | 14 days | 90 days | Standard (default for all restaurants at onboarding) |
| 3 | 30 days | 180 days | Stable menus (institutional-style, fixed menus with rare changes) |

**Design principle:** Check often. Recanvass when evidence requires it.

A Tier 2 restaurant is source-checked every 2 weeks (automated). If checks are clean, it is fully recanvassed every 90 days. A source check that detects changes triggers an immediate recanvass investigation, collapsing the 90-day window.

The due_soon lead time is **14 days** before the recanvass window boundary (was 30 days in the previous design — reduced to match the shorter windows).

---

## Source_Check_Status Values

| Value | Meaning | Effect on Recanvass_Status |
|---|---|---|
| `ok` | Source reachable; no changes detected | None |
| `changed` | Source content appears to have changed | Escalates to `needs_review` |
| `unreachable` | Source URL returned 404 / error / timeout | Escalates to `needs_review` |
| `overdue` | Source check window expired without a check | Noted in health report; does not change Recanvass_Status |
| `unknown` | Never checked or check data unavailable | Treated as a trigger (see Part 6 below) |

---

## Recanvass_Status Values

| Value | Meaning | Engine behavior |
|---|---|---|
| `current` | Last_Canvassed within window; no triggers active | Full confidence |
| `due_soon` | Within 14 days of window expiry | Full confidence; staleness caveat in limitations |
| `overdue` | Past recanvass window; no triggers | Confidence capped at `likely` (GP-RULE-009) |
| `needs_review` | Active trigger (see trigger catalog) | All derived conclusions suppressed → `Unknown` |

---

## Part 1: `freshness.py` — Shared Computation Module

### Purpose

Pure computation module. No Google Sheets dependency. Imported by both `check_freshness.py` and `compute_derived_filters.py`.

### Public API

```python
compute_freshness_map(rows, today=None)
    → dict[restaurant_id, FreshnessRecord]

compute_restaurant_status(row, today=None)
    → FreshnessRecord

days_since(date_str, today=None)
    → int | None

freshness_summary(freshness_map)
    → dict  # counts, score, target_met, critical_ok
```

### FreshnessRecord fields

```python
@dataclass
class FreshnessRecord:
    restaurant_id:        str
    restaurant_name:      str
    status:               str        # current | due_soon | overdue | needs_review | unknown
    recanvass_tier:       int
    recanvass_window:     int        # days, from tier
    source_check_window:  int        # days, from tier — NEW
    last_canvassed:       Optional[str]
    last_source_check:    Optional[str]   # NEW
    source_check_status:  str        # ok | changed | unreachable | overdue | unknown — NEW
    menu_changed:         str
    forced_recanvass:     bool
    days_since_canvass:   Optional[int]
    days_overdue:         int
    days_remaining:       int
    triggers:             list[str]
    computed_date:        str
```

---

## Part 2: `check_freshness.py` — Standalone Freshness Audit

### Interface

```bash
python3 check_freshness.py               # dry run — compute and report, no write
python3 check_freshness.py --apply       # compute + write Recanvass_Status snapshot
python3 check_freshness.py --apply --report  # compute + write + save freshness report to docs/
```

### What it does

```
For each active restaurant:

  1. Read from Menu Source Registry:
       Last_Canvassed, Last_Source_Check, Source_Check_Status,
       Recanvass_Tier, Menu_Changed, Forced_Recanvass_Flag

  2. Check triggers (escalation takes priority):
       - Forced_Recanvass_Flag = "yes"       → needs_review
       - Last_Canvassed is blank              → needs_review
       - Source_Check_Status = "changed"      → needs_review
       - Source_Check_Status = "unreachable"  → needs_review
       - Last_Source_Check is blank           → needs_review (never checked)
       - Menu_Changed = "unknown"             → needs_review
       - Change_Type includes "source_changed" → needs_review

  3. If no triggers → compute from recanvass window:
       window = {1: 30, 2: 90, 3: 180}[Recanvass_Tier]
       days_since_canvass = (today − Last_Canvassed).days
       if days_since_canvass > window        → overdue
       elif days_since_canvass > window - 14 → due_soon
       else                                  → current

  4. Write (--apply):
       Recanvass_Status     ← computed value
       Status_Computed_Date ← today
```

### What it does NOT do

- Does not modify ingredient data, scores, claims, or staging files
- Does not compute derived filter results
- Does not check whether source URLs are live (that is `check_sources.py`)
- Does not mark dishes as Inactive

---

## Part 3: `check_sources.py` — Public Source Monitor (future)

This script is not implemented in this phase. It is defined here to establish the architectural boundary.

### Purpose

Automated public source monitoring. Pings registered source URLs, detects changes, updates `Source_Check_Status` and `Last_Source_Check` in the Menu Source Registry.

### What it detects

- HTTP status of source URL (200 / 404 / redirect)
- Content-hash change on menu page or PDF
- Structural changes (new/removed dishes, section count, ingredient wording) via lightweight HTML diff

### What it does NOT do

- Does not update any evidence field
- Does not update ingredients, scores, or claims
- Does not trigger a recanvass automatically — it only updates `Source_Check_Status`

When `Source_Check_Status` is set to `"changed"` or `"unreachable"`, `check_freshness.py` will pick this up on the next pipeline run and escalate `Recanvass_Status` to `"needs_review"`.

---

## Part 4: Schema Changes — Menu Source Registry

**New columns (add in order at right of existing columns):**

| Column | Type | Set by |
|---|---|---|
| `Recanvass_Tier` | Integer (1/2/3) | Manual |
| `Last_Canvassed` | Date (YYYY-MM-DD) | Canvasser |
| `Last_Source_Check` | Date (YYYY-MM-DD) | `check_sources.py` or canvasser |
| `Source_Check_Status` | String | `check_sources.py` or canvasser |
| `Menu_Changed` | String (yes/no/unknown) | Canvasser |
| `Change_Type` | Comma-separated string | Canvasser |
| `Recanvass_Status` | Computed string | `check_freshness.py` — **never manually set** |
| `Status_Computed_Date` | Date (YYYY-MM-DD) | `check_freshness.py` — **never manually set** |
| `Forced_Recanvass_Flag` | String (yes / blank) | Manual or system |
| `Recanvass_Notes` | Free text | Canvasser |

**Initial backfill:**
- Set `Recanvass_Tier = 2` for all current restaurants
- Set `Last_Canvassed` from known canvass dates
- Leave `Last_Source_Check` blank (first check not yet run)
- Leave `Source_Check_Status` blank (or `unknown`)
- Set `Forced_Recanvass_Flag = "yes"` for restaurants with known data quality concerns

---

## Part 5: Engine Changes — `derived/engine.py`

### DishEvidence addition

Add `restaurant_id` to `DishEvidence` so the engine can look up freshness without an additional parameter:

```python
@dataclass
class DishEvidence:
    dish_id:                  str
    dish_name:                str
    restaurant:               str
    restaurant_id:            str    # ← add this field
    location:                 str
    ingredients:              List[dict]
    has_verified_ingredients: bool
    verified_sources:         List[str]
```

### Updated function signatures

```python
def run_filter(
    filter_def: FilterDefinition,
    evidence: DishEvidence,
    freshness_map: dict[str, FreshnessRecord],  # ← add
) -> DerivedConclusion:

def run_all_filters(
    evidence: DishEvidence,
    registry: dict[str, FilterDefinition],
    freshness_map: dict[str, FreshnessRecord],  # ← add
) -> dict[str, DerivedConclusion]:
```

### Engine gate order (updated)

```
Gate 0 — Freshness (GP-RULE-008 v1.1):
    rec = freshness_map.get(evidence.restaurant_id)
    status = rec.status if rec else "unknown"

    if status in ("needs_review", "unknown"):
        return DerivedConclusion(
            conclusion="Unknown",
            status="unknown",
            confidence="unknown",
            reasoning=(
                "Restaurant data is pending freshness verification (GP-RULE-008 v1.1). "
                f"Recanvass_Status: {status}. "
                f"Active triggers: {'; '.join(rec.triggers) if rec else 'freshness record missing'}"
            ),
            limitations="All derived conclusions are suppressed until recanvass is complete.",
            rule_ids=["GP-RULE-008"],
        )

Gate 1 — Dependency type (GP-RULE-007):
    (unchanged)

Gate 2 — Materiality test (GP-RULE-001):
    (applied inside compute_fn — unchanged)

Compute:
    result = filter_def.compute_fn(evidence, filter_def)

Post-compute — Confidence cap (GP-RULE-009):
    if status == "overdue":
        result.confidence = "likely"  (cap — never upgrade)
        result.reasoning += (
            f" Evidence quality supports 'verified', but Recanvass_Status is 'overdue' "
            f"(last canvassed: {rec.last_canvassed}, {rec.days_overdue} days past the "
            f"{rec.recanvass_window}-day window). Per GP-RULE-009, confidence capped at 'likely'."
        )
        result.rule_ids.append("GP-RULE-009")

    elif status == "due_soon":
        result.limitations += (
            f" Note: This restaurant's menu data is approaching its scheduled recanvass "
            f"date (last canvassed: {rec.last_canvassed}, {rec.days_remaining} days remaining)."
        )
        result.rule_ids.append("GP-RULE-008")
```

---

## Part 6: `needs_review` Trigger Catalog

Evaluated by `check_freshness.py` before the date-window calculation. First match stops evaluation; all active triggers are logged for transparency.

| Trigger | Detected by | Cleared by |
|---|---|---|
| `Forced_Recanvass_Flag = "yes"` | Manual | Manual clear after recanvass complete |
| `Last_Canvassed` is blank | `check_freshness.py` | First full recanvass |
| `Source_Check_Status = "changed"` | `check_sources.py` / canvasser | Completed recanvass with `Menu_Changed` resolved |
| `Source_Check_Status = "unreachable"` | `check_sources.py` / canvasser | Confirmed live source + new `Last_Source_Check` |
| `Last_Source_Check` is blank | `check_freshness.py` | Any confirmed source check that succeeds |
| `Menu_Changed = "unknown"` | Canvasser-set | Follow-up canvass with `Menu_Changed = "yes"` or `"no"` |
| `Change_Type` includes `source_changed` | Canvasser-set | Recanvass against new source with `Menu_Changed` resolved |

**`needs_review` is not a pipeline block.** The pipeline continues for all other restaurants. For the `needs_review` restaurant's dishes, the engine returns `Unknown` for all derived filters. Dish data (ingredients, tags, allergen summary) is still served — only derived conclusions are suppressed.

However, `needs_review` appears prominently in the Database Health Report and must be resolved before the next full database health audit returns a passing status.

---

## Part 7: Updated Pipeline Sequence

```
Step 0a: check_sources.py (future)
         → Ping all registered source URLs
         → Detect changes, 404s, redirects
         → Update Source_Check_Status + Last_Source_Check
         → Outputs: updated Menu Source Registry fields only

Step 0b: check_freshness.py --apply
         → Read Menu Source Registry (including Source_Check_Status)
         → Evaluate triggers (Source_Check_Status escalations first)
         → Compute Recanvass_Status for all restaurants
         → Write Recanvass_Status + Status_Computed_Date
         → Produce freshness report
         → Output: freshness_map {restaurant_id: FreshnessRecord}

Step 1:  validate_staging.py --all
         → Pre-flight: all staging files must pass

Step 2:  backfill_enrichment.py --apply

Step 3:  compute_derived_filters.py --apply
         → Receives freshness_map from Step 0b
         → Engine applies Gate 0 (freshness) before computing each filter
         → Produces derived_filters.json with freshness context per dish

Step 4:  fetch_dishes.py
         → Reads sheet + derived_filters.json
         → Produces dishes.json + restaurants.json

Step 5:  Verify outputs
```

Pipeline integration note: `pipeline.py` will need a new step between the current Step 1 (validate_staging) and Step 2 (backfill_enrichment) to run `check_freshness.py` and load the freshness_map.

---

## Part 8: Freshness Report Format

```
════════════════════════════════════════════════════════════════
DATA FRESHNESS                          Computed: 2026-06-29
════════════════════════════════════════════════════════════════

SOURCE CHECK STATUS
Restaurant                   Tier  Last Checked    Source Status     Next Due
─────────────────────────────────────────────────────────────────────────────
Adam & Eve Cafe              2     2026-06-27      ok                2026-07-11
Emmy Squared                 2     2026-06-20      ok                2026-07-04
Brick & Tin                  2     2026-06-01      overdue           7 days overdue  ⚠
Blue Root                    2     —               unknown           never checked   🔴
[Soho Standard]              1     2026-06-28      unreachable       → needs_review  🔴

RECANVASS STATUS
Restaurant                   Tier  Last Canvassed  Status            Days
─────────────────────────────────────────────────────────────────────────────
Adam & Eve Cafe              2     2026-06-27      current           83 remaining
Emmy Squared                 2     2026-06-27      current           83 remaining
Brick & Tin                  2     2026-05-15      overdue           44 overdue     ⚠
Blue Root                    2     2026-04-01      overdue           88 overdue     ⚠
[Soho Standard]              1     2026-06-28      needs_review      Source unreachable  🔴

────────────────────────────────────────────────────────────────
FRESHNESS SUMMARY
  current:       18 restaurants    (72%)
  due_soon:       3 restaurants    (12%)
  overdue:        3 restaurants    (12%)
  needs_review:   1 restaurant     ( 4%)

Freshness Score: 84%  (current + due_soon) / total
  Target: ≥ 80%  ✓
  Critical: 0 needs_review required  ✗ — 1 active, action required

EFFECT ON DERIVED FILTERS
  Full confidence (current/due_soon):         701 dishes
  Reduced confidence, capped at "likely" (overdue):   43 dishes
  Suppressed conclusions (needs_review):              12 dishes
════════════════════════════════════════════════════════════════
```

**Freshness score definition:**
```
Freshness Score = (current + due_soon) / total_active_restaurants × 100
```
Target: ≥ 80%. Below 80% = database health warning. Below 60% = database health failure. Any `needs_review` is a required-attention signal regardless of score.

---

## Part 9: `derived_filters.json` Shape (Updated)

```json
{
  "D064": {
    "dish_id": "D064",
    "dish_name": "Avocado Toast",
    "restaurant": "Adam & Eve Cafe",
    "restaurant_id": "R001",
    "freshness": {
      "recanvass_status": "current",
      "source_check_status": "ok",
      "last_canvassed": "2026-06-27",
      "last_source_check": "2026-06-27",
      "status_computed_date": "2026-06-29"
    },
    "computed": true,
    "filters": { ... }
  }
}
```

For a `needs_review` restaurant:
```json
{
  "freshness": {
    "recanvass_status": "needs_review",
    "source_check_status": "unreachable",
    "last_canvassed": "2026-06-28",
    "last_source_check": "2026-06-28",
    "status_computed_date": "2026-06-29"
  },
  "computed": false,
  "filters": {
    "no-beef-identified": {
      "conclusion": "Unknown",
      "confidence": "unknown",
      "status": "unknown",
      "reasoning": "Restaurant data is pending freshness verification (GP-RULE-008 v1.1). Recanvass_Status: needs_review. Active triggers: Source_Check_Status = 'unreachable'.",
      "rule_ids": ["GP-RULE-008"]
    }
  }
}
```

---

## Part 10: Implementation Order

### Phase 1 — Foundation (no engine changes yet)

1. **Add Menu Source Registry columns** (see Part 4)
2. **Backfill initial values** — Tier 2 for all; Last_Canvassed from known dates
3. **Rewrite `freshness.py`** — with two-track FreshnessRecord; unit-testable without Sheets
4. **Create `check_freshness.py`** — reads registry, computes, writes snapshot on --apply
5. **Verify** — run `check_freshness.py` dry-run and confirm statuses match expectations

### Phase 2 — Engine integration

6. **Update `derived/models.py`** — add `restaurant_id` to `DishEvidence`
7. **Update `derived/engine.py`** — Gate 0, updated `run_filter`/`run_all_filters` signatures
8. **Update `build_dish_evidence()`** — pass `restaurant_id` through
9. **Update `compute_derived_filters.py`** — call `compute_freshness_map()`, pass to engine, add freshness context to output
10. **Verify** — unit test: needs_review restaurant → Unknown for all filters; overdue → "likely" not "verified"

### Phase 3 — Report and storage

11. **Create `docs/recanvass_reports/`** — with `.gitkeep`
12. **Add freshness section** to Database Health Report in compute_derived_filters.py
13. **Add freshness object** to `derived_filters.json` output
14. **Update `pipeline.py`** — add check_freshness step between validate and backfill

### Phase 4 — Hardening

15. **Add `--require-fresh` flag** to `compute_derived_filters.py`
16. **Add stale-snapshot detection** to `validate_database.py` (warn if `Status_Computed_Date` > 7 days)
17. **Implement `check_sources.py`** — automated public source monitoring (its own sprint)

---

## Summary: Architecture Decisions

| Question | Answer |
|---|---|
| What is a Source Check? | Automated monitoring of public sources. Never modifies evidence. Output: Source_Check_Status only. |
| What is a Full Recanvass? | Evidence acquisition event. Updates ingredients, scores, claims. Run by canvasser. |
| What does the engine see? | Only `Recanvass_Status`. It does not know the source of the signal. |
| What triggers `needs_review`? | Source check flagging changes/unreachable, forced flag, blank Last_Canvassed, Menu_Changed = unknown, source_changed. |
| What are the tier windows? | Source check: 7/14/30 days. Recanvass: 30/90/180 days. |
| Does `needs_review` block deployment? | No. Suppresses that restaurant's derived conclusions only. Optional `--require-fresh` flag enforces blocking. |
| Do GP-RULE-008/009 need to expand? | GP-RULE-008 → v1.1 (adds two-track model, Source_Check_Status, escalation logic). GP-RULE-009 unchanged. |
| Are new rules needed? | No. The engine contract (one signal: Recanvass_Status → confidence gate) is unchanged. |
