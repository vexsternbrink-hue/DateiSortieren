import { ShieldCheck, Trash2 } from "lucide-react";
import { ActionForm, SubmitButton } from "@/components/form-status";
import { EmptyState, PageHeader } from "@/components/ui";
import { requireUser } from "@/lib/supabase/server";
import type { SafelistRow } from "@/lib/types";
import { addSafelistEntry, deleteSafelistEntry } from "../actions";

export const metadata = { title: "Safe-List" };

const KINDS: Record<SafelistRow["kind"], { label: string; example: string }> = {
  path: { label: "Ordner / Pfad", example: "~/Downloads/Projekte" },
  glob: { label: "Muster", example: "Steuer_*.pdf" },
  extension: { label: "Dateiendung", example: ".kdbx" },
  tag: { label: "Tag", example: "vertraulich" },
};

export default async function SafelistPage() {
  const { supabase, user } = await requireUser();
  const { data } = await supabase.from("safelist_entries").select("*").eq("user_id", user.id).order("kind").order("value");
  const entries = (data ?? []) as SafelistRow[];

  return (
    <>
      <PageHeader
        title="Safe-List"
        description="Alles hier wird vom Agenten niemals verschoben, umbenannt, komprimiert oder gelöscht. Zusätzlich kannst du in jeden Ordner eine leere Datei „.dateisortieren-ignore“ legen."
      />
      <section className="card mb-6 p-6">
        <ActionForm action={addSafelistEntry} resetOnSuccess className="grid gap-3 sm:grid-cols-[180px_1fr_1fr_auto] sm:items-end">
          <div>
            <label className="label">Typ</label>
            <select name="kind" className="input">
              {Object.entries(KINDS).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Wert</label>
            <input name="value" className="input font-mono" required placeholder="~/Downloads/Projekte  ·  *.key  ·  .kdbx  ·  privat" />
          </div>
          <div>
            <label className="label">Notiz (optional)</label>
            <input name="note" className="input" placeholder="Warum geschützt?" />
          </div>
          <SubmitButton>Hinzufügen</SubmitButton>
        </ActionForm>
      </section>

      {entries.length === 0 ? (
        <EmptyState icon={ShieldCheck} title="Noch keine Ausnahmen">
          Beispiele: {Object.values(KINDS).map((k) => k.example).join(" · ")}
        </EmptyState>
      ) : (
        <ul className="card divide-y divide-border">
          {entries.map((e) => (
            <li key={e.id} className="flex items-center gap-3 px-5 py-3">
              <span className="badge w-28 justify-center bg-indigo-500/10 text-indigo-700 dark:text-indigo-300">{KINDS[e.kind].label}</span>
              <span className="flex-1 truncate font-mono text-sm">{e.value}</span>
              {e.note && <span className="hidden text-xs text-muted sm:inline">{e.note}</span>}
              <form action={deleteSafelistEntry.bind(null, e.id)}>
                <button className="btn btn-sm" type="submit" title="Entfernen">
                  <Trash2 className="size-3.5 text-rose-600" />
                </button>
              </form>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
