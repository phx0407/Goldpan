"""
goldpan_ai_client.py — GoldPan™ AI Usage OS Client v1.0.0

Central wrapper for all Anthropic API calls. Every call:
  1. Checks budget_controls (daily/monthly limits, feature flags)
  2. Makes the Anthropic API call
  3. Writes a row to operations.ai_usage_logs (success or error)

Usage (class interface):
    from goldpan_ai_client import GoldPanAIClient, BudgetExceededError

    client = GoldPanAIClient()
    try:
        msg = client.call(
            model="claude-haiku-4-5-20251001",
            purpose="intake",
            messages=[{"role": "user", "content": prompt}],
            system=system_prompt,
            session_id="intake-abc123",
        )
        text = msg.content[0].text
    except BudgetExceededError as e:
        print(e.user_message)  # safe to show to end users

Usage (module-level convenience):
    import goldpan_ai_client as ai
    msg = ai.call(model="claude-haiku-4-5-20251001", purpose="testing",
                  messages=[{"role": "user", "content": "ping"}])

Environment variables required (loaded from .env):
    ANTHROPIC_API_KEY
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY

SECURITY: ANTHROPIC_API_KEY and SUPABASE_SERVICE_ROLE_KEY are never logged
or included in any output produced by this module.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime, timezone
from typing import Any, Optional, Tuple

import anthropic
from dotenv import load_dotenv
from supabase import create_client, Client as SupabaseClient

load_dotenv()


# ══════════════════════════════════════════════════════════════════════════════
# Exceptions
# ══════════════════════════════════════════════════════════════════════════════

class BudgetExceededError(Exception):
    """
    Raised when a budget limit or feature flag blocks an AI call before
    it reaches the Anthropic API.

    Attributes:
        reason       — machine-readable explanation (safe for internal logs)
        user_message — safe to surface to end users / callers
        limit_type   — one of:
                        'daily' | 'monthly' |
                        'ask_goldpan_daily' | 'ask_goldpan_monthly' |
                        'feature_disabled'
    """

    def __init__(self, reason: str, user_message: str, limit_type: str) -> None:
        super().__init__(reason)
        self.reason       = reason
        self.user_message = user_message
        self.limit_type   = limit_type

    def __repr__(self) -> str:
        return f"BudgetExceededError(limit_type={self.limit_type!r}, reason={self.reason!r})"


# ══════════════════════════════════════════════════════════════════════════════
# Internals
# ══════════════════════════════════════════════════════════════════════════════

# Maps model string substring → pricing tier key used in budget_controls
_TIER_CACHE: dict[str, str] = {}


def _model_tier(model: str) -> str:
    """
    Return the pricing tier for a model string.
    "claude-haiku-4-5-20251001" → "haiku"
    "claude-sonnet-4-6"        → "sonnet"
    "claude-opus-4-8"          → "opus"
    Defaults to "sonnet" for unknown models.
    """
    key = model.lower()
    if key in _TIER_CACHE:
        return _TIER_CACHE[key]
    if "haiku" in key:
        tier = "haiku"
    elif "opus" in key:
        tier = "opus"
    else:
        tier = "sonnet"
    _TIER_CACHE[key] = tier
    return tier


# ══════════════════════════════════════════════════════════════════════════════
# GoldPanAIClient
# ══════════════════════════════════════════════════════════════════════════════

class GoldPanAIClient:
    """
    Central AI client for the GoldPan™ Master OS.

    One instance is enough per process. The module exposes a singleton via
    get_client() / call() for simple call sites.

    budget_controls are cached for 60 seconds to avoid a Supabase round-trip
    on every call while still picking up admin updates within a minute.
    """

    _CONTROLS_CACHE_TTL = 60  # seconds

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        supabase_url:      Optional[str] = None,
        supabase_key:      Optional[str] = None,
    ) -> None:
        self._anthropic: anthropic.Anthropic = anthropic.Anthropic(
            api_key=anthropic_api_key or os.environ["ANTHROPIC_API_KEY"]
        )
        self._sb: SupabaseClient = create_client(
            supabase_url or os.environ["SUPABASE_URL"],
            supabase_key or os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
        self._controls_cache:     Optional[dict] = None
        self._controls_cached_at: float       = 0.0

    # ── budget_controls ───────────────────────────────────────────────────────

    def _load_controls(self) -> dict:
        """Load the budget_controls singleton, cached for _CONTROLS_CACHE_TTL seconds."""
        now = time.monotonic()
        if (
            self._controls_cache is not None
            and (now - self._controls_cached_at) < self._CONTROLS_CACHE_TTL
        ):
            return self._controls_cache

        res = (
            self._sb.schema("operations")
            .table("budget_controls")
            .select("*")
            .eq("scope", "global")
            .single()
            .execute()
        )
        self._controls_cache    = res.data
        self._controls_cached_at = now
        return self._controls_cache

    def invalidate_controls_cache(self) -> None:
        """Force a fresh budget_controls read on the next call."""
        self._controls_cache    = None
        self._controls_cached_at = 0.0

    # ── spend queries ─────────────────────────────────────────────────────────

    def _spend_today(self, purpose_filter: Optional[str] = None) -> float:
        """
        Sum estimated_cost for today (UTC midnight → now).
        Excludes rows with status='budget_exceeded' (those had cost 0 anyway).
        """
        today_start = (
            datetime.combine(date.today(), datetime.min.time())
            .replace(tzinfo=timezone.utc)
            .isoformat()
        )
        q = (
            self._sb.schema("operations")
            .table("ai_usage_logs")
            .select("estimated_cost")
            .gte("created_at", today_start)
            .neq("status", "budget_exceeded")
        )
        if purpose_filter:
            q = q.eq("purpose", purpose_filter)
        res = q.execute()
        return sum(float(r["estimated_cost"] or 0) for r in res.data)

    def _spend_this_month(self, purpose_filter: Optional[str] = None) -> float:
        """
        Sum estimated_cost for the current calendar month (UTC).
        Excludes rows with status='budget_exceeded'.
        """
        today      = date.today()
        month_start = datetime(today.year, today.month, 1, tzinfo=timezone.utc).isoformat()
        q = (
            self._sb.schema("operations")
            .table("ai_usage_logs")
            .select("estimated_cost")
            .gte("created_at", month_start)
            .neq("status", "budget_exceeded")
        )
        if purpose_filter:
            q = q.eq("purpose", purpose_filter)
        res = q.execute()
        return sum(float(r["estimated_cost"] or 0) for r in res.data)

    def spending_summary(self) -> dict:
        """
        Return current spend vs limits.
        Useful for dashboard API endpoints and health checks.

        Returns a dict:
            {
              "daily_spend":    float,
              "daily_limit":    float,
              "monthly_spend":  float,
              "monthly_limit":  float,
              "ag_daily_spend": float,
              "ag_daily_limit": float,
              "ag_monthly_spend": float,
              "ag_monthly_limit": float,
              "ask_goldpan_enabled": bool,
              "intake_ai_enabled":   bool,
              "governance_ai_enabled": bool,
            }
        """
        c = self._load_controls()
        return {
            "daily_spend":          self._spend_today(),
            "daily_limit":          float(c.get("daily_budget_limit",       10.00)),
            "monthly_spend":        self._spend_this_month(),
            "monthly_limit":        float(c.get("monthly_budget_limit",    200.00)),
            "ag_daily_spend":       self._spend_today(purpose_filter="ask_goldpan"),
            "ag_daily_limit":       float(c.get("ask_goldpan_daily_limit",   2.00)),
            "ag_monthly_spend":     self._spend_this_month(purpose_filter="ask_goldpan"),
            "ag_monthly_limit":     float(c.get("ask_goldpan_monthly_limit", 30.00)),
            "ask_goldpan_enabled":  bool(c.get("ask_goldpan_enabled",  False)),
            "intake_ai_enabled":    bool(c.get("intake_ai_enabled",    True)),
            "governance_ai_enabled": bool(c.get("governance_ai_enabled", True)),
        }

    # ── budget enforcement ────────────────────────────────────────────────────

    def _check_budget(self, purpose: str, controls: dict) -> None:
        """
        Raise BudgetExceededError if any limit would be exceeded.

        Checks in order:
          1. Feature flag (purpose-specific enable/disable)
          2. Global daily budget
          3. Global monthly budget
          4. Ask GoldPan daily cap   (purpose == 'ask_goldpan' only)
          5. Ask GoldPan monthly cap (purpose == 'ask_goldpan' only)
        """
        exceeded_msg = controls.get(
            "budget_exceeded_message",
            "GoldPan AI services are temporarily paused. Please contact support.",
        )
        beta_msg = controls.get(
            "ask_goldpan_beta_message",
            "Ask GoldPan™ is in limited beta. Daily capacity has been reached — please try again tomorrow.",
        )

        # 1. Feature flags
        if purpose == "ask_goldpan" and not controls.get("ask_goldpan_enabled", False):
            raise BudgetExceededError(
                reason="ask_goldpan feature flag is disabled",
                user_message=beta_msg,
                limit_type="feature_disabled",
            )
        if purpose in ("intake", "escalation") and not controls.get("intake_ai_enabled", True):
            raise BudgetExceededError(
                reason="intake_ai feature flag is disabled",
                user_message=exceeded_msg,
                limit_type="feature_disabled",
            )
        if purpose == "governance" and not controls.get("governance_ai_enabled", True):
            raise BudgetExceededError(
                reason="governance_ai feature flag is disabled",
                user_message=exceeded_msg,
                limit_type="feature_disabled",
            )

        # 2. Global daily
        daily_limit = float(controls.get("daily_budget_limit", 10.00))
        daily_spend = self._spend_today()
        if daily_spend >= daily_limit:
            raise BudgetExceededError(
                reason=(
                    f"Global daily budget exceeded: "
                    f"${daily_spend:.4f} >= ${daily_limit:.2f}"
                ),
                user_message=exceeded_msg,
                limit_type="daily",
            )

        # 3. Global monthly
        monthly_limit = float(controls.get("monthly_budget_limit", 200.00))
        monthly_spend = self._spend_this_month()
        if monthly_spend >= monthly_limit:
            raise BudgetExceededError(
                reason=(
                    f"Global monthly budget exceeded: "
                    f"${monthly_spend:.4f} >= ${monthly_limit:.2f}"
                ),
                user_message=exceeded_msg,
                limit_type="monthly",
            )

        # 4–5. Ask GoldPan per-feature caps
        if purpose == "ask_goldpan":
            ag_daily_limit = float(controls.get("ask_goldpan_daily_limit", 2.00))
            ag_daily_spend = self._spend_today(purpose_filter="ask_goldpan")
            if ag_daily_spend >= ag_daily_limit:
                raise BudgetExceededError(
                    reason=(
                        f"Ask GoldPan daily cap exceeded: "
                        f"${ag_daily_spend:.4f} >= ${ag_daily_limit:.2f}"
                    ),
                    user_message=beta_msg,
                    limit_type="ask_goldpan_daily",
                )

            ag_monthly_limit = float(controls.get("ask_goldpan_monthly_limit", 30.00))
            ag_monthly_spend = self._spend_this_month(purpose_filter="ask_goldpan")
            if ag_monthly_spend >= ag_monthly_limit:
                raise BudgetExceededError(
                    reason=(
                        f"Ask GoldPan monthly cap exceeded: "
                        f"${ag_monthly_spend:.4f} >= ${ag_monthly_limit:.2f}"
                    ),
                    user_message=beta_msg,
                    limit_type="ask_goldpan_monthly",
                )

    # ── cost computation ──────────────────────────────────────────────────────

    def _compute_cost(
        self,
        tier:          str,
        input_tokens:  int,
        output_tokens: int,
        controls:      dict,
    ) -> tuple[float, float, float]:
        """
        Return (estimated_cost_usd, cost_per_mtok_input, cost_per_mtok_output).
        Pricing is read from budget_controls at call time so admin changes apply
        immediately on the next cache refresh.
        """
        mtok_in  = float(controls.get(f"price_{tier}_input",   3.00))
        mtok_out = float(controls.get(f"price_{tier}_output", 15.00))
        cost = (input_tokens / 1_000_000) * mtok_in + (output_tokens / 1_000_000) * mtok_out
        return round(cost, 6), round(mtok_in, 4), round(mtok_out, 4)

    # ── usage logging ─────────────────────────────────────────────────────────

    def _log_usage(self, row: dict) -> None:
        """
        Insert one row into operations.ai_usage_logs.
        Never raises — log failures are printed to stderr but do not propagate.
        Callers must not include 'total_tokens' in row (it is GENERATED ALWAYS AS).
        """
        try:
            self._sb.schema("operations").table("ai_usage_logs").insert(row).execute()
        except Exception as exc:
            print(
                f"[goldpan_ai_client] WARNING: usage log write failed: {exc}",
                file=sys.stderr,
            )

    # ── public API ────────────────────────────────────────────────────────────

    def call(
        self,
        model:     str,
        purpose:   str,
        messages:  list[dict],
        system:    str = "",
        max_tokens: int = 16384,
        *,
        session_id:             Optional[str] = None,
        run_id:                 Optional[str] = None,
        restaurant_id:          Optional[str] = None,
        restaurant_external_id: Optional[str] = None,
        dish_id:                Optional[str] = None,
        dish_external_id:       Optional[str] = None,
        actor_id:               Optional[str] = None,
        actor_type:             str           = "system",
    ) -> anthropic.types.Message:
        """
        Make one Anthropic API call with budget enforcement and usage logging.

        Args:
            model:     Full model string, e.g. "claude-haiku-4-5-20251001"
            purpose:   intake | escalation | ask_goldpan | governance |
                       scoring | testing | other
            messages:  Anthropic messages list, e.g.
                       [{"role": "user", "content": "your prompt"}]
            system:    System prompt string (optional)
            max_tokens: Max output tokens (default 16384)

            Keyword-only context args (all optional — used for cost attribution):
            session_id:             Intake session ID, pipeline run ID, or Ask GoldPan session token
            run_id:                 UUID of knowledge.pipeline_runs row (if applicable)
            restaurant_id:          UUID from evidence.restaurants
            restaurant_external_id: Denormalized restaurant ID (e.g. "R014")
            dish_id:                UUID from evidence.dishes
            dish_external_id:       Denormalized dish ID (e.g. "D084")
            actor_id:               UUID from operations.users (if a human triggered this)
            actor_type:             canvasser | coordinator | admin | system | pipeline | customer

        Returns:
            anthropic.types.Message — same object the raw Anthropic SDK returns.
            Access the text via msg.content[0].text.

        Raises:
            BudgetExceededError  — budget limit or feature flag blocked the call
            anthropic.APITimeoutError — Anthropic timed out
            anthropic.APIError   — other Anthropic API error
        """
        controls = self._load_controls()
        tier     = _model_tier(model)

        # ── 1. Budget check (before touching Anthropic) ───────────────────────
        try:
            self._check_budget(purpose, controls)
        except BudgetExceededError as exc:
            self._log_usage({
                "session_id":             session_id,
                "run_id":                 run_id,
                "provider":               "anthropic",
                "model":                  model,
                "purpose":                purpose,
                "restaurant_id":          restaurant_id,
                "restaurant_external_id": restaurant_external_id,
                "dish_id":                dish_id,
                "dish_external_id":       dish_external_id,
                "input_tokens":           0,
                "output_tokens":          0,
                "estimated_cost":         "0",
                "status":                 "budget_exceeded",
                "error_message":          exc.reason,
                "actor_id":               actor_id,
                "actor_type":             actor_type,
            })
            raise

        # ── 2. Anthropic API call ─────────────────────────────────────────────
        t0:             int                         = time.monotonic_ns() // 1_000_000
        status:         str                         = "success"
        error_message:  Optional[str]                         = None
        message:        Optional[anthropic.types.Message]    = None

        try:
            kwargs: dict[str, Any] = dict(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
            )
            if system:
                kwargs["system"] = system

            message = self._anthropic.messages.create(**kwargs)

        except anthropic.APITimeoutError as exc:
            status        = "timeout"
            error_message = str(exc)
            raise

        except anthropic.APIError as exc:
            status        = "error"
            error_message = str(exc)
            raise

        finally:
            latency_ms = (time.monotonic_ns() // 1_000_000) - t0

            # ── 3. Compute tokens & cost ──────────────────────────────────────
            input_tokens  = 0
            output_tokens = 0
            if message is not None and message.usage:
                input_tokens  = message.usage.input_tokens
                output_tokens = message.usage.output_tokens

            estimated_cost, mtok_in, mtok_out = self._compute_cost(
                tier, input_tokens, output_tokens, controls
            )

            # ── 4. Write usage log ────────────────────────────────────────────
            self._log_usage({
                "session_id":             session_id,
                "run_id":                 run_id,
                "provider":               "anthropic",
                "model":                  model,
                "purpose":                purpose,
                "restaurant_id":          restaurant_id,
                "restaurant_external_id": restaurant_external_id,
                "dish_id":                dish_id,
                "dish_external_id":       dish_external_id,
                "input_tokens":           input_tokens,
                "output_tokens":          output_tokens,
                # Pass as strings to keep numeric precision through JSON serialization
                "estimated_cost":         str(estimated_cost),
                "cost_per_mtok_input":    str(mtok_in),
                "cost_per_mtok_output":   str(mtok_out),
                "status":                 status,
                "error_message":          error_message,
                "latency_ms":             latency_ms,
                "actor_id":               actor_id,
                "actor_type":             actor_type,
            })

        return message  # type: ignore[return-value]


# ══════════════════════════════════════════════════════════════════════════════
# Module-level singleton
# ══════════════════════════════════════════════════════════════════════════════

_default_client: Optional[GoldPanAIClient] = None


def get_client() -> GoldPanAIClient:
    """
    Return the module-level singleton GoldPanAIClient.
    Constructed lazily on first call using environment variables.
    """
    global _default_client
    if _default_client is None:
        _default_client = GoldPanAIClient()
    return _default_client


def call(
    model:      str,
    purpose:    str,
    messages:   list[dict],
    system:     str = "",
    max_tokens: int = 16384,
    **kwargs: Any,
) -> anthropic.types.Message:
    """
    Convenience wrapper using the module-level singleton.
    See GoldPanAIClient.call() for full parameter documentation.
    """
    return get_client().call(
        model=model,
        purpose=purpose,
        messages=messages,
        system=system,
        max_tokens=max_tokens,
        **kwargs,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Smoke test  (python3 goldpan_ai_client.py)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json

    print("goldpan_ai_client.py — smoke test")
    print("─" * 48)

    client = GoldPanAIClient()

    # 1. Budget controls
    controls = client._load_controls()
    print(f"budget_controls loaded:")
    print(f"  daily_budget_limit    = ${controls['daily_budget_limit']}")
    print(f"  monthly_budget_limit  = ${controls['monthly_budget_limit']}")
    print(f"  ask_goldpan_enabled   = {controls['ask_goldpan_enabled']}")
    print(f"  intake_ai_enabled     = {controls['intake_ai_enabled']}")
    print(f"  governance_ai_enabled = {controls['governance_ai_enabled']}")

    # 2. Spending summary
    summary = client.spending_summary()
    print(f"\nspending_summary:")
    print(f"  today   ${summary['daily_spend']:.6f}  /  ${summary['daily_limit']:.2f}")
    print(f"  month   ${summary['monthly_spend']:.6f}  /  ${summary['monthly_limit']:.2f}")

    # 3. Small test call
    print(f"\nMaking a test call (purpose=testing, model=haiku)…")
    try:
        msg = client.call(
            model="claude-haiku-4-5-20251001",
            purpose="testing",
            messages=[{"role": "user", "content": "Reply with exactly: pong"}],
            session_id="smoke-test",
        )
        print(f"  response : {msg.content[0].text.strip()}")
        print(f"  tokens   : {msg.usage.input_tokens} in / {msg.usage.output_tokens} out")
        print(f"  ✓ usage row written to operations.ai_usage_logs")
    except BudgetExceededError as e:
        print(f"  ⚠ BudgetExceededError ({e.limit_type}): {e.reason}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
