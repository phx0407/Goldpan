"use client";

// PartnerMap.tsx — Raw Leaflet map (no react-leaflet).
// Loaded dynamically with ssr:false — Leaflet requires window.
//
// Interaction model:
//   Hover  → lightweight tooltip: name, status, location, address, follow-up
//   Click  → richer popup: full details + "Open record →" link
//   Mobile → click/tap only (hover events don't exist on touch)

import { useEffect, useRef } from "react";
import type { PartnerRow } from "@/lib/types";

// ── Status colours ────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  active:      "#34d399",
  engaged:     "#60a5fa",
  negotiating: "#a78bfa",
  outreach:    "#38bdf8",
  prospect:    "#78716c",
  paused:      "#fbbf24",
  declined:    "#f87171",
  churned:     "#ef4444",
};

function markerColor(status: string): string {
  return STATUS_COLORS[status] ?? "#78716c";
}

// ── Legend ────────────────────────────────────────────────────────────────────

const LEGEND_ENTRIES = Object.entries(STATUS_COLORS);

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(s: string | null | undefined): string {
  return s ?? "";
}

function fmtDate(d: string | null | undefined): string {
  if (!d) return "";
  return d.slice(0, 10); // "YYYY-MM-DD"
}

function isOverdue(d: string | null | undefined): boolean {
  if (!d) return false;
  return d.slice(0, 10) <= new Date().toISOString().slice(0, 10);
}

function esc(s: string): string {
  // Minimal HTML escape for user-supplied strings in innerHTML
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── CSS injection (runs once) ─────────────────────────────────────────────────

const STYLE_ID = "gp-map-styles";

function injectMapStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const el = document.createElement("style");
  el.id = STYLE_ID;
  el.textContent = `
    /* ── Tooltip (hover) ─────────────────────────────────── */
    .gp-tooltip {
      background: rgba(21, 20, 19, 0.97) !important;
      border: 1px solid rgba(87, 83, 78, 0.55) !important;
      border-radius: 7px !important;
      padding: 8px 11px !important;
      color: #e7e5e4 !important;
      font-family: system-ui, -apple-system, sans-serif !important;
      font-size: 12px !important;
      box-shadow: 0 6px 20px rgba(0,0,0,0.55) !important;
      white-space: nowrap !important;
      pointer-events: none !important;
      max-width: 240px !important;
    }
    /* Hide the default arrow — offset handles the gap */
    .gp-tooltip::before { display: none !important; }

    /* ── Popup (click) ───────────────────────────────────── */
    .gp-popup .leaflet-popup-content-wrapper {
      background: rgba(21, 20, 19, 0.98) !important;
      border: 1px solid rgba(87, 83, 78, 0.55) !important;
      border-radius: 9px !important;
      color: #e7e5e4 !important;
      box-shadow: 0 10px 30px rgba(0,0,0,0.65) !important;
      min-width: 200px !important;
    }
    .gp-popup .leaflet-popup-content {
      margin: 14px 16px !important;
      font-family: system-ui, -apple-system, sans-serif !important;
    }
    .gp-popup .leaflet-popup-tip-container { display: none !important; }
    .gp-popup .leaflet-popup-close-button {
      color: #57534e !important;
      font-size: 18px !important;
      top: 8px !important;
      right: 10px !important;
      padding: 0 !important;
    }
    .gp-popup .leaflet-popup-close-button:hover { color: #a8a29e !important; }
  `;
  document.head.appendChild(el);
}

// ── Tooltip HTML (compact hover card) ────────────────────────────────────────

function tooltipHtml(p: PartnerRow): string {
  const color   = markerColor(p.status);
  const typeStr = p.partner_type.replace(/_/g, " ");
  const loc     = [p.city, p.state].filter(Boolean).join(", ");
  const addr    = fmt(p.address);
  const fu      = fmtDate(p.next_followup_date);
  const fuColor = isOverdue(p.next_followup_date) ? "#fbbf24" : "#a8a29e";

  return `
    <div>
      <p style="font-weight:600;font-size:13px;margin:0 0 3px;color:#f5f5f4">
        ${esc(p.name)}
      </p>
      <p style="font-size:10px;margin:0 0 4px;text-transform:capitalize;color:#a8a29e">
        ${esc(typeStr)} ·
        <span style="color:${color};font-weight:500">${esc(p.status)}</span>
      </p>
      ${loc  ? `<p style="font-size:10px;margin:0 0 1px;color:#78716c">${esc(loc)}</p>` : ""}
      ${addr ? `<p style="font-size:10px;margin:0 0 1px;color:#57534e">${esc(addr)}</p>` : ""}
      ${fu   ? `<p style="font-size:10px;margin:3px 0 0;color:${fuColor}">Follow-up: ${esc(fu)}</p>` : ""}
    </div>
  `;
}

// ── Popup HTML (richer click card) ────────────────────────────────────────────

function popupHtml(p: PartnerRow): string {
  const color    = markerColor(p.status);
  const typeStr  = p.partner_type.replace(/_/g, " ");
  const loc      = [p.city, p.state].filter(Boolean).join(", ");
  const addr     = fmt(p.address);
  const contact  = fmt(p.contact_name);
  const lastCon  = fmtDate(p.last_contact_date);
  const fu       = fmtDate(p.next_followup_date);
  const fuColor  = isOverdue(p.next_followup_date) ? "#fbbf24" : "#a8a29e";

  return `
    <div style="font-family:system-ui,-apple-system,sans-serif">
      <p style="font-weight:600;font-size:14px;margin:0 0 3px;color:#f5f5f4;line-height:1.3">
        ${esc(p.name)}
      </p>
      <p style="font-size:11px;margin:0 0 8px;text-transform:capitalize;color:#a8a29e">
        ${esc(typeStr)} ·
        <span style="color:${color};font-weight:500">${esc(p.status)}</span>
      </p>
      ${loc     ? `<p style="font-size:11px;margin:0 0 2px;color:#a8a29e">${esc(loc)}</p>` : ""}
      ${addr    ? `<p style="font-size:11px;margin:0 0 6px;color:#78716c">${esc(addr)}</p>` : ""}
      ${contact ? `<p style="font-size:11px;margin:0 0 2px;color:#78716c">Contact: ${esc(contact)}</p>` : ""}
      ${lastCon ? `<p style="font-size:11px;margin:0 0 2px;color:#57534e">Last contact: ${esc(lastCon)}</p>` : ""}
      ${fu      ? `<p style="font-size:11px;margin:0 0 2px;color:${fuColor}">Follow-up: ${esc(fu)}</p>` : ""}
      <a href="/admin/business-development/${esc(p.external_id)}"
         style="display:inline-block;margin-top:10px;font-size:11px;font-weight:500;
                color:#d97706;text-decoration:none;border:1px solid rgba(217,119,6,0.3);
                border-radius:4px;padding:3px 8px;transition:background 0.15s"
         onmouseover="this.style.background='rgba(217,119,6,0.12)'"
         onmouseout="this.style.background='transparent'">
        Open record →
      </a>
    </div>
  `;
}

// ── Component ─────────────────────────────────────────────────────────────────

interface PartnerMapProps {
  partners:      PartnerRow[];
  needsLocation: PartnerRow[];
  /** Map center — defaults to Birmingham, AL. Pass from MarketContext for multi-market support. */
  center?: [number, number];
  /** Initial zoom level — defaults to 10. */
  zoom?: number;
}

export default function PartnerMap({
  partners,
  needsLocation,
  center = [33.5186, -86.8104],
  zoom   = 10,
}: PartnerMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    import("leaflet").then((L) => {
      injectMapStyles();

      const map = L.map(containerRef.current!, {
        center,
        zoom,
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

      const mapped = partners.filter(
        (p) => p.latitude != null && p.longitude != null,
      );

      mapped.forEach((p) => {
        const color  = markerColor(p.status);
        const marker = L.circleMarker([p.latitude!, p.longitude!], {
          radius:      7,
          fillColor:   color,
          fillOpacity: 0.88,
          color:       color,
          weight:      1.5,
          opacity:     0.95,
        }).addTo(map);

        // Hover tooltip — compact, pointer-events:none prevents flicker
        marker.bindTooltip(tooltipHtml(p), {
          className:   "gp-tooltip",
          direction:   "top",
          offset:      [0, -10],
          opacity:     1,
          // sticky:false (default) anchors above marker rather than following cursor
          // This prevents flickering on dense markers
        });

        // Click popup — richer details + action link
        marker.bindPopup(popupHtml(p), {
          className:  "gp-popup",
          maxWidth:   280,
          offset:     [0, -4],
          autoPan:    true,
          autoPanPadding: [20, 20],
        });
      });

      if (mapped.length > 0) {
        const bounds = L.latLngBounds(
          mapped.map((p) => [p.latitude!, p.longitude!] as [number, number]),
        );
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
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

      {/* Legend */}
      <div className="absolute bottom-4 left-4 z-[1000] rounded-lg border border-stone-700 bg-stone-900/95 p-3 shadow-lg pointer-events-none">
        <p className="text-[10px] font-medium uppercase tracking-wider text-stone-400 mb-2">
          Status
        </p>
        <div className="space-y-1.5">
          {LEGEND_ENTRIES.map(([status, color]) => (
            <div key={status} className="flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-full shrink-0"
                style={{ backgroundColor: color }}
              />
              <span className="text-xs text-stone-400 capitalize">{status}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Missing location badge */}
      {needsLocation.length > 0 && (
        <div className="absolute top-3 right-3 z-[1000] rounded border border-amber-800/50 bg-amber-950/80 px-2.5 py-1 text-xs text-amber-400 shadow pointer-events-none">
          {needsLocation.length} partner{needsLocation.length !== 1 ? "s" : ""} missing location
        </div>
      )}
    </div>
  );
}
