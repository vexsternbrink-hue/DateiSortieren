import { AlertTriangle, ArrowRight, Bot, CheckCircle2, Copy, Eye, HardDrive, Undo2 } from "lucide-react";
import Link from "next/link";
import { EmptyState, KindBadge, PageHeader, StatCard, StatusBadge } from "@/components/ui";
import { fetchCounts } from "@/lib/data";
import { fileName, formatBytes, formatDate, isOnline, timeAgo } from "@/lib/format";
import { requireUser } from "@/lib/supabase/server";
import type { ActionRow, AgentRow, LogRow } from "@/lib/types";

export const metadata = { title: "Übersicht" };

export default async function OverviewPage() {
  const { supabase, user } = await requireUser();
  const since = new Date(Date.now() - 30 * 86400 * 1000).toISOString();

  const [counts, agentsRes, recentRes, appliedRes, logsRes, failedRes] = await Promise.all([
    fetchCounts(),
    supabase.from("agents").select("*").eq("user_id", user.id).order("created_at"),
    supabase.from("actions").select("*").eq("user_id", user.id).order("updated_at", { ascending: false }).limit(8),
    supabase
      .from("actions")
      .select("kind, details")
      .eq("user_id", user.id)
      .eq("status", "applied")
      .gte("applied_at", since)
      .limit(5000),
    supabase.from("activity_logs").select("*").eq("user_id", user.id).order("created_at", { ascending: false }).limit(6),
    supabase.from("actions").select("id", { count: "exact", head: true }).eq("user_id", user.id).eq("status", "failed"),
  ]);

  const agents = (agentsRes.data ?? []) as AgentRow[];
  const recent = (recentRes.data ?? []) as ActionRow[];
  const applied = (appliedRes.data ?? []) as Pick<ActionRow, "kind" | "details">[];
  const logs = (logsRes.data ?? []) as LogRow[];

  const savedBytes = applied.reduce((sum, a) => {
    if (a.kind === "compress") return sum + Math.max(0, Number(a.details.size_before ?? 0) - Number(a.details.size_after ?? 0));
    if (a.kind === "delete") return sum + Number(a.details.size ?? 0);
    return sum;
  }, 0);
  const sorted = applied.filter((a) => a.kind === "move").length;

  return (
    <>
      <PageHeader
        title="Übersicht"
        description="Alles, was dein Agent gefunden, vorgeschlagen und erledigt hat."
        actions={
          counts.proposed > 0 ? (
            <Link href="/dashboard/preview" className="btn btn-primary">
              {counts.proposed} Vorschläge prüfen <ArrowRight className="size-4" />
            </Link>
          ) : null
        }
      />

      {agents.length === 0 && (
        <div className="card mb-6 flex flex-wrap items-center gap-4 border-indigo-500/30 bg-indigo-500/5 p-5">
          <Bot className="size-8 text-indigo-500" />
          <div className="flex-1">
            <h2 className="font-medium">Verbinde deinen ersten Computer</h2>
            <p className="text-sm text-muted">
              Der lokale Agent beobachtet deine Ordner und schickt Vorschläge hierher. Erzeuge ein Token und starte ihn in 3 Schritten.
            </p>
          </div>
          <Link href="/dashboard/agents" className="btn btn-primary">
            Agent einrichten
          </Link>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Offene Vorschläge" value={counts.proposed} hint="warten auf deine Freigabe" icon={Eye} tone="amber" />
        <StatCard label="Sortiert (30 Tage)" value={sorted} hint="verschoben & umbenannt" icon={CheckCircle2} tone="emerald" />
        <StatCard label="Speicher gespart" value={formatBytes(savedBytes)} hint="Duplikate, Cleanup, Komprimierung" icon={HardDrive} tone="sky" />
        <StatCard label="Duplikate gefunden" value={counts.duplicates} hint="offene Vorschläge" icon={Copy} tone="rose" />
      </div>

      {(failedRes.count ?? 0) > 0 && (
        <Link href="/dashboard/preview?status=failed" className="card mt-4 flex items-center gap-3 border-rose-500/30 bg-rose-500/5 p-4 text-sm">
          <AlertTriangle className="size-4 text-rose-600" />
          {failedRes.count} Aktion(en) sind fehlgeschlagen – ansehen
        </Link>
      )}

      <div className="mt-8 grid gap-6 lg:grid-cols-3">
        <section className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-medium">Letzte Aktionen</h2>
            <Link href="/dashboard/history" className="text-sm text-indigo-600 dark:text-indigo-300">
              Verlauf <ArrowRight className="inline size-3.5" />
            </Link>
          </div>
          {recent.length === 0 ? (
            <EmptyState icon={Undo2} title="Noch keine Aktionen">
              Sobald der Agent läuft, erscheinen hier Vorschläge und erledigte Aufgaben.
            </EmptyState>
          ) : (
            <ul className="card divide-y divide-border">
              {recent.map((a) => (
                <li key={a.id} className="flex items-center gap-3 px-4 py-3 text-sm">
                  <KindBadge kind={a.kind} />
                  <span className="min-w-0 flex-1 truncate" title={a.src_path}>
                    {fileName(a.src_path)}
                    {a.dst_path && <span className="text-muted"> → {fileName(a.dst_path)}</span>}
                  </span>
                  <StatusBadge status={a.status} />
                  <span className="hidden text-xs text-muted sm:inline">{timeAgo(a.updated_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="space-y-6">
          <div>
            <h2 className="mb-3 font-medium">Agenten</h2>
            <ul className="card divide-y divide-border">
              {agents.length === 0 && <li className="px-4 py-3 text-sm text-muted">Noch kein Agent verbunden.</li>}
              {agents.map((agent) => (
                <li key={agent.id} className="flex items-center gap-3 px-4 py-3 text-sm">
                  <span className={`size-2 rounded-full ${isOnline(agent.last_seen_at) ? "bg-emerald-500" : "bg-slate-400"}`} />
                  <span className="flex-1 truncate">{agent.name}</span>
                  <span className="text-xs text-muted">{timeAgo(agent.last_seen_at)}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h2 className="mb-3 font-medium">Aktivität</h2>
            <ul className="card divide-y divide-border">
              {logs.length === 0 && <li className="px-4 py-3 text-sm text-muted">Noch keine Einträge.</li>}
              {logs.map((log) => (
                <li key={log.id} className="px-4 py-3 text-sm">
                  <div className={log.level === "error" ? "text-rose-600" : ""}>{log.message}</div>
                  <div className="text-xs text-muted">{formatDate(log.created_at)}</div>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>
    </>
  );
}
