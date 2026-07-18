// app/admin/executive/page.tsx
// Executive OS — bird's-eye leadership view of company health.
// Architecture documentation phase: teaches the OS design, will become a live dashboard.

import { OSArchitecturePage } from "@/app/admin/_components/OSArchitecturePage";

export default function ExecutivePage() {
  return (
    <OSArchitecturePage
      osNumber="3.1"
      name="Executive OS"
      tagline="Give leadership a bird's-eye view of company health — what needs attention today, what is growing, and what is blocked."
      buildPhase="planned"
      phaseLabel="Phase 10+ — Long-term"
      owns={[
        "executive_reports",
        "daily_briefs",
        "priorities",
        "risks",
        "KPIs",
      ]}
      consumes={[
        "Restaurant Operations health summary",
        "Business Development pipeline status",
        "AI spend and budget alerts (AI OS)",
        "Customer analytics and demand signals (Analytics OS)",
        "Governance health and conflict count",
        "Intake queue depth and approval rate",
        "Operations system health",
        "Finance runway and cost reports",
      ]}
      produces={[
        "Founder Daily Brief — what changed, what needs action",
        "Company Health Report — all-OS health meters aggregated",
        "Weekly priorities — cross-OS action list",
        "Strategic alerts — anomalies surfaced from all modules",
      ]}
      keyQuestions={[
        "What needs my attention today?",
        "Where are we blocked across the company?",
        "What is growing or trending positively?",
        "What is costing the most — AI, infrastructure, time?",
        "Which restaurants are overdue for follow-up or recanvass?",
      ]}
      healthPct={100}
      healthIssues={[]}
      activityExamples={[
        "Daily brief generated",
        "Company health report updated",
        "Strategic alert raised",
        "Priority list changed",
        "KPI milestone reached",
        "Risk flag cleared",
      ]}
      futureCapabilities={[
        "Live aggregated health meter across all 10 OS modules",
        "Founder Daily Brief — auto-generated every morning",
        "Cross-OS activity feed on one screen",
        "Weekly priority list with drag-and-drop reordering",
        "Risk register — open issues ranked by severity",
        "Revenue vs. cost overview with trend lines",
        "Alert center — critical items requiring leadership action",
        "Role-based dashboard (Executive, Ops, BD, Intake views)",
      ]}
      crossLinks={[
        { label: "Restaurant Operations", href: "/admin/restaurants",            note: "Restaurant health and pipeline" },
        { label: "Business Development",  href: "/admin/business-development",  note: "Partnership pipeline" },
        { label: "Intake OS",             href: "/admin/intake",                note: "Evidence acquisition queue" },
        { label: "Governance OS",         href: "/admin/governance",            note: "Rule outcomes and conflicts" },
        { label: "Analytics OS",          href: "/admin/analytics",             note: "Customer demand signals" },
        { label: "AI OS",                 href: "/admin/ai-usage",              note: "Spend and budget controls" },
        { label: "Operations OS",         href: "/admin/operations",            note: "System and pipeline health" },
        { label: "Finance OS",            href: "/admin/finance",               note: "Costs, revenue, runway" },
      ]}
    />
  );
}
