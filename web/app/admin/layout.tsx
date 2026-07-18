import Link from "next/link";
import type { ReactNode } from "react";

// ── Nav structure — mirrors Master OS Blueprint section 3 ─────────────────────

const NAV_GROUPS = [
  {
    label: "Leadership",
    items: [
      { href: "/admin/executive", label: "Executive" },
    ],
  },
  {
    label: "Core Operations",
    items: [
      { href: "/admin/restaurants",         label: "Restaurants" },
      { href: "/admin/business-development", label: "Business Dev" },
    ],
  },
  {
    label: "Evidence Pipeline",
    items: [
      { href: "/admin/intake",      label: "Intake" },
      { href: "/admin/knowledge",   label: "Knowledge" },
      { href: "/admin/governance",  label: "Governance" },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/admin/analytics",  label: "Analytics" },
      { href: "/admin/ai-usage",   label: "AI Usage" },
    ],
  },
  {
    label: "Infrastructure",
    items: [
      { href: "/admin/operations", label: "Operations" },
      { href: "/admin/finance",    label: "Finance" },
    ],
  },
];

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <header className="flex h-12 shrink-0 items-center gap-3 border-b border-stone-800 bg-stone-900 px-5">
        <Link href="/admin/executive" className="font-semibold tracking-tight text-amber-400 hover:text-amber-300 transition-colors">
          GoldPan™
        </Link>
        <span className="text-stone-300 text-sm">Master OS</span>
        <span className="ml-auto text-xs text-stone-500">internal</span>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="flex w-48 shrink-0 flex-col gap-4 border-r border-stone-800 bg-stone-900 overflow-y-auto p-3">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-widest text-stone-500">
                {group.label}
              </p>
              {group.items.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="block rounded px-3 py-1.5 text-sm text-stone-300 hover:bg-stone-800 hover:text-stone-100 transition-colors"
                >
                  {item.label}
                </Link>
              ))}
            </div>
          ))}
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
