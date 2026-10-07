"""Zentrale Orchestrierung: Planen, Ausführen, Rückgängig machen, Cloud-Sync."""

from __future__ import annotations

import logging
from pathlib import Path

from .classifier import Classifier
from .config import Config
from .executor import Executor
from .manifest import Manifest
from .models import Action, Plan, new_id
from .planner import Planner
from .sync import CloudClient, CloudError

log = logging.getLogger(__name__)


class Agent:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.manifest = Manifest(cfg.db_path)
        self.classifier = Classifier(cfg)
        self.planner = Planner(cfg, self.manifest, self.classifier)
        self.executor = Executor(cfg, self.manifest)
        self.cloud = CloudClient(cfg) if cfg.cloud.api_url and cfg.cloud.agent_token else None

    # ----------------------------------------------------------------- cloud
    def sync_config(self) -> bool:
        if not self.cloud:
            return False
        try:
            self.cfg.apply_cloud_settings(self.cloud.get_config())
            return True
        except CloudError as exc:
            log.warning("Konfiguration aus dem Dashboard nicht geladen: %s", exc)
            return False

    def push(self) -> int:
        if not self.cloud:
            return 0
        pending = self.manifest.unsynced()
        if not pending:
            return 0
        try:
            self.cloud.push_actions(pending)
        except CloudError as exc:
            log.warning("Sync fehlgeschlagen: %s", exc)
            return 0
        self.manifest.mark_synced([a.id for a in pending])
        return len(pending)

    def log_remote(self, level: str, message: str, details: dict | None = None) -> None:
        if self.cloud:
            self.cloud.log(level, message, details)

    def process_commands(self) -> dict[str, int]:
        """Holt Freigaben / Undo-Wünsche aus dem Dashboard und führt sie aus."""
        stats = {"applied": 0, "failed": 0, "undone": 0}
        if not self.cloud:
            return stats
        try:
            commands = self.cloud.fetch_commands()
        except CloudError as exc:
            log.warning("Befehle konnten nicht geladen werden: %s", exc)
            return stats

        approved: list[Action] = []
        for row in commands.get("approved", []):
            local = self.manifest.get(row["id"]) or Action.from_cloud(row)
            if local.status in ("applied", "skipped", "undone"):
                self.manifest.save(local)  # Status erneut melden
                continue
            local.status = "approved"
            approved.append(local)
        for result in self.executor.apply_many(approved):
            stats["applied" if result.status in ("applied", "skipped") else "failed"] += 1

        to_undo: list[Action] = []
        for row in commands.get("undo", []):
            local = self.manifest.get(row["id"])
            if local is None:
                local = Action.from_cloud(row)
                local.status = "applied"
                local.error = "Aktion ist im lokalen Manifest unbekannt – Undo nicht möglich"
                self.manifest.save(local)
                stats["failed"] += 1
                continue
            if local.status == "undone":
                self.manifest.save(local)
                continue
            to_undo.append(local)
        # Rückwärts in Ausführungsreihenfolge (z. B. erst Komprimierung, dann Verschiebung zurücknehmen)
        for local in sorted(to_undo, key=lambda a: a.applied_at or "", reverse=True):
            result = self.executor.undo(local)
            stats["undone" if result.status == "undone" else "failed"] += 1

        for action_id in commands.get("rejected", []):
            local = self.manifest.get(action_id)
            if local and local.status == "proposed":
                local.status = "rejected"
                self.manifest.save(local, synced=True)

        if any(stats.values()):
            self.log_remote("info", f"Dashboard-Befehle ausgeführt: {stats['applied']} angewendet, "
                                    f"{stats['undone']} rückgängig, {stats['failed']} Fehler", stats)
        self.push()
        return stats

    # ------------------------------------------------------------- planning
    def scan(self, roots: list[Path] | None = None) -> Plan:
        plan = self.planner.plan_directories(roots)
        self.manifest.save_many(plan.actions)
        applied = self.auto_apply(plan.actions)
        if plan.actions:
            self.log_remote("info", f"Scan: {len(plan)} Vorschläge, {applied} automatisch ausgeführt",
                            {"batch_id": plan.batch_id})
        self.push()
        return plan

    def handle_file(self, path: Path) -> list[Action]:
        actions = self.planner.plan_file(path)
        if not actions:
            return []
        batch = new_id()
        for a in actions:
            a.batch_id = batch
        self.manifest.save_many(actions)
        self.auto_apply(actions)
        self.push()
        return actions

    def auto_apply(self, actions: list[Action]) -> int:
        """Ohne Dry-Run werden sichere Aktionen mit hoher Konfidenz sofort ausgeführt."""
        if self.cfg.dry_run:
            return 0
        eligible = [
            a for a in actions
            if a.status == "proposed"
            and a.confidence >= self.cfg.auto_apply_min_confidence
            and (a.kind != "delete" or self.cfg.cleanup.auto_delete)
        ]
        results = self.executor.apply_many(eligible)
        return sum(1 for r in results if r.status == "applied")

    # ------------------------------------------------------------ apply/undo
    def apply_ids(self, ids: list[str]) -> list[Action]:
        actions = [a for a in (self.manifest.get(i) for i in ids) if a]
        return self._apply_and_push(actions)

    def apply_all_proposed(self, batch_id: str | None = None) -> list[Action]:
        return self._apply_and_push(self.manifest.query(status="proposed", batch_id=batch_id, limit=100000))

    def _apply_and_push(self, actions: list[Action]) -> list[Action]:
        results = self.executor.apply_many(actions)
        self.push()
        return results

    def undo(self, target: str | None = None) -> list[Action]:
        """target = Aktions-ID, Batch-ID oder None (= letzter Batch)."""
        target = target or self.manifest.last_batch_id()
        if not target:
            return []
        action = self.manifest.get(target)
        results = [self.executor.undo(action)] if action else self.executor.undo_batch(target)
        self.push()
        return results

    def close(self) -> None:
        self.manifest.close()
