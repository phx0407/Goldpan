"""
freshness.py — GoldPan freshness computation module.

Two-track freshness architecture per GP-RULE-008 v1.1:

  Track A — Source Check:
    Automated monitoring of public sources.
    Computes: Source_Check_Status
    Never modifies GoldPan evidence.

  Track B — Recanvass:
    Human-driven evidence acquisition.
    Computes: Recanvass_Status — the synthesized verdict.
    This is the only signal the derived filter engine reads.

Contract:
  - freshness.py synthesizes both tracks into Recanvass_Status.
  - The engine (derived/engine.py) reads only Recanvass_Status.
  - Source_Check_Status feeds into Recanvass_Status computation here.
    The engine never sees raw source-check details.

Governed by:
  GP-RULE-008 v1.1 (Data Freshness Rule)
  GP-RULE-009 v1.0 (Stale Evidence Confidence Degradation Rule)

Public API:
  compute_freshness_map(rows, today=None)
      → dict[str, FreshnessRecord]

  compute_restaurant_status(row, today=None)
      → FreshnessRecord

  days_since(date_str, today=None)
      → Optional[int]

  freshness_summary(freshness_map)
      → dict
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Optional


# ── Tier windows ──────────────────────────────────────────────────────────────
#
# Independent windows for each track per GP-RULE-008 v1.1.
#
# Source check: how often should the public source be monitored?
# Recanvass:    how often must evidence be fully re-acquired?
#
# The due_soon window is a 14-day lead before the recanvass window boundary.

TIER_SOURCE_CHECK_WINDOWS: dict[int, int] = {
    1: 7,    # Tier 1 — high-change restaurants: weekly
    2: 14,   # Tier 2 — standard: biweekly
    3: 30,   # Tier 3 — stable menus: monthly
}

TIER_RECANVASS_WINDOWS: dict[int, int] = {
    1: 30,   # Tier 1 — 30 days
    2: 90,   # Tier 2 — 90 days (default)
    3: 180,  # Tier 3 — 180 days
}

DEFAULT_TIER     = 2
DUE_SOON_LEAD    = 14   # days before recanvass window expiry → "due_soon"


# ── FreshnessRecord ───────────────────────────────────────────────────────────

@dataclass
class FreshnessRecord:
    """
    The computed freshness state for one restaurant.

    Two tracks are computed independently, then synthesized into Recanvass_Status.

    source_check_status values:
        "ok"          — source reachable, no changes detected within window
        "changed"     — source content appears to have changed
        "unreachable" — source URL returned 404/error/timeout
        "overdue"     — source check window expired without a new check
        "unknown"     — never checked (Last_Source_Check blank)

    status (= Recanvass_Status) values:
        "current"      — within recanvass window; no active triggers
        "due_soon"     — within 14 days of window boundary; still fresh
        "overdue"      — past recanvass window; confidence capped (GP-RULE-009)
        "needs_review" — active trigger fired; derived conclusions suppressed
        "unknown"      — freshness cannot be computed (no restaurant_id or data)

    triggers: list of human-readable strings explaining what fired needs_review.
    """
    # Identity
    restaurant_id:          str
    restaurant_name:        str

    # Synthesized verdict (the only field the engine reads)
    status:                 str        # current | due_soon | overdue | needs_review | unknown

    # Track A — Source Check
    source_check_status:    str        # ok | changed | unreachable | overdue | unknown
    last_source_check:      Optional[str]
    source_check_window:    int        # days, derived from tier

    # Track B — Recanvass
    recanvass_window:       int        # days, derived from tier
    last_canvassed:         Optional[str]
    menu_changed:           str        # yes | no | unknown | ""
    forced_recanvass:       bool
    days_since_canvass:     Optional[int]
    days_overdue:           int
    days_remaining:         int

    # Common
    recanvass_tier:         int
    triggers:               list = field(default_factory=list)
    computed_date:          str = ""

    def to_context_dict(self) -> dict:
        """Return the subset of fields for embedding in derived_filters.json."""
        return {
            "recanvass_status":    self.status,
            "source_check_status": self.source_check_status,
            "last_canvassed":      self.last_canvassed,
            "last_source_check":   self.last_source_check,
            "status_computed_date": self.computed_date,
        }


# ── Date utilities ────────────────────────────────────────────────────────────

def _today() -> datetime.date:
    return datetime.date.today()


def days_since(date_str: Optional[str], today: Optional[datetime.date] = None) -> Optional[int]:
    """
    Days between date_str (YYYY-MM-DD) and today.
    Returns None if date_str is blank, None, or unparseable.
    """
    if not date_str:
        return None
    try:
        parsed = datetime.date.fromisoformat(str(date_str).strip())
        return ((today or _today()) - parsed).days
    except ValueError:
        return None


# ── Track A: Source Check Status ──────────────────────────────────────────────

def _compute_source_check_status(
    row: dict,
    tier: int,
    today: datetime.date,
) -> str:
    """
    Compute Source_Check_Status for one restaurant.

    Priority order:
      1. Blank Last_Source_Check                → "unknown"
      2. Stored status "changed" or "unreachable" → propagate (active signals)
      3. Source check window expired             → "overdue"
      4. Stored status "ok" within window       → "ok"
      5. Default                                → "unknown"

    NOTE: The "unknown" case (blank Last_Source_Check) does NOT automatically
    trigger needs_review in Phase 1 — it is a soft warning only. This prevents
    suppressing all derived conclusions before check_sources.py is deployed.
    Enable the trigger in _evaluate_triggers() once source checking is active.
    """
    last_src_check = str(row.get("Last_Source_Check", "")).strip() or None
    stored_status  = str(row.get("Source_Check_Status", "")).strip().lower()

    if not last_src_check:
        return "unknown"

    # Active escalation signals from check_sources.py — propagate as-is
    if stored_status in ("changed", "unreachable"):
        return stored_status

    # Check whether the source check window has lapsed
    window = TIER_SOURCE_CHECK_WINDOWS.get(tier, TIER_SOURCE_CHECK_WINDOWS[DEFAULT_TIER])
    ds = days_since(last_src_check, today)
    if ds is not None and ds > window:
        return "overdue"

    return stored_status if stored_status == "ok" else "unknown"


# ── Track B: Recanvass Triggers ───────────────────────────────────────────────

def _evaluate_triggers(
    row: dict,
    source_check_status: str,
) -> list[str]:
    """
    Return a list of active trigger strings that set Recanvass_Status = "needs_review".
    Empty list → no triggers → proceed with date-window calculation.

    Source_Check_Status is synthesized before this call. The trigger logic
    reads the synthesized status, not the raw stored field.
    """
    triggers = []

    # Forced flag — highest priority
    forced = str(row.get("Forced_Recanvass_Flag", "")).strip().lower()
    if forced == "yes":
        triggers.append(
            "Forced_Recanvass_Flag = 'yes' — manually flagged for immediate recanvass"
        )

    # Never canvassed
    if not str(row.get("Last_Canvassed", "")).strip():
        triggers.append(
            "Last_Canvassed is blank — restaurant has not yet been fully canvassed"
        )

    # Source check signals (synthesized by Track A before this call)
    if source_check_status == "changed":
        triggers.append(
            "Source_Check_Status = 'changed' — public source content appears to have changed"
        )
    elif source_check_status == "unreachable":
        triggers.append(
            "Source_Check_Status = 'unreachable' — source URL is not responding"
        )
    # NOTE: source_check_status == "unknown" (never checked) is a soft warning only in Phase 1.
    # Uncomment the block below once check_sources.py is deployed and all restaurants
    # have at least one source check on record:
    #
    # elif source_check_status == "unknown":
    #     triggers.append(
    #         "Last_Source_Check is blank — source has never been confirmed live"
    #     )

    # Unresolved canvass outcome
    menu_changed = str(row.get("Menu_Changed", "")).strip().lower()
    if menu_changed == "unknown":
        triggers.append(
            "Menu_Changed = 'unknown' — last canvass outcome was not resolved"
        )

    # Source platform changed — must recanvass against new source
    change_type = str(row.get("Change_Type", "")).strip().lower()
    if "source_changed" in change_type:
        triggers.append(
            "Change_Type includes 'source_changed' — source platform changed; "
            "recanvass against new source required"
        )

    return triggers


# ── Per-restaurant computation ────────────────────────────────────────────────

def compute_restaurant_status(
    row: dict,
    today: Optional[datetime.date] = None,
) -> FreshnessRecord:
    """
    Compute the full FreshnessRecord for one Menu Source Registry row.

    Computation order:
      1. Parse tier and derive windows
      2. Track A: compute Source_Check_Status
      3. Track B: evaluate triggers (using Track A result)
      4. Track B: if no triggers, compute from recanvass date window

    The synthesized verdict (status / Recanvass_Status) is always the last field set.
    Source_Check_Status is an intermediate; it never reaches the engine directly.
    """
    ref       = today or _today()
    today_str = ref.isoformat()

    rid   = str(row.get("Restaurant_ID", "")).strip()
    rname = str(row.get("Restaurant_Name", "")).strip()

    # ── Tier ──────────────────────────────────────────────────────────────────
    try:
        tier = int(str(row.get("Recanvass_Tier", DEFAULT_TIER)).strip())
        if tier not in TIER_RECANVASS_WINDOWS:
            tier = DEFAULT_TIER
    except (ValueError, TypeError):
        tier = DEFAULT_TIER

    recanvass_window      = TIER_RECANVASS_WINDOWS[tier]
    source_check_window   = TIER_SOURCE_CHECK_WINDOWS[tier]

    last_canvassed    = str(row.get("Last_Canvassed", "")).strip() or None
    last_source_check = str(row.get("Last_Source_Check", "")).strip() or None
    menu_changed      = str(row.get("Menu_Changed", "")).strip()
    forced_recanvass  = str(row.get("Forced_Recanvass_Flag", "")).strip().lower() == "yes"

    # ── Track A: Source Check ─────────────────────────────────────────────────
    src_check_status = _compute_source_check_status(row, tier, ref)

    # ── Track B step 1: triggers ──────────────────────────────────────────────
    triggers = _evaluate_triggers(row, src_check_status)

    ds_canvass = days_since(last_canvassed, ref)

    if triggers:
        return FreshnessRecord(
            restaurant_id=rid,
            restaurant_name=rname,
            status="needs_review",
            source_check_status=src_check_status,
            last_source_check=last_source_check,
            source_check_window=source_check_window,
            recanvass_window=recanvass_window,
            last_canvassed=last_canvassed,
            menu_changed=menu_changed,
            forced_recanvass=forced_recanvass,
            days_since_canvass=ds_canvass,
            days_overdue=0,
            days_remaining=0,
            recanvass_tier=tier,
            triggers=triggers,
            computed_date=today_str,
        )

    # ── Track B step 2: date-window calculation ───────────────────────────────
    # Triggers cleared; Last_Canvassed must be present (blank trigger would have fired)
    assert ds_canvass is not None, (
        f"ds_canvass should be set for {rid} — blank Last_Canvassed trigger should have fired"
    )

    if ds_canvass > recanvass_window:
        status        = "overdue"
        days_overdue  = ds_canvass - recanvass_window
        days_remaining = 0
    elif ds_canvass > (recanvass_window - DUE_SOON_LEAD):
        status        = "due_soon"
        days_overdue  = 0
        days_remaining = recanvass_window - ds_canvass
    else:
        status        = "current"
        days_overdue  = 0
        days_remaining = recanvass_window - ds_canvass

    return FreshnessRecord(
        restaurant_id=rid,
        restaurant_name=rname,
        status=status,
        source_check_status=src_check_status,
        last_source_check=last_source_check,
        source_check_window=source_check_window,
        recanvass_window=recanvass_window,
        last_canvassed=last_canvassed,
        menu_changed=menu_changed,
        forced_recanvass=forced_recanvass,
        days_since_canvass=ds_canvass,
        days_overdue=days_overdue,
        days_remaining=days_remaining,
        recanvass_tier=tier,
        triggers=[],
        computed_date=today_str,
    )


# ── Batch computation ─────────────────────────────────────────────────────────

def compute_freshness_map(
    rows: list[dict],
    today: Optional[datetime.date] = None,
) -> dict[str, FreshnessRecord]:
    """
    Compute FreshnessRecord for every row in the Menu Source Registry.

    Returns: {restaurant_id: FreshnessRecord}

    Rows without a Restaurant_ID are skipped with a warning.
    """
    result: dict[str, FreshnessRecord] = {}
    today_str = (today or _today()).isoformat()

    for row in rows:
        rid = str(row.get("Restaurant_ID", "")).strip()
        if not rid:
            rname = str(row.get("Restaurant_Name", "(unknown)")).strip()
            print(f"  [freshness] WARNING: skipping row with no Restaurant_ID — '{rname}'")
            continue
        rec = compute_restaurant_status(row, today)
        rec.computed_date = today_str
        result[rid] = rec

    return result


# ── Summary helpers ───────────────────────────────────────────────────────────

def freshness_summary(freshness_map: dict[str, FreshnessRecord]) -> dict:
    """
    Aggregate freshness counts and compute the freshness score.

    Freshness Score = (current + due_soon) / total × 100
    Target: ≥ 80%. Critical: 0 needs_review.
    """
    counts: dict[str, int] = {
        "current": 0, "due_soon": 0, "overdue": 0,
        "needs_review": 0, "unknown": 0,
    }
    for rec in freshness_map.values():
        counts[rec.status] = counts.get(rec.status, 0) + 1

    total = sum(counts.values())
    fresh = counts["current"] + counts["due_soon"]
    score = round(fresh / total * 100) if total else 0

    return {
        **counts,
        "total":           total,
        "freshness_score": score,
        "target_met":      score >= 80,
        "critical_ok":     counts["needs_review"] == 0,
    }
