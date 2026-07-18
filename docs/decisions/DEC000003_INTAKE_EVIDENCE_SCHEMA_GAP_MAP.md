# DEC000003 groundwork — Intake Evidence Schema Gap Map

**Status (updated 2026-07-18): SUPPORTING DOCUMENT — not itself the Decision
Record.** The canonical DEC000003 Decision Record is
`docs/decisions/DEC000003_CANONICAL_INTAKE_EVIDENCE_INGESTION_ARCHITECTURE.md`
(Founder-approved 2026-07-16, formalized as a standalone canonical record
2026-07-18). Cite that record as governing policy for the six §13 decisions
below, the DEC000001 §5.7 interpretation (§9), the Evidence Disposition
mechanism (§9a), and the reopen/existing-packet-remediation invariants
(§9b, §11) — this document did not change substantively in that
formalization and remains the authoritative technical reference for the
schema-gap analysis (§1-§8), the proposed migration-020 design (§8), the
upstream Intake-model remediation map (§10), the sequencing plan (§12), and
non-blocking technical debt (§14), none of which the canonical record
duplicates. No migration in this document has been executed.

Produced during Task #46 grounding, per Brad's directive to stop and produce a
precise gap map before writing `intake.packet.commit_ingest`, rather than let
approved evidence silently fail to persist or fall back to Google Sheets.

**2026-07-16 update:** Brad has ruled on the §9 open question (original
draft below revised accordingly): DEC000001 §5.7's "durable write succeeds"
criterion is **not** amended. `commit_ingest` must hold the strict reading —
every approved, ingestion-bound evidence element must be durably and
faithfully persisted, or the packet stays `approved` and no `ingested`
transition occurs. No `partially_ingested` state. Allergen disclosures
missing `disclosure_status`/`scope` are a genuine upstream Intake-model gap,
not something `commit_ingest` can route around — see the new §9 and §10
below.

**2026-07-16 Founder review session — all six §13 blocking decisions
resolved.** Presented one at a time in priority order (§13.6, §13.4, §13.2,
§13.5, §13.1, §13.3); each ruling is recorded in §13, with the substantive
redesigns reflected throughout §9-§12 (notably the new Evidence Disposition
mechanism at §9a and the approved-packet reopen workflow at §9b). See §13
for the full ledger and the Summary for a condensed version. No SQL, code,
or migration was written or executed during this review; no governing
document besides this one was edited; nothing has been committed or pushed.

Scope: every field in an approved Intake Packet (`operations.intake_packets.packet_data`)
that has **no faithful destination** in the current `evidence.*` Postgres schema
(`supabase/migrations/002_evidence_tables.sql`), based on the actual JSON template
in `intake_agent.py`'s `_output_schema_instructions()` and two real packet samples
(`intake_packets/good_health_to_be_hail_2026-07-09.json`,
`..._2026-07-04.json`). Where the actual agent output and
`docs/INTAKE_AGENT_STANDARD.md` disagree, the actual code/output governs this
gap map, and the drift is noted separately (see §7).

---

## 1. `dish.verbatim_components[]`

1. **Packet path / field name**: `dishes[].verbatim_components[]`, each entry
   `{verbatim_text, ingredient_source, resolution_status}`.
2. **Meaning and provenance**: raw menu/source text for a dish component the
   agent could not confidently resolve into a structured `ingredients[]` entry
   (e.g. an unbroken phrase like "salad dressing"). `resolution_status` is
   observed as always `"unresolved"` — nothing downstream ever resolves it.
3. **Intended owning OS**: Intake / Evidence System — this is raw canvassed
   evidence, not a Knowledge conclusion.
4. **Current target table**: none. `ingest_packet.py`'s `collect_unsupported()`
   already flags this as having no Sheets destination; there is no `evidence.*`
   table either.
5. **Exact missing column/table/relationship**: no table exists at all.
6. **Required for faithful ingestion?**: yes, if the packet contains any
   entries — dropping it silently loses canvassed evidence that a human
   reviewer already approved as part of the packet.
7. **Recommended schema addition**: new table
   `evidence.dish_verbatim_components` (see §8, item 2).
8. **Backfill/migration implications**: none — this data was never persisted
   anywhere before, so there is nothing to backfill. Purely additive.
9. **API/UI implications**: none required for commit_ingest itself. A future
   Evidence System UI could surface unresolved components for manual
   resolution, but that's out of Task #46 scope.
10. **Governing-document clarification needed?**: no — this is a pure schema
    gap, not a semantics question.

---

## 2. `restaurant.restaurant_claims[].scope`

1. **Packet path / field name**: `restaurant.restaurant_claims[].scope`, one
   of `dish_level | menu_section_level | restaurant_level | ownership |
   sourcing | health_positioning | operational`.
2. **Meaning and provenance**: the claim's applicability scope, set by the
   agent from context (e.g. "we are a vegan restaurant" = `ownership`;
   "gluten-free menu section" = `menu_section_level`).
3. **Intended owning OS**: Evidence System.
4. **Current target table**: `evidence.restaurant_claims` exists and is the
   correct table, but has no `scope` column.
5. **Exact missing column/table/relationship**: `evidence.restaurant_claims.scope`
   does not exist. Related: `claim_type` (existing nullable column) has **no**
   packet source at all today — `ingest_packet.py`'s `build_claims_rows()`
   currently *derives* `claim_type` from `scope` via a lookup table that only
   covers 4 of the 7 enum values (`ownership/sourcing/health_positioning/operational`
   map 1:1; the three `*_level` values can't be inferred and are left blank
   with a warning). That derivation logic is lossy and packet-external — it
   belongs in the ingestion step, not the schema, and should stay optional/
   best-effort even after `scope` is added.
6. **Required for faithful ingestion?**: yes — without it, the claim's
   applicability (is this a restaurant-wide claim or dish-specific?) is lost,
   which materially changes how the claim can be used downstream.
7. **Recommended schema addition**: `ALTER TABLE evidence.restaurant_claims
   ADD COLUMN scope text CHECK (scope IN ('dish_level','menu_section_level',
   'restaurant_level','ownership','sourcing','health_positioning','operational'))`.
   Store the raw packet value verbatim — do not collapse it into `claim_type`.
8. **Backfill/migration implications**: `evidence.restaurant_claims` is
   currently empty (confirmed — no code has ever written to it; `migrate_sheets_to_supabase.py`
   does not read the "Restaurant Claims" tab). Zero backfill risk.
9. **API/UI implications**: none for commit_ingest. Any future claims-review
   UI would want to filter/group by `scope`.
10. **Governing-document clarification needed?**: no.

---

## 3. `restaurant.source_inventory[]`

1. **Packet path / field name**: `restaurant.source_inventory[]`, each entry
   `{source_type, url}` where `source_type` is one of the `APPROVED_SOURCES`
   values (`menu, website, allergen_guide, nutrition_document,
   ordering_platform, restaurant_qa, restaurant_confirmation, pdf`).
2. **Meaning and provenance**: the list of source URLs the agent actually
   drew from during this canvassing run — the provenance record for the
   whole packet.
3. **Intended owning OS**: Evidence System.
4. **Current target table**: closest fit is `evidence.menu_sources`, but it
   is structurally the wrong shape for this data (see below).
5. **Exact missing column/table/relationship**: `evidence.menu_sources` has a
   `UNIQUE (restaurant_id)` constraint (migration 008) — **one row per
   restaurant**, with fixed single-valued columns per source type
   (`official_website, official_menu_url, online_ordering_url, pdf_menu_url,
   allergen_nutrition_url`). `source_inventory[]` is an unbounded list that
   can contain multiple entries of the same `source_type` across canvassing
   runs, and includes `source_type` values (`restaurant_qa`,
   `restaurant_confirmation`) that have no corresponding URL column at all.
   Migration 008's own comment anticipates this exact conflict: *"If GoldPan
   later tracks multiple source records per restaurant... drop this
   constraint and replace it with a compound unique index... File a
   migration to handle existing data before making that change."*
6. **Required for faithful ingestion?**: yes — this is the packet's source
   provenance record; dropping it removes the ability to trace which URL
   backed which piece of evidence.
7. **Recommended schema addition**: new table
   `evidence.restaurant_source_inventory` (see §8, item 3) rather than
   overloading `menu_sources`. Leaves `menu_sources`'s existing one-row-per-
   restaurant model and its `UNIQUE(restaurant_id)` constraint untouched —
   no risk to the existing (unused-by-Intake, but potentially used
   elsewhere) `menu_sources` write path.
8. **Backfill/migration implications**: none — nothing currently populates
   this data anywhere. Purely additive.
9. **API/UI implications**: none required for commit_ingest.
10. **Governing-document clarification needed?**: no.

---

## 4. `dish.restaurant_calorie_content` sub-fields (`unit`, `source_url`, `ingredient_source`, `notes`)

1. **Packet path / field name**: `dishes[].restaurant_calorie_content`, an
   object `{value, unit, source_text, source_url, ingredient_source, notes}`.
2. **Meaning and provenance**: calorie disclosure for the dish, with its own
   independent provenance (`ingredient_source`, `source_url`) distinct from
   the dish's other ingredient provenance.
3. **Intended owning OS**: Evidence System.
4. **Current target table**: `evidence.dishes` — but only 2 of 6 sub-fields
   have columns.
5. **Exact missing column/table/relationship**: `evidence.dishes` has
   `calorie_value` and `calorie_source_text` only. `unit`, `source_url`,
   `ingredient_source`, `notes` have no columns.
6. **Required for faithful ingestion?**: yes for `unit` (a bare numeric value
   without its unit is ambiguous/unsafe for a food-safety-adjacent product)
   and `ingredient_source` (provenance is a first-class requirement
   everywhere else in this schema, per GP-RULE-011). `source_url` and
   `notes` are lower-severity but still packet content a reviewer approved.
   **Founder clarification (2026-07-16, Decision 6):** calories are
   optional evidence, not a required property of every dish. Many dishes
   legitimately have no public calorie information. "Required for faithful
   ingestion" means *if a calorie object is present in the approved
   packet, it must be persisted faithfully* — it does not mean every dish
   must have one. A dish with no approved `restaurant_calorie_content`
   object must ingest successfully with all seven calorie fields (listed in
   point 7 below) left null. Absence of calorie information must never
   block packet approval or `commit_ingest`, and `commit_ingest` must never
   infer, estimate, or fabricate a calorie value through this path.
   Restaurant-published calorie data persisted here must remain a distinct
   record from any future GoldPan-estimated calorie model — the two are not
   to be conflated in this or any downstream table.
7. **Recommended schema addition**: `ALTER TABLE evidence.dishes ADD COLUMN
   calorie_unit text, ADD COLUMN calorie_source_url text, ADD COLUMN
   calorie_ingredient_source text, ADD COLUMN calorie_notes text` — same
   naming pattern as the two existing calorie columns. **Per Decision 6
   (2026-07-16), also add** `ADD COLUMN calorie_raw_fragment jsonb` — a
   defensive fidelity copy of the exact approved `restaurant_calorie_content`
   object, populated only when one exists, guarding against future agent
   output including additional keys, alternate key names, or nested
   structure the six named/existing columns don't represent. All seven
   calorie-related columns on `evidence.dishes` (`calorie_value`,
   `calorie_source_text`, `calorie_unit`, `calorie_source_url`,
   `calorie_ingredient_source`, `calorie_notes`, `calorie_raw_fragment`)
   are nullable, with no CHECK or NOT NULL constraint tying them to each
   other or to any other dish field. The four/five named columns remain the
   canonical, queryable representation; `calorie_raw_fragment` is a
   fidelity/drift safeguard, not a second source of truth, and never
   overrides the named fields. The packet itself and
   `intake_packet_revisions` remain the authoritative historical source
   regardless of what's captured here.
8. **Backfill/migration implications**: existing `evidence.dishes` rows
   (from `migrate_sheets_to_supabase.py`) would have these new columns NULL;
   no destructive change, no backfill required, just permanently-incomplete
   history for pre-existing rows migrated from Sheets (which never had this
   substructure captured either).
9. **API/UI implications**: none required for commit_ingest. `commit_ingest`
   must populate `calorie_raw_fragment` with the exact approved calorie
   object when one exists in `packet_data`, and leave all seven calorie
   columns null when no calorie object exists for that dish — no dish is
   required to populate them.
10. **Governing-document clarification needed?**: no.

---

## 5. `dish.allergen_disclosures[].disclosure_status`

1. **Packet path / field name**: `dishes[].allergen_disclosures[].disclosure_status`
   — **does not exist in the packet at all.** The packet only has `{allergen,
   statement, ingredient_source, source_text}`.
2. **Meaning and provenance**: intended to be one of `contains | may_contain |
   free_from` per `evidence.allergen_disclosures`'s existing `NOT NULL CHECK`
   constraint. This is a *classification* of the free-text `statement` the
   agent captured (e.g. "Contains some soy oil" → `contains`), not something
   the agent currently produces.
3. **Intended owning OS**: Evidence System, but the classification step is
   explicitly human-judgment (per `ingest_packet.py`'s own comment: *"requires
   human judgment"*) — not something `intake_agent.py` is asked to infer today.
4. **Current target table**: `evidence.allergen_disclosures` — **this table
   already has the correct column.** This is not a schema gap.
5. **Exact missing column/table/relationship**: none on the DB side. The gap
   is entirely upstream — no step in intake or review currently captures
   this value for any disclosure, ever.
6. **Required for faithful ingestion?**: yes, structurally — the column is
   `NOT NULL`, so no row can be inserted without it. Per Brad's ruling
   (2026-07-16), this is now absolute: `commit_ingest` must **fail** rather
   than skip or infer when this is missing. See §9.
7. **Recommended schema addition**: **none.** Adding a schema element doesn't
   fix a missing input. What's actually missing is a data-capture step —
   see §10, the upstream Intake Packet remediation scope. Do not infer or
   default a value for this field under any circumstances.
8. **Backfill/migration implications**: N/A — no `evidence.*` schema change
   proposed for this item. See §10 for the separate remediation this
   requires in the Intake Packet schema, the intake agent, and the review
   workflow — and §9 for how already-`approved` packets with this gap are
   handled.
9. **API/UI implications**: significant — this is not a `commit_ingest`-only
   fix. See §10 for the exact surfaces (agent prompt/template, approve-RPC
   precondition, API models, Intake OS review UI) that must change.
10. **Governing-document clarification needed?**: resolved — see §9. No
    amendment to DEC000001 §5.7. The gap is upstream of ingestion, not a
    definition-of-success question.

---

## 6. `dish.allergen_disclosures[].scope`

Same analysis as §5, for the disclosure's `scope` (`dish | restaurant`) —
`evidence.allergen_disclosures.scope` is `NOT NULL` and already the correct
column, and the packet never populates a source value for it. Per Brad's
ruling (2026-07-16): **do not** default `scope='dish'` from packet nesting,
even though a dish-level disclosure being nested under a specific dish might
seem to imply it. Whether a disclosure is meant to generalize to the whole
restaurant is a real judgment call the packet doesn't currently record, and
`commit_ingest` must not infer it. See §9 and §10.

---

## 7. `dish.modifiers[]` — structural loss (bonus item, not explicitly listed but meets "any other field without a faithful destination")

1. **Packet path / field name**: `dishes[].modifiers[]`. Real packets use
   **inconsistent keys** within the same packet: some entries
   `{name, upcharge, description}`, others `{modifier_name,
   modifier_description, options[]}`.
2. **Meaning and provenance**: dish customization options (extra toppings,
   size upgrades, swaps) with associated price deltas.
3. **Intended owning OS**: Evidence System.
4. **Current target table**: `evidence.dishes.dietary_options` (text) — via
   `ingest_packet.py`'s `_modifiers_to_str()` flattening function.
5. **Exact missing column/table/relationship**: no structured table exists;
   the single `dietary_options` text column collapses name/description/
   options/upcharge into one string. Additionally, `_modifiers_to_str()`
   only reads the `modifier_name`/`modifier_price`/`modifier_description`
   key variant — it silently produces **blank output** for the `name`/
   `upcharge` variant that real packets also use (confirmed in the
   "Two Wraps" modifier example in the 07-09 sample). This is a pre-existing
   bug in the Sheets pipeline, not something introduced by this analysis.
6. **Required for faithful ingestion?**: borderline — modifiers are lower
   safety-relevance than allergen/ingredient data, but the existing
   flattening is provably lossy (structure) and buggy (silently blank for
   one observed key variant), which is worse than "no destination."
7. **Recommended schema addition**: new table `evidence.dish_modifiers` (see
   §8, item 5), storing a `raw_packet_fragment jsonb` verbatim copy of each
   modifier object alongside best-effort structured fields — this makes the
   record resilient to the same kind of key-naming drift already observed
   between packet versions, and eliminates the blank-output bug because
   nothing needs to be pre-parsed to avoid data loss.
8. **Backfill/migration implications**: none — purely additive; existing
   `dietary_options` text column can remain as a derived/rendered summary
   for backward read compatibility if anything currently depends on it (needs
   confirmation — no current API code was found reading it beyond display).
9. **API/UI implications**: none required for commit_ingest.
10. **Governing-document clarification needed?**: no.

---

## Not a gap — noted for clarity

**`restaurant.reviewer_status`** (`pending_review | approved | returned |
rejected`, packet-JSON-level field read by `ingest_packet.py`'s legacy
`validate_packet()`) has no `evidence.restaurants` column, and **should not
get one.** It is workflow state that already lives correctly in
`operations.intake_packets.packet_status` (DEC000001's canonical state
machine). `evidence.restaurants.lifecycle_status` is a different, unrelated
state machine (prospect → published → ...). Conflating the two by adding a
column would violate the Evidence/workflow separation this schema already
correctly maintains. No action recommended.

---

## 8. Proposed schema-extension migration (design only — not created, not executed)

Working title: `020_intake_evidence_schema_extension.sql`. Addresses items
1–4 and 7 above. Deliberately does **not** attempt to address items 5–6
(allergen disclosure classification) — see §9.

1. `ALTER TABLE evidence.restaurant_claims ADD COLUMN scope text CHECK
   (scope IN ('dish_level','menu_section_level','restaurant_level',
   'ownership','sourcing','health_positioning','operational'))`.

2. `CREATE TABLE evidence.dish_verbatim_components (verbatim_component_id
   uuid PK, dish_id uuid NOT NULL FK evidence.dishes, dish_external_id text
   NOT NULL, restaurant_id uuid NOT NULL FK evidence.restaurants,
   restaurant_external_id text NOT NULL, verbatim_text text NOT NULL,
   ingredient_source text, resolution_status text NOT NULL DEFAULT
   'unresolved' CHECK (resolution_status IN ('unresolved','resolved')),
   created_at timestamptz NOT NULL DEFAULT now())`.

3. `CREATE TABLE evidence.restaurant_source_inventory (source_inventory_id
   uuid PK, restaurant_id uuid NOT NULL FK evidence.restaurants,
   restaurant_external_id text NOT NULL, source_type text NOT NULL CHECK
   (source_type IN ('menu','website','allergen_guide','nutrition_document',
   'ordering_platform','restaurant_qa','restaurant_confirmation','pdf')),
   url text NOT NULL, source_packet_id uuid REFERENCES
   operations.intake_packets(packet_id), captured_at timestamptz NOT NULL
   DEFAULT now())`. Deliberately separate from `evidence.menu_sources` — see
   item 3's rationale above.

4. `ALTER TABLE evidence.dishes ADD COLUMN calorie_unit text, ADD COLUMN
   calorie_source_url text, ADD COLUMN calorie_ingredient_source text, ADD
   COLUMN calorie_notes text, ADD COLUMN calorie_raw_fragment jsonb`. All
   seven calorie-related columns (including the two pre-existing
   `calorie_value`/`calorie_source_text`) are nullable with no cross-column
   requirement — a dish with no approved calorie evidence ingests with all
   seven null. `calorie_raw_fragment` is a defensive fidelity copy of the
   exact approved `restaurant_calorie_content` object (populated by
   `commit_ingest` only when one exists), not a canonical field and never a
   substitute for the named columns. Per Decision 6 (2026-07-16).

5. `CREATE TABLE evidence.dish_modifiers (modifier_id uuid PK, dish_id uuid
   NOT NULL FK evidence.dishes, dish_external_id text NOT NULL,
   restaurant_id uuid NOT NULL FK evidence.restaurants,
   restaurant_external_id text NOT NULL, modifier_name text,
   modifier_description text, upcharge text, options jsonb,
   raw_packet_fragment jsonb NOT NULL, created_at timestamptz NOT NULL
   DEFAULT now())`.

All five changes are additive (new columns nullable, new tables), so they
carry no risk to existing rows or existing read paths. None of the existing
Sheets-pipeline or `migrate_sheets_to_supabase.py` code needs to change for
this migration to be safe to apply — but note per your standing rule, **this
migration must not be executed until you've reviewed it**, and it hasn't
been written as an actual `.sql` file yet — this is a design proposal only.

---

## 9. DEC000001 §5.7 semantics — resolved, strict reading holds

**Ruling (Brad, 2026-07-16): DEC000001 §5.7 is not amended.** The original
draft of this section presented two options and recommended relaxing §5.7
to a per-evidence-category success definition. That recommendation is
rejected. The governing rule is now explicit and absolute:

> A packet may reach `ingested` only when every approved, ingestion-bound
> evidence element has been durably and faithfully persisted in its
> canonical Postgres destination. There is no category-level exception, no
> skip-and-log path to `ingested`, and no `partially_ingested` state.

This means allergen disclosures are not a `commit_ingest` design problem to
solve — they're a **precondition failure** `commit_ingest` must detect and
refuse to proceed past. Required behavior, to build into `commit_ingest`
once Task #46 resumes:

- **Do not infer or default** `disclosure_status` or `scope` under any
  circumstances (no defaulting `scope='dish'` from nesting, no defaulting
  `disclosure_status` from statement text heuristics).
- **Do not skip** the affected disclosure rows and mark the packet
  `ingested` anyway.
- **Do not introduce** a `partially_ingested` or equivalent intermediate
  status.
- **Scope of the precondition — Founder clarification (2026-07-16):** this
  precondition evaluates only allergen-disclosure entries that actually
  exist in `packet_data`. It is not a completeness requirement over dishes.
  - A dish with zero `allergen_disclosures[]` entries has no allergen-
    disclosure validation requirement at all — absence of a disclosure is
    never itself a blocking condition.
  - A packet with zero allergen disclosures anywhere passes this
    precondition automatically.
  - A present disclosure passes if it has a valid `disclosure_status` and
    `scope` (per the CHECK constraints already on
    `evidence.allergen_disclosures`).
  - A present disclosure also passes if it instead carries an **approved
    Evidence Disposition** (see §10a) that removes it from the ingestion-
    bound set — governance has determined it is not suitable for canonical
    evidence, not that it was deleted from the packet (see §9a).
  - Only a present disclosure that is **neither** validly classified **nor**
    validly dispositioned blocks approval/ingestion.
- When an approved packet contains any `allergen_disclosures[]` entry that
  is present, unclassified, and undispositioned, `commit_ingest` must **fail
  the whole call** with an explicit structured precondition error using
  SQLSTATE `GP422` — confirmed (Decision 5, 2026-07-16) as a reuse of the
  existing validation/content-failure category already established across
  migrations 017-019 (`GP403` authorization, `GP404` not found, `GP409`
  state conflict, `GP422` validation/content failure), not a newly minted
  code — and leave the packet at `packet_status = 'approved'` — unchanged,
  not rolled forward, not rolled back to something else.
- The error/result must identify, per affected packet:
  - `evidence_type: "allergen_disclosure"`
  - `missing_fields`: which of `disclosure_status`/`scope` (or both) are
    absent, per record
  - affected dish or restaurant context (dish external ID + name, or
    restaurant-level if `dish_id` is absent in the packet entry)
  - `blocked_count`: how many disclosure records are blocked — counting
    only present, unclassified-and-undispositioned entries; dishes without
    any disclosure entries are never counted, listed, or referenced as a
    cause of this failure
  - `corrective_action_required`: a human-readable pointer to the
    remediation path (§10) — i.e., the packet must be corrected via
    disclosure classification, an Evidence Disposition (§9a), or (if
    `packet_data` itself must change) a governed reopen (§9b), before
    `commit_ingest` can be retried
- Because `packet_status` never changes on this failure path, this is not a
  transactional-rollback scenario in the migrations-017-019 sense (nothing
  was written that needs undoing) — it's a **precondition check that runs
  before any durable evidence write begins**, symmetrical with the existing
  `approved`/`archived`/`already-ingested` precondition checks already
  specified for `commit_ingest` in Task #46's original instructions.

This closes the semantics question. It does **not** unblock Task #46 by
itself — see §10 and the Summary below for what still has to happen first.

---

## 9a. Evidence Disposition mechanism (Decision 1, 2026-07-16)

**Ruling:** rejected the original Option A (silently drop unclassifiable
disclosures via `edit_payload`) and Option B (force every disclosure into
one of the three CHECK values) on governance-semantics grounds. Editing
evidence and determining the disposition of evidence are different
governance actions and must remain distinct. Redesigned around an explicit,
extensible **Evidence Disposition** concept:

- **Captured evidence is never silently removed.** A disclosure that enters
  an approved packet stays in `packet_data` and in the audit history
  regardless of what happens next.
- A reviewer (or, per §11, an authorized administrator under the b1 path)
  may determine that a captured disclosure is **not suitable for canonical
  evidence**. This determination is a governed act, not a data edit.
- Every disposition must be recorded with: the acting `actor_id`/
  `actor_type`, the authority basis for the action, a timestamp, and a
  **required, non-blank reason**. No disposition may be entered without a
  reason.
- `commit_ingest` (§9) treats a validly-dispositioned disclosure the same
  way it treats a validly-classified one for precondition purposes: it is
  excluded from the ingestion-bound set because governance decided it
  shouldn't ingest — not because it was deleted from history.
- The original captured disclosure (`statement`, `source_text`, etc.) is
  preserved unchanged for historical and audit purposes, exactly as
  captured.
- **Extensibility (Founder refinement, 2026-07-16):** the mechanism is not
  defined around a single permanent value. Today's implementation may only
  require one disposition value (`excluded`), but the model must not assume
  that will always be the only valid disposition — the schema/enum for
  disposition values must be designed to accept future values without a
  structural rework.

**Integration with DEC000001 and the Intake lifecycle:** Evidence
Disposition is a new, narrow governance action scoped to captured evidence
within a packet — it does not change `packet_status`, does not create a new
Intake Packet lifecycle state, and does not touch DEC000001's state machine
(§5.1-§5.9) directly. It is closest in kind to DEC000001 §5.8's append-only
audit stores (`intake_packet_revisions`, `operations.intake_packet_events`)
— a disposition record is itself an auditable event, not a packet mutation.

**Record-type determination:** this requires **only changes to DEC000003**
(and its eventual implementation), not a DEC000001 amendment and not a new
standalone Decision Record. It does not redefine `approved` or `ingested`,
does not add a state to the packet state machine, and does not alter any
mutation-rights table entry — it adds a new, disposition-specific audit
record type alongside the existing ones.

**Minimum additional scope this implies** (design only — nothing built):
- **Schema**: a new disposition table (working name
  `evidence.allergen_disclosure_dispositions` or an
  `operations.intake_evidence_dispositions` table scoped to be reusable
  beyond allergen disclosures) with columns for the disclosure/record
  reference, `disposition_value` (extensible — text or a lookup table, not
  a hardcoded boolean), `actor_id`, `actor_type`, `authority_basis`,
  `reason` (`NOT NULL`, non-blank enforced), and `created_at`. Exact shape
  is implementation, not policy, and is not being decided here.
- **API**: a new endpoint/RPC to record a disposition, distinct from
  `edit_payload`, with its own authorization and validation.
- **Audit**: a disposition is itself a new `intake_packet_events` event
  type (or a sibling append-only store) — not folded into an existing
  event type, per DEC000001 §5.8's enumerated-event-type pattern.
- **UI**: a reviewer-facing control to view a disclosure and enter a
  disposition with a reason — scoped narrowly per Decision 3 (§10 item 5).

---

## 9b. Reopen workflow for approved packets (Decision 2, 2026-07-16)

**Ruling:** an approved packet may not be edited silently or in place. The
governing invariant is: **any change to approved `packet_data` requires a
formal reopen workflow with complete audit history.** Evidence Disposition
backfill (§9a, applied to already-`approved` packets per §11's b1 path) does
**not** require reopening, because it does not change `packet_data` — it
only adds a disposition record. Any remediation that *does* require
changing `packet_data` on an already-`approved` packet must use a governed
`intake.packet.reopen` command instead of a direct administrative edit.

Requirements for that command, as ruled:
- Preserves the original approval and its full audit history — reopening
  does not erase or overwrite the record that the packet was once approved.
- Requires a non-blank reason, an authorized actor, and is recorded as its
  own distinct `intake_packet_events` event type.
- After reopen, the packet returns to an editable/reviewable lifecycle
  state and must pass through ordinary review and approval again — reopen
  is not a shortcut back to `approved`.

**Explicitly out of scope for DEC000003:** per instruction, `reopen` is
**not defined inside this document.** DEC000001 line 38 already flags
`intake.packet.reopen` (CMD000010) as "reserved and undefined," and DEC000001
§5.9 states that reversing an approved packet "must be proposed as its own,
separately governed, elevated action." This ruling confirms that
`intake.packet.reopen` is the intended vehicle for that separate governance
work, but its full design (guardrails, role requirements, exact transition
semantics) is anticipated future work, not something this decision record
resolves. Nothing here should be read as `reopen`'s governing specification.

---

## 10. Upstream Intake Packet remediation scope for allergen disclosures

This is **not** solved by extending `evidence.allergen_disclosures` —
confirmed by re-reading `002_evidence_tables.sql`: the table already has
the correct `disclosure_status` (`NOT NULL CHECK IN
('contains','may_contain','free_from')`) and `scope` (`NOT NULL CHECK IN
('dish','restaurant')`) columns. The gap is entirely upstream of the
evidence schema — in the packet itself, and in every surface between packet
creation and packet approval. Confirmed by direct inspection of the actual
code (not assumed):

1. **Intake Packet schema (`intake_agent.py`)** — `_output_schema_instructions()`,
   line 475: the `allergen_disclosures` field in the per-dish JSON template
   is currently a bare `"allergen_disclosures": []` with no example object
   shape at all (unlike sibling fields `ingredients` and
   `verbatim_components`, which both show full example objects). There is
   also no "Dish-level field rules" prose entry for `allergen_disclosures`
   in the rules block (lines 513-516). The template must be extended to
   include `disclosure_status` and `scope` as named fields on each
   disclosure object — most likely emitted as `null`/absent by the agent
   (per the existing judgment that classification is human work, not model
   work), rather than asking the model to classify.
2. **No structural/JSON-Schema validator exists to update** — confirmed
   `grep -rn "jsonschema"` across the whole repo returns zero hits, and
   there is no pydantic model for `dishes[]`/`allergen_disclosures[]`
   anywhere. `api/routers/intake.py`'s `SubmitPacketRequest`,
   `IntakePacketDetail`, and `EditPayloadRequest` all type `packet_data` as
   an opaque `Dict[str, Any]` (lines 112, 93, 149). This means a new
   validation rule is **greenfield plumbing**, not an edit to an existing
   validator.
3. **Approve-RPC precondition (`operations.approve_intake_packet`,
   `supabase/migrations/017_intake_review_decision_rpcs.sql:186-300`)** —
   today this function checks only workflow state (`packet_status =
   'in_review'` + claimed, lines 226-229) and actor authorization (lines
   231-254); it never inspects `packet_data` content at all (its own
   comment at line 169/265 states `packet_data` is "never referenced or
   written" by this function). A new precondition block must walk
   `v_row.packet_data->'dishes'` and refuse to transition to `approved`
   with SQLSTATE `GP422` — **confirmed, not a placeholder** (Decision 5,
   2026-07-16; reuses the existing validation/content-failure category, not
   a newly minted code) — if any *present* `allergen_disclosures[]` entry is
   neither validly classified (`disclosure_status` + `scope`) nor covered by
   an approved Evidence Disposition (§9a). Per the scope clarification in
   §9, dishes with no disclosure entries at all impose no requirement.
   Enforces item 3 of Brad's remediation list ("review UI and validation
   rules must require human confirmation of both fields — or a recorded
   disposition — before a packet containing allergen disclosures can be
   approved") at the same authoritative layer that already enforces every
   other approve precondition.
4. **API models (`api/routers/intake.py`)** — no model changes are strictly
   required if the RPC performs the check (errors already surface through
   the existing `_RPC_ERROR_STATUS` map, lines 202-207), but that map needs
   `GP422`'s existing entry confirmed to cover this new failure mode (it
   already maps `GP422` for other validation failures per migrations
   017-019, so this is likely a no-op, not a new map entry).
5. **Intake OS review UI (`web/app/admin/intake/[id]/page.tsx`)** — this UI
   **already exists** (615 lines; this is not greenfield, contrary to what
   Task #47's "pending" status might suggest — Task #47 is about updating
   already-built UI). Its dish table (lines 511-536) currently renders no
   allergen data at all — zero references to `allergen_disclosures` or
   `disclosure_status` in the file. **Authorization and scope — Decision 3
   (2026-07-16):** this UI work is authorized now, ahead of Task #47's
   formal start, but strictly limited to the minimum controls needed to
   satisfy the new approval precondition: (a) a per-disclosure
   classification control (`disclosure_status`/`scope`, wired through the
   existing `edit_payload` RPC/endpoint, migration 019 / `intake.py:634-666`)
   and (b) an Evidence Disposition control (§9a). These two controls are
   the minimum required to make the new approval precondition satisfiable
   by a reviewer; they are treated as the feature this task owns, not part
   of the broader Intake lifecycle UI redesign. Everything else —
   including the page's pre-existing `canApprove` gate drift (line 192,
   checking `["pending_review", "returned"]` instead of the actual RPC
   precondition of `in_review` + claimed), the six-state workflow
   presentation, queue behavior, and other action-visibility changes — is
   explicitly left to Task #47. When Task #47 begins, it must treat the
   classification and disposition controls as existing infrastructure to
   build around, not replace.
6. **Frontend types (`web/lib/types.ts:385`)** — `IntakePacketDetail.
   packet_data.dishes` is `Record<string, unknown>[]`, fully untyped. An
   `AllergenDisclosure` interface would make the new UI control (#5) safe
   to build against.
7. **Existing already-`approved` packets with incomplete disclosures** —
   **resolved (Decision 2, 2026-07-16); see §11 for the full ruling.**
   Summary: an Evidence Disposition backfill (§9a) may resolve an
   unclassifiable disclosure on an already-`approved` packet without
   mutating `packet_data` or changing `packet_status` (the "b1" path,
   approved for immediate use). Any remediation that requires changing
   `packet_data` itself must instead go through the governed
   `intake.packet.reopen` workflow (§9b) — direct administrative editing of
   an approved packet's `packet_data` ("b2") is **not approved**. This repo
   has no packets in `approved` status with unclassified allergen
   disclosures identified yet (no query has been run against a live
   database — none is available from this sandbox); the live-database
   scoping query (§12 step 4) still must happen before either remediation
   path is executed against real data.

8. **Approved values for `disclosure_status` and `scope`** — no new enum
   values are proposed; the existing `evidence.allergen_disclosures` CHECK
   constraints remain canonical and nothing upstream should introduce a
   value outside them:
   - `disclosure_status`: `contains` (affirmatively contains the allergen),
     `may_contain` (cross-contact/uncertain — the disclosure hedges),
     `free_from` (affirmatively excludes the allergen). A reviewer
     classifying a captured `statement` string picks exactly one; there is
     no `unknown`/`unspecified` value. **Resolved (Decision 1, 2026-07-16):**
     if a statement genuinely can't be classified into one of the three, the
     disclosure entry is **not** dropped from the packet and is **not**
     force-classified. It is preserved as captured and given an Evidence
     Disposition (§9a) — a recorded, auditable, non-destructive
     determination that the disclosure is not suitable for canonical
     evidence. `commit_ingest` treats a validly-dispositioned disclosure as
     resolved for precondition purposes, same as a validly-classified one.
   - `scope`: `dish` (applies only to the specific dish it's nested under)
     vs `restaurant` (applies restaurant-wide, e.g. "all fryer items may
     contain gluten," "we are a nut-free kitchen"). A reviewer must judge
     this from context. Per Brad's ruling in §9, dish-nesting must never be
     used to infer `scope='dish'` — both the review UI (§10 item 5) and
     `commit_ingest` must treat `scope` as a required, human-supplied
     judgment call with no structural shortcut.
9. **Tests/fixtures plan** — required before the approve-precondition (item
   3) and `commit_ingest`'s own precondition (§9) can be considered done:
   - RPC-level test: a packet with every *present* `allergen_disclosures[]`
     entry fully classified or dispositioned approves normally; a packet
     with any present entry missing `disclosure_status`/`scope` **and**
     lacking an approved disposition is rejected with `GP422` and a payload
     matching the shape specified in §9 (`evidence_type`, `missing_fields`,
     dish/restaurant context, `blocked_count`, `corrective_action_required`).
   - **Scope test (Founder clarification, 2026-07-16):** a packet where one
     or more dishes have **no** `allergen_disclosures[]` entries at all
     approves normally — absence of a disclosure must never be treated as a
     blocking condition. A packet with zero allergen disclosures anywhere
     passes the precondition automatically.
   - **Disposition test:** a packet with a present, unclassifiable
     disclosure that has been given an approved Evidence Disposition (§9a)
     approves normally; the original disclosure content remains intact and
     visible in `packet_data` and audit history.
   - Fixture packets: (a) fully classified, dish- and restaurant-scoped mix;
     (b) partially classified across multiple dishes, to verify
     `blocked_count` and per-record `missing_fields` are both accurate, not
     just a boolean fail — counting only present, unresolved entries; (c)
     restaurant-scoped entry (`dish_id` absent) missing classification, to
     verify the restaurant-level error-context path (§9) is exercised, not
     just the dish-level one; (d) a dish with zero disclosure entries mixed
     into an otherwise-blocked packet, to confirm it is never counted in
     `blocked_count`; (e) a dispositioned disclosure mixed with a genuinely
     unresolved one, to confirm only the unresolved entry blocks.
   - Regression test: the new approve precondition must not retroactively
     affect packets that reached `approved` before the precondition existed
     — it gates the `in_review → approved` transition only, never
     re-evaluates already-`approved` rows. This is what makes §11 a separate
     remediation problem rather than something the precondition itself
     fixes.
   - API test: `GP422` is present in `_RPC_ERROR_STATUS`
     (`api/routers/intake.py:202-207`) and maps to the correct HTTP status
     (confirm the existing entry covers this new failure mode).
   - UI/manual QA: reviewer can classify or disposition every present
     disclosure on a packet through the new controls (§10 item 5) and the
     `canApprove` gate correctly blocks approval only while a present
     disclosure is neither classified nor dispositioned.

None of items 1-9 are implemented by this document. They are scoped, not
built. No `intake_agent.py`, `api/routers/intake.py`, migration, or `web/`
file has been changed.

---

## 11. Existing approved packets with incomplete allergen disclosures — resolved (Decision 2, 2026-07-16)

This is the follow-up flagged in §10 item 7. No live-database query has been
run from this sandbox, so the actual volume of affected packets is unknown —
that query must happen before any remediation is executed (§12 step 4). The
original three-option framing (A: return-for-correction, B: administrative
backfill, C: hybrid) is **superseded** by Brad's ruling, which reframes the
question around whether `packet_data` itself needs to change, not around
which workflow feels proportionate to the volume of affected packets:

**Governing invariant:** an approved packet may not be edited silently or
in place. Any change to approved `packet_data` requires a formal reopen
workflow with complete audit history (§9b).

**Path b1 — Evidence Disposition backfill (approved for immediate use).**
An authorized administrator may resolve an unclassifiable disclosure on an
already-`approved` packet by recording an Evidence Disposition (§9a) —
without mutating `packet_data` and without changing `packet_status`. This
is available now, once §9a is built, and does not require the reopen
workflow because nothing about the packet's content changes — only a new,
separate audit record is added declaring the disclosure out of scope for
ingestion.

**Path b2 — Direct administrative edit to `packet_data` (not approved).**
Editing an already-approved packet's `packet_data` directly, without
reopening it, is **not approved.** If a remediation genuinely requires
changing the packet's content (as opposed to determining a disposition for
existing content), it must go through the governed `intake.packet.reopen`
workflow (§9b): non-blank reason, authorized actor, distinct audit event,
and a full pass back through ordinary review and approval before the packet
can reach `approved` again.

**Why both paths exist:** Brad's ruling explicitly rejects an architecture
that implies an approval can never be corrected. Real approvals may later
need to be reversed because of error, newly discovered evidence, or an
incomplete review — that possibility is preserved via `reopen`, not
foreclosed. But the two remediation shapes are kept structurally distinct:
a disposition never touches packet content; a reopen always does, and
always re-enters full review.

This closes blocking decision §13.4. `reopen` itself remains undefined by
this document (§9b) — its detailed design is separate governance work.

---

## 12. Sequencing plan (updated 2026-07-16 per Decisions 1-6)

All six §13 blocking decisions are now resolved (§13). This sequencing plan
reflects those rulings; SQL/code for any step below remains unwritten and
unexecuted, per standing instruction, until separately authorized.

1. **Migration 020 (Track A — §8, items 1-5, including Decision 6's
   `calorie_raw_fragment` addition) stands as a standalone package**
   (Decision 4). It may be reviewed, written, and executed independently of
   Track B — it carries no dependency on the allergen-disclosure remediation
   work and no risk to existing rows. Its SQL will not be written until this
   sequencing plan and all six §13 decisions are recorded (done, as of this
   update) — actual drafting still awaits your explicit go-ahead, since
   "decisions recorded" and "authorized to write SQL now" are treated as
   separate gates. When written, it must be reviewed for compatibility with
   existing rows, constraints, indexes, ownership boundaries, and future
   `commit_ingest` column mappings. Executing migration 020 does **not** by
   itself unblock Task #46 — `commit_ingest` remains blocked on Track B
   below regardless of migration 020's status.
2. **SQLSTATE resolved:** the approve-precondition and `commit_ingest`
   precondition (§9) will use `GP422` (Decision 5) — no further design work
   needed on this point before Track B's migration is drafted.
3. Build Track B (§10, §9a, §9b): agent template update (`intake_agent.py`),
   the new approve-RPC precondition migration (scoped per §9's
   existing-entries-only clarification), `_RPC_ERROR_STATUS` confirmation,
   the Evidence Disposition mechanism (§9a: schema, API, audit event type),
   and the narrowly-scoped review-UI controls authorized by Decision 3
   (§10 item 5: disclosure classification + Evidence Disposition only).
   Land the tests/fixtures from §10 item 9 alongside this work, not after
   it. **Track B will use a migration number later than 020**, reflecting
   its independence from and later readiness than Track A (Decision 4).
4. Run the live-database query to scope existing `approved` packets with
   incomplete allergen disclosures (§10 item 7 / §11) — cannot happen from
   this sandbox; requires Brad or another engineer with DB access.
5. Execute existing-packet remediation per Decision 2/§11: apply Evidence
   Disposition backfill (b1) wherever a disposition alone resolves the gap;
   apply the governed `intake.packet.reopen` workflow (b2, §9b) only where
   `packet_data` itself must change. `reopen`'s detailed design (guardrails,
   roles, exact transition semantics) is separate governance work not yet
   done — this step may itself be blocked on that design being completed
   first, if any real packet requires the b2 path.
6. Resume Task #46: implement `commit_ingest` itself, using the
   precondition-failure design in §9 (disposition-aware, existing-entries-
   only) and the `calorie_raw_fragment` population behavior from Decision 6.
   By this point every approved packet going forward will have complete
   allergen-disclosure resolution (step 3's precondition prevents new gaps)
   and every pre-existing gap will have been resolved (step 5) — so
   `commit_ingest`'s strict-fail behavior won't immediately block on
   essentially every real packet.
7. Begin Task #47 (Intake OS review UI updates). Per Decision 3, Task #47
   treats the disclosure-classification and Evidence Disposition controls
   built in step 3 as existing infrastructure to build around, not replace
   — the broader six-state workflow presentation, queue behavior, action
   visibility, `canApprove` cleanup, and other lifecycle UI work remain
   entirely Task #47's scope.

---

## 13. Section 13 decision ledger — all six resolved, 2026-07-16

All six blocking decisions below were presented one at a time, in
priority order (highest downstream impact first, per Brad's instruction),
and each was ruled on before the next was presented. Priority order as
presented: §13.6 → §13.4 → §13.2 → §13.5 → §13.1 → §13.3. Original section
numbering is preserved below for cross-reference continuity with the rest
of this document; none remain open.

1. **§13.6 — Unclassifiable disclosures. RESOLVED.** Rejected both original
   options (silent drop via `edit_payload`; force-classification with no
   drop path). Ruling: captured evidence is never silently removed. A
   reviewer may determine a captured disclosure is not suitable for
   canonical evidence via an explicit, extensible **Evidence Disposition**
   (§9a) — recorded with actor, authority basis, timestamp, and a required
   non-blank reason. `commit_ingest` excludes dispositioned disclosures from
   the ingestion-bound set because governance decided so, not because they
   were deleted. The disposition model must not be hardcoded to a single
   value (`excluded`) — it must accept future disposition values without a
   structural rework. See §9a for the full model and §10 item 8 for the
   corrected `disclosure_status` guidance this supersedes.
2. **§13.4 — Existing-packet remediation approach. RESOLVED.** The original
   three-option framing (return-for-correction / administrative backfill /
   hybrid) is superseded. Ruling: an approved packet may not be edited
   silently or in place — any change to `packet_data` requires a formal
   `intake.packet.reopen` workflow with complete audit history (§9b). Split
   into two paths: **b1 (approved for immediate use)** — Evidence
   Disposition backfill on an already-`approved` packet, which does not
   mutate `packet_data` or change `packet_status`, so it does not require
   reopening. **b2 (not approved as a direct edit)** — any remediation that
   requires changing `packet_data` itself must use the governed `reopen`
   command: non-blank reason, authorized actor, distinct audit event, and a
   full pass back through ordinary review/approval. `reopen` is explicitly
   **not defined inside DEC000003** — it is the separate governance work
   anticipated by DEC000001 line 38 and §5.9. See §9b and §11.
3. **§13.2 — UI-authorization timing. RESOLVED.** Ruling: authorize only
   the minimum UI required to support the new approval semantics —
   disclosure classification and the Evidence Disposition control — now,
   ahead of Task #47's formal start. Rationale: this task owns the feature
   it is implementing (establishing the approval contract), not every file
   it touches. These two controls are narrowly scoped and self-contained.
   All remaining Intake lifecycle UI work (six-state workflow presentation,
   queue behavior, action visibility, `canApprove` cleanup, and other
   lifecycle presentation changes) is left to Task #47, which must treat
   the two controls as existing infrastructure to build around. See §10
   item 5.
4. **§13.5 — Migration 020 sequencing. RESOLVED.** Ruling: migration 020
   (Track A) may be written, reviewed, and executed independently of Track
   B's remaining allergen-disclosure work — the five (now six, with
   Decision 6) Track A schema changes are additive and decoupled. Migration
   020 is a standalone implementation package; its SQL is written only
   after the remaining §13 decisions are presented and recorded (satisfied
   as of this update) unless explicitly authorized sooner; when written, it
   must be reviewed for compatibility with existing rows, constraints,
   indexes, ownership boundaries, and future `commit_ingest` mappings.
   Executing migration 020 does not by itself unblock Task #46 —
   `commit_ingest` remains blocked on Track B. Track B will use a later
   migration number. See §12.
5. **§13.1 — SQLSTATE code. RESOLVED.** A grep across migrations 017-019
   confirmed exactly four custom codes exist anywhere in the codebase —
   `GP403` (authorization), `GP404` (not found), `GP409` (state conflict),
   `GP422` (validation/content failure) — each reused across RPCs for a
   semantic category, not allocated per-RPC. Ruling: the new
   allergen-disclosure-completeness precondition reuses `GP422`, consistent
   with the existing category taxonomy, rather than minting a new code. See
   §9 and §10 item 3. **Founder scope clarification (same session):** the
   `GP422` precondition applies only to allergen-disclosure entries that
   actually exist in `packet_data` — dishes with no disclosures impose no
   requirement, and a packet with zero disclosures anywhere passes
   automatically. `blocked_count` counts only present, unresolved
   (unclassified-and-undispositioned) entries.
6. **§13.3 — Discretionary defensive columns. RESOLVED.** Ruling: migration
   020 adds `calorie_raw_fragment jsonb NULL` to `evidence.dishes`,
   alongside the named calorie columns, mirroring the `raw_packet_fragment`
   pattern already adopted for `evidence.dish_modifiers`. Purpose: defensive
   preservation of the exact approved `restaurant_calorie_content` fragment
   against future key-naming drift or additional/nested structure. The
   named columns remain canonical and queryable; the raw fragment never
   replaces or overrides them and is not a second source of truth — the
   packet and revision history remain authoritative. `commit_ingest`
   populates it with the exact approved calorie object when one exists and
   leaves it null otherwise; no dish is required to have calorie content.
   **Founder clarification (same session):** calories are optional
   evidence, not a required property of every dish. All seven
   calorie-related columns on `evidence.dishes` (existing `calorie_value`,
   `calorie_source_text`; proposed `calorie_unit`, `calorie_source_url`,
   `calorie_ingredient_source`, `calorie_notes`, `calorie_raw_fragment`)
   must remain nullable. A dish with no approved calorie object must ingest
   successfully with all seven null; absence must never block approval or
   `commit_ingest`; GoldPan must not infer, estimate, or fabricate calories
   through this path; restaurant-stated calories must stay a distinct
   record from any future GoldPan-estimated calorie model. See §4 item 4
   and §8 item 4.

---

## 14. Non-blocking technical debt

Noted for completeness; none of these gate Task #46, Track A, or Track B.

1. `_modifiers_to_str()`'s blank-output bug for the `name`/`upcharge`
   modifier key variant (§7 item 5) — pre-existing in the Sheets pipeline,
   independent of this work, and orthogonal once `evidence.dish_modifiers`
   (§8 item 5) exists as the real destination.
2. The Intake OS review UI's `canApprove` gate checking a pre-RPC status
   list instead of the actual RPC precondition (`in_review` + claimed) —
   pre-existing drift (§10 item 5), worth fixing in the same UI pass since
   Task #47/§10 item 5 is already touching this file.
3. No JSON-Schema or pydantic validation exists anywhere on `packet_data`
   (§10 item 2) — a greenfield gap larger than this document's scope;
   `commit_ingest`'s and the approve-RPC's own preconditions are the only
   structural checks in place today, and will remain so unless a separate
   effort builds real schema validation.
4. `evidence.dishes.dietary_options`'s fate once `evidence.dish_modifiers`
   exists as the structured destination (§7 item 8) — keep as a
   derived/rendered summary, or deprecate it — needs a decision eventually
   but doesn't block Track A.
5. `claim_type`'s derivation lookup covering only 4 of the 7 `scope` values
   (§2 item 5) — lossy, pre-existing, orthogonal to the `scope` column
   addition itself.

---

## Summary (updated 2026-07-16 — all six §13 decisions resolved)

- Items 1–4 and 7 (verbatim components, restaurant-claim scope, source
  inventory, calorie sub-fields including Decision 6's
  `calorie_raw_fragment`, modifier structure): clean additive `evidence.*`
  schema gaps, fully resolvable by the proposed (still unexecuted)
  migration-020 design in §8, now with all seven calorie columns confirmed
  nullable and calories confirmed optional evidence. No governance
  ambiguity, no upstream workflow change required.
- Items 5–6 (allergen disclosure `disclosure_status`/`scope`): **not** an
  `evidence.*` schema gap — `evidence.allergen_disclosures` already has the
  correct columns. This is an upstream Intake-model gap spanning the agent
  prompt/template, the (currently nonexistent) structural validator, the
  approve-RPC precondition, and the existing Intake OS review UI — scoped
  in §10, not yet built, and now shaped around the Evidence Disposition
  mechanism (§9a) rather than a drop-from-packet path.
- The `reviewer_status` non-gap: confirmed correctly out of scope, no
  action needed.
- DEC000001 §5.7 semantics: **resolved, not amended** (§9). Strict reading
  holds — `commit_ingest` fails closed (SQLSTATE `GP422`, confirmed) on
  present, unresolved allergen disclosures rather than skipping or
  inferring. The precondition applies only to disclosure entries that
  actually exist in `packet_data`; dishes without any disclosure entries
  impose no requirement, and a validly-dispositioned disclosure resolves
  the precondition the same as a validly-classified one.
- **§9a (new)** defines the Evidence Disposition mechanism: captured
  evidence is never silently removed; a reviewer may record an extensible,
  audited disposition (actor, authority basis, timestamp, required reason)
  that excludes a disclosure from the ingestion-bound set without deleting
  it from packet or audit history.
- **§9b (new)** defines the governing invariant for approved-packet
  correction: any change to approved `packet_data` requires the governed
  `intake.packet.reopen` workflow. Evidence Disposition backfill does not
  require reopening because it never touches `packet_data`. `reopen` itself
  remains undefined by this document — separate governance work, per
  DEC000001 line 38 and §5.9.
- §10 is implementation-ready: approved values for `disclosure_status`/
  `scope` (item 8, now disposition-aware), a file-by-file remediation map
  across the agent template, the (nonexistent) validator, the approve-RPC
  precondition (confirmed `GP422`), API models, and a narrowly-scoped
  review UI (item 5, per Decision 3), and an expanded tests/fixtures plan
  (item 9, including scope and disposition test cases).
- §11 resolves the existing-packet remediation question (Decision 2): a
  disposition-only backfill path (b1) requiring no reopen, and a
  `packet_data`-editing path (b2) that requires the governed reopen
  workflow and is not approved as a direct edit.
- §12 sequences all of the above, updated for standalone migration-020
  sequencing (Decision 4): migration 020 (standalone, later SQL drafting)
  → SQLSTATE already resolved → Track B build-out (with tests, later
  migration number) → live-DB scoping query → existing-packet remediation
  (b1/b2) → resume Task #46's `commit_ingest` → begin Task #47 (building
  around the Decision-3-scoped UI controls).
- §13 is now a **resolved decision ledger** — all six items (§13.6, §13.4,
  §13.2, §13.5, §13.1, §13.3, presented in that priority order) carry
  Founder rulings recorded 2026-07-16, with two additional scope
  clarifications folded in (disclosure precondition applies only to
  existing entries; calorie fields are all nullable/optional evidence).
- §14 lists five items of non-blocking technical debt surfaced during this
  analysis, noted for later but not gating any of the above — unchanged by
  this update.
- **Task #46 remains blocked** until: (1) migration 020's additive schema
  changes (§8, including `calorie_raw_fragment`) are reviewed, written, and
  applied; and (2) Track B (§10, §9a, §9b) — agent template, approve
  precondition, Evidence Disposition mechanism, narrowly-scoped review UI,
  and existing-packet remediation (b1/b2) — is built and deployed, so
  present allergen disclosures are resolved (classified or dispositioned)
  *before* a packet can reach `approved`. All six blocking decisions that
  previously stood between this design and that build-out are now resolved;
  what remains is the actual SQL/code implementation, which has not begun.

Stopping here per your instruction. No migration SQL has been written or
executed, DEC000001 has not been changed, no `commit_ingest` code has been
written, nothing has been committed or pushed, and Task #47 has not been
started. All six §13 items are now resolved in this document; implementation
still requires separate authorization to begin.
