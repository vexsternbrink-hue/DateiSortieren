// Zentrale Stelle für Umgebungsvariablen. Unterstützt die neuen (publishable/secret) und die
// klassischen (anon/service_role) Supabase-Schlüssel.

export const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const supabasePublishableKey =
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export function isSupabaseConfigured(): boolean {
  return Boolean(supabaseUrl && supabasePublishableKey);
}

export function supabaseSecretKey(): string {
  const key = process.env.SUPABASE_SECRET_KEY ?? process.env.SUPABASE_SERVICE_ROLE_KEY ?? "";
  if (!key) {
    throw new Error("SUPABASE_SECRET_KEY (oder SUPABASE_SERVICE_ROLE_KEY) ist nicht gesetzt");
  }
  return key;
}
