"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { createClient } from "@/lib/supabase/client";

/** Aktualisiert die Seite live, wenn der Agent neue Vorschläge oder Ergebnisse meldet. */
export function RealtimeRefresh({ userId }: { userId: string }) {
  const router = useRouter();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const supabase = createClient();
    const refresh = () => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => router.refresh(), 800);
    };
    const channel = supabase
      .channel(`live-${userId}`)
      .on("postgres_changes", { event: "*", schema: "public", table: "actions", filter: `user_id=eq.${userId}` }, refresh)
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "activity_logs", filter: `user_id=eq.${userId}` }, refresh)
      .subscribe();
    return () => {
      if (timer.current) clearTimeout(timer.current);
      supabase.removeChannel(channel);
    };
  }, [router, userId]);

  return null;
}
