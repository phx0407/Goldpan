// OSArchitecturePage.tsx
// Shared architecture documentation component for all skeleton OS pages.
// Each page teaches a new employee what the OS owns, consumes, produces,
// and will eventually become. Incorporates Section 5f architectural principles:
// cross-links, health meter placeholder, activity feed placeholder, status cards.

import Link from "next/link";

// ── Types ─────────────────────────────────────────────────────────────────────

export type BuildPhase = "live" | "building" | "planned";

export interface CrossLink {
  label: string;
  href: string;
  note: string;
}

export interface HealthIssue {
  text: string;
}

export interface HealthDeduction {
  condition: string;  // Human-readable trigger condition
  points:    number;  // Points subtracted from 100 when triggered
  severity:  "critical" | "warning" | "info";
  action:    string;  // What to do when triggered
}

export interface OSArchitecturePageProps {
  // Identity
  osNumber:    string;   // e.g. "3.4"
  name:        string;   // e.g. "Intake OS"
  tagline:     string;   // one-sentence purpose
  buildPhase:  BuildPhase;
  phaseLabel:  string;   // e.g. "Phase 5 — Next Priority"

  // Data model
  owns:     string[];
  consumes: string[];
  produces: string[];

  // Operational
  keyQuestions:       string[];
  futureCapabilities: string[];
  crossLinks:         CrossLink[];

  // Health (placeholder — will become live computed values)
  healthPct:    number;   // 0–100, shown as a meter
  healthIssues: HealthIssue[];
  healthFormula?: HealthDeduction[];  // Scoring rules — will compute live in a future phase

  // Activity feed (placeholder event types this OS will emit)
  activityExamples: string[];
}

// ── Sub-components ────────────────────────────────────────────────────────────

function PhaseBadge({ phase, label }: { phase: BuildPhase; label: string }) {
  const colors: Record<BuildPhase, string> = {
    live:     "bg-emerald-900/60 text-emerald-300 border-emerald-800",
    building: "bg-amber-900/60  text-amber-300  border-amber-800",
    planned:  "bg-stone-800     text-stone-400  border-stone-700",
  };
  const dot: Record<BuildPhase, string> = {
    live:     "bg-emerald-400",
    building: "bg-amber-400 animate-pulse",
    planned:  "bg-stone-500",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-xs font-medium ${colors[phase]}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot[phase]}`} />
      {label}
    </span>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-stone-400">
      {children}
    </p>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded bg-stone-800 px-1.5 py-0.5 font-mono text-[11px] text-stone-300">
      {children}
    </span>
  );
}

function HealthMeter({ pct, issues }: { pct: number; issues: HealthIssue[] }) {
  const color = pct >= 90 ? "bg-emerald-500" : pct >= 70 ? "bg-amber-500" : "bg-red-500";
  const textColor = pct >= 90 ? "text-emerald-300" : pct >= 70 ? "text-amber-300" : "text-red-400";
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <SectionLabel>OS Health</SectionLabel>
        <span className={`text-sm font-semibold ${textColor}`}>{pct}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-stone-800 overflow-hidden mb-3">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      {issues.length === 0 ? (
        <p className="text-xs text-stone-500">No open issues.</p>
      ) : (
        <ul className="space-y-1">
          {issues.map((issue, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-stone-400">
              <span className="mt-0.5 shrink-0 text-amber-600">·</span>
              {issue.text}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-[10px] text-stone-600 italic">
        Health score is a placeholder — will be computed live in a future phase.
      </p>
    </div>
  );
}

function HealthFormulaSection({ deductions }: { deductions: HealthDeduction[] }) {
  const severityBadge: Record<HealthDeduction["severity"], string> = {
    critical: "border-red-900/60 bg-red-950/30 text-red-400",
    warning:  "border-amber-900/60 bg-amber-950/20 text-amber-400",
    info:     "border-blue-900/60 bg-blue-950/20 text-blue-400",
  };
  const severityDot: Record<HealthDeduction["severity"], string> = {
    critical: "bg-red-500",
    warning:  "bg-amber-400",
    info:     "bg-blue-400",
  };

  return (
    <div className="rounded-lg border border-stone-800 bg-stone-900/40 p-4">
      <div className="flex items-center justify-between mb-2">
        <SectionLabel>Health formula — planned</SectionLabel>
        <span className="text-[10px] text-stone-600 italic">Section 5f Principle 7</span>
      </div>
      <p className="text-[11px] text-stone-500 mb-3">
        Score starts at 100. Each condition below deducts points when triggered. Formula will compute live against live data in a future phase.
      </p>
      <div className="space-y-1.5">
        {deductions.map((d, i) => (
          <div key={i} className="flex items-start gap-3 rounded border border-stone-800/80 bg-stone-900/60 px-3 py-2">
            <span className={`mt-1 shrink-0 h-1.5 w-1.5 rounded-full ${severityDot[d.severity]}`} />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-stone-300">{d.condition}</p>
              <p className="text-[10px] text-stone-500 mt-0.5">→ {d.action}</p>
            </div>
            <span className={`shrink-0 rounded border px-1.5 py-0.5 text-xs font-mono font-semibold ${severityBadge[d.severity]}`}>
              −{d.points}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function OSArchitecturePage({
  osNumber,
  name,
  tagline,
  buildPhase,
  phaseLabel,
  owns,
  consumes,
  produces,
  keyQuestions,
  futureCapabilities,
  crossLinks,
  healthPct,
  healthIssues,
  healthFormula,
  activityExamples,
}: OSArchitecturePageProps) {
  return (
    <div className="mx-auto max-w-5xl space-y-6">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-stone-500">OS {osNumber}</span>
            <PhaseBadge phase={buildPhase} label={phaseLabel} />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-stone-100">{name}</h1>
          <p className="mt-1 text-sm text-stone-300 max-w-2xl">{tagline}</p>
        </div>
        <div className="rounded border border-stone-800 bg-stone-900/60 px-3 py-2 text-right">
          <p className="text-[10px] uppercase tracking-widest text-stone-500 mb-0.5">Architecture Phase</p>
          <p className="text-xs text-stone-400">
            This page documents the OS design.<br />
            It will become a live operational dashboard.
          </p>
        </div>
      </div>

      {/* ── Top row: Health + Data flows ───────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Health */}
        <div className="rounded-lg border border-stone-800 bg-stone-900/40 p-4">
          <HealthMeter pct={healthPct} issues={healthIssues} />
        </div>

        {/* Owns */}
        <div className="rounded-lg border border-stone-800 bg-stone-900/40 p-4">
          <SectionLabel>Owns exclusively</SectionLabel>
          <div className="flex flex-wrap gap-1.5">
            {owns.map(t => <Tag key={t}>{t}</Tag>)}
          </div>
        </div>

        {/* Key questions */}
        <div className="rounded-lg border border-stone-800 bg-stone-900/40 p-4">
          <SectionLabel>Key questions this OS answers</SectionLabel>
          <ul className="space-y-1.5">
            {keyQuestions.map((q, i) => (
              <li key={i} className="text-xs text-stone-300 flex gap-1.5">
                <span className="text-amber-600 shrink-0">?</span>{q}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* ── Health formula ─────────────────────────────────────────────────── */}
      {healthFormula && healthFormula.length > 0 && (
        <HealthFormulaSection deductions={healthFormula} />
      )}

      {/* ── Data flows ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="rounded-lg border border-stone-800 bg-stone-900/40 p-4">
          <SectionLabel>Consumes from</SectionLabel>
          <ul className="space-y-1">
            {consumes.map((c, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs text-stone-300">
                <span className="text-blue-500 shrink-0 mt-0.5">←</span>{c}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-stone-800 bg-stone-900/40 p-4">
          <SectionLabel>Produces for</SectionLabel>
          <ul className="space-y-1">
            {produces.map((p, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs text-stone-300">
                <span className="text-emerald-500 shrink-0 mt-0.5">→</span>{p}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* ── Activity feed placeholder ───────────────────────────────────────── */}
      <div className="rounded-lg border border-stone-800 bg-stone-900/40 p-4">
        <div className="flex items-center justify-between mb-3">
          <SectionLabel>Activity feed — events this OS will emit</SectionLabel>
          <span className="text-[10px] text-stone-600 italic">Future — Section 5f Principle 2</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {activityExamples.map((e, i) => (
            <span
              key={i}
              className="rounded border border-stone-800 bg-stone-900 px-2 py-1 text-[11px] text-stone-400"
            >
              {e}
            </span>
          ))}
        </div>
      </div>

      {/* ── Future capabilities ─────────────────────────────────────────────── */}
      <div className="rounded-lg border border-stone-800 bg-stone-900/40 p-4">
        <SectionLabel>Future capabilities — what this page becomes</SectionLabel>
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1.5">
          {futureCapabilities.map((f, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-stone-400">
              <span className="text-stone-600 shrink-0 mt-0.5">○</span>{f}
            </li>
          ))}
        </ul>
      </div>

      {/* ── Cross-OS links ──────────────────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <SectionLabel>Cross-OS links — Section 5f Principle 1</SectionLabel>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {crossLinks.map(link => (
            <Link
              key={link.href}
              href={link.href}
              className="group rounded-lg border border-stone-800 bg-stone-900/40 p-3 hover:border-amber-800/60 hover:bg-stone-800/60 transition-colors"
            >
              <p className="text-xs font-medium text-stone-300 group-hover:text-amber-400 transition-colors">
                {link.label}
              </p>
              <p className="mt-0.5 text-[10px] text-stone-500">{link.note}</p>
            </Link>
          ))}
        </div>
      </div>

    </div>
  );
}
