"use client";

// app/admin/error.tsx
// Error boundary for the admin segment. Catches runtime errors in any admin page.
// Must be a Client Component.

import { useEffect } from "react";

export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[admin error]", error);
  }, [error]);

  return (
    <div className="flex flex-col gap-4 p-6 max-w-lg">
      <div className="rounded-lg border border-red-800 bg-red-950/40 p-5">
        <p className="text-sm font-medium text-red-400">Page error</p>
        <p className="mt-1 font-mono text-xs text-red-500 break-all">
          {error?.message ?? "An unexpected error occurred."}
        </p>
        {error?.digest && (
          <p className="mt-1 font-mono text-xs text-stone-600">
            digest: {error.digest}
          </p>
        )}
      </div>
      <button
        onClick={reset}
        className="self-start rounded bg-stone-800 hover:bg-stone-700 px-3 py-1.5 text-xs text-stone-300 transition-colors"
      >
        Try again
      </button>
    </div>
  );
}
