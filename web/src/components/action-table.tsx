"use client";

import { ArrowRight, Check, Copy, FolderInput, RotateCcw, Trash2, Undo2, X, Zap } from "lucide-react";
import { useMemo, useState, useTransition } from "react";
import {
  approveActions,
  cancelUndo,
  rejectActions,
  requestUndo,
  resetActions,
  type ActionResult,
} from "@/app/dashboard/actions";
import { ConfidenceBar, KindBadge, StatusBadge } from "@/components/ui";
import { dirName, fileName, formatBytes, formatDate } from "@/lib/format";
import type { ActionRow } from "@/lib/types";

type Mode = "review" | "history";

export function ActionTable({ actions, mode }: { actions: ActionRow[]; mode: Mode }) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState<ActionResult | null>(null);
  const [pending, startTransition] = useTransition();

  const selectable = useMemo(
    () =>
      actions.filter((a) =>
        mode === "review" ? ["proposed", "failed", "approved", "rejected"].includes(a.status) : ["applied", "undo_requested"].includes(a.status),
      ),
    [actions, mode],
  );
  const allSelected = selectable.length > 0 && selectable.every((a) => selected.has(a.id));

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function run(fn: (ids: string[]) => Promise<ActionResult>, ids: string[]) {
    startTransition(async () => {
      const result = await fn(ids);
      setMessage(result);
      setSelected(new Set());
    });
  }

  const ids = [...selected];
  const proposedIds = actions.filter((a) => a.status === "proposed").map((a) => a.id);

  return (
    <div className="card overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-border bg-surface-muted/50 px-4 py-3">
        <label className="mr-2 flex items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            className="size-4 accent-indigo-600"
            checked={allSelected}
            onChange={() => setSelected(allSelected ? new Set() : new Set(selectable.map((a) => a.id)))}
          />
          {selected.size > 0 ? `${selected.size} ausgewählt` : "Alle auswählen"}
        </label>
        {mode === "review" ? (
          <>
            <button className="btn btn-sm btn-primary" disabled={!ids.length || pending} onClick={() => run(approveActions, ids)}>
              <Check className="size-3.5" /> Freigeben
            </button>
            <button className="btn btn-sm" disabled={!ids.length || pending} onClick={() => run(rejectActions, ids)}>
              <X className="size-3.5" /> Ablehnen
            </button>
            <button className="btn btn-sm" disabled={!ids.length || pending} onClick={() => run(resetActions, ids)}>
              <RotateCcw className="size-3.5" /> Zurücksetzen
            </button>
            <div className="ml-auto">
              <button
                className="btn btn-sm"
                disabled={!proposedIds.length || pending}
                onClick={() => {
                  if (confirm(`Alle ${proposedIds.length} Vorschläge freigeben? Der Agent führt sie danach aus.`)) {
                    run(approveActions, proposedIds);
                  }
                }}
              >
                <Zap className="size-3.5" /> Alle {proposedIds.length} freigeben
              </button>
            </div>
          </>
        ) : (
          <>
            <button className="btn btn-sm btn-primary" disabled={!ids.length || pending} onClick={() => run(requestUndo, ids)}>
              <Undo2 className="size-3.5" /> Rückgängig machen
            </button>
            <button className="btn btn-sm" disabled={!ids.length || pending} onClick={() => run(cancelUndo, ids)}>
              Undo abbrechen
            </button>
          </>
        )}
      </div>

      {message && (
        <div
          className={`border-b border-border px-4 py-2 text-sm ${message.ok ? "text-emerald-700 dark:text-emerald-300" : "text-rose-600"}`}
        >
          {message.message}
        </div>
      )}

      <ul className="divide-y divide-border">
        {actions.map((a) => (
          <ActionItem
            key={a.id}
            action={a}
            mode={mode}
            checked={selected.has(a.id)}
            disabled={!selectable.includes(a)}
            onToggle={() => toggle(a.id)}
            onRun={(fn) => run(fn, [a.id])}
            pending={pending}
          />
        ))}
      </ul>
    </div>
  );
}

function ActionItem({
  action: a,
  mode,
  checked,
  disabled,
  onToggle,
  onRun,
  pending,
}: {
  action: ActionRow;
  mode: Mode;
  checked: boolean;
  disabled: boolean;
  onToggle: () => void;
  onRun: (fn: (ids: string[]) => Promise<ActionResult>) => void;
  pending: boolean;
}) {
  const c = a.details.classification;
  const Icon = a.kind === "move" ? FolderInput : a.kind === "delete" ? Trash2 : Zap;
  return (
    <li className={`flex gap-3 px-4 py-3 ${checked ? "bg-indigo-500/5" : ""}`}>
      <input type="checkbox" className="mt-1 size-4 accent-indigo-600" checked={checked} disabled={disabled} onChange={onToggle} />
      <Icon className="mt-0.5 size-4 shrink-0 text-muted" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <KindBadge kind={a.kind} />
          <StatusBadge status={a.status} />
          {a.category && <span className="badge bg-surface-muted text-muted">{a.category}</span>}
          {a.tags.slice(0, 4).map((t) => (
            <span key={t} className="badge bg-surface-muted text-muted">
              #{t}
            </span>
          ))}
        </div>

        <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          <span className="truncate font-medium" title={a.src_path}>
            {fileName(a.src_path)}
          </span>
          {a.kind === "move" && a.dst_path && (
            <>
              <ArrowRight className="size-3.5 shrink-0 text-muted" />
              <span className="truncate font-medium text-indigo-600 dark:text-indigo-300" title={a.dst_path}>
                {fileName(a.dst_path)}
              </span>
            </>
          )}
        </div>
        <div className="mt-0.5 truncate font-mono text-xs text-muted" title={a.src_path}>
          {a.kind === "move" && a.dst_path ? `${dirName(a.src_path)} → ${dirName(a.dst_path)}` : dirName(a.src_path)}
        </div>

        <div className="mt-1 text-xs text-muted">
          {a.reason}
          {a.details.duplicate_of && (
            <span className="ml-1 inline-flex items-center gap-1">
              <Copy className="size-3" /> Original: <span className="font-mono">{a.details.duplicate_of}</span>
            </span>
          )}
          {a.kind === "compress" && (
            <span className="ml-1">
              {formatBytes(a.details.size_before as number)} →{" "}
              {formatBytes((a.details.size_after ?? a.details.size_after_estimate) as number)}
            </span>
          )}
          {c?.summary && <span className="ml-1 italic">„{c.summary}“</span>}
        </div>
        {a.error && <div className="mt-1 text-xs text-rose-600">{a.error}</div>}
      </div>

      <div className="flex shrink-0 flex-col items-end gap-2">
        <ConfidenceBar value={a.confidence} />
        <span className="text-xs text-muted">{formatDate(a.applied_at ?? a.created_at)}</span>
        {mode === "review" && ["proposed", "failed"].includes(a.status) && (
          <div className="flex gap-1">
            <button className="btn btn-sm" title="Freigeben" disabled={pending} onClick={() => onRun(approveActions)}>
              <Check className="size-3.5 text-emerald-600" />
            </button>
            <button className="btn btn-sm" title="Ablehnen" disabled={pending} onClick={() => onRun(rejectActions)}>
              <X className="size-3.5 text-rose-600" />
            </button>
          </div>
        )}
        {mode === "history" && a.status === "applied" && (
          <button className="btn btn-sm" disabled={pending} onClick={() => onRun(requestUndo)}>
            <Undo2 className="size-3.5" /> Undo
          </button>
        )}
      </div>
    </li>
  );
}
