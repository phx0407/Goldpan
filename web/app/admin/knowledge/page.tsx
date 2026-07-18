// app/admin/knowledge/page.tsx
// Knowledge OS — manages GoldPan's structured food knowledge.
// Architecture documentation phase: teaches the OS design, will become live knowledge dashboards.

import { OSArchitecturePage } from "@/app/admin/_components/OSArchitecturePage";

export default function KnowledgePage() {
  return (
    <OSArchitecturePage
      osNumber="3.5"
      name="Knowledge OS"
      tagline="Manage GoldPan's structured food knowledge — dishes, ingredients, allergen flags, claims, calorie content, and transparency scoring."
      buildPhase="building"
      phaseLabel="Phase 4/5 — Partially Live"
      owns={[
        "evidence.dishes",
        "evidence.ingredients",
        "evidence.restaurant_claims",
        "evidence.allergen_disclosures",
        "evidence.allergen_flags (on ingredients)",
        "transparency_scores",
        "calorie_content (restaurant-stated)",
        "nutrition_estimates (future)",
      ]}
      consumes={[
        "Approved intake packets from Intake OS",
        "Restaurant update submissions after Intake review",
        "Scoring architecture (SCORING_ARCHITECTURE.md)",
        "Allergen rules from Rules Registry",
        "Nutrition databases (future integration)",
      ]}
      produces={[
        "Evidence summaries → Restaurant Master Page",
        "Transparency coverage % → Restaurant OS and Analytics",
        "Ingredient coverage → Governance OS",
        "Calorie coverage % → Restaurant OS",
        "Scoring audit reports → Executive OS",
        "Nutrition/calorie estimates (future) → Customer Platform",
        "Unknown filter count → Governance OS",
      ]}
      keyQuestions={[
        "How many ingredients have been identified for this restaurant?",
        "What is the transparency score for this dish?",
        "Which dishes have unknown allergen status?",
        "Which restaurants have the lowest evidence coverage?",
        "What restaurant claims have been recorded?",
        "Are restaurant-stated calories separated from GoldPan estimates?",
      ]}
      healthPct={78}
      healthIssues={[
        { text: "52 legacy dishes need re-scoring under the 0–25 canonical model" },
        { text: "Knowledge web UI not yet built — data exists in Supabase only" },
        { text: "Nutrition estimates not yet implemented" },
      ]}
      activityExamples={[
        "Ingredient added",
        "Dish evidence updated",
        "Transparency score computed",
        "Restaurant claim recorded",
        "Allergen flag set",
        "Calorie content added",
        "Scoring audit completed",
        "Unknown filter resolved",
      ]}
      futureCapabilities={[
        "Dish browser — all dishes across all restaurants with coverage indicators",
        "Ingredient browser — full ingredient index with allergen flags",
        "Transparency score dashboard — restaurant ranking by coverage",
        "Allergen disclosure viewer — verbatim restaurant allergen statements",
        "Calorie coverage tracker — which dishes have restaurant-stated calories",
        "Unknown filter queue — dishes blocked by unknown evidence",
        "Scoring audit report — live view of re-score backlog",
        "Restaurant claims viewer — all claims by type and restaurant",
        "Evidence completeness heatmap — per restaurant, per dish",
        "Nutrition estimate pipeline (future) — GoldPan-generated calorie estimates",
      ]}
      crossLinks={[
        { label: "Restaurants",      href: "/admin/restaurants",           note: "Evidence belongs to restaurants" },
        { label: "Intake OS",        href: "/admin/intake",                note: "Intake produces Knowledge evidence" },
        { label: "Governance OS",    href: "/admin/governance",            note: "Governance reads Knowledge evidence" },
        { label: "Analytics OS",     href: "/admin/analytics",             note: "Coverage metrics feed demand analysis" },
        { label: "Executive OS",     href: "/admin/executive",             note: "Scoring health in daily brief" },
      ]}
    />
  );
}
