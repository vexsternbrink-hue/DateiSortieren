"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { generateAgentToken } from "@/lib/agent-auth";
import { requireUser } from "@/lib/supabase/server";
import { DEFAULT_SETTINGS, type ProfileSettings, type RuleMatch } from "@/lib/types";

export type ActionResult = { ok: boolean; message?: string; token?: string };

function refresh() {
  revalidatePath("/dashboard", "layout");
}

function list(value: FormDataEntryValue | null): string[] {
  return String(value ?? "")
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

// ------------------------------------------------------------- Aktionen
async function setStatus(ids: string[], from: string[], to: string): Promise<ActionResult> {
  if (ids.length === 0) return { ok: false, message: "Nichts ausgewählt" };
  const { supabase, user } = await requireUser();
  const { error, count } = await supabase
    .from("actions")
    .update({ status: to }, { count: "exact" })
    .in("id", ids.slice(0, 1000))
    .in("status", from)
    .eq("user_id", user.id);
  refresh();
  if (error) return { ok: false, message: error.message };
  return { ok: true, message: `${count ?? 0} Aktion(en) aktualisiert` };
}

export async function approveActions(ids: string[]) {
  return setStatus(ids, ["proposed", "failed"], "approved");
}

export async function rejectActions(ids: string[]) {
  return setStatus(ids, ["proposed", "failed", "approved"], "rejected");
}

export async function resetActions(ids: string[]) {
  return setStatus(ids, ["approved", "rejected"], "proposed");
}

export async function requestUndo(ids: string[]) {
  return setStatus(ids, ["applied"], "undo_requested");
}

export async function cancelUndo(ids: string[]) {
  return setStatus(ids, ["undo_requested"], "applied");
}

export async function undoBatch(batchId: string) {
  const { supabase, user } = await requireUser();
  const { data } = await supabase
    .from("actions")
    .select("id")
    .eq("user_id", user.id)
    .eq("batch_id", batchId)
    .eq("status", "applied");
  return requestUndo((data ?? []).map((r) => r.id));
}

export async function clearRejected() {
  const { supabase, user } = await requireUser();
  await supabase.from("actions").delete().eq("user_id", user.id).eq("status", "rejected");
  refresh();
}

// --------------------------------------------------------------- Regeln
export async function saveRule(formData: FormData): Promise<ActionResult> {
  const { supabase, user } = await requireUser();
  const id = String(formData.get("id") ?? "");
  const minSize = Number(formData.get("min_size_kb") || 0) || null;
  const maxSize = Number(formData.get("max_size_kb") || 0) || null;
  const match: RuleMatch = {
    extensions: list(formData.get("extensions")).map((e) => (e.startsWith(".") ? e : `.${e}`).toLowerCase()),
    name_contains: list(formData.get("name_contains")),
    name_regex: String(formData.get("name_regex") ?? "").trim() || undefined,
    content_keywords: list(formData.get("content_keywords")),
    category_is: String(formData.get("category_is") ?? "").trim() || undefined,
    min_size_kb: minSize,
    max_size_kb: maxSize,
  };
  if (match.name_regex) {
    try {
      new RegExp(match.name_regex);
    } catch {
      return { ok: false, message: "Ungültiger regulärer Ausdruck" };
    }
  }
  const hasCondition = Object.values(match).some((v) => (Array.isArray(v) ? v.length > 0 : Boolean(v)));
  if (!hasCondition) return { ok: false, message: "Mindestens eine Bedingung angeben" };

  const action = String(formData.get("action") ?? "move") as "move" | "ignore" | "delete";
  const row = {
    name: String(formData.get("name") ?? "").trim() || "Neue Regel",
    description: String(formData.get("description") ?? "").trim() || null,
    priority: Number(formData.get("priority") || 100),
    enabled: formData.get("enabled") !== "off",
    match,
    action: ["move", "ignore", "delete"].includes(action) ? action : "move",
    target: String(formData.get("target") ?? "").trim().replace(/^\/+|\/+$/g, "") || null,
    rename_template: String(formData.get("rename_template") ?? "").trim() || null,
    tags: list(formData.get("tags")).map((t) => t.toLowerCase()),
  };
  const { error } = id
    ? await supabase.from("rules").update(row).eq("id", id).eq("user_id", user.id)
    : await supabase.from("rules").insert({ ...row, user_id: user.id });
  refresh();
  return error ? { ok: false, message: error.message } : { ok: true, message: "Regel gespeichert" };
}

export async function toggleRule(id: string, enabled: boolean) {
  const { supabase, user } = await requireUser();
  await supabase.from("rules").update({ enabled }).eq("id", id).eq("user_id", user.id);
  refresh();
}

export async function deleteRule(id: string) {
  const { supabase, user } = await requireUser();
  await supabase.from("rules").delete().eq("id", id).eq("user_id", user.id);
  refresh();
}

// ------------------------------------------------------------ Safe-List
export async function addSafelistEntry(formData: FormData): Promise<ActionResult> {
  const { supabase, user } = await requireUser();
  const kind = String(formData.get("kind") ?? "");
  let value = String(formData.get("value") ?? "").trim();
  if (!["path", "glob", "extension", "tag"].includes(kind) || !value) {
    return { ok: false, message: "Typ und Wert angeben" };
  }
  if (kind === "extension") value = (value.startsWith(".") ? value : `.${value}`).toLowerCase();
  if (kind === "tag") value = value.toLowerCase();
  const { error } = await supabase.from("safelist_entries").insert({
    user_id: user.id,
    kind,
    value,
    note: String(formData.get("note") ?? "").trim() || null,
  });
  refresh();
  if (error) {
    return { ok: false, message: error.code === "23505" ? "Eintrag existiert bereits" : error.message };
  }
  return { ok: true, message: "Hinzugefügt" };
}

export async function deleteSafelistEntry(id: string) {
  const { supabase, user } = await requireUser();
  await supabase.from("safelist_entries").delete().eq("id", id).eq("user_id", user.id);
  refresh();
}

// --------------------------------------------------------------- Agenten
export async function createAgent(formData: FormData): Promise<ActionResult> {
  const { supabase, user } = await requireUser();
  const name = String(formData.get("name") ?? "").trim() || "Mein Computer";
  const { token, hash, prefix } = generateAgentToken();
  const { error } = await supabase
    .from("agents")
    .insert({ user_id: user.id, name, token_hash: hash, token_prefix: prefix });
  refresh();
  if (error) return { ok: false, message: error.message };
  return { ok: true, token, message: "Agent angelegt – Token jetzt kopieren, es wird nur einmal angezeigt." };
}

export async function deleteAgent(id: string) {
  const { supabase, user } = await requireUser();
  await supabase.from("agents").delete().eq("id", id).eq("user_id", user.id);
  refresh();
}

export async function requestScan(id: string): Promise<ActionResult> {
  const { supabase, user } = await requireUser();
  const { error } = await supabase
    .from("agents")
    .update({ scan_requested_at: new Date().toISOString() })
    .eq("id", id)
    .eq("user_id", user.id);
  refresh();
  return error
    ? { ok: false, message: error.message }
    : { ok: true, message: "Scan angefordert – der Agent startet ihn beim nächsten Heartbeat (≤ 1 Min.)." };
}

// ---------------------------------------------------------- Einstellungen
export async function saveSettings(formData: FormData): Promise<ActionResult> {
  const { supabase, user } = await requireUser();
  const { data: profile } = await supabase.from("profiles").select("settings").eq("id", user.id).single();
  const current: ProfileSettings = { ...DEFAULT_SETTINGS, ...(profile?.settings ?? {}) };
  const bool = (key: string) => formData.get(key) === "on";
  const next: ProfileSettings = {
    ...current,
    dry_run: bool("dry_run"),
    media_enabled: bool("media_enabled"),
    duplicates_enabled: bool("duplicates_enabled"),
    cleanup_enabled: bool("cleanup_enabled"),
    rename_enabled: bool("rename_enabled"),
    auto_apply_min_confidence: Math.min(1, Math.max(0, Number(formData.get("auto_apply_min_confidence") ?? 0.85))),
    installer_max_age_days: Math.max(1, Number(formData.get("installer_max_age_days") ?? 14)),
    rename_template: String(formData.get("rename_template") ?? current.rename_template).trim() || DEFAULT_SETTINGS.rename_template,
    organize_template:
      String(formData.get("organize_template") ?? current.organize_template).trim() || DEFAULT_SETTINGS.organize_template,
  };
  const { error } = await supabase
    .from("profiles")
    .update({ settings: next, display_name: String(formData.get("display_name") ?? "").trim() || null })
    .eq("id", user.id);
  refresh();
  return error ? { ok: false, message: error.message } : { ok: true, message: "Einstellungen gespeichert" };
}

export async function saveAiInstructions(formData: FormData): Promise<ActionResult> {
  const { supabase, user } = await requireUser();
  const { data: profile } = await supabase.from("profiles").select("settings").eq("id", user.id).single();
  const settings = { ...DEFAULT_SETTINGS, ...(profile?.settings ?? {}), ai_instructions: String(formData.get("ai_instructions") ?? "").slice(0, 4000) };
  const { error } = await supabase.from("profiles").update({ settings }).eq("id", user.id);
  refresh();
  return error ? { ok: false, message: error.message } : { ok: true, message: "KI-Anweisungen gespeichert" };
}

export async function signOut() {
  const { supabase } = await requireUser();
  await supabase.auth.signOut();
  redirect("/login");
}
