// app/admin/business-development/map/page.tsx
// Geographic view of the BD partner pipeline.
// Color-coded CircleMarkers by status. Partners without coords shown in a queue below.

import nextDynamic from "next/dynamic";
import Link from "next/link";
import { fetchPartnerList, APIError } from "@/lib/api";
import type { PartnerRow } from "@/lib/types";
// Leaflet CSS — must be a global import so it reaches the client bundle
import "leaflet/dist/leaflet.css";

export const dynamic = "force-dynamic";

// Load Leaflet map client-side only (Leaflet requires window)
const PartnerMap = nextDynamic(() => import("./PartnerMap"), { ssr: false });

// ── Status colours (Tailwind classes, mirrors PartnerMap.tsx hex values) ──────

function statusBadge(s: string) {
  switch (s) {
    case "active":      return "bg-emerald-900/50 text-emerald-300";
    case "engaged":     return "bg-blue-900/50 text-blue-300";
    case "negotiating": return "bg-violet-900/50 text-violet-300";
    case "outreach":    return "bg-sky-900/50 text-sky-300";
    case "paused":      return "bg-amber-900/50 text-amber-400";
    case "declined":    return "bg-red-900/50 text-red-400";
    case "churned":     return "bg-red-900/50 text-red-500";
    default:            return "bg-stone-700 text-stone-400";
  }
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function BDMapPage() {
  let partners: PartnerRow[] = [];
  let fetchError: string | null = null;

  try {
    const data = await fetchPartnerList();
    partners = data.partners;
  } catch (err) {
    fetchError =
      err instanceof APIError
        ? `${err.status} — ${err.detail}`
        : err instanceof Error ? err.message : "Unknown error.";
  }

  const mapped       = partners.filter(p => p.latitude != null && p.longitude != null);
  const needsLocation = partners.filter(p => p.latitude == null || p.longitude == null);

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-h-[900px]">
      {/* Header */}
      <div className="flex items-center justify-between px-1 pb-3 shrink-0">
        <div>
          <div className="flex items-baseline gap-3">
            <h1 className="text-lg font-semibold text-stone-100">Partner Map</h1>
            <span className="text-xs text-stone-500">
              {mapped.length} mapped · {needsLocation.length} need location
            </span>
          </div>
          <div className="flex gap-3 mt-1">
            <Link
              href="/admin/business-development"
              className="text-xs text-stone-600 hover:text-stone-400 transition-colors"
            >
              ← Pipeline
            </Link>
            <Link
              href="/admin/business-development/new"
              className="text-xs text-amber-600 hover:text-amber-400 transition-colors"
            >
              + New Partner
            </Link>
          </div>
        </div>
      </div>

      {/* Error state */}
      {fetchError && (
        <div className="rounded-lg border border-red-800 bg-red-950/40 p-4 text-sm text-red-400">
          {fetchError}
        </div>
      )}

      {/* Map */}
      {!fetchError && (
        <div className="flex-1 rounded-lg border border-stone-700 overflow-hidden min-h-0">
          <PartnerMap partners={partners} needsLocation={needsLocation} />
        </div>
      )}

      {/* Needs Location queue */}
      {needsLocation.length > 0 && (
        <div className="shrink-0 mt-3">
          <p className="text-xs font-medium uppercase tracking-widest text-amber-600 mb-2">
            Needs Location ({needsLocation.length})
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
                {needsLocation.map(p => (
                  <tr key={p.partner_id} className="border-b border-stone-800/50 last:border-0 hover:bg-stone-800/30">
                    <td className="px-3 py-2 font-mono text-stone-600">{p.external_id}</td>
                    <td className="px-3 py-2 text-stone-300">{p.name}</td>
                    <td className="px-3 py-2 text-stone-500 capitalize">{p.partner_type.replace(/_/g, " ")}</td>
                    <td className="px-3 py-2">
                      <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${statusBadge(p.status)}`}>
                        {p.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-stone-500">
                      {[p.city, p.state].filter(Boolean).join(", ") || "—"}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Link
                        href={`/admin/business-development/${p.external_id}/edit`}
                        className="text-amber-600 hover:text-amber-400"
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
      )}
    </div>
  );
}
