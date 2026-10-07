import { Eye } from "lucide-react";
import Link from "next/link";
import { ActionTable } from "@/components/action-table";
import { EmptyState, PageHeader } from "@/components/ui";
import { fetchActions } from "@/lib/data";
import type { ActionKind, ActionStatus } from "@/lib/types";

export const metadata = { title: "Vorschau" };

const STATUS_TABS: { key: string; label: string; statuses: ActionStatus[] }[] = [
  { key: "open", label: "Offen", statuses: ["proposed", "approved"] },
  { key: "approved", label: "Freigegeben", statuses: ["approved"] },
  { key: "failed", label: "Fehlgeschlagen", statuses: ["failed"] },
  { key: "rejected", label: "Abgelehnt", statuses: ["rejected"] },
];
const KIND_TABS: { key: string; label: string }[] = [
  { key: "all", label: "Alle" },
  { key: "move", label: "Sortieren & Umbenennen" },
  { key: "delete", label: "Löschen" },
  { key: "compress", label: "Komprimieren" },
];

export default async function PreviewPage({ searchParams }: PageProps<"/dashboard/preview">) {
  const params = await searchParams;
  const statusKey = typeof params.status === "string" ? params.status : "open";
  const kindKey = typeof params.kind === "string" ? params.kind : "all";
  const tab = STATUS_TABS.find((t) => t.key === statusKey) ?? STATUS_TABS[0];
  const kinds = kindKey === "all" ? undefined : ([kindKey] as ActionKind[]);
  const actions = await fetchActions({ statuses: tab.statuses, kinds });

  const href = (s: string, k: string) => `/dashboard/preview?status=${s}&kind=${k}`;

  return (
    <>
      <PageHeader
        title="Vorschau (Dry-Run)"
        description="Das WÜRDE passieren. Nichts wird verändert, bis du freigibst – danach führt der Agent die Aktionen aus und jede bleibt rückgängig machbar."
      />
      <div className="mb-4 flex flex-wrap gap-2">
        {STATUS_TABS.map((t) => (
          <Link key={t.key} href={href(t.key, kindKey)} className={`btn btn-sm ${t.key === tab.key ? "btn-primary" : ""}`}>
            {t.label}
          </Link>
        ))}
        <span className="mx-1 w-px bg-border" />
        {KIND_TABS.map((k) => (
          <Link key={k.key} href={href(tab.key, k.key)} className={`btn btn-sm ${k.key === kindKey ? "btn-primary" : ""}`}>
            {k.label}
          </Link>
        ))}
      </div>
      {actions.length === 0 ? (
        <EmptyState icon={Eye} title="Keine Einträge">
          Starte im Bereich „Agenten“ einen Scan oder lege neue Dateien in einen überwachten Ordner.
        </EmptyState>
      ) : (
        <ActionTable actions={actions} mode="review" />
      )}
    </>
  );
}
