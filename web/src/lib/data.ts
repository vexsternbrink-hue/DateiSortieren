import "server-only";
import { requireUser } from "@/lib/supabase/server";
import type { ActionKind, ActionRow, ActionStatus } from "@/lib/types";

export type ActionFilter = {
  statuses?: ActionStatus[];
  kinds?: ActionKind[];
  only?: "duplicates" | "cleanup";
  limit?: number;
  orderBy?: "created_at" | "updated_at";
};

export async function fetchActions(filter: ActionFilter = {}): Promise<ActionRow[]> {
  const { supabase, user } = await requireUser();
  let query = supabase.from("actions").select("*").eq("user_id", user.id);
  if (filter.statuses?.length) query = query.in("status", filter.statuses);
  if (filter.kinds?.length) query = query.in("kind", filter.kinds);
  if (filter.only === "duplicates") query = query.not("details->>duplicate_of", "is", null);
  if (filter.only === "cleanup") query = query.not("details->>cleanup", "is", null);
  const { data } = await query.order(filter.orderBy ?? "created_at", { ascending: false }).limit(filter.limit ?? 300);
  return (data ?? []) as ActionRow[];
}

export async function fetchCounts() {
  const { supabase, user } = await requireUser();
  const base = () =>
    supabase.from("actions").select("id", { count: "exact", head: true }).eq("user_id", user.id).eq("status", "proposed");
  const [proposed, duplicates, cleanup, compress] = await Promise.all([
    base(),
    base().not("details->>duplicate_of", "is", null),
    base().not("details->>cleanup", "is", null),
    base().eq("kind", "compress"),
  ]);
  return {
    proposed: proposed.count ?? 0,
    duplicates: duplicates.count ?? 0,
    cleanup: cleanup.count ?? 0,
    compress: compress.count ?? 0,
  };
}
