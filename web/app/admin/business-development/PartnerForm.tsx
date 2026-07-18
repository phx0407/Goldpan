"use client";

// PartnerForm.tsx — Create and edit form for BD partners.
// Used by /new and /[id]/edit pages.
// formAction is a bound server action passed in by the parent server page.

import { useTransition, useState, useEffect } from "react";
import type { PartnerRow, RestaurantLookupItem } from "@/lib/types";

// ── Constants ─────────────────────────────────────────────────────────────────

const PARTNER_TYPES = [
  { value: "restaurant",             label: "Restaurant" },
  { value: "dietitian",              label: "Dietitian" },
  { value: "nutrition_clinic",       label: "Nutrition Clinic" },
  { value: "gym",                    label: "Gym" },
  { value: "corporate_wellness",     label: "Corporate Wellness" },
  { value: "employer",               label: "Employer" },
  { value: "healthcare_partner",     label: "Healthcare Partner" },
  { value: "university",             label: "University" },
  { value: "food_brand",             label: "Food Brand" },
  { value: "investor_grant",         label: "Investor / Grant" },
  { value: "community_organization", label: "Community Organization" },
  { value: "media",                  label: "Media" },
  { value: "government",             label: "Government" },
  { value: "other",                  label: "Other" },
];

const STATUSES = [
  { value: "prospect",    label: "Prospect" },
  { value: "outreach",    label: "Outreach" },
  { value: "engaged",     label: "Engaged" },
  { value: "negotiating", label: "Negotiating" },
  { value: "active",      label: "Active" },
  { value: "paused",      label: "Paused" },
  { value: "declined",    label: "Declined" },
  { value: "churned",     label: "Churned" },
];

const PRIORITIES = [
  { value: "high",   label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low",    label: "Low" },
];

const US_STATES = [
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
  "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
  "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
  "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
  "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC",
];

// ── Field components ──────────────────────────────────────────────────────────

function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label className="block text-xs text-stone-400 mb-1">
      {children}
      {required && <span className="text-red-400 ml-0.5">*</span>}
    </label>
  );
}

function Input({
  name, defaultValue, value, onChange, type = "text", placeholder, required, step,
}: {
  name: string;
  defaultValue?: string | number | null;
  value?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  type?: string;
  placeholder?: string;
  required?: boolean;
  step?: string;
}) {
  const controlled = value !== undefined;
  return (
    <input
      name={name}
      type={type}
      step={step}
      {...(controlled
        ? { value, onChange: onChange ?? (() => {}) }
        : { defaultValue: defaultValue ?? "" })}
      placeholder={placeholder}
      required={required}
      className="w-full rounded bg-stone-800 border border-stone-700 px-2.5 py-1.5 text-sm text-stone-200 placeholder-stone-600 focus:outline-none focus:border-amber-600 focus:ring-1 focus:ring-amber-600/30"
    />
  );
}

function Select({
  name, defaultValue, value, onChange, children, required,
}: {
  name: string;
  defaultValue?: string | null;
  value?: string;
  onChange?: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  children: React.ReactNode;
  required?: boolean;
}) {
  const controlled = value !== undefined;
  return (
    <select
      name={name}
      {...(controlled
        ? { value, onChange: onChange ?? (() => {}) }
        : { defaultValue: defaultValue ?? "" })}
      required={required}
      className="w-full rounded bg-stone-800 border border-stone-700 px-2.5 py-1.5 text-sm text-stone-200 focus:outline-none focus:border-amber-600 focus:ring-1 focus:ring-amber-600/30"
    >
      {children}
    </select>
  );
}

function Textarea({
  name, defaultValue, rows = 3, placeholder,
}: {
  name: string;
  defaultValue?: string | null;
  rows?: number;
  placeholder?: string;
}) {
  return (
    <textarea
      name={name}
      defaultValue={defaultValue ?? ""}
      rows={rows}
      placeholder={placeholder}
      className="w-full rounded bg-stone-800 border border-stone-700 px-2.5 py-1.5 text-sm text-stone-200 placeholder-stone-600 focus:outline-none focus:border-amber-600 focus:ring-1 focus:ring-amber-600/30 resize-y"
    />
  );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-medium uppercase tracking-widest text-stone-500 mb-3 pt-2 border-t border-stone-800 first:border-0 first:pt-0">
      {children}
    </p>
  );
}

function Field({ label, children, required }: { label: string; children: React.ReactNode; required?: boolean }) {
  return (
    <div>
      <Label required={required}>{label}</Label>
      {children}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface PartnerFormProps {
  formAction: (formData: FormData) => Promise<void>;
  mode: "create" | "edit";
  initial?: PartnerRow;
  restaurants: RestaurantLookupItem[];
}

export function PartnerForm({ formAction, mode, initial: p, restaurants }: PartnerFormProps) {
  const [pending, startTransition] = useTransition();

  // Auto-fill flag: true after a restaurant is selected
  const [autoFilled, setAutoFilled] = useState(false);
  // True when the linked restaurant has no street address in Restaurant Identity.
  // In that case we do not auto-fill the address field — address must come from
  // a trusted source (official site, Google Place ID, restaurant submission,
  // verified manual backfill). See Blueprint §5g.
  const [restaurantMissingAddress, setRestaurantMissingAddress] = useState(false);

  // Controlled state for auto-fillable fields
  const [ctrlName,    setCtrlName]    = useState(p?.name    ?? "");
  const [ctrlAddress, setCtrlAddress] = useState(p?.address ?? "");
  const [ctrlCity,    setCtrlCity]    = useState(p?.city    ?? "");
  const [ctrlState,   setCtrlState]   = useState(p?.state   ?? "");
  const [ctrlWebsite, setCtrlWebsite] = useState(p?.website ?? "");

  function handleRestaurantChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const selectedId = e.target.value;
    if (!selectedId) {
      setAutoFilled(false);
      setRestaurantMissingAddress(false);
      // Restore original values
      setCtrlName(p?.name    ?? "");
      setCtrlAddress(p?.address ?? "");
      setCtrlCity(p?.city    ?? "");
      setCtrlState(p?.state  ?? "");
      setCtrlWebsite(p?.website ?? "");
      return;
    }
    const r = restaurants.find(r => r.restaurant_id === selectedId);
    if (!r) return;
    setAutoFilled(true);
    // Address: only auto-fill if the restaurant identity has a verified street address.
    // Do NOT invent or geocode from city-level data.
    const hasAddress = Boolean(r.address?.trim());
    setRestaurantMissingAddress(!hasAddress);
    setCtrlName(r.name               ?? "");
    setCtrlAddress(hasAddress ? (r.address ?? "") : "");
    setCtrlCity(r.city               ?? "");
    setCtrlState(r.state             ?? "");
    setCtrlWebsite(r.official_website ?? "");
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    startTransition(async () => {
      await formAction(fd);
    });
  }

  const isRestaurant = p?.partner_type === "restaurant";

  return (
    <form onSubmit={handleSubmit} className="space-y-5">

      {/* ── Basics ─────────────────────────────────────────────────────────── */}
      <SectionHeader>Basics</SectionHeader>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Partner type" required>
          <Select name="partner_type" defaultValue={p?.partner_type ?? "restaurant"} required>
            <option value="">Select type…</option>
            {PARTNER_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </Select>
        </Field>

        <Field label="Name" required>
          <Input name="name" value={ctrlName} onChange={e => setCtrlName(e.target.value)} placeholder="e.g. True Food Kitchen" required />
        </Field>

        <Field label="Status">
          <Select name="status" defaultValue={p?.status ?? "prospect"}>
            {STATUSES.map(s => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </Select>
        </Field>

        <Field label="Priority">
          <Select name="priority" defaultValue={p?.priority ?? "medium"}>
            {PRIORITIES.map(pr => (
              <option key={pr.value} value={pr.value}>{pr.label}</option>
            ))}
          </Select>
        </Field>

        <Field label="Pipeline stage">
          <Input name="pipeline_stage" defaultValue={p?.pipeline_stage} placeholder="e.g. Initial outreach" />
        </Field>

        <Field label="Opportunity score (0–10)">
          <Input name="opportunity_score" type="number" step="1" defaultValue={p?.opportunity_score ?? ""} placeholder="0–10" />
        </Field>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Relationship owner">
          <Input name="relationship_owner" defaultValue={p?.relationship_owner} placeholder="e.g. Brad" />
        </Field>

        <Field label="Source">
          <Input name="source" defaultValue={p?.source} placeholder="e.g. canvasser_discovery" />
        </Field>

        <Field label="Deal value">
          <Input name="deal_value" defaultValue={p?.deal_value} placeholder="e.g. $500/mo or TBD" />
        </Field>
      </div>

      {/* ── Contact ────────────────────────────────────────────────────────── */}
      <SectionHeader>Contact</SectionHeader>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Contact name">
          <Input name="contact_name" defaultValue={p?.contact_name} placeholder="Full name" />
        </Field>

        <Field label="Contact title">
          <Input name="contact_title" defaultValue={p?.contact_title} placeholder="e.g. Owner, Manager" />
        </Field>

        <Field label="Email">
          <Input name="email" type="email" defaultValue={p?.email} placeholder="email@example.com" />
        </Field>

        <Field label="Phone">
          <Input name="phone" defaultValue={p?.phone} placeholder="(555) 000-0000" />
        </Field>

        <Field label="Instagram">
          <Input name="instagram" defaultValue={p?.instagram} placeholder="@handle" />
        </Field>

        <Field label="Website">
          <Input name="website" type="url" value={ctrlWebsite} onChange={e => setCtrlWebsite(e.target.value)} placeholder="https://…" />
        </Field>
      </div>

      {/* ── Location ───────────────────────────────────────────────────────── */}
      <SectionHeader>Location</SectionHeader>

      <Field label="Address">
        <Input name="address" value={ctrlAddress} onChange={e => setCtrlAddress(e.target.value)} placeholder="Street address" />
        {restaurantMissingAddress && (
          <p className="mt-1.5 text-xs text-amber-500">
            Street address missing from Restaurant Identity. Enter it here only if you have a trusted source (official website, verified listing). Do not guess or infer from city.
          </p>
        )}
      </Field>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <div className="col-span-2 sm:col-span-1">
          <Field label="City">
            <Input name="city" value={ctrlCity} onChange={e => setCtrlCity(e.target.value)} placeholder="Birmingham" />
          </Field>
        </div>

        <Field label="State">
          <Select name="state" value={ctrlState} onChange={e => setCtrlState(e.target.value)}>
            <option value="">—</option>
            {US_STATES.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </Select>
        </Field>

        <Field label="Latitude">
          <Input name="latitude" type="number" step="any" defaultValue={p?.latitude ?? ""} placeholder="Auto-geocoded" />
        </Field>

        <Field label="Longitude">
          <Input name="longitude" type="number" step="any" defaultValue={p?.longitude ?? ""} placeholder="Auto-geocoded" />
        </Field>
      </div>

      {p?.geocode_source && (
        <p className="text-xs text-stone-600 -mt-2">
          Coordinates via <span className="text-stone-500">{p.geocode_source}</span>
          {p.geocoded_at ? ` · ${p.geocoded_at.slice(0, 10)}` : ""}.
          Clear lat/lng fields to re-geocode from city + state.
        </p>
      )}

      {!p?.geocode_source && (
        <p className="text-xs text-stone-600 -mt-2">
          Leave lat/lng blank — coordinates will be auto-geocoded from city + state on save.
        </p>
      )}

      {/* ── Dates ──────────────────────────────────────────────────────────── */}
      <SectionHeader>Dates</SectionHeader>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Field label="First contact date">
          <Input name="first_contact_date" type="date" defaultValue={p?.first_contact_date ?? ""} />
        </Field>

        <Field label="Last contact date">
          <Input name="last_contact_date" type="date" defaultValue={p?.last_contact_date ?? ""} />
        </Field>

        <Field label="Next follow-up date">
          <Input name="next_followup_date" type="date" defaultValue={p?.next_followup_date ?? ""} />
        </Field>
      </div>

      {/* ── Restaurant link (restaurant-type only) ─────────────────────────── */}
      {(isRestaurant || mode === "create") && (
        <>
          <SectionHeader>Restaurant Link</SectionHeader>
          <p className="text-xs text-stone-600 -mt-2 mb-2">
            Link this partner to an evidence.restaurants record to enable restaurant intelligence enrichment.
            Only applies when partner type is Restaurant.
          </p>
          <Field label="Linked restaurant">
            <select
              name="restaurant_id"
              defaultValue={p?.restaurant_id ?? ""}
              onChange={handleRestaurantChange}
              className="w-full rounded bg-stone-800 border border-stone-700 px-2.5 py-1.5 text-sm text-stone-200 focus:outline-none focus:border-amber-600 focus:ring-1 focus:ring-amber-600/30"
            >
              <option value="">— None —</option>
              {restaurants.map(r => (
                <option key={r.restaurant_id} value={r.restaurant_id}>
                  {r.external_id} · {r.name}{r.location ? ` (${r.location})` : ""}
                </option>
              ))}
            </select>
          </Field>
          {autoFilled && (
            <p className="text-xs text-amber-600 mt-1">
              ↑ Name, address, city, state, and website auto-filled from restaurant record. You can edit them above.
            </p>
          )}
        </>
      )}

      {/* ── Strategic info (non-restaurant) ───────────────────────────────── */}
      {(!isRestaurant || mode === "create") && (
        <>
          <SectionHeader>Strategic Info</SectionHeader>
          <p className="text-xs text-stone-600 -mt-2 mb-2">
            Applicable to non-restaurant partner types.
          </p>
          <div className="space-y-3">
            <Field label="Strategic value">
              <Textarea name="strategic_value" defaultValue={p?.strategic_value} rows={2} placeholder="Why does this partnership matter strategically?" />
            </Field>

            <Field label="Audience fit">
              <Textarea name="audience_fit" defaultValue={p?.audience_fit} rows={2} placeholder="How does their audience align with GoldPan users?" />
            </Field>

            <Field label="Partnership model">
              <Textarea name="partnership_model" defaultValue={p?.partnership_model} rows={2} placeholder="e.g. referral, co-marketing, data sharing, sponsorship" />
            </Field>
          </div>
        </>
      )}

      {/* ── Notes ──────────────────────────────────────────────────────────── */}
      <SectionHeader>Notes</SectionHeader>

      <Field label="Notes">
        <Textarea name="notes" defaultValue={p?.notes} rows={4} placeholder="Relationship notes, context, background…" />
      </Field>

      <Field label="Objections">
        <Textarea name="objections" defaultValue={p?.objections} rows={3} placeholder="Known objections, hesitations, blockers…" />
      </Field>

      {/* ── Submit ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 pt-2 border-t border-stone-800">
        <button
          type="submit"
          disabled={pending}
          className="rounded bg-amber-600 hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white transition-colors"
        >
          {pending
            ? (mode === "create" ? "Creating…" : "Saving…")
            : (mode === "create" ? "Create partner" : "Save changes")}
        </button>

        <a
          href={mode === "edit" && p ? `/admin/business-development/${p.external_id}` : "/admin/business-development"}
          className="text-sm text-stone-500 hover:text-stone-300 transition-colors"
        >
          Cancel
        </a>

        {mode === "edit" && (
          <span className="ml-auto text-xs text-stone-700 font-mono">{p?.external_id}</span>
        )}
      </div>
    </form>
  );
}
