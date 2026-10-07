import { authenticateAgent, unauthorized } from "@/lib/agent-auth";

/** Freigaben und Undo-Wünsche aus dem Dashboard, die dieser Agent ausführen soll. */
export async function GET(request: Request) {
  const ctx = await authenticateAgent(request);
  if (!ctx) return unauthorized();
  const columns = "id, batch_id, kind, status, src_path, dst_path, reason, confidence, category, tags, details";
  const weekAgo = new Date(Date.now() - 7 * 86400 * 1000).toISOString();

  const [approved, undo, rejected] = await Promise.all([
    ctx.admin.from("actions").select(columns).eq("agent_id", ctx.agentId).eq("status", "approved").limit(200),
    ctx.admin.from("actions").select(columns).eq("agent_id", ctx.agentId).eq("status", "undo_requested").limit(200),
    ctx.admin
      .from("actions")
      .select("id")
      .eq("agent_id", ctx.agentId)
      .eq("status", "rejected")
      .gte("updated_at", weekAgo)
      .limit(500),
  ]);

  return Response.json({
    approved: approved.data ?? [],
    undo: undo.data ?? [],
    rejected: (rejected.data ?? []).map((r) => r.id),
  });
}
