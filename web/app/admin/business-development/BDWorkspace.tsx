"use client";

// BDWorkspace.tsx — BD Operational Workspace.
//
// Design principle: reduce work for the BD lead (Myles).
// "What should Myles immediately know, and what should he immediately do?"
//
// Layout: two-column on desktop — main content (left) + operational sidebar (right).
// Sidebar is always visible regardless of map/list view.
//
// Panels:
//   Quick Actions       — one-click navigation shortcuts
//   Today's Priorities  — overdue follow-ups, missing contacts, ready to publish
//   Recently Updated    — last 6 partners by updated_at
//   Incomplete Records  — count summary of missing data per field
//
// All interactivity:
//   Market selector (MarketContext) · Map/List toggle (localStorage) ·
//   Type/status filter pills · Shared filtered dataset (one pass, two views)

import { useState, useMemo, useEffect, useCallback } from "react";
import nextDynamic from "next/dynamic";
import Link from "next/link";
import { MarketProvider, useMarket } from "@/lib/market-context";
import type { PartnerRow, PartnerListSummary } from "@/lib/types";

// Leaflet map — client-only, no SSR
const PartnerMap = nextDynamic(() => import("./map/PartnerMap"), { ssr: false });

const VIEW_STORAGE_KEY = "gp-bd-view";

// ── Constants ─────────────────────────────────────────────────────────────────

const PIPELINE_ORDER = [
  "prospect", "outreach", "engaged", "negotiating", "active",
  "paused", "declined", "churned",
];

const PARTNER_TYPE_LABELS: Record<string, string> = {
  restaurant:             "Restaurant",
  dietitian:              "Dietitian",
  nutrition_clinic:       "Nutrition Clinic",
  gym:                    "Gym",
  corporate_wellness:     "Corporate Wellness",
  healthcare_partner:     "Healthcare",
  university:             "University",
  employer:               "Employer",
  food_brand:             "Food Brand",
  investor_grant:         "Investor / Grant",
  community_organization: "Community Org",
  media:                  "Media",
  other:                  "Other",
};

// ── Color helpers ─────────────────────────────────────────────────────────────

function statusColor(s: string) {
  switch (s) {
    case "active":      return "bg-emerald-900/50 text-emerald-300";
    case "engaged":     return "bg-blue-900/50 text-blue-300";
    case "negotiating": return "bg-violet-900/50 text-violet-300";
    case "outreach":    return "bg-sky-900/50 text-sky-300";
    case "prospect":    return "bg-stone-700 text-stone-400";
    case "paused":      return "bg-amber-900/50 text-amber-400";
    case "declined":    return "bg-red-900/50 text-red-400";
    case "churned":     return "bg-red-900/50 text-red-500";
    default:            return "bg-stone-700 text-stone-400";
  }
}

function typeColor(t: string) {
  switch (t) {
    case "restaurant":                     return "bg-amber-900/40 text-amber-300";
    case "dietitian":
    case "nutrition_clinic":
    case "healthcare_partner":             return "bg-teal-900/40 text-teal-300";
    case "gym":
    case "corporate_wellness":             return "bg-blue-900/40 text-blue-300";
    case "university":
    case "employer":                       return "bg-indigo-900/40 text-indigo-300";
    case "food_brand":                     return "bg-orange-900/40 text-orange-300";
    case "investor_grant":                 return "bg-violet-900/40 text-violet-300";
    case "media":                          return "bg-pink-900/40 text-pink-300";
    default:                               return "bg-stone-700 text-stone-400";
  }
}

function priorityColor(p: string) {
  switch (p) {
    case "high":   return "text-red-400";
    case "medium": return "text-amber-400";
    default:       return "text-stone-500";
  }
}

function coverageColor(n: number) {
  if (n >= 80) return "text-emerald-400";
  if (n >= 40) return "text-amber-400";
  return "text-red-400";
}

// ── Utility helpers ───────────────────────────────────────────────────────────

function fmtDate(d: string | null) {
  if (!d) return "—";
  return d.slice(0, 10);
}

function isOverdue(d: string | null) {
  if (!d) return false;
  return d.slice(0, 10) <= new Date().toISOString().slice(0, 10);
}

function daysOverdue(d: string): number {
  const diff =
    new Date(new Date().toISOString().slice(0, 10)).getTime() -
    new Date(d.slice(0, 10)).getTime();
  return Math.max(0, Math.floor(diff / 86_400_000));
}

function relTime(d: string): string {
  const ms   = Date.now() - new Date(d).getTime();
  const days = Math.floor(ms / 86_400_000);
  const hrs  = Math.floor(ms / 3_600_000);
  const mins = Math.floor(ms / 60_000);
  if (days > 0) return `${days}d ago`;
  if (hrs  > 0) return `${hrs}h ago`;
  if (mins > 0) return `${mins}m ago`;
  return "just now";
}

function pct(n: number) { return `${n.toFixed(0)}%`; }

// ── Shared sub-components ─────────────────────────────────────────────────────

function Badge({ label, className }: { label: string; className: string }) {
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${className}`}>
      {label.replace(/_/g, " ")}
    </span>
  );
}

function StatChip({
  value, label, alert,
}: { value: string | number; label: string; alert?: boolean }) {
  return (
    <div className={`flex flex-col items-center px-4 py-2 rounded-lg border ${
      alert ? "border-amber-500/30 bg-amber-950/30" : "border-stone-800 bg-stone-900"
    }`}>
      <span className={`text-xl font-semibold tabular-nums leading-tight ${
        alert ? "text-amber-400" : "text-stone-100"
      }`}>{value}</span>
      <span className="text-[10px] font-medium uppercase tracking-widest text-stone-500 mt-0.5 whitespace-nowrap">{label}</span>
    </div>
  );
}

function SidebarSection({
  title, children,
}: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-stone-800 bg-stone-900/60 overflow-hidden">
      <div className="px-3 py-2 border-b border-stone-800">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-500">
          {title}
        </p>
      </div>
      <div className="p-3">{children}</div>
    </div>
  );
}

// ── Pipeline funnel (list view) ───────────────────────────────────────────────

function PipelineFunnel({ summary }: { summary: PartnerListSummary }) {
  const active = PIPELINE_ORDER.filter(s => !["paused", "declined", "churned"].includes(s));
  const exits  = PIPELINE_ORDER.filter(s => ["paused", "declined", "churned"].includes(s));
  return (
    <div className="mb-6">
      <p className="text-xs font-medium uppercase tracking-widest text-stone-500 mb-2">Pipeline</p>
      <div className="flex flex-wrap gap-2 items-center">
        {active.map(s => {
          const count = summary.by_status[s] ?? 0;
          return (
            <div
              key={s}
              className={`flex items-center gap-2 rounded-lg border border-stone-700 bg-stone-900 px-3 py-1.5 ${count === 0 ? "opacity-40" : ""}`}
            >
              <span className={`w-2 h-2 rounded-full ${statusColor(s).split(" ")[0]}`} />
              <span className="text-xs text-stone-300 capitalize">{s}</span>
              <span className="text-sm font-semibold tabular-nums text-stone-200">{count}</span>
            </div>
          );
        })}
        <span className="text-stone-600 text-sm">→</span>
        {exits.map(s => {
          const count = summary.by_status[s] ?? 0;
          return (
            <div
              key={s}
              className={`flex items-center gap-2 rounded-lg border border-stone-800 bg-stone-900/50 px-3 py-1.5 ${count === 0 ? "opacity-30" : ""}`}
            >
              <span className="text-xs text-stone-500 capitalize">{s}</span>
              <span className="text-sm font-semibold tabular-nums text-stone-400">{count}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Needs-location queue (below map) ─────────────────────────────────────────

function NeedsLocationQueue({ partners }: { partners: PartnerRow[] }) {
  if (partners.length === 0) return null;
  return (
    <div className="shrink-0 mt-3">
      <p className="text-xs font-medium uppercase tracking-widest text-amber-600 mb-2">
        Needs Location ({partners.length})
      </p>
      <div className="rounded-lg border border-stone-800 bg-stone-900/60 overflow-auto max-h-40">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-stone-800 text-stone-500">
              <th className="text-left font-normal px-3 py-2">ID</th>
              <th className="text-left font-normal px-3 py-2">Name</th>
              <th className="text-left font-normal px-3 py-2">Type</th>
              <th className="text-left font-normal px-3 py-2">Status</th>
              <th className="text-left font-normal px-3 py-2">City / State</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {partners.map(p => (
              <tr
                key={p.partner_id}
                className="border-b border-stone-800/50 last:border-0 hover:bg-stone-800/30"
              >
                <td className="px-3 py-2 font-mono text-stone-600">{p.external_id}</td>
                <td className="px-3 py-2 text-stone-300">{p.name}</td>
                <td className="px-3 py-2 text-stone-500 capitalize">{p.partner_type.replace(/_/g, " ")}</td>
                <td className="px-3 py-2">
                  <Badge label={p.status} className={statusColor(p.status)} />
                </td>
                <td className="px-3 py-2 text-stone-500">
                  {[p.city, p.state].filter(Boolean).join(", ") || "—"}
                </td>
                <td className="px-3 py-2 text-right">
                  <Link
                    href={`/admin/business-development/${p.external_id}/edit`}
                    className="text-amber-600 hover:text-amber-400 transition-colors"
                  >
                    Add location
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Sidebar: Today's Priorities ───────────────────────────────────────────────

interface Priority {
  id:        string;
  label:     string;
  sublabel?: string;
  href:      string;
  severity:  "high" | "medium" | "low";
}

function TodaysPriorities({ priorities }: { priorities: Priority[] }) {
  const SHOW  = 7;
  const shown = priorities.slice(0, SHOW);
  const rest  = priorities.length - SHOW;

  if (priorities.length === 0) {
    return <p className="text-xs text-stone-600 italic">Nothing urgent right now.</p>;
  }

  return (
    <div className="flex flex-col gap-1">
      {shown.map(p => (
        <Link
          key={p.id}
          href={p.href}
          className="group flex flex-col gap-0.5 rounded-md px-2 py-1.5 hover:bg-stone-800/60 transition-colors"
        >
          <div className="flex items-start gap-1.5">
            <span
              className={`mt-[3px] shrink-0 text-[8px] leading-none ${
                p.severity === "high"   ? "text-red-400"   :
                p.severity === "medium" ? "text-amber-400" :
                                          "text-stone-500"
              }`}
            >●</span>
            <span className="text-xs text-stone-300 group-hover:text-amber-400 transition-colors leading-tight truncate">
              {p.label}
            </span>
          </div>
          {p.sublabel && (
            <p className="pl-[18px] text-[10px] text-stone-600 leading-tight">{p.sublabel}</p>
          )}
        </Link>
      ))}
      {rest > 0 && (
        <p className="text-[10px] text-stone-600 pl-2 mt-0.5">+{rest} more</p>
      )}
    </div>
  );
}

// ── Sidebar: Recently Updated ─────────────────────────────────────────────────

function RecentlyUpdated({ partners }: { partners: PartnerRow[] }) {
  const recent = useMemo(
    () =>
      [...partners]
        .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
        .slice(0, 6),
    [partners],
  );

  return (
    <div className="flex flex-col gap-0.5">
      {recent.map(p => (
        <Link
          key={p.partner_id}
          href={`/admin/business-development/${p.external_id}`}
          className="group flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-stone-800/60 transition-colors"
        >
          <span className="text-xs text-stone-300 group-hover:text-amber-400 transition-colors truncate mr-2">
            {p.name}
          </span>
          <span className="text-[10px] text-stone-600 shrink-0 tabular-nums">
            {relTime(p.updated_at)}
          </span>
        </Link>
      ))}
    </div>
  );
}

// ── Sidebar: Incomplete Records ───────────────────────────────────────────────

interface IncompleteGroup { label: string; count: number; }

function IncompleteRecords({ groups }: { groups: IncompleteGroup[] }) {
  const nonzero = groups.filter(g => g.count > 0);
  if (nonzero.length === 0) {
    return <p className="text-xs text-stone-600 italic">All records look complete.</p>;
  }
  return (
    <div className="flex flex-col gap-1.5">
      {nonzero.map(g => (
        <div key={g.label} className="flex items-center justify-between px-2">
          <span className="text-xs text-stone-500">{g.label}</span>
          <span className="text-xs font-semibold tabular-nums text-amber-500">{g.count}</span>
        </div>
      ))}
    </div>
  );
}

// ── Inner workspace (consumes MarketContext) ───────────────────────────────────

interface BDWorkspaceProps {
  partners: PartnerRow[];
  summary:  PartnerListSummary;
}

function BDWorkspaceInner({ partners, summary }: BDWorkspaceProps) {
  const { market, setMarket, markets } = useMarket();

  // ── View toggle — persisted ────────────────────────────────────────────────
  const [view, setView] = useState<"map" | "list">("map");

  useEffect(() => {
    const saved = localStorage.getItem(VIEW_STORAGE_KEY) as "map" | "list" | null;
    if (saved === "map" || saved === "list") setView(saved);
  }, []);

  const switchView = useCallback((v: "map" | "list") => {
    setView(v);
    localStorage.setItem(VIEW_STORAGE_KEY, v);
  }, []);

  // ── Filters ────────────────────────────────────────────────────────────────
  const [typeFilter,   setTypeFilter]   = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);

  // ── Shared filtered dataset ────────────────────────────────────────────────
  const filtered = useMemo(() => {
    let r = partners;
    if (typeFilter)   r = r.filter(p => p.partner_type === typeFilter);
    if (statusFilter) r = r.filter(p => p.status       === statusFilter);
    return r;
  }, [partners, typeFilter, statusFilter]);

  const mapped        = useMemo(() => filtered.filter(p => p.latitude  != null && p.longitude != null), [filtered]);
  const needsLocation = useMemo(() => filtered.filter(p => p.latitude  == null || p.longitude == null), [filtered]);

  // ── Enhanced market summary ────────────────────────────────────────────────
  const marketStats = useMemo(() => {
    const rests     = partners.filter(p => p.partner_type === "restaurant");
    const published = rests.filter(p => p.intel?.lifecycle_status === "published");
    const withIntel = rests.filter(p => p.intel != null);
    const avgTrans  = withIntel.length > 0
      ? withIntel.reduce((s, p) => s + p.intel!.transparency_coverage_pct, 0) / withIntel.length
      : null;
    const freshPct  = withIntel.length > 0
      ? (withIntel.filter(p => p.intel!.recanvass_status === "current").length / withIntel.length) * 100
      : null;
    return {
      total:       summary.total,
      restaurants: summary.by_type["restaurant"] ?? 0,
      published:   published.length,
      prospects:   summary.by_status["prospect"] ?? 0,
      followups:   summary.follow_ups_due,
      avgTrans,
      freshPct,
    };
  }, [partners, summary]);

  const typesPresent = useMemo(
    () => Array.from(new Set(partners.map(p => p.partner_type))).sort(),
    [partners],
  );

  const clearFilters = () => { setTypeFilter(null); setStatusFilter(null); };
  const hasFilters   = typeFilter !== null || statusFilter !== null;

  const handleMarketChange = (id: string) => {
    const m = markets.find(m => m.id === id);
    if (m) setMarket(m);
  };

  // ── Today's Priorities (from ALL partners — not affected by filters) ────────
  const priorities = useMemo((): Priority[] => {
    const today = new Date().toISOString().slice(0, 10);
    const items: Priority[] = [];

    // HIGH — overdue follow-ups (sorted oldest first)
    [...partners]
      .filter(p => p.next_followup_date && p.next_followup_date.slice(0, 10) <= today)
      .sort((a, b) => a.next_followup_date!.localeCompare(b.next_followup_date!))
      .forEach(p => {
        const d = daysOverdue(p.next_followup_date!);
        items.push({
          id:       `fu-${p.partner_id}`,
          label:    p.name,
          sublabel: d === 0 ? "Follow-up due today" : `Follow-up ${d}d overdue`,
          href:     `/admin/business-development/${p.external_id}`,
          severity: "high",
        });
      });

    // MEDIUM — restaurant partners ready for publication review
    partners
      .filter(p =>
        p.partner_type === "restaurant" &&
        ["qa_review", "verification"].includes(p.intel?.lifecycle_status ?? ""),
      )
      .forEach(p => {
        items.push({
          id:       `pub-${p.partner_id}`,
          label:    p.name,
          sublabel: `Ready to review · ${p.intel?.lifecycle_status?.replace(/_/g, " ")}`,
          href:     `/admin/business-development/${p.external_id}`,
          severity: "medium",
        });
      });

    // MEDIUM — active/engaged/negotiating with no contact name
    partners
      .filter(p => !p.contact_name && ["active", "engaged", "negotiating"].includes(p.status))
      .forEach(p => {
        items.push({
          id:       `nc-${p.partner_id}`,
          label:    p.name,
          sublabel: `No contact · ${p.status}`,
          href:     `/admin/business-development/${p.external_id}`,
          severity: "medium",
        });
      });

    return items;
  }, [partners]);

  // ── Incomplete records summary ─────────────────────────────────────────────
  const incomplete = useMemo((): IncompleteGroup[] => {
    const rests = partners.filter(p => p.partner_type === "restaurant");
    return [
      { label: "No follow-up set",  count: partners.filter(p => !p.next_followup_date && ["active","engaged","negotiating","outreach"].includes(p.status)).length },
      { label: "No contact name",   count: partners.filter(p => !p.contact_name).length },
      { label: "No relationship owner", count: partners.filter(p => !p.relationship_owner).length },
      { label: "No address",        count: partners.filter(p => !p.address).length },
      { label: "No phone (rest.)",  count: rests.filter(p => !p.phone).length },
      { label: "No website (rest.)", count: rests.filter(p => !p.website).length },
    ];
  }, [partners]);

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="max-w-screen-2xl grid grid-cols-1 lg:grid-cols-[1fr_256px] gap-x-5 items-start">

      {/* ── Main column ──────────────────────────────────────────────────── */}
      <div className="min-w-0">

        {/* Market hero + view controls */}
        <div className="flex flex-wrap items-start justify-between gap-3 mb-5">

          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-600 mb-0.5">
              Business Development
            </p>
            {markets.length === 1 ? (
              <div className="flex items-baseline gap-2">
                <h1 className="text-2xl font-bold text-stone-100 leading-tight">
                  {market.name}
                </h1>
                <span className="text-sm text-stone-600">{market.state} · Operating market</span>
              </div>
            ) : (
              <div className="flex items-baseline gap-2">
                <div className="relative">
                  <select
                    value={market.id}
                    onChange={e => handleMarketChange(e.target.value)}
                    className="appearance-none text-2xl font-bold text-stone-100 bg-transparent border-none cursor-pointer focus:outline-none pr-6"
                  >
                    {markets.map(m => (
                      <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                  </select>
                  <span className="pointer-events-none absolute right-0 top-1/2 -translate-y-1/2 text-stone-500 text-xs">▾</span>
                </div>
                <span className="text-sm text-stone-600">{market.state} · Operating market</span>
              </div>
            )}
          </div>

          {/* View toggle + new partner */}
          <div className="flex items-center gap-2 shrink-0">
            <div className="flex rounded-lg border border-stone-700 overflow-hidden text-xs font-medium">
              <button
                onClick={() => switchView("map")}
                className={`px-3.5 py-1.5 transition-colors ${
                  view === "map"
                    ? "bg-amber-600/20 text-amber-400 border-r border-amber-600/30"
                    : "bg-stone-900 text-stone-500 hover:text-stone-300 border-r border-stone-700"
                }`}
              >
                Map
              </button>
              <button
                onClick={() => switchView("list")}
                className={`px-3.5 py-1.5 transition-colors ${
                  view === "list"
                    ? "bg-amber-600/20 text-amber-400"
                    : "bg-stone-900 text-stone-500 hover:text-stone-300"
                }`}
              >
                List
              </button>
            </div>
            <Link
              href="/admin/business-development/new"
              className="rounded-lg bg-amber-600 hover:bg-amber-500 px-3.5 py-1.5 text-xs font-medium text-white transition-colors"
            >
              + New Partner
            </Link>
          </div>
        </div>

        {/* Market summary */}
        <div className="mb-5 rounded-lg border border-stone-800 bg-stone-900/40 px-4 py-3">
          <div className="flex flex-wrap gap-3">
            <StatChip value={marketStats.total}       label="Partners"       />
            <StatChip value={marketStats.restaurants} label="Restaurants"    />
            <StatChip value={marketStats.published}   label="Published"      />
            <StatChip value={marketStats.prospects}   label="Prospects"      />
            <StatChip
              value={marketStats.followups}
              label="Follow-ups Due"
              alert={marketStats.followups > 0}
            />
            {marketStats.avgTrans != null && (
              <StatChip value={pct(marketStats.avgTrans)} label="Avg Trans%" />
            )}
            {marketStats.freshPct != null && (
              <StatChip value={pct(marketStats.freshPct)} label="Fresh" />
            )}
          </div>
        </div>

        {/* Filter pills */}
        <div className="flex flex-wrap gap-2 mb-4 items-center">
          <button
            onClick={clearFilters}
            className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
              !hasFilters ? "bg-amber-600 text-white" : "bg-stone-800 text-stone-400 hover:text-stone-200"
            }`}
          >
            All ({summary.total})
          </button>
          {typesPresent.map(t => (
            <button
              key={t}
              onClick={() => setTypeFilter(typeFilter === t ? null : t)}
              className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                typeFilter === t
                  ? "bg-amber-600 text-white"
                  : "bg-stone-800 text-stone-400 hover:text-stone-200"
              }`}
            >
              {PARTNER_TYPE_LABELS[t] ?? t} ({summary.by_type[t] ?? 0})
            </button>
          ))}
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="rounded px-2 py-1 text-xs text-stone-500 hover:text-stone-300 border border-stone-800 hover:border-stone-700 transition-colors"
            >
              Clear ✕
            </button>
          )}
          <span className="ml-auto text-xs text-stone-600 tabular-nums">
            {filtered.length} of {summary.total}
            {view === "map" && ` · ${mapped.length} on map`}
          </span>
        </div>

        {/* Map view */}
        {view === "map" && (
          <div
            className="flex flex-col"
            style={{ height: "calc(100vh - 20rem)", minHeight: "400px", maxHeight: "760px" }}
          >
            <div className="flex-1 min-h-0 rounded-lg border border-stone-700 overflow-hidden">
              <PartnerMap
                partners={filtered}
                needsLocation={needsLocation}
                center={market.center}
                zoom={market.zoom}
              />
            </div>
            <NeedsLocationQueue partners={needsLocation} />
          </div>
        )}

        {/* List view */}
        {view === "list" && (
          <div>
            <PipelineFunnel summary={summary} />

            {filtered.length === 0 ? (
              <div className="rounded-lg border border-stone-700 bg-stone-900 p-8 text-center">
                <p className="text-sm text-stone-500">No partners match the current filter.</p>
                <button
                  onClick={clearFilters}
                  className="mt-2 text-xs text-stone-500 hover:text-amber-400 transition-colors"
                >
                  Clear filters
                </button>
              </div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-stone-700">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-stone-700 bg-stone-900">
                      <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400 w-14">ID</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Name</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Type</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Status</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Pri</th>
                      <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Score</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Contact</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Last Contact</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Follow-up</th>
                      <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Dishes</th>
                      <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Trans%</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Freshness</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map(p => {
                      const overdue = isOverdue(p.next_followup_date);
                      return (
                        <tr
                          key={p.partner_id}
                          className="border-b border-stone-800 last:border-0 hover:bg-stone-800/40"
                        >
                          <td className="px-4 py-2.5 font-mono text-xs text-stone-400">{p.external_id}</td>
                          <td className="px-4 py-2.5">
                            <Link
                              href={`/admin/business-development/${p.external_id}`}
                              className="font-medium text-stone-200 hover:text-amber-400 transition-colors"
                            >
                              {p.name}
                            </Link>
                            {(p.city || p.state) && (
                              <span className="ml-2 text-xs text-stone-500">
                                {[p.city, p.state].filter(Boolean).join(", ")}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-2.5">
                            <Badge
                              label={PARTNER_TYPE_LABELS[p.partner_type] ?? p.partner_type}
                              className={typeColor(p.partner_type)}
                            />
                          </td>
                          <td className="px-4 py-2.5">
                            <Badge label={p.status} className={statusColor(p.status)} />
                          </td>
                          <td className={`px-4 py-2.5 text-xs font-medium capitalize ${priorityColor(p.priority)}`}>
                            {p.priority}
                          </td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-stone-300">
                            {p.opportunity_score ?? "—"}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-stone-300">{p.contact_name ?? "—"}</td>
                          <td className="px-4 py-2.5 text-xs text-stone-400">{fmtDate(p.last_contact_date)}</td>
                          <td className={`px-4 py-2.5 text-xs font-medium ${overdue && p.next_followup_date ? "text-amber-400" : "text-stone-400"}`}>
                            {fmtDate(p.next_followup_date)}
                            {overdue && p.next_followup_date && <span className="ml-1">⚠</span>}
                          </td>
                          <td className="px-4 py-2.5 text-right tabular-nums text-stone-300">
                            {p.intel ? p.intel.dish_count : "—"}
                          </td>
                          <td className={`px-4 py-2.5 text-right tabular-nums ${p.intel ? coverageColor(p.intel.transparency_coverage_pct) : "text-stone-500"}`}>
                            {p.intel ? pct(p.intel.transparency_coverage_pct) : "—"}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-stone-400">
                            {p.intel ? p.intel.recanvass_status.replace(/_/g, " ") : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            <p className="mt-6 text-xs text-stone-600">
              Analytics ingestion not yet active — schema is ready.
            </p>
          </div>
        )}

      </div>

      {/* ── Operational sidebar ──────────────────────────────────────────────── */}
      <div className="hidden lg:flex flex-col gap-3 sticky top-4">

        {/* Quick Actions */}
        <SidebarSection title="Quick Actions">
          <div className="flex flex-col gap-0.5">
            <Link
              href="/admin/business-development/new"
              className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs font-medium text-stone-400 hover:text-amber-400 hover:bg-stone-800/60 transition-colors"
            >
              <span className="text-stone-600 w-3 text-center">+</span>
              New Partner
            </Link>
            <button
              onClick={() => switchView("list")}
              className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs font-medium text-stone-400 hover:text-amber-400 hover:bg-stone-800/60 transition-colors text-left w-full"
            >
              <span className="text-stone-600 w-3 text-center">≡</span>
              View Pipeline
            </button>
            <button
              onClick={() => switchView("map")}
              className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs font-medium text-stone-400 hover:text-amber-400 hover:bg-stone-800/60 transition-colors text-left w-full"
            >
              <span className="text-stone-600 w-3 text-center">◎</span>
              View Map
            </button>
          </div>
        </SidebarSection>

        {/* Today's Priorities */}
        <SidebarSection
          title={`Today's Priorities${priorities.length > 0 ? ` · ${priorities.length}` : ""}`}
        >
          <TodaysPriorities priorities={priorities} />
        </SidebarSection>

        {/* Recently Updated */}
        <SidebarSection title="Recently Updated">
          <RecentlyUpdated partners={partners} />
        </SidebarSection>

        {/* Incomplete Records */}
        <SidebarSection title="Incomplete Records">
          <IncompleteRecords groups={incomplete} />
        </SidebarSection>

      </div>

    </div>
  );
}

// ── Exported component wraps with MarketProvider ──────────────────────────────

export default function BDWorkspace(props: BDWorkspaceProps) {
  return (
    <MarketProvider>
      <BDWorkspaceInner {...props} />
    </MarketProvider>
  );
}
