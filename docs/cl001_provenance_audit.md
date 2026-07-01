# CL-001 Provenance Audit Report
## Ingredient_Source Cleanup — Phase 1

**Date:** 2026-06-30
**Rule:** GP-RULE-010 (Source Authority Hierarchy) / GP-RULE-011 (Evidence Provenance)
**Scope:** 236 dishes with non-canonical Ingredient_Source values blocking derived filter computation

---

## Root Cause

The `Ingredient_Source` field in Ingredient Details records the **acquisition channel** for the data
(e.g. `menu`, `website`, `allergen_guide`). In the pre-staging era, this field was populated with
**ingredient category/type values** instead — describing what the ingredient IS, not where the data
came from. These non-canonical values do not satisfy the `macro_dependent` evidence dependency and
cause the engine to return `Unknown (dependency not met)` for all macro filters.

**Non-canonical values found and their intended meaning:**

| Value found | What it describes | What it should be |
|------------|------------------|-------------------|
| `plant-based` | ingredient category | `menu` / `website` |
| `dairy` | ingredient category | `menu` / `website` |
| `animal` | ingredient category | `menu` / `website` |
| `animal-based` | ingredient category | `menu` / `website` |
| `seafood` | ingredient category | `menu` / `website` |
| `house` | preparation style | `menu` (house-made, listed on menu) |
| `neutral` | ingredient category | `menu` / `website` |
| `organic` | production claim | `menu` / `website` |
| `grass-fed` | production claim | `menu` / `website` |
| `unknown` | provenance unknown | leave blank or canvass to determine |

---

## Before State (2026-06-30)

| Category | Count |
|---------|-------|
| "Dependency not met" Unknowns — no ingredient data | 59 dishes |
| "Dependency not met" Unknowns — bad Ingredient_Source | 236 dishes |
| **Total dependency-not-met Unknowns** | **295 dishes** |
| No Beef Identified — computed | 386 dishes |
| No Pork Identified — computed | 353 dishes |

---

## Safety Classification

**Criterion:** A correction is safe only when a staging file exists for the dish. The staging file
is the documented evidence that ingredients were captured from the restaurant's published menu.
Dishes without staging evidence cannot have provenance assumed — they require manual re-canvassing.

### SAFE TO UPDATE — 28 dishes (2 restaurants)

Both restaurants have staging files that confirm menu-based canvassing.

#### Eli's Jerusalem Grill — 14 dishes — `staging_elis.json`

| Dish ID | Dish Name | Bad Source(s) |
|---------|-----------|--------------|
| D316 | Homemade Pita Bread | house |
| D317 | Homemade Pita Chips | house |
| D327 | Salad Sampler | house |
| D328 | Chicken Shawarma | house, organic |
| D330 | Chicken Kabob | house, organic |
| D331 | Chicken Tenders | organic |
| D333 | Beef & Lamb Shawarma | grass-fed, house |
| D334 | Beef Kabob | grass-fed, house |
| D335 | Lamb Kabob | grass-fed, house |
| D338 | Mixed Shawarma Plate | grass-fed, house, organic |
| D340 | Combination Plate | grass-fed, house, organic |
| D342 | Vegetarian & Vegan Plate | house |
| D347 | French Fries | organic |
| D348 | Sweet Potato Fries | organic |

Note: `house`, `organic`, `grass-fed` describe production characteristics, not the data source.
These ingredients are listed on Eli's menu — the staging file confirms this.

#### The Essential — 14 dishes — `staging_essential_dinner_backup.json`

| Dish ID | Dish Name | Bad Source(s) |
|---------|-----------|--------------|
| D097 | Arancini | dairy, plant-based |
| D098 | Hummus + Pickles | plant-based |
| D099 | Mushroom Toast | dairy, plant-based |
| D100 | Beef Carpaccio | animal-based, plant-based |
| D101 | Salmon Waldorf Salad | dairy, plant-based, seafood |
| D102 | Caprese Salad | dairy, plant-based |
| D103 | Agnolotti Pomodoro | dairy, plant-based |
| D104 | Spaghetti | dairy, plant-based |
| D105 | Casarecce | dairy, plant-based |
| D106 | Canestri | plant-based, seafood |
| D107 | Rainbow Trout | dairy, plant-based, seafood |
| D108 | Half Chicken Piri Piri | animal-based, plant-based |
| D109 | Bistro Steak | animal-based, plant-based |
| D110 | Rigatoni | animal-based, dairy, plant-based |

---

### NOT SAFE — 208 dishes (13 restaurants)

No staging file exists, and no patch script provides documented menu provenance for these dish IDs.
These dishes were loaded in the pre-staging era; their ingredient source cannot be established
without re-canvassing from the live menu.

| Restaurant | Dishes | Reason |
|-----------|--------|--------|
| Kale Me Crazy | 49 | No staging file; no patch provenance |
| SoHo Standard | 37 | No staging file |
| Yo Chef Surf & Turf Smokehouse | 28 | No staging file |
| Brick & Tin Mountain Brook | 14 | Patch covers only D015/D111; D113-D125 undocumented |
| Real & Rosemary | 20 | No staging file |
| The Essential (older batch) | 13 | D084-D096 predate staging_essential_dinner_backup.json |
| Emmy Squared | 21 | Pre-staging; CANVASSED_DISHES entries marked source=Unknown |
| Adam and Eve Cafe | 10 | Patch covers D064-D083; D038-D042 undocumented |
| Chopt Creative Salad Co. | 5 | Pre-staging dish IDs (D033-D037); staging covers D686+ |
| Clean Eatz | 5 | Pre-staging dish IDs (D058-D062); staging covers D715+ |
| East West | 3 | Pre-staging dish IDs (D048-D050); staging covers D471+ |
| Chop N Fresh | 1 | D043 predates staging; staging covers D044+ |
| Slutty Vegan | 2 | D029/D031 not in staging (covers D028/D030/D032/D681-D685) |

**Resolution path:** Re-canvass these dishes from their live menus during the next scheduled
recanvass cycle. Capture `Ingredient_Source = "menu"` with provenance date. Until then, these
dishes correctly surface as `Unknown` — the system is accurately reflecting the evidence gap.

---

## Phase 2 Action

**Script:** `fix_ingredient_source.py`
**Scope:** 28 safe dishes only (Eli's Jerusalem Grill + The Essential)
**Change:** Set `Ingredient_Source = "menu"` for all ingredient rows belonging to these dish IDs
**Evidence:** Staging file confirms menu-based canvassing for each dish

**Do not touch:**
- Ingredient Name, Cut_Type, Preparation, Ingredient_Type, or any other field
- The 208 unsafe dishes
- The 59 dishes with no ingredient data at all

---

*Report generated 2026-06-30. GP-RULE-010 v1.0, GP-RULE-011 v1.0.*
