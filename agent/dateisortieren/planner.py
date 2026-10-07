"""Planer: erzeugt aus Dateien eine Liste von Aktionen (Dry-Run), ohne etwas zu verändern."""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from . import cleanup, media
from .classifier import Classifier
from .config import Config
from .duplicates import DuplicateIndex
from .manifest import Manifest
from .models import Action, Plan
from .renamer import build_filename, build_target_dir, is_cryptic, unique_path
from .safelist import SafeList

log = logging.getLogger(__name__)


class Planner:
    def __init__(self, cfg: Config, manifest: Manifest, classifier: Classifier | None = None):
        self.cfg = cfg
        self.manifest = manifest
        self.safelist = SafeList(cfg)
        self.duplicates = DuplicateIndex(cfg, manifest)
        self.classifier = classifier or Classifier(cfg)

    # ------------------------------------------------------------------ files
    def _skip_dir(self, d: Path) -> bool:
        if d.name.startswith(".") or d == self.cfg.state_dir:
            return True
        if d == self.cfg.target_root:
            return True
        return self.safelist.is_protected(d) is not None

    def iter_files(self, roots: Iterable[Path]) -> Iterator[Path]:
        for root in roots:
            if not root.exists():
                log.warning("Ordner existiert nicht: %s", root)
                continue
            if not self.cfg.recursive:
                yield from (p for p in sorted(root.iterdir()) if p.is_file())
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                current = Path(dirpath)
                dirnames[:] = sorted(d for d in dirnames if not self._skip_dir(current / d))
                for name in sorted(filenames):
                    yield current / name

    def iter_target_files(self) -> Iterator[Path]:
        root = self.cfg.target_root
        if root.exists():
            for dirpath, _dirs, filenames in os.walk(root):
                for name in filenames:
                    yield Path(dirpath) / name

    # ------------------------------------------------------------------- plan
    def plan_directories(self, roots: list[Path] | None = None) -> Plan:
        roots = roots or self.cfg.watch_dirs
        plan = Plan()
        files = [f for f in self.iter_files(roots) if f.is_file() and not f.is_symlink()]
        if self.cfg.duplicates.enabled:
            # Index vorab aufbauen, damit Duplikate in beide Richtungen erkannt werden
            self.duplicates.build([*self.iter_target_files(), *files])
        reserved: set[str] = set()
        for f in files:
            for action in self.plan_file(f, reserved):
                plan.add(action)
        for root in roots:
            for cand in cleanup.find_empty_dirs(root, self.cfg):
                if self.safelist.is_protected(cand.path) or self.manifest.open_proposal_for(str(cand.path), "delete"):
                    continue
                plan.add(Action(kind="delete", src=str(cand.path), reason=cand.reason, confidence=1.0,
                                details={"cleanup": cand.category, "is_dir": True}))
        return plan

    def plan_file(self, path: Path, reserved: set[str] | None = None) -> list[Action]:
        reserved = reserved if reserved is not None else set()
        if not path.exists() or not path.is_file():
            return []
        protected = self.safelist.is_protected(path)
        if protected:
            log.debug("Übersprungen (%s): %s", protected, path)
            return []
        src = str(path)
        if self.manifest.open_proposal_for(src, "move") or self.manifest.open_proposal_for(src, "delete"):
            return []

        # 1) Aufräumen: temporäre Dateien, alte Installer, abgebrochene Downloads
        cand = cleanup.classify_file(path, self.cfg)
        if cand:
            return [Action(kind="delete", src=src, reason=cand.reason, confidence=1.0,
                           tags=["cleanup", cand.category], details={"cleanup": cand.category,
                                                                     "size": path.stat().st_size})]
        if cleanup.is_incomplete_download(path, self.cfg):
            return []  # Download läuft noch

        # 2) Inhalt verstehen
        try:
            classified = self.classifier.classify(path)
        except OSError as exc:
            log.warning("Konnte %s nicht lesen: %s", path, exc)
            return []
        c = classified.classification
        if self.safelist.protected_tags(c.tags):
            log.info("Übersprungen wegen geschütztem Tag %s: %s", self.safelist.protected_tags(c.tags), path.name)
            return []
        rule = classified.rule or {}
        details = {"classification": c.to_dict(), "original_name": path.name, "size": path.stat().st_size}
        if rule.get("action") == "ignore":
            return []
        if rule.get("action") == "delete":
            return [Action(kind="delete", src=src, reason=f"Regel '{rule.get('name')}'", confidence=c.confidence,
                           category=c.category, tags=c.tags, details={**details, "rule": rule.get("name")})]

        # 3) Duplikate
        if self.cfg.duplicates.enabled:
            try:
                match = self.duplicates.find_duplicate(path, classified.text)
            except OSError:
                match = None
            if match and self.duplicates.should_keep_other(path, match):
                return [Action(kind="delete", src=src, reason=f"Duplikat – {match.label}", confidence=1.0 if match.kind == "exact" else 0.8,
                               category=c.category, tags=["duplikat", *c.tags],
                               details={**details, "duplicate_of": str(match.original), "match": match.kind,
                                        "distance": match.distance})]

        actions: list[Action] = []
        # 4) Sortieren + Umbenennen
        final_path = path
        move = self._plan_move(path, classified, details, reserved)
        if move:
            actions.append(move)
            final_path = Path(move.dst)  # type: ignore[arg-type]

        # 5) Medien-Optimierung (wird nach dem Verschieben auf den neuen Pfad angewendet)
        compress = self._plan_compress(path, final_path)
        if compress:
            actions.append(compress)
        return actions

    def _plan_move(self, path: Path, classified, details: dict, reserved: set[str]) -> Action | None:
        if not self.cfg.organize.enabled and not self.cfg.rename.enabled:
            return None
        c = classified.classification
        rule = classified.rule or {}
        mtime = datetime.fromtimestamp(path.stat().st_mtime)

        if not rule and c.confidence < self.cfg.organize.min_confidence:
            c.category = self.cfg.organize.unknown_category

        target_dir = path.parent
        if self.cfg.organize.enabled:
            dir_template = self.cfg.organize.template
            if rule.get("target"):
                dir_template = rule["target"]
            target_dir = build_target_dir(c, dir_template, self.cfg.target_root, mtime)

        new_name = path.name
        rename_template = rule.get("rename_template") or self.cfg.rename.template
        should_rename = self.cfg.rename.enabled and (bool(rule.get("rename_template")) or not self.cfg.rename.only_cryptic
                                                      or is_cryptic(path.name))
        if should_rename and _is_document_like(path, c):
            new_name = build_filename(c, rename_template, path, mtime)

        dst = target_dir / new_name
        if dst == path:
            return None
        dst = unique_path(dst, reserved)
        reserved.add(str(dst))
        moved = dst.parent != path.parent
        renamed = dst.name != path.name
        verb = " + ".join(v for v, flag in (("verschieben", moved), ("umbenennen", renamed)) if flag)
        reason = f"{c.doc_type or 'Datei'} → {c.category} ({verb}; Quelle: {c.source})"
        return Action(kind="move", src=str(path), dst=str(dst), reason=reason, confidence=c.confidence,
                      category=c.category, tags=c.tags,
                      details={**details, "new_name": dst.name, "renamed": renamed, "moved": moved,
                               "rule": rule.get("name")})

    def _plan_compress(self, path: Path, final_path: Path) -> Action | None:
        try:
            kind = media.is_candidate(path, self.cfg)
        except OSError:
            return None
        if not kind:
            return None
        stat = path.stat()
        if self.manifest.is_optimized(str(path), stat.st_size, stat.st_mtime):
            return None
        with tempfile.TemporaryDirectory(dir=self.cfg.state_dir) as tmp:
            estimate = media.estimate_savings(path, self.cfg, Path(tmp))
        if not estimate:
            return None
        before, after = estimate
        saved_pct = 100 * (before - after) / before if before else 0
        if saved_pct < self.cfg.media.min_savings_percent:
            self.manifest.mark_optimized(str(path), stat.st_size, stat.st_mtime)
            return None
        label = "Bild" if kind == "image" else "Video"
        return Action(kind="compress", src=str(final_path), reason=f"{label} komprimieren: ca. {saved_pct:.0f}% kleiner",
                      confidence=0.9, tags=["optimierung", kind],
                      details={"media": kind, "size_before": before, "size_after_estimate": after,
                               "savings_percent": round(saved_pct, 1), "original_src": str(path)})


def _is_document_like(path: Path, c) -> bool:
    """Fotos/Videos behalten ihren Namen, außer die KI hat ein echtes Dokument erkannt (z. B. Foto einer Rechnung)."""
    from .extract import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS

    ext = path.suffix.lower()
    if ext in VIDEO_EXTENSIONS:
        return False
    if ext in IMAGE_EXTENSIONS:
        return not c.category.startswith(("Bilder", "Screenshots"))
    return True
