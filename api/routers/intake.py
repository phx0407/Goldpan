"""
api/routers/intake.py — Intake OS endpoints

Endpoints:
  GET  /admin/intake                   — queue summary + packet list
  GET  /admin/intake/{packet_id}       — packet detail (full packet_data)
  POST /admin/intake/submit            — submit a new packet (JSON body)
  POST /admin/intake/{packet_id}/claim   — claim packet for review (DEC000001 §5.3)
  POST /admin/intake/{packet_id}/release — release a claimed packet (DEC000001 §5.5)
  POST /admin/intake/{packet_id}/approve — approve packet (ready to ingest)
  POST /admin/intake/{packet_id}/return  — return to canvasser with reason
  POST /admin/intake/{packet_id}/ingest  — mark as ingested (CLI ran externally)

Python 3.9 compatible — uses typing.List / Dict / Optional throughout.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from postgrest.exceptions import APIError as PostgrestAPIError
from pydantic import BaseModel, Field
from supabase import Client as SupabaseClient

from api.deps import ActingUser, get_acting_user, get_supabase, verify_admin_key

router = APIRouter(prefix="/admin/intake", tags=["Intake OS"])

NOW = lambda: datetime.now(timezone.utc).isoformat()


# ══════════════════════════════════════════════════════════════════════════════
# Response models
# ══════════════════════════════════════════════════════════════════════════════

class IntakePacketRow(BaseModel):
    packet_id:               str
    restaurant_external_id:  str
    restaurant_name:         str
    restaurant_id:           Optional[str]
    packet_status:           str
    canvass_date:            str
    dish_count:              int
    review_flag_count:       int
    evidence_score_overall:  Optional[int]
    agent_version:           Optional[str]
    model_used:              Optional[str]
    reviewer_notes:          Optional[str]
    return_reason:           Optional[str]
    submitted_at:            str
    reviewed_at:             Optional[str]
    reviewed_by:             Optional[str]
    ingested_at:             Optional[str]
    claimed_by_user_id:      Optional[str]
    claimed_at:              Optional[str]


class IntakeQueueSummary(BaseModel):
    total:          int
    pending_review: int
    in_review:      int
    returned:       int
    approved:       int
    rejected:       int
    ingested:       int


class IntakeQueueResponse(BaseModel):
    generated_at: str
    summary:      IntakeQueueSummary
    packets:      List[IntakePacketRow]


class IntakePacketDetail(BaseModel):
    packet_id:               str
    restaurant_external_id:  str
    restaurant_name:         str
    restaurant_id:           Optional[str]
    packet_status:           str
    canvass_date:            str
    source_urls:             List[str]
    dish_count:              int
    review_flag_count:       int
    evidence_score_overall:  Optional[int]
    evidence_score_detail:   Optional[Dict[str, Any]]
    agent_version:           Optional[str]
    model_used:              Optional[str]
    processing_time_ms:      Optional[int]
    packet_data:             Dict[str, Any]
    reviewer_notes:          Optional[str]
    return_reason:           Optional[str]
    submitted_at:            str
    reviewed_at:             Optional[str]
    reviewed_by:             Optional[str]
    ingested_at:             Optional[str]
    claimed_by_user_id:      Optional[str]
    claimed_at:              Optional[str]


class IntakePacketDetailResponse(BaseModel):
    generated_at: str
    packet:       IntakePacketDetail


# ── Request bodies ─────────────────────────────────────────────────────────────

class SubmitPacketRequest(BaseModel):
    packet_data:            Dict[str, Any] = Field(
        description="Full intake packet JSON as produced by intake_agent.py"
    )
    restaurant_external_id: Optional[str] = Field(
        None,
        description="Override external_id. If omitted, derived from packet_data.restaurant.restaurant_id or auto-assigned."
    )


class ReturnPacketRequest(BaseModel):
    reason:         str  = Field(description="Reason for returning the packet to the canvasser")
    reviewer_notes: Optional[str] = None


class ApprovePacketRequest(BaseModel):
    reviewer_notes:  Optional[str] = None
    override_reason: Optional[str] = Field(
        None,
        description=(
            "Required when an Administrator approves a packet claimed by "
            "someone else (override approval, DEC000001 §3: 'claimant-or-admin "
            "only'). Not required for ordinary claimant approval."
        ),
    )


class ReleasePacketRequest(BaseModel):
    reason: Optional[str] = Field(
        None,
        description=(
            "Required when an Administrator releases a packet claimed by someone "
            "else (override release). Not required for ordinary self-release."
        ),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _row_to_packet_row(r: Dict[str, Any]) -> IntakePacketRow:
    return IntakePacketRow(
        packet_id               = r["packet_id"],
        restaurant_external_id  = r["restaurant_external_id"],
        restaurant_name         = r["restaurant_name"],
        restaurant_id           = r.get("restaurant_id"),
        packet_status           = r["packet_status"],
        canvass_date            = str(r["canvass_date"]),
        dish_count              = r["dish_count"] or 0,
        review_flag_count       = r["review_flag_count"] or 0,
        evidence_score_overall  = r.get("evidence_score_overall"),
        agent_version           = r.get("agent_version"),
        model_used              = r.get("model_used"),
        reviewer_notes          = r.get("reviewer_notes"),
        return_reason           = r.get("return_reason"),
        submitted_at            = r["submitted_at"],
        reviewed_at             = r.get("reviewed_at"),
        reviewed_by             = r.get("reviewed_by"),
        ingested_at             = r.get("ingested_at"),
        claimed_by_user_id      = r.get("claimed_by_user_id"),
        claimed_at              = r.get("claimed_at"),
    )


# SQLSTATE codes raised by operations.approve_intake_packet /
# operations.return_intake_packet (supabase/migrations/017_intake_review_
# decision_rpcs.sql) → the HTTPException status the API previously raised
# for the equivalent condition when the check lived in Python. Keeping this
# mapping table lets the RPC be "the authoritative atomic mutation" (task
# #44 correction) while the endpoints' response contract stays unchanged.
_RPC_ERROR_STATUS: Dict[str, int] = {
    "GP404": status.HTTP_404_NOT_FOUND,
    "GP409": status.HTTP_409_CONFLICT,
    "GP403": status.HTTP_403_FORBIDDEN,
    "GP422": status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def _raise_from_rpc_error(err: PostgrestAPIError) -> None:
    """
    Translate a decision RPC's raised error into the matching HTTPException.
    Unrecognized codes (anything not raised deliberately by the RPC itself,
    e.g. a real DB/connection fault) surface as 500 rather than being
    silently mapped to a 4xx — an unmapped error is a real failure, not a
    validation outcome.
    """
    http_status = _RPC_ERROR_STATUS.get(err.code)
    if http_status is None:
        raise HTTPException(
            status_code=500,
            detail=f"intake decision RPC failed: {err.message}",
        )
    raise HTTPException(status_code=http_status, detail=err.message)


def _extract_packet_fields(packet_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract summary fields from raw packet JSON."""
    restaurant  = packet_data.get("restaurant", {})
    dishes      = packet_data.get("dishes", [])
    flags       = packet_data.get("review_flags", [])
    ev_score    = packet_data.get("evidence_score", {})
    agent_meta  = packet_data.get("agent_metadata", {})

    source_urls: List[str] = agent_meta.get("input_sources", [])
    if not source_urls:
        inv = restaurant.get("source_inventory")
        if isinstance(inv, list):
            source_urls = inv
        elif isinstance(inv, str) and inv:
            source_urls = [inv]

    return {
        "canvass_date":           restaurant.get("canvass_date") or datetime.now(timezone.utc).date().isoformat(),
        "source_urls":            source_urls,
        "agent_version":          agent_meta.get("agent_version"),
        "model_used":             agent_meta.get("model"),
        "processing_time_ms":     agent_meta.get("processing_time_ms"),
        "dish_count":             len(dishes),
        "review_flag_count":      len(flags),
        "evidence_score_overall": ev_score.get("overall"),
        "evidence_score_detail":  ev_score if ev_score else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "",
    response_model=IntakeQueueResponse,
    summary="Intake queue",
    description="All intake packets with status summary.",
)
async def get_intake_queue(
    status_filter: Optional[str] = None,
    _: str = Depends(verify_admin_key),
    sb: SupabaseClient = Depends(get_supabase),
) -> IntakeQueueResponse:

    q = (
        sb.schema("operations").table("intake_packets")
        .select(
            "packet_id,restaurant_external_id,restaurant_name,restaurant_id,"
            "packet_status,canvass_date,dish_count,review_flag_count,"
            "evidence_score_overall,agent_version,model_used,"
            "reviewer_notes,return_reason,"
            "submitted_at,reviewed_at,reviewed_by,ingested_at,"
            "claimed_by_user_id,claimed_at"
        )
        .order("submitted_at", desc=True)
    )
    if status_filter:
        q = q.eq("packet_status", status_filter)

    res = q.execute()
    rows = res.data

    packets = [_row_to_packet_row(r) for r in rows]

    by_status: Dict[str, int] = {}
    for r in rows:
        by_status[r["packet_status"]] = by_status.get(r["packet_status"], 0) + 1

    summary = IntakeQueueSummary(
        total          = len(rows),
        pending_review = by_status.get("pending_review", 0),
        in_review      = by_status.get("in_review", 0),
        returned       = by_status.get("returned", 0),
        approved       = by_status.get("approved", 0),
        rejected       = by_status.get("rejected", 0),
        ingested       = by_status.get("ingested", 0),
    )

    return IntakeQueueResponse(
        generated_at = NOW(),
        summary      = summary,
        packets      = packets,
    )


@router.get(
    "/{packet_id}",
    response_model=IntakePacketDetailResponse,
    summary="Intake packet detail",
    description="Full packet including all dishes, review flags, and evidence.",
)
async def get_intake_packet(
    packet_id: str,
    _: str = Depends(verify_admin_key),
    sb: SupabaseClient = Depends(get_supabase),
) -> IntakePacketDetailResponse:

    res = (
        sb.schema("operations").table("intake_packets")
        .select("*")
        .eq("packet_id", packet_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Packet '{packet_id}' not found.")
    r = res.data[0]

    packet = IntakePacketDetail(
        packet_id               = r["packet_id"],
        restaurant_external_id  = r["restaurant_external_id"],
        restaurant_name         = r["restaurant_name"],
        restaurant_id           = r.get("restaurant_id"),
        packet_status           = r["packet_status"],
        canvass_date            = str(r["canvass_date"]),
        source_urls             = r.get("source_urls") or [],
        dish_count              = r["dish_count"] or 0,
        review_flag_count       = r["review_flag_count"] or 0,
        evidence_score_overall  = r.get("evidence_score_overall"),
        evidence_score_detail   = r.get("evidence_score_detail"),
        agent_version           = r.get("agent_version"),
        model_used              = r.get("model_used"),
        processing_time_ms      = r.get("processing_time_ms"),
        packet_data             = r["packet_data"] or {},
        reviewer_notes          = r.get("reviewer_notes"),
        return_reason           = r.get("return_reason"),
        submitted_at            = r["submitted_at"],
        reviewed_at             = r.get("reviewed_at"),
        reviewed_by             = r.get("reviewed_by"),
        ingested_at             = r.get("ingested_at"),
        claimed_by_user_id      = r.get("claimed_by_user_id"),
        claimed_at              = r.get("claimed_at"),
    )

    return IntakePacketDetailResponse(generated_at=NOW(), packet=packet)


@router.post(
    "/submit",
    response_model=IntakePacketRow,
    status_code=status.HTTP_201_CREATED,
    summary="Submit intake packet",
    description="Submit a new packet from intake_agent.py output. Idempotent on (restaurant_external_id, canvass_date).",
)
async def submit_packet(
    body: SubmitPacketRequest,
    _: str = Depends(verify_admin_key),
    sb: SupabaseClient = Depends(get_supabase),
) -> IntakePacketRow:

    packet_data = body.packet_data
    restaurant  = packet_data.get("restaurant", {})
    restaurant_name = (
        restaurant.get("restaurant_name")
        or restaurant.get("name")
        or "Unknown Restaurant"
    )

    # Resolve external_id
    external_id = (
        body.restaurant_external_id
        or restaurant.get("restaurant_id")
        or restaurant.get("external_id")
    )
    if not external_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot determine restaurant_external_id from packet. Pass it explicitly.",
        )
    external_id = external_id.upper()

    # Look up restaurant_id
    r_res = (
        sb.schema("evidence").table("restaurants")
        .select("restaurant_id")
        .eq("external_id", external_id)
        .limit(1)
        .execute()
    )
    restaurant_id = r_res.data[0]["restaurant_id"] if r_res.data else None

    fields = _extract_packet_fields(packet_data)

    row = {
        "restaurant_id":           restaurant_id,
        "restaurant_external_id":  external_id,
        "restaurant_name":         restaurant_name,
        "packet_status":           "pending_review",
        "packet_data":             packet_data,
        **fields,
    }

    try:
        ins = (
            sb.schema("operations").table("intake_packets")
            .insert(row)
            .execute()
        )
    except Exception as exc:
        # Duplicate (restaurant_external_id, canvass_date) → 409
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A packet for '{external_id}' on {fields['canvass_date']} already exists.",
            )
        raise HTTPException(status_code=500, detail=str(exc))

    return _row_to_packet_row(ins.data[0])


@router.post(
    "/{packet_id}/claim",
    response_model=IntakePacketRow,
    summary="Claim intake packet for review",
    description=(
        "Atomically claim a pending_review packet for review, transitioning it "
        "to in_review (DEC000001 §5.3-§5.4). Governance Reviewers only."
    ),
)
async def claim_packet(
    packet_id: str,
    _: str = Depends(verify_admin_key),
    actor: ActingUser = Depends(get_acting_user),
    sb: SupabaseClient = Depends(get_supabase),
) -> IntakePacketRow:

    # Task #43 (corrected): validation, authorization (Governance Reviewer
    # or Administrator, per the approved interim mapping — widened from
    # reviewer-only per this correction's explicit instruction), status
    # transition, claim-field mutation, and the claim event insert all
    # happen inside operations.claim_intake_packet
    # (supabase/migrations/018_intake_claim_release_rpcs.sql) as one DB
    # transaction — the RPC is the authoritative atomic mutation, same
    # pattern as approve/return (migration 017).
    try:
        res = sb.rpc(
            "claim_intake_packet",
            {
                "p_packet_id":     packet_id,
                "p_actor_user_id": actor.user_id,
            },
        ).execute()
    except PostgrestAPIError as err:
        _raise_from_rpc_error(err)
        raise  # pragma: no cover — _raise_from_rpc_error always raises

    row = res.data
    if isinstance(row, list):
        row = row[0]
    return _row_to_packet_row(row)


@router.post(
    "/{packet_id}/release",
    response_model=IntakePacketRow,
    summary="Release a claimed intake packet",
    description=(
        "Release an in_review packet back to pending_review (DEC000001 §5.5). "
        "The current claimant may self-release without a reason. Anyone else "
        "must be an Administrator performing an override release, which "
        "requires a non-blank reason."
    ),
)
async def release_packet(
    packet_id: str,
    body: ReleasePacketRequest,
    _: str = Depends(verify_admin_key),
    actor: ActingUser = Depends(get_acting_user),
    sb: SupabaseClient = Depends(get_supabase),
) -> IntakePacketRow:

    # Task #43 (corrected): same single-transaction RPC pattern as
    # claim_packet() above, via operations.release_intake_packet
    # (supabase/migrations/018_intake_claim_release_rpcs.sql). Self-release
    # needs no reason; an override release requires Administrator authority
    # and a non-blank reason — both enforced inside the RPC, which is
    # authoritative.
    try:
        res = sb.rpc(
            "release_intake_packet",
            {
                "p_packet_id":     packet_id,
                "p_actor_user_id": actor.user_id,
                "p_reason":        body.reason,
            },
        ).execute()
    except PostgrestAPIError as err:
        _raise_from_rpc_error(err)
        raise  # pragma: no cover — _raise_from_rpc_error always raises

    row = res.data
    if isinstance(row, list):
        row = row[0]
    return _row_to_packet_row(row)


@router.post(
    "/{packet_id}/approve",
    response_model=IntakePacketRow,
    summary="Approve intake packet",
    description=(
        "Approve an in_review packet, transitioning it to approved "
        "(DEC000001 §5.5, §5.9). Ordinarily restricted to the current "
        "claimant; an Administrator may override with a mandatory reason "
        "(DEC000001 §3: 'claimant-or-admin only'). Packet is then ready for "
        "intake.packet.commit_ingest."
    ),
)
async def approve_packet(
    packet_id: str,
    body: ApprovePacketRequest,
    _: str = Depends(verify_admin_key),
    actor: ActingUser = Depends(get_acting_user),
    sb: SupabaseClient = Depends(get_supabase),
) -> IntakePacketRow:

    # Task #44 (corrected): validation, claimant-or-admin authorization,
    # status transition, claim-clearing, and the append-only event insert
    # all happen inside operations.approve_intake_packet
    # (supabase/migrations/017_intake_review_decision_rpcs.sql) as one DB
    # transaction — the RPC is the authoritative atomic mutation. This
    # single call replaces what was previously a SELECT + conditional
    # UPDATE + separate INSERT from the API layer; the FastAPI layer above
    # (verify_admin_key, get_acting_user) still establishes who is calling,
    # but no longer makes the approve/override decision itself.
    try:
        res = sb.rpc(
            "approve_intake_packet",
            {
                "p_packet_id":       packet_id,
                "p_actor_user_id":   actor.user_id,
                "p_override_reason": body.override_reason,
                "p_reviewer_notes":  body.reviewer_notes,
            },
        ).execute()
    except PostgrestAPIError as err:
        _raise_from_rpc_error(err)
        raise  # pragma: no cover — _raise_from_rpc_error always raises

    row = res.data
    if isinstance(row, list):
        row = row[0]
    return _row_to_packet_row(row)


@router.post(
    "/{packet_id}/return",
    response_model=IntakePacketRow,
    summary="Return intake packet",
    description=(
        "Return an in_review packet to the canvasser with a mandatory "
        "reason, transitioning it to returned (DEC000001 §5.5, §5.9). "
        "Ordinary use is claimant-only; a Founder/CEO administrator "
        "override is also permitted, requiring the same mandatory reason "
        "and logged distinctly (DEC000001 §5.5, corrected 2026-07-16 per "
        "Founder/CEO governance clarification — return previously had no "
        "override path at all)."
    ),
)
async def return_packet(
    packet_id: str,
    body: ReturnPacketRequest,
    _: str = Depends(verify_admin_key),
    actor: ActingUser = Depends(get_acting_user),
    sb: SupabaseClient = Depends(get_supabase),
) -> IntakePacketRow:

    # Task #44 (corrected); Founder/CEO governance clarification 2026-07-16:
    # same single-transaction RPC pattern as approve_packet() above, via
    # operations.return_intake_packet (supabase/migrations/017_intake_
    # review_decision_rpcs.sql). Ordinary return is claimant-only; an
    # Administrator override is also permitted (added by the governance
    # clarification, superseding the original claimant-only-no-override
    # reading of DEC000001 §3) and requires the same mandatory, non-blank
    # reason, enforced inside the RPC. packet_data is never touched.
    try:
        res = sb.rpc(
            "return_intake_packet",
            {
                "p_packet_id":      packet_id,
                "p_actor_user_id":  actor.user_id,
                "p_reason":         body.reason,
                "p_reviewer_notes": body.reviewer_notes,
            },
        ).execute()
    except PostgrestAPIError as err:
        _raise_from_rpc_error(err)
        raise  # pragma: no cover — _raise_from_rpc_error always raises

    row = res.data
    if isinstance(row, list):
        row = row[0]
    return _row_to_packet_row(row)


@router.post(
    "/{packet_id}/ingest",
    response_model=IntakePacketRow,
    summary="Mark packet as ingested",
    description="Record that ingest_packet.py --commit ran successfully for this packet.",
)
async def mark_ingested(
    packet_id: str,
    _: str = Depends(verify_admin_key),
    sb: SupabaseClient = Depends(get_supabase),
) -> IntakePacketRow:

    existing = (
        sb.schema("operations").table("intake_packets")
        .select("packet_id,packet_status")
        .eq("packet_id", packet_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail=f"Packet '{packet_id}' not found.")
    if existing.data[0]["packet_status"] not in ("approved", "ingested"):
        raise HTTPException(
            status_code=409,
            detail="Only approved packets can be marked as ingested.",
        )

    res = (
        sb.schema("operations").table("intake_packets")
        .update({"packet_status": "ingested", "ingested_at": NOW()})
        .eq("packet_id", packet_id)
        .execute()
    )
    return _row_to_packet_row(res.data[0])
