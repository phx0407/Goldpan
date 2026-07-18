// app/admin/business-development/[id]/ActionPanel.tsx
// Client component — interactive action forms for a single partner.
// Server Actions live in ../actions.ts (server-only).

"use client";

import { useTransition, useState } from "react";
import {
  addPartnerNote,
  updatePartnerStatus,
  setFollowUp,
  markContacted,
} from "../actions";

const STATUSES = [
  "prospect", "outreach", "engaged", "negotiating",
  "active", "paused", "declined", "churned",
];

const CONTACT_METHODS = [
  { value: "call",          label: "Phone call" },
  { value: "email_sent",    label: "Email sent" },
  { value: "meeting",       label: "Meeting" },
  { value: "dm_instagram",  label: "Instagram DM" },
  { value: "contacted",     label: "Other" },
];

type Tab = "note" | "status" | "followup" | "contacted";

export function ActionPanel({
  externalId,
  currentStatus,
}: {
  externalId:    string;
  currentStatus: string;
}) {
  const [activeTab, setActiveTab] = useState<Tab>("note");
  const [pending, startTransition] = useTransition();
  const [done, setDone] = useState<string | null>(null);

  function wrap(fn: (fd: FormData) => Promise<void>) {
    return async (fd: FormData) => {
      startTransition(async () => {
        await fn(fd);
        setDone(activeTab);
        setTimeout(() => setDone(null), 2500);
      });
    };
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "note",      label: "Add note" },
    { id: "status",    label: "Update status" },
    { id: "followup",  label: "Set follow-up" },
    { id: "contacted", label: "Mark contacted" },
  ];

  return (
    <div className="rounded-lg border border-stone-700 bg-stone-900">
      {/* Tab bar */}
      <div className="flex border-b border-stone-700">
        {tabs.map(t => (
          <button
            key={t.id}
            type="button"
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2.5 text-xs font-medium transition-colors ${
              activeTab === t.id
                ? "text-amber-400 border-b-2 border-amber-400 -mb-px"
                : "text-stone-500 hover:text-stone-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="p-4">
        {done && (
          <p className="mb-3 text-xs text-emerald-400">✓ Saved</p>
        )}

        {/* Add note */}
        {activeTab === "note" && (
          <form action={wrap(addPartnerNote.bind(null, externalId))}>
            <textarea
              name="content"
              rows={3}
              placeholder="Add a note…"
              className="w-full rounded border border-stone-700 bg-stone-800 px-3 py-2 text-sm text-stone-200 placeholder:text-stone-600 focus:outline-none focus:border-amber-500/60 resize-none"
              required
            />
            <div className="mt-2 flex items-center gap-2">
              <input
                name="performed_by"
                placeholder="Your name (optional)"
                className="flex-1 rounded border border-stone-700 bg-stone-800 px-3 py-1.5 text-xs text-stone-300 placeholder:text-stone-600 focus:outline-none focus:border-amber-500/60"
              />
              <SubmitBtn pending={pending} label="Save note" />
            </div>
          </form>
        )}

        {/* Update status */}
        {activeTab === "status" && (
          <form action={wrap(updatePartnerStatus.bind(null, externalId))}>
            <input type="hidden" name="old_status" value={currentStatus} />
            <div className="flex items-center gap-2">
              <select
                name="new_status"
                defaultValue={currentStatus}
                className="flex-1 rounded border border-stone-700 bg-stone-800 px-3 py-1.5 text-sm text-stone-200 focus:outline-none focus:border-amber-500/60"
              >
                {STATUSES.map(s => (
                  <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                ))}
              </select>
              <input
                name="performed_by"
                placeholder="Your name (optional)"
                className="flex-1 rounded border border-stone-700 bg-stone-800 px-3 py-1.5 text-xs text-stone-300 placeholder:text-stone-600 focus:outline-none focus:border-amber-500/60"
              />
              <SubmitBtn pending={pending} label="Update" />
            </div>
          </form>
        )}

        {/* Set follow-up */}
        {activeTab === "followup" && (
          <form action={wrap(setFollowUp.bind(null, externalId))}>
            <div className="flex items-center gap-2 mb-2">
              <input
                name="next_followup_date"
                type="date"
                required
                className="rounded border border-stone-700 bg-stone-800 px-3 py-1.5 text-sm text-stone-200 focus:outline-none focus:border-amber-500/60"
              />
              <input
                name="performed_by"
                placeholder="Your name (optional)"
                className="flex-1 rounded border border-stone-700 bg-stone-800 px-3 py-1.5 text-xs text-stone-300 placeholder:text-stone-600 focus:outline-none focus:border-amber-500/60"
              />
              <SubmitBtn pending={pending} label="Set" />
            </div>
            <input
              name="note"
              placeholder="Follow-up note (optional)"
              className="w-full rounded border border-stone-700 bg-stone-800 px-3 py-1.5 text-xs text-stone-300 placeholder:text-stone-600 focus:outline-none focus:border-amber-500/60"
            />
          </form>
        )}

        {/* Mark contacted */}
        {activeTab === "contacted" && (
          <form action={wrap(markContacted.bind(null, externalId))}>
            <div className="flex items-center gap-2 mb-2">
              <select
                name="method"
                className="rounded border border-stone-700 bg-stone-800 px-3 py-1.5 text-sm text-stone-200 focus:outline-none focus:border-amber-500/60"
              >
                {CONTACT_METHODS.map(m => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
              <input
                name="performed_by"
                placeholder="Your name (optional)"
                className="flex-1 rounded border border-stone-700 bg-stone-800 px-3 py-1.5 text-xs text-stone-300 placeholder:text-stone-600 focus:outline-none focus:border-amber-500/60"
              />
            </div>
            <div className="flex gap-2 mt-2">
              <textarea
                name="notes"
                rows={2}
                placeholder="Contact notes (optional)…"
                className="flex-1 rounded border border-stone-700 bg-stone-800 px-3 py-2 text-sm text-stone-200 placeholder:text-stone-600 focus:outline-none focus:border-amber-500/60 resize-none"
              />
              <div className="self-end">
                <SubmitBtn pending={pending} label="Log" />
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

function SubmitBtn({ pending, label }: { pending: boolean; label: string }) {
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
    >
      {pending ? "Saving…" : label}
    </button>
  );
}
