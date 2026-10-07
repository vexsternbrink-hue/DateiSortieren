import { Database } from "lucide-react";
import Link from "next/link";

export const metadata = { title: "Einrichtung" };

export default function SetupPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <div className="card p-8">
        <Database className="mb-4 size-8 text-indigo-500" />
        <h1 className="text-2xl font-semibold">Supabase ist noch nicht verbunden</h1>
        <p className="mt-2 text-muted">
          Damit Login und Dashboard funktionieren, braucht die Web-App ein Supabase-Projekt. Das dauert etwa 5 Minuten:
        </p>
        <ol className="mt-6 list-decimal space-y-3 pl-5 text-sm">
          <li>
            Kostenloses Projekt auf <a className="text-indigo-600 underline" href="https://supabase.com/dashboard">supabase.com</a> anlegen.
          </li>
          <li>
            Im SQL-Editor den Inhalt von <code className="rounded bg-surface-muted px-1">supabase/migrations/0001_init.sql</code> ausführen.
          </li>
          <li>
            Unter <em>Project Settings → API Keys</em> die URL, den Publishable Key und den Secret Key kopieren.
          </li>
          <li>
            Als Umgebungsvariablen setzen (lokal in <code className="rounded bg-surface-muted px-1">web/.env.local</code>, auf Vercel unter
            <em> Settings → Environment Variables</em>):
            <pre className="mt-2 overflow-x-auto rounded-lg bg-surface-muted p-3 font-mono text-xs">
{`NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
SUPABASE_SECRET_KEY=sb_secret_...`}
            </pre>
          </li>
          <li>Neu deployen bzw. <code className="rounded bg-surface-muted px-1">npm run dev</code> neu starten.</li>
        </ol>
        <p className="mt-6 text-sm text-muted">
          Ausführliche Anleitung inkl. Google-Login: siehe README im Repository.
        </p>
        <Link href="/" className="btn mt-6">
          Zur Startseite
        </Link>
      </div>
    </main>
  );
}
