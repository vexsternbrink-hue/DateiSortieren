import { ActionForm, SubmitButton } from "@/components/form-status";
import type { RuleRow } from "@/lib/types";
import { saveRule } from "../actions";

export function RuleForm({ rule }: { rule?: RuleRow }) {
  const m = rule?.match ?? {};
  const join = (v?: string[]) => (v ?? []).join(", ");
  return (
    <ActionForm action={saveRule} resetOnSuccess={!rule} className="grid gap-4 sm:grid-cols-2">
      {rule && <input type="hidden" name="id" value={rule.id} />}
      <div>
        <label className="label">Name</label>
        <input name="name" className="input" required defaultValue={rule?.name} placeholder="Telekom-Rechnungen" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Aktion</label>
          <select name="action" className="input" defaultValue={rule?.action ?? "move"}>
            <option value="move">Sortieren</option>
            <option value="ignore">Ignorieren</option>
            <option value="delete">Löschen vorschlagen</option>
          </select>
        </div>
        <div>
          <label className="label">Priorität</label>
          <input name="priority" type="number" className="input" defaultValue={rule?.priority ?? 100} title="kleiner = wichtiger" />
        </div>
      </div>

      <fieldset className="col-span-full rounded-xl border border-border p-4">
        <legend className="px-1 text-sm font-medium">Wenn … (alle ausgefüllten Bedingungen müssen zutreffen)</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="label">Dateiendungen</label>
            <input name="extensions" className="input" defaultValue={join(m.extensions)} placeholder=".pdf, .jpg" />
          </div>
          <div>
            <label className="label">Dateiname enthält</label>
            <input name="name_contains" className="input" defaultValue={join(m.name_contains)} placeholder="telekom, rechnung" />
          </div>
          <div>
            <label className="label">Inhalt enthält (Schlüsselwörter)</label>
            <input name="content_keywords" className="input" defaultValue={join(m.content_keywords)} placeholder="Kundennummer 12345" />
          </div>
          <div>
            <label className="label">KI-Kategorie beginnt mit</label>
            <input name="category_is" className="input" defaultValue={m.category_is ?? ""} placeholder="Finanzen/Rechnungen" />
          </div>
          <div>
            <label className="label">Regulärer Ausdruck (Dateiname)</label>
            <input name="name_regex" className="input font-mono" defaultValue={m.name_regex ?? ""} placeholder="^IMG_\d+" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Min. KB</label>
              <input name="min_size_kb" type="number" className="input" defaultValue={m.min_size_kb ?? ""} />
            </div>
            <div>
              <label className="label">Max. KB</label>
              <input name="max_size_kb" type="number" className="input" defaultValue={m.max_size_kb ?? ""} />
            </div>
          </div>
        </div>
      </fieldset>

      <fieldset className="col-span-full rounded-xl border border-border p-4">
        <legend className="px-1 text-sm font-medium">Dann …</legend>
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <label className="label">Zielordner</label>
            <input name="target" className="input font-mono" defaultValue={rule?.target ?? ""} placeholder="Finanzen/Telekom/{year}" />
          </div>
          <div>
            <label className="label">Dateiname-Vorlage</label>
            <input name="rename_template" className="input font-mono" defaultValue={rule?.rename_template ?? ""} placeholder="{date}_Telekom_{amount}" />
          </div>
          <div>
            <label className="label">Tags</label>
            <input name="tags" className="input" defaultValue={join(rule?.tags)} placeholder="telekom, vertrag" />
          </div>
        </div>
        <p className="mt-2 text-xs text-muted">Platzhalter: {"{date} {year} {month} {vendor} {doc_type} {title} {amount} {category}"}</p>
      </fieldset>

      <div className="col-span-full">
        <SubmitButton>{rule ? "Änderungen speichern" : "Regel anlegen"}</SubmitButton>
      </div>
    </ActionForm>
  );
}
