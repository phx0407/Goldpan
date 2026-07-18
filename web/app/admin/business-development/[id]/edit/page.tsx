// app/admin/business-development/[id]/edit/page.tsx
// Edit an existing BD partner.

import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchPartnerDetail, fetchRestaurantsForLookup, APIError } from "@/lib/api";
import { updatePartnerFull } from "../../actions";
import { PartnerForm } from "../../PartnerForm";

export const dynamic = "force-dynamic";

export default async function EditPartnerPage({
  params,
}: {
  params: { id: string };
}) {
  let data: Awaited<ReturnType<typeof fetchPartnerDetail>> | null = null;
  let restaurants: Awaited<ReturnType<typeof fetchRestaurantsForLookup>> = [];
  let fetchError: string | null = null;

  try {
    [data, restaurants] = await Promise.all([
      fetchPartnerDetail(params.id),
      fetchRestaurantsForLookup().catch(() => []),
    ]);
  } catch (err) {
    if (err instanceof APIError && err.status === 404) notFound();
    fetchError =
      err instanceof APIError
        ? `${err.status} — ${err.detail}`
        : err instanceof Error ? err.message : "Unknown error.";
  }

  if (fetchError) {
    return (
      <div className="flex flex-col gap-3 max-w-2xl">
        <Link href="/admin/business-development" className="text-xs text-stone-500 hover:text-stone-300">
          ← Business Development
        </Link>
        <div className="rounded-lg border border-red-800 bg-red-950/40 p-5">
          <p className="text-sm font-medium text-red-400">Could not load partner</p>
          <p className="mt-1 font-mono text-xs text-red-500">{fetchError}</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { partner } = data;

  // Bind externalId into the server action — the form receives a single-arg action
  const updateAction = updatePartnerFull.bind(null, partner.external_id);

  return (
    <div className="max-w-2xl space-y-6">
      <Link
        href={`/admin/business-development/${partner.external_id}`}
        className="text-xs text-stone-500 hover:text-stone-300 transition-colors"
      >
        ← {partner.name}
      </Link>

      <div>
        <div className="flex items-center gap-2 mb-1">
          <span className="font-mono text-xs text-stone-600">{partner.external_id}</span>
        </div>
        <h1 className="text-xl font-semibold text-stone-100">Edit Partner</h1>
        <p className="text-sm text-stone-500 mt-0.5">{partner.name}</p>
      </div>

      <div className="rounded-lg border border-stone-700 bg-stone-900 p-5">
        <PartnerForm
          formAction={updateAction}
          mode="edit"
          initial={partner}
          restaurants={restaurants}
        />
      </div>
    </div>
  );
}
