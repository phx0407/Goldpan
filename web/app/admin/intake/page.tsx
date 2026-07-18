// app/admin/intake/page.tsx
// Intake OS — queue dashboard.
// Server component: fetches queue from FastAPI, renders summary + packet tables.

import Link from "next/link";
import { fetchIntakeQueue, APIError } from "@/lib/api";
import type { IntakePacketRow, IntakeQueueSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(s: string | null) {
  if (!s) return "—";
  return s.slice(0, 10);
}

function relAge(iso: string): string {
  const ms   = Date.now() - new Date(iso).getTime();
  const days = Math.floor(ms / 86_400_000);
  const hrs  = Math.floor(ms / 3_600_000);
  if (days > 0) return `${days}d ago`;
  if (hrs  > 0) return `${hrs}h ago`;
  return "just now";
}

function scoreColor(n: number | null) {
  if (n == null) return "text-stone-500";
  if (n >= 80) return "text-emerald-400";
  if (n >= 60) return "text-amber-400";
  return "text-red-400";
}

function statusBadge(s: string) {
  switch (s) {
    case "pending_review": return "bg-amber-900/50 text-amber-300";
    case "returned":       return "bg-red-900/50 text-red-300";
    case "approved":       return "bg-blue-900/50 text-blue-300";
    case "ingested":       return "bg-emerald-900/50 text-emerald-300";
    default:               return "bg-stone-700 text-stone-400";
  }
}

function statusLabel(s: string) {
  return s.replace(/_/g, " ");
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatChip({
  value, label, alert,
}: { value: number; label: string; alert?: boolean }) {
  return (
    <div className={`flex flex-col items-center px-4 py-2 rounded-lg border ${
      alert ? "border-amber-500/30 bg-amber-950/30" : "border-stone-800 bg-stone-900"
    }`}>
      <span className={`text-xl font-semibold tabular-nums leading-tight ${
        alert ? "text-amber-400" : "text-stone-100"
      }`}>{value}</span>
      <span className="text-[10px] font-medium uppercase tracking-widest text-stone-500 mt-0.5 whitespace-nowrap">
        {label}
      </span>
    </div>
  );
}

function PacketTable({
  packets, emptyMessage,
}: { packets: IntakePacketRow[]; emptyMessage: string }) {
  if (packets.length === 0) {
    return (
      <div className="rounded-lg border border-stone-800 bg-stone-900/40 px-4 py-6 text-center">
        <p className="text-sm text-stone-500">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-stone-700">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-stone-700 bg-stone-900">
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Restaurant</th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Status</th>
            <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Dishes</th>
            <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Flags</th>
            <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Evidence</th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Canvassed</th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Submitted</th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Model</th>
            <th className="px-4 py-2.5" />
          </tr>
        </thead>
        <tbody>
          {packets.map(p => (
            <tr key={p.packet_id} className="border-b border-stone-800 last:border-0 hover:bg-stone-800/40">
              <td className="px-4 py-2.5">
                <Link
                  href={`/admin/intake/${p.packet_id}`}
                  className="font-medium text-stone-200 hover:text-amber-400 transition-colors"
                >
                  {p.restaurant_name}
                </Link>
                <span className="ml-2 font-mono text-xs text-stone-500">{p.restaurant_external_id}</span>
                {p.return_reason && (
                  <p className="mt-0.5 text-xs text-red-400 truncate max-w-xs">{p.return_reason}</p>
                )}
              </td>
              <td className="px-4 py-2.5">
                <span className={`rounded px-1.5 py-0.5 text-xs font-medium capitalize ${statusBadge(p.packet_status)}`}>
                  {statusLabel(p.packet_status)}
                </span>
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums text-stone-300">{p.dish_count}</td>
              <td className={`px-4 py-2.5 text-right tabular-nums font-medium ${
                p.review_flag_count > 10 ? "text-amber-400" :
                p.review_flag_count > 0  ? "text-stone-300" : "text-stone-500"
              }`}>{p.review_flag_count || "—"}</td>
              <td className={`px-4 py-2.5 text-right tabular-nums font-medium ${scoreColor(p.evidence_score_overall)}`}>
                {p.evidence_score_overall ?? "—"}
              </td>
              <td className="px-4 py-2.5 text-xs text-stone-400">{fmtDate(p.canvass_date)}</td>
              <td className="px-4 py-2.5 text-xs text-stone-500">{relAge(p.submitted_at)}</td>
              <td className="px-4 py-2.5 text-xs text-stone-600 font-mono">{p.model_used ?? "—"}</td>
              <td className="px-4 py-2.5 text-right">
                <Link
                  href={`/admin/intake/${p.packet_id}`}
                  className="text-xs text-stone-500 hover:text-amber-400 transition-colors whitespace-nowrap"
                >
                  Review →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function IntakePage() {
  let data: Awaited<ReturnType<typeof fetchIntakeQueue>> | null = null;
  let fetchError: string | null = null;

  try {
    data = await fetchIntakeQueue();
  } catch (err) {
    fetchError =
      err instanceof APIError
        ? `${err.status} — ${err.detail}`
        : err instanceof Error ? err.message : "Unknown error.";
  }

  const summary: IntakeQueueSummary = data?.summary ?? {
    total: 0, pending_review: 0, returned: 0, approved: 0, ingested: 0,
  };
  const packets = data?.packets ?? [];

  const pending  = packets.filter(p => p.packet_status === "pending_review");
  const returned = packets.filter(p => p.packet_status === "returned");
  const approved = packets.filter(p => p.packet_status === "approved");
  const ingested = packets.filter(p => p.packet_status === "ingested");

  return (
    <div className="max-w-5xl">

      {/* ── Header ── */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-5">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-600 mb-0.5">
            Intake OS
          </p>
          <h1 className="text-2xl font-bold text-stone-100 leading-tight">Packet Queue</h1>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Link
            href="/admin/intake/submit"
            className="rounded-lg bg-amber-600 hover:bg-amber-500 px-3.5 py-1.5 text-xs font-medium text-white transition-colors"
          >
            + Submit Packet
          </Link>
        </div>
      </div>

      {/* ── Error state ── */}
      {fetchError && (
        <div className="mb-5 rounded-lg border border-amber-800/50 bg-amber-950/30 p-4">
          <p className="text-sm font-medium text-amber-400">Could not load intake queue</p>
          <p className="mt-1 font-mono text-xs text-amber-600">{fetchError}</p>
          <p className="mt-2 text-xs text-stone-500">
            Apply migration 015 in Supabase to create the intake_packets table, then restart the API.
          </p>
        </div>
      )}

      {/* ── Summary ── */}
      <div className="mb-6 flex flex-wrap gap-3">
        <StatChip value={summary.total}          label="Total"          />
        <StatChip value={summary.pending_review} label="Pending Review" alert={summary.pending_review > 0} />
        <StatChip value={summary.returned}       label="Returned"       alert={summary.returned > 0} />
        <StatChip value={summary.approved}       label="Approved"       />
        <StatChip value={summary.ingested}       label="Ingested"       />
      </div>

      {/* ── Pending review ── */}
      <section className="mb-8">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-stone-400 mb-3">
          Pending Review
          {pending.length > 0 && (
            <span className="ml-2 rounded-full bg-amber-600/20 text-amber-400 px-2 py-0.5 text-[10px] font-bold">
              {pending.length}
            </span>
          )}
        </h2>
        <PacketTable
          packets={pending}
          emptyMessage="No packets awaiting review."
        />
      </section>

      {/* ── Returned ── */}
      {returned.length > 0 && (
        <section className="mb-8">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-stone-400 mb-3">
            Returned to Canvasser
            <span className="ml-2 rounded-full bg-red-900/40 text-red-400 px-2 py-0.5 text-[10px] font-bold">
              {returned.length}
            </span>
          </h2>
          <PacketTable
            packets={returned}
            emptyMessage="No returned packets."
          />
        </section>
      )}

      {/* ── Approved ── */}
      {approved.length > 0 && (
        <section className="mb-8">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-stone-400 mb-3">
            Approved — Ready to Ingest
            <span className="ml-2 rounded-full bg-blue-900/40 text-blue-400 px-2 py-0.5 text-[10px] font-bold">
              {approved.length}
            </span>
          </h2>
          <PacketTable
            packets={approved}
            emptyMessage="No approved packets."
          />
          <p className="mt-2 text-xs text-stone-600">
            Run <span className="font-mono">python3 ingest_packet.py &lt;file&gt; --commit</span> for each approved packet, then mark it ingested from the packet detail page.
          </p>
        </section>
      )}

      {/* ── Recently ingested ── */}
      {ingested.length > 0 && (
        <section className="mb-8">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-stone-400 mb-3">
            Recently Ingested
          </h2>
          <PacketTable
            packets={ingested.slice(0, 10)}
            emptyMessage=""
          />
        </section>
      )}

      {/* ── Empty state ── */}
      {!fetchError && packets.length === 0 && (
        <div className="rounded-lg border border-stone-800 bg-stone-900/40 p-8 text-center">
          <p className="text-sm text-stone-400 mb-1">No intake packets yet.</p>
          <p className="text-xs text-stone-600">
            Run <span className="font-mono">python3 intake_agent.py</span> to produce a packet, then submit it here.
          </p>
        </div>
      )}

    </div>
  );
}
