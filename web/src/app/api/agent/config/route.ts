import { authenticateAgent, unauthorized } from "@/lib/agent-auth";

/** Regeln, Safe-List und Einstellungen des Nutzers für den lokalen Agenten. */
export async function GET(request: Request) {
  const ctx = await authenticateAgent(request);
  if (!ctx) return unauthorized();
  const { admin, userId } = ctx;

  const [profile, rules, safelist] = await Promise.all([
    admin.from("profiles").select("settings").eq("id", userId).maybeSingle(),
    admin
      .from("rules")
      .select("id, name, priority, enabled, match, action, target, rename_template, tags")
      .eq("user_id", userId)
      .eq("enabled", true)
      .order("priority"),
    admin.from("safelist_entries").select("kind, value").eq("user_id", userId),
  ]);

  return Response.json({
    settings: profile.data?.settings ?? {},
    rules: rules.data ?? [],
    safelist: safelist.data ?? [],
  });
}
