# GoldPan Intake OS — Restaurant Onboarding
**Version:** 1.0  
**Date:** 2026-07-03  
**Lifecycle Stage:** `onboarding` — begins when a canvasser is assigned a `qualified` restaurant and ends when all menu sources are documented and the restaurant is ready for evidence acquisition  
**Governed by:** GOLDPAN_COVERAGE_PHILOSOPHY.md, INTAKE_OS_RESTAURANT_LIFECYCLE.md

---

## Purpose

Restaurant Onboarding is the setup stage. Its job is not to collect dietary evidence — that happens in evidence_acquisition. Its job is to answer four questions before evidence work begins:

1. Is the restaurant currently operating?
2. Where does its menu information live?
3. How reliable are those sources?
4. Does any source contain dietary disclosure that will shape the evidence strategy?

A canvasser who completes onboarding correctly gives the evidence_acquisition stage a clear map: here are the sources, here are their tiers, here is what dietary disclosure exists. Evidence work does not begin until that map is in place.

---

## Onboarding Checklist

The checklist is sequential. Each step must be completed before moving to the next. Steps 1–3 are administrative setup. Steps 4–6 are source work. Step 7 is the exit gate.

---

### Step 1 — Assign Restaurant_ID

Generate the next available unique `Restaurant_ID` using the GoldPan ID assignment system. Record the ID in the Restaurant_Registry row for this restaurant.

**ID assignment must happen at the start of onboarding** — before any source records are created. All records created during onboarding (Menu Source Registry entries, Lifecycle_Events rows) reference the Restaurant_ID. If a Dish_ID or Ingredient_ID is later created, it also references this ID.

> IDs are never typed manually. The ID assignment system generates the next available value. If the system is unavailable, do not improvise — pause onboarding and resolve the system access issue first.

---

### Step 2 — Confirm Operating Status

Verify that the restaurant is currently open to the public before any further work is done. Check at least two sources:

- The restaurant's own website (look for hours, reservation availability, recent announcements)
- Google Business (check "Permanently closed" badge, hours, recent reviews)

**If the restaurant is confirmed closed:** Update lifecycle status to `suspended` or `deactivated` as appropriate (see Lifecycle doc for criteria). Write a Lifecycle_Events row with the reason. Do not proceed with onboarding.

**If operating status is uncertain** (no website, no recent Google activity, no phone answer): Note the uncertainty in the Restaurant_Registry. Attempt one additional check (Yelp, Instagram, direct call if feasible). If still unresolved after two checks, flag for coordinator review before proceeding.

**If the restaurant is confirmed open:** Proceed to Step 3.

---

### Step 3 — Update Lifecycle_Events

Write a row to the Lifecycle_Events log recording the transition from `qualified` to `onboarding`. Include:
- `From_Status`: qualified
- `To_Status`: onboarding
- `Actor`: canvasser name
- `Notes`: optional context (e.g., "Assigned 2026-07-03, operating confirmed via website and Google")

This is the first Lifecycle_Events entry for most restaurants. It establishes the canvasser of record and the onboarding start date.

---

### Step 4 — Locate All Menu Sources

Search systematically for every location where the restaurant's menu information is available. The goal is to find the best available source — not to stop at the first one found.

**Search order (highest to lowest source tier):**

**Tier 1 — Restaurant-Owned Sources**
- The restaurant's own website (look for pages labeled Menu, Food, Eat, Order, or similar)
- PDF menus linked from the restaurant's website
- A dedicated ordering page on the restaurant's own domain (e.g., using Toast, Square, or a branded ordering URL)

**Tier 2 — Authorized Third-Party Sources**
- Yelp (owner-claimed listings — look for the "Owner Verified" indicator)
- Google Business (verified listing)
- Food ordering aggregators where the restaurant has claimed or is listed with current menu data: Caviar, DoorDash, Uber Eats, Grubhub, Toast TakeOut

**Tier 3 — Unverified or Secondary Sources**
- Social media pages: Instagram (look for menu posts, story highlights labeled "Menu"), Facebook (some restaurants post menu photos or have a Menu tab)
- Third-party menu aggregator pages (Allmenus, MenuPix, etc.) where content is user-uploaded or scraped
- Canvasser direct observation (in-person menu photograph)
- Community-reported menus (screenshots from forums, food blogs, etc.)

**What the canvasser is looking for in each source:**
- Is the menu **itemized**? (Dish-level names and descriptions — not just category names or "we serve Italian food")
- Is there any **dietary disclosure**? (Allergen flags, ingredient lists, preparation method descriptions, dietary labels such as V, VG, GF, DF)
- Is it **current**? (Recent updates, current pricing, no "spring 2024" seasonal menus that haven't been refreshed)
- Is it **stable**? (A URL or document that can be bookmarked and returned to — not an ephemeral Instagram story)

**Document every source found**, not just the best one. A restaurant may have an outdated website and a current DoorDash listing. Both are relevant.

---

### Step 5 — Evaluate and Tier Each Source

For every source found, determine its source tier using the definitions from INTAKE_OS_RESTAURANT_REGISTRY.md:

| Tier | Definition |
|------|-----------|
| Tier 1 | Restaurant-owned: restaurant's website, domain-hosted PDF, restaurant-controlled ordering page |
| Tier 2 | Authorized third-party: claimed/verified listing where restaurant-provided data is expected |
| Tier 3 | Unverified third-party or canvasser observation: user-uploaded content, scraped aggregators, social media, direct observation |

**Apply dietary disclosure flags to each source:**
- `Contains_Allergen_Disclosure` — TRUE if the source includes any allergen information (formal guide, dish-level flags, or informal notation)
- `Contains_Ingredient_Detail` — TRUE if the source includes specific ingredient references in menu descriptions

**Assess the overall Evidence Tier** the available sources can support:
- If any source contains confirmed or published allergen/ingredient disclosure → Evidence Tier 2 (Disclosed) or potentially Tier 1 (Confirmed) if restaurant-provided
- If no source contains dietary disclosure, but itemized menu exists → Evidence Tier 3 (Inferred)

---

### Step 6 — Document Sources in the Menu Source Registry

Create one record in the Menu Source Registry for each source found. Each record contains:

| Field | Description |
|-------|-------------|
| `Source_ID` | Unique ID generated by the ID assignment system |
| `Restaurant_ID` | References this restaurant |
| `Source_URL` | Full URL or document path |
| `Source_Type` | `website` / `pdf` / `third-party-platform` / `social-media` / `canvasser-observation` |
| `Source_Tier` | `Tier_1` / `Tier_2` / `Tier_3` |
| `Access_Method` | `direct-link` / `pdf-download` / `requires-login` / `screenshot-required` |
| `Contains_Allergen_Disclosure` | Boolean |
| `Contains_Ingredient_Detail` | Boolean |
| `Date_Documented` | Today's date |
| `Date_Last_Verified` | Today's date (will be updated on recanvassing) |
| `Status` | `active` |
| `Notes` | Any relevant context (e.g., "PDF last updated 2024-12" or "Yelp listing appears outdated — use website instead") |

After all source records are created, update the Restaurant_Registry with:
- `Primary_Source_URL` — the highest-tier source URL
- `Primary_Source_Tier` — the tier of the primary source
- `Has_Allergen_Guide` — TRUE if any source contains allergen disclosure
- `Evidence_Tier` — the highest evidence tier achievable from available sources

---

### Step 7 — Exit Gate

Onboarding is complete when all of the following are true:

- [ ] Restaurant_ID is assigned and recorded in the Restaurant_Registry
- [ ] Operating status is confirmed
- [ ] All accessible sources have been found and documented in the Menu Source Registry
- [ ] At least one source meets the minimum threshold (see below)
- [ ] Restaurant_Registry is updated with Primary_Source_URL, Primary_Source_Tier, Has_Allergen_Guide, and Evidence_Tier
- [ ] Lifecycle_Events row written for `qualified → onboarding` transition

When all conditions are met, update the lifecycle status to `evidence_acquisition` and write a second Lifecycle_Events row for the `onboarding → evidence_acquisition` transition.

---

## Minimum Source Threshold

At least one source must meet the minimum threshold before onboarding can exit:

**Standard exit:** At least one Tier 1 or Tier 2 source with an itemized menu is documented.

**Tier 3 exception:** If no Tier 1 or Tier 2 source exists, the canvasser may proceed with Tier 3 only if:
1. At least one Tier 3 source contains an itemized menu
2. The limitation is documented in the Restaurant_Registry Notes field
3. The Evidence_Tier is set to `Tier_3_Inferred`
4. A note is added to the relevant source record indicating this is the best available source

**Cannot proceed:** If no accessible, itemized menu source exists at any tier, onboarding cannot exit. Update the lifecycle status back to `qualified`, write a Lifecycle_Events row explaining the situation, set `Recanvass_Status = needs_review`, and flag for coordinator follow-up. The restaurant will be re-examined when a source becomes available.

---

## Special Situations

**Restaurant has no website:** Common for neighborhood restaurants and community establishments. Proceed with Tier 2 sources (Yelp, Google, ordering platforms). Document "no website" in Notes. These restaurants often have high Community Value or Discovery Value — the lack of a website does not diminish their GoldPan value.

**Restaurant website exists but menu is not online:** Check all Tier 2 and Tier 3 sources before concluding. Many restaurants post menus on social media even without a web-based menu. If the only available menu is via direct observation, note it as Tier 3 and proceed with the exception protocol above.

**Menu is only in a language other than English:** Document the language in the source record. GoldPan covers restaurants in all languages. Evidence acquisition may require additional care or translation assistance — note this in the Notes field.

**Menu appears outdated:** If the best available source appears to be from more than 12 months ago, flag it in the source record. Document the uncertainty. Evidence acquisition should include a freshness note on extracted evidence.

**Restaurant has a seasonal menu:** Document the current season's menu if available. Note in the source record that menu is seasonal. Set a freshness reminder (see RECANVASSING_POLICY.md) for when the next seasonal menu is expected.

**Source requires login or app download:** If the only available menu source requires creating an account or downloading a third-party app, classify it as `Access_Method = requires-login` in the source record. This is a Tier 3 accessibility situation. Look for alternative sources. If none exist, proceed with documented limitation.

---

## What Onboarding Does NOT Include

Onboarding establishes where information lives — it does not extract or record the information itself. The following actions belong in evidence_acquisition, not onboarding:

- Reading and recording dish names and descriptions
- Creating ingredient rows
- Setting dietary tags or allergen flags
- Recording allergen disclosure data
- Making any dietary conclusion about any dish

If a canvasser notices something significant during source evaluation (e.g., "this restaurant has a full allergen guide PDF"), that observation belongs in the source record notes — not in the evidence system. Evidence acquisition begins after onboarding is complete.

---

## Relationship to Other Intake OS Documents

- **INTAKE_OS_COVERAGE_CRITERIA.md** — coverage was already approved before onboarding begins; the Coverage_Signal rationale is already written
- **INTAKE_OS_RESTAURANT_REGISTRY.md** — onboarding creates and populates the Restaurant_Registry row; the Menu Source Registry schema is defined there
- **INTAKE_OS_RESTAURANT_LIFECYCLE.md** — onboarding is Stage 3; this document defines the canvasser workflow for that stage
- **INTAKE_OS_EVIDENCE_ACQUISITION.md** _(forthcoming)_ — the next stage; depends on the source map this document produces
