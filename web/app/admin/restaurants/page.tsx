// app/admin/restaurants/page.tsx
// Server component — bird's-eye view of all GoldPan restaurants.

import Link from "next/link";
import { fetchRestaurantList, APIError } from "@/lib/api";
import type { RestaurantSummaryRow, RestaurantListSummary } from "@/lib/types";

export const revalidate = 60;

// ── Helpers ───────────────────────────────────────────────────────────────────

function pct(n: number) {
  return `${n.toFixed(0)}%`;
}

function lifecycleColor(s: string) {
  switch (s) {
    case "published":            return "bg-emerald-900/50 text-emerald-300";
    case "qa_review":            return "bg-amber-900/50 text-amber-300";
    case "verification":         return "bg-amber-900/50 text-amber-300";
    case "evidence_acquisition": return "bg-blue-900/50 text-blue-300";
    case "onboarding":           return "bg-blue-900/50 text-blue-300";
    case "qualified":            return "bg-blue-900/50 text-blue-300";
    case "recanvassing":         return "bg-amber-900/50 text-amber-300";
    case "prospect":             return "bg-stone-700 text-stone-400";
    case "suspended":            return "bg-red-900/50 text-red-300";
    default:                     return "bg-stone-700 text-stone-400";
  }
}

function recanvassColor(s: string) {
  switch (s) {
    case "current":      return "text-emerald-400";
    case "due_soon":     return "text-amber-400";
    case "overdue":      return "text-red-400";
    case "needs_review": return "text-stone-500";
    default:             return "text-stone-500";
  }
}

function coverageColor(pctVal: number) {
  if (pctVal >= 80) return "text-emerald-400";
  if (pctVal >= 40) return "text-amber-400";
  return "text-red-400";
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SummaryCard({
  label,
  value,
  sub,
  alert,
}: {
  label: string;
  value: string | number;
  sub?: string;
  alert?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-4 ${
        alert ? "border-amber-500/40 bg-amber-950/30" : "border-stone-700 bg-stone-900"
      }`}
    >
      <p className="text-xs font-medium uppercase tracking-widest text-stone-400">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${alert ? "text-amber-400" : "text-stone-100"}`}>
        {value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-stone-400">{sub}</p>}
    </div>
  );
}

function Badge({ label, className }: { label: string; className: string }) {
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${className}`}>
      {label.replace(/_/g, " ")}
    </span>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function RestaurantsPage() {
  let data: Awaited<ReturnType<typeof fetchRestaurantList>> | null = null;
  let fetchError: string | null = null;

  try {
    data = await fetchRestaurantList();
  } catch (err) {
    fetchError =
      err instanceof APIError
        ? `${err.status} — ${err.detail}`
        : err instanceof Error
          ? err.message
          : "Unknown error.";
  }

  if (fetchError) {
    return (
      <div className="flex flex-col gap-3">
        <h1 className="text-lg font-semibold text-stone-100">Restaurants</h1>
        <div className="rounded-lg border border-red-800 bg-red-950/40 p-5">
          <p className="text-sm font-medium text-red-400">Could not load restaurants</p>
          <p className="mt-1 font-mono text-xs text-red-500">{fetchError}</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { summary: s, restaurants } = data;
  const hasUrgent = s.recanvass_overdue > 0 || s.recanvass_needs_review > 0;

  return (
    <div className="max-w-7xl">
      {/* Header */}
      <div className="flex items-baseline gap-3 mb-1">
        <h1 className="text-lg font-semibold text-stone-100">Restaurants</h1>
        <span className="text-xs text-stone-400">{s.total} total</span>
      </div>
      <p className="text-xs text-stone-500 mb-6">
        Bird's-eye view · refreshes every 60 s
      </p>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-8">
        <SummaryCard label="Total"     value={s.total}     sub={`${s.published} published`} />
        <SummaryCard label="Published" value={s.published} sub="lifecycle status" />
        <SummaryCard
          label="Needs review"
          value={s.recanvass_needs_review}
          sub="freshness · needs_review"
          alert={s.recanvass_needs_review > 0}
        />
        <SummaryCard
          label="Overdue"
          value={s.recanvass_overdue}
          sub="freshness · overdue"
          alert={s.recanvass_overdue > 0}
        />
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-stone-700">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-stone-700 bg-stone-900">
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400 w-8">ID</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Name</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Status</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Freshness</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Dishes</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Ings</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Trans %</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Avg Score</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Cal %</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Claims</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Unknown</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Canvassed</th>
            </tr>
          </thead>
          <tbody>
            {restaurants.map((r) => (
              <tr
                key={r.restaurant_id}
                className="border-b border-stone-800 last:border-0 hover:bg-stone-800/40"
              >
                <td className="px-4 py-2.5 font-mono text-xs text-stone-400">{r.external_id}</td>
                <td className="px-4 py-2.5">
                  <Link
                    href={`/admin/restaurants/${r.external_id}`}
                    className="font-medium text-stone-200 hover:text-amber-400 transition-colors"
                  >
                    {r.name}
                  </Link>
                  {r.location && (
                    <span className="ml-2 text-xs text-stone-500">{r.location}</span>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  <Badge label={r.lifecycle_status} className={lifecycleColor(r.lifecycle_status)} />
                </td>
                <td className={`px-4 py-2.5 text-xs font-medium ${recanvassColor(r.recanvass_status)}`}>
                  {r.recanvass_status.replace(/_/g, " ")}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-stone-300">{r.dish_count}</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-stone-300">{r.ingredient_count}</td>
                <td className={`px-4 py-2.5 text-right tabular-nums ${coverageColor(r.transparency_coverage_pct)}`}>
                  {pct(r.transparency_coverage_pct)}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-stone-300">
                  {r.avg_transparency_score !== null ? r.avg_transparency_score : "—"}
                </td>
                <td className={`px-4 py-2.5 text-right tabular-nums ${coverageColor(r.calorie_coverage_pct)}`}>
                  {pct(r.calorie_coverage_pct)}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-stone-300">{r.claims_count}</td>
                <td className={`px-4 py-2.5 text-right tabular-nums ${r.unknown_filter_count > 0 ? "text-amber-400" : "text-stone-500"}`}>
                  {r.unknown_filter_count > 0 ? r.unknown_filter_count : "—"}
                </td>
                <td className="px-4 py-2.5 text-xs text-stone-400">
                  {r.last_canvassed ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
