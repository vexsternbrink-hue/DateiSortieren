import { authenticateAgent, unauthorized } from "@/lib/agent-auth";
import type { ActionRow } from "@/lib/types";

const KINDS = new Set(["move", "delete", "compress"]);
const STATUSES = new Set(["proposed", "approved", "rejected", "applied", "skipped", "failed", "undo_requested", "undone"]);
// Diese Status setzt der Nutzer im Dashboard – ein veralteter Agent-Stand darf sie nicht überschreiben
const USER_DECISIONS = new Set(["approved", "rejected", "undo_requested"]);

type IncomingAction = Partial<ActionRow> & { id: string };

/** Agent meldet neue Vorschläge (Dry-Run) und Ergebnisse (ausgeführt / rückgängig / Fehler). */
export async function POST(request: Request) {
  const ctx = await authenticateAgent(request);
  if (!ctx) return unauthorized();
  const body = (await request.json().catch(() => null)) as { actions?: IncomingAction[] } | null;
  const incoming = (body?.actions ?? []).slice(0, 500).filter(
    (a) => a && typeof a.id === "string" && KINDS.has(String(a.kind)) && STATUSES.has(String(a.status)) && a.src_path,
  );
  if (incoming.length === 0) return Response.json({ upserted: 0 });

  const { data: existing } = await ctx.admin
    .from("actions")
    .select("id, user_id, status")
    .in("id", incoming.map((a) => a.id));
  const known = new Map((existing ?? []).map((row) => [row.id as string, row]));

  const rows = [];
  for (const a of incoming) {
    const prev = known.get(a.id);
    if (prev && prev.user_id !== ctx.userId) continue; // fremde ID – ignorieren
    let status = a.status!;
    if (prev && USER_DECISIONS.has(prev.status) && (status === "proposed" || (prev.status === "undo_requested" && status === "applied"))) {
      status = prev.status;
    }
    rows.push({
      id: a.id,
      user_id: ctx.userId,
      agent_id: ctx.agentId,
      batch_id: a.batch_id ?? null,
      kind: a.kind,
      status,
      src_path: String(a.src_path).slice(0, 4096),
      dst_path: a.dst_path ? String(a.dst_path).slice(0, 4096) : null,
      reason: a.reason ? String(a.reason).slice(0, 1000) : null,
      confidence: typeof a.confidence === "number" ? a.confidence : null,
      category: a.category ?? null,
      tags: Array.isArray(a.tags) ? a.tags.slice(0, 20).map(String) : [],
      details: a.details ?? {},
      error: a.error ?? null,
      created_at: a.created_at ?? new Date().toISOString(),
      applied_at: a.applied_at ?? null,
      undone_at: a.undone_at ?? null,
    });
  }

  const { error } = await ctx.admin.from("actions").upsert(rows, { onConflict: "id" });
  if (error) return Response.json({ error: error.message }, { status: 500 });
  return Response.json({ upserted: rows.length });
}
