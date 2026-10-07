import { History } from "lucide-react";
import Link from "next/link";
import { ActionTable } from "@/components/action-table";
import { EmptyState, PageHeader } from "@/components/ui";
import { fetchActions } from "@/lib/data";
import { formatDate } from "@/lib/format";
import { undoBatch } from "../actions";

export const metadata = { title: "Verlauf & Undo" };

export default async function HistoryPage({ searchParams }: PageProps<"/dashboard/history">) {
  const params = await searchParams;
  const showAll = params.filter === "all";
  const actions = await fetchActions({
    statuses: showAll ? ["applied", "undo_requested", "undone", "skipped", "failed"] : ["applied", "undo_requested"],
    orderBy: "updated_at",
  });

  const batches = new Map<string, { count: number; at: string }>();
  for (const a of actions) {
    if (a.batch_id && a.status === "applied") {
      const b = batches.get(a.batch_id) ?? { count: 0, at: a.applied_at ?? a.created_at };
      b.count += 1;
      batches.set(a.batch_id, b);
    }
  }

  return (
    <>
      <PageHeader
        title="Verlauf & Undo"
        description="Das digitale Manifest: jede Verschiebung, Umbenennung, Löschung und Komprimierung. Ein Klick auf „Undo“ – der Agent stellt den alten Zustand wieder her."
        actions={
          <Link href={showAll ? "/dashboard/history" : "/dashboard/history?filter=all"} className="btn btn-sm">
            {showAll ? "Nur rückgängig machbare" : "Alles anzeigen"}
          </Link>
        }
      />

      {batches.size > 0 && (
        <div className="mb-6">
          <h2 className="mb-2 text-sm font-medium text-muted">Ganze Durchläufe rückgängig machen</h2>
          <div className="flex flex-wrap gap-2">
            {[...batches.entries()].slice(0, 6).map(([id, b]) => (
              <form key={id} action={async () => {
                "use server";
                await undoBatch(id);
              }}>
                <button className="btn btn-sm" type="submit">
                  Durchlauf {formatDate(b.at)} · {b.count} Aktionen rückgängig
                </button>
              </form>
            ))}
          </div>
        </div>
      )}

      {actions.length === 0 ? (
        <EmptyState icon={History} title="Noch nichts ausgeführt">Freigegebene Aktionen erscheinen hier, sobald der Agent sie erledigt hat.</EmptyState>
      ) : (
        <ActionTable actions={actions} mode="history" />
      )}
    </>
  );
}
