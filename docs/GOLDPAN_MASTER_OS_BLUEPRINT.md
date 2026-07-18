# GoldPan™ Master OS Blueprint
**Version:** 1.1  
**Status:** Governing Architecture Document

## Purpose
This document defines the operational architecture of GoldPan™.
All new systems, APIs, dashboards, AI agents, workflows, and database changes should conform to this blueprint.
Lower-level documents (schema specifications, API specifications, module specifications, migration documents, UI designs, etc.) derive from this document.

**Supersedes:**
- `BACKEND_MASTER_OS_VISION.md`
- `GOLDPAN_OS_ARCHITECTURE.md` (as the governing document)

These documents remain valuable as implementation references but no longer define the overall architecture.

## Mission
GoldPan™ exists to create the world's most trusted food transparency platform.
Master OS exists to make GoldPan scalable by turning founder knowledge into operational infrastructure.
Every system exists to increase trust, preserve evidence, improve execution, and enable excellent people to make excellent decisions.

---

# 1. Core Principle

## One entity, many systems

GoldPan must avoid duplicate records.
One restaurant should have one canonical restaurant record.
Every system references that same restaurant record:

- Restaurant Operations OS
- Business Development OS
- Intake OS
- Knowledge OS
- Governance OS
- Analytics OS
- AI OS
- Customer OS
- Restaurant Portal

Supabase is the system of record.

---

# 2. System Map

## GoldPan Platform

- **Customer Product**
  - Discover/search
  - Ask GoldPan™
  - Saved profiles
  - Restaurant/dish pages
- **Restaurant Portal**
  - Restaurant submissions
  - Contact updates
  - Menu updates
  - Allergen/nutrition docs
  - Partnership interest
- **Health Partner Portal**
  - Dietitian/clinic partnerships
  - Referral flows
  - Sponsored guidance
  - Patient/client resources
- **GoldPan™ Master OS**
  - Executive OS
  - Restaurant OS
  - Business Development OS
  - Intake OS
  - Knowledge OS
  - Governance OS
  - Analytics OS
  - AI OS
  - Operations OS
  - Finance OS

---

# 2b. User Roles

| Role | Description |
|---|---|
| Founder / CEO | Full access. Strategic oversight. Daily brief consumer. Approves architecture and major decisions. |
| Executive | Reads all dashboards. No direct data mutations. |
| Business Development | Manages partners, pipeline, follow-ups, and partner actions. Cannot mutate evidence. |
| Restaurant Operations | Manages restaurant status, freshness, publication, and map. Can trigger recanvass. |
| Intake Specialist | Runs intake sessions, enters evidence, submits for review. Cannot publish directly. |
| Governance Reviewer | Reviews and approves intake packets, reviews rule outcomes, approves evidence updates. |
| Knowledge Curator | Manages dishes, ingredients, claims, scoring corrections. Evidence-layer edit access. |
| Marketing | Reads analytics, restaurant views, demand signals. No data mutation access. |
| Finance | Reads cost reports, AI spend, revenue, unit economics. No operational data mutation. |
| Support | Reads restaurant and partner records. Can log notes. Cannot mutate evidence. |
| Restaurant Representative | External. Submits updates via Restaurant Portal only. Submissions enter pending_review. |
| Health Partner | External. Accesses Health Partner Portal. No access to Master OS. |
| System Administrator | Full access. Manages users, roles, feature flags, migrations. |
| AI Agents | Service account access scoped per agent type. All actions logged. No production writes without approval. |

## Permission Philosophy

Every user receives the minimum permissions necessary.
No module may mutate another module's owned data unless explicitly authorized.
Production evidence requires review permissions.
Administrative actions are audited.
Service keys remain server-side.

---

# 3. Master OS Modules

## 3.1 Executive OS

### Purpose
Give leadership a bird's-eye view of company health.

### Owns
- executive_reports
- priorities
- risks
- KPIs
- daily_briefs

### Consumes
- Restaurant status
- BD pipeline
- AI spend
- Customer analytics
- Governance health
- Intake queue
- Revenue later

### Produces
- Founder Daily Brief
- Company Health Report
- Weekly priorities
- Strategic alerts

### Key screens
- `/admin`
- `/admin/executive`
- `/admin/daily-brief`

### Key questions
- What needs my attention today?
- Where are we blocked?
- What is growing?
- What is costing money?
- What needs follow-up?

---

## 3.2 Restaurant Operations OS

### Purpose
Manage restaurants as operational entities.

### Owns
- restaurant operational status
- freshness status
- publication status
- restaurant metadata
- map visibility

### Consumes
- evidence.restaurants
- evidence.dishes
- evidence.ingredients
- menu_sources
- transparency scores
- derived filters
- BD partner status

### Produces
- Restaurant health summary
- Recanvass queue
- Publication readiness
- Restaurant map state

### Key screens
- `/admin/restaurants`
- `/admin/restaurants/[id]`
- `/admin/restaurants/map`

### Restaurant Master Page
Should show:
- Basic restaurant info
- Location/address/map
- Menu sources
- Dishes
- Ingredient count
- Claims
- Transparency score coverage
- Calorie coverage
- Unknown filter count
- Freshness/recanvass status
- BD relationship status
- Intake status
- Governance status
- Recent actions
- Audit trail

### Actions
- Open Intake Record
- Start Intake
- Trigger Recanvass
- View Governance
- View BD relationship
- Publish/unpublish
- Request restaurant update

---

## 3.3 Business Development OS

### Purpose
Manage all external relationships and partnerships.
This is not restaurant-only. Restaurants are one partner type.

### Owns
- operations.partners
- operations.partner_actions
- pipeline status
- follow-ups
- notes
- objections
- opportunity scoring

### Partner types
- restaurant
- dietitian
- nutrition clinic
- gym
- corporate wellness
- employer
- healthcare partner
- university
- food brand
- investor/grant
- community organization
- media
- government
- other

### Consumes
- evidence.restaurants when partner_type = restaurant
- restaurant intelligence
- analytics demand later
- customer search trends later

### Produces
- Partnership pipeline
- Follow-up queue
- Contact history
- Opportunity reports
- Intake requests for restaurant partners

### Key screens
- `/admin/business-development`
- `/admin/business-development/[id]`
- `/admin/business-development/map`

### Rules
- Restaurant partners must reference `evidence.restaurants` when applicable.
- Non-restaurant partners do not require restaurant data.
- BD notes are relationship evidence, not menu evidence.
- BD cannot write directly to production food evidence.
- Restaurant-submitted or partner-submitted facts must go through review.

### Actions
- Create partner
- Edit partner
- Add note
- Update status
- Set follow-up
- Mark contacted
- Link restaurant
- Start Intake
- Create restaurant update submission

---

## 3.4 Intake OS

### Purpose
Turn restaurant/menu/source information into structured, reviewable evidence.

### Owns
- intake_packets
- review_flags
- verbatim_components
- candidate_schema_reports
- evidence acquisition status
- intake approvals

### Consumes
- restaurant source URLs
- menu documents
- restaurant submissions
- BD restaurant context
- existing restaurant records

### Produces
- structured intake packets
- ingredient evidence
- restaurant claims
- allergen disclosures
- calorie content
- review flags
- candidate schema ideas

### Key screens
- `/admin/intake`
- `/admin/intake/queue`
- `/admin/intake/[packet_id]`

### Rules
- Intake records evidence.
- Intake does not make Governance conclusions.
- AI output defaults to pending_review.
- Humans approve before evidence becomes production data.
- Inference is never evidence.

### Actions
- Create intake run
- Upload/enter source
- Review packet
- Return packet
- Approve packet
- Send to Governance
- Create restaurant follow-up request

---

## 3.5 Knowledge OS

### Purpose
Manage GoldPan's structured food knowledge.

### Owns
- ingredients
- dishes
- restaurant claims
- allergen flags
- allergen disclosures
- calorie content
- transparency scores
- nutrition estimates later

### Consumes
- approved Intake evidence
- restaurant submissions after approval
- scoring architecture
- nutrition databases later

### Produces
- evidence summaries
- transparency coverage
- ingredient coverage
- scoring audit reports
- nutrition/calorie estimates later

### Key screens
- `/admin/knowledge`
- `/admin/knowledge/dishes`
- `/admin/knowledge/ingredients`
- `/admin/knowledge/scoring`
- `/admin/knowledge/calories`

### Rules
- Restaurant-stated calories and GoldPan-estimated calories must remain separate.
- Restaurant-stated allergen disclosures and GoldPan allergen flags must remain separate.
- Legacy scoring debt must be tracked and resolved before full Supabase pipeline mode.

---

## 3.6 Governance OS

### Purpose
Apply deterministic rules to evidence and produce conclusions.

### Owns
- rules registry
- derived filters
- rule outcomes
- confidence levels
- unknown conclusions
- governance audit trail
- rule versions

### Consumes
- approved evidence
- allergen flags
- allergen disclosures
- verbatim components
- scoring rules

### Produces
- filter conclusions
- unknown reasons
- rule conflicts
- readiness status
- public-facing eligibility

### Key screens
- `/admin/governance`
- `/admin/governance/rules`
- `/admin/governance/unknowns`
- `/admin/governance/audit`

### Rules
- Governance reads evidence.
- Governance does not rewrite Intake evidence.
- Unknown is valid when evidence is incomplete.
- GoldPan advisories are generated dynamically, not stored as Intake facts.

### Actions
- Run Governance
- View rule outcome
- Inspect unknowns
- Queue restaurant follow-up
- Review rule conflict
- Approve rule update

---

## 3.7 Analytics OS

### Purpose
Understand customer demand, search behavior, restaurant interest, and market opportunity.

### Owns
- analytics.page_views
- analytics.events
- analytics.restaurant_profile_views
- analytics.search_terms
- analytics.ask_goldpan_sessions

### Consumes
- frontend events
- Ask GoldPan usage
- restaurant views
- search activity
- referral sources
- partner campaigns later

### Produces
- Customer Demand Report
- Restaurant demand signals
- Market opportunity maps
- Most searched restrictions
- Most viewed restaurants
- Conversion insights

### Key screens
- `/admin/analytics`
- `/admin/analytics/search`
- `/admin/analytics/restaurants`
- `/admin/analytics/markets`

### Rules
- Prefer direct event logging from GoldPan frontend.
- GA4 can be secondary.
- Analytics should feed BD prioritization.
- Analytics should not alter evidence.

---

## 3.8 AI OS

### Purpose
Control AI usage, spending, agents, prompts, and feature availability.

### Owns
- operations.ai_usage_logs
- budget_controls
- feature_flags
- prompt versions
- AI run logs
- agent definitions

### Consumes
- AI calls from Intake
- Ask GoldPan calls
- BD assistant calls
- Governance assistant calls
- analytics explanation calls

### Produces
- AI Cost Report
- Budget alerts
- Feature shutdown states
- Agent usage summaries
- Cost per restaurant/intake/user

### Key screens
- `/admin/ai-usage`
- `/admin/ai-agents`
- `/admin/prompts`
- `/admin/budget-controls`

### Rules
- AI is used only where reasoning is valuable.
- Deterministic code handles validation, counting, comparisons, and reporting.
- All AI calls must be logged.
- Service role keys stay server-side.
- Ask GoldPan can be feature-flagged.

### Budget modes
- off
- beta capacity only
- scheduled windows
- always on

---

## 3.9 Operations OS

### Purpose
Monitor technical and operational health.

### Owns
- system health
- pipeline runs
- migration history
- job logs
- validation reports
- error logs

### Consumes
- FastAPI health
- Supabase status
- pipeline runs
- frontend errors
- AI errors
- migration records

### Produces
- System Health Report
- Pipeline status
- Error alerts
- Deployment readiness

### Key screens
- `/admin/operations`
- `/admin/system-health`
- `/admin/pipeline`
- `/admin/migrations`

---

## 3.10 Finance OS

### Purpose
Track business costs, revenue, grants, subscriptions, and unit economics.

### Owns
- expenses
- revenue records
- grant opportunities
- subscriptions
- cost allocation
- financial reports

### Consumes
- AI costs
- infrastructure costs
- partner revenue
- customer revenue
- sponsorship revenue later

### Produces
- runway report
- monthly cost report
- revenue report
- unit economics report

### Key screens
- `/admin/finance`
- `/admin/revenue`
- `/admin/costs`
- `/admin/grants`

---

## 3.11 Notification OS *(Reserved — not current build priority)*

### Purpose
Coordinate alerts and notifications across all Master OS modules. Single delivery layer so no module needs to implement its own alerting logic.

### Examples
- Partner follow-up overdue
- Restaurant recanvass due
- AI budget exceeded
- Governance conflict detected
- Restaurant submission received
- Analytics spike detected
- System failure / pipeline error

### Design notes
- All modules write to a notifications queue; Notification OS handles delivery.
- Supports in-app alerts, email digest, and future push/Slack delivery.
- Users configure notification preferences per role and per event type.

---

# 4. Data Ownership Rules

## Core ownership principle

Each table has one owning OS.
Other systems may read it, but only the owning OS should mutate it directly.

## Examples

**evidence.restaurants**
Owner: Restaurant Operations OS  
Readable by: BD, Intake, Analytics, Governance, Executive

**operations.partners**
Owner: Business Development OS  
Readable by: Restaurant OS, Executive, Analytics

**intake_packets**
Owner: Intake OS  
Readable by: Restaurant OS, Governance, Executive

**derived_filters**
Owner: Governance OS  
Readable by: Customer Platform, Restaurant OS, Analytics

**ai_usage_logs**
Owner: AI OS  
Readable by: Executive, Finance, Operations

---

# 5. Evidence Boundary

GoldPan must preserve the boundary between:
- Relationship data
- Submitted data
- Intake evidence
- Governance conclusions
- Published customer-facing output

## Relationship data
Examples: meeting notes, objections, restaurant interest, follow-up comments  
Owner: Business Development OS  
Not evidence.

## Submitted data
Examples: restaurant sends updated menu, restaurant submits allergen guide, restaurant edits contact information, partner sends correction  
Owner: Submission Review / Intake OS  
Candidate evidence only.

## Intake evidence
Examples: ingredient records, allergen flags, restaurant claims, calorie content, allergen disclosures  
Owner: Intake / Knowledge OS  
Review required.

## Governance conclusions
Examples: vegan compatible, no milk identified, unknown due to sauce, advisory generated  
Owner: Governance OS  
Derived from evidence.

## Published output
Examples: customer-facing restaurant/dish results, Ask GoldPan answers, public filter tags  
Owner: Customer Product  
Must be based on approved evidence + Governance.

---

# 5b. State Machine Philosophy

Every major entity moves through explicit, defined states. Implicit or undocumented transitions are not permitted.

| Entity | States |
|---|---|
| Restaurant | prospect → qualified → onboarding → evidence_acquisition → verification → qa_review → published → recanvassing → suspended → deactivated |
| Partner | prospect → outreach → engaged → negotiating → active → paused → declined → churned |
| Intake Packet | pending_review → in_review; in_review → returned \| approved \| rejected; returned → pending_review; approved → ingested *(canonical model per DEC000001, approved 2026-07-13 — not a single linear sequence; see the branching transitions above and §5i below for full detail — `superseded_by_packet_id` and `archived_at` are non-status attributes, not lifecycle states; see `docs/decisions/DEC000001_CANONICAL_INTAKE_PACKET_STATE_MACHINE.md`)* |
| Restaurant Update Submission | pending_review → in_review; in_review → returned \| approved \| rejected; returned → pending_review (via a new child row, not in place) *(canonical model per DEC000002, approved 2026-07-18 — five review statuses only, no `converted` status; disposition/routing is a separate model layered on top of `approved`, not a further review-status transition; see §5i below for full detail — `superseded_by_submission_id`, `archived_at`, and the disposition fields are non-status attributes, not lifecycle states; see `docs/decisions/DEC000002_submission_state_machine.md`)* |
| AI Job | queued → running → completed → failed → cancelled |
| Governance Run | queued → running → completed → failed → partial |

State transitions must be logged with actor, timestamp, previous state, and new state.

---

# 5c. ID Strategy

Every major entity is assigned a human-readable external ID at creation. Internal UUIDs remain the database primary key.

| Entity | Prefix / Format | Example |
|---|---|---|
| Restaurant | R000001 | R000001 |
| Partner | BD000001 | BD000001 |
| Intake Packet | PKT000001 | PKT000001 |
| Submission | SUB000001 | SUB000001 |
| Evidence Item | EVD000001 | EVD000001 |
| AI Run | AIRUN000001 | AIRUN000001 |
| Governance Run | GOVRUN000001 | GOVRUN000001 |

Rules:
- External IDs are assigned at row creation by database trigger or sequence.
- External IDs are stable — they never change after assignment.
- External IDs are used in all URLs, logs, and cross-references.
- Internal UUIDs are never exposed in URLs.

---

# 5d. Location Data Standard

Location data in GoldPan serves three purposes: geographic search and discovery, map rendering, and BD territory intelligence. Unstructured free-form location strings cannot reliably serve any of these. This standard defines required location fields, their sources of truth, and the rules governing their capture and use.

## Required fields (evidence.restaurants)

| Field | Type | Required | Source |
|---|---|---|---|
| `address` | text | Required when available | Official source — website, ordering platform, Google Business linked from official source |
| `city` | text | Required | Official source or parsed from structured location |
| `state` | text | Required | Official source or parsed from structured location |
| `postal_code` | text | When available | Official source |
| `country` | text | Default `"US"` | Assumed US unless stated otherwise |
| `location` | text | Display only | Free-form human label (e.g. "Hoover", "Southside") |

## Required fields (operations.partners)

Partners share the same location fields. Additionally:

| Field | Type | Required | Source |
|---|---|---|---|
| `latitude` | numeric | After geocoding | Auto-geocoded from address or city+state |
| `longitude` | numeric | After geocoding | Auto-geocoded from address or city+state |
| `geocode_source` | text | Set automatically | e.g. `"nominatim"`, `"manual"` |
| `geocoded_at` | timestamp | Set automatically | Time of last geocode run |

## Rules

1. **Free-form `location` is display metadata, not a source of truth.** It may be shown in UI labels (e.g. "Clean Eatz (Hoover)") but must never be used for geo-matching, filtering, or map placement.

2. **Intake approval must flag missing address, city, and state.** Any intake packet submitted without `city` or `state` must generate a Review Flag and may not be marked `approved` until either the fields are populated or a documented exception is recorded.

3. **BD partner creation requires city and state at minimum.** A partner record without city+state is ineligible for map placement and should be flagged in the "Needs Location" queue on the BD map.

4. **Map eligibility requires lat/lng.** A partner without geocoordinates will not appear on the BD map. Geocoding runs automatically from address or city+state on create/update. If geocoding fails, the partner enters the Needs Location queue.

5. **Existing restaurants with only free-form location are marked Location Backfill Required.** The `location_quality` field (when added) distinguishes `structured`, `location_only`, `geocoded`, and `unknown`. Until then, null `city`/`state` is the signal.

6. **Country defaults to "US".** GoldPan currently operates in the United States. International records must explicitly set `country`.

7. **Address is not inferred from delivery platforms.** If the restaurant's address is not found on an approved official source, leave `address` blank and add a Review Flag. Delivery platform listings (DoorDash, Uber Eats, etc.) are not approved address sources unless explicitly provided as a canvassing source URL.

## Location quality states

Address completeness is tracked with four named states. These are computed at display time from the presence/absence of structured fields.

| State | Condition | UI label |
|---|---|---|
| `complete_address` | `address` is not null | "Complete address" |
| `city_state_only` | `address` null, `city`/`state` present | "City/state only — needs street address backfill" |
| `missing_location` | `address`, `city`, `state` all null | "Missing location data" |
| `needs_manual_address_backfill` | `city`/`state` resolved but automated enrichment cannot determine street address | Subset of `city_state_only` — set after Identity Enrichment stage runs and fails to resolve |

**Rule: GoldPan never invents a street address from city-level data.** Addresses must come from an approved trusted source. See Section 5g Identity Enrichment for the resolution path.

## Backfill status

All pre-migration restaurants (imported via `migrate_sheets_to_supabase.py`) are in `city_state_only` state after running the location backfill script. The resolution path is:

1. Run `scripts/location_backfill.py --commit` to parse `city`/`state` from `location` — already completed for initial dataset.
2. Identity Enrichment Stage (Section 5g) attempts to resolve street address from official website, Google Place ID, or restaurant submission.
3. Fields that cannot be auto-resolved enter the Identity Review Queue for manual verified backfill.
4. During each recanvass, Intake must capture `address` per Intake Standard.
5. On each partner record create/edit, geocoding auto-runs from address or city+state to produce lat/lng.

See `docs/LOCATION_BACKFILL_REPORT.md` for full gap analysis.

---

# 5e. Restaurant Identity Standard

## Principle

Restaurant identity is foundational data owned by Restaurant Operations OS and Intake OS. It is not Business Development data. BD owns the relationship with a restaurant — not the restaurant's facts.

A restaurant may have an `evidence.restaurants` record long before BD ever touches it, and that record may be updated independently by Intake, recanvassing, or restaurant submissions. BD must never duplicate or diverge from that canonical record.

## Canonical Identity Record

`evidence.restaurants` is the single source of truth for all restaurant identity facts. No other table may store a competing copy of these fields.

| Field | Type | Owner | Notes |
|---|---|---|---|
| `restaurant_id` | uuid | System | Internal primary key |
| `external_id` | text | System | Human-readable ID (R000001 format) |
| `name` | text | Restaurant OS / Intake | Display name |
| `legal_name` | text | Restaurant OS / Intake | Legal entity name when different from display name |
| `brand` | text | Restaurant OS / Intake | Parent brand or chain if applicable |
| `street_address` | text | Intake | Full street address from official source |
| `city` | text | Intake | Structured city field — **required** |
| `state` | text | Intake | Two-letter state code — **required** |
| `postal_code` | text | Intake | ZIP code when available |
| `country` | text | Intake | Default `"US"` |
| `latitude` | numeric | System / Geocoder | Auto-geocoded from address or city+state |
| `longitude` | numeric | System / Geocoder | Auto-geocoded from address or city+state |
| `timezone` | text | System | e.g. `"America/Chicago"` — derived from geocoordinates |
| `market` | text | Restaurant OS | Geographic market label (e.g. `"Birmingham"`) |
| `website` | text | Intake | Official restaurant website URL |
| `menu_url` | text | Intake | Primary public menu URL |
| `ordering_url` | text | Intake | Online ordering platform URL |
| `phone` | text | Intake | Restaurant phone number from official source |
| `general_email` | text | Intake | Public contact email when available |
| `instagram` | text | Intake | Instagram handle (e.g. `@handle`) |
| `google_maps_url` | text | Intake | Google Maps listing URL |
| `google_place_id` | text | Intake | Google Place ID when available |
| `hours` | text | Intake | Operating hours verbatim from official source |
| `last_verified_at` | timestamp | Intake / Recanvass | Timestamp of last canvassing or source check |
| `location_quality_status` | text | System | `geocoded` / `structured` / `location_only` / `unknown` |

## Ownership Boundary

**Restaurant Operations OS and Intake OS own all fields above.** No other OS may write to these fields directly. Mutations flow through:
- Intake packets (canvassing)
- Recanvassing runs
- Restaurant update submissions (reviewed by Intake)
- Manual corrections by an authorized reviewer

**Business Development OS is read-only on `evidence.restaurants`.** BD may read any restaurant identity field to display or prefill, but may not write to it.

## BD Owns Relationship Fields Only

The following fields live on `operations.partners` and belong exclusively to BD:

- Pipeline status, stage, and priority
- Opportunity score
- Relationship owner
- Contact person name and title (may differ from the restaurant's public phone/email)
- BD-specific contact email and phone (the relationship contact, not the restaurant's general contact)
- Meeting notes, objections, and follow-up dates
- Deal value and partnership model
- Source (how BD discovered this restaurant)
- Strategic value and audience fit assessments

## BD Form Behavior

When `partner_type = restaurant`, the BD form must follow this workflow:

1. **Search first.** The user selects an existing `evidence.restaurants` record via the restaurant lookup dropdown. This is the primary path.
2. **Prefill read-only.** On selection, restaurant identity fields (name, address, city, state, website, etc.) prefill as read-only display values sourced from `evidence.restaurants`. BD user cannot edit them here.
3. **BD-only fields are editable.** The user fills in relationship-specific fields only: status, contact person, notes, deal value, etc.
4. **If the restaurant does not exist**, the form offers a "Start Restaurant Intake" path instead of free-form entry. This creates a proper `evidence.restaurants` record through Intake rather than producing a duplicate BD-only record.

**The BD form must never be used to create or correct restaurant identity data.** If a restaurant's address, website, or name is wrong in the BD view, the correction must go through Intake or the restaurant update submission workflow — not a BD edit.

## Why This Matters

Without this standard:
- Restaurant facts get entered twice (once in BD, once by Intake) with drift over time
- BD records become an unofficial shadow registry that diverges from canvassed data
- Map geocoding and restaurant intelligence depend on `evidence.restaurants` — a BD-only record is invisible to those systems
- When GoldPan scales to hundreds of restaurants, duplicate records create reconciliation debt

With this standard, BD is focused on what it uniquely owns — the relationship — and restaurant facts remain a single authoritative record that every OS reads from.

## Implementation Phases

| Phase | Work |
|---|---|
| Current (Phase 3) | Restaurant lookup dropdown prefills writable fields via auto-fill. Location fallback via `_parse_location()`. |
| Phase 4 | Prefilled fields become read-only display in BD form when restaurant is linked. "Start Intake" CTA for unlinked restaurants. |
| Phase 5+ | Restaurant identity fields in `evidence.restaurants` expanded to full standard above. Intake packets required to populate all fields before approval. |

---

# 5f. Cross-System Architectural Standards

These principles govern how all OS modules are designed, connected, and observed. They are architectural guidelines to be implemented progressively — not immediate feature requirements. Every new screen, component, and data model should be designed with these standards in mind.

---

## 1. Cross-Link Framework

Every major entity page must link to its related operational systems. No page should be a dead end.

**Restaurant** → Business Development · Intake · Knowledge · Governance · Analytics · Customer View  
**Partner** → Restaurant · Actions · Intake · Timeline  
**Intake Packet** → Restaurant · Knowledge · Governance · BD  
**Dish** → Restaurant · Ingredients · Governance · Knowledge  

Implementation: each entity detail page includes a "Related Systems" section with direct navigation to where that entity lives in other OSes.

---

## 2. Universal Activity Feed

Every OS emits structured activity events. Events accumulate into per-entity timelines and eventually into a company-wide activity stream.

**Event examples:**
- Restaurant added / published / recanvass started
- Partner created / meeting logged / status changed
- Intake started / packet approved / returned for review
- Governance run completed / conflict detected
- AI budget warning / budget exceeded
- Analytics spike detected

**Design rule:** Events are emitted by the owning OS and consumed by the activity feed. No OS duplicates event storage — events are assembled from activity logs, not re-entered.

---

## 3. Universal Status Cards

Every OS module exposes a consistent operational status card. Status cards form the backbone of the Executive OS dashboard and health monitoring.

**Standard status values:** Active · Needs Review · Waiting · Blocked · Completed · Stale · Unknown

**Card anatomy:**
- Module name
- Current status
- Count of items in each status
- Last updated timestamp
- Link to module queue

---

## 4. Global Search

Reserve architecture for a Master Search layer that spans every OS.

**Searchable entity types:**
- Restaurants (name, location, market)
- Partners (name, contact, type)
- Dishes (name, category, restaurant)
- Ingredients (name, allergen flags)
- Intake Packets (restaurant, status, date)
- Governance Rules (rule ID, description)
- Documentation (docs/ directory)

**Design rule:** Each OS is responsible for keeping its entities indexable. Global Search assembles results from OS-level indexes rather than scanning raw tables.

---

## 5. Notification Center

All OS modules write to a central notification queue. The Notification OS handles delivery. No module implements its own alerting logic.

**Notification types:**
- Overdue follow-up (BD OS)
- Restaurant recanvass due (Restaurant OS)
- Submission awaiting review (Intake OS)
- Governance conflict detected (Governance OS)
- AI budget exceeded (AI OS)
- Pipeline failure (Operations OS)
- Analytics spike detected (Analytics OS)

**Delivery targets:** in-app alert badge · email digest · future push/Slack  
**User control:** notification preferences are per-role and per-event-type.

---

## 6. Employee Dashboard

Each employee sees a role-filtered view of their own queue rather than the full Master OS.

**Standard dashboard sections:**
- My Tasks — assigned intake, review, BD follow-up items
- My Queue — packets, submissions, or approvals awaiting action
- My Activity — recent actions I've taken across all OSes
- My Follow-ups — BD follow-up dates I own
- My KPIs — metrics relevant to my role

**Design rule:** The Employee Dashboard is assembled from Master OS data — it does not duplicate storage. It is a filtered view, not a separate system.

---

## 7. Health Meter

Every OS exposes an operational health score. Health scores aggregate into the Executive OS overview.

**Health score anatomy:**
- Percentage (0–100%)
- Open issues list (human-readable, actionable)
- Trend (improving / stable / declining)
- Last computed timestamp

**Example:**
```
Business Development    91%
  - 2 overdue follow-ups
  - 1 stalled opportunity (90+ days no activity)

Restaurant Operations   84%
  - 3 stale restaurants (recanvass overdue)
  - 2 unpublished (governance pending)
  - 1 missing coordinates

Governance              100%  No conflicts.
```

**Design rule:** Health scores are computed, not manually entered. Each OS defines its own health formula. The Executive OS aggregates them.

---

## 8. Explainability

Every warning, blocked status, or unknown result must explain itself in plain language. Users must never have to guess why something is blocked.

**Explainability anatomy:**
- Status label (e.g. "Unpublished")
- Reason (e.g. "Governance Unknown")
- Cause (e.g. "Missing sauce ingredients on Spicy Bowl")
- Action (e.g. "Open Intake Packet → PKT000042")

**Design rule:** Explanations link directly to the entity or action that resolves the issue. A blocked status with no explanation is a design failure.

---

## 9. Entity Timeline Standard

Every major entity maintains a chronological timeline assembled from activity logs. Timelines are read from activity events — they are never entered separately.

**Restaurant Timeline events:**
Restaurant created · BD relationship started · First meeting held · Menu uploaded · Intake packet created · Intake approved · Governance run · Published · Recanvass initiated · Restaurant updated

**Partner Timeline events:**
Partner created · First contact · Meeting logged · Proposal sent · Negotiation started · Agreement reached · Follow-up set · Status changed · Churned

**Design rule:** Timeline data is assembled from the activity log. Storing timeline entries separately from the events that created them is a duplication violation.

---

## 10. Organizational Memory Principle

Master OS exists to preserve organizational knowledge, not merely store data. Every system must be able to answer:

- **What happened?** — via activity logs and timelines
- **Why did it happen?** — via explainability annotations and audit trails
- **Who changed it?** — via actor + timestamp on every state transition
- **What happens next?** — via queues, follow-ups, and health alerts

**Design rule:** Any state change without an actor, timestamp, and reason is an incomplete record. Incomplete records accumulate into organizational debt. The test of any OS screen is: could a new employee understand what happened here, why, and what to do next — without asking anyone?

---

# 5g. Identity Enrichment Pipeline

## Purpose

Restaurant Identity is not complete at creation. After a restaurant record enters `evidence.restaurants` — by any path — it goes through the Identity Enrichment Pipeline before it is considered a fully resolved identity.

The pipeline is **entry-point-agnostic**. It does not belong to Intake, BD, the Restaurant Portal, or any other OS. It fires whenever a restaurant record is created or materially updated, regardless of how that record entered GoldPan. Every entry point writes to `evidence.restaurants`; the enrichment pipeline runs from there.

The principle: **automated enrichment handles what it can; only what it cannot resolve enters the Identity Review Queue.**

## Trigger events

The Identity Enrichment Pipeline fires on:

| Event | Trigger |
|---|---|
| Restaurant record created | Any entry point — BD, Intake, Restaurant Portal, bulk import, API |
| `name` changed | Re-run Places lookup to confirm match |
| `street_address` updated | Re-geocode; re-run Places lookup |
| `website` updated | Re-verify URL; re-fetch structured data |
| `google_place_id` added | Full Places data pull |
| Manual enrichment requested | Staff or queue action |
| Scheduled re-verification | Freshness threshold exceeded |

Entry points do not implement their own enrichment logic. BD, Intake, Portal, and APIs write identity data to `evidence.restaurants`; the pipeline picks it up from there.

## Scope

The Identity Enrichment Pipeline is responsible only for improving the completeness and confidence of the canonical Restaurant Identity record.

**It does not:**
- Extract menu evidence (that is Intake's job)
- Perform governance or scoring
- Update relationship data (that belongs to BD / `operations.partners`)
- Trigger recanvass workflows

## Fields targeted for enrichment

| Field | Trusted sources |
|---|---|
| `street_address` | Official website, Google Places API, restaurant submission, verified manual |
| `city` | Parsed from `location`, confirmed by address or Places |
| `state` | Parsed from `location`, confirmed by address or Places |
| `postal_code` | Official website, Google Places, USPS |
| `country` | Default `"US"` unless stated otherwise |
| `latitude` | Geocoded from full address (preferred) or city+state (lower confidence) |
| `longitude` | Same as latitude |
| `google_place_id` | Google Places text search on name + city/state |
| `website` | Google Places, BD notes, search |
| `phone` | Official website, Google Places |
| `hours` | Official website, restaurant submission |

## Per-field provenance tracking

Each enrichable field should eventually track:

| Sub-field | Description |
|---|---|
| `value` | The resolved value |
| `source` | Where the value came from (e.g. `"google_places"`, `"official_website"`, `"restaurant_submission"`, `"manual_verified"`) |
| `confidence` | `verified` / `declared` / `inferred` / `likely` |
| `last_verified_at` | Timestamp of last confirmation against a trusted source |

Until a dedicated enrichment tracking table is built, these are tracked informally via recanvass notes and the `location_quality_status` field.

## Enrichment sources, in priority order

1. **Restaurant submission** — highest confidence; the restaurant provided it directly
2. **Official website** — fetched from the restaurant's own site by the enrichment pipeline
3. **Google Places API** — structured external source; treat as `declared`, not `verified`
4. **BD canvassing notes** — team-entered during outreach; `inferred` confidence
5. **Manual verified backfill** — human-researched and confirmed; `verified` if documented

**Never use:** delivery platforms (DoorDash, Uber Eats, etc.), Yelp, or third-party aggregators as authoritative address or identity sources.

## Identity Review Queue

Fields that cannot be resolved automatically enter the Identity Review Queue. This queue surfaces restaurants with outstanding enrichment gaps, prioritized by:

- **Publication blockers first** — restaurants at `qa_review` or `verification` stage with missing required fields
- **Recanvass candidates second** — restaurants due for recanvass that also have enrichment gaps
- **All others** — sorted by lifecycle stage and last canvassed date

The Identity Review Queue is part of Restaurant OS. It is **not** a manual data entry queue by default — it is a human review step for cases where automated enrichment has already run and failed or is insufficient.

## What this is NOT

- **Not the Intake Agent.** The Intake Agent extracts menu evidence from source URLs. The Identity Enrichment Pipeline enriches the canonical identity record using external APIs and structured data sources. These are separate systems with separate triggers.
- **Not per-entry-point.** BD, Intake, Portal, and future APIs do not each implement their own enrichment logic. They write to `evidence.restaurants` and the pipeline runs.
- **Not address inference.** City-level geocoding does not produce a street address. A restaurant in "Hoover, AL" does not have its address set to "Hoover, AL." The city and state fields are set; the address field remains null until a trusted source provides it.
- **Not a delivery platform import.** Third-party platform addresses are not approved sources.
- **Not a substitute for Intake.** Full menu evidence still requires Intake. Identity Enrichment handles identity fields only.

## Build phase

The Identity Enrichment Pipeline is planned for a future phase after Phase 5 (Intake OS UI). It depends on:
- Standalone enrichment service (not embedded in any entry point)
- Google Places API integration
- `identity_enrichment_runs` table for run history and field-level provenance
- Identity Review Queue UI in Restaurant OS
- Trigger mechanism: database webhook or post-write hook on `evidence.restaurants`

---

# 5h. Restaurant Identity Update System

## Purpose

Restaurant identity fields are living data. A restaurant's website, menu URL, ordering URL, phone number, hours, address, and social links change over time. The Identity Enrichment Stage (5g) handles initial population of blank fields. The Identity Update System governs how existing values are updated, challenged, and reconciled over the lifetime of a restaurant record.

The principle: **no identity field should be silently overwritten. Every change should have a source, a confidence level, and an actor.**

## Owned by

Restaurant Operations OS

## Fields governed

| Field | Change type | Notes |
|---|---|---|
| `website` | Frequent | Restaurants relaunch or change platforms |
| `menu_url` | Frequent | Menu platforms change seasonally |
| `ordering_url` | Occasional | Ordering platform switches |
| `allergen_nutrition_url` | Occasional | Often unpublished until regulatory pressure |
| `phone` | Infrequent | Changes on relocation or ownership change |
| `general_email` | Infrequent | Becomes stale; rarely maintained |
| `street_address` | Rare | Changes on relocation |
| `city` / `state` / `postal_code` | Rare | Changes on relocation |
| `hours` | Frequent | Seasonal and holiday changes common |
| `instagram` / social links | Occasional | Rebrand or new account |
| `google_place_id` | Very rare | Changes on ownership transfer or record merge |
| `latitude` / `longitude` | Rare | Re-geocoded if address changes |

## Update sources and trust levels

| Source | Trust | Write path |
|---|---|---|
| Restaurant-submitted change | High | Lands in Identity Review Queue as `pending_review` before applying |
| Intake / recanvass finding | High | Applied directly after human review of intake packet |
| Staff manual correction | Medium–High | Applied directly if user has `restaurant_identity_edit` permission |
| Automated enrichment (Places API, scraper) | Medium | Creates a **candidate update** — does not overwrite canonical value until reviewed |
| BD canvassing note | Low | Flagged for Intake review; not applied directly |

**Automated enrichment never becomes canonical truth on its own.** It creates a candidate, records its source and confidence, and waits for human confirmation or auto-promotion after a validation threshold.

## Per-field provenance tracking

Every updated identity field should track the following metadata. Until a dedicated tracking table is built, this is tracked via Intake review flags and recanvass notes.

| Sub-field | Description |
|---|---|
| `source` | Where the new value came from (e.g. `"restaurant_submission"`, `"recanvass"`, `"google_places"`, `"manual_staff"`) |
| `confidence` | `verified` / `declared` / `inferred` / `candidate` |
| `last_verified_at` | Timestamp of last confirmation against a trusted source |
| `updated_by` | User ID or system agent that applied the change |
| `previous_value` | The value before this update (stored in audit record) |

## Audit record requirement

Important identity changes must create an audit record. A change is "important" if it affects a field that is:
- Published and visible to users (website, hours, ordering_url, menu_url)
- Used for geocoding or mapping (address, city, state, postal_code, lat/lng)
- A publication blocker (required for a restaurant to reach `published` lifecycle status)

Audit records are append-only. No audit record may be deleted.

## Update workflow rules

1. **Restaurant-submitted changes land in pending review.** No restaurant-submitted value writes directly to `evidence.restaurants`. The submission enters the Identity Review Queue with status `pending_restaurant_submission`.

2. **Staff updates with permission apply directly.** A user with `restaurant_identity_edit` permission may update any identity field directly. The change is written immediately and creates an audit record.

3. **Automated enrichment creates candidates, not truth.** A script or enrichment service writes to a candidate field or staging record. The candidate is promoted to canonical only after explicit human confirmation or after the system confirms it matches at least two independent trusted sources.

4. **Recanvass findings apply through Intake.** A recanvass that discovers a changed website or hours updates the evidence through the normal Intake packet approval flow — not through a direct field update.

5. **Conflicting sources are surfaced, not silently resolved.** If two sources disagree on a field (e.g., the official website says one phone number, Google Places says another), the conflict is recorded and enters the Identity Review Queue rather than auto-resolving to the more recent value.

## Identity Review Queue

The Identity Review Queue is a persistent queue in Restaurant Operations OS. It surfaces all restaurants with outstanding identity issues, regardless of how those issues arose.

**Queue item types:**

| Type | Trigger |
|---|---|
| `pending_restaurant_submission` | Restaurant submitted an identity change |
| `missing_address` | `street_address` is null after initial enrichment pass |
| `changed_website` | Recanvass or enrichment detected a new or broken URL |
| `changed_menu_url` | Menu URL returns 404 or differs from last verified value |
| `outdated_hours` | `last_verified_at` for hours exceeds freshness threshold |
| `failed_geocode` | Geocoding attempt for address returned no result |
| `conflicting_source` | Two sources disagree on the same field |
| `candidate_ready` | Automated enrichment has a high-confidence candidate waiting for promotion |
| `pending_staff_review` | BD or staff flagged a suspected identity change |

**Queue behavior:**
- Items are prioritized: publication blockers first, recanvass-linked items second, all others by age
- Resolving an item requires a confirmed action: accept, reject, or defer
- Deferred items resurface after a configurable interval

## What this is NOT

- **Not a duplicate of the Identity Enrichment Stage.** Enrichment (5g) fills blank fields at creation. The Update System governs field-level changes over time.
- **Not a general-purpose edit form.** Staff cannot edit arbitrary identity fields through a free-form UI without permission and audit logging.
- **Not a BD-owned workflow.** BD may surface a suspected identity change (e.g., "their website seems to have changed"), but the resolution lives in Restaurant OS and Intake — not in BD.

## Build phase

This system is planned for a future phase after Phase 5 (Intake OS UI). It depends on:
- `identity_update_candidates` table (or equivalent staging on `evidence.restaurants`)
- `identity_audit_log` table (append-only; stores previous values, source, actor, timestamp)
- Identity Review Queue UI in Restaurant OS admin
- Permission model for `restaurant_identity_edit`
- Conflict detection logic in enrichment and recanvass pipelines

---

# 5i. Data Lifecycle Standard

## Purpose

Every major GoldPan entity follows a defined lifecycle from creation through retirement. The lifecycle defines ownership, mutation rights, trust level, and operational responsibility at every stage. This standard exists to protect long-term architectural consistency as Master OS grows — ensuring every future feature and every new entry point makes the same assumptions about what it means for a record to be created, trusted, published, stale, or archived.

## General lifecycle philosophy

Every GoldPan entity moves through the same fundamental arc:

```
Create → Enrich → Review → Approve → Publish → Monitor → Refresh → Archive
```

Not all stages apply to every entity type — a Governance Result has no "Publish" step visible to customers, for example — but the arc defines the vocabulary and the intent. Stages are not skipped silently; a record that moves from Create directly to Publish is either explicitly fast-tracked or is a bug.

## Design rules

1. **Every entity has one owner.** At any lifecycle stage, exactly one OS is responsible for the record. Ownership may transfer at a defined stage transition, but joint ownership is a design smell.

2. **Trust increases through review, not age.** A record does not become more trustworthy simply because it is old. Trust is conferred by a human review step, a verified source, or a successful automated check — not by time.

3. **Published data can always be traced back to evidence.** Any fact visible to a customer must have a traceable provenance chain: published value → evidence record → source URL or verified input.

4. **Records become stale before they become obsolete.** A record does not go from current to wrong overnight. The lifecycle includes a `stale` state that signals review is needed before the record reaches `outdated` or `incorrect`.

5. **Recanvass refreshes existing records rather than replacing them.** A recanvass run updates fields on the existing record and creates a new evidence version. It does not create a parallel record or mark the original as deleted.

6. **Archive is preferred over delete whenever practical.** Deleted records leave orphan references and erase audit history. Archived records remain queryable and traceable. Hard deletion is reserved for GDPR/legal requirements, not operational cleanup.

7. **Every lifecycle transition should be logged.** The transition itself — not just the final state — is the meaningful event. Logs capture: previous state, new state, actor (user or system), timestamp, and reason.

8. **Lifecycle state should always be explainable.** A new team member should be able to open any record, read its current lifecycle state, and understand why it is in that state without needing to ask anyone.

---

## Entity lifecycle definitions

### Restaurant (`evidence.restaurants`)

| Stage | Meaning | Owner | Who may mutate |
|---|---|---|---|
| `prospect` | Record created; identity incomplete | Restaurant OS | Restaurant OS, Intake, BD (identity fields via enrichment) |
| `enriching` | Identity Enrichment Pipeline running | Restaurant OS | Identity Enrichment Pipeline only |
| `qualified` | Identity complete enough for Intake to begin | Restaurant OS | Intake OS, Restaurant OS |
| `onboarding` | Active intake in progress | Intake OS | Intake OS |
| `evidence_acquisition` | Source verification underway | Intake OS | Intake OS |
| `verification` | Intake packet under human review | Intake OS | Reviewer |
| `qa_review` | Post-approval QA pass | Restaurant OS | Reviewer |
| `published` | Live and customer-visible | Restaurant OS | Restaurant OS (via update workflow) |
| `recanvassing` | Undergoing scheduled or triggered recanvass | Intake OS | Intake OS |
| `paused` | Temporarily withdrawn from publishing | Restaurant OS | Restaurant OS |
| `suspended` | Removed for cause | Restaurant OS | Restaurant OS (with approval) |
| `archived` | No longer active; retained for history | Restaurant OS | Read-only |

**Trust threshold:** `published` status implies that at least one full intake cycle has completed and a reviewer has approved the evidence.  
**Customer-visible from:** `published` only.  
**Becomes stale when:** `last_canvassed` exceeds the recanvass interval defined in the Freshness policy.  
**Refresh path:** Recanvass workflow (Workflow 3).  
**Archive over delete:** Yes — archived restaurants remain queryable for evidence, governance, and audit purposes.

---

### Partner (`operations.partners`)

| Stage | Meaning | Owner | Who may mutate |
|---|---|---|---|
| `prospect` | Identified; no contact made | BD OS | BD OS |
| `outreach` | Initial contact attempted | BD OS | BD OS |
| `engaged` | Two-way communication established | BD OS | BD OS |
| `negotiating` | Terms or partnership model under discussion | BD OS | BD OS |
| `active` | Partnership live | BD OS | BD OS |
| `paused` | Relationship on hold | BD OS | BD OS |
| `declined` | Restaurant declined partnership | BD OS | BD OS (read-only after) |
| `churned` | Previously active; relationship ended | BD OS | BD OS (read-only after) |
| `archived` | Retained for history | BD OS | Read-only |

**Trust threshold:** None — BD relationship data is not published to customers.  
**Customer-visible from:** Never directly (restaurant facts come from `evidence.restaurants`, not from the partner record).  
**Becomes stale when:** `next_followup_date` is overdue.  
**Refresh path:** BD follow-up workflow.  
**Archive over delete:** Yes.

---

### Intake Packet

**Canonical model per DEC000001 (Founder-approved 2026-07-13):** `docs/decisions/DEC000001_CANONICAL_INTAKE_PACKET_STATE_MACHINE.md`. Six `packet_status` values total — the earlier `draft`, `submitted`, `superseded`, and `archived` stage rows below are **replaced**, not merely relabeled: `draft` is excluded from the canonical model (no packet exists in Master OS before `pending_review`); `submitted` is unified into `pending_review` (a resubmission also lands in `pending_review`, per DEC000001 §5.1); and `superseded`/`archived` are **not lifecycle stages** — they are non-status attributes/relationships (`superseded_by_packet_id`, `archived_at`) that can apply alongside a packet's terminal status, per DEC000001 §7 item 4.

| Stage | Meaning | Owner | Who may mutate |
|---|---|---|---|
| `pending_review` | Awaiting or returned-to claim; payload read-only | Intake OS | Payload: no one. Status: `intake.review.claim` (Governance Reviewer) → `in_review`; or entry via `intake.packet.submit`/`intake.packet.resubmit` (Intake Specialist) |
| `in_review` | Claimed by a reviewer; actively being decided | Intake OS | Payload: no one (Governance Reviewers never mutate `packet_data`, per DEC000001 §4, §5.2). Status: claimant (or admin override) via `.release`, `.approve`, `.return`, or `.reject` |
| `returned` | Sent back for correction; **the only status where payload is mutable** | Intake OS | Payload: Intake Specialist only, via `intake.packet.edit_payload`. Status: Intake Specialist via `intake.packet.resubmit` → `pending_review` |
| `approved` | Reviewer accepted; ingestion authorized; payload immutable | Intake OS | Read-only, except system transition to `ingested` via `intake.packet.commit_ingest` on confirmed durable write (DEC000001 §5.7) |
| `rejected` | Terminal — fundamentally invalid or inappropriate as an Intake Packet; not correctable | Intake OS | Read-only. Reopening is out of scope for ordinary workflow (DEC000001 §5.10) |
| `ingested` | Evidence durably written to knowledge tables; factual system outcome, not a human judgment | Intake OS | Read-only |

**Non-status attributes (not stages):** `superseded_by_packet_id` (system-derived from canonical restaurant identity + canvass-date chronology among `ingested` packets, single-hop chain, DEC000001 §5.6) and `archived_at` (manual or future policy-driven; eligible only from `rejected` or `ingested`, DEC000001 §5.11).

**Trust threshold:** `approved` — a human reviewer has signed off.  
**Customer-visible from:** Never directly; downstream via published restaurant evidence.  
**Becomes stale:** A packet never becomes stale itself — it is point-in-time. Staleness belongs to the restaurant record, not the packet.  
**Archive over delete:** Yes — packets are permanent audit records; archival never deletes payload or event/revision history (DEC000001 §5.11).

---

### Evidence record (dish, ingredient, claim, transparency score)

| Stage | Meaning | Owner |
|---|---|---|
| `pending` | Written during ingestion; not yet governance-validated | Intake OS |
| `active` | Governance-validated; included in published output | Knowledge OS |
| `superseded` | Replaced by a newer intake version | Knowledge OS |
| `flagged` | Governance detected an anomaly; under review | Governance OS |
| `archived` | Removed from active output; retained for history | Knowledge OS |

**Trust threshold:** `active` — governance has run and passed.  
**Customer-visible from:** `active` only.  
**Becomes stale when:** Parent restaurant's `recanvass_status` is `overdue`.  
**Refresh path:** Recanvass → new intake packet → new evidence version supersedes old.  
**Archive over delete:** Yes.

---

### Governance Result

| Stage | Meaning | Owner |
|---|---|---|
| `pending` | Governance run queued or in progress | Governance OS |
| `passed` | All rules passed; evidence approved | Governance OS |
| `flagged` | One or more rules triggered; requires review | Governance OS |
| `overridden` | Flag acknowledged and overridden by reviewer | Governance OS |
| `archived` | Superseded by a newer governance run | Governance OS |

**Trust threshold:** `passed` or `overridden` (with documented reason).  
**Customer-visible from:** Never directly; downstream via evidence trust state.  
**Archive over delete:** Yes — governance history is an audit trail.

---

### Restaurant Update Submission (from restaurant or staff)

**Canonical model per DEC000002 (Founder-approved 2026-07-18):** `docs/decisions/DEC000002_submission_state_machine.md`, implemented in `supabase/migrations/021_submission_state_machine.sql` and `022_submission_review_rpcs.sql`. Five `status` values total, and a **separate disposition model** layered on top of `approved` — the earlier `received`, `accepted`, and `archived` stage rows below are **replaced**, not merely relabeled: `received` is not a distinct status (a submission enters directly at `pending_review`); `accepted` is replaced by `approved` plus a `disposition_type`/`disposition_status` pair, since "approved" and "what happens next" are two different questions (DEC000002 §5.3-§5.4); and `archived` is **not a lifecycle stage** — it is a non-status attribute (`archived_at`), per DEC000002 §5.9.

**Review status:**

| Stage | Meaning | Owner | Who may mutate |
|---|---|---|---|
| `pending_review` | Awaiting or returned-to claim; payload read-only | Restaurant Operations OS | Status: `submission.restaurant_update.claim` (reviewer) → `in_review`; entry via restaurant/staff submission, or via `submission.restaurant_update.resubmit` creating a brand-new child row (registry status `draft` — see note below) |
| `in_review` | Claimed by a reviewer; actively being decided | Restaurant Operations OS | Status: claimant (or admin override) via `.release`, `.approve`, `.return`, or `.reject` |
| `returned` | Sent back for correction; **terminal for that row — it never moves again.** Correction happens via a brand-new child row, never an in-place edit (DEC000002 §5.7) | Restaurant Operations OS | Payload: no one, on this row. `submission.restaurant_update.resubmit` creates a new child at `pending_review` and sets this row's `superseded_by_submission_id`, atomically, in one transaction |
| `approved` | Reviewer accepted; disposition selected atomically with the same transition; payload immutable | Restaurant Operations OS (submission row itself, end to end, per §4) | Read-only submission row. `disposition_status` advances via routing commands (`.convert_to_intake`, `.route_to_identity_review`, `.escalate_exception`) and downstream owning-OS callbacks — never by mutating the submission row's `status` again |
| `rejected` | Terminal — change not applied; reason recorded | Restaurant Operations OS | Read-only |

**Disposition model (not a further review-status transition — layered on top of `approved`, DEC000002 §5.3-§5.4):**

| `disposition_status` | Meaning |
|---|---|
| `unassessed` | No disposition selected yet (pre-approval default; no approved submission may remain here) |
| `pending` | Disposition selected at approval; downstream handoff not yet created |
| `in_progress` | Downstream record created and linked; owning OS has not yet reported a terminal outcome |
| `completed` | Downstream owning OS reports a terminal success, or `disposition_type = no_action` was approved (mandatory `resolution_summary`, the only record that disposition ever produces) |
| `failed` | Handoff creation failed, or the downstream owning OS reported a terminal failure. `failure_stage` (`handoff_call` \| `local_write` \| `downstream_terminal`) records where, per §5.3 |

| `disposition_type` | Routes to | Owning OS (sole) | Command | Build status |
|---|---|---|---|---|
| `intake_required` | Intake Packet | Intake OS (DEC000001) | `submission.convert_to_intake` | FK built (`resulting_intake_packet_id`), no RPC |
| `identity_review` | Identity Review Queue | Restaurant Operations OS | `submission.route_to_identity_review` | Placeholder FK built, destination table doesn't exist yet — blocked |
| `no_action` | No handoff | Restaurant Operations OS (closes within `.approve` itself) | none | Schema built, no RPC |
| `exception_escalation` | Exception request | Governance OS, sole owner (never jointly with Knowledge OS) | `submission.escalate_exception` | Placeholder FK built, destination entity doesn't exist yet — blocked |

**Non-status attributes (not stages):**
- `resubmission_of_submission_id` / `superseded_by_submission_id` — resubmission lineage. Each parent has at most one direct child (`UNIQUE` constraint); a chain cannot cycle by construction, since `resubmit` only ever creates a brand-new row and no command rewires an existing link, per DEC000002 §5.7-§5.8. Both fields are immutable once written by the child-creation transaction.
- `archived_at`, `archived_by_user_id`, `archive_reason` — archival eligibility: `rejected` submissions; `approved` submissions with `disposition_status = completed`; `returned` parents that already have a linked child (eligibility depends only on having a child, not the child's own outcome), per DEC000002 §5.9. Archival never deletes payload or event history.
- `resulting_intake_packet_id` (canonical FK, `operations.intake_packets`, ready to build), `resulting_intake_session_id` (non-canonical, optional, no confirmed target, excluded from cardinality rules), `identity_review_item_id` (Blueprint-defined, target table not yet implemented), `exception_request_id` (future recommendation, no confirmed target) — at most one canonical FK populated at a time, per DEC000002 §5.11.

**Audit coverage:** `operations.restaurant_update_submission_events` (append-only), covering `claim, release, return, resubmit, approve, reject, disposition_selected, disposition_handoff_attempted/_succeeded/_failed, downstream_completion_received, archive`. Every row sets `actor_type` (`user`/`system`/`pipeline`) and `actor_id`; handoff events additionally distinguish the initiating human actor from the executing system actor, and `downstream_completion_received` records the downstream owning OS's own callback identity — per DEC000002 §5.10.

**Command note — `resubmit`'s invocation authority is not yet decided.** DEC000002 §7 item 5 approves `submission.restaurant_update.resubmit`'s existence, model, and mechanics only — not who may call it. The RPC (`operations.resubmit_restaurant_update_submission`, migration 022) is built, but no `GRANT EXECUTE` has been issued to any role; its Command Registry entry (CMD000040) stays `draft` until a separate role/portal-origin decision resolves invocation authority.

**Trust threshold:** `approved` — a staff reviewer has confirmed the change.  
**Customer-visible from:** Never directly; downstream via whichever disposition's target object is eventually published.  
**Archive over delete:** Yes — submissions are permanent audit records; archival never deletes payload or event history (DEC000002 §5.9).

---

### AI Run (`operations.ai_usage_logs`)

| Stage | Meaning | Owner |
|---|---|---|
| `completed` | Run succeeded; result logged | AI OS |
| `error` | Run failed; error captured | AI OS |
| `timeout` | Run exceeded time limit | AI OS |
| `budget_exceeded` | Run blocked by budget cap | AI OS |

AI runs are append-only records. They are never updated or archived — they are permanent logs.  
**Archive over delete:** N/A — logs are immutable.

---

## Cross-entity lifecycle dependencies

These dependencies define when one entity's lifecycle is gated on another's:

| Dependency | Rule |
|---|---|
| Intake Packet → Restaurant | An intake packet cannot reach `approved` if the parent restaurant is `suspended` or `archived` |
| Evidence → Governance | Evidence does not become `active` until governance passes |
| Restaurant → Customer visibility | A restaurant is not customer-visible until at least one evidence set is `active` |
| Partner → Restaurant | A partner record may exist without a restaurant record; but a restaurant record must exist before BD can link to it for identity display |
| Submission → Identity | A restaurant update submission does not update `evidence.restaurants` directly; it flows through review first |

---

## Lifecycle transition log (standard)

Every lifecycle transition must write a record with:
- `entity_type` — e.g. `restaurant`, `intake_packet`, `partner`
- `entity_id` — the record's primary key
- `from_state` — previous lifecycle state
- `to_state` — new lifecycle state
- `actor_type` — `user` / `system` / `pipeline`
- `actor_id` — user ID or system agent name
- `reason` — free text or structured reason code
- `created_at` — timestamp

Until a dedicated `lifecycle_events` table is built, critical transitions are logged via existing audit mechanisms (`ai_usage_logs`, recanvass notes, intake review flags).

---

# 6. Core Workflows

## Workflow 1: Restaurant BD → Intake → Publish

1. Restaurant added to BD pipeline.
2. Partner record created.
3. Restaurant linked or created in evidence.restaurants.
4. BD moves restaurant to engaged.
5. Team starts Intake from partner page.
6. Intake packet created.
7. AI/human processes menu.
8. Review flags created.
9. Human approves.
10. Evidence enters Knowledge OS.
11. Governance runs.
12. Restaurant becomes publishable.
13. Restaurant appears in customer product.

---

## Workflow 2: Restaurant Update Submission

1. Restaurant submits update.
2. Submission lands in pending_review.
3. Team reviews.
4. If valid, Intake packet/update is created.
5. Human approves.
6. Evidence updates.
7. Governance reruns.
8. Published output updates.

No restaurant submission writes directly to production evidence.

---

## Workflow 3: Recanvass

1. Restaurant becomes stale or menu change detected.
2. Restaurant OS creates recanvass need.
3. Intake OS runs updated source acquisition.
4. Differences are reviewed.
5. Approved changes update evidence.
6. Governance reruns.
7. Freshness is updated.

---

## Workflow 4: Business Development Follow-up

1. Partner has next_followup_date.
2. BD OS surfaces overdue follow-up.
3. User opens partner detail.
4. AI optionally drafts follow-up.
5. Human sends message.
6. Action is logged.
7. Partner status updates.

---

## Workflow 5: AI Call

1. Feature requests AI call.
2. AI OS checks budget and feature flags.
3. If allowed, call executes.
4. Tokens/cost/status logged.
5. Dashboard updates.
6. If budget exceeded, user-safe message appears.

---

# 7. Navigation Blueprint

## Master OS sidebar

### Overview
- Dashboard
- Daily Brief
- System Health

### Restaurants
- Directory
- Map
- Review Queue
- Recanvass
- Publishing

### Business Development
- Pipeline
- Partner Map
- Follow-ups
- Organizations
- Actions

### Intake
- Intake Queue
- Packets
- Review Flags
- Submissions
- Candidate Schema

### Knowledge
- Dishes
- Ingredients
- Claims
- Calories
- Transparency Scores

### Governance
- Rule Outcomes
- Unknowns
- Rules Registry
- Audit

### Analytics
- Search Analytics
- Restaurant Views
- Customer Demand
- Market Map

### AI
- AI Usage
- Agents
- Prompt Library
- Budget Controls

### Finance
- Costs
- Revenue
- Grants
- Unit Economics

---

# 7b. Internal Search / Command Bar *(Future)*

Master OS should eventually support a global search and command palette accessible from any screen.

Searchable entities:
- Restaurants
- Partners
- Dishes
- Ingredients
- Intake packets
- Submissions
- Partner actions
- Governance outcomes
- AI runs
- Prompts

The command bar should allow operators to navigate directly to any record, trigger common actions, and surface context without clicking through the full navigation tree. This reduces founder memory dependence and enables new team members to operate efficiently.

---

# 8. Map Strategy

## Restaurant Operations Map
**Purpose:** Show restaurant coverage and operational status.

Marker colors:
- Published/current
- Needs review
- Needs recanvass
- Intake pending
- Unpublished
- Paused

## Business Development Map
**Purpose:** Show partner pipeline.

Restaurant partner marker colors:
- prospect
- outreach
- engaged
- negotiating
- active
- paused
- declined
- churned

Non-restaurant partner maps:
- dietitians/clinics
- gyms
- corporate wellness/employers
- universities
- community/media/investors

If exact address is unavailable:
- use city-level point
- show in Needs Location queue

---

# 9. Agent Strategy

AI agents are not always-on employees.
They are invoked capabilities inside Master OS.

## Agent types

### CEO Assistant
- Daily brief
- Risk summary
- Priority recommendations

### BD Assistant
- Draft follow-up emails
- Summarize notes
- Suggest next actions
- Rank opportunities

### Restaurant Intelligence Assistant
- Identify weak restaurant records
- Recommend recanvass priority
- Summarize restaurant health

### Intake Assistant
- Process menus
- Create packets
- Flag ambiguity
- Recommend schema candidates

### Governance Assistant
- Explain unknowns
- Audit scoring
- Suggest rule improvements

### Analytics Assistant
- Explain traffic changes
- Surface demand signals
- Connect analytics to BD priorities

### Finance/AI Cost Assistant
- Explain AI spend
- Forecast monthly cost
- Recommend cheaper model usage

## Rules
- Agents do not write directly to production unless explicitly allowed.
- Agent actions are logged.
- AI cost is tracked.
- Human approval required for evidence changes.

---

# 10. Build Phases

## Phase 1 — Foundation ✅ Completed
- Supabase migration
- FastAPI backend
- Next.js admin shell
- AI usage dashboard
- Restaurant Operations page
- Business Development shell

## Phase 2 — Master OS Blueprint ✅ Completed
- Document module ownership
- Define navigation
- Define data boundaries
- Define workflow handoffs
- Define future portal boundaries

## Phase 3 — Editable Business Development OS
- Create/edit partners
- Add actions/notes
- Follow-up tracking
- Status updates
- Restaurant-linked CRM
- BD map

## Phase 4 — Restaurant Master Page
- Full restaurant profile
- Dishes
- Evidence coverage
- Claims
- Freshness
- BD link
- Intake link
- Governance status

## Phase 5 — Intake OS UI
- Intake queue
- Packet review
- Review flags
- Approvals
- Submission review

## Phase 6 — Governance OS UI
- Unknowns
- Rule outcomes
- Filter readiness
- Scoring audit
- Rule registry

## Phase 7 — Analytics OS
- Direct event logging
- Search analytics
- Restaurant views
- Customer demand report
- Market opportunity map

## Phase 8 — Restaurant Portal
- Restaurant login
- Update submissions
- Contact info
- Menu docs
- Partnership interest
- Review-gated evidence flow

## Phase 9 — Partner Portal
- Dietitians
- Clinics
- Employers
- Corporate wellness
- Sponsorship/referral flows

---

# 11. Current Build Priority

Do not attempt to build all modules at once.

Immediate next priority:
1. Business Development OS editable
2. Partner actions working
3. Partner detail page
4. Restaurant-linked BD records
5. BD map
6. Restaurant Master Page
7. Intake cross-links

Read-only views first when possible.
Mutations only through FastAPI.
All important changes logged.

---

# 12. Design Rules

**Rule 1** — Every page must answer an operational question.

**Rule 2** — Every mutation must have an owner.

**Rule 3** — Every important change must be logged.

**Rule 4** — AI assists but does not silently decide.

**Rule 5** — Restaurant-submitted information is not production evidence until reviewed.

**Rule 6** — Business Development notes are not menu evidence.

**Rule 7** — Supabase is the system of record.

**Rule 8** — The Master OS should reduce founder memory dependence.

**Rule 9** — The system should be understandable by a future employee.

**Rule 10** — Do not build polish before workflow truth.

---

# 12b. Audit Philosophy

Every mutation in GoldPan must be traceable. A change without a record is a liability.

Every mutation should answer:

| Field | Description |
|---|---|
| who | The user, role, or agent that made the change |
| what | The table, field, and record that changed |
| when | Timestamp with timezone |
| why | Reason or action context (required for evidence mutations) |
| previous value | The value before the change |
| new value | The value after the change |
| source | System, form, API call, or agent that triggered it |
| human or AI | Whether the action was initiated by a human or AI agent |
| approval status | Whether the change required and received human approval |

Audit records are never deleted. This is enforced by schema constraints.

---

# 12c. AI Philosophy

GoldPan follows an AI-assisted architecture. AI is a reasoning tool, not the system of record.

The role of AI is to accelerate understanding, summarize information, identify ambiguity, generate recommendations, and assist human operators.

Deterministic software remains responsible for validation, calculations, enforcement, permissions, workflow orchestration, and repeatable business logic.

Humans remain responsible for approving production evidence and governance decisions.

## AI Rules

1. AI performs reasoning.
2. Software performs validation.
3. Humans approve truth.
4. Evidence is never created solely by AI.
5. AI never bypasses Governance or review workflows.
6. Every AI call must be logged.
7. AI costs must be tracked.
8. AI feature availability is controlled through feature flags.
9. AI outputs should be explainable whenever practical.
10. GoldPan should prefer deterministic software whenever reasoning is unnecessary.
11. AI should augment employees rather than obscure operational visibility.
12. Every AI action should be attributable to an agent, prompt version, user, or workflow.

---

# 12d. Long-Term Scale Vision

Master OS is designed to scale with GoldPan through each phase of growth.

| Stage | Scope |
|---|---|
| Current | Birmingham launch — 27 restaurants, solo founder |
| Near-term | 100 restaurants — Birmingham full coverage |
| Mid-term | 1,000 restaurants — multi-city Southeast expansion |
| Growth | 40 metros — regional national presence |
| Vision | National food transparency platform |
| Ecosystem | Health partner ecosystem (dietitians, clinics, corporate wellness) |
| Ecosystem | Restaurant partner ecosystem (portals, direct submissions, verification partnerships) |

Architectural decisions made today must not require rewrites to support this scale. The schema, OS boundaries, and evidence architecture are designed to accommodate this trajectory without fundamental changes.

---

# 13. Success Criteria

GoldPan Master OS succeeds when:
- The founder can see company health in one place.
- Restaurant status is visible.
- Partnership follow-ups are not forgotten.
- Intake can scale beyond one person.
- Governance unknowns are explainable.
- AI costs are controlled.
- Analytics inform BD and product decisions.
- New employees can operate without asking where everything lives.
- Restaurants can eventually submit data safely.
- The company can double in Birmingham without operational chaos.

---

# 14. Guiding Statement

GoldPan™ Master OS exists to transform knowledge into trusted operations, and trusted operations into scalable growth.

---

# Appendix A — GoldPan Philosophy

GoldPan believes:

- Truth is more valuable than speed.
- Unknown is preferable to incorrect.
- Evidence is more valuable than opinion.
- Transparency creates trust.
- Systems should make people better.
- Automation should preserve judgment.
- Excellent companies are built on excellent operating systems.
- Every decision should make future GoldPan easier to operate.

---

# Appendix B — Role Ownership Matrix *(Placeholder)*

This section will define each operational role within GoldPan as the team grows. Each role entry will include:

| Field | Description |
|---|---|
| Mission | What this role exists to accomplish |
| Systems owned | Which Master OS modules this role primarily operates |
| Decisions they can make | Autonomous decisions within their scope |
| KPIs they monitor | Metrics they are accountable for |
| Systems they influence | Modules they read or inform without owning |
| Expected deliverables | Recurring outputs this role produces |

**Roles to be defined:**
- Founder / CEO
- Head of Restaurant Operations
- Business Development Lead
- Intake Specialist
- Governance Reviewer
- Knowledge Curator
- Marketing Lead
- Finance Lead
- Support Lead
- System Administrator

*This matrix will be completed when GoldPan hires its first employees or engages contractors in defined operational roles.*
