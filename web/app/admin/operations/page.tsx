// app/admin/operations/page.tsx
// Operations OS — monitors technical and operational health.
// Architecture documentation phase: teaches the OS design, will become live system health dashboards.

import { OSArchitecturePage } from "@/app/admin/_components/OSArchitecturePage";

export default function OperationsPage() {
  return (
    <OSArchitecturePage
      osNumber="3.9"
      name="Operations OS"
      tagline="Monitor technical and operational health — system uptime, pipeline runs, migration history, job logs, and deployment readiness."
      buildPhase="planned"
      phaseLabel="Phase 8 — Planned"
      owns={[
        "system_health_reports",
        "pipeline_runs",
        "migration_history",
        "job_logs",
        "validation_reports",
        "error_logs",
      ]}
      consumes={[
        "FastAPI health endpoints",
        "Supabase connection status",
        "Pipeline run results (pipeline.py)",
        "Frontend error events",
        "AI error logs from AI OS",
        "Migration execution records",
        "Validation reports (validate_database.py)",
      ]}
      produces={[
        "System Health Report → Executive OS",
        "Pipeline status and run history → all OS modules",
        "Error alerts → Notification Center",
        "Deployment readiness report",
        "Migration success / rollback log",
        "Database validation report — row counts, constraint checks",
      ]}
      keyQuestions={[
        "Is the system healthy right now?",
        "When did the last pipeline run complete?",
        "What errors occurred in the last 24 hours?",
        "Are all migrations applied and idempotent?",
        "Is the database passing validation checks?",
        "What changed in the last deployment?",
      ]}
      healthPct={88}
      healthIssues={[
        { text: "Operations web UI not yet built — monitoring is manual" },
        { text: "No automated pipeline scheduling — runs triggered manually" },
      ]}
      healthFormula={[
        { condition: "API health check failing", points: 25, severity: "critical", action: "Diagnose and restore failing FastAPI endpoint immediately" },
        { condition: "Database validation errors present", points: 15, severity: "critical", action: "Run validate_database.py and resolve constraint violations" },
        { condition: "Migration pending and not applied", points: 10, severity: "warning", action: "Review and apply pending migration with rollback plan" },
        { condition: "Pipeline failure not resolved", points: 20, severity: "critical", action: "Check pipeline.py logs and re-run; escalate if systemic" },
        { condition: "Frontend error spike (>10 errors in 24h)", points: 10, severity: "warning", action: "Review frontend error logs and trace root cause" },
      ]}
      activityExamples={[
        "Pipeline run started",
        "Pipeline run completed",
        "Migration applied",
        "Validation check passed",
        "Validation check failed",
        "API error logged",
        "System health check completed",
        "Deployment triggered",
      ]}
      futureCapabilities={[
        "Live system health dashboard — API, database, pipeline status",
        "Pipeline run history — every run with timing and outcome",
        "Error log browser — grouped by type with frequency trends",
        "Migration history viewer — all migrations applied with timestamps",
        "Database validation report — row counts, constraint violations",
        "Automated health checks — scheduled validation on a cron",
        "Deployment log — what changed, when, and by whom",
        "Alert routing — system failures notify Operations and Executive OS",
        "Resource utilization tracking — Supabase row limits, API rate limits",
      ]}
      crossLinks={[
        { label: "AI OS",         href: "/admin/ai-usage",    note: "AI errors feed Operations log" },
        { label: "Executive OS",  href: "/admin/executive",   note: "System health in daily brief" },
        { label: "Finance OS",    href: "/admin/finance",     note: "Infrastructure costs tracked here" },
        { label: "Intake OS",     href: "/admin/intake",      note: "Pipeline runs serve Intake" },
        { label: "Governance OS", href: "/admin/governance",  note: "Governance run logs" },
      ]}
    />
  );
}
