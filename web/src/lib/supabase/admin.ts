import "server-only";
import { createClient } from "@supabase/supabase-js";
import { supabaseSecretKey, supabaseUrl } from "@/lib/env";

/** Service-Role-Client: umgeht RLS – nur in der Agent-API verwenden, niemals im Browser. */
export function createAdminClient() {
  return createClient(supabaseUrl, supabaseSecretKey(), {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
