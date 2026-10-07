"use client";

import { Check, Copy, KeyRound } from "lucide-react";
import { useActionState, useState } from "react";
import { createAgent, type ActionResult } from "../actions";

export function CreateAgent({ apiUrl }: { apiUrl: string }) {
  const [state, formAction, pending] = useActionState(
    async (_prev: ActionResult | null, formData: FormData) => createAgent(formData),
    null,
  );
  const [copied, setCopied] = useState(false);

  const snippet = state?.token
    ? `cloud:\n  api_url: ${apiUrl}\n  agent_token: ${state.token}`
    : "";

  return (
    <div>
      <form action={formAction} className="flex flex-wrap gap-3">
        <input name="name" className="input max-w-xs" placeholder="z. B. MacBook Pro" />
        <button className="btn btn-primary" disabled={pending} type="submit">
          <KeyRound className="size-4" /> Token erzeugen
        </button>
      </form>
      {state && !state.ok && <p className="mt-3 text-sm text-rose-600">{state.message}</p>}
      {state?.token && (
        <div className="mt-4 rounded-xl border border-amber-500/40 bg-amber-500/5 p-4">
          <p className="mb-2 text-sm font-medium">{state.message}</p>
          <p className="mb-2 text-sm text-muted">
            Füge das in <code>~/.dateisortieren/config.yaml</code> ein (oder setze <code>DATEISORTIEREN_API_URL</code> und{" "}
            <code>DATEISORTIEREN_AGENT_TOKEN</code>):
          </p>
          <pre className="overflow-x-auto rounded-lg bg-surface-muted p-3 font-mono text-xs">{snippet}</pre>
          <button
            type="button"
            className="btn btn-sm mt-3"
            onClick={async () => {
              await navigator.clipboard.writeText(snippet);
              setCopied(true);
            }}
          >
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />} {copied ? "Kopiert" : "Kopieren"}
          </button>
        </div>
      )}
    </div>
  );
}
