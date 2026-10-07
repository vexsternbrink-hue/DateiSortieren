"""Daemon: überwacht Ordner mit watchdog, synchronisiert mit dem Dashboard und plant regelmäßige Scans."""

from __future__ import annotations

import logging
import signal
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .service import Agent
from .sync import CloudError

log = logging.getLogger(__name__)


class _Handler(FileSystemEventHandler):
    def __init__(self, daemon: "Daemon"):
        self.daemon = daemon

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self.daemon.enqueue(Path(str(event.src_path)))

    def on_moved(self, event: FileSystemEvent) -> None:
        # z. B. Browser benennt "datei.pdf.crdownload" -> "datei.pdf" um
        if not event.is_directory:
            self.daemon.enqueue(Path(str(event.dest_path)))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory and str(event.src_path) in self.daemon.pending:
            self.daemon.enqueue(Path(str(event.src_path)))


class Daemon:
    def __init__(self, agent: Agent):
        self.agent = agent
        self.cfg = agent.cfg
        self.pending: dict[str, tuple[float, int]] = {}  # Pfad -> (letzte Änderung, Größe)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._scan_now = threading.Event()

    def _ignored(self, path: Path) -> bool:
        s = str(path)
        if s in self.agent.executor.busy_paths:
            return True
        for root in (self.cfg.state_dir, self.cfg.target_root):
            if path == root or root in path.parents:
                return True
        return path.name.startswith(".~") or path.name.endswith((".tmp", ".swp"))

    def enqueue(self, path: Path) -> None:
        if self._ignored(path):
            return
        try:
            size = path.stat().st_size
        except OSError:
            return
        with self._lock:
            self.pending[str(path)] = (time.monotonic(), size)

    def _settled(self) -> list[Path]:
        """Dateien, deren Größe sich `settle_seconds` lang nicht geändert hat (Download fertig)."""
        ready: list[Path] = []
        now = time.monotonic()
        with self._lock:
            for key, (seen, size) in list(self.pending.items()):
                path = Path(key)
                try:
                    current = path.stat().st_size
                except OSError:
                    del self.pending[key]
                    continue
                if current != size:
                    self.pending[key] = (now, current)
                elif now - seen >= self.cfg.settle_seconds:
                    ready.append(path)
                    del self.pending[key]
        return ready

    # ---------------------------------------------------------------- loops
    def _file_loop(self) -> None:
        while not self._stop.is_set():
            for path in self._settled():
                try:
                    actions = self.agent.handle_file(path)
                    for a in actions:
                        log.info("[%s] %s %s -> %s (%s)", a.status, a.kind, Path(a.src).name,
                                 Path(a.dst).name if a.dst else "", a.reason)
                except Exception:  # noqa: BLE001
                    log.exception("Fehler bei %s", path)
            self._stop.wait(1.0)

    def _cloud_loop(self) -> None:
        last_heartbeat = 0.0
        while not self._stop.is_set():
            if self.agent.cloud:
                now = time.monotonic()
                if now - last_heartbeat >= self.cfg.cloud.heartbeat_interval_seconds:
                    last_heartbeat = now
                    try:
                        reply = self.agent.cloud.heartbeat({"stats": self.agent.manifest.stats()})
                        if reply.get("scan_requested"):
                            log.info("Scan wurde im Dashboard angefordert")
                            self._scan_now.set()
                        self.agent.sync_config()
                    except CloudError as exc:
                        log.warning("Heartbeat fehlgeschlagen: %s", exc)
                try:
                    self.agent.process_commands()
                except Exception:  # noqa: BLE001
                    log.exception("Fehler beim Verarbeiten der Dashboard-Befehle")
            self._stop.wait(self.cfg.cloud.poll_interval_seconds)

    def _scan_loop(self) -> None:
        last_purge = 0.0
        while not self._stop.is_set():
            try:
                plan = self.agent.scan()
                log.info("Scan abgeschlossen: %d Vorschläge", len(plan))
                if time.monotonic() - last_purge > 86400:
                    removed = self.agent.executor.purge_trash()
                    last_purge = time.monotonic()
                    if removed:
                        log.info("Quarantäne bereinigt: %d Einträge endgültig gelöscht", removed)
            except Exception:  # noqa: BLE001
                log.exception("Scan fehlgeschlagen")
            self._scan_now.wait(self.cfg.scan_interval_minutes * 60)
            self._scan_now.clear()

    def run(self) -> None:
        self.agent.sync_config()
        observer = Observer()
        handler = _Handler(self)
        for d in self.cfg.watch_dirs:
            if d.exists():
                observer.schedule(handler, str(d), recursive=self.cfg.recursive)
                log.info("Überwache %s", d)
            else:
                log.warning("Ordner existiert nicht und wird ignoriert: %s", d)
        observer.start()

        threads = [threading.Thread(target=t, daemon=True, name=t.__name__)
                   for t in (self._file_loop, self._cloud_loop, self._scan_loop)]
        for t in threads:
            t.start()
        mode = "DRY-RUN (nur Vorschläge)" if self.cfg.dry_run else "AUTOMATISCH"
        log.info("Agent läuft – Modus: %s, KI: %s, Dashboard: %s", mode, self.cfg.ai.provider,
                 self.cfg.cloud.api_url or "nicht verbunden")
        self.agent.log_remote("info", f"Agent gestartet ({mode})")

        def _shutdown(*_args) -> None:
            self._stop.set()
            self._scan_now.set()

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
        try:
            while not self._stop.is_set():
                self._stop.wait(1.0)
        finally:
            observer.stop()
            observer.join(timeout=5)
            self.agent.log_remote("info", "Agent gestoppt")
            log.info("Agent gestoppt")
