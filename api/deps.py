"""
api/deps.py — Shared FastAPI dependencies

Provides:
  get_supabase()      — yields a Supabase service-role client per request
  verify_admin_key()  — enforces X-Admin-Key header auth for admin endpoints
  get_acting_user()   — TEMPORARY X-User-Id bridge for per-action actor
                         attribution (DEC000001 gap map §0); never stands
                         in for verify_admin_key, see below
"""

import os
import uuid as _uuid
from typing import Generator, Optional

from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException, status
from supabase import create_client, Client as SupabaseClient

load_dotenv()

# ── Supabase ──────────────────────────────────────────────────────────────────

_SUPABASE_URL = os.getenv("SUPABASE_URL", "")
_SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def get_supabase() -> Generator[SupabaseClient, None, None]:
    """
    Yield a Supabase service-role client.
    The service-role key bypasses RLS — admin endpoints only.
    Never expose this client to untrusted callers.
    """
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    client = create_client(_SUPABASE_URL, _SUPABASE_KEY)
    try:
        yield client
    finally:
        pass  # supabase-py is stateless; no teardown needed


# ── Admin key auth ────────────────────────────────────────────────────────────

_ADMIN_KEY = os.getenv("ADMIN_API_KEY", "")


def verify_admin_key(x_admin_key: str = Header(..., alias="X-Admin-Key")) -> str:
    """
    Require a valid X-Admin-Key header.
    Set ADMIN_API_KEY in .env. If unset, all admin requests are rejected.

    Usage: add `_: str = Depends(verify_admin_key)` to any admin endpoint.
    """
    if not _ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_API_KEY is not configured on this server.",
        )
    if x_admin_key != _ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key.",
        )
    return x_admin_key


# ── Acting user (X-User-Id) — TEMPORARY bridge, technical debt ─────────────────
#
# ⚠ TECHNICAL DEBT: the admin API authenticates every request with a single
# shared X-Admin-Key (above) — there is no per-user Supabase Auth session on
# these routes yet. DEC000001 (and DEC000002 after it) requires every write
# to record a stable acting-user identity (claimed_by_user_id, actor_id,
# etc. — see DEC000001 §5.3, §5.8). X-User-Id is a temporary bridge to
# satisfy that requirement until real per-user Supabase Auth sessions are
# wired into the admin API (DEC000001 Implementation Gap Map §0).
#
# X-User-Id identifies WHO is acting. It NEVER authenticates the request by
# itself — that is still X-Admin-Key's job. This is enforced structurally,
# not just by convention: get_acting_user() below declares verify_admin_key
# as its own sub-dependency, so a caller who supplies a valid X-User-Id but
# an invalid/missing X-Admin-Key is rejected by verify_admin_key() before
# X-User-Id is ever inspected. No endpoint should accept X-User-Id without
# also depending on verify_admin_key (directly or via this dependency).
#
# Remove this mechanism, and this comment, once real per-user auth lands.

class ActingUser:
    """
    Resolved acting user for DEC000001-style actor attribution.

    Not a Pydantic response model on purpose — this represents the caller's
    claimed identity for the duration of one request and should never be
    serialized directly into an API response.
    """

    def __init__(self, user_id: str, role: str, display_name: Optional[str]):
        self.user_id = user_id
        self.role = role
        self.display_name = display_name


def get_acting_user(
    x_user_id: str = Header(..., alias="X-User-Id"),
    _admin: str = Depends(verify_admin_key),
    sb: SupabaseClient = Depends(get_supabase),
) -> ActingUser:
    """
    Validate the X-User-Id header and resolve it to an active operations.users
    row. Required alongside X-Admin-Key on every DEC000001 write endpoint that
    needs to attribute an action to a specific reviewer/specialist/admin.

    Validates (per Brad's implementation direction):
      - X-User-Id is a syntactically valid UUID
      - it references an existing operations.users row
      - that row has is_active = true

    Does NOT check role-specific authority (e.g. "is this a Governance
    Reviewer") — that is a per-endpoint concern. For the four intake review-
    decision commands (claim/release/approve/return), that check is enforced
    directly inside each command's Postgres RPC (operations.claim_intake_
    packet / release_intake_packet / approve_intake_packet / return_intake_
    packet, supabase/migrations/017 and 018) via its own operations.users.role
    lookup — not via api/role_adapter.py, which is currently unused dead code
    on this path (see that module's own docstring).
    """
    try:
        _uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id must be a valid UUID.",
        )

    res = (
        sb.schema("operations").table("users")
        .select("user_id,role,display_name,is_active")
        .eq("user_id", x_user_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-User-Id does not reference a known operations.users record.",
        )

    row = res.data[0]
    if not row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-User-Id references an inactive operations.users record.",
        )

    return ActingUser(
        user_id=row["user_id"],
        role=row["role"],
        display_name=row.get("display_name"),
    )
