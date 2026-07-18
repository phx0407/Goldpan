// app/admin/business-development/page.tsx
// Server component — fetches partner data and hands it to BDWorkspace.
// All interactivity (market selector, view toggle, filters) lives in BDWorkspace.

import { fetchPartnerList, APIError } from "@/lib/api";
import BDWorkspace from "./BDWorkspace";

// Leaflet CSS must be imported in a component that Next.js processes at build
// time. The server component is the right place — it reaches the client bundle.
import "leaflet/dist/leaflet.css";

// no ISR — mutations need immediate freshness
export const dynamic = "force-dynamic";

export default async function BusinessDevelopmentPage() {
  let data: Awaited<ReturnType<typeof fetchPartnerList>> | null = null;
  let fetchError: string | null = null;

  try {
    data = await fetchPartnerList();
  } catch (err) {
    fetchError =
      err instanceof APIError
        ? `${err.status} — ${err.detail}`
        : err instanceof Error ? err.message : "Unknown error.";
  }

  if (fetchError) {
    return (
      <div className="flex flex-col gap-3">
        <h1 className="text-lg font-semibold text-stone-100">Business Development</h1>
        <div className="rounded-lg border border-red-800 bg-red-950/40 p-5">
          <p className="text-sm font-medium text-red-400">Could not load partners</p>
          <p className="mt-1 font-mono text-xs text-red-500">{fetchError}</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return <BDWorkspace partners={data.partners} summary={data.summary} />;
}
