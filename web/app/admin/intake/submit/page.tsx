"use client";
// app/admin/intake/submit/page.tsx
// Intake OS — submit packet via file upload or paste.
// Client component: parses + validates JSON in-browser, shows preview, then calls server action.

import { useState, useRef } from "react";
import Link from "next/link";
import { submitPacketAction } from "./actions";

// ── Types ─────────────────────────────────────────────────────────────────────

type Mode = "file" | "paste";

interface PacketPreview {
  restaurantName: string;
  externalId:     string;
  dishCount:      number;
  flagCount:      number;
  evidenceScore:  number | null;
  canvassDate:    string | null;
  modelUsed:      string | null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const REQUIRED_KEYS = ["restaurant", "dishes", "evidence_score", "agent_metadata"] as const;

function validate(data: Record<string, unknown>): string | null {
  for (const k of REQUIRED_KEYS) {
    if (!(k in data)) return `Missing required key: "${k}"`;
  }
  if (!Array.isArray(data.dishes)) return `"dishes" must be an array`;
  return null;
}

function parsePreview(data: Record<string, unknown>): PacketPreview {
  const restaurant = (data.restaurant ?? {}) as Record<string, unknown>;
  const dishes     = (data.dishes     ?? []) as unknown[];
  const flags      = (data.review_flags ?? []) as unknown[];
  const evidence   = (data.evidence_score ?? {}) as Record<string, unknown>;
  const meta       = (data.agent_metadata ?? {}) as Record<string, unknown>;

  return {
    restaurantName: String(restaurant.restaurant_name ?? restaurant.name ?? "Unknown"),
    externalId:     String(restaurant.restaurant_id   ?? restaurant.external_id ?? ""),
    dishCount:      dishes.length,
    flagCount:      flags.length,
    evidenceScore:  typeof evidence.overall === "number" ? evidence.overall : null,
    canvassDate:    typeof restaurant.canvass_date === "string" ? restaurant.canvass_date : null,
    modelUsed:      typeof meta.model === "string" ? meta.model : null,
  };
}

function scoreColor(n: number | null) {
  if (n == null) return "text-stone-500";
  if (n >= 80)   return "text-emerald-400";
  if (n >= 60)   return "text-amber-400";
  return "text-red-400";
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SubmitPacketPage() {
  const [mode, setMode]               = useState<Mode>("file");
  const [pasteText, setPasteText]     = useState("");
  const [fileName, setFileName]       = useState<string | null>(null);
  const [parseError, setParseError]   = useState<string | null>(null);
  const [preview, setPreview]         = useState<PacketPreview | null>(null);
  const [parsedData, setParsedData]   = useState<Record<string, unknown> | null>(null);
  const [externalId, setExternalId]   = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [loading, setLoading]         = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // ── JSON processing ─────────────────────────────────────────────────────────

  function processJson(text: string) {
    setParseError(null);
    setPreview(null);
    setParsedData(null);

    if (!text.trim()) return;

    let data: Record<string, unknown>;
    try {
      data = JSON.parse(text) as Record<string, unknown>;
    } catch {
      setParseError("Invalid JSON — could not parse.");
      return;
    }

    const err = validate(data);
    if (err) { setParseError(err); return; }

    const pv = parsePreview(data);
    setPreview(pv);
    setParsedData(data);

    // Auto-fill external ID from packet if not already overridden
    if (!externalId && pv.externalId) {
      setExternalId(pv.externalId.toUpperCase());
    }
  }

  // ── File handler ────────────────────────────────────────────────────────────

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = (ev) => processJson(ev.target?.result as string);
    reader.readAsText(file);
  }

  // ── Mode switch (reset state) ───────────────────────────────────────────────

  function switchMode(m: Mode) {
    setMode(m);
    setParseError(null);
    setPreview(null);
    setParsedData(null);
    setFileName(null);
    setPasteText("");
    setSubmitError(null);
    if (fileRef.current) fileRef.current.value = "";
  }

  // ── Submit ──────────────────────────────────────────────────────────────────

  async function handleSubmit() {
    if (!parsedData || loading) return;
    setLoading(true);
    setSubmitError(null);
    try {
      const result = await submitPacketAction(
        parsedData,
        externalId.trim() || undefined,
      );
      // result is only returned on error; success redirects server-side
      if (result?.error) {
        setSubmitError(result.error);
        setLoading(false);
      }
    } catch {
      setSubmitError("Unexpected error during submission.");
      setLoading(false);
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="max-w-3xl">

      {/* ── Header ── */}
      <div className="mb-5">
        <Link
          href="/admin/intake"
          className="text-xs text-stone-600 hover:text-stone-400 transition-colors"
        >
          ← Packet Queue
        </Link>
        <div className="mt-2">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-600 mb-0.5">
            Intake OS
          </p>
          <h1 className="text-2xl font-bold text-stone-100 leading-tight">Submit Packet</h1>
        </div>
      </div>

      {/* ── Mode toggle ── */}
      <div className="mb-5 flex rounded-lg border border-stone-700 overflow-hidden text-xs font-medium w-fit">
        <button
          onClick={() => switchMode("file")}
          className={`px-4 py-2 transition-colors ${
            mode === "file"
              ? "bg-amber-600/20 text-amber-400 border-r border-amber-600/30"
              : "bg-stone-900 text-stone-500 hover:text-stone-300 border-r border-stone-700"
          }`}
        >
          Upload File
        </button>
        <button
          onClick={() => switchMode("paste")}
          className={`px-4 py-2 transition-colors ${
            mode === "paste"
              ? "bg-amber-600/20 text-amber-400"
              : "bg-stone-900 text-stone-500 hover:text-stone-300"
          }`}
        >
          Paste JSON
        </button>
      </div>

      {/* ── External ID override ── */}
      <div className="mb-4">
        <label className="block text-[10px] font-medium uppercase tracking-widest text-stone-500 mb-1.5">
          Restaurant External ID <span className="text-stone-600 normal-case font-normal tracking-normal">(optional — derived from packet if omitted)</span>
        </label>
        <input
          type="text"
          value={externalId}
          onChange={e => setExternalId(e.target.value)}
          placeholder="e.g. R027"
          className="w-64 rounded border border-stone-700 bg-stone-800 px-3 py-2 text-sm text-stone-200 placeholder-stone-600 font-mono focus:outline-none focus:border-stone-500"
        />
      </div>

      {/* ── Upload file mode ── */}
      {mode === "file" && (
        <div className="mb-4">
          <label className="block text-[10px] font-medium uppercase tracking-widest text-stone-500 mb-1.5">
            Packet JSON File
          </label>
          <div
            onClick={() => fileRef.current?.click()}
            className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
              fileName
                ? "border-emerald-700/50 bg-emerald-950/10"
                : "border-stone-700 hover:border-stone-500 bg-stone-900/40"
            }`}
          >
            {fileName ? (
              <>
                <p className="text-sm font-medium text-stone-200 font-mono mb-0.5">{fileName}</p>
                <p className="text-xs text-stone-500">Click to choose a different file</p>
              </>
            ) : (
              <>
                <p className="text-sm text-stone-400 mb-1">Click to choose a file</p>
                <p className="text-xs text-stone-600">intake_packets/*.json</p>
              </>
            )}
            <input
              ref={fileRef}
              type="file"
              accept=".json,application/json"
              onChange={handleFileChange}
              className="hidden"
            />
          </div>
        </div>
      )}

      {/* ── Paste mode ── */}
      {mode === "paste" && (
        <div className="mb-4">
          <label className="block text-[10px] font-medium uppercase tracking-widest text-stone-500 mb-1.5">
            Packet JSON
          </label>
          <textarea
            value={pasteText}
            onChange={e => { setPasteText(e.target.value); processJson(e.target.value); }}
            rows={20}
            placeholder={"{\n  \"restaurant\": { ... },\n  \"dishes\": [ ... ],\n  \"review_flags\": [ ... ],\n  \"evidence_score\": { ... },\n  \"agent_metadata\": { ... }\n}"}
            className="w-full rounded border border-stone-700 bg-stone-900 px-3 py-2.5 text-xs text-stone-300 placeholder-stone-700 font-mono focus:outline-none focus:border-stone-500 resize-y"
          />
        </div>
      )}

      {/* ── Parse error ── */}
      {parseError && (
        <div className="mb-4 rounded-lg border border-red-800/50 bg-red-950/30 p-3">
          <p className="text-xs font-medium text-red-400">{parseError}</p>
        </div>
      )}

      {/* ── Preview card ── */}
      {preview && (
        <div className="mb-5 rounded-lg border border-emerald-800/40 bg-emerald-950/10 p-4">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-emerald-500 mb-3">
            Packet valid ✓
          </p>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-2 text-xs">
            <div className="flex items-center justify-between gap-3">
              <dt className="text-stone-500 shrink-0">Restaurant</dt>
              <dd className="text-stone-200 font-medium truncate">{preview.restaurantName}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-stone-500 shrink-0">External ID</dt>
              <dd className="font-mono text-stone-400">{preview.externalId || "—"}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-stone-500 shrink-0">Dishes</dt>
              <dd className="text-stone-300 tabular-nums">{preview.dishCount}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-stone-500 shrink-0">Review flags</dt>
              <dd className={`tabular-nums font-medium ${preview.flagCount > 0 ? "text-amber-400" : "text-stone-500"}`}>
                {preview.flagCount || "—"}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-stone-500 shrink-0">Evidence score</dt>
              <dd className={`tabular-nums font-medium ${scoreColor(preview.evidenceScore)}`}>
                {preview.evidenceScore ?? "—"}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-stone-500 shrink-0">Canvass date</dt>
              <dd className="text-stone-400">{preview.canvassDate ?? "—"}</dd>
            </div>
            {preview.modelUsed && (
              <div className="flex items-center justify-between gap-3 col-span-2">
                <dt className="text-stone-500 shrink-0">Model</dt>
                <dd className="font-mono text-stone-500 text-[11px]">{preview.modelUsed}</dd>
              </div>
            )}
          </dl>
        </div>
      )}

      {/* ── Submit error ── */}
      {submitError && (
        <div className="mb-4 rounded-lg border border-red-800/50 bg-red-950/30 p-4">
          <p className="text-sm font-medium text-red-400">Submission failed</p>
          <p className="mt-1 font-mono text-xs text-red-500">{submitError}</p>
        </div>
      )}

      {/* ── Actions ── */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSubmit}
          disabled={!parsedData || loading}
          className={`rounded-lg px-5 py-2 text-sm font-medium transition-colors ${
            parsedData && !loading
              ? "bg-amber-600 hover:bg-amber-500 text-white"
              : "bg-stone-800 text-stone-600 cursor-not-allowed"
          }`}
        >
          {loading ? "Submitting…" : "Submit Packet"}
        </button>
        <Link
          href="/admin/intake"
          className="text-xs text-stone-500 hover:text-stone-300 transition-colors"
        >
          Cancel
        </Link>
      </div>

    </div>
  );
}
