"""Klassifizierung: Nutzer-Regeln -> KI-Provider -> Heuristik als Fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import rules as rules_mod
from .ai import FileContext, HeuristicProvider, get_provider
from .config import Config
from .extract import extract_text
from .models import Classification

log = logging.getLogger(__name__)


@dataclass
class ClassifiedFile:
    path: Path
    text: str
    classification: Classification
    rule: dict[str, Any] | None = None


class Classifier:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.heuristic = HeuristicProvider(cfg)
        self._provider = None
        self._provider_error: str | None = None

    @property
    def provider(self):
        if self._provider is None and self._provider_error is None:
            try:
                self._provider = get_provider(self.cfg)
            except Exception as exc:  # noqa: BLE001 – fehlender Key / Paket -> Heuristik
                self._provider_error = str(exc)
                log.warning("KI-Provider '%s' nicht verfügbar (%s) – nutze Heuristik", self.cfg.ai.provider, exc)
        return self._provider or self.heuristic

    def _extra_categories(self) -> list[str]:
        cats = []
        for rule in self.cfg.rules:
            target = (rule.get("target") or "").split("{")[0].strip("/")
            if target:
                cats.append(target)
        return cats

    def classify(self, path: Path) -> ClassifiedFile:
        stat = path.stat()
        text = extract_text(path, self.cfg)
        ctx = FileContext(
            path=path, text=text, size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).date().isoformat(),
        )
        ordered = rules_mod.sorted_rules(self.cfg.rules)

        # 1) Regeln ohne Kategorie-Bedingung: sparen den KI-Aufruf komplett
        for rule in ordered:
            if not rules_mod.needs_category(rule) and rules_mod.matches(rule, path, text, stat.st_size):
                base = self.heuristic.classify(ctx, [])
                return ClassifiedFile(path, text, self._apply_rule(base, rule), rule)

        # 2) KI (oder Heuristik)
        provider = self.provider
        try:
            classification = provider.classify(ctx, self._extra_categories())
        except Exception as exc:  # noqa: BLE001
            log.warning("KI-Klassifizierung fehlgeschlagen für %s: %s – nutze Heuristik", path.name, exc)
            classification = self.heuristic.classify(ctx, [])
            classification.source = f"heuristic (Fallback: {type(exc).__name__})"

        # 3) Regeln, die auf die erkannte Kategorie reagieren
        for rule in ordered:
            if rules_mod.needs_category(rule) and rules_mod.matches(rule, path, text, stat.st_size,
                                                                   classification.category):
                return ClassifiedFile(path, text, self._apply_rule(classification, rule), rule)
        return ClassifiedFile(path, text, classification)

    @staticmethod
    def _apply_rule(c: Classification, rule: dict[str, Any]) -> Classification:
        target = rule.get("target")
        if target:
            # Platzhalter wie {year} gehören in den Zielpfad, nicht in die Kategorie
            c.category = target.split("{")[0].strip("/") or c.category
        c.tags = list(dict.fromkeys([*c.tags, *(rule.get("tags") or [])]))
        c.confidence = max(c.confidence, 0.95)
        c.source = f"rule:{rule.get('name', '?')}"
        return c
