import { Bot, Radar, Trash2 } from "lucide-react";
import { headers } from "next/headers";
import { EmptyState, PageHeader } from "@/components/ui";
import { isOnline, timeAgo } from "@/lib/format";
import { requireUser } from "@/lib/supabase/server";
import type { AgentRow } from "@/lib/types";
import { deleteAgent, requestScan } from "../actions";
import { CreateAgent } from "./create-agent";

export const metadata = { title: "Agenten" };

export default async function AgentsPage() {
  const { supabase, user } = await requireUser();
  const { data } = await supabase.from("agents").select("*").eq("user_id", user.id).order("created_at");
  const agents = (data ?? []) as AgentRow[];
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "localhost:3000";
  const proto = h.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  const apiUrl = process.env.NEXT_PUBLIC_SITE_URL ?? `${proto}://${host}`;

  return (
    <>
      <PageHeader
        title="Agenten"
        description="Ein Agent ist das kleine Python-Programm auf deinem Computer. Er liest deine Dateien lokal und meldet nur Pfade und Vorschläge an dieses Dashboard."
      />

      <section className="card mb-8 p-6">
        <h2 className="mb-1 font-medium">Neuen Computer verbinden</h2>
        <ol className="mb-5 mt-3 list-decimal space-y-1 pl-5 text-sm text-muted">
          <li>
            Agent installieren: <code className="rounded bg-surface-muted px-1">pip install -e &quot;./agent[anthropic]&quot;</code> (siehe README)
          </li>
          <li>
            Konfiguration anlegen: <code className="rounded bg-surface-muted px-1">dateisortieren init</code>
          </li>
          <li>Token erzeugen und in die Konfiguration kopieren:</li>
        </ol>
        <CreateAgent apiUrl={apiUrl} />
        <p className="mt-4 text-sm text-muted">
          Danach: <code className="rounded bg-surface-muted px-1">dateisortieren doctor</code> prüft die Verbindung,{" "}
          <code className="rounded bg-surface-muted px-1">dateisortieren run</code> startet den Daemon.
        </p>
      </section>

      {agents.length === 0 ? (
        <EmptyState icon={Bot} title="Noch kein Agent verbunden" />
      ) : (
        <ul className="grid gap-4 md:grid-cols-2">
          {agents.map((agent) => {
            const online = isOnline(agent.last_seen_at);
            const info = agent.info as { watch_dirs?: string[]; target_root?: string; dry_run?: boolean; ai_provider?: string };
            return (
              <li key={agent.id} className="card p-5">
                <div className="flex items-start gap-3">
                  <span className={`mt-1.5 size-2.5 rounded-full ${online ? "bg-emerald-500" : "bg-slate-400"}`} />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium">{agent.name}</div>
                    <div className="text-xs text-muted">
                      {online ? "online" : "offline"} · zuletzt {timeAgo(agent.last_seen_at)} · Token {agent.token_prefix}…
                    </div>
                  </div>
                </div>
                <dl className="mt-4 grid grid-cols-[110px_1fr] gap-y-1 text-xs">
                  <dt className="text-muted">Rechner</dt>
                  <dd className="truncate">{agent.hostname ?? "–"} {agent.platform && `(${agent.platform})`}</dd>
                  <dt className="text-muted">Überwacht</dt>
                  <dd className="truncate font-mono">{info.watch_dirs?.join(", ") ?? "–"}</dd>
                  <dt className="text-muted">Ziel</dt>
                  <dd className="truncate font-mono">{info.target_root ?? "–"}</dd>
                  <dt className="text-muted">Modus / KI</dt>
                  <dd>
                    {info.dry_run === undefined ? "–" : info.dry_run ? "Dry-Run" : "Automatisch"} · {info.ai_provider ?? "–"}
                  </dd>
                  <dt className="text-muted">Version</dt>
                  <dd>{agent.version ?? "–"}</dd>
                </dl>
                <div className="mt-4 flex gap-2">
                  <form action={async () => {
                    "use server";
                    await requestScan(agent.id);
                  }}>
                    <button className="btn btn-sm" type="submit" disabled={!!agent.scan_requested_at}>
                      <Radar className="size-3.5" /> {agent.scan_requested_at ? "Scan angefordert …" : "Jetzt scannen"}
                    </button>
                  </form>
                  <form action={deleteAgent.bind(null, agent.id)}>
                    <button className="btn btn-sm" type="submit">
                      <Trash2 className="size-3.5 text-rose-600" /> Entfernen
                    </button>
                  </form>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
