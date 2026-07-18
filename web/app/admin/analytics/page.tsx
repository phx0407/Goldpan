// app/admin/analytics/page.tsx
// Analytics OS — understands customer demand, search behavior, and market opportunity.
// Architecture documentation phase: teaches the OS design, will become live analytics dashboards.

import { OSArchitecturePage } from "@/app/admin/_components/OSArchitecturePage";

export default function AnalyticsPage() {
  return (
    <OSArchitecturePage
      osNumber="3.7"
      name="Analytics OS"
      tagline="Understand customer demand, search behavior, restaurant interest, and market opportunity. Analytics feeds BD prioritization — it never alters evidence."
      buildPhase="planned"
      phaseLabel="Phase 7 — Planned"
      owns={[
        "analytics.page_views",
        "analytics.events",
        "analytics.restaurant_profile_views",
        "analytics.search_terms",
        "analytics.ask_goldpan_sessions",
      ]}
      consumes={[
        "Frontend events from GoldPan customer platform",
        "Ask GoldPan™ session data — queries and outcomes",
        "Restaurant profile view counts",
        "Search activity — terms, filters applied, results clicked",
        "Referral sources — how customers find GoldPan",
        "Partner campaign data (future)",
      ]}
      produces={[
        "Customer Demand Report — most requested dietary restrictions",
        "Restaurant demand signals → BD OS (which restaurants customers want)",
        "Market opportunity maps → Executive OS",
        "Most searched dietary restrictions and allergens",
        "Most viewed restaurants and dishes",
        "Conversion insights — search → view → return visits",
        "Ask GoldPan™ usage and satisfaction data",
      ]}
      keyQuestions={[
        "What dietary restrictions are customers searching for most?",
        "Which restaurants are getting the most profile views?",
        "What markets are showing the strongest demand?",
        "Which restaurants do customers want but GoldPan doesn't have?",
        "What is the Ask GoldPan™ success rate?",
        "How is search-to-engagement conversion trending?",
      ]}
      healthPct={100}
      healthIssues={[]}
      activityExamples={[
        "Search term logged",
        "Restaurant profile viewed",
        "Ask GoldPan session completed",
        "Demand spike detected",
        "New market signal identified",
        "Campaign attribution recorded",
        "Conversion milestone reached",
      ]}
      futureCapabilities={[
        "Customer demand dashboard — most searched restrictions by market",
        "Restaurant demand ranking — which restaurants customers want most",
        "Search term explorer — trending queries with no results vs. good results",
        "Ask GoldPan™ analytics — success rate, fallback rate, topic breakdown",
        "Market opportunity map — demand by geography vs. current coverage",
        "BD signal integration — high-demand restaurants surfaced in BD pipeline",
        "Cohort analysis — user return rates and engagement trends",
        "A/B test result viewer (future)",
        "Partner campaign tracking (future)",
      ]}
      crossLinks={[
        { label: "Business Development", href: "/admin/business-development",  note: "Analytics signals BD restaurant priorities" },
        { label: "Restaurants",          href: "/admin/restaurants",           note: "View counts per restaurant" },
        { label: "AI OS",                href: "/admin/ai-usage",              note: "Ask GoldPan AI costs and usage" },
        { label: "Executive OS",         href: "/admin/executive",             note: "Demand signals in daily brief" },
        { label: "Governance OS",        href: "/admin/governance",            note: "Coverage gaps visible in analytics" },
      ]}
    />
  );
}
