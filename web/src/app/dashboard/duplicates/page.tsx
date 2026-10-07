import { Copy } from "lucide-react";
import { ActionTable } from "@/components/action-table";
import { EmptyState, PageHeader } from "@/components/ui";
import { fetchActions } from "@/lib/data";

export const metadata = { title: "Duplikate" };

export default async function DuplicatesPage() {
  const actions = await fetchActions({ statuses: ["proposed", "approved", "failed"], only: "duplicates" });
  return (
    <>
      <PageHeader
        title="Duplikate"
        description="Exakte Kopien (SHA-256) und inhaltlich ähnliche Bilder/PDFs (pHash/SimHash). Behalten wird immer die ältere bzw. bereits einsortierte Datei; die Kopie wandert nach Freigabe in die Quarantäne."
      />
      {actions.length === 0 ? (
        <EmptyState icon={Copy} title="Keine Duplikate gefunden">Super – alles nur einmal vorhanden.</EmptyState>
      ) : (
        <ActionTable actions={actions} mode="review" />
      )}
    </>
  );
}
