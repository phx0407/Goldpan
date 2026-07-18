"use client";

// app/global-error.tsx
// Required by Next.js App Router — catches errors that bubble to the root layout.
// Must be a Client Component.

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="bg-stone-950 text-stone-100 flex items-center justify-center min-h-screen">
        <div className="max-w-md text-center p-8">
          <p className="text-xs font-mono text-stone-500 mb-2">global error</p>
          <h1 className="text-lg font-semibold text-red-400 mb-2">
            Something went wrong
          </h1>
          <p className="text-sm text-stone-400 mb-6 font-mono break-all">
            {error?.message ?? "Unknown error"}
          </p>
          <button
            onClick={reset}
            className="rounded bg-stone-800 hover:bg-stone-700 px-4 py-2 text-sm text-stone-300 transition-colors"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
