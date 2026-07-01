# GoldPan Design Philosophy

**Status:** Canonical — referenced by all architecture documents  
**Date:** 2026-06-30

---

## What GoldPan Is

GoldPan is a food intelligence platform built on a single commitment: every conclusion it communicates to a customer must be traceable to evidence, governed by named rules, and honest about its limits.

This commitment shapes every technical decision GoldPan makes.

---

## The Two Systems

GoldPan operates as two complementary systems. They are deliberately separate. They should never be collapsed together.

**The Evidence System** acquires, preserves, timestamps, attributes, and validates what is known. It records what restaurants disclose — ingredients, allergen claims, dietary labels, menu sources, provenance. It never draws conclusions. Its job is to be a faithful record of what evidence exists and where it came from.

**The Knowledge System** reasons from that evidence. It computes governed conclusions using GoldPan's named rules, produces explanations, assigns confidence, and documents limitations. It never invents evidence. Its job is to answer, responsibly, what the evidence supports.

One system feeds the other. The Evidence System exists first. The Knowledge System exists above it.

---

## Lifecycle: Evidence Is Durable, Knowledge Is Disposable

The Evidence System and Knowledge System do not simply hold different types of data. They have fundamentally different lifecycles.

**Evidence is durable.** It represents observations, disclosures, provenance, and verified facts that GoldPan has acquired from the world. Once recorded with complete provenance, evidence should be preserved. It is the historical record from which everything else is derived. Losing evidence means losing ground truth — it cannot be reconstructed from conclusions.

**Knowledge is disposable.** It represents governed interpretations of evidence at a point in time. Every conclusion in the Knowledge System is always reproducible from the Evidence System. If a rule changes, the reasoning engine improves, or new evidence is added, GoldPan should be able to delete every Knowledge System output and regenerate it without losing anything that matters.

This means:
- Evidence should never contain computed conclusions. If it does, the Knowledge System has leaked into the Evidence System and a re-run of the engine will produce a different answer than what history recorded.
- Knowledge should never become a permanent source of truth. If it does, the engine cannot be improved without risking inconsistency between old stored conclusions and what the current rules would produce.
- The Evidence System is the source of truth. The Knowledge System is a governed interpretation of that truth at a point in time.

**The test:** if GoldPan deleted `derived_filters.json`, `allergen_conclusions.json`, and every other Knowledge System output today, and re-ran the pipeline from the Evidence System, the result should be identical — or better if the rules have been improved. If anything would be lost, something has drifted.

This lifecycle distinction protects GoldPan from two specific failure modes: architectural drift (computed conclusions accumulating in the Evidence System until they are treated as facts) and reasoning lock-in (the Knowledge System becoming so entangled with stored outputs that improving the engine requires rewriting history).

---

## The Design Heuristic

> If it was computed by GoldPan's rules, it belongs in the Knowledge System.  
> If it records a fact, a disclosure, or a source, it belongs in the Evidence System.

Every new feature, field, tab, output, or conclusion should naturally belong to one of these systems. If it doesn't fit cleanly, that is a signal the feature needs to be reconsidered before it is built.

---

## The Principles

**Separate evidence from knowledge.**  
A restaurant saying "gluten-free" is evidence. GoldPan concluding "no gluten ingredients identified from disclosed ingredients" is knowledge. These are different claims, with different authority, different limitations, and different accountability. They must never be presented as the same thing.

**Preserve provenance.**  
Every piece of evidence must carry its source. Where did it come from? When was it obtained? What channel was used? Evidence without provenance cannot be used to compute conclusions. Provenance is not metadata — it is a first-class data requirement.

**Never overstate certainty.**  
GoldPan's conclusions reflect what the available evidence supports — nothing more. "No beef identified" means the disclosed ingredient list does not contain beef. It is not a claim that the dish is beef-free. The distinction matters, and GoldPan must always communicate it.

**Unknown is preferable to unsupported certainty.**  
When evidence is insufficient, the correct answer is Unknown. A confident wrong answer is worse than an honest gap. GoldPan should surface gaps rather than fill them with inference, assumption, or extrapolation.

**Every conclusion must be explainable and traceable.**  
GoldPan does not produce opaque results. Every derived conclusion carries the evidence it was based on, the rule that authorized it, the confidence it warrants, and the limitations that bound it. A conclusion without an explanation is an architectural violation.

**Rules govern computation, not evidence.**  
The GoldPan Rules Registry defines what conclusions the Knowledge System may draw and under what conditions. Rules apply to the computation layer. Evidence is recorded faithfully regardless of whether any rule currently uses it. Rules are not filters on what evidence gets preserved.

**Freshness is part of evidence quality.**  
Evidence has a timestamp. Stale evidence is degraded evidence. A conclusion computed from evidence that may no longer reflect the restaurant's current menu is a less trustworthy conclusion. Freshness tracking is not an operational concern — it is part of the evidence integrity model.

---

## What This Means for Customers

GoldPan can eventually give customers two distinct perspectives on every dish.

**Evidence:** *What do we know?*  
What the restaurant disclosed. What ingredients were recorded. What allergens were declared. When the information was last verified. Where it came from.

**Knowledge:** *Given what we know, what can GoldPan responsibly conclude?*  
Derived conclusions with named rules, explicit reasoning, measured confidence, and honest limitations.

These are not the same question, and they deserve different answers.

---

## On Separation

The Evidence System and Knowledge System do not need to be physically separated today. They can share the same pipeline, the same repository, and the same operational infrastructure for as long as that serves the product.

What must be maintained now is not physical separation — it is clean seams.

A clean seam means the boundary is clear even when the systems are adjacent. Evidence flows in one direction: from acquisition into the record. Knowledge flows in one direction: from the record into governed conclusions. Neither crosses back. A conclusion does not become evidence. A disclosure does not become a conclusion.

Physical divergence — separate deployments, separate storage, separate APIs — should happen when the product and operations require it, not before. Premature separation adds complexity without adding clarity. The goal now is to maintain the architectural boundary so that separation, when it becomes necessary, is a deployment decision rather than a redesign.

---

## How to Use This Document

This document does not define schemas, rules, or implementation details. Those belong in the documents it governs.

When evaluating a new feature, schema change, or architectural decision, the first questions are:

1. Does this record evidence or compute knowledge?
2. If it computes, does it belong in the Knowledge System with a named rule and a traceable explanation?
3. If it records, does it carry provenance?
4. Does it overstate what the evidence supports?
5. Is Unknown handled honestly?
6. Does it maintain the seam between Evidence and Knowledge, even if the systems remain adjacent?
7. If every Knowledge System output were deleted and regenerated from the Evidence System, would anything be lost? If yes, something has drifted.

If those questions have clear answers, the decision is probably sound. If they don't, the design needs more work before implementation begins.
