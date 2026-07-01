# GoldPan Recanvassing Policy

**Status:** Active policy  
**Last updated:** 2026-06-28  
**Governed by:** GP-RULE-008, GP-RULE-009 (see `docs/RULES_REGISTRY.md`)

---

## Core Principle

> **GoldPan is only healthy if its data remains connected to the real-world restaurant menu. Validation proves internal consistency. Recanvassing proves external freshness. Both are required.**

A database can pass every validation check and still be wrong — if the restaurant changed its menu after the last canvass, the validated data no longer reflects reality. Internal consistency and external freshness are independent properties. GoldPan must track and enforce both.

Recanvassing is not a recovery mechanism for errors. It is a routine maintenance requirement built into the architecture from the beginning.

---

## Field Definitions

These fields are added to the **Menu Source Registry** tab, one row per restaurant. They describe the freshness state of the restaurant's data as a whole. Dish-level freshness is derived from these restaurant-level fields.

---

### `Recanvass_Tier`

**Type:** Integer (1, 2, or 3)  
**Set by:** GoldPan data team at restaurant onboarding  
**Purpose:** Defines which recanvass frequency window applies to this restaurant.

| Tier | Frequency | Applies to |
|---|---|---|
| 1 | 90 days | High-value restaurants; restaurants with known frequent menu changes; restaurants where allergen accuracy is especially critical (allergy-focused menus, fusion menus with complex ingredients) |
| 2 | 180 days | Standard active restaurants with reasonably stable menus |
| 3 | 365 days | Restaurants with documented stable, long-term menus; restaurants where the menu is verified as rarely changing |

When in doubt, assign Tier 2. Tier 3 must be explicitly justified. A restaurant's tier may be upgraded (shortened window) at any time if menu instability is observed. A restaurant's tier may only be downgraded (extended window) after at least two consecutive recanvasses find no changes.

---

### `Last_Canvassed`

**Type:** Date (YYYY-MM-DD)  
**Set by:** Canvasser at the end of each recanvass  
**Purpose:** Records when a human canvasser last reviewed the restaurant's live menu and confirmed or updated GoldPan's data.

This is not the date the data was last written to the sheet — it is the date the source was last examined with human judgment. A backfill run does not update `Last_Canvassed`. An upsert from a new staging file does update it. A patch to fix a data error does not.

`Last_Canvassed` is the primary input for `Recanvass_Status` computation.

---

### `Last_Source_Check`

**Type:** Date (YYYY-MM-DD)  
**Set by:** Canvasser or automated source checker  
**Purpose:** Records when the restaurant's registered menu source URL(s) were last verified as live and accessible.

`Last_Source_Check` is a lower bar than `Last_Canvassed`. A source check confirms that the URL returns a valid response and that menu content appears present. It does not confirm that the content matches GoldPan's records. It does not require human review of individual dishes.

A source check may be performed without a full recanvass — for example, a weekly automated ping that confirms the URL is still live. When a full recanvass is performed, `Last_Source_Check` is updated alongside `Last_Canvassed`.

If `Last_Source_Check` fails (URL returns 404, redirects to a generic page, or returns inaccessible content), `Recanvass_Status` is immediately upgraded to `needs_review` regardless of how recent the last full canvass was.

---

### `Menu_Changed`

**Type:** String — `yes` | `no` | `unknown`  
**Set by:** Canvasser after each recanvass  
**Purpose:** Records whether the canvasser observed any change from the previously recorded menu data.

- `yes` — at least one change was detected. `Change_Type` must be set.
- `no` — canvasser reviewed the menu and confirmed it matches GoldPan's current records.
- `unknown` — canvass was partial, the source was unavailable for content review, or the canvasser could not determine whether changes occurred.

`unknown` triggers review — it is not a clean result.

---

### `Change_Type`

**Type:** Comma-separated string of one or more values  
**Set by:** Canvasser when `Menu_Changed = yes`  
**Valid values:** `none`, `price`, `dish_added`, `dish_removed`, `ingredients_changed`, `allergen_changed`, `source_changed`

`Change_Type` is multi-valued because a single recanvass may find multiple types of changes simultaneously. `none` is the only single value — it means no changes were detected and is synonymous with `Menu_Changed = no`.

| Value | Meaning | Action required |
|---|---|---|
| `none` | No changes detected | Update `Last_Canvassed`, recompute `Recanvass_Status` |
| `price` | Price changes only — no ingredient, allergen, or menu structure changes | Update price data if tracked; no derived filter recompute required |
| `dish_added` | One or more new dishes are on the live menu | Canvass new dishes; create staging file; upsert |
| `dish_removed` | One or more dishes GoldPan tracks are no longer on the menu | Mark affected dishes Inactive in DLD; recompute derived filters |
| `ingredients_changed` | Ingredient list for one or more existing dishes has changed | Update ingredient rows; recompute derived filters for affected dishes |
| `allergen_changed` | Allergen information has changed without necessarily changing ingredients | Update allergen data; recompute derived filters for affected dishes |
| `source_changed` | The menu source URL or platform has changed | Update Menu Source Registry; verify new source; re-check all data against new source |

When `source_changed` is detected, treat all data as unverified against the new source until a full recanvass against the new source is complete. The data itself may be correct, but its provenance needs re-verification.

---

### `Recanvass_Status`

**Type:** String — `current` | `due_soon` | `overdue` | `needs_review`  
**Set by:** Computed — never manually set  
**Purpose:** The single field that the pipeline and engine consult to determine whether a restaurant's data is fresh enough to support full-confidence derived filter computation.

`Recanvass_Status` must be recomputed at the start of every pipeline run. It is a derived field, not a stored opinion. Setting it manually is a data integrity violation because it will immediately drift from the computed truth as time passes.

**Computation logic:**

```
days_since_canvass = today − Last_Canvassed
window = 90  if Tier 1
         180 if Tier 2
         365 if Tier 3

if source_check_failed:
    Recanvass_Status = "needs_review"

elif days_since_canvass > window:
    Recanvass_Status = "overdue"

elif days_since_canvass > (window − 30):
    Recanvass_Status = "due_soon"

else:
    Recanvass_Status = "current"
```

A forced trigger (see section below) may upgrade `Recanvass_Status` to `needs_review` regardless of the date calculation. `needs_review` is never reached through the date window alone — it requires an external signal.

| Status | Meaning | Effect on pipeline |
|---|---|---|
| `current` | Last canvass is within the required window | No effect — full confidence |
| `due_soon` | Within 30 days of window expiry | Staleness caveat added to derived filter limitations; no confidence change |
| `overdue` | Past window expiry | Derived conclusions computed but confidence downgraded from `verified` to `likely`; staleness warning added |
| `needs_review` | Forced trigger has fired; data may not reflect current menu | All derived conclusions return `Unknown` until recanvass is completed |

---

## Recanvass Frequency Windows

| Tier | Window | Due Soon threshold |
|---|---|---|
| 1 | 90 days | 60 days after `Last_Canvassed` (30 days before expiry) |
| 2 | 180 days | 150 days after `Last_Canvassed` |
| 3 | 365 days | 335 days after `Last_Canvassed` |

The window starts from `Last_Canvassed`, not from the onboarding date.

---

## Source Freshness Rules

A **source** is fresh when all of the following are true:

1. The registered menu URL(s) return valid, accessible content.
2. `Last_Source_Check` is within 30 days (regardless of `Recanvass_Tier`).
3. No redirect to a 404, "page not found," or generic restaurant homepage is detected.
4. The source platform has not changed (same domain, same URL path structure).

Source freshness is a lower bar than data freshness. A fresh source means the URL is alive. Data freshness (full recanvass) means a human has reviewed the source content and confirmed GoldPan's records.

**Source check frequency:** Source URLs should be checked at minimum once every 30 days for all active restaurants, regardless of `Recanvass_Tier`. This is a lightweight check — URL ping, not content review — and is appropriate for automation. If a source check fails, `Recanvass_Status` is immediately set to `needs_review`.

**When a source moves:** If a restaurant migrates their menu to a new platform (e.g., from a PDF to a website, or from their website to a third-party ordering platform), the old URL becomes invalid. This triggers `Change_Type = source_changed` and `Recanvass_Status = needs_review`. All dish-level data remains in the database but is treated as unverified against the new source until a full recanvass confirms accuracy.

---

## Forced Recanvassing Triggers

The following events immediately set `Recanvass_Status = needs_review`, bypassing the time-window calculation. Each trigger must be logged with the triggering event and date.

| Trigger | Description |
|---|---|
| **Source URL failure** | `Last_Source_Check` returns 404, redirect, or inaccessible content |
| **Source platform changed** | Menu moved to a new URL, domain, or platform |
| **`Change_Type` includes high-impact values** | Previous recanvass found `dish_removed`, `ingredients_changed`, or `allergen_changed` — the next recanvass is forced before derived filters can run at full confidence |
| **Restaurant relocation** | Address changes; menus often change with new locations |
| **Restaurant ownership change** | New ownership may substantially change the menu |
| **Customer-reported discrepancy** | A diner reports a dish is no longer available or ingredients differ from what GoldPan shows |
| **Seasonal menu indicator** | Restaurant is tagged as having known seasonal menu changes and the seasonal transition period has arrived |
| **External menu change signal** | Any external signal (third-party mention, social media, news) suggesting a significant menu change — triggers review, not automatic update |

Forced triggers require human review before `Recanvass_Status` can be cleared back to `current`. Automated source checks can detect the trigger; only a completed recanvass can clear it.

---

## How Staleness Affects Confidence

Staleness and evidence quality are independent axes. A stale dish was accurately documented at canvass time — the question raised by staleness is whether that documentation is still true today.

```
Evidence Quality:  Is the data correct as of the canvass date?  (Answered by validation)
Evidence Freshness: Is the data still correct today?            (Answered by recanvassing)
```

GoldPan tracks both. A dish may have high-quality stale data or low-quality fresh data. Neither substitutes for the other.

### Confidence levels by `Recanvass_Status`

| Status | Confidence in derived conclusions | Displayed as |
|---|---|---|
| `current` | `verified` — full confidence | Standard derived filter results |
| `due_soon` | `verified` — no confidence change, but staleness caveat added to limitations | Standard results + "Recanvass due soon" note in explanation |
| `overdue` | `likely` — evidence is internally consistent but may no longer reflect current menu | Results shown with "Data may be outdated" indicator; confidence degraded |
| `needs_review` | `unknown` — data freshness cannot be established | All derived conclusions return Unknown; "Verification pending" shown |

The confidence field in `DerivedConclusion` (see `derived/models.py`) must reflect this:
- `verified` when `Recanvass_Status` is `current` or `due_soon`
- `likely` when `Recanvass_Status` is `overdue`
- `unknown` when `Recanvass_Status` is `needs_review`

These are maximum confidence values. A derived conclusion that was already `likely` or `unknown` due to evidence quality (GP-RULE-001) is not upgraded by a `current` recanvass status.

---

## Stale Dish Handling Policy

**GoldPan does not hide stale dishes. It flags them.**

The rationale: hiding a stale dish removes potentially accurate information from users without explanation. Silently showing stale data is misleading. The correct response is to display the data with an honest freshness indicator so users can make their own decisions.

### Handling by status

**`current` and `due_soon`:**  
No change to dish display. The due_soon status is an internal signal for canvassers — it is not surfaced to users.

**`overdue`:**  
Dish remains visible and searchable. Derived filter conclusions are shown with `likely` confidence. The "Last verified" date is displayed with the dish. If the date is substantially old (over 12 months), a visible indicator — "Information may be outdated" — is shown. The dish is not removed from filter results, but its degraded confidence is communicated.

**`needs_review`:**  
Dish remains visible. Derived filter conclusions are suppressed (replaced with "Verification in progress"). The "Last verified" date is displayed. The dish is flagged in the admin/canvasser dashboard for immediate attention. Importantly, the dish is NOT removed from display — its ingredient list, dietary tags, and other manually curated data are still shown. Only derived, engine-computed conclusions are withheld until freshness is re-established.

### What is never done

- Dishes are not automatically marked `Inactive` due to staleness. Only a human who has confirmed the dish is no longer on the menu may mark it Inactive.
- Derived filter conclusions are not silently served with outdated confidence levels. Every conclusion shows the confidence that its evidence freshness actually supports.
- A canvasser's `Last_Canvassed` update alone does not restore confidence — the recanvass must produce a new staging file or confirmed `Menu_Changed = no` entry to justify the status change.

---

## Recanvassing and Derived Filters

The derived filter engine (`derived/engine.py`) must check `Recanvass_Status` as a pre-condition before computing any derived conclusion. This is a third gate in addition to the dependency-type check (GP-RULE-007) and the materiality test (GP-RULE-001).

### Engine execution order

For each dish:

1. **Check `Recanvass_Status`** of the dish's restaurant.
   - `needs_review` → return `Unknown` for all filters. Record reason: "Restaurant data pending verification."
   - `overdue` → proceed, but cap confidence at `likely` for all conclusions.
   - `current` / `due_soon` → proceed normally.

2. **Check dependency type** (GP-RULE-007) — does the available evidence meet the filter's declared dependency?

3. **Apply materiality test** (GP-RULE-001) — could missing evidence change this conclusion?

4. **Compute conclusion** via the filter's `compute_fn`.

5. **Apply staleness caveat** to the explanation's `limitations` field if `Recanvass_Status` is anything other than `current`.

### Staleness and recomputation

When a recanvass finds `Menu_Changed = no`:
- `Last_Canvassed` is updated
- `Recanvass_Status` is recomputed (typically moves to `current`)
- Derived filters do not need to be recomputed — the evidence has been re-confirmed, not changed

When a recanvass finds `Menu_Changed = yes` with `ingredients_changed` or `allergen_changed`:
- Update the staging file and upsert
- Run `backfill_enrichment.py --apply` for affected dishes
- Run `compute_derived_filters.py --apply` for affected dishes (or all dishes if uncertain which are affected)
- Update `Last_Canvassed`, `Menu_Changed`, and `Change_Type`

When a recanvass finds `dish_removed`:
- Mark the dish `Inactive` in DLD
- The derived filter engine already excludes Inactive dishes — no additional recompute needed
- Update `Last_Canvassed`, `Menu_Changed = yes`, `Change_Type = dish_removed`

### Staleness in the explanation object

Every `DerivedConclusion` produced while `Recanvass_Status` is not `current` must include a staleness note in its `limitations` field:

```
due_soon:
  "Note: This restaurant's menu data is approaching its scheduled recanvass date.
   Results reflect verified data from [Last_Canvassed]."

overdue:
  "Warning: This restaurant's menu data is past its scheduled recanvass window.
   Results are shown with reduced confidence. Last verified: [Last_Canvassed].
   Diners should confirm current menu details with the restaurant."

needs_review:
  (Result is Unknown — no conclusion to append a limitation to)
```

---

## Required Recanvass Report Format

Every completed recanvass must produce a report. This report is the audit trail that proves the recanvass happened, documents what was found, and specifies what follow-up work is required. A recanvass without a report is not considered complete.

```
═══════════════════════════════════════════════
GOLDPAN RECANVASS REPORT
═══════════════════════════════════════════════
Restaurant:        [Name]  [Restaurant_ID]
Recanvass Date:    [YYYY-MM-DD]
Performed by:      [Canvasser name or system]
Previous canvass:  [YYYY-MM-DD]  ([N] days ago)
Recanvass Tier:    [1 / 2 / 3]  (window: [N] days)

──────────────────────────────────────────────
SOURCES CHECKED
──────────────────────────────────────────────
[URL or source description]  → [accessible / inaccessible]
[URL or source description]  → [accessible / inaccessible]

──────────────────────────────────────────────
FINDINGS
──────────────────────────────────────────────
Menu_Changed:    [yes / no / unknown]
Change_Type:     [none | list of types]

Dishes reviewed:   [N]
Dishes added:      [N]  [list Dish_IDs if > 0]
Dishes removed:    [N]  [list Dish_IDs if > 0]
Dishes changed:    [N]  [list Dish_IDs if > 0]

Ingredients changed:
  [Dish_ID] [Dish_Name]: [description of change]

Allergen data changed:
  [Dish_ID] [Dish_Name]: [description of change]

──────────────────────────────────────────────
STATUS UPDATE
──────────────────────────────────────────────
Last_Canvassed:      [new date]
Last_Source_Check:   [new date]
Recanvass_Status:    [new computed status]

──────────────────────────────────────────────
FOLLOW-UP REQUIRED
──────────────────────────────────────────────
[ ] Staging file created for new/changed dishes
[ ] Upsert run: python3 upsert_dishes.py [file]
[ ] Backfill run: python3 backfill_enrichment.py --apply
[ ] Derived filters recomputed: python3 compute_derived_filters.py --apply
[ ] Inactive dishes marked: [list Dish_IDs]
[ ] Menu Source Registry updated
[ ] No follow-up required — no changes detected

═══════════════════════════════════════════════
```

This report is saved to `docs/recanvass_reports/` named `recanvass_[RestaurantID]_[YYYY-MM-DD].md`. It is not overwritten by future recanvasses — it is the permanent record of what was found on that date.

---

## Integration Map

This section specifies exactly where each recanvassing concept belongs in the GoldPan system. These are architectural assignments, not suggestions.

---

### Rules Registry (`docs/RULES_REGISTRY.md`)

**GP-RULE-008 — Data Freshness Rule:**  
Establishes that a derived conclusion is only valid while its evidence source is reasonably current. Defines the relationship between `Recanvass_Status` and derived filter computation eligibility. Requires the engine to check freshness before computing any derived conclusion.

**GP-RULE-009 — Stale Evidence Confidence Degradation Rule:**  
Defines the specific confidence outcomes for each `Recanvass_Status` value. Requires that derived conclusions reflect the freshness of the evidence they cite, not just the quality.

Both rules are cited in the `rule_ids` field of any derived conclusion affected by staleness.

---

### Menu Source Registry (Google Sheet tab)

**New columns to add:**

| Column | Type | Set by |
|---|---|---|
| `Recanvass_Tier` | Integer (1/2/3) | Manually at onboarding |
| `Last_Canvassed` | Date | Canvasser after each recanvass |
| `Last_Source_Check` | Date | Automated checker or canvasser |
| `Menu_Changed` | String (yes/no/unknown) | Canvasser |
| `Change_Type` | Comma-separated string | Canvasser when Menu_Changed = yes |
| `Recanvass_Status` | Computed string | Computed — never manually set |
| `Recanvass_Notes` | Free text | Canvasser — optional notes |

`Recanvass_Status` should be computed by `compute_derived_filters.py` (or a dedicated `check_freshness.py` script) at the start of every run. It is written to the sheet as a record but must be recomputed at each run, not read as authoritative without rechecking the date.

---

### Pipeline Orchestrator

Recanvassing introduces a **Step 0** that runs before any derived filter computation:

```
Step 0: Freshness Check
  - Read Last_Canvassed and Recanvass_Tier for every active restaurant
  - Compute Recanvass_Status for every restaurant
  - Write computed Recanvass_Status back to Menu Source Registry
  - Produce Freshness Report (see Database Health Report below)
  - If any restaurant is needs_review: flag in report; engine will return Unknown for those dishes
  - If any restaurant is overdue: flag in report; engine will cap confidence at "likely" for those dishes
  - Proceed to derived filter computation

Step 1: Backfill (if applicable)
Step 2: Compute derived filters (engine checks Recanvass_Status per dish)
Step 3: Fetch/export
Step 4: Deploy
```

The full documented pipeline sequence is:
```bash
python3 check_freshness.py          # Step 0 — produces freshness report, updates Recanvass_Status
python3 backfill_enrichment.py --apply   # Step 1
python3 compute_derived_filters.py --apply  # Step 2
python3 fetch_dishes.py             # Step 3
# git push → GitHub Pages deploy   # Step 4
```

---

### Database Health Report

The Database Health Report should include a **Data Freshness** section:

```
DATA FRESHNESS
══════════════════════════════════════════════════════
Restaurant           Tier  Last Canvassed  Status       Days Until Due / Overdue
─────────────────────────────────────────────────────
Brick & Tin          2     2026-05-15      overdue      44 days overdue
Adam & Eve Cafe      2     2026-06-27      current      136 days remaining
Emmy Squared         2     2026-06-27      current      136 days remaining
[...all restaurants]

Summary:
  current:      18 restaurants
  due_soon:      4 restaurants
  overdue:       2 restaurants
  needs_review:  1 restaurant

Overall Freshness Score: 72%  (restaurants with current or due_soon status)
══════════════════════════════════════════════════════
```

The freshness score is a health metric: if it falls below 80%, the database as a whole has a freshness problem that requires canvasser attention before more onboarding work.

---

### Future UI / Customer Confidence Indicators

These are not implemented today but are the intended customer-facing expressions of recanvass status.

**Per-dish "Last verified" label:**  
Every dish card shows "Last verified: [Month Year]" derived from the restaurant's `Last_Canvassed`. This is always visible — not hidden behind an expand or tooltip. Users should not need to go looking for freshness information.

**Confidence indicator:**  
A subtle visual indicator accompanies derived filter results:
- `current` — no indicator (clean)
- `due_soon` — no customer-facing indicator (internal signal only)
- `overdue` — "Information may be outdated" label next to derived filter results; "Last verified" date shown prominently
- `needs_review` — derived filter results hidden; "Verification in progress" shown in their place

**Admin / canvasser dashboard:**  
A sorted table of all restaurants by `Recanvass_Status` and days overdue. Restaurants `needs_review` are shown at the top in red. `overdue` in amber. A one-click "Mark for recanvass" action queues a restaurant for the next canvass cycle.

**Long-term — customer trust signal:**  
GoldPan's value proposition depends on customers trusting the data. A public-facing "How current is this information?" page — describing the recanvass policy, typical verification frequency, and the distinction between "No [X] Identified" and "[X]-Free" — builds the trust that makes derived filters useful rather than dangerous.

---

## What Recanvassing Does Not Cover

Recanvassing confirms that GoldPan's data matches the restaurant's published menu. It does not cover:

- **Kitchen practices** — cross-contact, shared fryers, preparation variation by shift
- **Seasonal or daily specials** not listed on the primary menu source
- **Off-menu modifications** the restaurant may accommodate
- **Ingredient supply chain changes** the restaurant has not disclosed on their menu

These are documented in the standard limitation language of individual derived filters and in GP-RULE-002 and GP-RULE-003. Recanvassing improves the freshness of what GoldPan can verify — it does not expand what GoldPan claims to verify.
