import { ActionForm, SubmitButton } from "@/components/form-status";
import { PageHeader } from "@/components/ui";
import { requireUser } from "@/lib/supabase/server";
import { DEFAULT_SETTINGS, type ProfileRow } from "@/lib/types";
import { clearRejected, saveSettings } from "../actions";

export const metadata = { title: "Einstellungen" };

function Toggle({ name, label, hint, defaultChecked }: { name: string; label: string; hint: string; defaultChecked: boolean }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border p-4 hover:bg-surface-muted/50">
      <input type="checkbox" name={name} defaultChecked={defaultChecked} className="mt-0.5 size-4 accent-indigo-600" />
      <span>
        <span className="block text-sm font-medium">{label}</span>
        <span className="block text-xs text-muted">{hint}</span>
      </span>
    </label>
  );
}

export default async function SettingsPage() {
  const { supabase, user } = await requireUser();
  const { data } = await supabase.from("profiles").select("*").eq("id", user.id).maybeSingle();
  const profile = data as ProfileRow | null;
  const s = { ...DEFAULT_SETTINGS, ...(profile?.settings ?? {}) };

  return (
    <>
      <PageHeader
        title="Einstellungen"
        description="Gilt für alle deine Agenten und wird beim nächsten Heartbeat übernommen. API-Keys bleiben immer lokal auf deinem Rechner."
      />
      <ActionForm action={saveSettings} className="space-y-6">
        <section className="card p-6">
          <h2 className="mb-4 font-medium">Profil</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">Anzeigename</label>
              <input name="display_name" className="input" defaultValue={profile?.display_name ?? ""} />
            </div>
            <div>
              <label className="label">E-Mail</label>
              <input className="input" value={user.email ?? ""} disabled readOnly />
            </div>
          </div>
        </section>

        <section className="card p-6">
          <h2 className="mb-4 font-medium">Sicherheit</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <Toggle
              name="dry_run"
              label="Dry-Run-Modus (empfohlen)"
              hint="Der Agent schlägt nur vor. Nichts passiert ohne deine Freigabe."
              defaultChecked={s.dry_run}
            />
            <div className="rounded-xl border border-border p-4">
              <label className="label">Automatisch ausführen ab KI-Sicherheit</label>
              <input
                name="auto_apply_min_confidence"
                type="number"
                min={0}
                max={1}
                step={0.05}
                className="input"
                defaultValue={s.auto_apply_min_confidence}
              />
              <p className="mt-1 text-xs text-muted">Nur ohne Dry-Run. Löschungen brauchen immer eine Freigabe.</p>
            </div>
          </div>
        </section>

        <section className="card p-6">
          <h2 className="mb-4 font-medium">Funktionen</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <Toggle name="rename_enabled" label="Automatisch umbenennen" hint="Kryptische Namen → 2026-09-12_Telekom_Rechnung_89Euro.pdf" defaultChecked={s.rename_enabled} />
            <Toggle name="duplicates_enabled" label="Duplikate erkennen" hint="SHA-256, pHash (Bilder) und SimHash (PDFs)" defaultChecked={s.duplicates_enabled} />
            <Toggle name="cleanup_enabled" label="Smart Cleanup" hint="Temp-Dateien, alte Installer, abgebrochene Downloads, leere Ordner" defaultChecked={s.cleanup_enabled} />
            <Toggle name="media_enabled" label="Medien komprimieren" hint="Große Bilder und Videos verkleinern (Original bleibt in Quarantäne)" defaultChecked={s.media_enabled} />
          </div>
          <div className="mt-4 max-w-xs">
            <label className="label">Installer löschen nach (Tagen)</label>
            <input name="installer_max_age_days" type="number" min={1} className="input" defaultValue={s.installer_max_age_days} />
          </div>
        </section>

        <section className="card p-6">
          <h2 className="mb-4 font-medium">Vorlagen</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">Ordnerstruktur</label>
              <input name="organize_template" className="input font-mono" defaultValue={s.organize_template} />
            </div>
            <div>
              <label className="label">Dateiname</label>
              <input name="rename_template" className="input font-mono" defaultValue={s.rename_template} />
            </div>
          </div>
          <p className="mt-2 text-xs text-muted">Platzhalter: {"{category} {year} {month} {date} {vendor} {doc_type} {title} {amount}"}</p>
        </section>

        <SubmitButton>Einstellungen speichern</SubmitButton>
      </ActionForm>

      <section className="card mt-8 p-6">
        <h2 className="mb-2 font-medium">Aufräumen</h2>
        <p className="mb-4 text-sm text-muted">Abgelehnte Vorschläge endgültig aus dem Dashboard entfernen.</p>
        <form action={clearRejected}>
          <button className="btn" type="submit">Abgelehnte Vorschläge löschen</button>
        </form>
      </section>
    </>
  );
}
