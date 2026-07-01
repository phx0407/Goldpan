"""
pipeline.py — GoldPan canonical update pipeline.

Runs the full data update sequence in order:

  Step 1  validate_staging     — pre-flight: all staging files must pass
  Step 2  backfill_enrichment  — fill blank enrichment fields in Ingredient Details
  Step 3  compute_derived_filters — recompute derived filter conclusions → derived_filters.json
  Step 4  fetch_dishes         — join sheets + derived filters → dishes.json + restaurants.json
  Step 5  verify               — confirm output files are valid JSON with expected shape

Dry-run by default: steps 2–4 run in report-only mode (no writes).
Use --apply to execute all writes.

Usage:
    python3 pipeline.py                  # dry run — report only
    python3 pipeline.py --apply          # full run — writes all outputs
    python3 pipeline.py --from=3         # resume from step 3 (skip 1-2)
    python3 pipeline.py --only=1         # run step 1 only
    python3 pipeline.py --skip=2         # skip step 2, run rest

Flags:
    --apply          Write outputs (default: dry run)
    --from=N         Start from step N (1-5)
    --only=N         Run only step N
    --skip=N[,N...]  Skip step(s) N
    --no-color       Disable ANSI color output

Exit codes:
    0  All steps passed
    1  One or more steps failed
    2  Usage error
"""

import json
import os
import re as _re
import sys
import subprocess
import datetime
import time

# ── Config ────────────────────────────────────────────────────────────────────

GOLDPAN_DIR  = os.path.dirname(os.path.abspath(__file__))
TODAY        = datetime.date.today().isoformat()
DRY_RUN      = "--apply" not in sys.argv
NO_COLOR     = "--no-color" in sys.argv or not sys.stdout.isatty()

DERIVED_FILTERS_FILE = os.path.join(GOLDPAN_DIR, "derived_filters.json")
DISHES_FILE          = os.path.join(GOLDPAN_DIR, "dishes.json")
RESTAURANTS_FILE     = os.path.join(GOLDPAN_DIR, "restaurants.json")

DOCS_DIR         = os.path.join(GOLDPAN_DIR, "docs")
LAST_RUN_FILE    = os.path.join(DOCS_DIR, "pipeline_last_run.json")
HISTORY_FILE     = os.path.join(DOCS_DIR, "pipeline_history.jsonl")

# Minimum expected counts — alert if output falls below these
MIN_DISHES      = 600
MIN_RESTAURANTS = 20
MIN_DERIVED     = 500


# ── ANSI helpers ──────────────────────────────────────────────────────────────

def _c(code: str, text: str) -> str:
    if NO_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"

GREEN  = lambda t: _c("32", t)
RED    = lambda t: _c("31", t)
YELLOW = lambda t: _c("33", t)
BOLD   = lambda t: _c("1",  t)
DIM    = lambda t: _c("2",  t)


# ── Step result ───────────────────────────────────────────────────────────────

class StepResult:
    def __init__(self, name: str):
        self.name    = name
        self.status  = "pending"   # pending | ok | warning | failed | skipped
        self.elapsed = 0.0
        self.notes   = []          # list of str

    def ok(self, note: str = ""):
        self.status = "ok"
        if note:
            self.notes.append(note)

    def warn(self, note: str):
        self.status = "warning"
        self.notes.append(note)

    def fail(self, note: str):
        self.status = "failed"
        self.notes.append(note)

    def skip(self, reason: str = ""):
        self.status = "skipped"
        if reason:
            self.notes.append(reason)

    @property
    def icon(self) -> str:
        return {
            "ok":      GREEN("✓"),
            "warning": YELLOW("⚠"),
            "failed":  RED("✗"),
            "skipped": DIM("–"),
            "pending": " ",
        }.get(self.status, "?")

    def to_dict(self, num: int = 0) -> dict:
        return {
            "num":     num,
            "name":    self.name,
            "status":  self.status,
            "elapsed": round(self.elapsed, 2),
            "notes":   [_re.sub(r'\033\[[0-9;]*m', '', n) for n in self.notes],
        }


# ── Argument parsing ──────────────────────────────────────────────────────────

def _parse_args():
    args  = sys.argv[1:]
    from_step = 1
    only_step = None
    skip_steps = set()

    for a in args:
        if a.startswith("--from="):
            try:
                from_step = int(a.split("=", 1)[1])
            except ValueError:
                print(f"Error: --from= requires an integer (got {a})", file=sys.stderr)
                sys.exit(2)
        elif a.startswith("--only="):
            try:
                only_step = int(a.split("=", 1)[1])
            except ValueError:
                print(f"Error: --only= requires an integer (got {a})", file=sys.stderr)
                sys.exit(2)
        elif a.startswith("--skip="):
            for part in a.split("=", 1)[1].split(","):
                try:
                    skip_steps.add(int(part.strip()))
                except ValueError:
                    print(f"Error: --skip= requires integer(s) (got {a})", file=sys.stderr)
                    sys.exit(2)

    return from_step, only_step, skip_steps


def should_run(step_num: int, from_step: int, only_step, skip_steps: set) -> bool:
    if only_step is not None:
        return step_num == only_step
    if step_num < from_step:
        return False
    if step_num in skip_steps:
        return False
    return True


# ── Step implementations ──────────────────────────────────────────────────────

def step_validate_staging(dry_run: bool) -> StepResult:
    """Step 1: validate all staging files. Fails on any ERROR finding."""
    r = StepResult("validate_staging (all files)")
    script = os.path.join(GOLDPAN_DIR, "validate_staging.py")

    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, script, "--all"],
        capture_output=True, text=True, cwd=GOLDPAN_DIR
    )
    r.elapsed = time.monotonic() - t0

    # Parse summary lines from output:
    #   Files:    22 total  /  22 passed  /  0 failed
    #   Findings: 0 error(s)  /  290 warning(s)
    total = passed = failed = warnings = None
    for line in proc.stdout.splitlines():
        m = _re.search(r'Files:\s+(\d+) total\s*/\s*(\d+) passed\s*/\s*(\d+) failed', line)
        if m:
            total, passed, failed = int(m.group(1)), int(m.group(2)), int(m.group(3))
        m2 = _re.search(r'Findings:.*?/\s*(\d+) warning', line)
        if m2:
            warnings = int(m2.group(1))

    if proc.returncode != 0:
        r.fail(f"{failed or '?'} file(s) failed validation — pipeline cannot continue")
        if failed is not None:
            r.notes.append(f"Run: python3 validate_staging.py --all  for full details")
    else:
        summary = f"{passed or '?'}/{total if passed is not None else '?'} files passed"
        if warnings:
            summary += f" · {warnings} warning(s)"
        r.ok(summary)

    return r


def step_backfill_enrichment(dry_run: bool) -> StepResult:
    """Step 2: backfill blank enrichment fields in Ingredient Details."""
    r = StepResult("backfill_enrichment")
    script = os.path.join(GOLDPAN_DIR, "backfill_enrichment.py")

    cmd = [sys.executable, script]
    if not dry_run:
        cmd.append("--apply")

    t0 = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=GOLDPAN_DIR)
    r.elapsed = time.monotonic() - t0

    if proc.returncode != 0:
        r.fail(f"backfill_enrichment.py exited {proc.returncode}")
        # Show last few lines of stderr for context
        err_lines = [l for l in (proc.stderr or proc.stdout).splitlines() if l.strip()]
        for line in err_lines[-5:]:
            r.notes.append(DIM(f"  {line}"))
    else:
        # Try to extract fill count from output
        fills = needs = 0
        for line in proc.stdout.splitlines():
            if "populated" in line.lower() or "fill" in line.lower():
                try:
                    fills += int(line.strip().split()[0])
                except (ValueError, IndexError):
                    pass
            if "needs canvassing" in line.lower():
                try:
                    needs = int(line.strip().split()[0])
                except (ValueError, IndexError):
                    pass
        mode = "dry run" if dry_run else "applied"
        note = f"[{mode}]"
        if fills:
            note += f" · {fills} field(s) filled"
        if needs:
            note += f" · {needs} row(s) need canvassing"
        r.ok(note)

    return r


def step_compute_derived_filters(dry_run: bool) -> StepResult:
    """Step 3: recompute derived filter conclusions → derived_filters.json."""
    r = StepResult("compute_derived_filters")
    script = os.path.join(GOLDPAN_DIR, "compute_derived_filters.py")

    cmd = [sys.executable, script]
    if not dry_run:
        cmd.append("--apply")

    t0 = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=GOLDPAN_DIR)
    r.elapsed = time.monotonic() - t0

    if proc.returncode != 0:
        r.fail(f"compute_derived_filters.py exited {proc.returncode}")
        err_lines = [l for l in (proc.stderr or proc.stdout).splitlines() if l.strip()]
        for line in err_lines[-5:]:
            r.notes.append(DIM(f"  {line}"))
        return r

    # Parse counts from output
    total = computed = not_applicable = dep_not_met = 0
    for line in proc.stdout.splitlines():
        low = line.lower()
        if "total dishes" in low or "dishes processed" in low:
            try: total = int(line.strip().split()[-1])
            except (ValueError, IndexError): pass
        if "computed" in low and "not_applicable" not in low and "not applicable" not in low:
            try: computed = int(line.strip().split()[-1])
            except (ValueError, IndexError): pass
        if "not applicable" in low or "not_applicable" in low:
            try: not_applicable = int(line.strip().split()[-1])
            except (ValueError, IndexError): pass
        if "dependency not met" in low:
            try: dep_not_met = int(line.strip().split()[-1])
            except (ValueError, IndexError): pass

    mode = "dry run" if dry_run else "written"
    note = f"[{mode}]"
    if total:
        note += f" · {total} dishes"
    if computed:
        note += f" · {computed} computed"
    if dep_not_met:
        note += f" · {dep_not_met} dependency-not-met (see CL-001)"

    if not dry_run:
        # Verify output file was written
        if os.path.exists(DERIVED_FILTERS_FILE):
            try:
                with open(DERIVED_FILTERS_FILE) as f:
                    df = json.load(f)
                if len(df) < MIN_DERIVED:
                    r.warn(f"derived_filters.json has only {len(df)} entries (expected ≥{MIN_DERIVED})")
                    return r
                note += f" · {len(df)} entries in derived_filters.json"
            except json.JSONDecodeError:
                r.fail("derived_filters.json is not valid JSON after write")
                return r
        else:
            r.fail("derived_filters.json not found after --apply")
            return r

    r.ok(note)
    return r


def step_fetch_dishes(dry_run: bool) -> StepResult:
    """Step 4: join sheets + derived_filters.json → dishes.json + restaurants.json."""
    r = StepResult("fetch_dishes")
    script = os.path.join(GOLDPAN_DIR, "fetch_dishes.py")

    if dry_run:
        # fetch_dishes.py has no dry-run mode; skip write but report
        r.skip("fetch_dishes.py has no dry-run mode — will run in --apply only")
        return r

    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, script],
        capture_output=True, text=True, cwd=GOLDPAN_DIR
    )
    r.elapsed = time.monotonic() - t0

    if proc.returncode != 0:
        r.fail(f"fetch_dishes.py exited {proc.returncode}")
        err_lines = [l for l in (proc.stderr or proc.stdout).splitlines() if l.strip()]
        for line in err_lines[-5:]:
            r.notes.append(DIM(f"  {line}"))
        return r

    # Parse exported count
    # fetch_dishes.py prints:
    #   "  Total dishes exported:        686"
    #   "  Dishes with derived filters:  686"
    exported = with_filters = 0
    for line in proc.stdout.splitlines():
        low = line.lower()
        if "total dishes exported" in low or "dishes written" in low:
            try: exported = int(line.strip().split()[-1])
            except (ValueError, IndexError): pass
        if "dishes with derived filters" in low or "with derived" in low:
            try: with_filters = int(line.strip().split()[-1])
            except (ValueError, IndexError): pass

    r.ok(f"{exported} dishes exported · {with_filters} with derived_filters")
    return r


def step_verify(dry_run: bool) -> StepResult:
    """Step 5: verify output files are valid JSON with expected shape."""
    r = StepResult("verify outputs")
    issues = []
    notes  = []

    def check_json(path: str, label: str, min_count: int, id_key: str):
        if not os.path.exists(path):
            issues.append(f"{label}: file not found")
            return
        try:
            with open(path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            issues.append(f"{label}: invalid JSON — {e}")
            return
        count = len(data)
        if count < min_count:
            issues.append(f"{label}: only {count} entries (expected ≥{min_count})")
        else:
            notes.append(f"{label}: {count} entries ✓")
        # Check ID key presence
        if data and id_key:
            missing = sum(1 for item in data if not item.get(id_key))
            if missing:
                issues.append(f"{label}: {missing} entries missing '{id_key}'")

    if not dry_run:
        check_json(DISHES_FILE,      "dishes.json",      MIN_DISHES,      "id")
        check_json(RESTAURANTS_FILE, "restaurants.json", MIN_RESTAURANTS, "name")
        check_json(DERIVED_FILTERS_FILE, "derived_filters.json", MIN_DERIVED, None)
    else:
        # In dry-run, just check existing files
        check_json(DISHES_FILE,      "dishes.json",      MIN_DISHES,      "id")
        check_json(DERIVED_FILTERS_FILE, "derived_filters.json", MIN_DERIVED, None)

    r.elapsed = 0.0
    if issues:
        for issue in issues:
            r.fail(issue)
        for note in notes:
            r.notes.append(note)
    else:
        for note in notes:
            r.notes.append(note)
        r.ok()

    return r


# ── Reporting ─────────────────────────────────────────────────────────────────

STEPS = [
    (1, "Validate staging files",        step_validate_staging),
    (2, "Backfill enrichment",           step_backfill_enrichment),
    (3, "Compute derived filters",       step_compute_derived_filters),
    (4, "Fetch dishes (write outputs)",  step_fetch_dishes),
    (5, "Verify outputs",                step_verify),
]


def print_header(dry_run: bool):
    mode = DIM("DRY RUN — no writes") if dry_run else BOLD("APPLY — writing outputs")
    print()
    print(BOLD(f"GoldPan Pipeline  —  {TODAY}"))
    print(f"Mode: {mode}")
    print("─" * 60)


def print_step_start(num: int, label: str):
    print(f"\n  {BOLD(f'[{num}/5]')} {label}")


def print_step_result(r: StepResult):
    elapsed = f" ({r.elapsed:.1f}s)" if r.elapsed > 0.1 else ""
    print(f"        {r.icon}  {r.status.upper()}{elapsed}")
    for note in r.notes:
        print(f"           {note}")


def print_summary(results: list):
    print()
    print("─" * 60)
    print(BOLD("  Pipeline Summary"))
    print()

    status_counts = {}
    for r in results:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    ok      = status_counts.get("ok", 0)
    warned  = status_counts.get("warning", 0)
    failed  = status_counts.get("failed", 0)
    skipped = status_counts.get("skipped", 0)

    for r in results:
        elapsed = f"  ({r.elapsed:.1f}s)" if r.elapsed > 0.1 else ""
        print(f"  {r.icon}  {r.name}{DIM(elapsed)}")

    print()
    parts = []
    if ok:      parts.append(GREEN(f"{ok} passed"))
    if warned:  parts.append(YELLOW(f"{warned} warned"))
    if failed:  parts.append(RED(f"{failed} failed"))
    if skipped: parts.append(DIM(f"{skipped} skipped"))
    print("  " + "  ·  ".join(parts))

    if failed:
        print()
        print(RED("  Pipeline FAILED — see step output above for details."))
    elif warned:
        print()
        print(YELLOW("  Pipeline completed with warnings — review before deploying."))
    else:
        print()
        print(GREEN("  Pipeline PASSED."))

    print("─" * 60)
    print()


# ── Run history ───────────────────────────────────────────────────────────────

def write_run_record(
    results: list,
    pipeline_failed: bool,
    dry_run: bool,
    total_elapsed: float,
    from_step: int,
    only_step,
    skip_steps: set,
):
    """
    Write pipeline run record to:
      docs/pipeline_last_run.json  — always overwritten (current state)
      docs/pipeline_history.jsonl  — appended (one JSON object per line)

    ANSI escape codes are stripped from notes before writing.
    """
    status_counts = {}
    for r in results:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    overall = "failed" if pipeline_failed else (
        "warned" if status_counts.get("warning", 0) else "passed"
    )

    record = {
        "timestamp":     datetime.datetime.now().isoformat(timespec="seconds"),
        "date":          TODAY,
        "mode":          "dry_run" if dry_run else "apply",
        "overall":       overall,
        "total_elapsed": round(total_elapsed, 2),
        "passed":        status_counts.get("ok", 0),
        "warned":        status_counts.get("warning", 0),
        "failed":        status_counts.get("failed", 0),
        "skipped":       status_counts.get("skipped", 0),
        "from_step":     from_step,
        "only_step":     only_step,
        "skip_steps":    sorted(skip_steps),
        "steps": [
            r.to_dict(num=i + 1)
            for i, r in enumerate(results)
        ],
    }

    os.makedirs(DOCS_DIR, exist_ok=True)

    with open(LAST_RUN_FILE, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    from_step, only_step, skip_steps = _parse_args()
    print_header(DRY_RUN)

    results = []
    pipeline_failed = False
    pipeline_start = time.monotonic()

    for num, label, fn in STEPS:
        if not should_run(num, from_step, only_step, skip_steps):
            r = StepResult(label)
            r.skip()
            results.append(r)
            continue

        print_step_start(num, label)
        r = fn(DRY_RUN)
        r.name = label
        print_step_result(r)
        results.append(r)

        # Abort rules:
        #   Step 1 (validate) fail → abort everything: bad staging = bad data
        #   Step 3 (compute)  fail → abort step 4: fetch with stale derived_filters is wrong
        if r.status == "failed":
            pipeline_failed = True
            abort = num in (1, 3)
            if abort:
                msg = {
                    1: "Step 1 failed — aborting pipeline. Fix validation errors first.",
                    3: "Step 3 failed — skipping fetch_dishes to avoid stale derived_filters.",
                }.get(num, f"Step {num} failed — aborting pipeline.")
                print()
                print(RED(f"  {msg}"))
                # Mark remaining steps skipped
                for remaining_num, remaining_label, _ in STEPS[num:]:
                    if should_run(remaining_num, from_step, only_step, skip_steps):
                        rr = StepResult(remaining_label)
                        rr.skip("Skipped: upstream failure")
                        results.append(rr)
                break

    total_elapsed = time.monotonic() - pipeline_start
    print_summary(results)
    write_run_record(results, pipeline_failed, DRY_RUN, total_elapsed,
                     from_step, only_step, skip_steps)
    sys.exit(1 if pipeline_failed else 0)


if __name__ == "__main__":
    main()
