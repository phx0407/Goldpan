"""
api/routers/business_development.py — Business Development OS endpoints

Endpoints:
  GET    /admin/business-development                      — partner pipeline list
  GET    /admin/business-development/{external_id}        — partner detail + action history
  POST   /admin/business-development                      — create partner
  PATCH  /admin/business-development/{external_id}        — update partner fields
  POST   /admin/business-development/{external_id}/actions — add action/note

Restaurant partners are enriched with live restaurant intelligence from the
evidence and knowledge schemas (dish count, coverage, freshness, etc.).

Python 3.9 compatible — no `X | Y` union syntax, no lowercase generics.
No `from __future__ import annotations` (Pydantic models present).
"""

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client as SupabaseClient

from api.deps import get_supabase, verify_admin_key

router = APIRouter(prefix="/admin/business-development", tags=["Business Development"])


# ══════════════════════════════════════════════════════════════════════════════
# Sub-models
# ══════════════════════════════════════════════════════════════════════════════

class PartnerIntel(BaseModel):
    """Restaurant intelligence — only present when partner_type == 'restaurant'."""
    dish_count:               int
    ingredient_count:         int
    transparency_coverage_pct: float
    avg_transparency_score:   Optional[float]
    calorie_coverage_pct:     float
    claims_count:             int
    unknown_filter_count:     int
    lifecycle_status:         str
    recanvass_status:         str
    last_canvassed:           Optional[str]


class PartnerRow(BaseModel):
    partner_id:         str
    external_id:        str
    partner_type:       str
    name:               str
    contact_name:       Optional[str]
    contact_title:      Optional[str]
    status:             str
    pipeline_stage:     Optional[str]
    priority:           str
    opportunity_score:  Optional[int]
    relationship_owner: Optional[str]
    source:             Optional[str]
    deal_value:         Optional[str]
    email:              Optional[str]
    phone:              Optional[str]
    instagram:          Optional[str]
    website:            Optional[str]
    address:            Optional[str]
    city:               Optional[str]
    state:              Optional[str]
    latitude:           Optional[float]
    longitude:          Optional[float]
    geocode_source:     Optional[str]
    geocoded_at:        Optional[str]
    first_contact_date: Optional[str]
    last_contact_date:  Optional[str]
    next_followup_date: Optional[str]
    notes:              Optional[str]
    objections:         Optional[str]
    strategic_value:    Optional[str]
    audience_fit:       Optional[str]
    partnership_model:  Optional[str]
    restaurant_id:      Optional[str]
    created_at:         str
    updated_at:         str
    intel:              Optional[PartnerIntel] = None


class PartnerListSummary(BaseModel):
    total:          int
    active:         int
    high_priority:  int
    follow_ups_due: int             = Field(description="Partners with next_followup_date <= today")
    by_status:      Dict[str, int]
    by_type:        Dict[str, int]


class PartnerListResponse(BaseModel):
    generated_at: str
    summary:      PartnerListSummary
    partners:     List[PartnerRow]


class ActionRow(BaseModel):
    action_id:    str
    action_type:  str
    content:      Optional[str]
    old_status:   Optional[str]
    new_status:   Optional[str]
    performed_by: Optional[str]
    performed_at: str


class PartnerDetailResponse(BaseModel):
    generated_at: str
    partner:      PartnerRow
    actions:      List[ActionRow]


# ══════════════════════════════════════════════════════════════════════════════
# Request bodies
# ══════════════════════════════════════════════════════════════════════════════

class PartnerCreate(BaseModel):
    partner_type:       str
    name:               str
    restaurant_id:      Optional[str] = None    # UUID of evidence.restaurants row
    contact_name:       Optional[str] = None
    contact_title:      Optional[str] = None
    status:             str           = "prospect"
    pipeline_stage:     Optional[str] = None
    priority:           str           = "medium"
    opportunity_score:  Optional[int] = None
    relationship_owner: Optional[str] = None
    source:             Optional[str] = None
    deal_value:         Optional[str] = None
    email:              Optional[str] = None
    phone:              Optional[str] = None
    instagram:          Optional[str] = None
    website:            Optional[str] = None
    city:               Optional[str] = None
    state:              Optional[str] = None
    notes:              Optional[str] = None
    objections:         Optional[str] = None
    strategic_value:    Optional[str] = None
    audience_fit:       Optional[str] = None
    partnership_model:  Optional[str] = None


class PartnerUpdate(BaseModel):
    """Partial update — only explicitly-provided fields (including explicit null) are written.
    Uses model_dump(exclude_unset=True) so omitted fields are ignored, but
    fields sent as null ARE written (clears the column in the DB).
    """
    name:               Optional[str]   = None
    contact_name:       Optional[str]   = None
    contact_title:      Optional[str]   = None
    status:             Optional[str]   = None
    pipeline_stage:     Optional[str]   = None
    priority:           Optional[str]   = None
    opportunity_score:  Optional[int]   = None
    relationship_owner: Optional[str]   = None
    source:             Optional[str]   = None
    deal_value:         Optional[str]   = None
    email:              Optional[str]   = None
    phone:              Optional[str]   = None
    instagram:          Optional[str]   = None
    website:            Optional[str]   = None
    address:            Optional[str]   = None
    city:               Optional[str]   = None
    state:              Optional[str]   = None
    latitude:           Optional[float] = None
    longitude:          Optional[float] = None
    geocode_source:     Optional[str]   = None
    geocoded_at:        Optional[str]   = None
    first_contact_date: Optional[str]   = None
    last_contact_date:  Optional[str]   = None
    next_followup_date: Optional[str]   = None
    notes:              Optional[str]   = None
    objections:         Optional[str]   = None
    strategic_value:    Optional[str]   = None
    audience_fit:       Optional[str]   = None
    partnership_model:  Optional[str]   = None


class ActionCreate(BaseModel):
    action_type:  str
    content:      Optional[str] = None
    performed_by: Optional[str] = None
    old_status:   Optional[str] = None
    new_status:   Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

_EMPTY_CALORIE: set = {"", "null", "unknown", "Unknown", "N/A", "n/a"}


def _has_calorie(value: Any) -> bool:
    return bool(value) and str(value).strip() not in _EMPTY_CALORIE


def _build_partner_row(p: Dict[str, Any], intel: Optional[PartnerIntel] = None) -> PartnerRow:
    lat = p.get("latitude")
    lon = p.get("longitude")
    return PartnerRow(
        partner_id         = p["partner_id"],
        external_id        = p["external_id"],
        partner_type       = p["partner_type"],
        name               = p["name"],
        contact_name       = p.get("contact_name"),
        contact_title      = p.get("contact_title"),
        status             = p["status"],
        pipeline_stage     = p.get("pipeline_stage"),
        priority           = p["priority"],
        opportunity_score  = p.get("opportunity_score"),
        relationship_owner = p.get("relationship_owner"),
        source             = p.get("source"),
        deal_value         = p.get("deal_value"),
        email              = p.get("email"),
        phone              = p.get("phone"),
        instagram          = p.get("instagram"),
        website            = p.get("website"),
        address            = p.get("address"),
        city               = p.get("city"),
        state              = p.get("state"),
        latitude           = float(lat) if lat is not None else None,
        longitude          = float(lon) if lon is not None else None,
        geocode_source     = p.get("geocode_source"),
        geocoded_at        = p.get("geocoded_at"),
        first_contact_date = p.get("first_contact_date"),
        last_contact_date  = p.get("last_contact_date"),
        next_followup_date = p.get("next_followup_date"),
        notes              = p.get("notes"),
        objections         = p.get("objections"),
        strategic_value    = p.get("strategic_value"),
        audience_fit       = p.get("audience_fit"),
        partnership_model  = p.get("partnership_model"),
        restaurant_id      = p.get("restaurant_id"),
        created_at         = p["created_at"],
        updated_at         = p["updated_at"],
        intel              = intel,
    )


def _fetch_restaurant_intel(
    sb: SupabaseClient,
    restaurant_ids: List[str],
) -> Dict[str, PartnerIntel]:
    """
    Bulk-fetch restaurant intelligence for a list of restaurant UUIDs.
    Returns a map: restaurant_id -> PartnerIntel.
    Mirrors the aggregation logic in restaurants.py.
    """
    if not restaurant_ids:
        return {}

    # Restaurants (lifecycle + freshness)
    r_res = (
        sb.schema("evidence").table("restaurants")
        .select("restaurant_id,lifecycle_status,recanvass_status,last_canvassed")
        .in_("restaurant_id", restaurant_ids)
        .execute()
    )
    rest_map: Dict[str, Dict[str, Any]] = {
        r["restaurant_id"]: r for r in r_res.data
    }

    # Active dishes
    d_res = (
        sb.schema("evidence").table("dishes")
        .select("restaurant_id,dish_id,calorie_value")
        .in_("restaurant_id", restaurant_ids)
        .eq("is_active", True)
        .execute()
    )
    dish_counts:   Dict[str, int] = defaultdict(int)
    calorie_counts: Dict[str, int] = defaultdict(int)
    for d in d_res.data:
        rid = d["restaurant_id"]
        dish_counts[rid] += 1
        if _has_calorie(d.get("calorie_value")):
            calorie_counts[rid] += 1

    # Active ingredients
    i_res = (
        sb.schema("evidence").table("ingredients")
        .select("restaurant_id")
        .in_("restaurant_id", restaurant_ids)
        .eq("is_active", True)
        .execute()
    )
    ingredient_counts: Dict[str, int] = defaultdict(int)
    for i in i_res.data:
        ingredient_counts[i["restaurant_id"]] += 1

    # Current transparency scores
    ts_res = (
        sb.schema("knowledge").table("transparency_scores")
        .select("restaurant_id,dish_id,total_score")
        .in_("restaurant_id", restaurant_ids)
        .eq("is_current", True)
        .execute()
    )
    ts_dish_ids:   Dict[str, set]         = defaultdict(set)
    ts_score_lists: Dict[str, List[float]] = defaultdict(list)
    for ts in ts_res.data:
        rid = ts["restaurant_id"]
        ts_dish_ids[rid].add(ts["dish_id"])
        if ts.get("total_score") is not None:
            ts_score_lists[rid].append(float(ts["total_score"]))

    # Claims
    cl_res = (
        sb.schema("evidence").table("restaurant_claims")
        .select("restaurant_id")
        .in_("restaurant_id", restaurant_ids)
        .execute()
    )
    claims_counts: Dict[str, int] = defaultdict(int)
    for c in cl_res.data:
        claims_counts[c["restaurant_id"]] += 1

    # Unknown derived filters
    df_res = (
        sb.schema("knowledge").table("derived_filters")
        .select("restaurant_id,dish_id")
        .in_("restaurant_id", restaurant_ids)
        .eq("is_current", True)
        .eq("conclusion", "unknown")
        .execute()
    )
    unknown_dish_ids: Dict[str, set] = defaultdict(set)
    for df in df_res.data:
        unknown_dish_ids[df["restaurant_id"]].add(df["dish_id"])

    # Build intel map
    intel: Dict[str, PartnerIntel] = {}
    for rid in restaurant_ids:
        if rid not in rest_map:
            continue
        r   = rest_map[rid]
        dc  = dish_counts.get(rid, 0)
        ts_count = len(ts_dish_ids.get(rid, set()))
        scores   = ts_score_lists.get(rid, [])

        intel[rid] = PartnerIntel(
            dish_count               = dc,
            ingredient_count         = ingredient_counts.get(rid, 0),
            transparency_coverage_pct = round(ts_count / dc * 100, 1) if dc else 0.0,
            avg_transparency_score   = round(sum(scores) / len(scores), 1) if scores else None,
            calorie_coverage_pct     = round(calorie_counts.get(rid, 0) / dc * 100, 1) if dc else 0.0,
            claims_count             = claims_counts.get(rid, 0),
            unknown_filter_count     = len(unknown_dish_ids.get(rid, set())),
            lifecycle_status         = r.get("lifecycle_status", "unknown"),
            recanvass_status         = r.get("recanvass_status", "unknown"),
            last_canvassed           = r.get("last_canvassed"),
        )

    return intel


# ══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "",
    response_model=PartnerListResponse,
    summary="Partner pipeline list",
    description=(
        "All partners with pipeline status, contact info, and (for restaurant "
        "partners) live restaurant intelligence from the evidence system."
    ),
)
async def get_partner_list(
    _:  str             = Depends(verify_admin_key),
    sb: SupabaseClient  = Depends(get_supabase),
) -> PartnerListResponse:

    # ── Partners ──────────────────────────────────────────────────────────────
    p_res = (
        sb.schema("operations").table("partners")
        .select("*")
        .order("name")
        .execute()
    )
    all_partners: List[Dict[str, Any]] = p_res.data

    # ── Collect restaurant_ids for intel enrichment ───────────────────────────
    restaurant_ids: List[str] = [
        p["restaurant_id"]
        for p in all_partners
        if p.get("partner_type") == "restaurant" and p.get("restaurant_id")
    ]
    intel_map = _fetch_restaurant_intel(sb, restaurant_ids)

    # ── Build rows ────────────────────────────────────────────────────────────
    today = date.today().isoformat()
    rows: List[PartnerRow] = []
    status_counter: Dict[str, int] = defaultdict(int)
    type_counter:   Dict[str, int] = defaultdict(int)
    active_count        = 0
    high_priority_count = 0
    follow_ups_due      = 0

    for p in all_partners:
        rid   = p.get("restaurant_id")
        intel = intel_map.get(rid) if rid else None
        row   = _build_partner_row(p, intel)
        rows.append(row)

        status_counter[p["status"]] += 1
        type_counter[p["partner_type"]] += 1

        if p["status"] == "active":
            active_count += 1
        if p["priority"] == "high":
            high_priority_count += 1
        nf = p.get("next_followup_date")
        if nf and nf <= today:
            follow_ups_due += 1

    summary = PartnerListSummary(
        total          = len(rows),
        active         = active_count,
        high_priority  = high_priority_count,
        follow_ups_due = follow_ups_due,
        by_status      = dict(status_counter),
        by_type        = dict(type_counter),
    )

    return PartnerListResponse(
        generated_at = datetime.now(timezone.utc).isoformat(),
        summary      = summary,
        partners     = rows,
    )


@router.get(
    "/{external_id}",
    response_model=PartnerDetailResponse,
    summary="Partner detail",
    description="Partner record with full field set, restaurant intel (if applicable), and action history.",
)
async def get_partner_detail(
    external_id: str,
    _:  str             = Depends(verify_admin_key),
    sb: SupabaseClient  = Depends(get_supabase),
) -> PartnerDetailResponse:

    p_res = (
        sb.schema("operations").table("partners")
        .select("*")
        .eq("external_id", external_id.upper())
        .limit(1)
        .execute()
    )
    if not p_res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partner '{external_id}' not found.",
        )
    p: Dict[str, Any] = p_res.data[0]

    # Intel enrichment for restaurant partners
    intel: Optional[PartnerIntel] = None
    rid = p.get("restaurant_id")
    if p.get("partner_type") == "restaurant" and rid:
        intel_map = _fetch_restaurant_intel(sb, [rid])
        intel = intel_map.get(rid)

    # Action history
    a_res = (
        sb.schema("operations").table("partner_actions")
        .select("action_id,action_type,content,old_status,new_status,performed_by,performed_at")
        .eq("partner_id", p["partner_id"])
        .order("performed_at", desc=True)
        .execute()
    )
    actions = [
        ActionRow(
            action_id    = a["action_id"],
            action_type  = a["action_type"],
            content      = a.get("content"),
            old_status   = a.get("old_status"),
            new_status   = a.get("new_status"),
            performed_by = a.get("performed_by"),
            performed_at = a["performed_at"],
        )
        for a in a_res.data
    ]

    return PartnerDetailResponse(
        generated_at = datetime.now(timezone.utc).isoformat(),
        partner      = _build_partner_row(p, intel),
        actions      = actions,
    )


@router.post(
    "",
    response_model=PartnerDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create partner",
)
async def create_partner(
    body: PartnerCreate,
    _:   str            = Depends(verify_admin_key),
    sb:  SupabaseClient = Depends(get_supabase),
) -> PartnerDetailResponse:

    payload: Dict[str, Any] = {
        k: v for k, v in body.model_dump().items() if v is not None
    }
    # external_id filled by DB trigger — do not pass it
    payload.pop("external_id", None)

    insert_res = (
        sb.schema("operations").table("partners")
        .insert(payload)
        .execute()
    )
    if not insert_res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create partner.",
        )

    new_external_id: str = insert_res.data[0]["external_id"]
    return await get_partner_detail(new_external_id, _, sb)


@router.patch(
    "/{external_id}",
    response_model=PartnerDetailResponse,
    summary="Update partner fields",
    description="Partial update — only provided (non-null) fields are written.",
)
async def update_partner(
    external_id: str,
    body: PartnerUpdate,
    _:   str            = Depends(verify_admin_key),
    sb:  SupabaseClient = Depends(get_supabase),
) -> PartnerDetailResponse:

    # Look up partner_id
    lookup = (
        sb.schema("operations").table("partners")
        .select("partner_id")
        .eq("external_id", external_id.upper())
        .limit(1)
        .execute()
    )
    if not lookup.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partner '{external_id}' not found.",
        )

    # exclude_unset=True: only fields explicitly sent are updated;
    # explicit null values ARE included (they clear the DB column).
    updates: Dict[str, Any] = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields to update.",
        )

    (
        sb.schema("operations").table("partners")
        .update(updates)
        .eq("external_id", external_id.upper())
        .execute()
    )

    return await get_partner_detail(external_id, _, sb)


@router.post(
    "/{external_id}/actions",
    response_model=ActionRow,
    status_code=status.HTTP_201_CREATED,
    summary="Add action / note",
    description="Append an action to the partner's history log.",
)
async def add_partner_action(
    external_id: str,
    body: ActionCreate,
    _:   str            = Depends(verify_admin_key),
    sb:  SupabaseClient = Depends(get_supabase),
) -> ActionRow:

    # Look up partner_id
    lookup = (
        sb.schema("operations").table("partners")
        .select("partner_id")
        .eq("external_id", external_id.upper())
        .limit(1)
        .execute()
    )
    if not lookup.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partner '{external_id}' not found.",
        )
    partner_uuid: str = lookup.data[0]["partner_id"]

    payload: Dict[str, Any] = {
        "partner_id":   partner_uuid,
        "action_type":  body.action_type,
    }
    if body.content:
        payload["content"] = body.content
    if body.performed_by:
        payload["performed_by"] = body.performed_by
    if body.old_status:
        payload["old_status"] = body.old_status
    if body.new_status:
        payload["new_status"] = body.new_status

    insert_res = (
        sb.schema("operations").table("partner_actions")
        .insert(payload)
        .execute()
    )
    if not insert_res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to insert action.",
        )
    a = insert_res.data[0]
    return ActionRow(
        action_id    = a["action_id"],
        action_type  = a["action_type"],
        content      = a.get("content"),
        old_status   = a.get("old_status"),
        new_status   = a.get("new_status"),
        performed_by = a.get("performed_by"),
        performed_at = a["performed_at"],
    )
