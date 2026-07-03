# GoldPan™ Coverage Philosophy
**Version:** 1.1  
**Date:** 2026-07-03  
**Status:** Governing — all Intake OS design decisions are subordinate to this document

---

## The Foundational Principle

**GoldPan™ is not collecting restaurants. GoldPan™ is collecting dietary value.**

This distinction governs every intake decision GoldPan makes. A restaurant is not in GoldPan because it applied, partnered, or agreed to participate. A restaurant is in GoldPan because its public presence contains enough dietary signal to create meaningful value for a user.

The question a canvasser must always ask is not "does this restaurant want to be in GoldPan?" The question is: **"does this restaurant's public presence emit enough dietary signal to create meaningful value for a GoldPan user?"**

---

## Dietary Signal

**GoldPan™ does not evaluate restaurants solely by the amount of information they publish. GoldPan™ evaluates the dietary signal emitted by a restaurant's public presence.**

A dietary signal is any observable characteristic that meaningfully communicates dietary value to a user. Signal is not the same as disclosure. A restaurant can emit strong dietary signal without a formal allergen guide. A restaurant can publish extensive information and emit weak dietary signal if that information tells users nothing meaningful about what they can eat.

Dietary signals may be:

- **Explicit** — direct ingredient or allergen disclosure, nutrition information, labeled dietary certifications
- **Implicit** — a menu structure that reveals dietary intent, the presence of dedicated vegan or gluten-free sections, language that reflects ingredient awareness
- **Preparation-oriented** — descriptions of how food is made that allow dietary inference (scratch cooking, named oils, specific cooking methods)
- **Sourcing-oriented** — identifiable ingredient sourcing that communicates quality and specificity
- **Community-oriented** — a restaurant built around a dietary community's needs, where the entire concept is the signal
- **Transparency-oriented** — a demonstrated willingness to answer dietary questions, even when answers are not pre-published

**The stronger the dietary signal, the stronger GoldPan's justification for coverage — and the more evidence GoldPan can produce from that signal.**

Dietary Signal is the mechanism behind every coverage decision GoldPan makes. The five dimensions of dietary value described below are not independent criteria. They are five different forms dietary signal can take.

### The GoldPan Value Chain

Every restaurant that enters GoldPan follows this chain:

```
Restaurant
    ↓
Dietary Signal        ← Does the public presence emit meaningful dietary signal?
    ↓
Coverage Decision     ← Is the signal strong enough to create user value?
    ↓
Evidence Collection   ← What can we document from available sources?
    ↓
Confidence            ← How certain are we in the conclusions we can draw?
    ↓
Publishing            ← What does the user see, and how is uncertainty communicated?
```

Dietary Signal is the first evaluation. Everything downstream — evidence collection, confidence levels, publishing standards — flows from what signal the restaurant emits and how much of that signal GoldPan can convert into documented evidence.

---

## The Architectural Principle

> **Coverage is determined by diversified dietary value and public dietary signal — not by partnership status or restaurant confirmation.**
>
> Restaurant confirmation is a later-stage enhancement that increases confidence, expands available evidence, and improves the customer experience. It is never the prerequisite for creating value.

This principle has two direct implications for how the Intake OS is designed:

**1. A restaurant can be published on public menu data alone.** If a restaurant's publicly available menu contains meaningful dietary signal, that is sufficient to produce a GoldPan record. The evidence tier will be lower and the confidence in specific conclusions will reflect that — but the value to the user is real. They learn this restaurant exists. They understand what it broadly offers. That is a GoldPan outcome.

**2. Confirmation moves a restaurant up the evidence tiers — it does not move it into GoldPan.** Allergen guides, ingredient-level disclosure, staff verification, and certified sourcing information all increase the precision and confidence of GoldPan conclusions. They are always pursued. They are never required before coverage begins.

---

## The Five Dimensions of Dietary Value

Dietary signal takes five forms. GoldPan evaluates every prospective restaurant across all five. A restaurant does not need to score highly on all five — strong signal in one or two dimensions is often sufficient for meaningful coverage.

### 1. Transparency Value

The restaurant publicly discloses information about what is in its food. This is the dimension most directly convertible to GoldPan evidence.

Transparency signals include:
- Ingredient disclosure on the menu or website
- Allergen disclosure (formal or informal)
- Nutrition information
- Preparation method description
- Substitution options and their implications
- Specificity of public menu language (e.g., "sautéed in olive oil" vs. "cooked")

A restaurant with high Transparency Value gives GoldPan something to work with. A restaurant with low Transparency Value may still have strong signal in other dimensions — but the evidence will be thinner and conclusions more limited until confirmation occurs.

### 2. Diversified Dietary Value

The restaurant's menu genuinely serves multiple dietary patterns or communities. GoldPan is most useful when it surfaces restaurants that a dietary-conscious user might not otherwise know about.

Dietary patterns GoldPan tracks include (but are not limited to):
- Vegan
- Vegetarian
- Pescatarian
- Paleo
- Keto
- Gluten-conscious
- Dairy-conscious
- Halal
- Kosher
- Allergy-friendly
- Whole-food / minimally processed
- Nut-free
- Soy-free
- And many others

**This taxonomy is intentionally expandable.** GoldPan's dietary vocabulary grows as user needs and cultural dietary patterns evolve. No list is final. A canvasser who encounters a dietary pattern not yet in the taxonomy should surface it rather than suppress it.

A restaurant that serves several of these patterns — even without formal certification or disclosure — has high Diversified Dietary Value. Its menu is already doing meaningful work for multiple communities.

### 3. Ingredient Quality Value

The restaurant demonstrates care about what goes into its food. Restaurants that emphasize fresh ingredients, whole foods, scratch preparation, ingredient specificity, or high-quality sourcing tend to produce significantly more useful GoldPan evidence — because they think carefully about their ingredients and often communicate about them.

Ingredient quality is not a social class signal. A neighborhood restaurant that makes everything from scratch with named ingredients has higher Ingredient Quality Value than an expensive restaurant that lists vague menu descriptions. GoldPan evaluates quality of ingredient relationship, not price point.

Ingredient Quality Value also predicts confirmation success: restaurants that care about their ingredients are more likely to be able to answer specific questions about them when canvassers reach out.

### 4. Community Value

Some restaurants intentionally serve communities with specific dietary, religious, ethical, cultural, or medical needs. These restaurants have unique value because they provide options that many customers struggle to find in mainstream dining.

Community Value is distinct from Diversified Dietary Value because it reflects intentionality. A Halal restaurant is not just a restaurant that happens to serve a dietary pattern — it is a restaurant built around a community's needs. A restaurant that caters to food allergy families is not just allergy-friendly — it has made allergy safety part of its identity.

Restaurants with high Community Value deserve prioritized coverage because the communities they serve are most likely to actively need what GoldPan provides.

### 5. Discovery Value

One of GoldPan's core missions is surfacing restaurants that people with dietary needs would never find through conventional recommendation systems.

Discovery Value is present when:
- A restaurant has high dietary value but low public visibility
- A restaurant serves a community that is underrepresented in mainstream food media
- A restaurant exists in a neighborhood or context that typical food discovery tools overlook
- A restaurant has been operating for years without being "discovered" by the dining mainstream

Discovery is itself a GoldPan outcome. When a GoldPan user finds a restaurant through the platform that they otherwise never would have encountered — and that restaurant meets their dietary needs — GoldPan has delivered its full promise, regardless of the evidence tier.

---

## What This Means for Coverage Decisions

### A restaurant belongs in GoldPan if:
Its public presence contains meaningful signal in one or more of the five value dimensions — and that signal can be documented in a way that produces value for at least one GoldPan user.

### A restaurant does not belong in GoldPan if:
Its public presence contains no dietary signal that GoldPan can document, regardless of how popular, well-reviewed, or socially prominent the restaurant is. A famous restaurant with a generic menu and no dietary information is not a GoldPan restaurant.

### A restaurant's coverage tier reflects its evidence, not its value:
A restaurant with exceptional Community Value and Discovery Value but only public menu data available is still a valuable GoldPan record — it will simply have `inferred` or `unknown` conclusions for many filters until confirmation occurs. The coverage decision is separate from the confidence level. Both are communicated honestly to the user.

---

## What This Means for Confirmation

Confirmation is the process of obtaining evidence beyond what is publicly available — through direct restaurant contact, allergen guides, staff interviews, certification verification, or other primary sources.

Confirmation always improves GoldPan records. It is always pursued when resources allow. It is the primary mechanism for advancing a restaurant's evidence tier.

But confirmation is never a prerequisite for coverage. A canvasser who discovers a restaurant with exceptional dietary value should bring it into GoldPan immediately, at whatever evidence tier the public record supports. Confirmation follows coverage — not the other way around.

**The wrong mental model:**  
*"We'll add this restaurant once we can confirm their allergen information."*

**The right mental model:**  
*"This restaurant has real dietary value. We'll add it now with what we know. We'll confirm what we can. The user gets value either way."*

---

## How This Document Relates to the Intake OS

Every subsystem of the GoldPan Intake OS — Restaurant Onboarding, Evidence Acquisition, Dish Capture, Verification, Freshness Management, Quality Assurance, AI-Assisted Extraction, and the Publishing Pipeline — is designed to serve this philosophy.

The Intake OS does not exist to enforce bureaucratic gates. It exists to ensure that every restaurant that enters GoldPan delivers the dietary value that justified its coverage — and that every user who encounters that restaurant gets an honest, evidence-grounded representation of what GoldPan knows.

This philosophy is the answer to the question every canvasser will eventually face:

**"I found a restaurant. Does it belong in GoldPan?"**

The answer is not found in a checklist. It is found by asking: *does this restaurant's public presence contain dietary value that a GoldPan user deserves to know about?*

If yes — it belongs.
