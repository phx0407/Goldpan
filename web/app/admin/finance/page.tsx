// app/admin/finance/page.tsx
// Finance OS — tracks business costs, revenue, grants, and unit economics.
// Architecture documentation phase: teaches the OS design, will become live financial dashboards.

import { OSArchitecturePage } from "@/app/admin/_components/OSArchitecturePage";

export default function FinancePage() {
  return (
    <OSArchitecturePage
      osNumber="3.10"
      name="Finance OS"
      tagline="Track business costs, revenue, grants, subscriptions, and unit economics. Finance tells you what GoldPan costs to run and what it earns."
      buildPhase="planned"
      phaseLabel="Phase 9 — Planned"
      owns={[
        "expenses",
        "revenue_records",
        "grant_opportunities",
        "subscriptions",
        "cost_allocation",
        "financial_reports",
      ]}
      consumes={[
        "AI costs from AI OS (per-call, per-purpose, per-month)",
        "Infrastructure costs — Supabase, Vercel, domain, services",
        "Partner revenue — when BD partnerships generate income",
        "Customer subscription revenue (future)",
        "Sponsorship and brand revenue (future)",
        "Grant disbursements and milestones (future)",
      ]}
      produces={[
        "Runway report — current burn rate vs. funding",
        "Monthly cost report — AI + infra + operations broken down",
        "Revenue report — actual vs. projected by source",
        "Unit economics report — cost per restaurant, cost per intake run",
        "Grant pipeline — open opportunities and milestone tracking",
        "Cost allocation — which OS costs the most to run",
      ]}
      keyQuestions={[
        "What is our current monthly burn rate?",
        "What does each AI call actually cost per restaurant?",
        "Which cost category is growing fastest?",
        "What is our runway given current spending?",
        "Which grant opportunities are active or pending?",
        "What is the cost per published restaurant?",
      ]}
      healthPct={100}
      healthIssues={[]}
      healthFormula={[
        { condition: "Monthly cost data missing or incomplete", points: 10, severity: "warning", action: "Collect and record all cost categories for the period" },
        { condition: "AI spend not allocated to OS cost centers", points: 8, severity: "warning", action: "Allocate AI costs by OS module in Finance OS" },
        { condition: "Grant deadline within 7 days with no assigned owner", points: 12, severity: "critical", action: "Assign owner and confirm submission or deferral plan" },
        { condition: "Revenue records incomplete for closed period", points: 10, severity: "warning", action: "Record all revenue transactions before period close" },
      ]}
      activityExamples={[
        "Monthly cost report generated",
        "AI spend threshold reached",
        "Revenue milestone recorded",
        "Grant application submitted",
        "Grant milestone completed",
        "Subscription activated",
        "Cost allocation updated",
        "Runway projection updated",
      ]}
      futureCapabilities={[
        "Monthly cost dashboard — AI, infra, and ops costs in one view",
        "AI cost drill-down — cost per purpose, per model, per restaurant",
        "Revenue tracker — partner, customer, and grant revenue streams",
        "Runway calculator — burn rate × current funding",
        "Unit economics — cost per restaurant onboarded, cost per intake run",
        "Grant pipeline — open opportunities with deadlines and status",
        "Cost vs. value analysis — which activities drive the most value per dollar",
        "Budget vs. actual comparison — monthly variance reporting",
        "Subscription management — active plans, renewal dates, cost",
      ]}
      crossLinks={[
        { label: "AI OS",          href: "/admin/ai-usage",   note: "AI costs flow into Finance OS" },
        { label: "Operations OS",  href: "/admin/operations", note: "Infrastructure costs tracked" },
        { label: "Executive OS",   href: "/admin/executive",  note: "Runway and costs in daily brief" },
        { label: "Business Dev",   href: "/admin/business-development", note: "Partner revenue recorded here" },
      ]}
    />
  );
}
