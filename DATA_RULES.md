# Goldpan Data Rules

This file is the authoritative rule set for the Goldpan database and software pipeline.
It covers business/database rules and software engineering rules in clearly separated sections.

For non-technical canvassing guidance, see the **Canvassing Standards** tab in the Google Sheet.

---

## PART 1 — DATABASE RULES
*What belongs in Goldpan's data system and how it must be structured.*

---

### R1 — Restaurant Inclusion

**R1.1** A restaurant must be located in the Birmingham, AL metro area (including Mountain Brook, Homewood, Hoover, Vestavia Hills, and adjacent municipalities).

**R1.2** A restaurant must have a publicly accessible, current menu. If no verifiable menu source exists, the restaurant cannot be onboarded.

**R1.3** A restaurant must be confirmed open and operating before canvassing begins. Restaurants listed as "Needs Review" in the Menu Source Registry must not be canvassed until their status is resolved.

**R1.4** Chain restaurants may be included when the Birmingham-area location has meaningful local menu variation or allergen transparency not covered by national databases.

**R1.5** The Menu Source Registry entry must be completed and validated before any restaurant enters the dish-level data process.

---

### R2 — Dish Inclusion

**R2.1** A dish may only be created from a current, verified live menu. Supporting documents may enrich an existing dish but may never create one.

**R2.2** Every dish in a staging file must carry `"menu_verified": true` — the canvasser's attestation that the dish was confirmed on the live menu. `upsert_dishes.py` blocks if this field is missing.

**R2.3** Dishes that leave the menu are marked `Status = Inactive`, never deleted. Inactive dishes are excluded from the public site but preserved in the database for historical reference. The build validation treats them as accounted for.

**R2.4** If a dish is renamed, update the existing Dish_ID. Do not create a new ID for a rename.

**R2.5** Duplicate dishes (same restaurant, same name) are not permitted. The deduplication rule in `fetch_dishes.py` keeps the entry with the most ingredient data and drops the other.

---

### R3 — Side Item Policy

**R3.1** Include side items only when they provide meaningful transparency value: verified dietary tags, allergen data, ingredient information, preparation details, or dietary classifications.

**R3.2** Do not include a side item that only has a name and a price. A name and price provide no transparency value.

**R3.3** Excluded sides may be added later when transparency data becomes available through recanvassing or an official allergen source.

**R3.4** The goal is not to catalog every menu item. The goal is to maintain a high-quality transparency database. When in doubt, exclude a side until its transparency data can be confirmed.

**Examples — include:** sweet potato fries (vegan, GF confirmed), mac & cheese (wheat, dairy declared), house salad with ingredient list.
**Examples — exclude:** "Side salad — $4" (name and price only), "Side of rice" (no data of any kind).

---

### R4 — Beverage Policy

**R4.1** Standard beverages (soft drinks, coffee, tea, water, alcohol) are excluded.

**R4.2** Specialty beverages with disclosed ingredients may be included: smoothies, açaí drinks, protein drinks, house-made juices with ingredient or allergen data.

**R4.3** If a beverage is included, the same `menu_verified: true` and dish inclusion standards apply.

---

### R5 — Dietary Tag Definitions

Tags are applied only when the dish is confirmed to meet the definition — not assumed from the dish name.

| Tag | Definition |
|-----|------------|
| vegan | No animal products (no meat, fish, dairy, eggs, honey) |
| vegetarian | No meat or fish. May contain dairy or eggs |
| gluten-free | No gluten-containing ingredients, confirmed by the restaurant. Note cross-contact risk where applicable |
| dairy-free | No dairy ingredients. Note if kitchen processes dairy |
| nut-free | No tree nuts or peanuts. Note if kitchen processes nuts |
| high-protein | 30g+ protein per serving from disclosed nutrition data, or clearly protein-forward dish confirmed from menu |
| low-carb | Confirmed from nutrition data or explicit menu designation. Do not infer from ingredient lists alone |

Tags reflect the dish as served. Add-ons and modifications are not reflected in base tags.

---

### R6 — Allergen Standards

**R6.1** Allergen data must come from an official source: restaurant's own allergen guide, menu page, staff confirmation, or published nutrition document.

**R6.2** The Big 9 allergens are the primary focus: milk, eggs, fish, shellfish, tree nuts, peanuts, wheat/gluten, soy, sesame.

**R6.3** Additional allergens may be noted when confirmed from official sources: allium/garlic, nightshades, sulfites, citrus, mushrooms.

**R6.4** If allergen data is unavailable, `Allergen_summary` is set to `Unknown`. Do not guess or infer allergens from dish names alone.

**R6.5** If the kitchen processes a major allergen, include a cross-contact note even if the dish itself does not contain that allergen.

**R6.6** Ingredient-derived allergen estimates must be labeled as such and flagged for manual verification. Official PDF or menu data supersedes ingredient-derived estimates when the official source is confirmed current.

**R6.7** Data anomalies in source documents (e.g., a fish allergen listed for a pork dish) must be flagged as warnings, not silently written to the database.

---

### R7 — Transparency Scoring

**R7.1** Transparency scoring is private. Scores, sub-scores, scoring criteria, and canvassing notes are never published.

**R7.2** Only the derived transparency level is public: Building, Moderate, or High.

**R7.3** Scores are assigned at the dish level during canvassing and live in the Transparency Scoring tab only.

---

### R8 — Required Fields

| Tab | Required fields |
|-----|----------------|
| Goldpan Dish Level Data | Restaurant_ID, Restaurant, Location, Dish_ID, Dish_Name, Last_Updated, Status |
| Ingredient Details | Dish_ID, Ingredient (at least one row per dish unless genuinely unknown) |
| Transparency Scoring | Restaurant_ID, Restaurant_Name, Dish_ID, Dish_Name, Transparency_Level |
| Menu Source Registry | Restaurant_Name, Official_Website, Official_Menu_URL, Source_Confidence, Preferred_Data_Source, Menu_Status, Canvass_Priority |

---

### R9 — Menu Source Hierarchy

Always use the highest-ranked available source.

1. **Tier 1** — Official website menu page (HTML, current, restaurant-controlled)
2. **Tier 2** — Restaurant's own ordering platform (Toast, Square, ChowNow) when it shows full item descriptions
3. **Tier 3** — Official dated PDF linked from the restaurant's own website
4. **Tier 4** — Official allergen/nutrition PDF from the restaurant's own website *(supporting source — enriches existing dishes; does not create new ones)*

**Not permitted as primary source:** third-party delivery platforms, Yelp, Google Maps, social media, undated PDFs of unknown origin.

---

### R10 — Source Confidence Levels

| Level | Definition |
|-------|------------|
| Official | Sourced directly from the restaurant's own website or platform; URL verified; content confirmed current |
| Third-Party | Sourced from a platform the restaurant uses but does not own (e.g., Toast CDN, GetBento). Content is restaurant-provided but hosting is external |
| Unverified | Link not checked or content currency unknown. Must be verified before canvassing |
| Inferred | No direct source; data derived from ingredient analysis or secondary sources. Must be labeled as such in all database fields |

---

### R11 — Data Freshness & Review Policy

**R11.1** `Last_Updated` reflects the date a dish was recanvassed. It is never bulk-stamped.

**R11.2** Dishes with `Last_Updated` older than 90 days should be flagged as review priority.

**R11.3** The Menu Source Registry `Last_Verified_Date` must be updated each time a source URL is confirmed working.

**R11.4** If a menu source URL is found dead or stale, update the Menu Source Registry immediately and flag the restaurant for recanvassing before writing any new data.

**R11.5** When a seasonal dish leaves the menu, mark it Inactive. When it returns, reactivate and recanvass to confirm ingredients are unchanged before setting it Active again.

---

## PART 2 — SOFTWARE ENGINEERING RULES
*How Goldpan's software and data pipeline must be built and maintained.*

---

### E1 — Data Safety

**E1.1** Never write directly to production data when staging is appropriate. All new restaurant and dish data goes through a staging JSON file, reviewed before upsert.

**E1.2** Staging files are the review checkpoint. A staging file must be readable and auditable before `upsert_dishes.py` runs.

**E1.3** Patch scripts are acceptable for small targeted updates but must be scoped and documented in the script header: source, date, and what changed.

**E1.4** Never overwrite a non-empty field unless the new value is a confirmed correction. When in doubt, append or flag — do not replace.

**E1.5** The `--force` flag on `upsert_dishes.py` bypasses the `menu_verified` gate. It exists only for legacy staging files. Document why it was used if ever invoked.

---

### E2 — Build Gates

**E2.1** `fetch_dishes.py` must not produce output if validation fails. It exits with a non-zero status and a clear error report.

**E2.2** Required validation gates (in order):
1. Menu Source Registry coverage — every restaurant in Transparency Scoring must have a registry entry
2. Dish Level Data coverage — every scored dish must have a Dish Level Data row or be marked Inactive

**E2.3** Build gates produce a report showing exactly what is missing and which script to run to fix it. Never silently skip a validation failure.

**E2.4** A build that passes all gates but produces zero dishes is a failure. Validate output record count.

---

### E3 — Staging Pipeline

**E3.1** Canonical pipeline order:
```
Canvass live menu
→ staging JSON (menu_verified: true on every dish)
→ python3 upsert_dishes.py [staging_file.json]
→ python3 fetch_dishes.py
→ bash update.sh
```

**E3.2** Allergen and nutritional PDFs are applied after the dish exists in the database. Patch scripts only update existing rows — they never create new rows from PDF data alone.

**E3.3** Staging files must be kept after use. They are the audit trail for what was added and when. Do not delete staging files.

---

### E4 — Debugging Protocol

If data is missing from the site, diagnose in this order before writing any fix:

1. Is the row missing from **Transparency Scoring**?
2. Is it missing from **Goldpan Dish Level Data**?
3. Did the **upsert** run successfully?
4. Did **`fetch_dishes.py`** run and produce output?
5. Is there a **frontend mapping** issue (wrong field name, missing field)?
6. Is the deployment **stale or cached**?

**Do not write a cleanup patch until the failure stage is identified.** Patching the wrong layer wastes effort and introduces new risk.

---

### E5 — Error & Warning Reporting

**E5.1** Every script that writes to the database or produces an output file must print: script name, date, what it did, and how many records were affected.

**E5.2** Warnings allow the script to continue. Errors stop execution. Both must be printed clearly.

**E5.3** Data anomalies found during processing must be printed as warnings with the source cited. Never silently write anomalous data.

**E5.4** Scripts that touch the Google Sheet must confirm the number of rows written at completion.

---

### E6 — Naming Conventions

| Thing | Convention |
|-------|-----------|
| Scripts | `snake_case`, prefixed with action: `fetch_`, `patch_`, `upsert_`, `create_`, `insert_`, `update_`, `verify_` |
| Staging files | `staging_[restaurantname].json` — lowercase, no spaces |
| Addendum files | `staging_[restaurantname]_addendum.json` |
| Dish IDs | `D` + integer (`D001`, `D099`, `D100`, `D1000`). Never reuse a Dish_ID |
| Restaurant IDs | `R` + zero-padded integer (`R001`, `R025`). Never reuse |
| Sheet tab names | Title Case with spaces. Must match exactly across all scripts — mismatches cause silent failures |

---

### E7 — JSON Schema Standards

**E7.1** Every staging file must include: `restaurant_id`, `restaurant_name`, `location`, `restaurant_address`, `restaurant_website`, `hours`, `menu_link`, `dishes` array.

**E7.2** Every dish object must include: `dish_id`, `dish_name`, `menu_verified` (must be `true`), `dietary_tags`, `allergen_summary`, `ingredients` array.

**E7.3** Optional dish fields: `menu_price`, `category`, `dietary_options`, `core_clarity`, `sauce_disclosure`, `allergen_transparency`, `prep_clarity`, `total_score`, `transparency_level`, `notes`.

**E7.4** Do not add fields to staging files that are not read by `upsert_dishes.py`. Unknown fields are silently ignored and create confusion.

---

### E8 — Deployment Checklist

**Before `bash update.sh`:**
- [ ] All patch/upsert scripts for this session have been run
- [ ] `fetch_dishes.py` validation passes (zero errors; warnings understood)
- [ ] Output dish count is consistent with expectations

**After `bash update.sh`:**
- [ ] `dishes.json` and `restaurants.json` timestamps updated
- [ ] Spot-check 2–3 dishes on the live site
- [ ] Confirm map and filter UI still function

Never run `bash update.sh` without first running `fetch_dishes.py` locally to confirm the build is clean.

---

### E9 — Post-Build Verification

**E9.1** After every deployment, verify: a recently updated dish appears correctly on the public site, `restaurants.json` was updated, and the filter/tag UI reflects any new tags.

**E9.2** Spot-check a restaurant that was recanvassed this session — confirm allergen and ingredient data is visible.

**E9.3** If the site does not reflect changes after deployment, check in this order: CDN/cache → GitHub Pages build status → `dishes.json` content → `fetch_dishes.py` output.

---

### E10 — Logging Expectations

**E10.1** Every script that writes to the database or produces an output file must log: script name, date, action taken, records affected.

**E10.2** Patch scripts must log the source document being applied (URL, date of document) in both the script header and terminal output.

**E10.3** `upsert_dishes.py` logs: staging file name, restaurant, dish count, ingredient count, per-tab results (added/updated).

---

*Last updated: June 2026*
