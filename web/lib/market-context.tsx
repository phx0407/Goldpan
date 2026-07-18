"use client";

// lib/market-context.tsx — GoldPan Market Registry + React Context
//
// A "market" is a metropolitan operating area (e.g. Birmingham, Nashville).
// Birmingham is the only market today. The context is the single source of
// truth for which market the user is currently operating in — it will drive
// every BD view (Map, List, Analytics, etc.) once multi-market is live.
//
// To add a market: add an entry to MARKETS. No other changes required.
// Backend market filtering is a future concern; this is the UI layer only.

import { createContext, useContext, useState } from "react";

// ── Market type ───────────────────────────────────────────────────────────────

export interface Market {
  id:     string;           // stable slug — used as a key in filters, URLs, etc.
  name:   string;           // display name shown in the selector
  city:   string;           // primary city
  state:  string;           // US state abbreviation
  center: [number, number]; // [lat, lng] — Leaflet map default center
  zoom:   number;           // Leaflet default zoom level
}

// ── Market registry ───────────────────────────────────────────────────────────
// Add future markets here. The UI will pick them up automatically.

export const MARKETS: Market[] = [
  {
    id:     "birmingham",
    name:   "Birmingham",
    city:   "Birmingham",
    state:  "AL",
    center: [33.5186, -86.8104],
    zoom:   10,
  },
  // Future markets (not yet live — uncomment when backend supports them):
  // { id: "nashville",    name: "Nashville",    city: "Nashville",    state: "TN", center: [36.1627, -86.7816], zoom: 11 },
  // { id: "atlanta",      name: "Atlanta",      city: "Atlanta",      state: "GA", center: [33.7490, -84.3880], zoom: 11 },
  // { id: "charlotte",    name: "Charlotte",    city: "Charlotte",    state: "NC", center: [35.2271, -80.8431], zoom: 11 },
  // { id: "new-orleans",  name: "New Orleans",  city: "New Orleans",  state: "LA", center: [29.9511, -90.0715], zoom: 11 },
];

// ── Context ───────────────────────────────────────────────────────────────────

interface MarketContextValue {
  market:    Market;
  setMarket: (m: Market) => void;
  markets:   readonly Market[];
}

const MarketContext = createContext<MarketContextValue>({
  market:    MARKETS[0],
  setMarket: () => {},
  markets:   MARKETS,
});

export function MarketProvider({ children }: { children: React.ReactNode }) {
  const [market, setMarket] = useState<Market>(MARKETS[0]);
  return (
    <MarketContext.Provider value={{ market, setMarket, markets: MARKETS }}>
      {children}
    </MarketContext.Provider>
  );
}

export function useMarket(): MarketContextValue {
  return useContext(MarketContext);
}
