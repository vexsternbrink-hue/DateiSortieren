import { Sparkles, Trash2 } from "lucide-react";
import { ActionForm, SubmitButton } from "@/components/form-status";
import { PageHeader } from "@/components/ui";
import { requireUser } from "@/lib/supabase/server";
import { DEFAULT_SETTINGS, type RuleRow } from "@/lib/types";
import { deleteRule, saveAiInstructions, toggleRule } from "../actions";
import { RuleForm } from "./rule-form";

export const metadata = { title: "KI-Regeln" };

function describe(rule: RuleRow): string {
  const m = rule.match;
  const parts = [
    m.extensions?.length && `Endung ${m.extensions.join("/")}`,
    m.name_contains?.length && `Name enthält „${m.name_contains.join("“ oder „")}“`,
    m.content_keywords?.length && `Inhalt enthält „${m.content_keywords.join("“ oder „")}“`,
    m.category_is && `KI-Kategorie ${m.category_is}`,
    m.name_regex && `Name passt zu /${m.name_regex}/`,
  ].filter(Boolean);
  const then = rule.action === "ignore" ? "ignorieren" : rule.action === "delete" ? "Löschen vorschlagen" : `→ ${rule.target ?? "Standardordner"}`;
  return `${parts.join(" und ")} ${then}`;
}

export default async function RulesPage() {
  const { supabase, user } = await requireUser();
  const [rulesRes, profileRes] = await Promise.all([
    supabase.from("rules").select("*").eq("user_id", user.id).order("priority").order("created_at"),
    supabase.from("profiles").select("settings").eq("id", user.id).maybeSingle(),
  ]);
  const rules = (rulesRes.data ?? []) as RuleRow[];
  const instructions = profileRes.data?.settings?.ai_instructions ?? DEFAULT_SETTINGS.ai_instructions;

  return (
    <>
      <PageHeader
        title="KI-Regeln"
        description="Bringe der KI deine persönliche Ordnung bei – in natürlicher Sprache oder mit präzisen Wenn-Dann-Regeln. Regeln haben Vorrang vor der KI."
      />

      <section className="card mb-8 p-6">
        <h2 className="mb-1 flex items-center gap-2 font-medium">
          <Sparkles className="size-4 text-indigo-500" /> Anweisungen an die KI
        </h2>
        <p className="mb-4 text-sm text-muted">Wird bei jeder Klassifizierung mitgeschickt (Anthropic, OpenAI oder lokales LLM).</p>
        <ActionForm action={saveAiInstructions}>
          <textarea
            name="ai_instructions"
            rows={5}
            className="input font-mono"
            defaultValue={instructions}
            placeholder={"Rechnungen meines Arbeitgebers \"Muster GmbH\" gehören nach Arbeit/Muster GmbH.\nKita-Unterlagen nach Familie/Kita.\nFotos von Quittungen als Finanzen/Quittungen behandeln."}
          />
          <div className="mt-3">
            <SubmitButton>Speichern</SubmitButton>
          </div>
        </ActionForm>
      </section>

      <h2 className="mb-3 font-medium">Regeln ({rules.length})</h2>
      <div className="space-y-3">
        {rules.map((rule) => (
          <details key={rule.id} className="card group">
            <summary className="flex cursor-pointer list-none items-center gap-3 px-5 py-4">
              <span className="badge bg-surface-muted font-mono text-muted">{rule.priority}</span>
              <div className="min-w-0 flex-1">
                <div className={`font-medium ${rule.enabled ? "" : "text-muted line-through"}`}>{rule.name}</div>
                <div className="truncate text-xs text-muted">{describe(rule)}</div>
              </div>
              <form action={toggleRule.bind(null, rule.id, !rule.enabled)}>
                <button className="btn btn-sm" type="submit">{rule.enabled ? "Deaktivieren" : "Aktivieren"}</button>
              </form>
              <form action={deleteRule.bind(null, rule.id)}>
                <button className="btn btn-sm" type="submit" title="Löschen">
                  <Trash2 className="size-3.5 text-rose-600" />
                </button>
              </form>
            </summary>
            <div className="border-t border-border p-5">
              <RuleForm rule={rule} />
            </div>
          </details>
        ))}
      </div>

      <section className="card mt-6 p-6">
        <h2 className="mb-4 font-medium">Neue Regel</h2>
        <RuleForm />
      </section>
    </>
  );
}
