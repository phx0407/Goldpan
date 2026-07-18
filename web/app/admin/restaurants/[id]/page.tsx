// app/admin/restaurants/[id]/page.tsx
// Restaurant Master Page — canonical entity workspace.
// Reference pattern for all future GoldPan entity workspaces.
//
// Sections (in order):
//   1. Header (name, ID, lifecycle, actions)
//   2. Identity (enriched: address, phone, coords, google_place_id, website, menu)
//   3. Restaurant Health (diagnostic indicators + overall state)
//   4. Lifecycle Explainability (conditional — when not published)
//   5. Stats
//   6. Freshness / Recanvass
//   7. Business Development
//   8. Intake OS
//   9. Knowledge (transparency)
//  10. Governance (filter conclusions)
//  11. Analytics (placeholder)
//  12. Entity Timeline
//  13. Menu Sources
//  14. Dishes
//  15. Claims
//  16. Notes
//  17. Footer timestamps

import { redirect } from "next/navigation";
import Link from "next/link";
import { fetchRestaurantDetail, performLifecycleAction, APIError } from "@/lib/api";
import type {
  RestaurantInfo,
  RestaurantStats,
  MenuSourceRow,
  DishRow,
  ClaimRow,
  PartnerLinkRow,
  FilterSummaryRow,
} from "@/lib/types";

export const dynamic = "force-dynamic";

// ── Badge helpers ─────────────────────────────────────────────────────────────

function lifecycleBadge(s: string) {
  const map: Record<string, string> = {
    published:            "bg-emerald-900/50 text-emerald-300",
    qa_review:            "bg-amber-900/50 text-amber-300",
    verification:         "bg-amber-900/50 text-amber-300",
    evidence_acquisition: "bg-blue-900/50 text-blue-300",
    onboarding:           "bg-blue-900/50 text-blue-300",
    qualified:            "bg-blue-900/50 text-blue-300",
    recanvassing:         "bg-amber-900/50 text-amber-300",
    prospect:             "bg-stone-700 text-stone-400",
    suspended:            "bg-red-900/50 text-red-300",
  };
  return map[s] ?? "bg-stone-700 text-stone-400";
}

function recanvassBadge(s: string) {
  const map: Record<string, string> = {
    current:      "bg-emerald-900/50 text-emerald-300",
    due_soon:     "bg-amber-900/50 text-amber-300",
    overdue:      "bg-red-900/50 text-red-300",
    needs_review: "bg-stone-700 text-stone-500",
  };
  return map[s] ?? "bg-stone-700 text-stone-500";
}

function sourceCheckBadge(s: string) {
  const map: Record<string, string> = {
    ok:          "text-emerald-400",
    changed:     "text-amber-400",
    unreachable: "text-red-400",
    overdue:     "text-amber-400",
    unknown:     "text-stone-500",
  };
  return map[s] ?? "text-stone-500";
}

function pct(n: number) { return `${n.toFixed(0)}%`; }

// ── Location quality ───────────────────────────────────────────────────────────

type LocationQuality = "complete_address" | "city_state_only" | "missing_location";

function getLocationQuality(r: Pick<RestaurantInfo, "address" | "city" | "state">): LocationQuality {
  if (r.address) return "complete_address";
  if (r.city || r.state) return "city_state_only";
  return "missing_location";
}

// ── Health indicators ─────────────────────────────────────────────────────────

type IndicatorState = "green" | "amber" | "red" | "neutral";

interface HealthIndicator {
  label:   string;
  state:   IndicatorState;
  detail?: string;
}

function computeHealth(
  r: RestaurantInfo,
  stats: RestaurantStats,
): { state: "healthy" | "needs_attention" | "blocked"; indicators: HealthIndicator[] } {
  const lq = getLocationQuality(r);

  const indicators: HealthIndicator[] = [
    // Lifecycle
    {
      label:  "Lifecycle",
      state:  r.lifecycle_status === "published" ? "green"
            : r.lifecycle_status === "suspended"  ? "red"
            : "amber",
      detail: r.lifecycle_status.replace(/_/g, " "),
    },
    // Location
    {
      label:  "Location",
      state:  lq === "complete_address" ? "green"
            : lq === "city_state_only"  ? "amber"
            : "red",
      detail: lq === "complete_address" ? "Complete address" :
              lq === "city_state_only"  ? "City/state only — street address needed" :
              "No location data",
    },
    // Geocoordinates
    {
      label:  "Geocoords",
      state:  (r.latitude != null && r.longitude != null) ? "green" : "amber",
      detail: (r.latitude != null && r.longitude != null) ? "Lat/lng present" : "No coordinates — not visible on map",
    },
    // Freshness
    {
      label:  "Freshness",
      state:  r.recanvass_status === "current"      ? "green"
            : r.recanvass_status === "due_soon"     ? "amber"
            : r.recanvass_status === "overdue"      ? "red"
            : "neutral",
      detail: r.recanvass_status.replace(/_/g, " "),
    },
    // Source check
    {
      label:  "Source",
      state:  r.source_check_status === "ok"          ? "green"
            : r.source_check_status === "changed"     ? "amber"
            : r.source_check_status === "unreachable" ? "red"
            : r.source_check_status === "overdue"     ? "amber"
            : "neutral",
      detail: r.source_check_status,
    },
    // Transparency
    ...(stats.dish_count > 0 ? [{
      label:  "Transparency",
      state:  (stats.transparency_coverage_pct >= 75 ? "green"
             : stats.transparency_coverage_pct >= 40 ? "amber"
             : "red") as IndicatorState,
      detail: `${pct(stats.transparency_coverage_pct)} coverage`,
    }] : []),
    // Unknown filters
    ...(stats.unknown_filter_count > 0 ? [{
      label:  "Governance",
      state:  "amber" as IndicatorState,
      detail: `${stats.unknown_filter_count} dish${stats.unknown_filter_count !== 1 ? "es" : ""} with unknown conclusion`,
    }] : []),
  ];

  const hasRed   = indicators.some(i => i.state === "red");
  const hasAmber = indicators.some(i => i.state === "amber");

  return {
    state: hasRed ? "blocked" : hasAmber ? "needs_attention" : "healthy",
    indicators,
  };
}

// ── Lifecycle explainability ──────────────────────────────────────────────────

const LIFECYCLE_EXPLAIN: Record<string, { title: string; body: string; next?: string }> = {
  prospect: {
    title: "Prospect — not yet in the intake pipeline",
    body:  "This restaurant has been identified as a candidate but has not entered the intake process. Create a BD record to begin the qualification pipeline.",
    next:  "Create a BD record to advance to Qualified.",
  },
  qualified: {
    title: "Qualified — awaiting intake",
    body:  "Restaurant has been qualified for intake. An intake packet needs to be created and canvassing scheduled.",
    next:  "Schedule a canvassing run to advance to Onboarding.",
  },
  onboarding: {
    title: "Onboarding — intake in progress",
    body:  "Restaurant is actively being onboarded. Intake packet is open or in progress.",
    next:  "Complete the intake packet and submit for evidence acquisition.",
  },
  evidence_acquisition: {
    title: "Evidence Acquisition — gathering data",
    body:  "Evidence is being gathered from the restaurant's menu sources. Transparency data is not yet complete.",
    next:  "Run the governance pipeline once evidence is complete.",
  },
  verification: {
    title: "Verification — evidence under review",
    body:  "Evidence has been gathered and is being verified before publication.",
    next:  "Pass QA review to publish.",
  },
  qa_review: {
    title: "QA Review — final checks before publish",
    body:  "Restaurant is in QA review. Final data quality checks are being performed.",
    next:  "Approve QA review to publish.",
  },
  recanvassing: {
    title: "Recanvassing — data is being refreshed",
    body:  "This restaurant is in an active recanvass cycle. Data may be stale pending the new intake run.",
    next:  "Complete the recanvass packet and re-run governance.",
  },
  suspended: {
    title: "Suspended — not visible to users",
    body:  "This restaurant has been suspended. It is not shown on the public-facing GoldPan product.",
    next:  "Resolve the suspension reason before republishing.",
  },
};

// ── Indicator dot ─────────────────────────────────────────────────────────────

function IndicatorDot({ state }: { state: IndicatorState }) {
  const cls =
    state === "green"   ? "bg-emerald-400" :
    state === "amber"   ? "bg-amber-400"   :
    state === "red"     ? "bg-red-400"     :
    "bg-stone-600";
  return <span className={`inline-block w-2 h-2 rounded-full shrink-0 mt-1 ${cls}`} />;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mt-8 mb-3">
      <h2 className="text-xs font-semibold uppercase tracking-widest text-stone-400">{title}</h2>
      {sub && <p className="mt-0.5 text-xs text-stone-600">{sub}</p>}
    </div>
  );
}

function InfoGrid({ rows }: { rows: { label: string; value: React.ReactNode }[] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
      {rows.map(({ label, value }) => (
        <div key={label} className="min-w-0">
          <dt className="text-xs font-medium uppercase tracking-widest text-stone-400">{label}</dt>
          <dd className="mt-0.5 text-sm text-stone-200 break-words overflow-hidden">
            {value ?? <span className="text-stone-500">—</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function UrlRow({ label, href }: { label: string; href: string }) {
  return (
    <div className="flex gap-4 min-w-0">
      <dt className="shrink-0 w-28 text-xs font-medium uppercase tracking-widest text-stone-400 pt-0.5">
        {label}
      </dt>
      <dd className="flex-1 min-w-0">
        <a href={href} target="_blank" rel="noreferrer"
          className="block text-sm text-amber-400 hover:underline break-all leading-relaxed">
          {href}
        </a>
      </dd>
    </div>
  );
}

function StatPill({
  label, value, sub, highlight,
}: { label: string; value: string | number; sub?: string; highlight?: boolean }) {
  return (
    <div className={`rounded-lg border p-3 ${highlight ? "border-amber-500/30 bg-amber-950/20" : "border-stone-700 bg-stone-900"}`}>
      <p className="text-xs font-medium uppercase tracking-widest text-stone-400">{label}</p>
      <p className={`mt-0.5 text-xl font-semibold tabular-nums ${highlight ? "text-amber-400" : "text-stone-100"}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-stone-500">{sub}</p>}
    </div>
  );
}

function OsPlaceholder({
  title, body, link, linkLabel,
}: { title: string; body: string; link: string; linkLabel: string }) {
  return (
    <div className="rounded-lg border border-stone-800 bg-stone-900/40 p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-sm text-stone-400">{title}</p>
          <p className="text-xs text-stone-600 mt-0.5">{body}</p>
        </div>
        <Link href={link}
          className="shrink-0 rounded border border-stone-800 px-3 py-1.5 text-xs text-stone-500 hover:text-stone-300 hover:border-stone-700 transition-colors whitespace-nowrap">
          {linkLabel}
        </Link>
      </div>
    </div>
  );
}

// ── Entity Timeline ───────────────────────────────────────────────────────────

interface TimelineEvent {
  date:  string;
  label: string;
  type:  "created" | "published" | "canvassed" | "source_check" | "bd" | "enriched";
}

function buildTimeline(r: RestaurantInfo, partners: PartnerLinkRow[]): TimelineEvent[] {
  const events: TimelineEvent[] = [];

  if (r.created_at)      events.push({ date: r.created_at,       label: "Restaurant record created",    type: "created" });
  if (r.published_date)  events.push({ date: r.published_date,   label: "Published to GoldPan",         type: "published" });
  if (r.last_canvassed)  events.push({ date: r.last_canvassed,   label: "Last canvassed",               type: "canvassed" });
  if (r.last_source_check) events.push({ date: r.last_source_check, label: "Last source check",         type: "source_check" });

  for (const p of partners) {
    if (p.last_contact_date) {
      events.push({ date: p.last_contact_date, label: `BD contact — ${p.name}`, type: "bd" });
    }
  }

  return events
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
    .slice(0, 12); // cap at 12 events
}

function fmtDate(s: string): string {
  try {
    return new Date(s).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return s.slice(0, 10);
  }
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function RestaurantDetailPage({
  params,
}: {
  params: { id: string };
}) {
  let data: Awaited<ReturnType<typeof fetchRestaurantDetail>> | null = null;
  let fetchError: string | null = null;

  try {
    data = await fetchRestaurantDetail(params.id);
  } catch (err) {
    fetchError =
      err instanceof APIError
        ? `${err.status} — ${err.detail}`
        : err instanceof Error ? err.message : "Unknown error.";
  }

  if (fetchError) {
    return (
      <div className="flex flex-col gap-3">
        <Link href="/admin/restaurants" className="text-xs text-stone-500 hover:text-stone-300">
          ← Restaurants
        </Link>
        <div className="rounded-lg border border-red-800 bg-red-950/40 p-5">
          <p className="text-sm font-medium text-red-400">Could not load restaurant</p>
          <p className="mt-1 font-mono text-xs text-red-500">{fetchError}</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { restaurant: r, stats, menu_sources, dishes, claims, linked_partners, filter_summary } = data;

  const lq        = getLocationQuality(r);
  const health    = computeHealth(r, stats);
  const timeline  = buildTimeline(r, linked_partners);
  const lcExplain = LIFECYCLE_EXPLAIN[r.lifecycle_status];

  // Google Maps link — prefer lat/lng, fall back to address string
  const mapsUrl = (r.latitude != null && r.longitude != null)
    ? `https://maps.google.com?q=${r.latitude},${r.longitude}`
    : r.address
      ? `https://maps.google.com?q=${encodeURIComponent([r.address, r.city, r.state].filter(Boolean).join(", "))}`
      : null;

  const cityState = [r.city, r.state].filter(Boolean).join(", ") || null;

  // ── Lifecycle action availability ──────────────────────────────────────────
  const advanceActionName: string | null =
    ["evidence_acquisition", "onboarding", "suspended"].includes(r.lifecycle_status)
      ? "advance_to_qa"
      : r.lifecycle_status === "qa_review"
      ? "advance_to_verification"
      : null;

  const canRecanvass  = r.lifecycle_status !== "recanvassing";
  const canPublish    = ["qa_review", "verification", "evidence_acquisition", "onboarding"].includes(r.lifecycle_status);
  const canUnpublish  = r.lifecycle_status === "published";

  // ── Server Actions ──────────────────────────────────────────────────────────

  async function handleRecanvass(_fd: FormData) {
    "use server";
    await performLifecycleAction(params.id, "recanvass");
    redirect(`/admin/restaurants/${params.id}`);
  }

  async function handleAdvance(_fd: FormData) {
    "use server";
    if (!advanceActionName) return;
    await performLifecycleAction(params.id, advanceActionName);
    redirect(`/admin/restaurants/${params.id}`);
  }

  async function handlePublishToggle(_fd: FormData) {
    "use server";
    const action = r.lifecycle_status === "published" ? "unpublish" : "publish";
    await performLifecycleAction(params.id, action);
    redirect(`/admin/restaurants/${params.id}`);
  }

  return (
    <div className="max-w-5xl">

      {/* ── Breadcrumb ── */}
      <Link href="/admin/restaurants" className="text-xs text-stone-500 hover:text-stone-300 transition-colors">
        ← Restaurants
      </Link>

      {/* ── Header ── */}
      <div className="mt-3 flex flex-wrap items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-semibold text-stone-100">{r.name}</h1>
            <span className="font-mono text-xs text-stone-500">{r.external_id}</span>
            <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${lifecycleBadge(r.lifecycle_status)}`}>
              {r.lifecycle_status.replace(/_/g, " ")}
            </span>
            {r.evidence_tier && (
              <span className="rounded border border-stone-700 px-1.5 py-0.5 text-[10px] font-mono text-stone-500">
                {r.evidence_tier}
              </span>
            )}
          </div>
          {cityState && <p className="mt-0.5 text-sm text-stone-400">{cityState}</p>}
        </div>
        <div className="flex gap-2 shrink-0 flex-wrap">
          {/* Recanvass */}
          <form action={handleRecanvass}>
            <button
              type="submit"
              disabled={!canRecanvass}
              className={`rounded border px-3 py-1.5 text-xs font-medium transition-colors ${
                canRecanvass
                  ? "border-stone-600 bg-stone-800 text-stone-300 hover:text-stone-100 hover:border-stone-500"
                  : "border-stone-800 bg-stone-900 text-stone-600 cursor-not-allowed opacity-50"
              }`}
            >
              Recanvass
            </button>
          </form>

          {/* Advance to next stage */}
          {advanceActionName && (
            <form action={handleAdvance}>
              <button
                type="submit"
                className="rounded border border-stone-600 bg-stone-800 px-3 py-1.5 text-xs font-medium text-stone-300 hover:text-stone-100 hover:border-stone-500 transition-colors"
              >
                {advanceActionName === "advance_to_qa" ? "Advance to QA" : "Advance to Verification"}
              </button>
            </form>
          )}

          {/* Publish / Unpublish */}
          <form action={handlePublishToggle}>
            <button
              type="submit"
              disabled={!canPublish && !canUnpublish}
              className={`rounded border px-3 py-1.5 text-xs font-medium transition-colors ${
                canUnpublish
                  ? "border-red-800/60 bg-red-950/30 text-red-400 hover:bg-red-950/50"
                  : canPublish
                  ? "border-emerald-800/60 bg-emerald-950/30 text-emerald-400 hover:bg-emerald-950/50"
                  : "border-stone-800 bg-stone-900 text-stone-600 cursor-not-allowed opacity-50"
              }`}
            >
              {canUnpublish ? "Unpublish" : "Publish"}
            </button>
          </form>
        </div>
      </div>

      {/* ── Identity ── */}
      <SectionHeader title="Identity" sub="Enriched via Google Places API + Identity Enrichment Pipeline" />
      <div className="rounded-lg border border-stone-700 bg-stone-900/50 p-4 space-y-4">

        {/* Address block */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-widest text-stone-400">Address</p>
            <p className="mt-0.5 text-sm text-stone-200 break-words">
              {lq === "complete_address"
                ? r.address
                : lq === "city_state_only"
                  ? <span className="text-amber-500 italic text-xs">Street address needed</span>
                  : <span className="text-red-500 italic text-xs">No location data</span>
              }
            </p>
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-widest text-stone-400">City / State</p>
            <p className="mt-0.5 text-sm text-stone-200">{cityState ?? <span className="text-stone-500">—</span>}</p>
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-widest text-stone-400">Postal Code</p>
            <p className="mt-0.5 text-sm text-stone-200">{r.postal_code ?? <span className="text-stone-500">—</span>}</p>
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-widest text-stone-400">Phone</p>
            <p className="mt-0.5 text-sm text-stone-200">
              {r.phone
                ? <a href={`tel:${r.phone}`} className="text-stone-200 hover:text-amber-400 transition-colors">{r.phone}</a>
                : <span className="text-stone-500">—</span>
              }
            </p>
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-widest text-stone-400">Coordinates</p>
            <p className="mt-0.5 text-sm font-mono text-stone-400">
              {r.latitude != null && r.longitude != null
                ? `${r.latitude.toFixed(5)}, ${r.longitude.toFixed(5)}`
                : <span className="text-stone-500">—</span>
              }
            </p>
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium uppercase tracking-widest text-stone-400">Google Place ID</p>
            <p className="mt-0.5 text-xs font-mono text-stone-400 break-all">
              {r.google_place_id
                ? <a
                    href={`https://www.google.com/maps/place/?q=place_id:${r.google_place_id}`}
                    target="_blank" rel="noreferrer"
                    className="text-amber-500/70 hover:text-amber-400 transition-colors"
                  >
                    {r.google_place_id}
                  </a>
                : <span className="text-stone-500">— not enriched yet</span>
              }
            </p>
          </div>
        </div>

        {/* URLs */}
        {(r.official_website || r.menu_url || mapsUrl) && (
          <dl className="space-y-2 border-t border-stone-800 pt-3">
            {r.official_website && <UrlRow label="Website"  href={r.official_website} />}
            {r.menu_url          && <UrlRow label="Menu URL" href={r.menu_url} />}
            {mapsUrl             && <UrlRow label="Map"      href={mapsUrl} />}
          </dl>
        )}

        {/* Allergen / hours */}
        <div className="flex flex-wrap gap-x-8 gap-y-2 border-t border-stone-800 pt-3 text-xs">
          <div>
            <span className="text-stone-500 uppercase tracking-widest">Allergen guide</span>
            <span className={`ml-2 font-medium ${r.has_allergen_guide ? "text-emerald-400" : "text-stone-500"}`}>
              {r.has_allergen_guide ? "Yes" : "No"}
            </span>
          </div>
          {r.hours && (
            <div>
              <span className="text-stone-500 uppercase tracking-widest">Hours</span>
              <span className="ml-2 text-stone-300">{r.hours}</span>
            </div>
          )}
          {r.menu_statement && (
            <div className="w-full mt-1">
              <span className="text-stone-500 uppercase tracking-widest">Menu statement</span>
              <p className="mt-0.5 text-stone-400 italic">&ldquo;{r.menu_statement}&rdquo;</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Restaurant Health ── */}
      <SectionHeader title="Restaurant Health" />
      <div className={`rounded-lg border p-4 ${
        health.state === "healthy"         ? "border-emerald-800/50 bg-emerald-950/20" :
        health.state === "needs_attention" ? "border-amber-800/40 bg-amber-950/20"    :
                                             "border-red-800/40 bg-red-950/20"
      }`}>
        {/* Overall badge */}
        <div className="flex items-center gap-2 mb-4">
          <span className={`text-xs font-semibold uppercase tracking-widest px-2 py-0.5 rounded ${
            health.state === "healthy"         ? "bg-emerald-900/60 text-emerald-300" :
            health.state === "needs_attention" ? "bg-amber-900/50 text-amber-300"    :
                                                 "bg-red-900/50 text-red-300"
          }`}>
            {health.state === "healthy"         ? "Healthy" :
             health.state === "needs_attention" ? "Needs Attention" :
                                                  "Blocked"}
          </span>
          <span className="text-xs text-stone-500">
            {health.state === "healthy"         ? "All core indicators passing" :
             health.state === "needs_attention" ? "One or more indicators need review" :
                                                  "One or more critical issues must be resolved"}
          </span>
        </div>
        {/* Indicator grid */}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {health.indicators.map((ind) => (
            <div key={ind.label} className="flex items-start gap-2 rounded border border-stone-800 bg-stone-900/60 px-3 py-2">
              <IndicatorDot state={ind.state} />
              <div className="min-w-0">
                <p className="text-[10px] font-medium uppercase tracking-widest text-stone-400">{ind.label}</p>
                {ind.detail && <p className="mt-0.5 text-xs text-stone-300 break-words">{ind.detail}</p>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Lifecycle Explainability (only when not published) ── */}
      {r.lifecycle_status !== "published" && lcExplain && (
        <>
          <SectionHeader title="Why is this restaurant not published?" />
          <div className="rounded-lg border border-stone-700 bg-stone-900/60 p-4">
            <p className="text-sm font-medium text-stone-200 mb-1">{lcExplain.title}</p>
            <p className="text-sm text-stone-400">{lcExplain.body}</p>
            {lcExplain.next && (
              <p className="mt-2 text-xs text-amber-600">
                → {lcExplain.next}
              </p>
            )}
          </div>
        </>
      )}

      {/* ── Stats ── */}
      <SectionHeader title="Evidence summary" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatPill label="Active dishes"    value={stats.active_dish_count} sub={`${stats.dish_count} total`} />
        <StatPill label="Ingredients"      value={stats.ingredient_count} />
        <StatPill label="Trans. coverage"  value={pct(stats.transparency_coverage_pct)}
          sub={stats.avg_transparency_score !== null ? `avg ${stats.avg_transparency_score}/25` : undefined}
          highlight={stats.transparency_coverage_pct < 50 && stats.dish_count > 0}
        />
        <StatPill label="Calorie coverage" value={pct(stats.calorie_coverage_pct)}
          highlight={stats.calorie_coverage_pct < 20 && stats.dish_count > 0}
        />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatPill label="Claims"          value={stats.claims_count} />
        <StatPill label="Unknown filters" value={stats.unknown_filter_count}
          sub="dishes with unknown conclusion"
          highlight={stats.unknown_filter_count > 0}
        />
        <StatPill label="Menu sources"   value={stats.menu_sources_count} />
        <StatPill label="Recanvass tier" value={`T${r.recanvass_tier}`} />
      </div>

      {/* ── Freshness ── */}
      <SectionHeader title="Freshness / Recanvass" />
      <div className="flex flex-wrap gap-4 rounded-lg border border-stone-700 bg-stone-900 p-4">
        <div>
          <p className="text-xs text-stone-400 uppercase tracking-widest">Recanvass status</p>
          <span className={`mt-1 inline-block rounded px-2 py-0.5 text-sm font-medium ${recanvassBadge(r.recanvass_status)}`}>
            {r.recanvass_status.replace(/_/g, " ")}
          </span>
        </div>
        <div>
          <p className="text-xs text-stone-400 uppercase tracking-widest">Source check</p>
          <p className={`mt-1 text-sm font-medium ${sourceCheckBadge(r.source_check_status)}`}>
            {r.source_check_status}
          </p>
        </div>
        <div>
          <p className="text-xs text-stone-400 uppercase tracking-widest">Last source check</p>
          <p className="mt-1 text-sm text-stone-300">{r.last_source_check ?? "—"}</p>
        </div>
        <div>
          <p className="text-xs text-stone-400 uppercase tracking-widest">Last canvassed</p>
          <p className="mt-1 text-sm text-stone-300">{r.last_canvassed ?? "—"}</p>
        </div>
        <div>
          <p className="text-xs text-stone-400 uppercase tracking-widest">Recanvass tier</p>
          <p className="mt-1 text-sm text-stone-300">Tier {r.recanvass_tier}</p>
        </div>
        <div>
          <p className="text-xs text-stone-400 uppercase tracking-widest">Published</p>
          <p className="mt-1 text-sm text-stone-300">{r.published_date ?? "—"}</p>
        </div>
      </div>
      {r.recanvass_status === "overdue" && (
        <p className="mt-2 text-xs text-red-400">
          This restaurant is overdue for recanvassing. Menu data may be stale. Schedule a canvassing run.
        </p>
      )}
      {r.source_check_status === "changed" && (
        <p className="mt-2 text-xs text-amber-400">
          Source check detected a change since last canvassing. Review the source before relying on existing evidence.
        </p>
      )}
      {r.source_check_status === "unreachable" && (
        <p className="mt-2 text-xs text-red-400">
          Menu source is currently unreachable. Verify the URL and check for site outages before recanvassing.
        </p>
      )}

      {/* ── Business Development ── */}
      <SectionHeader title="Business Development" />
      {linked_partners.length === 0 ? (
        <div className="flex items-center gap-4 rounded-lg border border-stone-800 bg-stone-900/40 px-4 py-3">
          <p className="text-sm text-stone-500 flex-1">
            No BD record — this restaurant is not in the partnership pipeline.
          </p>
          <Link
            href="/admin/business-development/new"
            className="shrink-0 rounded border border-stone-700 bg-stone-900 px-3 py-1.5 text-xs font-medium text-stone-400 hover:border-amber-700 hover:text-amber-400 transition-colors"
          >
            + Create BD record
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {linked_partners.map((p) => {
            const followupOverdue = p.next_followup_date && new Date(p.next_followup_date) < new Date();
            return (
              <div key={p.partner_id} className="rounded-lg border border-stone-700 bg-stone-900 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <span className="text-sm font-medium text-stone-200">{p.name}</span>
                      <span className="font-mono text-xs text-stone-500">{p.external_id}</span>
                      <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                        p.status === "active"   ? "bg-emerald-900/50 text-emerald-300" :
                        p.status === "engaged"  ? "bg-blue-900/50 text-blue-300" :
                        p.status === "prospect" ? "bg-stone-700 text-stone-400" :
                        "bg-stone-700 text-stone-400"
                      }`}>{p.status}</span>
                      {p.priority === "high" && (
                        <span className="rounded bg-amber-900/40 px-1.5 py-0.5 text-xs font-medium text-amber-400">high priority</span>
                      )}
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-1.5 text-xs">
                      {p.pipeline_stage && (
                        <div>
                          <span className="text-stone-500 uppercase tracking-widest text-[10px]">Stage</span>
                          <p className="text-stone-300 mt-0.5">{p.pipeline_stage.replace(/_/g, " ")}</p>
                        </div>
                      )}
                      {p.contact_name && (
                        <div>
                          <span className="text-stone-500 uppercase tracking-widest text-[10px]">Contact</span>
                          <p className="text-stone-300 mt-0.5">{p.contact_name}</p>
                        </div>
                      )}
                      {p.relationship_owner && (
                        <div>
                          <span className="text-stone-500 uppercase tracking-widest text-[10px]">Owner</span>
                          <p className="text-stone-300 mt-0.5">{p.relationship_owner}</p>
                        </div>
                      )}
                      {p.last_contact_date && (
                        <div>
                          <span className="text-stone-500 uppercase tracking-widest text-[10px]">Last contact</span>
                          <p className="text-stone-300 mt-0.5">{p.last_contact_date}</p>
                        </div>
                      )}
                      {p.next_followup_date && (
                        <div>
                          <span className="text-stone-500 uppercase tracking-widest text-[10px]">Follow-up</span>
                          <p className={`mt-0.5 ${followupOverdue ? "text-amber-400" : "text-stone-300"}`}>
                            {p.next_followup_date}
                            {followupOverdue && " — overdue"}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                  <Link
                    href={`/admin/business-development/${p.external_id}`}
                    className="shrink-0 rounded border border-stone-700 bg-stone-800 px-3 py-1.5 text-xs font-medium text-stone-400 hover:border-amber-700 hover:text-amber-400 transition-colors"
                  >
                    Open BD record →
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Intake OS ── */}
      <SectionHeader title="Intake OS" sub="Canvassing history and packet queue" />
      <div className="rounded-lg border border-stone-800 bg-stone-900/40 p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 space-y-2">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-2 text-xs">
              <div>
                <span className="text-stone-500 uppercase tracking-widest text-[10px]">Last canvassed</span>
                <p className={`mt-0.5 text-sm ${r.last_canvassed ? "text-stone-300" : "text-stone-500"}`}>
                  {r.last_canvassed ?? "Never canvassed"}
                </p>
              </div>
              <div>
                <span className="text-stone-500 uppercase tracking-widest text-[10px]">Recanvass tier</span>
                <p className="mt-0.5 text-sm text-stone-300">
                  Tier {r.recanvass_tier}
                  <span className="ml-1.5 text-stone-600 text-[10px]">
                    {r.recanvass_tier === 1 ? "(monthly)" : r.recanvass_tier === 2 ? "(quarterly)" : "(annual)"}
                  </span>
                </p>
              </div>
              <div>
                <span className="text-stone-500 uppercase tracking-widest text-[10px]">Recanvass status</span>
                <span className={`mt-0.5 inline-block rounded px-1.5 py-0.5 text-xs font-medium ${recanvassBadge(r.recanvass_status)}`}>
                  {r.recanvass_status.replace(/_/g, " ")}
                </span>
              </div>
            </div>
            <p className="text-xs text-stone-600 pt-1 border-t border-stone-800">
              Intake packets managed via <span className="font-mono">ingest_packet.py</span>. Intake OS web UI ships in Phase 5.
            </p>
          </div>
          <Link href="/admin/intake"
            className="shrink-0 rounded border border-stone-800 px-3 py-1.5 text-xs text-stone-500 hover:text-stone-300 hover:border-stone-700 transition-colors">
            Intake OS →
          </Link>
        </div>
      </div>

      {/* ── Knowledge ── */}
      <SectionHeader title="Knowledge" sub="Transparency scores and menu evidence quality" />
      {stats.dish_count === 0 ? (
        <OsPlaceholder
          title="No dishes — no knowledge data yet"
          body="Transparency scoring runs after dishes are ingested via the Intake Pipeline."
          link="/admin/knowledge"
          linkLabel="Knowledge OS →"
        />
      ) : (
        <div className="rounded-lg border border-stone-700 bg-stone-900 p-4 space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-3 text-xs">
            <div>
              <span className="text-stone-400 uppercase tracking-widest text-[10px]">Active dishes</span>
              <p className="mt-0.5 text-sm font-semibold text-stone-100">{stats.active_dish_count}</p>
            </div>
            <div>
              <span className="text-stone-400 uppercase tracking-widest text-[10px]">Trans. coverage</span>
              <p className={`mt-0.5 text-sm font-semibold ${
                stats.transparency_coverage_pct >= 75 ? "text-emerald-400" :
                stats.transparency_coverage_pct >= 40 ? "text-amber-400"   : "text-red-400"
              }`}>{pct(stats.transparency_coverage_pct)}</p>
            </div>
            <div>
              <span className="text-stone-400 uppercase tracking-widest text-[10px]">Avg trans. score</span>
              <p className="mt-0.5 text-sm font-semibold text-stone-100">
                {stats.avg_transparency_score !== null ? `${stats.avg_transparency_score} / 25` : "—"}
              </p>
            </div>
            <div>
              <span className="text-stone-400 uppercase tracking-widest text-[10px]">Calorie coverage</span>
              <p className={`mt-0.5 text-sm font-semibold ${
                stats.calorie_coverage_pct >= 60 ? "text-emerald-400" :
                stats.calorie_coverage_pct >= 25 ? "text-amber-400"   : "text-stone-500"
              }`}>{pct(stats.calorie_coverage_pct)}</p>
            </div>
          </div>
          {stats.transparency_coverage_pct < 100 && stats.dish_count > 0 && (
            <p className="text-xs text-stone-600 border-t border-stone-800 pt-2">
              {stats.active_dish_count - Math.round(stats.transparency_coverage_pct / 100 * stats.active_dish_count)} active {
                stats.active_dish_count - Math.round(stats.transparency_coverage_pct / 100 * stats.active_dish_count) === 1 ? "dish" : "dishes"
              } without a current transparency score. Run the transparency pipeline to fill gaps.
            </p>
          )}
          <div className="flex justify-end border-t border-stone-800 pt-2">
            <Link href="/admin/knowledge" className="text-xs text-stone-500 hover:text-stone-300 transition-colors">
              Knowledge OS →
            </Link>
          </div>
        </div>
      )}

      {/* ── Governance ── */}
      <SectionHeader title="Governance" sub="Derived filter conclusions — computed by the governance pipeline" />
      {filter_summary.length === 0 ? (
        <div className="rounded-lg border border-stone-800 bg-stone-900/40 p-4">
          <p className="text-sm text-stone-500">No governance runs recorded for this restaurant.</p>
          <p className="text-xs text-stone-600 mt-1">
            Run the governance pipeline (<span className="font-mono">pipeline.py --governance</span>) to compute filter conclusions.
          </p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-stone-700">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-stone-700 bg-stone-900">
                  <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Filter</th>
                  <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Computed</th>
                  <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Unknown</th>
                  <th className="px-4 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">N/A</th>
                </tr>
              </thead>
              <tbody>
                {filter_summary.map((f) => (
                  <tr key={f.filter_slug} className="border-b border-stone-800 last:border-0 hover:bg-stone-800/30">
                    <td className="px-4 py-2.5">
                      <span className="text-stone-200">{f.filter_name}</span>
                      <span className="ml-2 font-mono text-[10px] text-stone-500">{f.filter_slug}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-emerald-400">{f.computed_count || "—"}</td>
                    <td className={`px-4 py-2.5 text-right tabular-nums ${f.unknown_count > 0 ? "text-amber-400" : "text-stone-500"}`}>
                      {f.unknown_count > 0 ? f.unknown_count : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-stone-500">
                      {f.not_applicable_count > 0 ? f.not_applicable_count : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {stats.unknown_filter_count > 0 && (
            <p className="mt-2 text-xs text-amber-600">
              {stats.unknown_filter_count} dish{stats.unknown_filter_count !== 1 ? "es have" : " has"} at least one unknown filter conclusion.
              Unknown means the evidence was insufficient to compute a definitive answer. Add ingredient data or claims to resolve.
            </p>
          )}
          <div className="flex justify-end mt-1">
            <Link href="/admin/governance" className="text-xs text-stone-500 hover:text-stone-300 transition-colors">
              Governance OS →
            </Link>
          </div>
        </>
      )}

      {/* ── Analytics ── */}
      <SectionHeader title="Analytics" />
      <OsPlaceholder
        title="Restaurant-level analytics"
        body="Page views, search appearances, filter usage, and engagement metrics. Analytics OS ships in a future phase."
        link="/admin/analytics"
        linkLabel="Analytics OS →"
      />

      {/* ── Entity Timeline ── */}
      <SectionHeader title="Activity Timeline" sub="Assembled from available activity data across OS layers" />
      {timeline.length === 0 ? (
        <p className="text-sm text-stone-500">No activity recorded yet.</p>
      ) : (
        <div className="relative border-l border-stone-800 ml-2 pl-6 space-y-4">
          {timeline.map((ev, i) => {
            const dotColor =
              ev.type === "published"    ? "bg-emerald-500" :
              ev.type === "canvassed"    ? "bg-amber-500"   :
              ev.type === "bd"           ? "bg-blue-500"    :
              ev.type === "source_check" ? "bg-sky-500"     :
              "bg-stone-500";
            return (
              <div key={i} className="relative">
                {/* Dot on the timeline line */}
                <span className={`absolute -left-[29px] top-1.5 w-2.5 h-2.5 rounded-full border-2 border-stone-950 ${dotColor}`} />
                <p className="text-xs font-medium text-stone-300">{ev.label}</p>
                <p className="text-[11px] text-stone-600 font-mono">{fmtDate(ev.date)}</p>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Menu Sources ── */}
      <SectionHeader title={`Menu sources (${menu_sources.length})`} />
      {menu_sources.length === 0 ? (
        <p className="text-sm text-stone-500">
          No menu source records. Ordering/allergen links and verification status will appear here once a source record exists.
        </p>
      ) : (
        <div className="space-y-2">
          {menu_sources.map((ms) => {
            const srcWebsite =
              ms.official_website && ms.official_website !== r.official_website
                ? ms.official_website : null;
            const srcMenuUrl =
              ms.official_menu_url && ms.official_menu_url !== r.menu_url
                ? ms.official_menu_url : null;
            const urlFields: [string, string | null | undefined][] = [
              ["Source Website",  srcWebsite],
              ["Source Menu URL", srcMenuUrl],
              ["Ordering URL",    ms.online_ordering_url],
              ["Allergen URL",    ms.allergen_nutrition_url],
            ];
            const metaFields: [string, string | null | undefined][] = [
              ["Preferred src",  ms.preferred_data_source],
              ["Confidence",     ms.source_confidence],
              ["Status",         ms.menu_status],
              ["Recanvass",      ms.recanvass_status?.replace(/_/g, " ")],
              ["Last canvassed", ms.last_canvassed],
              ["Last verified",  ms.last_verified_date],
              ["Source check",   ms.source_check_status],
            ];
            return (
              <div key={ms.source_id} className="rounded-lg border border-stone-700 bg-stone-900 p-4 space-y-3">
                {urlFields.some(([, v]) => v) && (
                  <dl className="space-y-2">
                    {urlFields.map(([label, val]) => val ? (
                      <UrlRow key={label} label={label} href={val} />
                    ) : null)}
                  </dl>
                )}
                {metaFields.some(([, v]) => v) && (
                  <div className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4 text-xs border-t border-stone-800 pt-3">
                    {metaFields.map(([label, val]) => val ? (
                      <div key={label} className="min-w-0">
                        <span className="text-stone-400 uppercase tracking-widest text-[10px]">{label}</span>
                        <p className="mt-0.5 text-stone-300 break-words">{val as string}</p>
                      </div>
                    ) : null)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Dishes ── */}
      <SectionHeader title={`Dishes (${stats.active_dish_count} active of ${stats.dish_count})`} />
      {dishes.length === 0 ? (
        <p className="text-sm text-stone-500">No dishes.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-stone-700">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-stone-700 bg-stone-900">
                <th className="px-3 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400 w-12">ID</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Dish</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Section</th>
                <th className="px-3 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Ings</th>
                <th className="px-3 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Score</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Calories</th>
                <th className="px-3 py-2.5 text-left text-xs font-medium uppercase tracking-widest text-stone-400">Tag src</th>
                <th className="px-3 py-2.5 text-right text-xs font-medium uppercase tracking-widest text-stone-400">Unk</th>
              </tr>
            </thead>
            <tbody>
              {dishes.map((d) => (
                <tr key={d.dish_id}
                  className={`border-b border-stone-800 last:border-0 ${!d.is_active ? "opacity-40" : "hover:bg-stone-800/30"}`}>
                  <td className="px-3 py-2 font-mono text-xs text-stone-400">{d.external_id}</td>
                  <td className="px-3 py-2 text-stone-200 max-w-xs">
                    <span className="font-medium">{d.dish_name}</span>
                    {d.category && <span className="ml-1.5 text-xs text-stone-500">{d.category}</span>}
                    {!d.is_active && <span className="ml-1.5 text-xs text-stone-500">[inactive]</span>}
                  </td>
                  <td className="px-3 py-2 text-xs text-stone-400 max-w-[120px] truncate">{d.menu_section ?? "—"}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-stone-300">{d.ingredient_count || "—"}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {d.has_transparency_score
                      ? <span className="text-amber-400/90">{d.transparency_score}</span>
                      : <span className="text-stone-500">—</span>}
                  </td>
                  <td className="px-3 py-2 text-xs text-stone-300">
                    {d.has_calorie ? d.calorie_value : <span className="text-stone-500">—</span>}
                  </td>
                  <td className="px-3 py-2 text-xs text-stone-400">{d.tag_source ?? "—"}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {d.unknown_filter_count > 0
                      ? <span className="text-amber-400">{d.unknown_filter_count}</span>
                      : <span className="text-stone-600">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Claims ── */}
      {claims.length > 0 && (
        <>
          <SectionHeader title={`Claims (${claims.length})`} />
          <div className="space-y-1.5">
            {claims.map((c) => (
              <div key={c.claim_id} className="rounded border border-stone-800 bg-stone-900/60 px-4 py-2.5">
                <p className="text-sm text-stone-200">{c.claim_text}</p>
                <p className="mt-0.5 text-xs text-stone-500">
                  {[c.claim_type, c.source_type].filter(Boolean).join(" · ")}
                </p>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── Notes ── */}
      {r.notes && (
        <>
          <SectionHeader title="Notes" />
          <p className="text-sm text-stone-400 rounded-lg border border-stone-800 bg-stone-900/50 p-4">{r.notes}</p>
        </>
      )}

      {/* ── Footer ── */}
      <p className="mt-10 text-xs text-stone-600">
        {r.external_id} · Created {fmtDate(r.created_at)} · Updated {fmtDate(r.updated_at)}
      </p>

    </div>
  );
}
