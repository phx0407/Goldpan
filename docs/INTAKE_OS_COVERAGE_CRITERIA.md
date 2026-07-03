# GoldPan Intake OS — Coverage Criteria
**Version:** 1.0  
**Date:** 2026-07-03  
**Governs:** Prospect qualification decisions — the transition from `prospect` to `qualified` or `rejected`  
**Governed by:** GOLDPAN_COVERAGE_PHILOSOPHY.md — all criteria in this document are operationalizations of that philosophy

---

## Purpose

This document converts the Coverage Philosophy's governing principle into a concrete decision framework that a canvasser can apply. Every prospect that enters GoldPan must be evaluated against these criteria. Coverage is approved when all Gate Criteria pass and at least one Signal Criterion is documented.

The Coverage Philosophy answers: **why does a restaurant belong in GoldPan?**  
This document answers: **how do we decide if a specific restaurant belongs?**

---

## Coverage Decision Framework

### Step 1 — Gate Criteria

All three Gate Criteria must pass. If any gate fails, the restaurant is `rejected` regardless of dietary value. Gate failures are operational constraints, not judgments about a restaurant's worth.

| Gate | Criterion | Pass | Fail |
|------|-----------|------|------|
| G1 | **Currently operating** | Restaurant is open to the public | Permanently closed, or seasonal and not currently in season |
| G2 | **Menu accessible** | At least one itemized menu source exists (restaurant website, PDF, third-party platform) | No accessible menu of any kind |
| G3 | **Active coverage area** | Restaurant is within GoldPan's current geographic scope | Outside active coverage area |

> **G3 Note — Coverage Area:** Geographic scope is defined by GoldPan market strategy, not this document. Canvassers should maintain a current list of active coverage areas. When scope is uncertain, escalate — do not reject or approve on geographic uncertainty alone.

A Gate failure is never permanent. A closed restaurant that reopens is a new `prospect`. A restaurant outside current coverage may qualify when scope expands.

---

### Step 2 — Signal Criteria

At least one Signal Criterion must be documented. The canvasser identifies which dimension(s) are present, and records the specific evidence that demonstrates the signal.

Signal Criteria operationalize the [Five Dimensions of Dietary Value](./GOLDPAN_COVERAGE_PHILOSOPHY.md) from the Coverage Philosophy.

---

**S1 — Transparency Signal**  
The restaurant's public presence contains explicit dietary language beyond dish names alone.

Qualifying evidence includes:
- Allergen disclosure (formal guide, informal notation, or labeled menu items)
- Ingredient disclosure (specific named ingredients in menu descriptions)
- Preparation method description that enables dietary inference (e.g., "sautéed in olive oil," "made with almond flour")
- Substitution options with stated dietary implications
- Specificity of language that signals ingredient awareness (e.g., "grass-fed beef," "dairy-free bun available")

**Not qualifying:** generic dish names without any dietary language ("grilled chicken," "pasta with sauce").

---

**S2 — Diversified Dietary Signal**  
The menu demonstrably serves two or more dietary patterns. Signal is structural or content-based — what the menu reveals about who it is designed to feed.

Qualifying evidence includes:
- Dedicated sections for a dietary pattern (vegan section, gluten-free menu, Halal-only items labeled)
- A menu composition where the canvasser can identify meaningful options for multiple dietary communities
- Explicit dietary labeling on individual dishes (V, VG, GF, DF notations, etc.)

**Not qualifying:** a restaurant that happens to have one vegan item with no labeling and no intent — unless that item's presence is itself meaningful in context.

---

**S3 — Ingredient Quality Signal**  
The restaurant demonstrates a relationship with its ingredients that produces usable GoldPan evidence.

Qualifying evidence includes:
- Scratch cooking (stated in menu, website, or About section)
- Named sourcing ("local farms," "heritage breed pork," specific farm or supplier named)
- Ingredient-level specificity in menu descriptions (the restaurant thinks in ingredients, not just dish categories)
- Visible menu philosophy that prioritizes ingredient transparency

**Not qualifying:** generic quality language ("fresh ingredients," "made with care") without specificity.

---

**S4 — Community Signal**  
The restaurant's concept, name, branding, or positioning indicates it is intentionally built around a specific dietary, religious, ethical, or medical community's needs.

Qualifying evidence includes:
- Restaurant concept is explicitly built around a dietary pattern (all-vegan restaurant, Halal butcher and café, dedicated allergen-safe kitchen)
- Religious dietary certification that defines the restaurant's identity (Kosher-certified, Halal-certified)
- Restaurant markets itself to or is known within a specific dietary community
- Restaurant's About page, name, or concept explicitly references a dietary mission

**Community Signal is the strongest single-dimension justification for coverage** because the community's needs are exactly what GoldPan exists to serve.

---

**S5 — Discovery Signal**  
The restaurant has meaningful dietary value for GoldPan users but low visibility in conventional recommendation systems.

Discovery Signal is often a multiplier on other signals — a restaurant with S1 and S5 together has high coverage priority — but it can also justify coverage on its own when the restaurant's value to dietary-conscious users is clear even if its public presence is thin.

Qualifying evidence includes:
- Strong community presence (known within a dietary community, recommended in dietary-focused forums or groups) despite limited public web presence
- High dietary value observable from in-person visit or community knowledge
- Restaurant exists in a neighborhood underrepresented in mainstream food media
- Restaurant has been operating for years without appearing in conventional food discovery tools

> **Discovery Signal requires a documented reason.** The canvasser must state specifically what makes this restaurant valuable for GoldPan users to discover. "It seems like a good place" is not a documented Discovery Signal.

---

### Step 3 — Coverage Rationale

Before any prospect is approved, the canvasser records:

1. **Which Signal Criterion (or criteria) justified coverage** — S1, S2, S3, S4, S5, or a combination
2. **The specific evidence that demonstrates the signal** — a sentence or two that describes what the canvasser observed from the restaurant's public presence
3. **The source of that evidence** — where the canvasser saw it (URL, third-party platform, community knowledge)

This becomes the permanent record of why GoldPan is covering this restaurant. It is stored in the `Coverage_Signal` field of the Restaurant_Registry.

**Example Coverage Rationale:**  
*"S1 + S4 — Restaurant's menu lists allergen flags (G, D, N, S) on every dish. Restaurant's name and About page explicitly identify as an allergen-safe kitchen founded by a parent of a child with multiple food allergies. Community Signal is core to the restaurant's identity."*

---

## Rejection Criteria

A restaurant is `rejected` if:
- Any Gate Criterion fails (operational constraint — not a judgment on value)
- All Signal Criteria are evaluated and none is present — the public presence contains no dietary signal that GoldPan can document

**Rejection is rare when evaluation is genuine.** Most restaurants that make it to canvasser review have some dietary signal. The canvasser's job is to find and document it, not to look for reasons to exclude. If a canvasser cannot find any signal, that finding should itself be documented before rejecting.

> A famous, highly-rated restaurant with a generic menu and no dietary language is not a GoldPan restaurant. Popularity is not dietary signal.

---

## No Minimum Dish Count

There is no hard minimum dish count for coverage. A restaurant with three dishes can qualify if the signal is present and the evidence can produce value for at least one GoldPan user. A restaurant with eighty dishes does not automatically qualify.

The relevant threshold is: **can the canvasser produce at least one GoldPan record (one dish with at least one meaningful dietary conclusion) that is useful to a user?** If yes, the dish count is sufficient.

---

## Coverage Is Not Permanent

Coverage approval (`prospect` → `qualified`) is based on the public presence at the time of evaluation. If a restaurant's menu or public presence changes materially, the coverage rationale should be reassessed at the next recanvassing cycle. A restaurant that loses its dietary signal may eventually be `deactivated` if evidence can no longer be maintained to GoldPan standards.

---

## Relationship to Other Intake OS Documents

- **GOLDPAN_COVERAGE_PHILOSOPHY.md** — the governing philosophy behind every criterion in this document
- **INTAKE_OS_RESTAURANT_LIFECYCLE.md** — defines the lifecycle stages; this document governs the `prospect → qualified` transition
- **INTAKE_OS_RESTAURANT_REGISTRY.md** — Coverage_Signal, Coverage_Approved_By, and Coverage_Approved_Date are recorded here upon qualification
- **INTAKE_OS_RESTAURANT_ONBOARDING.md** _(forthcoming)_ — the next stage after `qualified`

---

## Open Questions

1. **Geographic scope definition** — What specific neighborhoods, cities, or regions constitute GoldPan's active coverage area? This needs to be defined as a separate policy or maintained as a canvasser reference list.
2. **Seasonal restaurants** — A restaurant that is seasonal-only qualifies when in season. What is the protocol when a canvasser discovers a restaurant during off-season? (Suggest: add as `prospect`, note seasonal status, hold at `qualified` until season opens.)
3. **Rejection re-evaluation** — How long before a rejected restaurant can be re-submitted as a prospect? (Suggest: 6 months minimum, or when the canvasser documents a material change in public presence.)
