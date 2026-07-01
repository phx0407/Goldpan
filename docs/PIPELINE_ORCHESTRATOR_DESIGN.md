# GoldPan Pipeline Orchestrator Design

**Status:** Design-complete — ready for implementation  
**Date:** 2026-06-28  
**Prerequisite reading:** `docs/EVIDENCE_ARCHITECTURE.md`, `docs/FRESHNESS_IMPLEMENTATION_PLAN.md`, `docs/ARCHITECTURAL_HEALTH_REVIEW.md`

---

## Purpose

The Pipeline Orchestrator (`pipeline.py`) is a coordinator, not a business logic container. It runs the existing tools in the correct order, passes outputs between stages, stops on blocking failures, and assembles one final Pipeline Report from each stage's structured output.

**The orchestrator owns:**
- Execution order
- Context passing between stages
- Failure handling and stop conditions
- Report collection and assembly

**The orchestrator does not own:**
- Validation logic (`validate_staging.py`, `validate_database.py`)
- Upsert logic (`upsert_dishes.py`)
- Enrichment logic (`backfill_enrichment.py`)
- Freshness computation (`check_freshness.py`, `freshness.py`)
- Derived filter computation (`compute_derived_filters.py`)
- Application data building (`fetch_dishes.py`)

Each existing script remains responsible for its own work. If business logic needs to change, the script changes — the orchestrator does not.

---

## Long-Term Goal

Every restaurant onboarding should require only:

```bash
python3 pipeline.py staging_newrestaurant.json
```

Input: a staging file.  
Output: verified GoldPan knowledge in the application.

The canvasser should not need to remember or coordinate individual commands. The pipeline is the interface.

---

## Governing Principles

1. **Explicit over implicit.** Every stage declares what it needs and what it produces. No stage assumes state from a previous stage without receiving it through context.
2. **Stop on blocking failures.** A failed stage that produces unreliable output must not allow downstream stages to run. A downstream stage running on corrupt input produces corrupt output — a worse outcome than stopping.
3. **Non-blocking failures continue.** Warnings and medium-severity issues are logged and included in the final report. They do not stop the pipeline.
4. **Every stage produces a structured report.** Reports are machine-readable JSON. The orchestrator assembles them; it does not interpret them.
5. **Dry run is a first-class mode.** Every stage must support dry-run. The orchestrator passes `--dry-run` through to all stages when invoked with `--dry-run`.
6. **Resumability via run directory.** Every pipeline run writes its state to a run directory. A failed pipeline can be resumed from any stage without re-running earlier stages.

---

## Shared Interfaces

### `StageResult`

Every stage returns exactly one `StageResult`. The orchestrator collects these and builds the Pipeline Report from them.

```python
@dataclass
class StageResult:
    stage_number:    int         # 1–7
    stage_name:      str         # human-readable name
    status:          str         # "passed" | "warned" | "failed" | "skipped"
    blocking:        bool        # True if this failure stops the pipeline
    inputs_received: dict        # what was passed in from context
    outputs_produced: dict       # what this stage adds to context for downstream
    report:          dict        # structured, stage-specific detail
    errors:          List[str]   # [] if passed
    warnings:        List[str]   # [] if no warnings
    duration_s:      float
    timestamp:       str         # ISO 8601
```

`status` is set by the stage itself, not by the orchestrator. The orchestrator reads it and decides whether to continue.

`outputs_produced` is the stage's contribution to `PipelineContext`. The orchestrator merges it into the shared context after each stage completes.

### `PipelineContext`

The shared state that accumulates as stages complete. Each stage receives the full context; each stage adds its outputs to it.

```python
@dataclass
class PipelineContext:
    run_id:                str           # uuid, generated at pipeline start
    run_dir:               str           # pipeline_runs/{run_id}/
    staging_file:          str           # set at pipeline start
    dry_run:               bool
    require_fresh:         bool
    restaurant_id:         str           # set by Stage 1
    restaurant_name:       str           # set by Stage 1
    dish_ids_staged:       List[str]     # set by Stage 1
    dish_ids_upserted:     List[str]     # set by Stage 2
    enrichment_verified:   bool          # set by Stage 3
    validation_passed:     bool          # set by Stage 4
    critical_violations:   int           # set by Stage 4
    freshness_map:         dict          # set by Stage 5a
    derived_filters_path:  str           # set by Stage 5b
    computed_count:        int           # set by Stage 5b
    needs_review_count:    int           # set by Stage 5b
    dishes_json_path:      str           # set by Stage 6
    restaurants_json_path: str           # set by Stage 6
    stage_results:         List[StageResult]  # appended after each stage
```

Context is serialized to `{run_dir}/context.json` after each stage completes. This enables resumability: `--from-stage N` loads the context from disk and continues from stage N without re-running earlier stages.

---

## Stage Specifications

---

### Stage 1 — Validate Staging File

**Purpose:** Confirm the staging file is valid before any writes occur. This is the one stage that must block all other work on any failure — writing invalid data into the database is worse than not writing at all.

**Script:** `validate_staging.py` (to be created; currently this validation is partial inside `upsert_dishes.py`)

**Inputs from context:**
```
staging_file: str
```

**Outputs to context:**
```
restaurant_id:    str       # from staging file
restaurant_name:  str
dish_ids_staged:  List[str] # all dish IDs in the staging file
```

**Success criteria:**
- Staging file is valid JSON
- `restaurant_id` and `restaurant_name` are present and consistent across the file
- Every dish has `menu_verified: true`
- Every dish has required fields: `dish_id`, `dish_name`
- `dish_id` values are unique within the file
- `dish_id` format is valid (D + digits)
- Scoring fields are Schema A: `total_score`, `core_clarity`, `prep_clarity`, `sauce_disclosure`, `allergen_transparency`, `transparency_level`
- Ingredient `type` values are canonical or absent (non-canonical values produce a warning, not a failure — backfill will normalize them)
- Ingredient `role` values are canonical or absent (same)

**Blocking failures (pipeline stops):**
- File not found or not valid JSON
- Any dish missing `menu_verified: true` (and `--force` not passed)
- Any dish missing `dish_id` or `dish_name`
- Duplicate `dish_id` values within the file
- `restaurant_id` inconsistent across dishes

**Non-blocking warnings (pipeline continues):**
- Non-canonical `type` or `role` values (backfill will normalize)
- Missing optional fields (`allergen_flags`, `source`, etc.)
- Schema B scoring fields present (note in report; Stage 2 will handle or skip)

**Report structure:**
```json
{
  "restaurant_id": "R001",
  "restaurant_name": "Adam & Eve Cafe",
  "dish_count": 16,
  "ingredient_count": 87,
  "menu_verified_gate": "passed",
  "schema_check": "Schema A",
  "blocking_failures": [],
  "warnings": ["3 ingredients have non-canonical type values — will be normalized by backfill"],
  "dish_ids": ["D064", "D065", ...]
}
```

---

### Stage 2 — Upsert Data

**Purpose:** Write the validated staging file into the Google Sheet. For existing dishes, preserve enrichment columns. For new dishes, create full rows.

**Script:** `upsert_dishes.py`

**Inputs from context:**
```
staging_file:     str
restaurant_id:    str
dish_ids_staged:  List[str]
dry_run:          bool
```

**Outputs to context:**
```
dish_ids_upserted:   List[str]   # dish IDs successfully written
```

**Success criteria:**
- All dishes in `dish_ids_staged` are present in the sheet after upsert
- Ingredient Details rows match staging file contents for the upserted dishes
- Transparency Scoring rows are written
- DLD rows are written or updated
- Two-level verification passes (Level 1: values written; Level 2: dish appears in enrichment analysis)

**Blocking failures:**
- API error during write
- Any dish in `dish_ids_staged` is not found in the sheet after upsert
- `validate_ingredient_rows()` fails pre-write
- Required column missing in sheet

**Non-blocking warnings:**
- Dishes that already existed and had enrichment overwritten (note in report for review)

**Report structure:**
```json
{
  "dishes_written": 16,
  "dishes_updated": 0,
  "ingredients_written": 87,
  "rows_deleted_before_rewrite": 0,
  "transparency_rows_written": 16,
  "dld_rows_written": 16,
  "verification_level_1": "passed",
  "verification_level_2": "passed",
  "blocking_failures": [],
  "warnings": []
}
```

---

### Stage 3 — Run Enrichment

**Purpose:** Fill enrichment fields (Cut_Type, Preparation, Ingredient_Type, Component_Role, Allergen_Flags, Ingredient_Source) for the newly upserted dishes from verified sources.

**Script:** `backfill_enrichment.py --apply`

**Inputs from context:**
```
dish_ids_upserted: List[str]
dry_run:           bool
```

**Outputs to context:**
```
enrichment_verified: bool   # True if post-write verification passed
```

**Success criteria:**
- Post-write verification reports PASS
- Cells targeted equals cells confirmed (expected values present after write)
- Zero cells mismatched (expected X, found Y)

**Blocking failures:**
- Post-write verification reports FAIL
- Required enrichment column not found in sheet
- API error during write

**Non-blocking warnings:**
- Some dishes had no resolvable enrichment values (left blank — expected for dishes with limited menu disclosure)
- Non-canonical values remapped to Unknown (note which fields)

**Report structure:**
```json
{
  "dishes_targeted": 16,
  "cells_targeted": 87,
  "cells_written": 64,
  "cells_skipped_already_populated": 20,
  "cells_left_blank_unresolvable": 3,
  "post_write_verification": {
    "cells_confirmed": 64,
    "cells_mismatched": 0,
    "cells_still_blank": 3,
    "result": "PASS"
  },
  "blocking_failures": [],
  "warnings": ["3 cells left blank: no verified source for Preparation on D066, D067, D068"]
}
```

---

### Stage 4 — Validate Database

**Purpose:** Confirm the full database (not just the newly upserted restaurant) is internally consistent after the write. This is the integrity gate before any derived computation runs.

**Script:** `validate_database.py`

**Inputs from context:**
```
(none — reads live from sheet)
```

**Outputs to context:**
```
validation_passed:    bool
critical_violations:  int
```

**Success criteria:**
- Zero critical violations across the full database

**Blocking failures:**
- Any critical violation (🔴) found

**Non-blocking warnings:**
- Medium (🟡) or low (🟢) severity violations logged in report; pipeline continues

**Report structure:**
```json
{
  "total_dishes_checked": 756,
  "total_ingredient_rows_checked": 3877,
  "critical_violations": 0,
  "medium_violations": 4,
  "low_violations": 2,
  "violations": [
    {
      "severity": "medium",
      "field": "Ingredient_Type",
      "dish_id": "D012",
      "value": "house",
      "issue": "Non-canonical value — not in valid enum"
    }
  ],
  "result": "PASSED_WITH_WARNINGS"
}
```

---

### Stage 5 — Compute Derived Filters

**Purpose:** Compute freshness status for all restaurants and then run the derived filter engine. Freshness computation runs first and is passed into the engine.

**Scripts:**
- Stage 5a: `check_freshness.py --apply` → produces freshness map
- Stage 5b: `compute_derived_filters.py --apply` → consumes freshness map, produces `derived_filters.json`

**Inputs from context:**
```
require_fresh: bool
```

**Outputs to context:**
```
freshness_map:          dict    # {restaurant_id: {status, last_canvassed, ...}}
derived_filters_path:   str     # path to derived_filters.json
computed_count:         int
unknown_count:          int
needs_review_count:     int
```

**Success criteria:**
- `derived_filters.json` is written
- Engine produced results for all active dishes (computed or documented Unknown — no missing entries)
- No engine errors

**Blocking failures:**
- `derived_filters.json` not written
- Engine error or exception during computation
- If `require_fresh = True`: any restaurant at `needs_review` status

**Non-blocking warnings:**
- Restaurants at `needs_review` (when `require_fresh = False`) — noted in report
- Restaurants at `overdue` — noted in report with confidence impact

**Sub-stage 5a report:**
```json
{
  "restaurants_checked": 25,
  "current": 20,
  "due_soon": 3,
  "overdue": 1,
  "needs_review": 1,
  "freshness_score_pct": 92,
  "needs_review_restaurants": ["R014"],
  "overdue_restaurants": ["R003"]
}
```

**Sub-stage 5b report:**
```json
{
  "active_dishes": 701,
  "computed": 643,
  "unknown": 46,
  "not_applicable": 12,
  "suppressed_needs_review": 12,
  "confidence_degraded_overdue": 33,
  "filters_run": ["no-beef-identified"],
  "derived_filters_path": "derived_filters.json"
}
```

**Combined Stage 5 report:** merges both sub-stage reports.

---

### Stage 6 — Build Application Data

**Purpose:** Join the sheet data with derived filter results and write the public-facing `dishes.json` and `restaurants.json`.

**Script:** `fetch_dishes.py` (updated to consume `derived_filters.json`)

**Inputs from context:**
```
derived_filters_path: str
```

**Outputs to context:**
```
dishes_json_path:       str
restaurants_json_path:  str
```

**Success criteria:**
- `dishes.json` written with at least one dish entry
- `restaurants.json` written with at least one restaurant entry
- Every active dish in the sheet has a corresponding entry in `dishes.json`
- Every dish entry that has a computed derived filter result includes it

**Blocking failures:**
- `dishes.json` not written
- `restaurants.json` not written
- Zero dishes in output (suggests a read failure)

**Non-blocking warnings:**
- Dishes with no derived filter results (expected for dishes with insufficient evidence)
- Restaurants with all dishes Inactive (note only)

**Report structure:**
```json
{
  "total_dishes": 701,
  "total_restaurants": 25,
  "dishes_with_derived_filters": 643,
  "dishes_without_derived_filters": 58,
  "dishes_json_written": true,
  "restaurants_json_written": true,
  "dishes_json_path": "dishes.json",
  "restaurants_json_path": "restaurants.json"
}
```

---

### Stage 7 — Final Health Report

**Purpose:** Assemble all stage reports into one Pipeline Report, compute an overall result, and produce a human-readable summary. This stage always runs — even if earlier stages failed — so the failure state is documented.

**Script:** Inline in `pipeline.py` — no external script. This is pure orchestrator work: assembling what each stage already reported.

**Inputs from context:**
```
stage_results: List[StageResult]
(all accumulated context fields)
```

**Outputs:**
```
pipeline_report.json     → written to {run_dir}/pipeline_report.json
                           and to pipeline_reports/pipeline_{run_id}.json (permanent archive)
(human-readable summary) → printed to stdout
```

**Overall pipeline result:**
```
PASSED               All stages passed with no warnings
PASSED_WITH_WARNINGS All stages passed; at least one stage has warnings
FAILED               At least one blocking stage failed (pipeline stopped early)
```

**Report structure:**
```json
{
  "run_id": "a3f2...",
  "started": "2026-06-28T14:32:00Z",
  "completed": "2026-06-28T14:32:47Z",
  "duration_s": 47.3,
  "result": "PASSED_WITH_WARNINGS",
  "staging_file": "staging_adamandevecafe.json",
  "restaurant_id": "R001",
  "restaurant_name": "Adam & Eve Cafe",
  "stages": [
    { "stage": 1, "name": "Validate Staging", "status": "passed", "duration_s": 0.3 },
    { "stage": 2, "name": "Upsert Data",      "status": "passed", "duration_s": 4.2 },
    { "stage": 3, "name": "Run Enrichment",   "status": "passed", "duration_s": 6.1 },
    { "stage": 4, "name": "Validate Database","status": "warned",  "duration_s": 2.1 },
    { "stage": 5, "name": "Derive Filters",   "status": "passed", "duration_s": 3.4 },
    { "stage": 6, "name": "Build App Data",   "status": "passed", "duration_s": 2.8 },
    { "stage": 7, "name": "Health Report",    "status": "passed", "duration_s": 0.1 }
  ],
  "stage_reports": { ... }
}
```

---

## Human-Readable Pipeline Summary

Printed to stdout at pipeline completion (always, even on failure):

```
═══════════════════════════════════════════════════════════════
GOLDPAN PIPELINE REPORT
  Run ID:      a3f2c891
  Result:      PASSED WITH WARNINGS
  Duration:    47.3s
  Restaurant:  Adam & Eve Cafe  (R001)
  File:        staging_adamandevecafe.json
═══════════════════════════════════════════════════════════════

STAGES
  1  Validate Staging      ✓  0.3s   16 dishes, 87 ingredients validated
  2  Upsert Data           ✓  4.2s   16 dishes, 87 ingredients written
  3  Run Enrichment        ✓  6.1s   64 cells written, verification PASS
  4  Validate Database     ⚠  2.1s   0 critical, 4 medium, 2 low violations
  5  Derive Filters        ✓  3.4s   643 computed, 46 unknown, 12 needs_review
  6  Build App Data        ✓  2.8s   701 dishes → dishes.json
  7  Health Report         ✓  0.1s   Report saved

WARNINGS
  Stage 4: 4 medium violations — see pipeline_reports/pipeline_a3f2c891.json
  Stage 5: 1 restaurant needs_review (R014) — 12 dish conclusions suppressed

NEXT STEPS
  [ ] Review Stage 4 violations in pipeline_reports/pipeline_a3f2c891.json
  [ ] Recanvass R014 (needs_review) — see docs/RECANVASSING_POLICY.md
  [ ] Deploy: git add dishes.json restaurants.json && git push

═══════════════════════════════════════════════════════════════
```

On blocking failure:

```
═══════════════════════════════════════════════════════════════
GOLDPAN PIPELINE REPORT
  Run ID:      b7d1e204
  Result:      FAILED
  Stopped at:  Stage 1 — Validate Staging
  Duration:    0.4s
═══════════════════════════════════════════════════════════════

STAGES
  1  Validate Staging      ✗  0.4s   BLOCKING FAILURE — pipeline stopped

FAILURE DETAIL
  Stage 1: 3 dishes missing menu_verified: true
    D112  House Special
    D113  Chef's Plate
    D114  Market Bowl

PIPELINE DID NOT WRITE ANYTHING.

NEXT STEPS
  [ ] Add "menu_verified": true to each dish after confirming live menu
  [ ] Re-run: python3 pipeline.py staging_newrestaurant.json

═══════════════════════════════════════════════════════════════
```

---

## CLI Interface

```bash
# Standard usage — full pipeline
python3 pipeline.py <staging_file>

# Dry run — all stages run without writing
python3 pipeline.py <staging_file> --dry-run

# Require all restaurants to be fresh before deriving filters
python3 pipeline.py <staging_file> --require-fresh

# Run only specific stages (useful for development and debugging)
python3 pipeline.py <staging_file> --stage 3        # Stage 3 only
python3 pipeline.py <staging_file> --from-stage 3   # Stages 3–7
python3 pipeline.py <staging_file> --through-stage 4 # Stages 1–4

# Resume a failed run from the stage it stopped at
python3 pipeline.py --resume <run_id>

# Skip staging validation (for pipelines that don't involve a new staging file)
python3 pipeline.py --from-stage 4                  # Database health + derive + build

# Force upsert past menu_verified gate (legacy files only)
python3 pipeline.py <staging_file> --force
```

### Stage-range behavior

`--from-stage N` and `--through-stage N` require that context from skipped stages is available on disk in the run directory. On the first run, stages must be run in order. On a resume, earlier stage results are loaded from `{run_dir}/context.json`.

`--from-stage 4` with no prior run directory will fail: Stage 4 does not require staging-file context, so it can run standalone. But Stage 5 requires the freshness map from Stage 5a, and Stage 6 requires `derived_filters_path` from Stage 5. These dependencies are checked at startup.

---

## Orchestrator Behavior Specification

### Execution loop

```
for stage in stages_to_run:
    print(f"Stage {stage.number} — {stage.name}...")
    result = stage.run(context)
    context.stage_results.append(result)
    context.merge(result.outputs_produced)
    save_context_to_disk(context)

    if result.status == "failed" and result.blocking:
        print(f"  ✗ BLOCKING FAILURE — pipeline stopped")
        break

    if result.status == "failed" and not result.blocking:
        print(f"  ✗ Non-blocking failure — continuing with warning")

    if result.status == "warned":
        print(f"  ⚠ Warning — see report for details")

    if result.status == "passed":
        print(f"  ✓ Passed")

run_stage_7(context)   # always runs
```

### Failure taxonomy

| Failure type | Blocks pipeline? | Example |
|---|---|---|
| Blocking failure | Yes | Stage 1: `menu_verified` missing; Stage 2: API error; Stage 3: verification FAIL; Stage 4: critical violation |
| Non-blocking failure | No | Stage 4: medium violation; Stage 5: `needs_review` restaurant (unless `--require-fresh`) |
| Warning | No | Stage 1: non-canonical type values; Stage 3: unresolvable blanks |

Stage 7 (Health Report) never produces a blocking failure. It always runs as the final step regardless of what happened before it.

### Context persistence

After each stage completes, context is serialized to:
```
pipeline_runs/{run_id}/context.json
pipeline_runs/{run_id}/stage_{N}_result.json
```

This allows:
- Inspection of any stage's result after the run
- Resuming a failed run with `--resume {run_id}`
- Debugging by examining intermediate state

---

## Pipeline Report Storage

Pipeline reports are archived permanently:
```
goldpan/
  pipeline_runs/
    {run_id}/
      context.json
      stage_1_result.json
      stage_2_result.json
      ...
      pipeline_report.json
  pipeline_reports/
    pipeline_{run_id}.json      ← permanent archive copy
    pipeline_{YYYY-MM-DD}.json  ← latest run on each date (symlink or copy)
```

`pipeline_reports/` accumulates the record of every pipeline run. It is the audit trail for all database changes. A database change without a corresponding pipeline report is an untracked change.

---

## Stage Dependency Map

```
Stage 1 → Stage 2 → Stage 3 → Stage 4 → Stage 5 → Stage 6 → Stage 7
   ↑                                        ↑
  (staging_file)                     (freshness_map from 5a
                                      → engine in 5b)
```

Strict sequential dependency — no stages run in parallel. This keeps the model simple and the sheet state predictable at each step.

**What each stage requires from the previous:**

| Stage | Requires from context |
|---|---|
| 1 | `staging_file` (from CLI) |
| 2 | `staging_file`, `restaurant_id`, `dish_ids_staged` |
| 3 | `dish_ids_upserted` |
| 4 | (none — reads live from sheet) |
| 5a | (none — reads live from sheet) |
| 5b | `freshness_map` (from 5a) |
| 6 | `derived_filters_path` |
| 7 | `stage_results` (all of them) |

---

## What the Orchestrator Explicitly Does Not Do

- **Does not contain validation logic.** Validation rules belong in `validate_staging.py` and `validate_database.py`.
- **Does not contain upsert logic.** Row construction and sheet writes belong in `upsert_dishes.py`.
- **Does not contain enrichment logic.** Field resolution belongs in `backfill_enrichment.py`.
- **Does not contain business rules.** All rules are in the Rules Registry and enforced by the scripts that implement them.
- **Does not deploy.** The pipeline produces `dishes.json` and `restaurants.json`. Deployment (git push) is a separate, intentional human action or a separate CI step. The pipeline does not push.
- **Does not retry.** If a stage fails, the pipeline stops. Retrying is the operator's decision after investigating the failure.
- **Does not make schema decisions.** If a field is wrong, the pipeline reports it. Fixing schema issues requires a human decision and a new pipeline run.

---

## Implementation Order

Phase 1 — Orchestrator scaffold:
1. Create `pipeline.py` with the execution loop, context model, and StageResult interface
2. Stub each stage as a pass-through that returns a mock StageResult
3. Verify the orchestrator runs end-to-end and produces a Pipeline Report from stub results

Phase 2 — Wire real stages:
4. Wire Stage 1 to `validate_staging.py` (create `validate_staging.py` first — see Architectural Health Review Finding 7)
5. Wire Stage 2 to `upsert_dishes.py` (update it to return a structured StageResult)
6. Wire Stage 3 to `backfill_enrichment.py` (already returns structured output)
7. Wire Stage 4 to `validate_database.py`
8. Wire Stage 5 to `check_freshness.py` + `compute_derived_filters.py`
9. Wire Stage 6 to `fetch_dishes.py` (update to consume `derived_filters.json`)

Phase 3 — Hardening:
10. Implement `--resume` with context persistence
11. Implement `--from-stage` and `--through-stage`
12. Add `pipeline_reports/` archive
13. Write unit tests for the orchestrator execution loop

The orchestrator scaffold (Phase 1) can be built and tested before any scripts are updated. Each script is wired in one at a time, making the integration verifiable at each step.
