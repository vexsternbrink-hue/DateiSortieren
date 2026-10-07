"""Individuelle Nutzer-Regeln aus dem Dashboard.

Beispiel:
    {
      "name": "Telekom-Rechnungen",
      "priority": 10,
      "match": {"extensions": [".pdf"], "name_contains": ["telekom"], "content_keywords": ["rechnung"]},
      "target": "Finanzen/Rechnungen/Telekom/{year}",
      "rename_template": "{date}_Telekom_Rechnung_{amount}",
      "tags": ["telekom"],
      "action": "move"            # move | ignore | delete
    }
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _norm_ext(e: str) -> str:
    e = e.strip().lower()
    return e if e.startswith(".") else f".{e}"


def needs_category(rule: dict[str, Any]) -> bool:
    return bool((rule.get("match") or {}).get("category_is"))


def matches(rule: dict[str, Any], path: Path, text: str, size: int, category: str | None = None) -> bool:
    m = rule.get("match") or {}
    name = path.name.lower()
    lowered_text = text.lower()

    exts = [_norm_ext(e) for e in m.get("extensions") or [] if e.strip()]
    if exts and path.suffix.lower() not in exts:
        return False
    contains = [s.lower() for s in m.get("name_contains") or [] if s.strip()]
    if contains and not any(s in name for s in contains):
        return False
    if m.get("name_regex"):
        try:
            if not re.search(m["name_regex"], path.name, re.IGNORECASE):
                return False
        except re.error:
            return False
    keywords = [k.lower() for k in m.get("content_keywords") or [] if k.strip()]
    if keywords and not any(k in lowered_text for k in keywords):
        return False
    if m.get("path_contains") and str(m["path_contains"]).lower() not in str(path).lower():
        return False
    if m.get("min_size_kb") and size < float(m["min_size_kb"]) * 1024:
        return False
    if m.get("max_size_kb") and size > float(m["max_size_kb"]) * 1024:
        return False
    if m.get("category_is"):
        if not category or not category.lower().startswith(str(m["category_is"]).lower()):
            return False
    # Eine Regel ganz ohne Bedingungen trifft nie (Schutz vor "alles verschieben")
    return any(m.get(k) for k in ("extensions", "name_contains", "name_regex", "content_keywords",
                                  "path_contains", "category_is", "min_size_kb", "max_size_kb"))


def sorted_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rules, key=lambda r: (r.get("priority", 100), r.get("name", "")))
