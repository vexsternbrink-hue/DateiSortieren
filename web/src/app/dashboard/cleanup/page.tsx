import { Eraser } from "lucide-react";
import { ActionTable } from "@/components/action-table";
import { EmptyState, PageHeader } from "@/components/ui";
import { fetchActions } from "@/lib/data";

export const metadata = { title: "Aufräumen" };

export default async function CleanupPage() {
  const actions = await fetchActions({ statuses: ["proposed", "approved", "failed"], only: "cleanup" });
  return (
    <>
      <PageHeader
        title="Smart Trash & Cleanup"
        description="Temporäre Dateien, alte Installer (.dmg, .exe, .msi …), abgebrochene Downloads (.crdownload, .part) und leere Ordner. Gelöscht wird erst nach deiner Freigabe – und auch dann nur in die Quarantäne (Standard: 30 Tage wiederherstellbar)."
      />
      {actions.length === 0 ? (
        <EmptyState icon={Eraser} title="Nichts aufzuräumen">Dein Download-Ordner ist sauber.</EmptyState>
      ) : (
        <ActionTable actions={actions} mode="review" />
      )}
    </>
  );
}
