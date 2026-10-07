"""Safe-List / Whitelist: Pfade, Muster, Endungen und Tags, die niemals angefasst werden."""

from __future__ import annotations

import fnmatch
from pathlib import Path

from .config import Config

IGNORE_MARKER = ".dateisortieren-ignore"


class SafeList:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    @property
    def _sl(self):
        return self.cfg.safelist

    def _protected_roots(self) -> list[Path]:
        roots = [Path(p).expanduser() for p in self._sl.paths]
        roots.append(self.cfg.state_dir)  # eigene Daten (Manifest, Papierkorb) nie anfassen
        return roots

    def is_protected(self, path: Path) -> str | None:
        """Gibt den Grund zurück, falls der Pfad geschützt ist, sonst None."""
        path = Path(path).expanduser()
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        for root in self._protected_roots():
            try:
                root_resolved = root.resolve()
            except OSError:
                root_resolved = root
            if resolved == root_resolved or root_resolved in resolved.parents:
                return f"Geschützter Pfad: {root}"

        name = path.name
        for pattern in self._sl.globs:
            if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(str(path), pattern):
                return f"Geschütztes Muster: {pattern}"

        ext = path.suffix.lower()
        exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in self._sl.extensions}
        if ext and ext in exts:
            return f"Geschützte Dateiendung: {ext}"

        # Ordner mit Marker-Datei werden komplett ignoriert
        for parent in [path.parent, *path.parent.parents]:
            if (parent / IGNORE_MARKER).exists():
                return f"Ordner enthält {IGNORE_MARKER}"
            if parent in self.cfg.watch_dirs or parent == parent.parent:
                break
        return None

    def protected_tags(self, tags: list[str]) -> list[str]:
        wanted = {t.lower() for t in self._sl.tags}
        return [t for t in tags if t.lower() in wanted]
