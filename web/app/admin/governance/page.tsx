// app/admin/governance/page.tsx
// Governance OS — applies deterministic rules to evidence and produces conclusions.
// Architecture documentation phase: teaches the OS design, will become live governance dashboards.

import { OSArchitecturePage } from "@/app/admin/_components/OSArchitecturePage";

export default function GovernancePage() {
  return (
    <OSArchitecturePage
      osNumber="3.6"
      name="Governance OS"
      tagline="Apply deterministic rules to evidence and produce conclusions. Governance reads evidence — it never rewrites Intake facts. Unknown is valid when evidence is incomplete."
      buildPhase="building"
      phaseLabel="Phase 6 — Planned"
      owns={[
        "rules_registry",
        "derived_filters",
        "rule_outcomes",
        "confidence_levels",
        "unknown_conclusions",
        "governance_audit_trail",
        "rule_versions",
      ]}
      consumes={[
        "Approved ingredient evidence from Knowledge OS",
        "Allergen flags on ingredient rows",
        "Allergen disclosures from restaurants",
        "Verbatim components (unresolved = unknown evidence)",
        "Scoring rules (SCORING_ARCHITECTURE.md)",
        "Rules Registry (GP-RULE-001 through GP-RULE-015+)",
      ]}
      produces={[
        "Filter conclusions (vegan, dairy-free, no-gluten, etc.) → Customer Platform",
        "Unknown reasons with explainability → Restaurant OS and Customer Platform",
        "Rule conflicts → Governance audit queue",
        "Publication readiness status → Restaurant OS",
        "Public-facing filter eligibility → Customer Platform",
        "GoldPan advisories (generated dynamically, never stored as Intake facts)",
      ]}
      keyQuestions={[
        "What is blocking this restaurant from being published?",
        "Why is this dish returning 'Unknown' for dairy-free?",
        "Which restaurants have unresolved Governance conflicts?",
        "Which rules fired on this dish and what was the outcome?",
        "How many dishes are blocked by unknown verbatim components?",
        "What changed between the last two Governance runs?",
      ]}
      healthPct={85}
      healthIssues={[
        { text: "Governance web UI not yet built — pipeline runs via Python only" },
        { text: "Rule conflict viewer not yet implemented" },
        { text: "Explainability annotations exist in code but not surfaced in UI" },
      ]}
      healthFormula={[
        { condition: "Unresolved rule conflict in rules registry", points: 20, severity: "critical", action: "Review conflicting rules and resolve in rules registry" },
        { condition: "Unknown backlog increasing (7-day upward trend)", points: 10, severity: "warning", action: "Identify evidence gaps driving unknowns and queue for intake" },
        { condition: "Legacy scoring debt unresolved (dishes under old model)", points: 8, severity: "warning", action: "Re-score dishes under canonical 0–25 model" },
        { condition: "Governance changes not yet published to customer platform", points: 12, severity: "critical", action: "Review pending changes and trigger publish workflow" },
      ]}
      activityExamples={[
        "Governance run started",
        "Governance run completed",
        "Rule conflict detected",
        "Rule conflict resolved",
        "Dish marked publication-ready",
        "Unknown conclusion raised",
        "Unknown resolved after intake update",
        "Rule version updated",
        "Restaurant published after Governance approval",
      ]}
      futureCapabilities={[
        "Rules Registry browser — all GP-RULE entries with descriptions and outcomes",
        "Governance run history — per-restaurant run log with diff view",
        "Unknown queue — dishes/restaurants blocked by unknown conclusions",
        "Explainability panel — why is this dish blocked, what resolves it",
        "Rule conflict viewer — conflicting rules with resolution workflow",
        "Publication readiness dashboard — which restaurants are ready to publish",
        "Rule version history — who changed a rule, when, and what changed",
        "Governance audit trail — full chronological log per entity",
        "Re-run trigger from UI — no Python script required",
        "Confidence score display — not just pass/fail but evidence quality",
      ]}
      crossLinks={[
        { label: "Restaurants",   href: "/admin/restaurants",           note: "Governance determines publication readiness" },
        { label: "Knowledge OS",  href: "/admin/knowledge",             note: "Governance reads Knowledge evidence" },
        { label: "Intake OS",     href: "/admin/intake",                note: "Approved intake triggers Governance" },
        { label: "Analytics OS",  href: "/admin/analytics",             note: "Governance outcomes feed demand analysis" },
        { label: "Executive OS",  href: "/admin/executive",             note: "Conflict count in daily brief" },
      ]}
    />
  );
}
