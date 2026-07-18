"use client";

// RestaurantMap.tsx — Public-facing Leaflet map of published GoldPan restaurants.
// Loaded dynamically with ssr:false — Leaflet requires window.
//
// Interaction model:
//   Hover  → lightweight tooltip: name, city/state
//   Click  → popup: name, address, "Visit website →" / "View menu →"
//   Mobile → click/tap only

import { useEffect, useRef } from "react";
import type { RestaurantMapItem } from "@/lib/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(s: string | null | undefined): string {
  return s ?? "";
}

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── CSS injection ─────────────────────────────────────────────────────────────

const STYLE_ID = "gp-public-map-styles";

function injectMapStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const el = document.createElement("style");
  el.id = STYLE_ID;
  el.textContent = `
    /* ── Tooltip (hover) ─────────────────────────────────── */
    .gp-pub-tooltip {
      background: rgba(21, 20, 19, 0.97) !important;
      border: 1px solid rgba(217, 119, 6, 0.35) !important;
      border-radius: 7px !important;
      padding: 7px 11px !important;
      color: #e7e5e4 !important;
      font-family: system-ui, -apple-system, sans-serif !important;
      font-size: 12px !important;
      box-shadow: 0 6px 20px rgba(0,0,0,0.55) !important;
      white-space: nowrap !important;
      pointer-events: none !important;
      max-width: 220px !important;
    }
    .gp-pub-tooltip::before { display: none !important; }

    /* ── Popup (click) ───────────────────────────────────── */
    .gp-pub-popup .leaflet-popup-content-wrapper {
      background: rgba(21, 20, 19, 0.98) !important;
      border: 1px solid rgba(217, 119, 6, 0.30) !important;
      border-radius: 9px !important;
      color: #e7e5e4 !important;
      box-shadow: 0 10px 30px rgba(0,0,0,0.65) !important;
      min-width: 190px !important;
    }
    .gp-pub-popup .leaflet-popup-content {
      margin: 14px 16px !important;
      font-family: system-ui, -apple-system, sans-serif !important;
    }
    .gp-pub-popup .leaflet-popup-tip-container { display: none !important; }
    .gp-pub-popup .leaflet-popup-close-button {
      color: #57534e !important;
      font-size: 18px !important;
      top: 8px !important;
      right: 10px !important;
      padding: 0 !important;
    }
    .gp-pub-popup .leaflet-popup-close-button:hover { color: #a8a29e !important; }
  `;
  document.head.appendChild(el);
}

// ── Pin colour ─────────────────────────────────────────────────────────────────
// Single amber accent — all published restaurants are equal on the public map.

const PIN_COLOR = "#d97706"; // amber-600

// ── Tooltip HTML ──────────────────────────────────────────────────────────────

function tooltipHtml(r: RestaurantMapItem): string {
  const loc = [r.city, r.state].filter(Boolean).join(", ");
  return `
    <div>
      <p style="font-weight:600;font-size:13px;margin:0 0 2px;color:#f5f5f4">
        ${esc(r.name)}
      </p>
      ${loc ? `<p style="font-size:10px;margin:0;color:#a8a29e">${esc(loc)}</p>` : ""}
    </div>
  `;
}

// ── Popup HTML ────────────────────────────────────────────────────────────────

function popupHtml(r: RestaurantMapItem): string {
  const loc     = [r.city, r.state].filter(Boolean).join(", ");
  const addr    = fmt(r.address);
  const website = r.official_website || r.menu_url;
  const linkLabel = r.official_website ? "Visit website →" : "View menu →";

  return `
    <div style="font-family:system-ui,-apple-system,sans-serif">
      <p style="font-weight:600;font-size:14px;margin:0 0 4px;color:#f5f5f4;line-height:1.3">
        ${esc(r.name)}
      </p>
      ${addr ? `<p style="font-size:11px;margin:0 0 1px;color:#a8a29e">${esc(addr)}</p>` : ""}
      ${loc  ? `<p style="font-size:11px;margin:0 0 0;color:#78716c">${esc(loc)}</p>` : ""}
      ${website ? `
        <a href="${esc(website)}"
           target="_blank"
           rel="noopener noreferrer"
           style="display:inline-block;margin-top:10px;font-size:11px;font-weight:500;
                  color:#d97706;text-decoration:none;border:1px solid rgba(217,119,6,0.3);
                  border-radius:4px;padding:3px 8px;transition:background 0.15s"
           onmouseover="this.style.background='rgba(217,119,6,0.12)'"
           onmouseout="this.style.background='transparent'">
          ${esc(linkLabel)}
        </a>
      ` : ""}
    </div>
  `;
}

// ── Component ─────────────────────────────────────────────────────────────────

interface RestaurantMapProps {
  restaurants: RestaurantMapItem[];
}

export default function RestaurantMap({ restaurants }: RestaurantMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    import("leaflet").then((L) => {
      injectMapStyles();

      const map = L.map(containerRef.current!, {
        center: [33.5186, -86.8104], // Birmingham, AL
        zoom: 11,
        zoomControl: true,
      });
      mapRef.current = map;

      L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        {
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors ' +
            '&copy; <a href="https://carto.com/attributions">CARTO</a>',
          maxZoom: 19,
        },
      ).addTo(map);

      restaurants.forEach((r) => {
        const marker = L.circleMarker([r.latitude, r.longitude], {
          radius:      8,
          fillColor:   PIN_COLOR,
          fillOpacity: 0.85,
          color:       "#92400e", // darker amber ring
          weight:      1.5,
          opacity:     0.9,
        }).addTo(map);

        marker.bindTooltip(tooltipHtml(r), {
          className: "gp-pub-tooltip",
          direction: "top",
          offset:    [0, -10],
          opacity:   1,
        });

        marker.bindPopup(popupHtml(r), {
          className:      "gp-pub-popup",
          maxWidth:       280,
          offset:         [0, -4],
          autoPan:        true,
          autoPanPadding: [20, 20],
        });
      });

      if (restaurants.length > 0) {
        const bounds = L.latLngBounds(
          restaurants.map((r) => [r.latitude, r.longitude] as [number, number]),
        );
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
      }
    });

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} style={{ height: "100%", width: "100%" }} />

      {/* Pin count badge */}
      <div className="absolute bottom-4 left-4 z-[1000] rounded-lg border border-stone-700 bg-stone-900/95 px-3 py-2 shadow-lg pointer-events-none">
        <p className="text-[11px] text-stone-400">
          <span className="font-semibold text-amber-500">{restaurants.length}</span>
          {" "}restaurant{restaurants.length !== 1 ? "s" : ""} on GoldPan
        </p>
      </div>
    </div>
  );
}
