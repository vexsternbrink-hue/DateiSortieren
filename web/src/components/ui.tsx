import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import type { ActionKind, ActionStatus } from "@/lib/types";

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function StatCard({ label, value, hint, icon: Icon, tone = "indigo" }: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon: LucideIcon;
  tone?: "indigo" | "emerald" | "amber" | "rose" | "sky";
}) {
  const tones = {
    indigo: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-300",
    emerald: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-300",
    amber: "bg-amber-500/10 text-amber-600 dark:text-amber-300",
    rose: "bg-rose-500/10 text-rose-600 dark:text-rose-300",
    sky: "bg-sky-500/10 text-sky-600 dark:text-sky-300",
  };
  return (
    <div className="card p-5">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted">{label}</span>
        <span className={`rounded-lg p-2 ${tones[tone]}`}>
          <Icon className="size-4" />
        </span>
      </div>
      <div className="mt-3 text-3xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center justify-center px-6 py-14 text-center">
      <span className="mb-4 rounded-2xl bg-surface-muted p-4 text-muted">
        <Icon className="size-7" />
      </span>
      <h3 className="font-medium">{title}</h3>
      {children && <div className="mt-2 max-w-md text-sm text-muted">{children}</div>}
    </div>
  );
}

const STATUS: Record<ActionStatus, { label: string; cls: string }> = {
  proposed: { label: "Vorschlag", cls: "bg-amber-500/15 text-amber-700 dark:text-amber-300" },
  approved: { label: "Freigegeben", cls: "bg-sky-500/15 text-sky-700 dark:text-sky-300" },
  rejected: { label: "Abgelehnt", cls: "bg-slate-500/15 text-slate-600 dark:text-slate-300" },
  applied: { label: "Ausgeführt", cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
  skipped: { label: "Übersprungen", cls: "bg-slate-500/15 text-slate-600 dark:text-slate-300" },
  failed: { label: "Fehler", cls: "bg-rose-500/15 text-rose-700 dark:text-rose-300" },
  undo_requested: { label: "Undo angefordert", cls: "bg-violet-500/15 text-violet-700 dark:text-violet-300" },
  undone: { label: "Rückgängig", cls: "bg-violet-500/15 text-violet-700 dark:text-violet-300" },
};

export function StatusBadge({ status }: { status: ActionStatus }) {
  const s = STATUS[status] ?? STATUS.proposed;
  return <span className={`badge ${s.cls}`}>{s.label}</span>;
}

const KIND: Record<ActionKind, { label: string; cls: string }> = {
  move: { label: "Sortieren", cls: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300" },
  delete: { label: "Löschen", cls: "bg-rose-500/15 text-rose-700 dark:text-rose-300" },
  compress: { label: "Komprimieren", cls: "bg-teal-500/15 text-teal-700 dark:text-teal-300" },
};

export function KindBadge({ kind }: { kind: ActionKind }) {
  const k = KIND[kind];
  return <span className={`badge ${k.cls}`}>{k.label}</span>;
}

export function ConfidenceBar({ value }: { value: number | null }) {
  const pct = Math.round((value ?? 0) * 100);
  const color = pct >= 85 ? "bg-emerald-500" : pct >= 60 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="flex items-center gap-2" title={`KI-Sicherheit ${pct}%`}>
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-surface-muted">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-muted">{pct}%</span>
    </div>
  );
}
