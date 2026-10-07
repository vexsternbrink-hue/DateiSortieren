import { ScrollText } from "lucide-react";
import { EmptyState, PageHeader } from "@/components/ui";
import { formatDate } from "@/lib/format";
import { requireUser } from "@/lib/supabase/server";
import type { LogRow } from "@/lib/types";

export const metadata = { title: "Aktivität" };

const LEVEL_CLS: Record<LogRow["level"], string> = {
  debug: "bg-slate-500/15 text-slate-600",
  info: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  warning: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  error: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
};

export default async function ActivityPage() {
  const { supabase, user } = await requireUser();
  const [logsRes, agentsRes] = await Promise.all([
    supabase.from("activity_logs").select("*").eq("user_id", user.id).order("created_at", { ascending: false }).limit(300),
    supabase.from("agents").select("id, name").eq("user_id", user.id),
  ]);
  const logs = (logsRes.data ?? []) as LogRow[];
  const agentNames = new Map((agentsRes.data ?? []).map((a) => [a.id as string, a.name as string]));

  return (
    <>
      <PageHeader title="Aktivitäts-Log" description="Was deine Agenten wann getan haben." />
      {logs.length === 0 ? (
        <EmptyState icon={ScrollText} title="Noch keine Aktivität" />
      ) : (
        <ul className="card divide-y divide-border">
          {logs.map((log) => (
            <li key={log.id} className="flex flex-wrap items-center gap-3 px-5 py-3 text-sm">
              <span className={`badge w-16 justify-center ${LEVEL_CLS[log.level]}`}>{log.level}</span>
              <span className="min-w-0 flex-1">{log.message}</span>
              <span className="text-xs text-muted">{log.agent_id ? agentNames.get(log.agent_id) ?? "gelöschter Agent" : ""}</span>
              <span className="w-28 text-right text-xs text-muted">{formatDate(log.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
