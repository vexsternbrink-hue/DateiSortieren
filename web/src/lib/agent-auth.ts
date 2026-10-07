import "server-only";
import { createHash, randomBytes } from "node:crypto";
import { createAdminClient } from "@/lib/supabase/admin";

export function hashToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

export function generateAgentToken(): { token: string; hash: string; prefix: string } {
  const token = `ds_${randomBytes(32).toString("base64url")}`;
  return { token, hash: hashToken(token), prefix: token.slice(0, 10) };
}

export interface AgentContext {
  agentId: string;
  userId: string;
  admin: ReturnType<typeof createAdminClient>;
}

/** Prüft das Bearer-Token eines lokalen Agenten. */
export async function authenticateAgent(request: Request): Promise<AgentContext | null> {
  const header = request.headers.get("authorization") ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  if (!token.startsWith("ds_")) return null;
  const admin = createAdminClient();
  const { data, error } = await admin
    .from("agents")
    .select("id, user_id")
    .eq("token_hash", hashToken(token))
    .maybeSingle();
  if (error || !data) return null;
  return { agentId: data.id, userId: data.user_id, admin };
}

export function unauthorized() {
  return Response.json({ error: "Ungültiges Agent-Token" }, { status: 401 });
}
