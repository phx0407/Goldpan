// app/admin/ai-usage/page.tsx
// Server component — fetches data at render time.
// ADMIN_API_KEY stays on the server; never reaches the browser.

import { fetchAIUsageReport, APIError } from "@/lib/api";
import type {
  AIUsageReport,
  PurposeBreakdown,
  ModelBreakdown,
  RecentError,
} from "@/lib/types";

export const revalidate = 30; // ISR: re-fetch every 30 s

// ── Helpers ───────────────────────────────────────────────────────────────────

function usd(n: number) {
  return n < 0.01 && n > 0 ? `$${n.toFixed(6)}` : `$${n.toFixed(4)}`;
}

function fmtTokens(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

function clamp(n: number) {
  return Math.min(Math.max(n, 0), 100);
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  pct,
  alert,
}: {
  label: string;
  value: string;
  sub?: string;
  pct?: number;
  alert?: boolean;
}) {
  const barColor =
    pct === undefined
      ? ""
      : pct >= 90
        ? "bg-red-500"
        : pct >= 70
          ? "bg-amber-400"
          : "bg-emerald-500";

  return (
    <div
      className={`rounded-lg border p-4 ${
        alert
          ? "border-amber-500/40 bg-amber-950/30"
          : "border-stone-700 bg-stone-900"
      }`}
    >
      <p className="text-xs font-medium uppercase tracking-widest text-stone-400">
        {label}
      </p>
      <p
        className={`mt-1 text-2xl font-semibold tabular-nums ${
          alert ? "text-amber-400" : "text-stone-100"
        }`}
      >
        {value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-stone-400">{sub}</p>}
      {pct !== undefined && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-stone-400 mb-1">
            <span>{pct.toFixed(1)}% used</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-stone-700">
            <div
              className={`h-1.5 rounded-full transition-all ${barColor}`}
              style={{ width: `${clamp(pct)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <h2 className="mt-8 mb-3 text-xs font-semibold uppercase tracking-widest text-stone-400">
      {title}
    </h2>
  );
}

function Flag({
  label,
  enabled,
}: {
  label: string;
  enabled: boolean;
}) {
  return (
    <div className="flex items-center gap-2 rounded border border-stone-700 bg-stone-900 px-3 py-2">
      <span
        className={`h-2 w-2 rounded-full ${enabled ? "bg-emerald-400" : "bg-stone-600"}`}
      />
      <span className="text-sm text-stone-300">{label}</span>
      <span
        className={`ml-auto text-xs font-medium ${
          enabled ? "text-emerald-400" : "text-stone-500"
        }`}
      >
        {enabled ? "on" : "off"}
      </span>
    </div>
  );
}

function CallsTable({
  rows,
  keyField,
}: {
  rows: (PurposeBreakdown | ModelBreakdown)[];
  keyField: "purpose" | "model";
}) {
  if (!rows.length) {
    return <p className="text-sm text-stone-500">No data this month.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-stone-700">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-stone-700 bg-stone-900">
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400 capitalize">
              {keyField}
            </th>
            <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">
              Calls
            </th>
            <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">
              Cost
            </th>
            <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">
              Tokens in
            </th>
            <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">
              Tokens out
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const key = keyField === "purpose"
              ? (row as PurposeBreakdown).purpose
              : (row as ModelBreakdown).model;
            return (
              <tr
                key={key}
                className="border-b border-stone-800 last:border-0 hover:bg-stone-800/50"
              >
                <td className="px-4 py-2.5 font-mono text-xs text-stone-300">
                  {key}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-stone-300">
                  {row.calls}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-amber-400/90">
                  {usd(row.total_cost_usd)}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-stone-400">
                  {fmtTokens(row.input_tokens)}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-stone-400">
                  {fmtTokens(row.output_tokens)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ErrorsTable({ errors }: { errors: RecentError[] }) {
  if (!errors.length) {
    return (
      <p className="text-sm text-emerald-500">No errors this month. ✓</p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-stone-700">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-stone-700 bg-stone-900">
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">
              Time
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">
              Status
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">
              Purpose
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">
              Model
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">
              Message
            </th>
          </tr>
        </thead>
        <tbody>
          {errors.map((e) => (
            <tr
              key={e.log_id}
              className="border-b border-stone-800 last:border-0 hover:bg-stone-800/50"
            >
              <td className="px-4 py-2.5 text-xs text-stone-400 whitespace-nowrap">
                {fmtDate(e.created_at)}
              </td>
              <td className="px-4 py-2.5">
                <span
                  className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                    e.status === "timeout"
                      ? "bg-amber-900/60 text-amber-300"
                      : "bg-red-900/60 text-red-300"
                  }`}
                >
                  {e.status}
                </span>
              </td>
              <td className="px-4 py-2.5 font-mono text-xs text-stone-400">
                {e.purpose}
              </td>
              <td className="px-4 py-2.5 font-mono text-xs text-stone-400">
                {e.model.split("-").slice(0, 2).join("-")}
              </td>
              <td className="px-4 py-2.5 text-xs text-stone-400 max-w-xs truncate">
                {e.error_message ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function AIUsagePage() {
  let report: AIUsageReport | null = null;
  let fetchError: string | null = null;

  try {
    report = await fetchAIUsageReport();
  } catch (err) {
    fetchError =
      err instanceof APIError
        ? `${err.status} — ${err.detail}`
        : err instanceof Error
          ? err.message
          : "Unknown error fetching report.";
  }

  if (fetchError) {
    return (
      <div className="flex flex-col gap-3">
        <h1 className="text-lg font-semibold text-stone-100">AI Usage</h1>
        <div className="rounded-lg border border-red-800 bg-red-950/40 p-5">
          <p className="text-sm font-medium text-red-400">
            Could not load report
          </p>
          <p className="mt-1 font-mono text-xs text-red-500">{fetchError}</p>
          <p className="mt-3 text-xs text-stone-500">
            Make sure the FastAPI server is running and{" "}
            <code className="text-stone-400">ADMIN_API_KEY</code> is set in{" "}
            <code className="text-stone-400">.env.local</code>.
          </p>
        </div>
      </div>
    );
  }

  if (!report) return null;

  const { spend, tokens, calls, budget_flags: flags, errors } = report;
  const hasErrors = errors.errors_today > 0 || errors.budget_exceeded_today > 0;

  return (
    <div className="max-w-5xl">
      {/* Page header */}
      <div className="flex items-baseline gap-3 mb-1">
        <h1 className="text-lg font-semibold text-stone-100">AI Usage</h1>
        <span className="text-xs text-stone-400">{report.period_month}</span>
      </div>
      <p className="text-xs text-stone-500 mb-6">
        Generated {fmtDate(report.generated_at)} · refreshes every 30 s
      </p>

      {/* ── Spend ── */}
      <SectionHeader title="Spend" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Today"
          value={usd(spend.today_usd)}
          sub={`of ${usd(spend.daily_limit_usd)} daily limit`}
          pct={spend.daily_pct_used}
          alert={spend.daily_pct_used >= 80}
        />
        <StatCard
          label="This month"
          value={usd(spend.month_usd)}
          sub={`of ${usd(spend.monthly_limit_usd)} monthly limit`}
          pct={spend.monthly_pct_used}
          alert={spend.monthly_pct_used >= 80}
        />
        <StatCard
          label="Daily remaining"
          value={usd(spend.daily_remaining_usd)}
          sub={`${(100 - spend.daily_pct_used).toFixed(1)}% left`}
        />
        <StatCard
          label="Monthly remaining"
          value={usd(spend.monthly_remaining_usd)}
          sub={`${(100 - spend.monthly_pct_used).toFixed(1)}% left`}
        />
      </div>

      {/* ── Tokens ── */}
      <SectionHeader title="Tokens" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Today — input"
          value={fmtTokens(tokens.today_input)}
        />
        <StatCard
          label="Today — output"
          value={fmtTokens(tokens.today_output)}
        />
        <StatCard
          label="Month — input"
          value={fmtTokens(tokens.month_input)}
        />
        <StatCard
          label="Month — output"
          value={fmtTokens(tokens.month_output)}
        />
      </div>

      {/* ── Call counts ── */}
      <SectionHeader title="Calls" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-5">
        <StatCard
          label="Today"
          value={calls.today_total.toString()}
          sub="successful calls"
        />
        <StatCard
          label="This month"
          value={calls.month_total.toString()}
          sub="successful calls"
        />
        <StatCard
          label="Errors today"
          value={errors.errors_today.toString()}
          sub="error + timeout"
          alert={errors.errors_today > 0}
        />
        <StatCard
          label="Budget blocks today"
          value={errors.budget_exceeded_today.toString()}
          sub="budget_exceeded status"
          alert={errors.budget_exceeded_today > 0}
        />
      </div>

      <SectionHeader title="Calls by purpose — month to date" />
      <CallsTable rows={calls.by_purpose} keyField="purpose" />

      <SectionHeader title="Calls by model — month to date" />
      <CallsTable rows={calls.by_model} keyField="model" />

      {/* ── Budget flags ── */}
      <SectionHeader title="Budget flags" />
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 mb-2">
        <Flag label="Ask GoldPan™" enabled={flags.ask_goldpan_enabled} />
        <Flag label="Intake AI" enabled={flags.intake_ai_enabled} />
        <Flag label="Governance AI" enabled={flags.governance_ai_enabled} />
      </div>
      {flags.ask_goldpan_enabled && (
        <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard
            label="Ask GP today"
            value={usd(flags.ag_spend_today_usd)}
            sub={`of ${usd(flags.ask_goldpan_daily_limit_usd)} daily cap`}
            pct={(flags.ag_spend_today_usd / flags.ask_goldpan_daily_limit_usd) * 100}
          />
          <StatCard
            label="Ask GP month"
            value={usd(flags.ag_spend_month_usd)}
            sub={`of ${usd(flags.ask_goldpan_monthly_limit_usd)} monthly cap`}
            pct={(flags.ag_spend_month_usd / flags.ask_goldpan_monthly_limit_usd) * 100}
          />
        </div>
      )}

      {/* ── Errors ── */}
      <SectionHeader title={`Recent errors${hasErrors ? " ⚠" : ""}`} />
      <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Errors this month"
          value={errors.errors_month.toString()}
          alert={errors.errors_month > 0}
        />
        <StatCard
          label="Budget blocks month"
          value={errors.budget_exceeded_month.toString()}
          alert={errors.budget_exceeded_month > 0}
        />
      </div>
      <ErrorsTable errors={errors.recent} />
    </div>
  );
}
