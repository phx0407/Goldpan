// app/admin/intake/[id]/page.tsx
// Intake OS — packet detail + review workspace.
// Server component: fetches packet, renders structured evidence, exposes the
// DEC000001 packet-lifecycle commands (claim/release/approve/return/reject/
// edit_payload/resubmit/archive/ingest).
//
// Button visibility mirrors the preconditions enforced by the authoritative
// Postgres RPCs (supabase/migrations/017-019) — the UI does not invent state
// transitions of its own. Every mutation calls performIntakeAction() (lib/api.ts)
// and then redirects back to this page so it re-fetches from server state.
// Failures surface via an ?error= query param banner rather than failing silently.

import React from "react";
import { redirect, notFound } from "next/navigation";
import Link from "next/link";
import { fetchIntakePacket, performIntakeAction, APIError } from "@/lib/api";

export const dynamic = "force-dynamic";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(s: string | null | undefined) {
  if (!s) return "—";
  return s.slice(0, 10);
}

function fmtDateTime(s: string | null | undefined) {
  if (!s) return "—";
  try {
    const d = new Date(s);
    return (
      d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) +
      " · " +
      d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
    );
  } catch {
    return s.slice(0, 16);
  }
}

function scoreColor(n: number | null | undefined) {
  if (n == null) return "text-stone-500";
  if (n >= 80) return "text-emerald-400";
  if (n >= 60) return "text-amber-400";
  return "text-red-400";
}

function statusBadge(s: string) {
  switch (s) {
    case "pending_review": return "bg-amber-900/50 text-amber-300";
    case "in_review":      return "bg-sky-900/50 text-sky-300";
    case "returned":       return "bg-red-900/50 text-red-300";
    case "approved":       return "bg-blue-900/50 text-blue-300";
    case "rejected":       return "bg-rose-950/60 text-rose-300";
    case "ingested":       return "bg-emerald-900/50 text-emerald-300";
    default:               return "bg-stone-700 text-stone-400";
  }
}

function statusLabel(s: string) {
  return s.replace(/_/g, " ");
}

function flagSeverityColor(type: string) {
  if (["allergen_claim", "safety_concern", "false_claim"].some(t => type.includes(t))) {
    return "border-red-800/50 bg-red-950/20";
  }
  if (["hedged", "uncertain", "missing", "incomplete"].some(t => type.includes(t))) {
    return "border-amber-800/40 bg-amber-950/10";
  }
  return "border-stone-700 bg-stone-900/20";
}

function flagTypeLabel(type: string) {
  return type.replace(/_/g, " ");
}

// ── Safe value rendering ───────────────────────────────────────────────────────
// packet_data fields are typed loosely; the agent may emit objects or arrays
// where strings are expected. These helpers prevent "Objects are not valid as
// a React child" crashes throughout the detail page.

// Known scalar-like keys to extract from unknown objects, in priority order.
const SCALAR_KEYS = [
  "note", "message", "description", "text", "reason",
  "dish", "label", "value", "name", "type", "severity",
] as const;

/** Convert any value to a safe display string (no JSX). */
function safeStr(val: unknown): string {
  if (val == null)                  return "";
  if (typeof val === "string")      return val;
  if (typeof val === "number" || typeof val === "boolean") return String(val);
  if (Array.isArray(val))           return val.map(safeStr).filter(Boolean).join(" · ");
  if (typeof val === "object") {
    const obj = val as Record<string, unknown>;
    for (const k of SCALAR_KEYS) {
      if (k in obj && (typeof obj[k] === "string" || typeof obj[k] === "number")) {
        return String(obj[k]);
      }
    }
    try { return JSON.stringify(val); } catch { return "[object]"; }
  }
  return String(val);
}

/** Render any value as React nodes — objects become field lists, arrays become <ul>. */
function renderValue(val: unknown, depth = 0): React.ReactNode {
  if (val == null)             return null;
  if (typeof val === "string") return val;
  if (typeof val === "number" || typeof val === "boolean") return String(val);

  if (Array.isArray(val)) {
    if (val.length === 0) return null;
    return (
      <ul className="list-disc list-inside space-y-0.5">
        {val.map((item, i) => (
          <li key={i} className="text-stone-400">{renderValue(item, depth + 1)}</li>
        ))}
      </ul>
    );
  }

  if (typeof val === "object") {
    const obj = val as Record<string, unknown>;
    // If there's a single dominant text field, just return it inline
    for (const k of SCALAR_KEYS) {
      if (Object.keys(obj).length === 1 && k in obj) return safeStr(obj[k]);
    }
    // Otherwise render as compact key/value pairs
    if (depth > 1) {
      // Avoid deep nesting — stringify instead
      try { return <code className="text-stone-500 text-[10px]">{JSON.stringify(val)}</code>; }
      catch { return "[object]"; }
    }
    return (
      <dl className="space-y-0.5">
        {Object.entries(obj).map(([k, v]) => (
          <div key={k} className="flex gap-2">
            <dt className="text-stone-600 shrink-0 capitalize">{k.replace(/_/g, " ")}:</dt>
            <dd className="text-stone-400">{renderValue(v, depth + 1)}</dd>
          </div>
        ))}
      </dl>
    );
  }

  return String(val);
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function IntakeDetailPage({
  params,
  searchParams,
}: {
  params: { id: string };
  searchParams?: { error?: string; action?: string };
}) {
  let data: Awaited<ReturnType<typeof fetchIntakePacket>> | null = null;

  try {
    data = await fetchIntakePacket(params.id);
  } catch (err) {
    if (err instanceof APIError && err.status === 404) notFound();
    throw err;
  }

  const { packet } = data!;
  const pd = packet.packet_data;

  const dishes   = (pd.dishes         ?? []) as Record<string, unknown>[];
  const rawFlags = (pd.review_flags   ?? []) as unknown[];
  const advisory = Array.isArray(pd.advisory_notes) ? pd.advisory_notes as unknown[] : [];

  // Normalize flags — the agent may emit objects that don't perfectly match ReviewFlag.
  // We read every field defensively via safeStr / direct access.
  interface NormFlag {
    type:             string;
    dish:             unknown;
    phrase:           unknown;
    reason:           unknown;
    suggested_action: unknown;
    _raw:             unknown;
  }
  const flags: NormFlag[] = rawFlags.map((f) => {
    const obj = (f != null && typeof f === "object" ? f : {}) as Record<string, unknown>;
    return {
      type:             safeStr(obj.type  ?? obj.flag_type ?? obj.category ?? "flag"),
      dish:             obj.dish          ?? obj.item       ?? null,
      phrase:           obj.phrase        ?? obj.text       ?? obj.quote    ?? null,
      reason:           obj.reason        ?? obj.note       ?? obj.message  ?? obj.description ?? null,
      suggested_action: obj.suggested_action ?? obj.action ?? null,
      _raw:             f,
    };
  });

  // Group by type
  const flagsByType = flags.reduce<Record<string, NormFlag[]>>((acc, f) => {
    (acc[f.type] ||= []).push(f);
    return acc;
  }, {});

  // ── Command visibility — mirrors the RPC preconditions exactly ─────────────
  // (operations.claim_intake_packet / release_intake_packet — migration 018;
  //  operations.approve_intake_packet / return_intake_packet — migration 017;
  //  operations.edit_intake_packet_payload / resubmit_intake_packet /
  //  reject_intake_packet / archive_intake_packet — migration 019.)
  //
  // NOTE on DEC000001 rule text vs. the RPC: the instruction that a
  // `returned` packet should also present Claim as an entry point into
  // review does not match operations.claim_intake_packet, which only
  // accepts packets in pending_review. A returned packet's actual re-entry
  // path is Edit Payload (optional) → Resubmit → pending_review → Claim.
  // We follow the RPC (the authoritative atomic mutation) rather than
  // invent a Claim call that would always fail with a 409 from the backend.
  // See the final report for this flagged as an explicit deviation.
  const isClaimed      = !!packet.claimed_by_user_id;
  const canClaim        = packet.packet_status === "pending_review" && !isClaimed;
  const canRelease       = packet.packet_status === "in_review" && isClaimed;
  const canApprove       = packet.packet_status === "in_review" && isClaimed;
  const canReturn         = packet.packet_status === "in_review" && isClaimed;
  const canReject         = packet.packet_status === "in_review" && isClaimed;
  const canEditPayload    = packet.packet_status === "returned";
  const canResubmit       = packet.packet_status === "returned";
  const canArchive        = packet.packet_status === "rejected" || packet.packet_status === "ingested";
  const canIngest         = packet.packet_status === "approved";
  const isIngested        = packet.packet_status === "ingested";
  const hasAnyAction =
    canClaim || canRelease || canApprove || canReturn || canReject ||
    canEditPayload || canResubmit || canArchive || canIngest;

  // ── Server Actions ──────────────────────────────────────────────────────────
  // Every mutation is try/caught; on failure we redirect back to this page
  // with an ?error= banner instead of throwing (which would render Next's
  // generic error page) or swallowing the failure silently.

  function errorRedirect(action: string, err: unknown): never {
    const message = err instanceof APIError ? err.detail : "Unexpected error.";
    redirect(
      `/admin/intake/${params.id}?action=${encodeURIComponent(action)}&error=${encodeURIComponent(message)}`,
    );
  }

  async function handleClaim(_formData: FormData) {
    "use server";
    try {
      await performIntakeAction(params.id, "claim");
    } catch (err) {
      errorRedirect("claim", err);
    }
    redirect(`/admin/intake/${params.id}`);
  }

  async function handleRelease(formData: FormData) {
    "use server";
    const reason = ((formData.get("reason") as string | null) ?? "").trim() || undefined;
    try {
      await performIntakeAction(params.id, "release", { reason });
    } catch (err) {
      errorRedirect("release", err);
    }
    redirect(`/admin/intake/${params.id}`);
  }

  async function handleApprove(formData: FormData) {
    "use server";
    const notes = (formData.get("reviewer_notes") as string | null)?.trim() || undefined;
    const overrideReason = (formData.get("override_reason") as string | null)?.trim() || undefined;
    try {
      await performIntakeAction(params.id, "approve", {
        reviewer_notes: notes,
        override_reason: overrideReason,
      });
    } catch (err) {
      errorRedirect("approve", err);
    }
    redirect(`/admin/intake/${params.id}`);
  }

  async function handleReturn(formData: FormData) {
    "use server";
    const reason = ((formData.get("reason") as string | null) ?? "").trim();
    const notes  = (formData.get("reviewer_notes") as string | null)?.trim() || undefined;
    if (!reason) {
      redirect(
        `/admin/intake/${params.id}?action=return&error=${encodeURIComponent("Return reason is required.")}`,
      );
    }
    try {
      await performIntakeAction(params.id, "return", { reason, reviewer_notes: notes });
    } catch (err) {
      errorRedirect("return", err);
    }
    redirect(`/admin/intake/${params.id}`);
  }

  async function handleReject(formData: FormData) {
    "use server";
    const reason = ((formData.get("reason") as string | null) ?? "").trim();
    if (!reason) {
      redirect(
        `/admin/intake/${params.id}?action=reject&error=${encodeURIComponent("Reject reason is required.")}`,
      );
    }
    try {
      await performIntakeAction(params.id, "reject", { reason });
    } catch (err) {
      errorRedirect("reject", err);
    }
    redirect(`/admin/intake/${params.id}`);
  }

  async function handleEditPayload(formData: FormData) {
    "use server";
    const reason = ((formData.get("reason") as string | null) ?? "").trim();
    const rawJson = ((formData.get("packet_data") as string | null) ?? "").trim();
    if (!reason) {
      redirect(
        `/admin/intake/${params.id}?action=edit_payload&error=${encodeURIComponent("Edit reason is required.")}`,
      );
    }
    let packetData: Record<string, unknown>;
    try {
      packetData = JSON.parse(rawJson);
    } catch {
      redirect(
        `/admin/intake/${params.id}?action=edit_payload&error=${encodeURIComponent(
          "packet_data is not valid JSON — edit not sent.",
        )}`,
      );
    }
    try {
      await performIntakeAction(params.id, "edit_payload", { packet_data: packetData, reason });
    } catch (err) {
      errorRedirect("edit_payload", err);
    }
    redirect(`/admin/intake/${params.id}`);
  }

  async function handleResubmit(formData: FormData) {
    "use server";
    const reason = (formData.get("reason") as string | null)?.trim() || undefined;
    try {
      await performIntakeAction(params.id, "resubmit", { reason });
    } catch (err) {
      errorRedirect("resubmit", err);
    }
    redirect(`/admin/intake/${params.id}`);
  }

  async function handleArchive(formData: FormData) {
    "use server";
    const reason = ((formData.get("reason") as string | null) ?? "").trim();
    if (!reason) {
      redirect(
        `/admin/intake/${params.id}?action=archive&error=${encodeURIComponent("Archive reason is required.")}`,
      );
    }
    try {
      await performIntakeAction(params.id, "archive", { reason });
    } catch (err) {
      errorRedirect("archive", err);
    }
    redirect(`/admin/intake/${params.id}`);
  }

  async function handleIngest(_formData: FormData) {
    "use server";
    try {
      await performIntakeAction(params.id, "ingest");
    } catch (err) {
      errorRedirect("ingest", err);
    }
    redirect(`/admin/intake/${params.id}`);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="max-w-4xl">

      {/* ── Breadcrumb + Header ── */}
      <div className="mb-5">
        <Link
          href="/admin/intake"
          className="text-xs text-stone-600 hover:text-stone-400 transition-colors"
        >
          ← Packet Queue
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-600 mb-0.5">
              Intake OS · Packet Review
            </p>
            <h1 className="text-2xl font-bold text-stone-100 leading-tight">
              {packet.restaurant_name}
            </h1>
            <div className="mt-1.5 flex items-center gap-2 flex-wrap">
              <span className="font-mono text-xs text-stone-500">
                {packet.restaurant_external_id}
              </span>
              <span
                className={`rounded px-1.5 py-0.5 text-xs font-medium capitalize ${statusBadge(packet.packet_status)}`}
              >
                {statusLabel(packet.packet_status)}
              </span>
              {isClaimed && (
                <span className="rounded px-1.5 py-0.5 text-xs font-medium bg-stone-800 text-stone-400">
                  Claimed
                </span>
              )}
              {packet.restaurant_id && (
                <Link
                  href={`/admin/restaurants/${packet.restaurant_external_id}`}
                  className="text-xs text-amber-500 hover:text-amber-400 transition-colors"
                >
                  View restaurant →
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Error banner ── */}
      {searchParams?.error && (
        <div className="mb-5 rounded-lg border border-red-800/60 bg-red-950/40 p-4">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-red-500 mb-1">
            {searchParams.action ? `${statusLabel(searchParams.action)} failed` : "Action failed"}
          </p>
          <p className="text-sm text-red-300">{searchParams.error}</p>
        </div>
      )}

      {/* ── Return reason banner ── */}
      {packet.return_reason && (
        <div className="mb-5 rounded-lg border border-red-800/50 bg-red-950/30 p-4">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-red-500 mb-1">
            Previously Returned
          </p>
          <p className="text-sm text-red-300">{packet.return_reason}</p>
          {packet.reviewer_notes && (
            <p className="mt-1 text-xs text-stone-500">{packet.reviewer_notes}</p>
          )}
        </div>
      )}

      {/* ── Ingested banner ── */}
      {isIngested && (
        <div className="mb-5 rounded-lg border border-emerald-800/40 bg-emerald-950/20 p-4">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-emerald-500 mb-1">
            Ingested
          </p>
          <p className="text-sm text-stone-400">
            Data committed to the database on {fmtDateTime(packet.ingested_at)}.
          </p>
          {packet.reviewer_notes && (
            <p className="mt-1 text-xs text-stone-500">{packet.reviewer_notes}</p>
          )}
        </div>
      )}

      {/* ── Action panel ── */}
      {hasAnyAction && (
        <div className="mb-6 rounded-lg border border-stone-700 bg-stone-900/50 p-4">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-500 mb-3">
            Review Actions
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

            {/* Claim */}
            {canClaim && (
              <form action={handleClaim} className="flex flex-col gap-2">
                <p className="text-xs text-stone-500">
                  Claim this packet to begin review. Only the claimant (or an
                  Administrator override) may approve, return, or reject it.
                </p>
                <button
                  type="submit"
                  className="self-start rounded-lg bg-sky-800 hover:bg-sky-700 px-4 py-1.5 text-xs font-medium text-white transition-colors"
                >
                  Claim for Review
                </button>
              </form>
            )}

            {/* Release */}
            {canRelease && (
              <form action={handleRelease} className="flex flex-col gap-2">
                <label className="text-[10px] font-medium uppercase tracking-widest text-stone-500">
                  Override Reason (required only if releasing someone else's claim)
                </label>
                <textarea
                  name="reason"
                  placeholder="Reason (leave blank for self-release)…"
                  rows={2}
                  className="w-full rounded border border-stone-700 bg-stone-800 px-3 py-2 text-xs text-stone-200 placeholder-stone-600 focus:outline-none focus:border-stone-500 resize-none"
                />
                <button
                  type="submit"
                  className="self-start rounded-lg bg-stone-700 hover:bg-stone-600 px-4 py-1.5 text-xs font-medium text-stone-100 transition-colors"
                >
                  Release Claim
                </button>
              </form>
            )}

            {/* Approve */}
            {canApprove && (
              <form action={handleApprove} className="flex flex-col gap-2">
                <label className="text-[10px] font-medium uppercase tracking-widest text-stone-500">
                  Reviewer Notes (optional)
                </label>
                <textarea
                  name="reviewer_notes"
                  placeholder="Any notes for the record…"
                  rows={3}
                  defaultValue={packet.reviewer_notes ?? ""}
                  className="w-full rounded border border-stone-700 bg-stone-800 px-3 py-2 text-xs text-stone-200 placeholder-stone-600 focus:outline-none focus:border-blue-700/60 resize-none"
                />
                <label className="text-[10px] font-medium uppercase tracking-widest text-stone-500">
                  Override Reason (required only if approving someone else's claim)
                </label>
                <textarea
                  name="override_reason"
                  placeholder="Required only for an Administrator override…"
                  rows={2}
                  className="w-full rounded border border-stone-700 bg-stone-800 px-3 py-2 text-xs text-stone-200 placeholder-stone-600 focus:outline-none focus:border-blue-700/60 resize-none"
                />
                <button
                  type="submit"
                  className="self-start rounded-lg bg-blue-700 hover:bg-blue-600 px-4 py-1.5 text-xs font-medium text-white transition-colors"
                >
                  Approve
                </button>
              </form>
            )}

            {/* Return to canvasser */}
            {canReturn && (
              <form action={handleReturn} className="flex flex-col gap-2">
                <label className="text-[10px] font-medium uppercase tracking-widest text-stone-500">
                  Return Reason <span className="text-red-500">*</span>
                </label>
                <textarea
                  name="reason"
                  placeholder="Describe what needs to be fixed…"
                  rows={3}
                  required
                  className="w-full rounded border border-stone-700 bg-stone-800 px-3 py-2 text-xs text-stone-200 placeholder-stone-600 focus:outline-none focus:border-red-700/60 resize-none"
                />
                <label className="text-[10px] font-medium uppercase tracking-widest text-stone-500">
                  Reviewer Notes (optional)
                </label>
                <textarea
                  name="reviewer_notes"
                  placeholder="Any additional notes…"
                  rows={2}
                  className="w-full rounded border border-stone-700 bg-stone-800 px-3 py-2 text-xs text-stone-200 placeholder-stone-600 focus:outline-none focus:border-red-700/60 resize-none"
                />
                <button
                  type="submit"
                  className="self-start rounded-lg bg-red-900 hover:bg-red-800 px-4 py-1.5 text-xs font-medium text-red-100 transition-colors"
                >
                  Return to Canvasser
                </button>
              </form>
            )}

            {/* Reject */}
            {canReject && (
              <form action={handleReject} className="flex flex-col gap-2">
                <label className="text-[10px] font-medium uppercase tracking-widest text-stone-500">
                  Reject Reason <span className="text-red-500">*</span>
                </label>
                <textarea
                  name="reason"
                  placeholder="Why is this packet being rejected outright?"
                  rows={3}
                  required
                  className="w-full rounded border border-stone-700 bg-stone-800 px-3 py-2 text-xs text-stone-200 placeholder-stone-600 focus:outline-none focus:border-rose-700/60 resize-none"
                />
                <button
                  type="submit"
                  className="self-start rounded-lg bg-rose-950 hover:bg-rose-900 px-4 py-1.5 text-xs font-medium text-rose-200 transition-colors"
                >
                  Reject Packet
                </button>
              </form>
            )}

            {/* Edit payload (Intake Specialist, returned packets only) */}
            {canEditPayload && (
              <form action={handleEditPayload} className="sm:col-span-2 flex flex-col gap-2 border-t border-stone-800 pt-4">
                <label className="text-[10px] font-medium uppercase tracking-widest text-stone-500">
                  Edit Payload (packet_data JSON) — Intake Specialist only
                </label>
                <textarea
                  name="packet_data"
                  defaultValue={JSON.stringify(pd, null, 2)}
                  rows={8}
                  className="w-full rounded border border-stone-700 bg-stone-800 px-3 py-2 font-mono text-[11px] text-stone-200 focus:outline-none focus:border-amber-700/60"
                />
                <label className="text-[10px] font-medium uppercase tracking-widest text-stone-500">
                  Edit Reason <span className="text-red-500">*</span>
                </label>
                <textarea
                  name="reason"
                  placeholder="What was changed and why…"
                  rows={2}
                  required
                  className="w-full rounded border border-stone-700 bg-stone-800 px-3 py-2 text-xs text-stone-200 placeholder-stone-600 focus:outline-none focus:border-amber-700/60 resize-none"
                />
                <button
                  type="submit"
                  className="self-start rounded-lg bg-amber-800 hover:bg-amber-700 px-4 py-1.5 text-xs font-medium text-amber-50 transition-colors"
                >
                  Save Payload Edit
                </button>
              </form>
            )}

            {/* Resubmit (Intake Specialist, returned packets only) */}
            {canResubmit && (
              <form action={handleResubmit} className="flex flex-col gap-2">
                <label className="text-[10px] font-medium uppercase tracking-widest text-stone-500">
                  Resubmit Reason (optional)
                </label>
                <textarea
                  name="reason"
                  placeholder="Optional note on the resubmission…"
                  rows={2}
                  className="w-full rounded border border-stone-700 bg-stone-800 px-3 py-2 text-xs text-stone-200 placeholder-stone-600 focus:outline-none focus:border-emerald-700/60 resize-none"
                />
                <button
                  type="submit"
                  className="self-start rounded-lg bg-emerald-800 hover:bg-emerald-700 px-4 py-1.5 text-xs font-medium text-emerald-50 transition-colors"
                >
                  Resubmit for Review
                </button>
              </form>
            )}

            {/* Archive */}
            {canArchive && (
              <form action={handleArchive} className="flex flex-col gap-2">
                <label className="text-[10px] font-medium uppercase tracking-widest text-stone-500">
                  Archive Reason <span className="text-red-500">*</span>
                </label>
                <textarea
                  name="reason"
                  placeholder="Why is this packet being archived?"
                  rows={2}
                  required
                  className="w-full rounded border border-stone-700 bg-stone-800 px-3 py-2 text-xs text-stone-200 placeholder-stone-600 focus:outline-none focus:border-stone-500 resize-none"
                />
                <button
                  type="submit"
                  className="self-start rounded-lg bg-stone-700 hover:bg-stone-600 px-4 py-1.5 text-xs font-medium text-stone-100 transition-colors"
                >
                  Archive Packet
                </button>
              </form>
            )}

            {/* Mark ingested */}
            {canIngest && (
              <div className="sm:col-span-2 border-t border-stone-800 pt-4">
                <p className="text-xs text-stone-500 mb-2">
                  Once you've run{" "}
                  <span className="font-mono text-stone-400">
                    python3 ingest_packet.py &lt;file&gt; --commit
                  </span>{" "}
                  successfully:
                </p>
                <form action={handleIngest}>
                  <button
                    type="submit"
                    className="rounded-lg bg-emerald-900 hover:bg-emerald-800 px-4 py-1.5 text-xs font-medium text-emerald-100 transition-colors"
                  >
                    Mark as Ingested
                  </button>
                </form>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Review Flags ── */}
      {flags.length > 0 && (
        <section className="mb-6">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-stone-400 mb-3">
            Review Flags
            <span className="ml-2 rounded-full bg-amber-900/40 text-amber-400 px-2 py-0.5 text-[10px] font-bold">
              {flags.length}
            </span>
          </h2>
          <div className="flex flex-col gap-3">
            {Object.entries(flagsByType).map(([type, typeFlags]) => (
              <div
                key={type}
                className={`rounded-lg border overflow-hidden ${flagSeverityColor(type)}`}
              >
                <div className="px-4 py-2 border-b border-stone-800 flex items-center gap-2">
                  <span className="text-xs font-semibold text-stone-300 capitalize">
                    {flagTypeLabel(type)}
                  </span>
                  <span className="text-[10px] text-stone-600">({typeFlags.length})</span>
                </div>
                <div className="divide-y divide-stone-800/60">
                  {typeFlags.map((f, i) => {
                    const dishStr   = safeStr(f.dish);
                    const phraseStr = safeStr(f.phrase);
                    const actionStr = safeStr(f.suggested_action);
                    return (
                      <div key={i} className="px-4 py-3">
                        <div className="flex items-start justify-between gap-3 flex-wrap mb-1">
                          {dishStr && (
                            <span className="text-xs font-medium text-stone-200">{dishStr}</span>
                          )}
                          {actionStr && (
                            <span className="text-[10px] font-medium uppercase tracking-wider text-amber-400 bg-amber-950/50 px-1.5 py-0.5 rounded whitespace-nowrap">
                              {actionStr}
                            </span>
                          )}
                        </div>
                        {phraseStr && (
                          <p className="text-xs text-stone-500 italic mb-1">"{phraseStr}"</p>
                        )}
                        <div className="text-xs text-stone-500">
                          {renderValue(f.reason)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Advisory Notes ── */}
      {advisory.length > 0 && (
        <section className="mb-6">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-stone-400 mb-3">
            Advisory Notes
          </h2>
          <div className="rounded-lg border border-stone-700 bg-stone-900/30 divide-y divide-stone-800">
            {advisory.map((note, i) => (
              <div key={i} className="px-4 py-2.5 text-xs text-stone-400 leading-relaxed">
                {renderValue(note)}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Evidence Score ── */}
      <section className="mb-6">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-stone-400 mb-3">
          Evidence Score
        </h2>
        <div className="rounded-lg border border-stone-700 bg-stone-900/40 p-4">
          <div className="flex items-end gap-2 mb-4">
            <span
              className={`text-5xl font-bold tabular-nums leading-none ${scoreColor(packet.evidence_score_overall)}`}
            >
              {packet.evidence_score_overall ?? "—"}
            </span>
            <span className="text-stone-600 text-xl mb-1">/100</span>
          </div>
          {packet.evidence_score_detail && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {Object.entries(packet.evidence_score_detail)
                .filter(([k]) => k !== "overall")
                .sort(([, a], [, b]) => (b as number) - (a as number))
                .map(([key, val]) => {
                  const n = val as number;
                  return (
                    <div key={key} className="flex items-center gap-3">
                      <div className="flex-1 h-1 bg-stone-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            n >= 80 ? "bg-emerald-500" : n >= 60 ? "bg-amber-500" : "bg-red-500"
                          }`}
                          style={{ width: `${Math.min(100, n)}%` }}
                        />
                      </div>
                      <span className={`text-xs font-medium tabular-nums w-7 text-right ${scoreColor(n)}`}>
                        {n}
                      </span>
                      <span className="text-xs text-stone-500 capitalize w-40 truncate">
                        {key.replace(/_/g, " ")}
                      </span>
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      </section>

      {/* ── Dishes ── */}
      {dishes.length > 0 && (
        <section className="mb-6">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-stone-400 mb-3">
            Dishes
            <span className="ml-2 text-stone-600 font-normal normal-case tracking-normal">
              {dishes.length}
            </span>
          </h2>
          <div className="overflow-x-auto rounded-lg border border-stone-700">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-stone-700 bg-stone-900">
                  <th className="px-3 py-2 text-left text-[10px] font-medium uppercase tracking-widest text-stone-500">
                    Dish
                  </th>
                  <th className="px-3 py-2 text-left text-[10px] font-medium uppercase tracking-widest text-stone-500">
                    Section
                  </th>
                  <th className="px-3 py-2 text-right text-[10px] font-medium uppercase tracking-widest text-stone-500">
                    Ingredients
                  </th>
                  <th className="px-3 py-2 text-right text-[10px] font-medium uppercase tracking-widest text-stone-500">
                    Calories
                  </th>
                </tr>
              </thead>
              <tbody>
                {dishes.map((d, i) => {
                  const name    = (d.dish_name ?? d.name ?? "—") as string;
                  const section = (d.menu_section ?? d.section ?? "") as string;
                  const ingCount = Array.isArray(d.ingredients)
                    ? (d.ingredients as unknown[]).length
                    : typeof d.ingredient_count === "number"
                    ? d.ingredient_count
                    : null;
                  const calorie = (d.calorie_value ?? d.calories ?? null) as string | number | null;

                  return (
                    <tr
                      key={i}
                      className="border-b border-stone-800 last:border-0 hover:bg-stone-800/30"
                    >
                      <td className="px-3 py-2 text-stone-200 font-medium">{name}</td>
                      <td className="px-3 py-2 text-stone-500">{section || "—"}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-stone-400">
                        {ingCount != null ? ingCount : "—"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-stone-400">
                        {calorie != null ? calorie : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* ── Metadata ── */}
      <section className="mb-6">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-stone-400 mb-3">
          Metadata
        </h2>
        <div className="rounded-lg border border-stone-700 bg-stone-900/40 p-4">
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2.5 text-xs">
            <div className="flex items-center justify-between gap-4">
              <dt className="text-stone-500 shrink-0">Canvass date</dt>
              <dd className="text-stone-300 font-medium">{fmtDate(packet.canvass_date)}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-stone-500 shrink-0">Submitted</dt>
              <dd className="text-stone-400">{fmtDateTime(packet.submitted_at)}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-stone-500 shrink-0">Reviewed</dt>
              <dd className="text-stone-400">{fmtDateTime(packet.reviewed_at)}</dd>
            </div>
            {packet.reviewed_by && (
              <div className="flex items-center justify-between gap-4">
                <dt className="text-stone-500 shrink-0">Reviewed by</dt>
                <dd className="text-stone-300">{packet.reviewed_by}</dd>
              </div>
            )}
            {isClaimed && (
              <div className="flex items-center justify-between gap-4">
                <dt className="text-stone-500 shrink-0">Claimed by</dt>
                <dd className="text-stone-300 font-mono text-[11px]">
                  {packet.claimed_by_user_id}
                  {packet.claimed_at && (
                    <span className="text-stone-600 font-sans"> · {fmtDateTime(packet.claimed_at)}</span>
                  )}
                </dd>
              </div>
            )}
            {packet.ingested_at && (
              <div className="flex items-center justify-between gap-4">
                <dt className="text-stone-500 shrink-0">Ingested</dt>
                <dd className="text-stone-400">{fmtDateTime(packet.ingested_at)}</dd>
              </div>
            )}
            <div className="flex items-center justify-between gap-4">
              <dt className="text-stone-500 shrink-0">Model</dt>
              <dd className="font-mono text-stone-500">{packet.model_used ?? "—"}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-stone-500 shrink-0">Agent version</dt>
              <dd className="font-mono text-stone-500">{packet.agent_version ?? "—"}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-stone-500 shrink-0">Processing time</dt>
              <dd className="text-stone-400">
                {packet.processing_time_ms != null
                  ? `${(packet.processing_time_ms / 1000).toFixed(1)}s`
                  : "—"}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4 sm:col-span-2">
              <dt className="text-stone-500 shrink-0">Packet ID</dt>
              <dd className="font-mono text-stone-600 text-[10px] break-all">{packet.packet_id}</dd>
            </div>
          </dl>

          {packet.source_urls.length > 0 && (
            <div className="mt-4 pt-4 border-t border-stone-800">
              <p className="text-[10px] font-medium uppercase tracking-widest text-stone-600 mb-2">
                Source URLs ({packet.source_urls.length})
              </p>
              <ul className="flex flex-col gap-1.5">
                {packet.source_urls.map((url, i) => (
                  <li key={i} className="font-mono text-[11px] text-stone-500 break-all leading-relaxed">
                    {url}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </section>

    </div>
  );
}
