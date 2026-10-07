"use client";

import { Loader2, Mail } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

export function LoginForm({ initialMode, initialError, next }: { initialMode: "login" | "signup"; initialError?: string; next: string }) {
  const router = useRouter();
  const [mode, setMode] = useState(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(initialError ?? "");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);

  const callbackUrl = () => `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`;

  async function signInWithGoogle() {
    setLoading(true);
    setError("");
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOAuth({ provider: "google", options: { redirectTo: callbackUrl() } });
    if (error) {
      setError(error.message);
      setLoading(false);
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setInfo("");
    const supabase = createClient();
    if (mode === "signup") {
      const { data, error } = await supabase.auth.signUp({ email, password, options: { emailRedirectTo: callbackUrl() } });
      if (error) setError(error.message);
      else if (data.session) router.push(next);
      else setInfo("Fast geschafft! Bitte bestätige deine E-Mail-Adresse über den Link in deinem Postfach.");
    } else if (mode === "login") {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) setError(error.message === "Invalid login credentials" ? "E-Mail oder Passwort falsch" : error.message);
      else {
        router.push(next);
        router.refresh();
      }
    }
    setLoading(false);
  }

  async function resetPassword() {
    if (!email) {
      setError("Bitte zuerst die E-Mail-Adresse eingeben");
      return;
    }
    const supabase = createClient();
    const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: `${window.location.origin}/auth/callback?next=/dashboard/settings` });
    if (error) setError(error.message);
    else setInfo("Wir haben dir einen Link zum Zurücksetzen geschickt.");
  }

  return (
    <div>
      <h1 className="text-xl font-semibold">{mode === "signup" ? "Konto erstellen" : "Willkommen zurück"}</h1>
      <p className="mt-1 text-sm text-muted">{mode === "signup" ? "In 2 Minuten startklar." : "Melde dich an, um dein Dashboard zu öffnen."}</p>

      <button className="btn mt-6 w-full" onClick={signInWithGoogle} disabled={loading} type="button">
        <svg viewBox="0 0 48 48" className="size-4" aria-hidden>
          <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
          <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
          <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
          <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
        </svg>
        Mit Google fortfahren
      </button>

      <div className="my-5 flex items-center gap-3 text-xs text-muted">
        <div className="h-px flex-1 bg-border" /> oder mit E-Mail <div className="h-px flex-1 bg-border" />
      </div>

      <form onSubmit={submit} className="space-y-3">
        <div>
          <label className="label" htmlFor="email">E-Mail</label>
          <input id="email" type="email" required autoComplete="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="password">Passwort</label>
          <input
            id="password"
            type="password"
            required
            minLength={8}
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {error && <p className="text-sm text-rose-600">{error}</p>}
        {info && <p className="text-sm text-emerald-700 dark:text-emerald-300">{info}</p>}
        <button type="submit" className="btn btn-primary w-full" disabled={loading}>
          {loading ? <Loader2 className="size-4 animate-spin" /> : <Mail className="size-4" />}
          {mode === "signup" ? "Registrieren" : "Anmelden"}
        </button>
      </form>

      <div className="mt-4 flex justify-between text-xs text-muted">
        <button type="button" className="underline" onClick={() => setMode(mode === "signup" ? "login" : "signup")}>
          {mode === "signup" ? "Schon ein Konto? Anmelden" : "Neu hier? Konto erstellen"}
        </button>
        {mode === "login" && (
          <button type="button" className="underline" onClick={resetPassword}>
            Passwort vergessen?
          </button>
        )}
      </div>
    </div>
  );
}
