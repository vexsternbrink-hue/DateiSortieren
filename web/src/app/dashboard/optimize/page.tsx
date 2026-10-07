import { Zap } from "lucide-react";
import { ActionTable } from "@/components/action-table";
import { EmptyState, PageHeader } from "@/components/ui";
import { fetchActions } from "@/lib/data";

export const metadata = { title: "Medien-Optimierung" };

export default async function OptimizePage() {
  const actions = await fetchActions({ statuses: ["proposed", "approved", "failed"], kinds: ["compress"] });
  return (
    <>
      <PageHeader
        title="Medien-Optimierung"
        description="Bilder (PNG, JPG, WEBP) und Videos, die sich spürbar verkleinern lassen. Das Original bleibt in der Quarantäne und kann wiederhergestellt werden. Aktivierung unter Einstellungen."
      />
      {actions.length === 0 ? (
        <EmptyState icon={Zap} title="Keine Vorschläge">
          Aktiviere die Medien-Optimierung in den Einstellungen, damit der Agent große Bilder und Videos vorschlägt.
        </EmptyState>
      ) : (
        <ActionTable actions={actions} mode="review" />
      )}
    </>
  );
}
