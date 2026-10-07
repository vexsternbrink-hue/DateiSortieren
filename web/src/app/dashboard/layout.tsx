import { LogOut } from "lucide-react";
import { RealtimeRefresh } from "@/components/realtime-refresh";
import { Sidebar } from "@/components/sidebar";
import { fetchCounts } from "@/lib/data";
import { requireUser } from "@/lib/supabase/server";
import { signOut } from "./actions";

export default async function DashboardLayout({ children }: LayoutProps<"/dashboard">) {
  const { user } = await requireUser();
  const counts = await fetchCounts();
  const name = (user.user_metadata?.full_name as string | undefined) ?? user.email ?? "";

  const footer = (
    <div className="flex items-center gap-3 px-2">
      <div className="grid size-8 shrink-0 place-items-center rounded-full bg-indigo-500/15 text-sm font-semibold text-indigo-700 dark:text-indigo-300">
        {name.slice(0, 1).toUpperCase()}
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{name}</div>
        <div className="truncate text-xs text-muted">{user.email}</div>
      </div>
      <form action={signOut}>
        <button className="btn btn-sm" title="Abmelden" type="submit">
          <LogOut className="size-3.5" />
        </button>
      </form>
    </div>
  );

  return (
    <div className="lg:flex">
      <RealtimeRefresh userId={user.id} />
      <Sidebar counts={counts} footer={footer} />
      <main className="min-w-0 flex-1 px-4 py-6 sm:px-8 lg:py-10">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
