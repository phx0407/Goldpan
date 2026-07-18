// app/admin/business-development/actions.ts
// Server Actions for all BD partner mutations.
// ADMIN_API_KEY is server-only — never exposed to the browser.
// All writes go through FastAPI; FastAPI writes to Supabase with the service role key.

"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

const API_URL   = process.env.GOLDPAN_API_URL  ?? "http://localhost:8000";
const ADMIN_KEY = process.env.ADMIN_API_KEY    ?? "";

function hdrs() {
  return { "X-Admin-Key": ADMIN_KEY, "Content-Type": "application/json" };
}

// ── Geocoding (Nominatim / OpenStreetMap) ─────────────────────────────────────
// Called server-side only. Auto-fills lat/lng when city + state are provided.
// Nominatim usage policy: 1 req/s max; must send User-Agent.

async function geocode(
  city: string,
  state: string,
): Promise<{ lat: number; lon: number } | null> {
  try {
    const q   = encodeURIComponent(`${city.trim()}, ${state.trim()}, USA`);
    const url = `https://nominatim.openstreetmap.org/search?q=${q}&format=json&limit=1`;
    const res = await fetch(url, {
      headers: { "User-Agent": "GoldPanMasterOS/1.0 (internal admin; bradcad1@gmail.com)" },
      // No caching — always geocode fresh
      cache: "no-store",
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (Array.isArray(data) && data.length > 0) {
      return { lat: parseFloat(data[0].lat), lon: parseFloat(data[0].lon) };
    }
  } catch {
    // Geocoding failure is non-fatal
  }
  return null;
}

// ── Form-data helpers ─────────────────────────────────────────────────────────

function str(fd: FormData, key: string): string | null {
  const v = (fd.get(key) as string | null)?.trim() ?? "";
  return v || null;
}

function dateStr(fd: FormData, key: string): string | null {
  return str(fd, key);  // same — null if empty
}

function num(fd: FormData, key: string): number | null {
  const v = str(fd, key);
  if (!v) return null;
  const n = parseInt(v, 10);
  return isNaN(n) ? null : n;
}

function float_(fd: FormData, key: string): number | null {
  const v = str(fd, key);
  if (!v) return null;
  const n = parseFloat(v);
  return isNaN(n) ? null : n;
}

// Build a body object from form data, including only explicitly-set fields.
// Null values ARE included so they clear the DB column (PATCH uses exclude_unset=True).
function buildBody(fd: FormData, keys: string[]): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  for (const k of keys) {
    if (fd.has(k)) body[k] = str(fd, k);
  }
  return body;
}

// ── API helpers ───────────────────────────────────────────────────────────────

async function patchPartner(externalId: string, body: Record<string, unknown>) {
  const res = await fetch(
    `${API_URL}/admin/business-development/${encodeURIComponent(externalId)}`,
    { method: "PATCH", headers: hdrs(), body: JSON.stringify(body) },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "PATCH failed");
  }
}

async function postAction(externalId: string, body: Record<string, unknown>) {
  await fetch(
    `${API_URL}/admin/business-development/${encodeURIComponent(externalId)}/actions`,
    { method: "POST", headers: hdrs(), body: JSON.stringify(body) },
  );
}

function revalidate(externalId?: string) {
  revalidatePath("/admin/business-development");
  revalidatePath("/admin/business-development/map");
  if (externalId) revalidatePath(`/admin/business-development/${externalId}`);
}

// ── Create partner ────────────────────────────────────────────────────────────

export async function createPartner(formData: FormData) {
  const body: Record<string, unknown> = {
    partner_type:       str(formData, "partner_type"),
    name:               str(formData, "name"),
    contact_name:       str(formData, "contact_name"),
    contact_title:      str(formData, "contact_title"),
    status:             str(formData, "status") ?? "prospect",
    pipeline_stage:     str(formData, "pipeline_stage"),
    priority:           str(formData, "priority") ?? "medium",
    opportunity_score:  num(formData, "opportunity_score"),
    relationship_owner: str(formData, "relationship_owner"),
    source:             str(formData, "source"),
    deal_value:         str(formData, "deal_value"),
    email:              str(formData, "email"),
    phone:              str(formData, "phone"),
    instagram:          str(formData, "instagram"),
    website:            str(formData, "website"),
    address:            str(formData, "address"),
    city:               str(formData, "city"),
    state:              str(formData, "state"),
    latitude:           float_(formData, "latitude"),
    longitude:          float_(formData, "longitude"),
    first_contact_date: dateStr(formData, "first_contact_date"),
    last_contact_date:  dateStr(formData, "last_contact_date"),
    next_followup_date: dateStr(formData, "next_followup_date"),
    notes:              str(formData, "notes"),
    objections:         str(formData, "objections"),
    strategic_value:    str(formData, "strategic_value"),
    audience_fit:       str(formData, "audience_fit"),
    partnership_model:  str(formData, "partnership_model"),
    restaurant_id:      str(formData, "restaurant_id"),
  };

  // Auto-geocode if city+state provided and no manual coords
  const city  = body.city  as string | null;
  const state = body.state as string | null;
  if (city && state && !body.latitude && !body.longitude) {
    const coords = await geocode(city, state);
    if (coords) {
      body.latitude        = coords.lat;
      body.longitude       = coords.lon;
      body.geocode_source  = "nominatim";
      body.geocoded_at     = new Date().toISOString();
    }
  } else if (body.latitude && body.longitude) {
    body.geocode_source = "manual";
    body.geocoded_at    = new Date().toISOString();
  }

  // Strip nulls from create payload (optional fields don't need to be null)
  const cleanBody = Object.fromEntries(
    Object.entries(body).filter(([, v]) => v !== null && v !== undefined),
  );

  const res = await fetch(`${API_URL}/admin/business-development`, {
    method: "POST",
    headers: hdrs(),
    body: JSON.stringify(cleanBody),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Create failed");
  }

  const data = await res.json();
  const newId: string = data.partner?.external_id;
  revalidate(newId);
  redirect(`/admin/business-development/${newId}`);
}

// ── Update partner (full edit form) ──────────────────────────────────────────

export async function updatePartnerFull(externalId: string, formData: FormData) {
  const body: Record<string, unknown> = {
    name:               str(formData, "name"),
    contact_name:       str(formData, "contact_name"),
    contact_title:      str(formData, "contact_title"),
    status:             str(formData, "status"),
    pipeline_stage:     str(formData, "pipeline_stage"),
    priority:           str(formData, "priority"),
    opportunity_score:  num(formData, "opportunity_score"),
    relationship_owner: str(formData, "relationship_owner"),
    source:             str(formData, "source"),
    deal_value:         str(formData, "deal_value"),
    email:              str(formData, "email"),
    phone:              str(formData, "phone"),
    instagram:          str(formData, "instagram"),
    website:            str(formData, "website"),
    address:            str(formData, "address"),
    city:               str(formData, "city"),
    state:              str(formData, "state"),
    latitude:           float_(formData, "latitude"),
    longitude:          float_(formData, "longitude"),
    first_contact_date: dateStr(formData, "first_contact_date"),
    last_contact_date:  dateStr(formData, "last_contact_date"),
    next_followup_date: dateStr(formData, "next_followup_date"),
    notes:              str(formData, "notes"),
    objections:         str(formData, "objections"),
    strategic_value:    str(formData, "strategic_value"),
    audience_fit:       str(formData, "audience_fit"),
    partnership_model:  str(formData, "partnership_model"),
  };

  // Re-geocode if city/state changed and no manual coords
  const city  = body.city  as string | null;
  const state = body.state as string | null;
  const lat   = body.latitude  as number | null;
  const lon   = body.longitude as number | null;

  if (city && state && !lat && !lon) {
    const coords = await geocode(city, state);
    if (coords) {
      body.latitude       = coords.lat;
      body.longitude      = coords.lon;
      body.geocode_source = "nominatim";
      body.geocoded_at    = new Date().toISOString();
    }
  } else if (lat && lon) {
    body.geocode_source = "manual";
    body.geocoded_at    = new Date().toISOString();
  }

  await patchPartner(externalId, body);
  revalidate(externalId);
  redirect(`/admin/business-development/${externalId}`);
}

// ── Quick action panel mutations (existing, kept) ─────────────────────────────

export async function addPartnerNote(externalId: string, formData: FormData) {
  const content     = (formData.get("content")      as string | null) ?? "";
  const performedBy = (formData.get("performed_by") as string | null) ?? undefined;
  if (!content.trim()) return;
  await postAction(externalId, {
    action_type:  "note",
    content:      content.trim(),
    performed_by: performedBy || undefined,
  });
  revalidate(externalId);
}

export async function updatePartnerStatus(externalId: string, formData: FormData) {
  const newStatus   = (formData.get("new_status")   as string | null) ?? "";
  const oldStatus   = (formData.get("old_status")   as string | null) ?? "";
  const performedBy = (formData.get("performed_by") as string | null) ?? undefined;
  if (!newStatus) return;
  await patchPartner(externalId, { status: newStatus });
  await postAction(externalId, {
    action_type:  "status_change",
    content:      `Status: ${oldStatus} → ${newStatus}`,
    old_status:   oldStatus || undefined,
    new_status:   newStatus,
    performed_by: performedBy || undefined,
  });
  revalidate(externalId);
}

export async function setFollowUp(externalId: string, formData: FormData) {
  const date        = (formData.get("next_followup_date") as string | null) ?? "";
  const note        = (formData.get("note")               as string | null) ?? "";
  const performedBy = (formData.get("performed_by")       as string | null) ?? undefined;
  if (!date) return;
  await patchPartner(externalId, { next_followup_date: date });
  await postAction(externalId, {
    action_type:  "follow_up_set",
    content:      note.trim() || `Follow-up set for ${date}`,
    performed_by: performedBy || undefined,
  });
  revalidate(externalId);
}

export async function markContacted(externalId: string, formData: FormData) {
  const method      = (formData.get("method")       as string | null) ?? "contacted";
  const notes       = (formData.get("notes")        as string | null) ?? "";
  const performedBy = (formData.get("performed_by") as string | null) ?? undefined;
  const today       = new Date().toISOString().split("T")[0];
  await patchPartner(externalId, { last_contact_date: today });
  await postAction(externalId, {
    action_type:  method || "contacted",
    content:      notes.trim() || `Contacted on ${today}`,
    performed_by: performedBy || undefined,
  });
  revalidate(externalId);
}

export async function updateNotes(externalId: string, formData: FormData) {
  const notes      = (formData.get("notes")      as string | null) ?? "";
  const objections = (formData.get("objections") as string | null) ?? "";
  await patchPartner(externalId, {
    notes:      notes      || null,
    objections: objections || null,
  });
  revalidate(externalId);
}
