// app/admin/business-development/new/page.tsx
// Create a new BD partner.

import Link from "next/link";
import { fetchRestaurantsForLookup } from "@/lib/api";
import { createPartner } from "../actions";
import { PartnerForm } from "../PartnerForm";

export const dynamic = "force-dynamic";

export default async function NewPartnerPage() {
  let restaurants: Awaited<ReturnType<typeof fetchRestaurantsForLookup>> = [];
  try {
    restaurants = await fetchRestaurantsForLookup();
  } catch {
    // Non-fatal — restaurant dropdown just won't populate
  }

  return (
    <div className="max-w-2xl space-y-6">
      <Link
        href="/admin/business-development"
        className="text-xs text-stone-500 hover:text-stone-300 transition-colors"
      >
        ← Business Development
      </Link>

      <div>
        <h1 className="text-xl font-semibold text-stone-100">New Partner</h1>
        <p className="text-sm text-stone-500 mt-0.5">
          Add a prospect, active partner, or any external relationship to the BD pipeline.
        </p>
      </div>

      <div className="rounded-lg border border-stone-700 bg-stone-900 p-5">
        <PartnerForm
          formAction={createPartner}
          mode="create"
          restaurants={restaurants}
        />
      </div>
    </div>
  );
}
