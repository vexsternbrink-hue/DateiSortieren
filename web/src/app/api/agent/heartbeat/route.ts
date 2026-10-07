import { authenticateAgent, unauthorized } from "@/lib/agent-auth";

/** Lebenszeichen des Agenten; antwortet mit angeforderten Scans aus dem Dashboard. */
export async function POST(request: Request) {
  const ctx = await authenticateAgent(request);
  if (!ctx) return unauthorized();
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;

  const { data: agent } = await ctx.admin
    .from("agents")
    .select("scan_requested_at")
    .eq("id", ctx.agentId)
    .single();

  const { hostname, platform, version, ...info } = body;
  await ctx.admin
    .from("agents")
    .update({
      hostname: typeof hostname === "string" ? hostname : null,
      platform: typeof platform === "string" ? platform : null,
      version: typeof version === "string" ? version : null,
      info,
      last_seen_at: new Date().toISOString(),
      scan_requested_at: null,
    })
    .eq("id", ctx.agentId);

  return Response.json({ ok: true, scan_requested: Boolean(agent?.scan_requested_at) });
}
