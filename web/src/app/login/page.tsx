import Link from "next/link";
import { redirect } from "next/navigation";
import { Brand } from "@/components/sidebar";
import { isSupabaseConfigured } from "@/lib/env";
import { LoginForm } from "./login-form";

export const metadata = { title: "Anmelden" };

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const params = await searchParams;
  if (!isSupabaseConfigured()) redirect("/setup");
  const mode = params.mode === "signup" ? "signup" : "login";
  const error = typeof params.error === "string" ? params.error : undefined;
  const next = typeof params.next === "string" ? params.next : "/dashboard";

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex justify-center">
          <Brand />
        </div>
        <div className="card p-6">
          <LoginForm initialMode={mode} initialError={error} next={next} />
        </div>
        <p className="mt-6 text-center text-xs text-muted">
          <Link href="/" className="underline">
            Zurück zur Startseite
          </Link>
        </p>
      </div>
    </main>
  );
}
