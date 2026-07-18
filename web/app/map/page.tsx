// app/map/page.tsx — Public restaurant map.
// Shows all published GoldPan restaurants with geocoordinates.
// Dark Leaflet tile layer. Hover = name + city. Click = details + website link.

import nextDynamic from "next/dynamic";
import { fetchRestaurantsForMap, APIError } from "@/lib/api";
import type { RestaurantMapItem } from "@/lib/types";
import "leaflet/dist/leaflet.css";

export const dynamic = "force-dynamic";

// Load Leaflet client-side only (Leaflet requires window)
const RestaurantMap = nextDynamic(() => import("./RestaurantMap"), { ssr: false });

export default async function PublicMapPage() {
  let restaurants: RestaurantMapItem[] = [];
  let fetchError: string | null = null;

  try {
    restaurants = await fetchRestaurantsForMap();
  } catch (err) {
    fetchError =
      err instanceof APIError
        ? `${err.status} — ${err.detail}`
        : err instanceof Error ? err.message : "Unknown error.";
  }

  return (
    <div className="flex flex-col" style={{ height: "100dvh" }}>
      {/* Minimal header */}
      <div className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-stone-800 bg-stone-950">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-amber-500 tracking-tight">
            GoldPan
          </span>
          <span className="text-stone-600 text-xs">·</span>
          <span className="text-xs text-stone-500">Restaurant Map</span>
        </div>
        {!fetchError && restaurants.length > 0 && (
          <span className="text-xs text-stone-600">
            {restaurants.length} restaurant{restaurants.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Error state */}
      {fetchError && (
        <div className="flex-1 flex items-center justify-center">
          <div className="rounded-lg border border-red-800 bg-red-950/40 px-5 py-4 text-sm text-red-400 max-w-sm">
            {fetchError}
          </div>
        </div>
      )}

      {/* Map — fills remaining height */}
      {!fetchError && (
        <div className="flex-1 min-h-0">
          <RestaurantMap restaurants={restaurants} />
        </div>
      )}
    </div>
  );
}
