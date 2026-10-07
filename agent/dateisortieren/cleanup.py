"""Smart Trash & Cleanup: temporäre Dateien, alte Installer, abgebrochene Downloads, leere Ordner."""

from __future__ import annotations

import fnmatch
import os
import time
from dataclasses import dataclass
from pathlib import Path

from .config import Config


@dataclass
class CleanupCandidate:
    path: Path
    category: str  # temp | installer | incomplete | empty_dir
    reason: str


def _age_hours(path: Path, now: float) -> float:
    return (now - path.stat().st_mtime) / 3600


def classify_file(path: Path, cfg: Config, now: float | None = None) -> CleanupCandidate | None:
    c = cfg.cleanup
    if not c.enabled:
        return None
    now = now or time.time()
    name, ext = path.name, path.suffix.lower()
    try:
        age = _age_hours(path, now)
    except OSError:
        return None

    if ext in {e.lower() for e in c.incomplete_extensions}:
        if age >= c.incomplete_max_age_hours:
            return CleanupCandidate(path, "incomplete", f"Abgebrochener Download, seit {age:.0f} h unverändert")
        return None
    if any(fnmatch.fnmatch(name, pat) for pat in c.temp_patterns):
        if age >= c.temp_max_age_hours or name in {".DS_Store", "Thumbs.db", "desktop.ini"}:
            return CleanupCandidate(path, "temp", "Temporäre Datei / Systemdatei")
        return None
    if ext in {e.lower() for e in c.installer_extensions}:
        days = age / 24
        if days >= c.installer_max_age_days:
            return CleanupCandidate(path, "installer", f"Installer, {days:.0f} Tage alt (Limit {c.installer_max_age_days})")
    return None


def is_incomplete_download(path: Path, cfg: Config) -> bool:
    return path.suffix.lower() in {e.lower() for e in cfg.cleanup.incomplete_extensions}


def find_empty_dirs(root: Path, cfg: Config) -> list[CleanupCandidate]:
    if not (cfg.cleanup.enabled and cfg.cleanup.remove_empty_dirs) or not root.is_dir():
        return []
    result: list[CleanupCandidate] = []
    empty: set[Path] = set()
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        current = Path(dirpath)
        if current == root:
            continue
        ignorable = {f for f in filenames if f in {".DS_Store", "Thumbs.db", "desktop.ini"}}
        children_empty = all((current / d) in empty for d in dirnames)
        if children_empty and len(filenames) == len(ignorable):
            empty.add(current)
    # Nur die obersten leeren Ordner vorschlagen (Unterordner wandern mit)
    for d in sorted(empty):
        if not any(parent in empty for parent in d.parents):
            result.append(CleanupCandidate(d, "empty_dir", "Leerer Ordner"))
    return result
