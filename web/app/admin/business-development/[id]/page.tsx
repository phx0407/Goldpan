// app/admin/business-development/[id]/page.tsx
// Server component — partner master page.

import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchPartnerDetail, APIError } from "@/lib/api";
import type { PartnerRow, ActionRow, PartnerIntel } from "@/lib/types";
import { ActionPanel } from "./ActionPanel";

export const dynamic = "force-dynamic";

// ── Helpers ───────────────────────────────────────────────────────────────────

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

const ACTION_TYPE_LABELS: Record<string, string> = {
  note:             "Note",
  email_sent:       "Email sent",
  email_received:   "Email received",
  call:             "Call",
  meeting:          "Meeting",
  follow_up_set:    "Follow-up set",
  status_change:    "Status changed",
  contacted:        "Contacted",
  dm_instagram:     "Instagram DM",
  other:            "Other",
};

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

function priorityDot(p: string) {
  switch (p) {
    case "high":   return "bg-red-400";
    case "medium": return "bg-amber-400";
    default:       return "bg-stone-500";
  }
}

function coverageColor(pct: number) {
  if (pct >= 80) return "text-emerald-400";
  if (pct >= 40) return "text-amber-400";
  return "text-red-400";
}

function recanvassColor(s: string) {
  switch (s) {
    case "current":      return "text-emerald-400";
    case "due_soon":     return "text-amber-400";
    case "overdue":      return "text-red-400";
    default:             return "text-stone-500";
  }
}

function lifecycleColor(s: string) {
  switch (s) {
    case "published":            return "bg-emerald-900/50 text-emerald-300";
    case "qa_review":
    case "verification":
    case "recanvassing":         return "bg-amber-900/50 text-amber-300";
    case "evidence_acquisition":
    case "onboarding":
    case "qualified":            return "bg-blue-900/50 text-blue-300";
    case "prospect":             return "bg-stone-700 text-stone-400";
    case "suspended":            return "bg-red-900/50 text-red-300";
    default:                     return "bg-stone-700 text-stone-400";
  }
}

function actionTypeColor(t: string) {
  switch (t) {
    case "status_change":  return "bg-violet-900/40 text-violet-300";
    case "call":
    case "meeting":        return "bg-blue-900/40 text-blue-300";
    case "email_sent":
    case "email_received": return "bg-sky-900/40 text-sky-300";
    case "follow_up_set":  return "bg-amber-900/40 text-amber-300";
    case "dm_instagram":   return "bg-pink-900/40 text-pink-300";
    default:               return "bg-stone-700/60 text-stone-400";
  }
}

function pct(n: number) { return `${n.toFixed(0)}%`; }
function fmtDate(d: string | null) { return d ? d.slice(0, 10) : "—"; }

function fmtDatetime(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric",
    });
  } catch {
    return iso.slice(0, 10);
  }
}

// ── Sub-components ────────────────────────────────────────────────────────────

function InfoRow({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs text-stone-500 mb-0.5">{label}</p>
      <p className={`text-sm text-stone-200 ${mono ? "font-mono" : ""}`}>{value ?? "—"}</p>
    </div>
  );
}

function Badge({ label, className }: { label: string; className: string }) {
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${className}`}>
      {label}
    </span>
  );
}

function IntelPanel({ intel, restaurantId }: { intel: PartnerIntel; restaurantId: string | null }) {
  return (
    <div className="rounded-lg border border-amber-800/40 bg-amber-950/20 p-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-medium uppercase tracking-widest text-amber-500">
          Restaurant Intelligence
        </p>
        {restaurantId && (
          <Badge label={intel.lifecycle_status.replace(/_/g, " ")} className={lifecycleColor(intel.lifecycle_status)} />
        )}
      </div>
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
        <div>
          <p className="text-xs text-stone-500">Dishes</p>
          <p className="text-lg font-semibold tabular-nums text-stone-100">{intel.dish_count}</p>
        </div>
        <div>
          <p className="text-xs text-stone-500">Ingredients</p>
          <p className="text-lg font-semibold tabular-nums text-stone-100">{intel.ingredient_count}</p>
        </div>
        <div>
          <p className="text-xs text-stone-500">Trans %</p>
          <p className={`text-lg font-semibold tabular-nums ${coverageColor(intel.transparency_coverage_pct)}`}>
            {pct(intel.transparency_coverage_pct)}
          </p>
        </div>
        <div>
          <p className="text-xs text-stone-500">Cal %</p>
          <p className={`text-lg font-semibold tabular-nums ${coverageColor(intel.calorie_coverage_pct)}`}>
            {pct(intel.calorie_coverage_pct)}
          </p>
        </div>
        <div>
          <p className="text-xs text-stone-500">Claims</p>
          <p className="text-lg font-semibold tabular-nums text-stone-100">{intel.claims_count}</p>
        </div>
        <div>
          <p className="text-xs text-stone-500">Unknown</p>
          <p className={`text-lg font-semibold tabular-nums ${intel.unknown_filter_count > 0 ? "text-amber-400" : "text-stone-600"}`}>
            {intel.unknown_filter_count || "—"}
          </p>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-4 text-xs">
        <span className={`font-medium ${recanvassColor(intel.recanvass_status)}`}>
          {intel.recanvass_status.replace(/_/g, " ")}
        </span>
        {intel.last_canvassed && (
          <span className="text-stone-600">Last canvassed: {fmtDate(intel.last_canvassed)}</span>
        )}
        {intel.avg_transparency_score !== null && (
          <span className="text-stone-500">
            Avg score: <span className="text-stone-300">{intel.avg_transparency_score}</span>
          </span>
        )}
      </div>
    </div>
  );
}

function ActionHistory({ actions }: { actions: ActionRow[] }) {
  if (actions.length === 0) {
    return (
      <p className="text-xs text-stone-600 py-3">No actions logged yet.</p>
    );
  }
  return (
    <div className="space-y-2">
      {actions.map(a => (
        <div key={a.action_id} className="flex gap-3 py-2 border-b border-stone-800 last:border-0">
          <div className="mt-0.5 shrink-0">
            <Badge
              label={ACTION_TYPE_LABELS[a.action_type] ?? a.action_type}
              className={actionTypeColor(a.action_type)}
            />
          </div>
          <div className="flex-1 min-w-0">
            {a.content && (
              <p className="text-sm text-stone-300 break-words">{a.content}</p>
            )}
            {a.action_type === "status_change" && a.old_status && a.new_status && (
              <p className="text-xs text-stone-500 mt-0.5">
                <span className="line-through">{a.old_status}</span>
                {" → "}
                <span className="text-stone-300">{a.new_status}</span>
              </p>
            )}
          </div>
          <div className="shrink-0 text-right">
            <p className="text-xs text-stone-600">{fmtDatetime(a.performed_at)}</p>
            {a.performed_by && (
              <p className="text-xs text-stone-600 mt-0.5">{a.performed_by}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function PartnerDetailPage({
  params,
}: {
  params: { id: string };
}) {
  let data: Awaited<ReturnType<typeof fetchPartnerDetail>> | null = null;
  let fetchError: string | null = null;

  try {
    data = await fetchPartnerDetail(params.id);
  } catch (err) {
    if (err instanceof APIError && err.status === 404) notFound();
    fetchError =
      err instanceof APIError
        ? `${err.status} — ${err.detail}`
        : err instanceof Error ? err.message : "Unknown error.";
  }

  if (fetchError) {
    return (
      <div className="flex flex-col gap-3 max-w-4xl">
        <Link href="/admin/business-development" className="text-xs text-stone-500 hover:text-stone-300">
          ← Business Development
        </Link>
        <div className="rounded-lg border border-red-800 bg-red-950/40 p-5">
          <p className="text-sm font-medium text-red-400">Could not load partner</p>
          <p className="mt-1 font-mono text-xs text-red-500">{fetchError}</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { partner: p, actions } = data;
  const isRestaurant = p.partner_type === "restaurant";

  return (
    <div className="max-w-4xl space-y-6">
      {/* Breadcrumb */}
      <Link
        href="/admin/business-development"
        className="text-xs text-stone-500 hover:text-stone-300 transition-colors"
      >
        ← Business Development
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs text-stone-600">{p.external_id}</span>
            <span className="text-stone-700">·</span>
            <span className="text-xs text-stone-500">
              {PARTNER_TYPE_LABELS[p.partner_type] ?? p.partner_type}
            </span>
          </div>
          <h1 className="text-xl font-semibold text-stone-100">{p.name}</h1>
          {p.contact_name && (
            <p className="text-sm text-stone-400 mt-0.5">
              {p.contact_name}{p.contact_title ? ` · ${p.contact_title}` : ""}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div className={`w-2 h-2 rounded-full ${priorityDot(p.priority)}`} title={`${p.priority} priority`} />
          <Badge label={p.status} className={statusColor(p.status)} />
          {p.opportunity_score !== null && (
            <span className="text-xs text-stone-500">
              Score: <span className="text-stone-200 font-medium">{p.opportunity_score}/10</span>
            </span>
          )}
          <Link
            href={`/admin/business-development/${p.external_id}/edit`}
            className="ml-1 rounded border border-stone-700 bg-stone-800 hover:bg-stone-700 px-2.5 py-1 text-xs text-stone-300 transition-colors"
          >
            Edit
          </Link>
        </div>
      </div>

      {/* Restaurant intel */}
      {isRestaurant && p.intel && (
        <IntelPanel intel={p.intel} restaurantId={p.restaurant_id} />
      )}

      {/* Restaurant intel missing warning */}
      {isRestaurant && !p.intel && (
        <div className="rounded-lg border border-stone-700 bg-stone-900 p-4">
          <p className="text-sm text-stone-500">
            No restaurant intelligence available.
            {!p.restaurant_id
              ? " Link this partner to an evidence.restaurants record to enable intel enrichment."
              : " Restaurant data may not yet be ingested."}
          </p>
        </div>
      )}

      {/* Two-column: info + pipeline */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Contact info */}
        <div className="rounded-lg border border-stone-700 bg-stone-900 p-4 space-y-3">
          <p className="text-xs font-medium uppercase tracking-widest text-stone-500">Contact</p>
          <InfoRow label="Email"     value={p.email     ? <a href={`mailto:${p.email}`} className="text-amber-400 hover:underline">{p.email}</a>     : null} />
          <InfoRow label="Phone"     value={p.phone} />
          <InfoRow label="Instagram" value={p.instagram  ? <a href={`https://instagram.com/${p.instagram.replace("@","")}`} target="_blank" rel="noreferrer" className="text-amber-400 hover:underline">@{p.instagram.replace("@","")}</a> : null} />
          <InfoRow label="Website"   value={p.website   ? <a href={p.website} target="_blank" rel="noreferrer" className="text-amber-400 hover:underline">{p.website}</a>   : null} />
          {(p.city || p.state) && (
            <InfoRow label="Location" value={[p.city, p.state].filter(Boolean).join(", ")} />
          )}
        </div>

        {/* Pipeline */}
        <div className="rounded-lg border border-stone-700 bg-stone-900 p-4 space-y-3">
          <p className="text-xs font-medium uppercase tracking-widest text-stone-500">Pipeline</p>
          <InfoRow label="Status"         value={<Badge label={p.status} className={statusColor(p.status)} />} />
          <InfoRow label="Priority"       value={<span className={`text-sm font-medium capitalize ${p.priority === "high" ? "text-red-400" : p.priority === "medium" ? "text-amber-400" : "text-stone-400"}`}>{p.priority}</span>} />
          {p.pipeline_stage && <InfoRow label="Stage"    value={p.pipeline_stage} />}
          <InfoRow label="Owner"          value={p.relationship_owner} />
          <InfoRow label="Source"         value={p.source} />
          <InfoRow label="Deal value"     value={p.deal_value} />
          <InfoRow label="First contact"  value={fmtDate(p.first_contact_date)} />
          <InfoRow label="Last contact"   value={fmtDate(p.last_contact_date)} />
          <InfoRow
            label="Next follow-up"
            value={
              p.next_followup_date
                ? <span className={p.next_followup_date <= new Date().toISOString().slice(0,10) ? "text-amber-400" : "text-stone-200"}>
                    {fmtDate(p.next_followup_date)}
                  </span>
                : "—"
            }
          />
        </div>
      </div>

      {/* Non-restaurant BD fields */}
      {!isRestaurant && (p.strategic_value || p.audience_fit || p.partnership_model) && (
        <div className="rounded-lg border border-stone-700 bg-stone-900 p-4 space-y-3">
          <p className="text-xs font-medium uppercase tracking-widest text-stone-500">Strategic Info</p>
          {p.strategic_value    && <InfoRow label="Strategic value"    value={p.strategic_value} />}
          {p.audience_fit       && <InfoRow label="Audience fit"       value={p.audience_fit} />}
          {p.partnership_model  && <InfoRow label="Partnership model"  value={p.partnership_model} />}
        </div>
      )}

      {/* Notes + objections */}
      {(p.notes || p.objections) && (
        <div className="rounded-lg border border-stone-700 bg-stone-900 p-4 space-y-4">
          {p.notes && (
            <div>
              <p className="text-xs font-medium uppercase tracking-widest text-stone-500 mb-1">Notes</p>
              <p className="text-sm text-stone-300 whitespace-pre-wrap">{p.notes}</p>
            </div>
          )}
          {p.objections && (
            <div>
              <p className="text-xs font-medium uppercase tracking-widest text-stone-500 mb-1">Objections</p>
              <p className="text-sm text-stone-300 whitespace-pre-wrap">{p.objections}</p>
            </div>
          )}
        </div>
      )}

      {/* Action panel */}
      <ActionPanel externalId={p.external_id} currentStatus={p.status} />

      {/* Action history */}
      <div className="rounded-lg border border-stone-700 bg-stone-900 p-4">
        <p className="text-xs font-medium uppercase tracking-widest text-stone-500 mb-3">
          Action History ({actions.length})
        </p>
        <ActionHistory actions={actions} />
      </div>

      {/* Meta */}
      <p className="text-xs text-stone-700 pb-4">
        Created {fmtDate(p.created_at)} · Updated {fmtDate(p.updated_at)}
      </p>
    </div>
  );
}
