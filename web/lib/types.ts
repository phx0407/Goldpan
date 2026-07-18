// Types mirror the Pydantic response models in api/routers/ai_usage.py.
// Keep in sync if the API response shape changes.

export interface SpendSummary {
  today_usd: number;
  month_usd: number;
  daily_limit_usd: number;
  monthly_limit_usd: number;
  daily_remaining_usd: number;
  monthly_remaining_usd: number;
  daily_pct_used: number;
  monthly_pct_used: number;
}

export interface TokenSummary {
  today_input: number;
  today_output: number;
  today_total: number;
  month_input: number;
  month_output: number;
  month_total: number;
}

export interface PurposeBreakdown {
  purpose: string;
  calls: number;
  total_cost_usd: number;
  input_tokens: number;
  output_tokens: number;
}

export interface ModelBreakdown {
  model: string;
  calls: number;
  total_cost_usd: number;
  input_tokens: number;
  output_tokens: number;
}

export interface CallSummary {
  today_total: number;
  month_total: number;
  by_purpose: PurposeBreakdown[];
  by_model: ModelBreakdown[];
}

export interface BudgetFlags {
  ask_goldpan_enabled: boolean;
  ask_goldpan_daily_limit_usd: number;
  ask_goldpan_monthly_limit_usd: number;
  ag_spend_today_usd: number;
  ag_spend_month_usd: number;
  intake_ai_enabled: boolean;
  governance_ai_enabled: boolean;
}

export interface RecentError {
  log_id: string;
  created_at: string;
  status: string;
  model: string;
  purpose: string;
  error_message: string | null;
  latency_ms: number | null;
  session_id: string | null;
}

export interface ErrorSummary {
  budget_exceeded_today: number;
  budget_exceeded_month: number;
  errors_today: number;
  errors_month: number;
  recent: RecentError[];
}

// ── Restaurant Operations ─────────────────────────────────────────────────────

export interface RestaurantSummaryRow {
  restaurant_id: string;
  external_id: string;
  name: string;
  location: string | null;
  lifecycle_status: string;
  recanvass_status: string;
  last_canvassed: string | null;
  source_check_status: string;
  has_allergen_guide: boolean;
  dish_count: number;
  ingredient_count: number;
  transparency_coverage_pct: number;
  avg_transparency_score: number | null;
  calorie_coverage_pct: number;
  claims_count: number;
  unknown_filter_count: number;
}

export interface RestaurantListSummary {
  total: number;
  published: number;
  recanvass_needs_review: number;
  recanvass_overdue: number;
  recanvass_due_soon: number;
  recanvass_current: number;
  by_lifecycle: Record<string, number>;
}

export interface RestaurantListResponse {
  generated_at: string;
  summary: RestaurantListSummary;
  restaurants: RestaurantSummaryRow[];
}

export interface RestaurantInfo {
  restaurant_id: string;
  external_id: string;
  name: string;
  location: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  phone: string | null;
  official_website: string | null;
  menu_url: string | null;
  google_place_id: string | null;
  latitude: number | null;
  longitude: number | null;
  hours: string | null;
  menu_statement: string | null;
  lifecycle_status: string;
  recanvass_status: string;
  last_canvassed: string | null;
  recanvass_tier: number;
  source_check_status: string;
  last_source_check: string | null;
  has_allergen_guide: boolean;
  evidence_tier: string | null;
  published_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface MenuSourceRow {
  source_id: string;
  official_website: string | null;
  official_menu_url: string | null;
  online_ordering_url: string | null;
  allergen_nutrition_url: string | null;
  preferred_data_source: string | null;
  source_confidence: string | null;
  menu_status: string | null;
  recanvass_status: string;
  last_canvassed: string | null;
  last_verified_date: string | null;
  source_check_status: string;
}

export interface DishRow {
  dish_id: string;
  external_id: string;
  dish_name: string;
  menu_section: string | null;
  category: string | null;
  status: string;
  is_active: boolean;
  ingredient_count: number;
  has_transparency_score: boolean;
  transparency_score: number | null;
  has_calorie: boolean;
  calorie_value: string | null;
  tag_source: string | null;
  unknown_filter_count: number;
}

export interface ClaimRow {
  claim_id: string;
  claim_type: string | null;
  claim_text: string;
  source_type: string | null;
  created_at: string;
}

export interface RestaurantStats {
  dish_count: number;
  active_dish_count: number;
  ingredient_count: number;
  transparency_coverage_pct: number;
  avg_transparency_score: number | null;
  calorie_coverage_pct: number;
  claims_count: number;
  unknown_filter_count: number;
  menu_sources_count: number;
}

export interface PartnerLinkRow {
  partner_id:         string;
  external_id:        string;
  name:               string;
  contact_name:       string | null;
  status:             string;
  pipeline_stage:     string | null;
  priority:           string;
  relationship_owner: string | null;
  last_contact_date:  string | null;
  next_followup_date: string | null;
}

export interface FilterSummaryRow {
  filter_slug:          string;
  filter_name:          string;
  computed_count:       number;
  unknown_count:        number;
  not_applicable_count: number;
}

export interface RestaurantDetailResponse {
  generated_at:    string;
  restaurant:      RestaurantInfo;
  stats:           RestaurantStats;
  menu_sources:    MenuSourceRow[];
  dishes:          DishRow[];
  claims:          ClaimRow[];
  linked_partners: PartnerLinkRow[];
  filter_summary:  FilterSummaryRow[];
}

// ── Business Development ──────────────────────────────────────────────────────

export interface PartnerIntel {
  dish_count:                number;
  ingredient_count:          number;
  transparency_coverage_pct: number;
  avg_transparency_score:    number | null;
  calorie_coverage_pct:      number;
  claims_count:              number;
  unknown_filter_count:      number;
  lifecycle_status:          string;
  recanvass_status:          string;
  last_canvassed:            string | null;
}

export interface PartnerRow {
  partner_id:         string;
  external_id:        string;
  partner_type:       string;
  name:               string;
  contact_name:       string | null;
  contact_title:      string | null;
  status:             string;
  pipeline_stage:     string | null;
  priority:           string;
  opportunity_score:  number | null;
  relationship_owner: string | null;
  source:             string | null;
  deal_value:         string | null;
  email:              string | null;
  phone:              string | null;
  instagram:          string | null;
  website:            string | null;
  address:            string | null;
  city:               string | null;
  state:              string | null;
  latitude:           number | null;
  longitude:          number | null;
  geocode_source:     string | null;
  geocoded_at:        string | null;
  first_contact_date: string | null;
  last_contact_date:  string | null;
  next_followup_date: string | null;
  notes:              string | null;
  objections:         string | null;
  strategic_value:    string | null;
  audience_fit:       string | null;
  partnership_model:  string | null;
  restaurant_id:      string | null;
  created_at:         string;
  updated_at:         string;
  intel:              PartnerIntel | null;
}

export interface RestaurantLookupItem {
  restaurant_id:    string;
  external_id:      string;
  name:             string;
  location:         string | null;
  address:          string | null;
  city:             string | null;
  state:            string | null;
  official_website: string | null;
}

export interface PartnerListSummary {
  total:          number;
  active:         number;
  high_priority:  number;
  follow_ups_due: number;
  by_status:      Record<string, number>;
  by_type:        Record<string, number>;
}

export interface PartnerListResponse {
  generated_at: string;
  summary:      PartnerListSummary;
  partners:     PartnerRow[];
}

export interface ActionRow {
  action_id:    string;
  action_type:  string;
  content:      string | null;
  old_status:   string | null;
  new_status:   string | null;
  performed_by: string | null;
  performed_at: string;
}

export interface PartnerDetailResponse {
  generated_at: string;
  partner:      PartnerRow;
  actions:      ActionRow[];
}

// ── Intake OS ─────────────────────────────────────────────────────────────────

// packet_status mirrors the CHECK constraint on operations.intake_packets
// (supabase/migrations/016_intake_packet_state_machine.sql): six states, not
// four — "in_review" and "rejected" were missing here even though the API
// (api/routers/intake.py) and RPCs (017-019) have supported them since Task
// #43-45. claimed_by_user_id/claimed_at were likewise missing despite being
// present on IntakePacketRow/IntakePacketDetail in api/routers/intake.py.
export type IntakePacketStatus =
  | "pending_review"
  | "in_review"
  | "returned"
  | "approved"
  | "rejected"
  | "ingested";

export interface IntakePacketRow {
  packet_id:               string;
  restaurant_external_id:  string;
  restaurant_name:         string;
  restaurant_id:           string | null;
  packet_status:           IntakePacketStatus;
  canvass_date:            string;
  dish_count:              number;
  review_flag_count:       number;
  evidence_score_overall:  number | null;
  agent_version:           string | null;
  model_used:              string | null;
  reviewer_notes:          string | null;
  return_reason:           string | null;
  submitted_at:            string;
  reviewed_at:             string | null;
  reviewed_by:             string | null;
  ingested_at:             string | null;
  claimed_by_user_id:      string | null;
  claimed_at:              string | null;
}

export interface IntakeQueueSummary {
  total:          number;
  pending_review: number;
  returned:       number;
  approved:       number;
  ingested:       number;
}

export interface IntakeQueueResponse {
  generated_at: string;
  summary:      IntakeQueueSummary;
  packets:      IntakePacketRow[];
}

export interface ReviewFlag {
  type:              string;
  dish:              string;
  phrase:            string;
  reason:            string;
  suggested_action?: string;
}

export interface IntakePacketDetail {
  packet_id:               string;
  restaurant_external_id:  string;
  restaurant_name:         string;
  restaurant_id:           string | null;
  packet_status:           IntakePacketStatus;
  canvass_date:            string;
  source_urls:             string[];
  dish_count:              number;
  review_flag_count:       number;
  evidence_score_overall:  number | null;
  evidence_score_detail:   Record<string, number> | null;
  agent_version:           string | null;
  model_used:              string | null;
  processing_time_ms:      number | null;
  packet_data:             {
    restaurant:            Record<string, unknown>;
    dishes:                Record<string, unknown>[];
    review_flags:          ReviewFlag[];
    advisory_notes?:       string[];
    candidate_schema_report?: Record<string, unknown>;
    evidence_score:        Record<string, number>;
    agent_metadata:        Record<string, unknown>;
  };
  reviewer_notes:          string | null;
  return_reason:           string | null;
  submitted_at:            string;
  reviewed_at:             string | null;
  reviewed_by:             string | null;
  ingested_at:             string | null;
  claimed_by_user_id:      string | null;
  claimed_at:              string | null;
}

export interface IntakePacketDetailResponse {
  generated_at: string;
  packet:       IntakePacketDetail;
}

export interface LifecycleResult {
  external_id:      string;
  previous_status:  string;
  new_status:       string;
  recanvass_status: string | null;
  updated_at:       string;
}

// ── Public Map ────────────────────────────────────────────────────────────────

export interface RestaurantMapItem {
  external_id:      string;
  name:             string;
  address:          string | null;
  city:             string | null;
  state:            string | null;
  latitude:         number;
  longitude:        number;
  official_website: string | null;
  menu_url:         string | null;
}

// ── AI Usage ──────────────────────────────────────────────────────────────────

export interface AIUsageReport {
  generated_at: string;
  period_today: string;
  period_month: string;
  spend: SpendSummary;
  tokens: TokenSummary;
  calls: CallSummary;
  budget_flags: BudgetFlags;
  errors: ErrorSummary;
}
