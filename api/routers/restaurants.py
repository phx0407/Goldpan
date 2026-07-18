"""
api/routers/restaurants.py — Restaurant Operations endpoints

Endpoints:
  GET /admin/restaurants        — list all restaurants with aggregates
  GET /admin/restaurants/lookup — minimal list for CRM dropdowns (id, name, location)
  GET /admin/restaurants/{id}   — detail for one restaurant (by external_id)

Python 3.9 compatible — uses typing.List / Dict / Optional throughout.
No `X | None` or lowercase generic aliases in annotations.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import Client as SupabaseClient

from api.deps import get_supabase, verify_admin_key

router = APIRouter(prefix="/admin/restaurants", tags=["Restaurants"])


# ══════════════════════════════════════════════════════════════════════════════
# Response models — list endpoint
# ══════════════════════════════════════════════════════════════════════════════

class RestaurantSummaryRow(BaseModel):
    restaurant_id:            str
    external_id:              str
    name:                     str
    location:                 Optional[str]
    lifecycle_status:         str
    recanvass_status:         str
    last_canvassed:           Optional[str]
    source_check_status:      str
    has_allergen_guide:       bool
    dish_count:               int
    ingredient_count:         int
    transparency_coverage_pct: float = Field(description="% active dishes with a current transparency score")
    avg_transparency_score:   Optional[float]
    calorie_coverage_pct:     float  = Field(description="% active dishes with calorie_value set")
    claims_count:             int
    unknown_filter_count:     int    = Field(description="dishes with ≥1 unknown derived filter conclusion")


class RestaurantListSummary(BaseModel):
    total:                  int
    published:              int
    recanvass_needs_review: int
    recanvass_overdue:      int
    recanvass_due_soon:     int
    recanvass_current:      int
    by_lifecycle:           Dict[str, int]


class RestaurantListResponse(BaseModel):
    generated_at: str
    summary:      RestaurantListSummary
    restaurants:  List[RestaurantSummaryRow]


# ══════════════════════════════════════════════════════════════════════════════
# Response models — detail endpoint
# ══════════════════════════════════════════════════════════════════════════════

class RestaurantInfo(BaseModel):
    restaurant_id:      str
    external_id:        str
    name:               str
    location:           Optional[str]
    address:            Optional[str]
    city:               Optional[str]
    state:              Optional[str]
    postal_code:        Optional[str]
    phone:              Optional[str]
    official_website:   Optional[str]
    menu_url:           Optional[str]
    google_place_id:    Optional[str]
    latitude:           Optional[float]
    longitude:          Optional[float]
    hours:              Optional[str]
    menu_statement:     Optional[str]
    lifecycle_status:   str
    recanvass_status:   str
    last_canvassed:     Optional[str]
    recanvass_tier:     int
    source_check_status: str
    last_source_check:  Optional[str]
    has_allergen_guide: bool
    evidence_tier:      Optional[str]
    published_date:     Optional[str]
    notes:              Optional[str]
    created_at:         str
    updated_at:         str


class MenuSourceRow(BaseModel):
    source_id:             str
    official_website:      Optional[str]
    official_menu_url:     Optional[str]
    online_ordering_url:   Optional[str]
    allergen_nutrition_url: Optional[str]
    preferred_data_source: Optional[str]
    source_confidence:     Optional[str]
    menu_status:           Optional[str]
    recanvass_status:      str
    last_canvassed:        Optional[str]
    last_verified_date:    Optional[str]
    source_check_status:   str


class DishRow(BaseModel):
    dish_id:              str
    external_id:          str
    dish_name:            str
    menu_section:         Optional[str]
    category:             Optional[str]
    status:               str
    is_active:            bool
    ingredient_count:     int
    has_transparency_score: bool
    transparency_score:   Optional[float]
    has_calorie:          bool
    calorie_value:        Optional[str]
    tag_source:           Optional[str]
    unknown_filter_count: int


class ClaimRow(BaseModel):
    claim_id:    str
    claim_type:  Optional[str]
    claim_text:  str
    source_type: Optional[str]
    created_at:  str


class RestaurantStatsModel(BaseModel):
    dish_count:               int
    active_dish_count:        int
    ingredient_count:         int
    transparency_coverage_pct: float
    avg_transparency_score:   Optional[float]
    calorie_coverage_pct:     float
    claims_count:             int
    unknown_filter_count:     int
    menu_sources_count:       int


class PartnerLinkRow(BaseModel):
    """Linked BD partner record for this restaurant (read-only cross-link)."""
    partner_id:         str
    external_id:        str
    name:               str
    contact_name:       Optional[str]
    status:             str
    pipeline_stage:     Optional[str]
    priority:           str
    relationship_owner: Optional[str]
    last_contact_date:  Optional[str]
    next_followup_date: Optional[str]


class FilterSummaryRow(BaseModel):
    """Per-filter governance conclusion counts for this restaurant."""
    filter_slug:          str
    filter_name:          str
    computed_count:       int   = Field(description="Dishes with a computed conclusion")
    unknown_count:        int   = Field(description="Dishes with unknown (insufficient evidence)")
    not_applicable_count: int   = Field(description="Dishes where filter does not apply")


class RestaurantDetailResponse(BaseModel):
    generated_at:   str
    restaurant:     RestaurantInfo
    stats:          RestaurantStatsModel
    menu_sources:   List[MenuSourceRow]
    dishes:         List[DishRow]
    claims:         List[ClaimRow]
    linked_partners: List[PartnerLinkRow]   = Field(default_factory=list)
    filter_summary:  List[FilterSummaryRow] = Field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# Lookup model (for CRM dropdowns)
# ══════════════════════════════════════════════════════════════════════════════

class RestaurantLookupItem(BaseModel):
    restaurant_id:    str
    external_id:      str
    name:             str
    location:         Optional[str]
    address:          Optional[str]
    city:             Optional[str]
    state:            Optional[str]
    official_website: Optional[str]


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

_EMPTY_CALORIE: set = {"", "null", "unknown", "Unknown", "N/A", "n/a"}


def _parse_location(location: Optional[str]) -> tuple:
    """Derive (city, state) from a free-form location string as a fallback.

    Handles formats like:
      "Hoover"          → ("Hoover", None)
      "Hoover, AL"      → ("Hoover", "AL")
      "Birmingham, AL"  → ("Birmingham", "AL")
    Returns (None, None) if location is empty.
    """
    if not location:
        return (None, None)
    parts = [p.strip() for p in location.split(",")]
    city  = parts[0] if parts[0] else None
    state = parts[1].upper() if len(parts) >= 2 and parts[1].strip() else None
    return (city, state)


def _has_calorie(value: Any) -> bool:
    return bool(value) and str(value).strip() not in _EMPTY_CALORIE


# ══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "",
    response_model=RestaurantListResponse,
    summary="Restaurant list with aggregates",
    description=(
        "All non-deactivated restaurants with dish/ingredient counts, "
        "transparency coverage, calorie coverage, and freshness status."
    ),
)
async def get_restaurant_list(
    _: str = Depends(verify_admin_key),
    sb: SupabaseClient = Depends(get_supabase),
) -> RestaurantListResponse:

    # ── 1. Restaurants ────────────────────────────────────────────────────────
    r_res = (
        sb.schema("evidence").table("restaurants")
        .select(
            "restaurant_id,external_id,name,location,lifecycle_status,"
            "recanvass_status,last_canvassed,source_check_status,has_allergen_guide"
        )
        .neq("lifecycle_status", "deactivated")
        .order("name")
        .execute()
    )
    all_restaurants: List[Dict[str, Any]] = r_res.data

    # ── 2. Active dishes (restaurant_id + calorie_value) ─────────────────────
    d_res = (
        sb.schema("evidence").table("dishes")
        .select("restaurant_id,dish_id,calorie_value")
        .eq("is_active", True)
        .execute()
    )
    all_dishes: List[Dict[str, Any]] = d_res.data

    # ── 3. Active ingredients (restaurant_id only — for count) ───────────────
    i_res = (
        sb.schema("evidence").table("ingredients")
        .select("restaurant_id")
        .eq("is_active", True)
        .execute()
    )
    all_ingredients: List[Dict[str, Any]] = i_res.data

    # ── 4. Current transparency scores ───────────────────────────────────────
    ts_res = (
        sb.schema("knowledge").table("transparency_scores")
        .select("restaurant_id,dish_id,total_score")
        .eq("is_current", True)
        .execute()
    )
    all_ts: List[Dict[str, Any]] = ts_res.data

    # ── 5. Claims (restaurant_id only — for count) ───────────────────────────
    cl_res = (
        sb.schema("evidence").table("restaurant_claims")
        .select("restaurant_id")
        .execute()
    )
    all_claims: List[Dict[str, Any]] = cl_res.data

    # ── 6. Unknown derived filter conclusions (unique dish count per restaurant)
    df_res = (
        sb.schema("knowledge").table("derived_filters")
        .select("restaurant_id,dish_id")
        .eq("is_current", True)
        .eq("conclusion", "unknown")
        .execute()
    )
    all_unknown_df: List[Dict[str, Any]] = df_res.data

    # ── Aggregate ─────────────────────────────────────────────────────────────
    dish_counts:    Dict[str, int] = defaultdict(int)
    calorie_counts: Dict[str, int] = defaultdict(int)
    for d in all_dishes:
        rid = d["restaurant_id"]
        dish_counts[rid] += 1
        if _has_calorie(d.get("calorie_value")):
            calorie_counts[rid] += 1

    ingredient_counts: Dict[str, int] = defaultdict(int)
    for i in all_ingredients:
        ingredient_counts[i["restaurant_id"]] += 1

    ts_dish_ids: Dict[str, set] = defaultdict(set)
    ts_score_lists: Dict[str, List[float]] = defaultdict(list)
    for ts in all_ts:
        rid = ts["restaurant_id"]
        ts_dish_ids[rid].add(ts["dish_id"])
        if ts.get("total_score") is not None:
            ts_score_lists[rid].append(float(ts["total_score"]))

    claims_counts: Dict[str, int] = defaultdict(int)
    for c in all_claims:
        claims_counts[c["restaurant_id"]] += 1

    unknown_dish_ids: Dict[str, set] = defaultdict(set)
    for df in all_unknown_df:
        unknown_dish_ids[df["restaurant_id"]].add(df["dish_id"])

    # ── Build rows ────────────────────────────────────────────────────────────
    rows: List[RestaurantSummaryRow] = []
    lifecycle_counter: Dict[str, int] = defaultdict(int)

    for r in all_restaurants:
        rid = r["restaurant_id"]
        dc = dish_counts.get(rid, 0)
        scores = ts_score_lists.get(rid, [])
        ts_count = len(ts_dish_ids.get(rid, set()))

        rows.append(RestaurantSummaryRow(
            restaurant_id             = rid,
            external_id               = r["external_id"],
            name                      = r["name"],
            location                  = r.get("location"),
            lifecycle_status          = r["lifecycle_status"],
            recanvass_status          = r["recanvass_status"],
            last_canvassed            = r.get("last_canvassed"),
            source_check_status       = r.get("source_check_status") or "unknown",
            has_allergen_guide        = bool(r.get("has_allergen_guide", False)),
            dish_count                = dc,
            ingredient_count          = ingredient_counts.get(rid, 0),
            transparency_coverage_pct = round(ts_count / dc * 100, 1) if dc > 0 else 0.0,
            avg_transparency_score    = round(sum(scores) / len(scores), 1) if scores else None,
            calorie_coverage_pct      = round(calorie_counts.get(rid, 0) / dc * 100, 1) if dc > 0 else 0.0,
            claims_count              = claims_counts.get(rid, 0),
            unknown_filter_count      = len(unknown_dish_ids.get(rid, set())),
        ))
        lifecycle_counter[r["lifecycle_status"]] += 1

    summary = RestaurantListSummary(
        total                  = len(rows),
        published              = lifecycle_counter.get("published", 0),
        recanvass_needs_review = sum(1 for r in rows if r.recanvass_status == "needs_review"),
        recanvass_overdue      = sum(1 for r in rows if r.recanvass_status == "overdue"),
        recanvass_due_soon     = sum(1 for r in rows if r.recanvass_status == "due_soon"),
        recanvass_current      = sum(1 for r in rows if r.recanvass_status == "current"),
        by_lifecycle           = dict(lifecycle_counter),
    )

    return RestaurantListResponse(
        generated_at = datetime.now(timezone.utc).isoformat(),
        summary      = summary,
        restaurants  = rows,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Map endpoint model
# ══════════════════════════════════════════════════════════════════════════════

class RestaurantMapItem(BaseModel):
    """One map pin — only what the public map needs."""
    external_id:      str
    name:             str
    address:          Optional[str]
    city:             Optional[str]
    state:            Optional[str]
    latitude:         float
    longitude:        float
    official_website: Optional[str]
    menu_url:         Optional[str]


# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/map",
    response_model=List[RestaurantMapItem],
    summary="Published restaurants for the public map",
    description=(
        "Returns published restaurants that have geocoordinates. "
        "Used by the public-facing restaurant map. "
        "Excludes draft, paused, and deactivated restaurants."
    ),
)
async def get_restaurants_for_map(
    _:  str            = Depends(verify_admin_key),
    sb: SupabaseClient = Depends(get_supabase),
) -> List[RestaurantMapItem]:
    r_res = (
        sb.schema("evidence").table("restaurants")
        .select(
            "external_id,name,address,city,state,latitude,longitude,"
            "official_website,menu_url,location"
        )
        .eq("lifecycle_status", "published")
        .not_.is_("latitude",  "null")
        .not_.is_("longitude", "null")
        .order("name")
        .execute()
    )

    items: List[RestaurantMapItem] = []
    for r in r_res.data:
        raw_city  = r.get("city")
        raw_state = r.get("state")
        if not raw_city or not raw_state:
            parsed_city, parsed_state = _parse_location(r.get("location"))
            if not raw_city:
                raw_city = parsed_city
            if not raw_state:
                raw_state = parsed_state
        items.append(RestaurantMapItem(
            external_id      = r["external_id"],
            name             = r["name"],
            address          = r.get("address"),
            city             = raw_city,
            state            = raw_state,
            latitude         = float(r["latitude"]),
            longitude        = float(r["longitude"]),
            official_website = r.get("official_website"),
            menu_url         = r.get("menu_url"),
        ))
    return items


# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/lookup",
    response_model=List[RestaurantLookupItem],
    summary="Minimal restaurant list for CRM dropdowns",
    description="Returns id, external_id, name, location only — used by the BD partner form.",
)
async def get_restaurants_lookup(
    _:  str             = Depends(verify_admin_key),
    sb: SupabaseClient  = Depends(get_supabase),
) -> List[RestaurantLookupItem]:
    r_res = (
        sb.schema("evidence").table("restaurants")
        .select("restaurant_id,external_id,name,location,address,city,state,official_website")
        .neq("lifecycle_status", "deactivated")
        .order("name")
        .execute()
    )
    items = []
    for r in r_res.data:
        raw_city  = r.get("city")
        raw_state = r.get("state")
        # Derive city/state from location if structured fields are null
        if not raw_city or not raw_state:
            parsed_city, parsed_state = _parse_location(r.get("location"))
            if not raw_city:
                raw_city = parsed_city
            if not raw_state:
                raw_state = parsed_state
        items.append(RestaurantLookupItem(
            restaurant_id    = r["restaurant_id"],
            external_id      = r["external_id"],
            name             = r["name"],
            location         = r.get("location"),
            address          = r.get("address"),
            city             = raw_city,
            state            = raw_state,
            official_website = r.get("official_website"),
        ))
    return items


@router.get(
    "/{external_id}",
    response_model=RestaurantDetailResponse,
    summary="Restaurant detail",
    description="Full restaurant master page — info, stats, dishes, sources, claims.",
)
async def get_restaurant_detail(
    external_id: str,
    _: str = Depends(verify_admin_key),
    sb: SupabaseClient = Depends(get_supabase),
) -> RestaurantDetailResponse:

    # ── 1. Restaurant ─────────────────────────────────────────────────────────
    r_res = (
        sb.schema("evidence").table("restaurants")
        .select("*")
        .eq("external_id", external_id.upper())
        .limit(1)
        .execute()
    )
    if not r_res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Restaurant '{external_id}' not found.",
        )
    r: Dict[str, Any] = r_res.data[0]
    rid: str = r["restaurant_id"]

    # ── 2. Menu sources ───────────────────────────────────────────────────────
    ms_res = (
        sb.schema("evidence").table("menu_sources")
        .select(
            "source_id,official_website,official_menu_url,online_ordering_url,"
            "allergen_nutrition_url,preferred_data_source,source_confidence,"
            "menu_status,recanvass_status,last_canvassed,last_verified_date,source_check_status"
        )
        .eq("restaurant_id", rid)
        .execute()
    )
    menu_sources_raw: List[Dict[str, Any]] = ms_res.data

    # ── 3. Dishes ─────────────────────────────────────────────────────────────
    d_res = (
        sb.schema("evidence").table("dishes")
        .select(
            "dish_id,external_id,dish_name,menu_section,category,"
            "status,is_active,calorie_value,tag_source"
        )
        .eq("restaurant_id", rid)
        .order("menu_section")
        .order("dish_name")
        .execute()
    )
    dishes_raw: List[Dict[str, Any]] = d_res.data

    # ── 4. Ingredient counts per dish ─────────────────────────────────────────
    ing_res = (
        sb.schema("evidence").table("ingredients")
        .select("dish_id")
        .eq("restaurant_id", rid)
        .eq("is_active", True)
        .execute()
    )
    ing_counts: Dict[str, int] = defaultdict(int)
    for i in ing_res.data:
        ing_counts[i["dish_id"]] += 1

    # ── 5. Transparency scores per dish ───────────────────────────────────────
    ts_res = (
        sb.schema("knowledge").table("transparency_scores")
        .select("dish_id,total_score")
        .eq("restaurant_id", rid)
        .eq("is_current", True)
        .execute()
    )
    ts_by_dish: Dict[str, float] = {}
    for ts in ts_res.data:
        if ts.get("total_score") is not None:
            ts_by_dish[ts["dish_id"]] = float(ts["total_score"])

    # ── 6. Unknown derived filter count per dish ──────────────────────────────
    df_res = (
        sb.schema("knowledge").table("derived_filters")
        .select("dish_id")
        .eq("restaurant_id", rid)
        .eq("is_current", True)
        .eq("conclusion", "unknown")
        .execute()
    )
    unknown_per_dish: Dict[str, int] = defaultdict(int)
    for df in df_res.data:
        unknown_per_dish[df["dish_id"]] += 1

    # ── 7. Claims ─────────────────────────────────────────────────────────────
    cl_res = (
        sb.schema("evidence").table("restaurant_claims")
        .select("claim_id,claim_type,claim_text,source_type,created_at")
        .eq("restaurant_id", rid)
        .order("created_at")
        .execute()
    )
    claims_raw: List[Dict[str, Any]] = cl_res.data

    # ── 8. Linked BD partners (cross-link — read-only) ────────────────────────
    pt_res = (
        sb.schema("operations").table("partners")
        .select(
            "partner_id,external_id,name,contact_name,status,"
            "pipeline_stage,priority,relationship_owner,"
            "last_contact_date,next_followup_date"
        )
        .eq("restaurant_id", rid)
        .order("created_at")
        .execute()
    )
    partners_raw: List[Dict[str, Any]] = pt_res.data

    # ── 9. Governance filter summary ──────────────────────────────────────────
    # Fetch all current derived filter rows and aggregate per filter_slug.
    gf_res = (
        sb.schema("knowledge").table("derived_filters")
        .select("filter_slug,filter_name,conclusion")
        .eq("restaurant_id", rid)
        .eq("is_current", True)
        .execute()
    )
    filter_agg: Dict[str, Dict[str, Any]] = {}
    for row in gf_res.data:
        slug = row["filter_slug"]
        if slug not in filter_agg:
            filter_agg[slug] = {
                "filter_name":          row["filter_name"],
                "computed_count":       0,
                "unknown_count":        0,
                "not_applicable_count": 0,
            }
        conclusion = row.get("conclusion", "")
        if conclusion == "computed":
            filter_agg[slug]["computed_count"] += 1
        elif conclusion == "unknown":
            filter_agg[slug]["unknown_count"] += 1
        elif conclusion == "not_applicable":
            filter_agg[slug]["not_applicable_count"] += 1
    filter_summary_rows: List[FilterSummaryRow] = [
        FilterSummaryRow(
            filter_slug          = slug,
            filter_name          = agg["filter_name"],
            computed_count       = agg["computed_count"],
            unknown_count        = agg["unknown_count"],
            not_applicable_count = agg["not_applicable_count"],
        )
        for slug, agg in sorted(filter_agg.items())
    ]

    # ── Build dishes + compute stats ──────────────────────────────────────────
    dishes:          List[DishRow] = []
    active_count     = 0
    ts_covered       = 0
    calorie_covered  = 0
    all_ts_scores:   List[float] = []
    total_unknown    = 0

    for d in dishes_raw:
        did       = d["dish_id"]
        is_active = bool(d.get("is_active", True))
        ts_score  = ts_by_dish.get(did)
        has_ts    = ts_score is not None
        has_cal   = _has_calorie(d.get("calorie_value"))
        unk       = unknown_per_dish.get(did, 0)

        if is_active:
            active_count += 1
            if has_ts:
                ts_covered += 1
                all_ts_scores.append(ts_score)  # type: ignore[arg-type]
            if has_cal:
                calorie_covered += 1

        total_unknown += unk

        dishes.append(DishRow(
            dish_id               = did,
            external_id           = d["external_id"],
            dish_name             = d["dish_name"],
            menu_section          = d.get("menu_section"),
            category              = d.get("category"),
            status                = d.get("status") or "Active",
            is_active             = is_active,
            ingredient_count      = ing_counts.get(did, 0),
            has_transparency_score = has_ts,
            transparency_score    = ts_score,
            has_calorie           = has_cal,
            calorie_value         = str(d["calorie_value"]) if has_cal else None,
            tag_source            = d.get("tag_source"),
            unknown_filter_count  = unk,
        ))

    tc_pct  = round(ts_covered     / active_count * 100, 1) if active_count else 0.0
    cal_pct = round(calorie_covered / active_count * 100, 1) if active_count else 0.0
    avg_ts  = round(sum(all_ts_scores) / len(all_ts_scores), 1) if all_ts_scores else None

    stats = RestaurantStatsModel(
        dish_count               = len(dishes_raw),
        active_dish_count        = active_count,
        ingredient_count         = sum(ing_counts.values()),
        transparency_coverage_pct = tc_pct,
        avg_transparency_score   = avg_ts,
        calorie_coverage_pct     = cal_pct,
        claims_count             = len(claims_raw),
        unknown_filter_count     = total_unknown,
        menu_sources_count       = len(menu_sources_raw),
    )

    menu_sources = [
        MenuSourceRow(
            source_id             = ms["source_id"],
            official_website      = ms.get("official_website"),
            official_menu_url     = ms.get("official_menu_url"),
            online_ordering_url   = ms.get("online_ordering_url"),
            allergen_nutrition_url = ms.get("allergen_nutrition_url"),
            preferred_data_source = ms.get("preferred_data_source"),
            source_confidence     = ms.get("source_confidence"),
            menu_status           = ms.get("menu_status"),
            recanvass_status      = ms.get("recanvass_status") or "needs_review",
            last_canvassed        = ms.get("last_canvassed"),
            last_verified_date    = ms.get("last_verified_date"),
            source_check_status   = ms.get("source_check_status") or "unknown",
        )
        for ms in menu_sources_raw
    ]

    claims = [
        ClaimRow(
            claim_id   = c["claim_id"],
            claim_type = c.get("claim_type"),
            claim_text = c["claim_text"],
            source_type = c.get("source_type"),
            created_at = c["created_at"],
        )
        for c in claims_raw
    ]

    linked_partners = [
        PartnerLinkRow(
            partner_id         = p["partner_id"],
            external_id        = p["external_id"],
            name               = p["name"],
            contact_name       = p.get("contact_name"),
            status             = p.get("status") or "unknown",
            pipeline_stage     = p.get("pipeline_stage"),
            priority           = p.get("priority") or "medium",
            relationship_owner = p.get("relationship_owner"),
            last_contact_date  = p.get("last_contact_date"),
            next_followup_date = p.get("next_followup_date"),
        )
        for p in partners_raw
    ]

    return RestaurantDetailResponse(
        generated_at = datetime.now(timezone.utc).isoformat(),
        restaurant   = RestaurantInfo(
            restaurant_id      = r["restaurant_id"],
            external_id        = r["external_id"],
            name               = r["name"],
            location           = r.get("location"),
            address            = r.get("address"),
            city               = r.get("city"),
            state              = r.get("state"),
            postal_code        = r.get("postal_code"),
            phone              = r.get("phone"),
            official_website   = r.get("official_website"),
            menu_url           = r.get("menu_url"),
            google_place_id    = r.get("google_place_id"),
            latitude           = float(r["latitude"])  if r.get("latitude")  is not None else None,
            longitude          = float(r["longitude"]) if r.get("longitude") is not None else None,
            hours              = r.get("hours"),
            menu_statement     = r.get("menu_statement"),
            lifecycle_status   = r["lifecycle_status"],
            recanvass_status   = r["recanvass_status"],
            last_canvassed     = r.get("last_canvassed"),
            recanvass_tier     = int(r.get("recanvass_tier") or 2),
            source_check_status = r.get("source_check_status") or "unknown",
            last_source_check  = r.get("last_source_check"),
            has_allergen_guide = bool(r.get("has_allergen_guide", False)),
            evidence_tier      = r.get("evidence_tier"),
            published_date     = r.get("published_date"),
            notes              = r.get("notes"),
            created_at         = r["created_at"],
            updated_at         = r["updated_at"],
        ),
        stats            = stats,
        menu_sources     = menu_sources,
        dishes           = dishes,
        claims           = claims,
        linked_partners  = linked_partners,
        filter_summary   = filter_summary_rows,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Lifecycle mutation
# ══════════════════════════════════════════════════════════════════════════════

class LifecycleAction(BaseModel):
    action: str = Field(
        description="One of: publish, unpublish, recanvass, advance_to_qa, advance_to_verification"
    )
    note: Optional[str] = Field(None, description="Optional note for the audit trail")


class LifecycleResult(BaseModel):
    external_id:      str
    previous_status:  str
    new_status:       str
    recanvass_status: Optional[str]
    updated_at:       str


# Valid transitions: action → (allowed_from_statuses, new_lifecycle, new_recanvass_status)
_LIFECYCLE_TRANSITIONS: Dict[str, Any] = {
    "publish": {
        "from":     {"qa_review", "verification", "evidence_acquisition", "onboarding"},
        "to":       "published",
        "recanvass": "needs_review",
    },
    "unpublish": {
        "from":     {"published"},
        "to":       "suspended",
        "recanvass": None,  # leave unchanged
    },
    "recanvass": {
        "from":     None,  # any status
        "to":       "recanvassing",
        "recanvass": "needs_review",
    },
    "advance_to_qa": {
        "from":     {"evidence_acquisition", "verification", "onboarding"},
        "to":       "qa_review",
        "recanvass": None,
    },
    "advance_to_verification": {
        "from":     {"onboarding", "evidence_acquisition"},
        "to":       "verification",
        "recanvass": None,
    },
}


@router.patch(
    "/{external_id}/lifecycle",
    response_model=LifecycleResult,
    summary="Restaurant lifecycle action",
    description="Transition a restaurant's lifecycle_status. Valid actions: publish, unpublish, recanvass, advance_to_qa, advance_to_verification.",
)
async def lifecycle_action(
    external_id: str,
    body: LifecycleAction,
    _: str = Depends(verify_admin_key),
    sb: SupabaseClient = Depends(get_supabase),
) -> LifecycleResult:

    action = body.action.lower()
    if action not in _LIFECYCLE_TRANSITIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown action '{action}'. Valid: {', '.join(_LIFECYCLE_TRANSITIONS)}",
        )

    # Fetch current status
    res = (
        sb.schema("evidence").table("restaurants")
        .select("restaurant_id,external_id,lifecycle_status,recanvass_status")
        .eq("external_id", external_id.upper())
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Restaurant '{external_id}' not found.")
    r = res.data[0]
    prev_status = r["lifecycle_status"]

    transition = _LIFECYCLE_TRANSITIONS[action]
    allowed_from = transition["from"]
    if allowed_from is not None and prev_status not in allowed_from:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Action '{action}' not valid from status '{prev_status}'. "
                f"Allowed from: {', '.join(sorted(allowed_from))}."
            ),
        )

    new_status = transition["to"]
    new_recanvass = transition["recanvass"]

    now = datetime.now(timezone.utc).isoformat()
    update: Dict[str, Any] = {
        "lifecycle_status": new_status,
        "status_updated_at": now,
    }
    if new_recanvass is not None:
        update["recanvass_status"] = new_recanvass
    if action == "publish":
        update["published_date"] = datetime.now(timezone.utc).date().isoformat()

    upd = (
        sb.schema("evidence").table("restaurants")
        .update(update)
        .eq("external_id", external_id.upper())
        .execute()
    )
    updated = upd.data[0]

    return LifecycleResult(
        external_id      = updated["external_id"],
        previous_status  = prev_status,
        new_status       = updated["lifecycle_status"],
        recanvass_status = updated.get("recanvass_status"),
        updated_at       = now,
    )
