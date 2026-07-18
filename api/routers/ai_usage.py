"""
api/routers/ai_usage.py — AI Usage OS reporting endpoints

Endpoints:
  GET /admin/ai-usage/report     — full usage report (spend, tokens, calls, errors)
  GET /admin/ai-usage/controls   — raw budget_controls row (admin view)

All endpoints require X-Admin-Key header.
Data source: operations.ai_usage_logs + operations.budget_controls.

Python 3.9 compatible — uses typing.List / Dict / Tuple / Optional throughout.
No `X | None` or lowercase generic aliases in annotations.
"""

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from supabase import Client as SupabaseClient

from api.deps import get_supabase, verify_admin_key

router = APIRouter(prefix="/admin/ai-usage", tags=["AI Usage"])


# ══════════════════════════════════════════════════════════════════════════════
# Response models
# ══════════════════════════════════════════════════════════════════════════════

class SpendSummary(BaseModel):
    today_usd:              float = Field(description="Total estimated spend today (UTC)")
    month_usd:              float = Field(description="Total estimated spend this calendar month (UTC)")
    daily_limit_usd:        float = Field(description="Daily budget limit from budget_controls")
    monthly_limit_usd:      float = Field(description="Monthly budget limit from budget_controls")
    daily_remaining_usd:    float = Field(description="Daily budget remaining")
    monthly_remaining_usd:  float = Field(description="Monthly budget remaining")
    daily_pct_used:         float = Field(description="Daily budget used, 0–100")
    monthly_pct_used:       float = Field(description="Monthly budget used, 0–100")


class TokenSummary(BaseModel):
    today_input:   int
    today_output:  int
    today_total:   int
    month_input:   int
    month_output:  int
    month_total:   int


class PurposeBreakdown(BaseModel):
    purpose:        str
    calls:          int
    total_cost_usd: float
    input_tokens:   int
    output_tokens:  int


class ModelBreakdown(BaseModel):
    model:          str
    calls:          int
    total_cost_usd: float
    input_tokens:   int
    output_tokens:  int


class CallSummary(BaseModel):
    today_total:  int                    = Field(description="Total calls today (excludes budget_exceeded)")
    month_total:  int                    = Field(description="Total calls this month (excludes budget_exceeded)")
    by_purpose:   List[PurposeBreakdown] = Field(description="Month-to-date, sorted by call count desc")
    by_model:     List[ModelBreakdown]   = Field(description="Month-to-date, sorted by call count desc")


class RecentError(BaseModel):
    log_id:        str
    created_at:    str
    status:        str
    model:         str
    purpose:       str
    error_message: Optional[str]
    latency_ms:    Optional[int]
    session_id:    Optional[str]


class ErrorSummary(BaseModel):
    budget_exceeded_today:  int               = Field(description="budget_exceeded rows today")
    budget_exceeded_month:  int               = Field(description="budget_exceeded rows this month")
    errors_today:           int               = Field(description="error + timeout rows today")
    errors_month:           int               = Field(description="error + timeout rows this month")
    recent:                 List[RecentError] = Field(description="10 most recent error/timeout rows")


class BudgetFlags(BaseModel):
    ask_goldpan_enabled:          bool
    ask_goldpan_daily_limit_usd:  float
    ask_goldpan_monthly_limit_usd: float
    ag_spend_today_usd:           float
    ag_spend_month_usd:           float
    intake_ai_enabled:            bool
    governance_ai_enabled:        bool


class AIUsageReport(BaseModel):
    generated_at: str = Field(description="ISO 8601 UTC timestamp of report generation")
    period_today: str = Field(description="YYYY-MM-DD (UTC)")
    period_month: str = Field(description="YYYY-MM (UTC)")
    spend:        SpendSummary
    tokens:       TokenSummary
    calls:        CallSummary
    budget_flags: BudgetFlags
    errors:       ErrorSummary


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _utc_today_start() -> str:
    return (
        datetime.combine(date.today(), datetime.min.time())
        .replace(tzinfo=timezone.utc)
        .isoformat()
    )


def _utc_month_start() -> str:
    today = date.today()
    return datetime(today.year, today.month, 1, tzinfo=timezone.utc).isoformat()


def _pct(spent: float, limit: float) -> float:
    if limit <= 0:
        return 0.0
    return round(min(spent / limit * 100, 100), 2)


def _sum_cost(rows: List[Dict[str, Any]]) -> float:
    return round(sum(float(r.get("estimated_cost") or 0) for r in rows), 6)


def _sum_tokens(rows: List[Dict[str, Any]]) -> Tuple[int, int]:
    inp = sum(int(r.get("input_tokens") or 0) for r in rows)
    out = sum(int(r.get("output_tokens") or 0) for r in rows)
    return inp, out


# ══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/report",
    response_model=AIUsageReport,
    summary="AI usage report",
    description=(
        "Full AI cost and usage report for today and this calendar month. "
        "Reads operations.ai_usage_logs and operations.budget_controls."
    ),
)
async def get_ai_usage_report(
    _: str = Depends(verify_admin_key),
    sb: SupabaseClient = Depends(get_supabase),
) -> AIUsageReport:
    today_start = _utc_today_start()
    month_start = _utc_month_start()

    # ── Fetch all this month's log rows in one query ──────────────────────────
    # today rows are a subset; split in Python to avoid two round-trips.
    month_res = (
        sb.schema("operations")
        .table("ai_usage_logs")
        .select(
            "log_id,created_at,status,provider,model,purpose,"
            "input_tokens,output_tokens,estimated_cost,"
            "session_id,error_message,latency_ms"
        )
        .gte("created_at", month_start)
        .order("created_at", desc=True)
        .execute()
    )
    all_month: List[Dict[str, Any]] = month_res.data

    all_today: List[Dict[str, Any]] = [
        r for r in all_month if r["created_at"] >= today_start
    ]

    # Exclude budget_exceeded rows from billed counts (they cost $0)
    month_billed: List[Dict[str, Any]] = [
        r for r in all_month if r["status"] != "budget_exceeded"
    ]
    today_billed: List[Dict[str, Any]] = [
        r for r in all_today if r["status"] != "budget_exceeded"
    ]

    # ── Fetch budget_controls ─────────────────────────────────────────────────
    ctrl_res = (
        sb.schema("operations")
        .table("budget_controls")
        .select("*")
        .eq("scope", "global")
        .single()
        .execute()
    )
    ctrl: Dict[str, Any] = ctrl_res.data

    # ── Spend ─────────────────────────────────────────────────────────────────
    today_usd   = _sum_cost(today_billed)
    month_usd   = _sum_cost(month_billed)
    daily_lim   = float(ctrl.get("daily_budget_limit",   10.00))
    monthly_lim = float(ctrl.get("monthly_budget_limit", 200.00))

    spend = SpendSummary(
        today_usd             = today_usd,
        month_usd             = month_usd,
        daily_limit_usd       = daily_lim,
        monthly_limit_usd     = monthly_lim,
        daily_remaining_usd   = round(max(daily_lim - today_usd, 0), 6),
        monthly_remaining_usd = round(max(monthly_lim - month_usd, 0), 6),
        daily_pct_used        = _pct(today_usd, daily_lim),
        monthly_pct_used      = _pct(month_usd, monthly_lim),
    )

    # ── Tokens ────────────────────────────────────────────────────────────────
    today_in, today_out = _sum_tokens(today_billed)
    month_in, month_out = _sum_tokens(month_billed)

    tokens = TokenSummary(
        today_input  = today_in,
        today_output = today_out,
        today_total  = today_in + today_out,
        month_input  = month_in,
        month_output = month_out,
        month_total  = month_in + month_out,
    )

    # ── Calls by purpose (month, billed only) ────────────────────────────────
    purpose_agg: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"calls": 0, "total_cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
    )
    for r in month_billed:
        p = r.get("purpose") or "other"
        purpose_agg[p]["calls"]          += 1
        purpose_agg[p]["total_cost_usd"] += float(r.get("estimated_cost") or 0)
        purpose_agg[p]["input_tokens"]   += int(r.get("input_tokens") or 0)
        purpose_agg[p]["output_tokens"]  += int(r.get("output_tokens") or 0)

    by_purpose: List[PurposeBreakdown] = sorted(
        [
            PurposeBreakdown(
                purpose        = k,
                calls          = v["calls"],
                total_cost_usd = round(v["total_cost_usd"], 6),
                input_tokens   = v["input_tokens"],
                output_tokens  = v["output_tokens"],
            )
            for k, v in purpose_agg.items()
        ],
        key=lambda x: x.calls,
        reverse=True,
    )

    # ── Calls by model (month, billed only) ──────────────────────────────────
    model_agg: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"calls": 0, "total_cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
    )
    for r in month_billed:
        m = r.get("model") or "unknown"
        model_agg[m]["calls"]          += 1
        model_agg[m]["total_cost_usd"] += float(r.get("estimated_cost") or 0)
        model_agg[m]["input_tokens"]   += int(r.get("input_tokens") or 0)
        model_agg[m]["output_tokens"]  += int(r.get("output_tokens") or 0)

    by_model: List[ModelBreakdown] = sorted(
        [
            ModelBreakdown(
                model          = k,
                calls          = v["calls"],
                total_cost_usd = round(v["total_cost_usd"], 6),
                input_tokens   = v["input_tokens"],
                output_tokens  = v["output_tokens"],
            )
            for k, v in model_agg.items()
        ],
        key=lambda x: x.calls,
        reverse=True,
    )

    calls = CallSummary(
        today_total = len(today_billed),
        month_total = len(month_billed),
        by_purpose  = by_purpose,
        by_model    = by_model,
    )

    # ── Ask GoldPan feature caps ──────────────────────────────────────────────
    ag_month: List[Dict[str, Any]] = [
        r for r in month_billed if r.get("purpose") == "ask_goldpan"
    ]
    ag_today: List[Dict[str, Any]] = [
        r for r in today_billed if r.get("purpose") == "ask_goldpan"
    ]

    budget_flags = BudgetFlags(
        ask_goldpan_enabled           = bool(ctrl.get("ask_goldpan_enabled",          False)),
        ask_goldpan_daily_limit_usd   = float(ctrl.get("ask_goldpan_daily_limit",      2.00)),
        ask_goldpan_monthly_limit_usd = float(ctrl.get("ask_goldpan_monthly_limit",   30.00)),
        ag_spend_today_usd            = round(_sum_cost(ag_today), 6),
        ag_spend_month_usd            = round(_sum_cost(ag_month), 6),
        intake_ai_enabled             = bool(ctrl.get("intake_ai_enabled",             True)),
        governance_ai_enabled         = bool(ctrl.get("governance_ai_enabled",         True)),
    )

    # ── Errors ────────────────────────────────────────────────────────────────
    budget_exceeded_month: List[Dict[str, Any]] = [
        r for r in all_month if r["status"] == "budget_exceeded"
    ]
    budget_exceeded_today: List[Dict[str, Any]] = [
        r for r in all_today if r["status"] == "budget_exceeded"
    ]
    api_errors_month: List[Dict[str, Any]] = [
        r for r in all_month if r["status"] in ("error", "timeout")
    ]
    api_errors_today: List[Dict[str, Any]] = [
        r for r in all_today if r["status"] in ("error", "timeout")
    ]

    # Already sorted desc by created_at from the query
    recent_raw: List[Dict[str, Any]] = [
        r for r in all_month if r["status"] in ("error", "timeout")
    ][:10]

    recent_errors: List[RecentError] = [
        RecentError(
            log_id        = r["log_id"],
            created_at    = r["created_at"],
            status        = r["status"],
            model         = r.get("model") or "",
            purpose       = r.get("purpose") or "",
            error_message = r.get("error_message"),
            latency_ms    = r.get("latency_ms"),
            session_id    = r.get("session_id"),
        )
        for r in recent_raw
    ]

    errors = ErrorSummary(
        budget_exceeded_today = len(budget_exceeded_today),
        budget_exceeded_month = len(budget_exceeded_month),
        errors_today          = len(api_errors_today),
        errors_month          = len(api_errors_month),
        recent                = recent_errors,
    )

    return AIUsageReport(
        generated_at = datetime.now(timezone.utc).isoformat(),
        period_today = date.today().isoformat(),
        period_month = date.today().strftime("%Y-%m"),
        spend        = spend,
        tokens       = tokens,
        calls        = calls,
        budget_flags = budget_flags,
        errors       = errors,
    )


@router.get(
    "/controls",
    summary="Raw budget_controls",
    description="Return the raw budget_controls singleton row. Admin only.",
)
async def get_budget_controls(
    _: str = Depends(verify_admin_key),
    sb: SupabaseClient = Depends(get_supabase),
) -> Dict[str, Any]:
    res = (
        sb.schema("operations")
        .table("budget_controls")
        .select("*")
        .eq("scope", "global")
        .single()
        .execute()
    )
    row: Dict[str, Any] = res.data
    return {k: v for k, v in row.items() if k != "control_id"}
