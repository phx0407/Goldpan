# GoldPan™ Backend Master OS Vision

**Version:** 1.0  
**Date:** 2026-07-05  
**Status:** Architecture — pending implementation  
**Scope:** Governing document for GoldPan's backend operational control center

---

## Purpose

This document is the governing specification for GoldPan's backend. It is not an admin panel. It is the Master Operating System — the operational control center from which every GoldPan workflow is managed, monitored, and maintained.

The backend must mirror the architecture that already governs GoldPan's data. That architecture has hard boundaries. The backend must enforce them, not paper over them.

This document covers: system architecture, the six OS modules, the canonical restaurant entity, database architecture, API architecture, authentication and authorization, audit logging, report generation, background jobs, feature flags, dashboard architecture, navigation, deployment, scalability, and a phased implementation plan.

---

## Governing Principles

These principles derive from GOLDPAN_OS_ARCHITECTURE.md, GOLDPAN_PHILOSOPHY.md, and the Rules Registry. The backend must operationalize all of them.

**1. Intake records evidence. Governance derives conclusions. Backend manages the system.**

The backend is a third OS — it does not produce evidence and it does not compute dietary conclusions. It provides the operational surface for humans to manage the pipeline that does.

**2. One restaurant. One canonical entity.**

Every operating system references the same restaurant record. There is no "restaurants table for intake" and a separate "restaurants table for reporting." One record. Referenced everywhere.

**3. Human judgment is always accountable.**

Automation may assist at any stage, but a human is accountable for every state transition that introduces or modifies evidence. The backend enforces this: transitions that require human sign-off have explicit approval workflows. The pipeline cannot advance a restaurant past a stage without a human actor on record.

**4. The Evidence/Knowledge boundary is architectural, not aspirational.**

The backend enforces this boundary structurally — in the database schema, in the API, in the UI. Governance outputs never flow back into the Evidence tables. The UI cannot conflate them. This is not a code review comment; it is enforced by the schema.

**5. AI never writes directly to production.**

AI output is always staged. A human reviews and approves. The backend models this explicitly: every AI-assisted action creates a staging record, not a production record.

**6. Deterministic over clever.**

The backend builds on GoldPan's existing principle: if you delete all computed outputs, rerunning the pipeline should reproduce them exactly. Every report, every derived filter, every freshness status is regeneratable from the evidence system. The backend enforces this by keeping evidence immutable and making all computation explicit and repeatable.

**7. Audit trail is first-class.**

Every state change is logged with actor, timestamp, and reason. This is not a feature — it is a schema constraint. Records without provenance do not exist in this system.

---

## Phase 1 Infrastructure Decision: Supabase

### The Question

Should GoldPan remain on Google Sheets for the first backend phase, bridge to Airtable, or migrate directly to Supabase (PostgreSQL)?

### Option Analysis

**Google Sheets (current)**

Sheets has carried GoldPan from zero to a working pipeline with 700+ dishes, 16 governance rules, a freshness system, and a functioning intake workflow. That is real. It should not be discarded carelessly.

But Sheets has structural limits that are already causing friction:
- The Restaurant_Registry and Lifecycle_Events tabs are *designed but do not exist* — they were deferred because implementing them in Sheets requires a migration script and column-order management.
- The Allergen_Disclosures tab requires manual entry because there is no row-level API to enforce schema at write time.
- Adding Calorie_Value and Calorie_Source_Text required two one-shot scripts. Adding any column requires a one-shot script.
- There is no referential integrity — a Dish_ID in Ingredient Details can reference a non-existent dish in DLD, and the only enforcement is `validate_database.py`.
- Role-based access is impossible. Canvassers and QA reviewers see the same spreadsheet.
- The pipeline (gspread reads) is brittle to column reorder, whitespace in headers, and tab rename.
- Lifecycle state is not stored anywhere — it is implicit in which scripts have been run.

**Airtable**

Airtable is a no-code database that solves the UI problem but not the architecture problem. It is not PostgreSQL. It does not have JOIN, transactions, or triggers. For GoldPan's needs — complex governance rule evaluation, append-only audit logs, referential integrity across six OS modules — Airtable is the wrong foundation. It would solve today's UI friction and introduce tomorrow's data model debt.

**Supabase**

Supabase is PostgreSQL with built-in Auth, Row-Level Security, a REST API, real-time subscriptions, Storage (for PDFs and allergen guides), and Edge Functions. The user has a dormant account. It is open-source and self-hostable.

For GoldPan's architecture, Supabase is the correct Phase 1 backend database because:
- PostgreSQL referential integrity enforces the canonical entity model
- Row-Level Security enforces the Evidence/Knowledge boundary structurally
- The REST API replaces gspread with a stable, typed interface
- Triggers enforce append-only Lifecycle_Events — no row is ever deleted, no transition is undone
- Auth with JWT roles maps directly to canvasser / QA reviewer / admin / governance engine
- Storage handles allergen guide PDFs and menu document archives with provenance tracking
- Edge Functions can trigger the governance pipeline when a restaurant transitions lifecycle state
- The existing Python scripts (pipeline.py, compute_derived_filters.py, fetch_dishes.py) can call the Supabase REST API with minimal changes
- The local dev environment matches production — no "it works on Sheets, fails in prod" class of bugs

### Decision

**Move directly to Supabase. Do not extend Sheets as the production database for the backend phase.**

This is not a big-bang migration. The migration is one phase of a phased plan (Phase 2). Until then, the pipeline continues to run against Sheets while the Supabase schema is built and validated. Phase 1 is schema design and Supabase setup. Phase 2 is migration and pipeline switchover. Phase 3 onwards builds the backend UI on top of the now-stable Supabase foundation.

Google Sheets is not abandoned — it continues as a human-readable view and manual override surface during the migration window. Once the pipeline runs cleanly against Supabase for 30 days, Sheets becomes read-only.

---

## Canonical Restaurant Entity

The canonical restaurant entity is the single record that every operating system references. It is the architectural foundation of the entire backend.

### What the Canonical Entity Is

A restaurant in GoldPan is not just a name and an address. It is a durable record of:
- **Identity** — what this restaurant is, where it is, what it presents to the public
- **Lifecycle state** — where this restaurant is in GoldPan's pipeline right now
- **Coverage rationale** — why GoldPan is covering this restaurant (the documented signal)
- **Evidence quality** — how reliable the dietary data is (Evidence Tier, Source Tier)
- **Operational state** — who owns this restaurant in the canvassing queue, what the next required action is
- **Freshness state** — when was this restaurant last verified, what is the recanvass status

### Why "Canonical" Matters

Every OS module references the restaurant by `restaurant_id`. The Intake OS records evidence against it. The Governance OS computes filter conclusions against it. The Business Development OS tracks its prospect status. The Restaurant Intelligence OS tracks its menu changes over time. The Customer Analytics OS tracks which users searched for it.

Without a canonical entity, these systems diverge. A restaurant is one record, or it is chaos.

### Canonical Restaurant Schema (Supabase target)

```sql
-- Core identity (never changes after creation)
restaurant_id         uuid PRIMARY KEY DEFAULT gen_random_uuid()
external_id           text UNIQUE NOT NULL  -- e.g., "R027"
name                  text NOT NULL
address               text
neighborhood          text
city                  text
state                 text
zip                   text
latitude              numeric
longitude             numeric
created_at            timestamptz DEFAULT now()

-- Operating identity (updated on recanvassing)
official_website      text
menu_url              text
online_ordering_url   text
phone                 text
hours                 text               -- raw hours string from menu source
menu_statement        text               -- restaurant's own description of their food

-- Lifecycle state (FK to lifecycle_events)
lifecycle_status      text NOT NULL      -- enum enforced by CHECK constraint
status_updated_at     timestamptz
status_updated_by     uuid               -- FK to users

-- Coverage
prospect_source       text               -- customer_request / canvasser_discovery / ...
prospect_date         date
coverage_signal       text               -- documented rationale
coverage_approved_by  uuid               -- FK to users
coverage_approved_at  timestamptz

-- Evidence quality
evidence_tier         text               -- Tier_1_Confirmed / Tier_2_Disclosed / Tier_3_Inferred
primary_source_url    text
primary_source_tier   text               -- Tier_1 / Tier_2 / Tier_3
has_allergen_guide    boolean DEFAULT false

-- Operations
assigned_canvasser_id uuid               -- FK to users
assigned_reviewer_id  uuid               -- FK to users
published_date        date
last_canvassed        date
recanvass_status      text               -- current / due_soon / overdue / needs_review
recanvass_tier        int                -- 1 / 2 / 3

-- Source check (Track A freshness)
last_source_check     date
source_check_status   text               -- ok / changed / unreachable / overdue / unknown

-- Exceptions
suspension_reason     text
deactivation_reason   text
notes                 text
```

### Lifecycle Status Enum

Enforced by CHECK constraint on `lifecycle_status`:
`prospect | qualified | onboarding | evidence_acquisition | verification | qa_review | published | recanvassing | suspended | deactivated`

### Lifecycle Events (append-only audit log)

```sql
lifecycle_event_id    uuid PRIMARY KEY DEFAULT gen_random_uuid()
restaurant_id         uuid NOT NULL REFERENCES restaurants(restaurant_id)
event_date            date NOT NULL
from_status           text NOT NULL
to_status             text NOT NULL
actor_id              uuid               -- FK to users; NULL only for system events
actor_type            text               -- canvasser / reviewer / pipeline / freshness_system
notes                 text
created_at            timestamptz DEFAULT now()
```

A PostgreSQL trigger prevents UPDATE and DELETE on this table. Every state change in the `restaurants` table produces an insert in `lifecycle_events`. The audit trail is structurally complete.

---

## The Six Operating Systems

### OS 1 — Intake OS

**What it owns:** The complete journey from prospect identification to published restaurant. All evidence collection. All human canvassing workflows. All verification and QA. The lifecycle audit trail.

**Backend modules:**
- **Prospect Queue** — list of unqualified prospects, coverage evaluation workflow, qualification decision recording
- **Canvasser Dashboard** — assignment queue, active onboarding checklist, evidence entry progress, validation status
- **Evidence Entry** — structured dish entry with source reference enforcement, ingredient row entry, allergen disclosure entry
- **Verification Workflow** — spot-check assignment, source-matched comparison interface, discrepancy logging, pass/fail decision
- **QA Review Dashboard** — pipeline run trigger, filter conclusion review, approval/rejection decision, publishing workflow
- **Lifecycle Timeline** — visual audit trail for each restaurant's full history (prospect to present)

**Key constraints the backend must enforce:**
- No ingredient row without a `Source_ID` reference
- No allergen disclosure row without complete provenance (source_type, source_reference, source_date, scope)
- No lifecycle transition without a `lifecycle_events` row
- `evidence_acquisition` cannot exit without `validate_database.py` passing with no ERRORS
- `qa_review` cannot approve without a logged freshness record update

### OS 2 — Governance OS

**What it owns:** All derived conclusions. All governance rules. The pipeline that computes conclusions from evidence. Freshness monitoring. Transparency scoring.

**Backend modules:**
- **Pipeline Control Center** — trigger full pipeline runs, view run history, inspect stage-by-stage results
- **Rules Registry UI** — view all GP-RULEs, their version history, their current status, which restaurants are affected by each rule
- **Filter Registry UI** — view all registered derived filters, their dependency types, which rules they apply, their current computation counts
- **Freshness Monitor** — live dashboard of all restaurants' recanvass status, source check status, overdue counts, needs_review alerts
- **Transparency Scoring** — per-dish scoring UI, batch scoring workflows, scoring history, score distribution reports

**Key constraints:**
- Governance pipeline outputs (derived_filters, transparency_scores) are stored in Knowledge System tables — separate from Evidence System tables, no FK from Knowledge to Evidence that would allow Knowledge to overwrite Evidence
- Rules Registry is read-only in the UI — rule changes require a code commit and version increment
- Pipeline runs are logged with full StageResult JSON for every stage

### OS 3 — Business Development OS

**What it owns:** The commercial pipeline. Restaurant relationships. Coverage expansion strategy. Partner tracking.

**Backend modules:**
- **Coverage Map** — geographic view of current restaurant coverage, coverage gaps, prospect density
- **Prospect Pipeline** — Kanban-style view of prospects by lifecycle stage, filtering by neighborhood/cuisine/signal
- **Restaurant Relationship Log** — history of all direct restaurant contacts (calls, emails, responses), confirmation requests, allergen guide requests
- **Coverage Analytics** — coverage signal distribution, which signal types are most common, coverage gaps by neighborhood
- **Expansion Planner** — target neighborhood/cuisine lists, coverage goals, prioritized prospect queue

### OS 4 — Restaurant Intelligence OS

**What it owns:** Longitudinal restaurant data. Menu change detection. Source monitoring. Competitive intelligence.

**Backend modules:**
- **Menu Change Log** — history of detected and confirmed menu changes per restaurant, version-controlled dish snapshots
- **Source Monitor Dashboard** — current source_check_status for all active restaurants, reachability history, broken URL alerts
- **Recanvassing Queue** — restaurants ordered by recanvass urgency, canvasser assignment for recanvass cycles
- **Ingredient Trends** — cross-restaurant ingredient patterns, trending items, dietary pattern shifts over time
- **Restaurant Profile** — full longitudinal view of a single restaurant: every canvass, every menu version, every score history

### OS 5 — Customer Analytics OS

**What it owns:** User-side data. Search patterns. Filter usage. Discovery outcomes.

**Backend modules:**
- **Search Analytics** — top search terms, zero-result searches, filter combination frequency
- **Discovery Reports** — which restaurants are being surfaced, which are being clicked, which filters drive the most engagement
- **Ask GoldPan™ Usage** — query volume, model usage, cost per query, common question types, answer quality signals
- **User Cohort Analysis** — dietary profile distribution of users, retention by dietary category, feature adoption

*Note: Customer Analytics OS depends on Ask GoldPan™ logging architecture, which is not yet implemented. This OS is Phase 4+.*

### OS 6 — AI Usage and Cost OS

**What it owns:** All AI-assisted operations. Token tracking. Model selection. Cost attribution. Quality monitoring.

**Backend modules:**
- **AI Session Log** — every AI-assisted intake session, model used, token count, cost, output quality flags
- **Cost Dashboard** — daily/monthly AI spend by OS module, by model, by operation type
- **Model Performance** — intake packet quality scores over time, hallucination flags, human correction rate
- **Prompt Registry** — versioned prompt templates, A/B test results, prompt performance history
- **Cost Attribution** — cost per restaurant onboarded, cost per dish verified, cost per confirmed conclusion

---

## Database Architecture

### Schema Organization

Supabase schemas separate the three core systems plus operational support:

```
schema: evidence         -- Intake OS tables (Evidence System)
schema: knowledge        -- Governance OS tables (Knowledge System)
schema: operations       -- Lifecycle, audit, users, jobs, reports
schema: analytics        -- Customer Analytics OS, AI Usage OS
schema: public           -- Application output (dishes.json equivalent, API output)
```

The schema separation enforces the Evidence/Knowledge boundary at the database level. No FK from `knowledge.*` to `evidence.*` that would allow Knowledge outputs to be used as Evidence inputs.

### Core Tables by Schema

**`evidence` schema:**
```
evidence.restaurants          -- canonical restaurant entity (see above)
evidence.lifecycle_events     -- append-only audit trail (triggers prevent UPDATE/DELETE)
evidence.dishes               -- one row per dish (primary source of truth)
evidence.ingredients          -- one row per ingredient row per dish
evidence.allergen_disclosures -- restaurant allergen disclosures with full provenance
evidence.menu_sources         -- Menu Source Registry
evidence.source_documents     -- archived PDFs, allergen guides (links to Supabase Storage)
evidence.restaurant_claims    -- restaurant-level dietary/operational claims
evidence.intake_sessions      -- log of intake agent sessions (AI or human)
```

**`knowledge` schema:**
```
knowledge.derived_filters     -- computed filter conclusions per dish
knowledge.transparency_scores -- per-dish transparency scoring
knowledge.filter_registry     -- registered filters, dependency types, rule references
knowledge.pipeline_runs       -- pipeline execution log (StageResult JSON per stage)
knowledge.pipeline_stages     -- individual stage results
knowledge.freshness_state     -- materialized freshness status per restaurant
```

**`operations` schema:**
```
operations.users              -- canvassers, reviewers, admins
operations.roles              -- canvasser / reviewer / coordinator / admin / system
operations.user_roles         -- many-to-many
operations.rules_registry     -- GP-RULE definitions (read-only; updated by migrations)
operations.background_jobs    -- job queue for pipeline triggers, source checks
operations.notifications      -- alert queue (overdue restaurants, pipeline failures)
operations.feature_flags      -- per-restaurant, per-user, or global feature flags
operations.audit_log          -- catch-all audit log for all administrative actions
```

**`public` schema:**
```
public.dishes_json_view       -- materialized view powering the dishes.json endpoint
public.restaurants_view       -- materialized view for restaurant-level public data
```

### Row-Level Security

RLS policies enforce the three-tier authorization model across every table:

```
canvasser:
  - evidence.dishes: SELECT (own restaurant assignments), INSERT (own assignments)
  - evidence.ingredients: SELECT, INSERT (own assignments)
  - evidence.allergen_disclosures: SELECT, INSERT (own assignments)
  - evidence.lifecycle_events: INSERT only (cannot UPDATE or DELETE)
  - knowledge.*: SELECT only

reviewer:
  - All canvasser permissions
  - evidence.dishes: UPDATE (for corrections with provenance)
  - evidence.lifecycle_events: INSERT for review transitions

coordinator:
  - All reviewer permissions
  - evidence.restaurants: INSERT, UPDATE lifecycle fields
  - operations.users: SELECT

admin:
  - Full access to all non-Knowledge tables
  - knowledge.*: SELECT only (Knowledge is pipeline-written, not admin-written)

governance_engine (service role):
  - knowledge.*: INSERT, UPDATE (the only actor that writes Knowledge tables)
  - evidence.*: SELECT only
```

The `governance_engine` service role is used exclusively by the pipeline. No human user is granted this role. The boundary is enforced by the database, not by application code.

---

## API Architecture

### Approach

The backend exposes two API surfaces:

**1. Supabase REST API (auto-generated)** — used directly by the pipeline scripts and internal tooling. Authentication via service-role key (pipeline) or JWT (authenticated users). This is not the public API.

**2. Backend Application API (FastAPI)** — the API layer for the admin UI and any future integrations. Runs in front of Supabase. Handles business logic, workflow orchestration, and the lifecycle-transition approval workflow. Never exposes raw Supabase tables — always returns typed, shaped responses.

**3. Public dishes API (read-only)** — the existing `dishes.json` equivalent, served from the `public` schema materialized views. No authentication required. Rate-limited.

### Key API Endpoints (Backend Application API)

```
# Intake OS
POST   /restaurants                          -- create prospect
PATCH  /restaurants/{id}/lifecycle           -- advance or return lifecycle state (human approval)
GET    /restaurants/{id}/lifecycle-events    -- full audit trail
POST   /restaurants/{id}/dishes             -- create dish record
PATCH  /dishes/{id}                          -- update dish (with provenance required)
POST   /dishes/{id}/ingredients             -- add ingredient row
DELETE /ingredients/{id}                    -- requires actor + reason (soft delete only)
POST   /allergen-disclosures                -- create disclosure with full provenance
GET    /restaurants/{id}/validation-status  -- current validation state

# Governance OS
POST   /pipeline/trigger                     -- trigger pipeline for restaurant(s) or all
GET    /pipeline/runs                        -- pipeline run history
GET    /pipeline/runs/{run_id}               -- full stage results for a run
GET    /rules                                -- all GP-RULEs
GET    /filters                              -- filter registry
GET    /restaurants/{id}/freshness           -- current freshness state

# Business Development OS
GET    /prospects                            -- qualified prospect queue
PATCH  /prospects/{id}/qualify              -- approve coverage (writes coverage_signal)
GET    /coverage-map                         -- geographic coverage data

# Admin
GET    /users                                -- user list
POST   /users                                -- create user
PATCH  /users/{id}/roles                    -- assign/revoke roles
GET    /audit-log                            -- global audit log with filters
GET    /feature-flags                        -- current feature flags
PATCH  /feature-flags/{id}                  -- toggle flag

# AI Usage OS
GET    /ai/sessions                          -- intake session log
GET    /ai/cost-summary                      -- cost by period, model, operation
```

### Versioning

All API routes are prefixed `/api/v1/`. Version is incremented on any breaking change. The pipeline scripts pin to a version and are updated explicitly.

---

## Authentication and Authorization

### Auth Model

Supabase Auth handles user accounts, JWTs, and session management. The backend uses Supabase Auth directly — no separate auth system.

**User types:**
- `canvasser` — evidence acquisition, dish entry, verification
- `reviewer` — verification sign-off, QA review approval
- `coordinator` — canvasser assignments, coverage decisions, lifecycle management
- `admin` — full backend access, user management, feature flags
- `governance_engine` — service account used by pipeline scripts (not a human user)
- `public_api` — anonymous read-only access to public dishes endpoint

**Role assignment:** Roles are stored in `operations.user_roles` and embedded in the JWT claims. The API reads roles from JWT; Supabase RLS reads roles from JWT.

### Lifecycle Transition Approval

A lifecycle transition requires:
1. The actor must have permission for the transition (enforced by RLS + API middleware)
2. The transition must meet the exit gate criteria for the current stage (enforced by API middleware before the Supabase write)
3. A `lifecycle_events` row must be created atomically with the status update (enforced by Postgres trigger)

The API does not allow a lifecycle state change without all three conditions being met. The trigger ensures the audit trail is complete even if the API call fails partway through — the transition either happens completely or not at all.

---

## Audit Logging

### Levels of Audit Logging

**Level 1 — Lifecycle Events (domain audit log)**
Every restaurant lifecycle transition. Append-only table with trigger enforcement. This is the primary operational audit trail. See schema above.

**Level 2 — Evidence Change Log (row-level audit)**
Every INSERT, UPDATE, or soft-DELETE on Evidence tables. Captured by triggers into `operations.audit_log`. Format:

```sql
audit_log_id     uuid PRIMARY KEY
table_name       text
record_id        uuid
operation        text            -- INSERT / UPDATE / DELETE
actor_id         uuid
actor_type       text
old_values       jsonb           -- NULL for INSERT
new_values       jsonb           -- NULL for DELETE
changed_at       timestamptz DEFAULT now()
reason           text            -- required for UPDATE/DELETE on allergen fields
```

Allergen-related updates (ingredient `allergen_flags`, allergen_disclosures rows) require a `reason` field. An UPDATE without a reason is rejected by the trigger.

**Level 3 — Administrative Audit Log**
All admin actions: user creation, role changes, feature flag changes, pipeline triggers. Stored in `operations.audit_log` with `table_name = 'admin'`.

**Level 4 — Pipeline Run Log**
Every pipeline execution with its full StageResult JSON. Stored in `knowledge.pipeline_runs` and `knowledge.pipeline_stages`.

### Retention

Audit logs are never deleted. This is enforced by triggers. Storage is cheap; provenance is expensive to reconstruct.

---

## Report Generation Architecture

Reports are first-class objects — not ad hoc queries.

### Report Types

**Operational Reports** (generated on-demand, cached 1 hour):
- Restaurant pipeline status by lifecycle stage
- Canvasser assignment and throughput
- Overdue recanvassing queue with priority ranking
- Freshness health summary (current / due_soon / overdue / needs_review counts)
- Validation error summary by restaurant

**Quality Reports** (generated weekly or on-demand):
- Filter conclusion distribution (verified / inferred / unknown by filter)
- Evidence Tier distribution across all published restaurants
- Tag_Source audit (restaurant_disclosed vs goldpan_inferred vs blank)
- Allergen disclosure coverage (which allergens are documented, which are unknown)
- Transparency score distribution

**AI Usage Reports** (generated daily):
- Token usage by model, operation type, and date
- Cost per restaurant onboarded
- Intake packet quality scores
- Human correction rate (what percentage of AI-drafted packets required corrections)

**Business Reports** (generated weekly):
- New restaurants added (prospect → published funnel)
- Coverage expansion by neighborhood
- Recanvassing throughput

### Report Execution

Reports are defined as named SQL queries (or Python functions that call Supabase). Every report is versioned. Report outputs are cached in `operations.report_cache` with a timestamp and a cache key. Stale cache is regenerated on the next request.

Reports are not generated inline in the backend UI — they are generated by background jobs and displayed from cache. This prevents slow queries from blocking the UI.

---

## Background Jobs and Scheduled Processes

### Job Queue

Background jobs run via Supabase Edge Functions or a simple Python queue worker (depending on complexity). Every job is logged in `operations.background_jobs`:

```sql
job_id          uuid PRIMARY KEY
job_type        text              -- source_check / recanvass_scan / pipeline_run / report_gen
status          text              -- pending / running / completed / failed
restaurant_id   uuid              -- if restaurant-specific; NULL for global jobs
triggered_by    text              -- schedule / user_action / trigger
triggered_at    timestamptz
started_at      timestamptz
completed_at    timestamptz
error           text
result_summary  jsonb
```

### Scheduled Processes

| Process | Frequency | What it does |
|---|---|---|
| `source_check` | Per restaurant per tier (7/14/30 days) | Checks that registered menu URLs are live and detects content changes. Writes `Source_Check_Status`. |
| `recanvass_scan` | Daily | Scans all published restaurants, recomputes `Recanvass_Status` from `Last_Canvassed` and tier windows, escalates `needs_review` when triggered. |
| `freshness_report` | Daily | Generates the freshness health summary report and sends alerts for `needs_review` restaurants. |
| `pipeline_scheduled` | On-demand or weekly | Runs the full Governance pipeline for all published restaurants. Produces Knowledge System outputs. |
| `report_generation` | Daily/weekly | Pre-generates scheduled reports and populates the cache. |
| `ai_cost_summary` | Daily | Aggregates AI usage from the session log and writes the daily cost summary. |

### Alert System

Alerts are written to `operations.notifications` and surfaced in the backend dashboard. Alert types:
- Restaurant entered `needs_review` (immediate)
- Pipeline run failed (immediate)
- Source check detected change at a high-priority restaurant (immediate)
- Canvasser has restaurants overdue for QA review (daily digest)
- AI cost spike (daily, if >2x previous 7-day average)

---

## Feature Flags

Feature flags control the rollout of new capabilities without code deployments. Stored in `operations.feature_flags`.

### Flag Types

**Global flags** — apply to the entire system:
- `ask_goldpan_beta` — enables the Ask GoldPan™ AI explanation layer in the public interface
- `public_api_v2` — enables v2 of the public dishes endpoint
- `allergen_communication_v2` — enables the new allergen display format (post GP-RULE-016 UI implementation)

**Restaurant-level flags** — apply to a specific restaurant:
- `suppress_from_public` — temporarily removes a restaurant from public output without deactivating it
- `force_recanvass` — overrides `Recanvass_Status` to `needs_review` for a specific restaurant
- `skip_freshness_gate` — for restaurants being actively canvassed (avoids GP-RULE-008 blocking in-progress work)

**User-level flags** — apply to a specific user:
- `ai_intake_beta` — enables AI-assisted intake for canvassers in the beta program
- `advanced_validation` — shows extended validation output in the verification workflow

### Flag Resolution

At runtime, the flag resolution order is: restaurant-level flag > user-level flag > global flag. If no flag is set for a given context, the default (disabled) applies.

---

## Dashboard Architecture

### Primary Dashboards

**Intake Operations Dashboard** (coordinator and admin view):
- Live count: prospects / qualified / onboarding / evidence_acquisition / verification / qa_review
- Restaurants blocked at each stage (flagged for attention)
- Canvasser assignment overview
- Today's lifecycle transitions
- Pipeline stage bottlenecks (where restaurants are accumulating)

**Canvasser Dashboard** (canvasser view):
- Assigned restaurants and their current stage
- Evidence entry progress (dishes entered / dishes in source)
- Validation status (last run result)
- Next required action for each assignment

**QA Review Dashboard** (reviewer view):
- Restaurants awaiting QA review
- Pipeline run status for each restaurant in qa_review
- Filter conclusion summary per restaurant
- Approval/rejection workflow

**Governance Monitor** (admin view):
- Filter conclusion distribution (current snapshot)
- Freshness status overview (all published restaurants)
- Overdue recanvassing queue
- Rules Registry — current rules and their computation counts
- Pipeline run history (last 30 days)

**AI Usage Dashboard** (admin view):
- Daily AI token usage and cost
- Cost trend chart (30 days)
- Session quality flags
- Model usage breakdown

### Dashboard Refresh Strategy

Dashboards pull from pre-computed materialized views and report cache. The Governance Monitor's freshness panel refreshes every 60 seconds via Supabase Realtime subscriptions. All other panels refresh on-demand (page load) or on a 5-minute polling interval.

Supabase Realtime subscriptions are used for two things: freshness status changes (so the monitor updates without a page refresh) and pipeline run status (so the coordinator can watch a pipeline run in real time).

---

## Navigation

The backend is a single-page application with a persistent left sidebar:

```
GoldPan™ OS
├── Intake OS
│   ├── Prospect Queue
│   ├── Restaurant Pipeline
│   ├── Canvasser Assignments
│   ├── Evidence Entry          (canvasser view)
│   ├── Verification Queue
│   └── QA Review Queue
├── Governance OS
│   ├── Pipeline Control
│   ├── Freshness Monitor
│   ├── Rules Registry
│   ├── Filter Registry
│   └── Transparency Scoring
├── Business Development OS
│   ├── Coverage Map
│   ├── Prospect Pipeline
│   └── Restaurant Relationships
├── Restaurant Intelligence OS
│   ├── Menu Change Log
│   ├── Source Monitor
│   └── Recanvassing Queue
├── Reports
│   ├── Operational
│   ├── Quality
│   ├── AI Usage
│   └── Business
├── Administration
│   ├── Users
│   ├── Roles
│   ├── Feature Flags
│   └── Audit Log
└── Settings
```

Canvassers see only: Intake OS (their assignments only) and their own Reports.  
Reviewers see: Intake OS (verification + QA queues) and Reports.  
Coordinators see: all Intake OS, Business Development OS, Reports.  
Admins see: everything.

---

## Deployment Architecture

### Phase 1 Infrastructure (MVP)

```
Supabase (managed PostgreSQL + Auth + Storage + Realtime)
  └── evidence schema
  └── knowledge schema
  └── operations schema

Backend API (FastAPI, Python)
  └── Deployed on Railway or Fly.io
  └── Single process, auto-scaled on demand
  └── Reads/writes Supabase via service-role key
  └── JWT validation for user-facing endpoints

Backend UI (Next.js or React + Vite)
  └── Deployed on Vercel or Cloudflare Pages
  └── Calls Backend API (not Supabase directly)
  └── Auth via Supabase Auth JS client

Pipeline Scripts (existing Python)
  └── Run locally or via scheduled cron on Railway
  └── Migrated from gspread → Supabase REST API
  └── Same logic, different data source

Public Dishes API
  └── Served from Supabase REST API directly
  └── Rate limited via Supabase API gateway
  └── dishes.json still generated as static file for compatibility
```

### Environment Strategy

Three environments:
- `local` — Supabase local dev (docker-compose). All developers run this. Schema migrations are developed and tested here.
- `staging` — Supabase hosted project (separate from production). Pipeline test runs. UI QA.
- `production` — Supabase hosted project. Only promoted migrations touch this.

Migrations are managed with `supabase/migrations/` directory, versioned and applied via `supabase db push`.

---

## Scalability Considerations

GoldPan is currently one person with 700 dishes and 27 restaurants. The architecture must not over-engineer for hypothetical scale, but it must avoid future rewrites.

### What the Current Architecture Handles Without Change

- Thousands of restaurants: the schema handles this. Supabase PostgreSQL scales to millions of rows without architectural changes.
- Multiple canvassers: RLS already supports multi-user access. Adding users is configuration, not architecture.
- Multiple OS modules: each module gets its own dashboard views and API endpoints. Adding a module is additive.
- AI-assisted intake at scale: the `intake_sessions` table captures every session. Cost attribution and quality tracking work regardless of volume.

### What Would Need Architecture Work at Scale

- **Pipeline throughput**: the current pipeline is synchronous (one restaurant at a time). At 100+ restaurants requiring concurrent pipeline runs, the background job system would need a distributed task queue (Celery + Redis, or Temporal). Design for this by keeping the job queue schema in place from Phase 1.
- **Public API caching**: at high traffic, the public dishes endpoint needs a CDN layer (Cloudflare) in front of the materialized views. This is additive — the materialized view stays, a cache sits in front.
- **Real-time source checking**: at thousands of restaurants, the source check schedule needs a distributed crawler. Design for this by keeping source_check as a job type with configurable workers.
- **Multi-city operations**: no schema changes required. City/state fields already on the canonical entity. Coverage map and reporting would need geo-aware queries, but the data model supports this.

### What to Avoid Now That Would Cause Future Rewrites

- Do NOT store derived conclusions as columns on the restaurant or dish record. Knowledge belongs in Knowledge System tables.
- Do NOT build a JSON-blob Evidence table. Individual columns with constraints are harder to build but impossible to query well in blob form.
- Do NOT put business logic in the Supabase triggers beyond audit enforcement and lifecycle event creation. Business logic belongs in the API layer.
- Do NOT use Supabase Edge Functions as the primary compute layer for the governance pipeline. Edge Functions have runtime limits that the governance pipeline will eventually exceed. Keep pipeline as Python scripts calling Supabase REST.

---

## Phased Implementation Plan

Each phase is independently shippable. A phase is complete when its completion criteria pass. No phase skips ahead.

---

### Phase 1 — Supabase Foundation (2–3 weeks)

**Objective:** Establish the Supabase database schema, migrate the canonical restaurant entity and all existing Sheets data, and validate that the pipeline reads from Supabase without regression.

**Database work:**
- Set up Supabase project (use existing dormant account)
- Create `evidence`, `knowledge`, `operations`, `public` schemas
- Write and apply migration for all tables in the canonical restaurant entity, lifecycle_events, dishes, ingredients, allergen_disclosures, menu_sources, and knowledge output tables
- Implement all RLS policies for canvasser / reviewer / coordinator / admin / governance_engine roles
- Implement triggers: lifecycle_events append-only, audit_log for evidence changes, lifecycle_events auto-create on restaurants status change
- Migrate existing Google Sheets data (all 27 restaurants, 700+ dishes, ingredient rows, transparency scores, menu source registry)
- Validate migration: run `validate_database.py` equivalent against Supabase and confirm zero errors

**Pipeline work:**
- Update `pipeline.py` and all stage scripts to read from Supabase REST API instead of gspread
- Confirm pipeline produces identical `dishes.json` output from Supabase as it did from Sheets
- Keep Sheets as read-only backup during migration window (30 days)

**API work:**
- None — pipeline calls Supabase REST directly

**UI work:**
- None — this phase is backend infrastructure only

**Testing:**
- Run full pipeline against Supabase data, compare `dishes.json` output line-by-line with Sheets-produced output
- Confirm all RLS policies behave correctly under each role
- Confirm lifecycle_events trigger fires on every restaurants status change
- Confirm audit_log captures all evidence table writes

**Completion criteria:**
- [ ] All Sheets data migrated to Supabase with no data loss
- [ ] Pipeline produces identical output from Supabase as from Sheets
- [ ] Zero RLS policy violations in role testing
- [ ] Lifecycle_events trigger verified on 5 test transitions
- [ ] 30-day pipeline run period clean (no Supabase-specific failures)
- [ ] Sheets set to read-only

---

### Phase 2 — Intake OS Backend API (3–4 weeks)

**Objective:** Build the Backend Application API for Intake OS workflows. Enable programmatic lifecycle management, evidence entry, and validation triggering via the API.

**Database work:**
- Add `operations.users` and `operations.user_roles`
- Add `operations.background_jobs` job queue table
- Add `operations.notifications` alert table
- Implement Supabase Auth users, sync to `operations.users`

**API work:**
- FastAPI application scaffold (Python)
- Auth middleware (Supabase JWT validation)
- Restaurant CRUD endpoints (POST, PATCH, GET)
- Lifecycle transition endpoint (`PATCH /restaurants/{id}/lifecycle`) with exit gate enforcement
- Dish and ingredient entry endpoints
- Allergen disclosure entry endpoints (with provenance field enforcement)
- Validation trigger endpoint (calls `validate_database.py` equivalent against Supabase)
- Audit log endpoint (GET with filters)

**UI work:**
- None — this phase is API only (the pipeline and any manual API calls use it)

**Testing:**
- Every lifecycle transition tested for exit gate enforcement (e.g., cannot transition to qa_review without validation passing)
- Every allergen disclosure endpoint tested for provenance field completeness
- Role-based access tests for every endpoint
- Audit log verified for every write operation

**Completion criteria:**
- [ ] All Intake OS operations possible via API
- [ ] Lifecycle exit gates enforced on every transition
- [ ] All allergen disclosure writes enforce complete provenance
- [ ] Audit log complete for all API writes
- [ ] API documented (FastAPI auto-generates OpenAPI spec)

---

### Phase 3 — Backend UI: Intake OS (4–5 weeks)

**Objective:** Build the Intake OS UI. Canvassers, reviewers, and coordinators can manage the full restaurant lifecycle from the browser.

**Database work:**
- Add `operations.feature_flags` table
- Implement restaurant-level `skip_freshness_gate` and `suppress_from_public` flags
- Add Supabase Realtime subscription support for pipeline status

**UI work:**
- Authentication (login, logout, role-based navigation)
- Intake Operations Dashboard (coordinator view)
- Canvasser Dashboard (assignment queue, per-restaurant evidence entry progress)
- Restaurant Pipeline view (Kanban or list, filterable by status)
- Lifecycle Timeline (visual audit trail per restaurant)
- Verification Queue (spot-check assignment, source comparison interface)
- QA Review Queue (pipeline trigger, filter conclusion review, approval workflow)
- Restaurant profile view (all evidence, all lifecycle history, all sources)

**Reports:**
- Restaurant pipeline status report (lifecycle stage counts)
- Canvasser throughput report (restaurants per canvasser per period)

**Testing:**
- End-to-end: create prospect → qualify → onboard → evidence_acquisition → verification → qa_review → publish (full lifecycle via UI)
- Role-based UI access tests (canvasser cannot see coordinator views)
- Lifecycle transition UI enforces same exit gates as API

**Completion criteria:**
- [ ] Full restaurant lifecycle manageable via UI
- [ ] All role-based views correct
- [ ] Audit trail populated correctly for all UI-triggered actions
- [ ] Two operational reports available in-app

---

### Phase 4 — Governance OS UI (3–4 weeks)

**Objective:** Build the Governance OS UI. Pipeline control, freshness monitoring, rules and filter registry views.

**Database work:**
- Implement Supabase Realtime subscriptions for pipeline run status
- Implement materialized view refresh on pipeline completion

**UI work:**
- Pipeline Control Center (trigger runs, watch real-time stage progress, view run history)
- Freshness Monitor (live dashboard with overdue counts, needs_review alerts)
- Rules Registry view (all GP-RULEs, version history, current computation counts)
- Filter Registry view (all registered filters, dependency types, which rules they apply)
- Transparency Scoring UI (per-dish scoring, batch scoring, score distribution)

**Reports:**
- Filter conclusion distribution report
- Freshness health summary report
- Transparency score distribution report

**Testing:**
- Pipeline run triggers via UI and confirms correct StageResult output
- Freshness monitor updates in real-time when recanvass_scan job runs
- Rules Registry shows correct current version for all 16 GP-RULEs

**Completion criteria:**
- [ ] Pipeline triggerable and monitorable from UI
- [ ] Freshness Monitor live-updating via Supabase Realtime
- [ ] Rules Registry and Filter Registry complete and accurate
- [ ] Three governance reports available in-app

---

### Phase 5 — Business Development OS and Restaurant Intelligence OS (3–4 weeks)

**Objective:** Build the BD and Intelligence OS modules.

**Database work:**
- Add `operations.restaurant_contacts` (relationship log)
- Add `knowledge.menu_snapshots` (version-controlled dish snapshots for change detection)

**UI work:**
- Coverage Map (geographic view of published restaurants and coverage gaps)
- Prospect Pipeline (filterable Kanban by lifecycle stage, neighborhood, coverage signal)
- Restaurant Relationship Log (contacts, confirmation requests, allergen guide requests)
- Source Monitor Dashboard (source check status for all active restaurants, broken URL alerts)
- Recanvassing Queue (overdue + needs_review restaurants, canvasser assignment)
- Menu Change Log (detected changes per restaurant, version comparison)

**Reports:**
- Coverage expansion report (new restaurants added per period, coverage by neighborhood)
- Source health report (URL reachability, broken sources by restaurant)

**Completion criteria:**
- [ ] Coverage Map rendering all published restaurants
- [ ] Prospect Pipeline showing all restaurants with correct lifecycle status
- [ ] Source Monitor alerting on unreachable URLs
- [ ] Recanvassing Queue accurate and sortable by urgency

---

### Phase 6 — AI Usage OS and Cost Dashboard (2–3 weeks)

**Objective:** Full AI usage visibility. Cost tracking, model performance, prompt registry.

**Database work:**
- Add `analytics.ai_sessions` (intake session log with token counts)
- Add `analytics.prompt_registry` (versioned prompt templates)
- Add `analytics.ai_cost_daily` (materialized daily cost rollup)

**UI work:**
- AI Session Log (every intake session, model, tokens, cost, quality flags)
- Cost Dashboard (daily/monthly spend by model and operation, 30-day trend chart)
- Model Performance view (quality scores over time, correction rate)
- Prompt Registry (versioned prompts, A/B comparison, performance history)

**Reports:**
- Daily AI cost report
- Weekly AI usage summary

**Completion criteria:**
- [ ] Every AI intake session logged with full token and cost data
- [ ] Cost dashboard accurate against actual Anthropic billing (within 5%)
- [ ] Prompt Registry shows current prompt versions for all operations

---

### Phase 7 — Customer Analytics OS (4+ weeks, dependent on Ask GoldPan™ logging)

**Objective:** User-side analytics. Search pattern visibility, filter usage, discovery outcomes.

*This phase depends on Ask GoldPan™ having a logging architecture in place (search queries, filter selections, restaurant clicks). It is deferred until Phase 6 is complete and Ask GoldPan™ is in active use.*

**Completion criteria defined in Phase 7 planning, post-Phase 6.**

---

## What Is Explicitly Out of Scope

The following are not in scope for this backend:

- Customer-facing UI (the Ask GoldPan™ app, the restaurant search interface) — this is a separate product surface, not a backend module
- Direct menu scraping or automated menu ingestion — the backend manages the pipeline but does not scrape menus autonomously
- Dietary reasoning logic — Governance rules are defined in code (Rules Registry), not in the backend UI. Changing a GP-RULE is a code commit, not an admin action
- Allergen guide PDF parsing — the backend can store and display PDFs (via Supabase Storage), but parsing is a pipeline operation

---

## Summary

The GoldPan backend is the operational control center for a pipeline that runs from prospect identification to published restaurant data. Its job is to make that pipeline visible, manageable, and auditable.

The architecture recommendation is direct migration to Supabase as the Phase 1 source of truth. The phased plan begins with infrastructure (schema + migration), advances to API (Intake OS), then to UI (Intake OS → Governance OS → BD/Intelligence → AI/Cost), and defers Customer Analytics until Ask GoldPan™ has a logging foundation.

Every architectural decision in this document derives from the governing principles already in place: evidence is evidence, knowledge is knowledge, humans are accountable, AI never writes to production, and the audit trail is non-negotiable.
