"use client";

import { useActionState, useEffect, useRef, type ReactNode } from "react";
import type { ActionResult } from "@/app/dashboard/actions";

/** Formular, das eine Server Action ausführt und das Ergebnis anzeigt. */
export function ActionForm({
  action,
  children,
  className,
  resetOnSuccess = false,
}: {
  action: (formData: FormData) => Promise<ActionResult>;
  children: ReactNode;
  className?: string;
  resetOnSuccess?: boolean;
}) {
  const [state, formAction, pending] = useActionState(async (_prev: ActionResult | null, formData: FormData) => {
    return action(formData);
  }, null);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (resetOnSuccess && state?.ok) formRef.current?.reset();
  }, [state, resetOnSuccess]);

  return (
    <form ref={formRef} action={formAction} className={className}>
      <fieldset disabled={pending} className="contents">
        {children}
      </fieldset>
      {state?.message && (
        <p className={`mt-3 text-sm ${state.ok ? "text-emerald-700 dark:text-emerald-300" : "text-rose-600"}`}>{state.message}</p>
      )}
    </form>
  );
}

export function SubmitButton({ children, className = "btn btn-primary" }: { children: ReactNode; className?: string }) {
  return (
    <button type="submit" className={className}>
      {children}
    </button>
  );
}
