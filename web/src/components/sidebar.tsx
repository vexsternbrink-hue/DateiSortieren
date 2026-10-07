"use client";

import {
  Activity,
  Bot,
  Copy,
  Eraser,
  Eye,
  History,
  LayoutDashboard,
  Menu,
  ScrollText,
  Settings,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

const NAV = [
  { href: "/dashboard", label: "Übersicht", icon: LayoutDashboard },
  { href: "/dashboard/preview", label: "Vorschau (Dry-Run)", icon: Eye, countKey: "proposed" },
  { href: "/dashboard/duplicates", label: "Duplikate", icon: Copy, countKey: "duplicates" },
  { href: "/dashboard/cleanup", label: "Aufräumen", icon: Eraser, countKey: "cleanup" },
  { href: "/dashboard/optimize", label: "Medien-Optimierung", icon: Zap, countKey: "compress" },
  { href: "/dashboard/history", label: "Verlauf & Undo", icon: History },
  { href: "/dashboard/rules", label: "KI-Regeln", icon: Sparkles },
  { href: "/dashboard/safelist", label: "Safe-List", icon: ShieldCheck },
  { href: "/dashboard/agents", label: "Agenten", icon: Bot },
  { href: "/dashboard/activity", label: "Aktivität", icon: ScrollText },
  { href: "/dashboard/settings", label: "Einstellungen", icon: Settings },
] as const;

export function Sidebar({ counts, footer }: { counts: Record<string, number>; footer: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const nav = (
    <nav className="flex flex-col gap-0.5">
      {NAV.map((item) => {
        const active = item.href === "/dashboard" ? pathname === item.href : pathname.startsWith(item.href);
        const count = "countKey" in item ? counts[item.countKey] : 0;
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setOpen(false)}
            className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
              active ? "bg-indigo-500/10 font-medium text-indigo-700 dark:text-indigo-300" : "text-muted hover:bg-surface-muted hover:text-foreground"
            }`}
          >
            <Icon className="size-4" />
            <span className="flex-1">{item.label}</span>
            {count > 0 && (
              <span className="rounded-full bg-amber-500/15 px-2 text-xs font-semibold text-amber-700 dark:text-amber-300">{count}</span>
            )}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <>
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-border bg-surface/90 px-4 py-3 backdrop-blur lg:hidden">
        <Brand />
        <button className="btn btn-sm" onClick={() => setOpen((v) => !v)} aria-label="Menü">
          <Menu className="size-4" />
        </button>
      </header>
      {open && (
        <div className="border-b border-border bg-surface p-3 lg:hidden">
          {nav}
          <div className="mt-3 border-t border-border pt-3">{footer}</div>
        </div>
      )}

      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-border bg-surface p-4 lg:flex">
        <div className="mb-6 px-2">
          <Brand />
        </div>
        <div className="flex-1 overflow-y-auto">{nav}</div>
        <div className="mt-4 border-t border-border pt-4">{footer}</div>
      </aside>
    </>
  );
}

export function Brand() {
  return (
    <Link href="/dashboard" className="flex items-center gap-2 font-semibold">
      <span className="grid size-8 place-items-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white">
        <Activity className="size-4" />
      </span>
      DateiSortieren
    </Link>
  );
}
