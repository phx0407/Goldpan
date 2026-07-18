// lib/api.ts — Server-side fetch functions for the GoldPan FastAPI backend.
// Called from Next.js Server Components only.
// ADMIN_API_KEY is a server-only env var — never put NEXT_PUBLIC_ on it.

import type {
  AIUsageReport,
  RestaurantListResponse,
  RestaurantDetailResponse,
  PartnerListResponse,
  PartnerDetailResponse,
  RestaurantLookupItem,
  RestaurantMapItem,
  IntakeQueueResponse,
  IntakePacketDetailResponse,
  IntakePacketRow,
  LifecycleResult,
} from "@/lib/types";

const API_URL = process.env.GOLDPAN_API_URL ?? "http://localhost:8000";
const ADMIN_KEY = process.env.ADMIN_API_KEY ?? "";

// Acting-user bridge (see api/deps.py get_acting_user docstring: "TEMPORARY
// bridge, technical debt"). Every DEC000001 write endpoint except /ingest
// requires an X-User-Id header resolving to an active operations.users row,
// so that claim/release/approve/return/reject/edit_payload/resubmit/archive
// can be attributed to a specific reviewer/specialist/admin. There is no
// per-user auth session in this admin tool yet, so — mirroring how
// ADMIN_API_KEY is a single shared secret for this single-operator tool —
// GOLDPAN_ACTING_USER_ID is a single configured operations.users.user_id
// sent on every call that needs one. Replace with real per-user identity
// once Supabase Auth sessions land on the admin API.
const ACTING_USER_ID = process.env.GOLDPAN_ACTING_USER_ID ?? "";

export class APIError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "APIError";
  }
}

export async function fetchAIUsageReport(): Promise<AIUsageReport> {
  if (!ADMIN_KEY) {
    throw new APIError(503, "ADMIN_API_KEY is not set in .env.local");
  }

  const res = await fetch(`${API_URL}/admin/ai-usage/report`, {
    headers: { "X-Admin-Key": ADMIN_KEY },
    // Revalidate every 30 s in production; disable cache in dev for live data
    next: { revalidate: 30 },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore JSON parse failure
    }
    throw new APIError(res.status, detail);
  }

  return res.json() as Promise<AIUsageReport>;
}

export async function fetchRestaurantList(): Promise<RestaurantListResponse> {
  if (!ADMIN_KEY) {
    throw new APIError(503, "ADMIN_API_KEY is not set in .env.local");
  }
  const res = await fetch(`${API_URL}/admin/restaurants`, {
    headers: { "X-Admin-Key": ADMIN_KEY },
    next: { revalidate: 60 },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { const b = await res.json(); detail = b.detail ?? detail; } catch {}
    throw new APIError(res.status, detail);
  }
  return res.json() as Promise<RestaurantListResponse>;
}

export async function fetchRestaurantDetail(externalId: string): Promise<RestaurantDetailResponse> {
  if (!ADMIN_KEY) {
    throw new APIError(503, "ADMIN_API_KEY is not set in .env.local");
  }
  const res = await fetch(`${API_URL}/admin/restaurants/${encodeURIComponent(externalId)}`, {
    headers: { "X-Admin-Key": ADMIN_KEY },
    next: { revalidate: 60 },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { const b = await res.json(); detail = b.detail ?? detail; } catch {}
    throw new APIError(res.status, detail);
  }
  return res.json() as Promise<RestaurantDetailResponse>;
}

export async function fetchPartnerList(): Promise<PartnerListResponse> {
  if (!ADMIN_KEY) {
    throw new APIError(503, "ADMIN_API_KEY is not set in .env.local");
  }
  const res = await fetch(`${API_URL}/admin/business-development`, {
    headers: { "X-Admin-Key": ADMIN_KEY },
    next: { revalidate: 0 },   // no cache — mutations need fresh data
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { const b = await res.json(); detail = b.detail ?? detail; } catch {}
    throw new APIError(res.status, detail);
  }
  return res.json() as Promise<PartnerListResponse>;
}

export async function fetchRestaurantsForLookup(): Promise<RestaurantLookupItem[]> {
  if (!ADMIN_KEY) {
    throw new APIError(503, "ADMIN_API_KEY is not set in .env.local");
  }
  const res = await fetch(`${API_URL}/admin/restaurants/lookup`, {
    headers: { "X-Admin-Key": ADMIN_KEY },
    next: { revalidate: 60 },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { const b = await res.json(); detail = b.detail ?? detail; } catch {}
    throw new APIError(res.status, detail);
  }
  return res.json() as Promise<RestaurantLookupItem[]>;
}

export async function fetchRestaurantsForMap(): Promise<RestaurantMapItem[]> {
  if (!ADMIN_KEY) {
    throw new APIError(503, "ADMIN_API_KEY is not set in .env.local");
  }
  const res = await fetch(`${API_URL}/admin/restaurants/map`, {
    headers: { "X-Admin-Key": ADMIN_KEY },
    next: { revalidate: 300 }, // 5-minute cache — map data changes infrequently
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { const b = await res.json(); detail = b.detail ?? detail; } catch {}
    throw new APIError(res.status, detail);
  }
  return res.json() as Promise<RestaurantMapItem[]>;
}

export async function fetchPartnerDetail(externalId: string): Promise<PartnerDetailResponse> {
  if (!ADMIN_KEY) {
    throw new APIError(503, "ADMIN_API_KEY is not set in .env.local");
  }
  const res = await fetch(
    `${API_URL}/admin/business-development/${encodeURIComponent(externalId)}`,
    {
      headers: { "X-Admin-Key": ADMIN_KEY },
      next: { revalidate: 0 },
    },
  );
  if (!res.ok) {
    let detail = res.statusText;
    try { const b = await res.json(); detail = b.detail ?? detail; } catch {}
    throw new APIError(res.status, detail);
  }
  return res.json() as Promise<PartnerDetailResponse>;
}

// ── Intake OS ─────────────────────────────────────────────────────────────────

export async function fetchIntakeQueue(statusFilter?: string): Promise<IntakeQueueResponse> {
  if (!ADMIN_KEY) throw new APIError(503, "ADMIN_API_KEY is not set in .env.local");
  const qs = statusFilter ? `?status_filter=${statusFilter}` : "";
  const res = await fetch(`${API_URL}/admin/intake${qs}`, {
    headers: { "X-Admin-Key": ADMIN_KEY },
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new APIError(res.status, err.detail ?? res.statusText);
  }
  return res.json() as Promise<IntakeQueueResponse>;
}

export async function fetchIntakePacket(packetId: string): Promise<IntakePacketDetailResponse> {
  if (!ADMIN_KEY) throw new APIError(503, "ADMIN_API_KEY is not set in .env.local");
  const res = await fetch(`${API_URL}/admin/intake/${packetId}`, {
    headers: { "X-Admin-Key": ADMIN_KEY },
    cache: "no-store",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new APIError(res.status, err.detail ?? res.statusText);
  }
  return res.json() as Promise<IntakePacketDetailResponse>;
}

// ── Lifecycle mutation (server action) ────────────────────────────────────────
// Called from Next.js Server Actions — runs server-side, safe to use ADMIN_API_KEY.

export async function performLifecycleAction(
  externalId: string,
  action: string,
  note?: string,
): Promise<LifecycleResult> {
  if (!ADMIN_KEY) throw new APIError(503, "ADMIN_API_KEY is not set in .env.local");
  const res = await fetch(`${API_URL}/admin/restaurants/${externalId}/lifecycle`, {
    method: "PATCH",
    headers: { "X-Admin-Key": ADMIN_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ action, note: note ?? null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new APIError(res.status, err.detail ?? res.statusText);
  }
  return res.json() as Promise<LifecycleResult>;
}

export async function submitIntakePacket(
  packetData: Record<string, unknown>,
  restaurantExternalId?: string,
): Promise<IntakePacketRow> {
  if (!ADMIN_KEY) throw new APIError(503, "ADMIN_API_KEY is not set in .env.local");
  const res = await fetch(`${API_URL}/admin/intake/submit`, {
    method: "POST",
    headers: { "X-Admin-Key": ADMIN_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({
      packet_data: packetData,
      restaurant_external_id: restaurantExternalId ?? null,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new APIError(res.status, err.detail ?? res.statusText);
  }
  return res.json() as Promise<IntakePacketRow>;
}

export type IntakeActionType =
  | "claim"
  | "release"
  | "approve"
  | "return"
  | "reject"
  | "edit_payload"
  | "resubmit"
  | "archive"
  | "ingest";

export interface IntakeActionPayload {
  reason?: string;
  reviewer_notes?: string;
  override_reason?: string;
  packet_data?: Record<string, unknown>;
}

// Every DEC000001 write endpoint except /ingest requires X-User-Id (see
// api/deps.py get_acting_user). Keep this set in sync with
// api/routers/intake.py's per-endpoint Depends(get_acting_user) usage.
const ACTIONS_REQUIRING_ACTOR = new Set<IntakeActionType>([
  "claim",
  "release",
  "approve",
  "return",
  "reject",
  "edit_payload",
  "resubmit",
  "archive",
]);

export async function performIntakeAction(
  packetId: string,
  action: IntakeActionType,
  payload?: IntakeActionPayload,
): Promise<IntakePacketRow> {
  if (!ADMIN_KEY) throw new APIError(503, "ADMIN_API_KEY is not set in .env.local");

  const headers: Record<string, string> = {
    "X-Admin-Key": ADMIN_KEY,
    "Content-Type": "application/json",
  };
  if (ACTIONS_REQUIRING_ACTOR.has(action)) {
    if (!ACTING_USER_ID) {
      throw new APIError(
        503,
        "GOLDPAN_ACTING_USER_ID is not set in .env.local — required to attribute " +
          "this action to a reviewer/specialist/admin (see api/deps.py get_acting_user).",
      );
    }
    headers["X-User-Id"] = ACTING_USER_ID;
  }

  const res = await fetch(`${API_URL}/admin/intake/${packetId}/${action}`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload ?? {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new APIError(res.status, err.detail ?? res.statusText);
  }
  return res.json() as Promise<IntakePacketRow>;
}
