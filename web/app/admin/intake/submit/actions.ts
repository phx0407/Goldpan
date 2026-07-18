"use server";
// app/admin/intake/submit/actions.ts — server action for packet submission.
// Kept separate so the submit page can be a client component.

import { redirect } from "next/navigation";
import { submitIntakePacket, APIError } from "@/lib/api";

export async function submitPacketAction(
  packetData: Record<string, unknown>,
  externalId?: string,
): Promise<{ error: string }> {
  let row;
  try {
    row = await submitIntakePacket(packetData, externalId);
  } catch (err: unknown) {
    // Re-throw Next.js redirect signals
    if (
      err != null &&
      typeof err === "object" &&
      "digest" in err &&
      typeof (err as { digest: unknown }).digest === "string" &&
      (err as { digest: string }).digest.startsWith("NEXT_REDIRECT")
    ) {
      throw err;
    }
    const msg =
      err instanceof APIError
        ? `${err.status} — ${err.detail}`
        : err instanceof Error
        ? err.message
        : "Unknown error";
    return { error: msg };
  }
  redirect(`/admin/intake/${row.packet_id}`);
}
