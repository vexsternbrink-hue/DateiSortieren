import { authenticateAgent, unauthorized } from "@/lib/agent-auth";

const LEVELS = new Set(["debug", "info", "warning", "error"]);

export async function POST(request: Request) {
  const ctx = await authenticateAgent(request);
  if (!ctx) return unauthorized();
  const body = (await request.json().catch(() => ({}))) as { level?: string; message?: string; details?: unknown };
  if (!body.message) return Response.json({ error: "message fehlt" }, { status: 400 });

  const { error } = await ctx.admin.from("activity_logs").insert({
    user_id: ctx.userId,
    agent_id: ctx.agentId,
    level: LEVELS.has(body.level ?? "") ? body.level : "info",
    message: String(body.message).slice(0, 2000),
    details: typeof body.details === "object" && body.details ? body.details : {},
  });
  if (error) return Response.json({ error: error.message }, { status: 500 });
  return Response.json({ ok: true });
}
