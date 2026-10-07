"""Führt Aktionen sicher aus und macht sie rückgängig.

Sicherheitsprinzipien:
- Es wird NIE etwas überschrieben (eindeutige Zielnamen).
- "Löschen" = Verschieben in die Quarantäne (~/.dateisortieren/trash) -> jederzeit wiederherstellbar.
- Komprimierung behält das Original in der Quarantäne, bis die Aufbewahrungsfrist abläuft.
- Jede Aktion wird vor und nach der Ausführung im Manifest protokolliert.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import threading
import time
from pathlib import Path

from . import media
from .config import Config
from .duplicates import sha256_file
from .manifest import Manifest
from .models import Action, now_iso
from .renamer import unique_path
from .safelist import SafeList

log = logging.getLogger(__name__)


class ActionError(Exception):
    pass


class Executor:
    def __init__(self, cfg: Config, manifest: Manifest):
        self.cfg = cfg
        self.manifest = manifest
        self.safelist = SafeList(cfg)
        # Pfade, die gerade vom Agenten selbst verändert werden (Watcher ignoriert diese Events)
        self.busy_paths: set[str] = set()
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ apply
    def apply(self, action: Action) -> Action:
        with self._lock:
            if action.status not in ("proposed", "approved", "failed"):
                raise ActionError(f"Aktion {action.id} hat Status '{action.status}' und kann nicht ausgeführt werden")
            try:
                src = self._resolve_current(Path(action.src))
                reason = self.safelist.is_protected(src)  # Safe-List kann sich seit dem Vorschlag geändert haben
                if reason:
                    raise ActionError(f"Abgebrochen – {reason}")
                if not src.exists():
                    raise ActionError(f"Quelle existiert nicht mehr: {src}")
                handler = {"move": self._apply_move, "delete": self._apply_delete, "compress": self._apply_compress}[action.kind]
                handler(action, src)
                if action.status not in ("skipped",):
                    action.status = "applied"
                action.error = None
                action.applied_at = now_iso()
            except Exception as exc:  # noqa: BLE001
                action.status = "failed"
                action.error = str(exc)
                log.error("Aktion fehlgeschlagen (%s %s): %s", action.kind, action.src, exc)
            self.manifest.save(action)
            return action

    def apply_many(self, actions: list[Action]) -> list[Action]:
        # Reihenfolge: erst verschieben, dann komprimieren, dann löschen (leere Ordner zuletzt)
        order = {"move": 0, "compress": 1, "delete": 2}
        ordered = sorted(actions, key=lambda a: (order[a.kind], bool(a.details.get("is_dir"))))
        return [self.apply(a) for a in ordered]

    def _resolve_current(self, path: Path) -> Path:
        """Folgt bereits ausgeführten Verschiebungen (z. B. Komprimierung nach dem Sortieren)."""
        seen = 0
        while not path.exists() and seen < 10:
            moved = [a for a in self.manifest.query(status="applied", limit=50) if a.kind == "move" and a.src == str(path)]
            if not moved:
                break
            path = Path(moved[0].dst)  # type: ignore[arg-type]
            seen += 1
        return path

    def _resolve_after_undo(self, path: Path) -> Path:
        """Findet eine Datei wieder, deren Verschiebung bereits rückgängig gemacht wurde."""
        if path.exists():
            return path
        for a in self.manifest.query(status="undone", limit=200):
            if a.kind == "move" and a.dst == str(path) and Path(a.src).exists():
                return Path(a.src)
        return path

    def _mark_busy(self, *paths: Path) -> None:
        for p in paths:
            self.busy_paths.add(str(p))

    def _release_busy(self, *paths: Path) -> None:
        def release() -> None:
            time.sleep(3)
            for p in paths:
                self.busy_paths.discard(str(p))

        threading.Thread(target=release, daemon=True).start()

    def _apply_move(self, action: Action, src: Path) -> None:
        if not action.dst:
            raise ActionError("Kein Ziel angegeben")
        dst = unique_path(Path(action.dst))
        dst.parent.mkdir(parents=True, exist_ok=True)
        self._mark_busy(src, dst)
        try:
            digest = sha256_file(src) if src.stat().st_size < 512 * 1024 * 1024 else None
            shutil.move(str(src), str(dst))
            if digest and sha256_file(dst) != digest:
                shutil.move(str(dst), str(src))
                raise ActionError("Prüfsumme nach dem Verschieben stimmt nicht – zurückgerollt")
        finally:
            self._release_busy(src, dst)
        action.src = str(src)
        action.dst = str(dst)
        action.details["sha256"] = digest
        self.manifest.index_rename(str(src), str(dst))

    def _quarantine_path(self, action: Action, src: Path) -> Path:
        target = self.cfg.trash_dir / action.id / src.name
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def _apply_delete(self, action: Action, src: Path) -> None:
        if action.details.get("is_dir") and any(p.is_file() and p.name not in {".DS_Store", "Thumbs.db", "desktop.ini"}
                                                for p in src.rglob("*")):
            raise ActionError("Ordner ist nicht mehr leer – nichts gelöscht")
        if action.details.get("duplicate_of"):
            # Das Original kann inzwischen einsortiert worden sein – der Verschiebung folgen
            original = self._resolve_current(Path(action.details["duplicate_of"]))
            if not original.exists():
                raise ActionError("Original des Duplikats existiert nicht mehr – nichts gelöscht")
            action.details["duplicate_of"] = str(original)
        backup = self._quarantine_path(action, src)
        self._mark_busy(src)
        try:
            shutil.move(str(src), str(backup))
        finally:
            self._release_busy(src)
        action.src = str(src)
        action.backup_path = str(backup)
        self.manifest.index_remove(str(src))

    def _apply_compress(self, action: Action, src: Path) -> None:
        before = src.stat().st_size
        with tempfile.TemporaryDirectory(dir=self.cfg.state_dir) as tmp:
            out = Path(tmp) / f"out{src.suffix.lower()}"
            media.compress(src, out, self.cfg)
            after = out.stat().st_size
            saved = 100 * (before - after) / before if before else 0
            if saved < self.cfg.media.min_savings_percent:
                action.status = "skipped"
                action.details.update(size_before=before, size_after=after, savings_percent=round(saved, 1))
                self.manifest.mark_optimized(str(src), before, src.stat().st_mtime)
                return
            backup = self._quarantine_path(action, src)
            self._mark_busy(src)
            try:
                shutil.copy2(src, backup)  # Original sichern
                shutil.copyfile(out, src)  # dann ersetzen (Metadaten/Zeitstempel des Originals bleiben)
                shutil.copystat(backup, src)
            finally:
                self._release_busy(src)
        stat = src.stat()
        self.manifest.mark_optimized(str(src), stat.st_size, stat.st_mtime)
        action.src = str(src)
        action.backup_path = str(backup)
        action.details.update(size_before=before, size_after=after, savings_percent=round(saved, 1))

    # ------------------------------------------------------------------- undo
    def undo(self, action: Action) -> Action:
        with self._lock:
            if action.status not in ("applied", "undo_requested"):
                raise ActionError(f"Nur ausgeführte Aktionen können rückgängig gemacht werden (Status: {action.status})")
            try:
                {"move": self._undo_move, "delete": self._undo_delete, "compress": self._undo_compress}[action.kind](action)
                action.status = "undone"
                action.undone_at = now_iso()
                action.error = None
            except Exception as exc:  # noqa: BLE001
                action.status = "applied"
                action.error = f"Undo fehlgeschlagen: {exc}"
                log.error("Undo fehlgeschlagen für %s: %s", action.id, exc)
            self.manifest.save(action)
            return action

    def undo_batch(self, batch_id: str) -> list[Action]:
        actions = self.manifest.query(status="applied", batch_id=batch_id, limit=10000, newest_first=True)
        return [self.undo(a) for a in actions]

    def _undo_move(self, action: Action) -> None:
        src, dst = Path(action.src), Path(action.dst or "")
        if not dst.exists():
            raise ActionError(f"Datei liegt nicht mehr am Ziel: {dst}")
        restore = src if not src.exists() else unique_path(src)
        restore.parent.mkdir(parents=True, exist_ok=True)
        self._mark_busy(dst, restore)
        try:
            shutil.move(str(dst), str(restore))
        finally:
            self._release_busy(dst, restore)
        self.manifest.index_rename(str(dst), str(restore))
        self._prune_empty_parents(dst.parent)

    def _undo_delete(self, action: Action) -> None:
        backup, src = Path(action.backup_path or ""), Path(action.src)
        if not backup.exists():
            raise ActionError("Quarantäne-Kopie existiert nicht mehr (Aufbewahrungsfrist abgelaufen?)")
        restore = src if not src.exists() else unique_path(src)
        restore.parent.mkdir(parents=True, exist_ok=True)
        self._mark_busy(restore)
        try:
            shutil.move(str(backup), str(restore))
        finally:
            self._release_busy(restore)
        _rmdir_quiet(backup.parent)

    def _undo_compress(self, action: Action) -> None:
        backup, src = Path(action.backup_path or ""), self._resolve_after_undo(Path(action.src))
        if not backup.exists():
            raise ActionError("Original existiert nicht mehr in der Quarantäne")
        self._mark_busy(src)
        try:
            shutil.copy2(backup, src)
            backup.unlink()
        finally:
            self._release_busy(src)
        _rmdir_quiet(backup.parent)

    def _prune_empty_parents(self, directory: Path) -> None:
        root = self.cfg.target_root
        while directory != root and root in directory.parents:
            try:
                directory.rmdir()
            except OSError:
                return
            directory = directory.parent

    # ------------------------------------------------------------------ trash
    def purge_trash(self) -> int:
        """Löscht Quarantäne-Einträge endgültig, die älter als die Aufbewahrungsfrist sind."""
        cutoff = time.time() - self.cfg.trash.retention_days * 86400
        removed = 0
        if not self.cfg.trash_dir.exists():
            return 0
        for entry in self.cfg.trash_dir.iterdir():
            try:
                if entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
                    removed += 1
            except OSError as exc:
                log.warning("Konnte %s nicht löschen: %s", entry, exc)
        return removed


def _rmdir_quiet(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass
