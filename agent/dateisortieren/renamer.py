"""Erzeugt lesbare Dateinamen und Zielpfade aus einer Klassifizierung.

    SCAN_2026_09_12.pdf  ->  2026-09-12_Telekom_Rechnung_89Euro.pdf
"""

from __future__ import annotations

import re
import string
import unicodedata
from datetime import datetime
from pathlib import Path

from .models import Classification

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_CRYPTIC_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^(scan|scanned|img|dsc|dscn|dcim|pxl|mvimg|photo|image|bild|doc|document|dokument|file|datei|download|"
        r"unbenannt|untitled|neu|new|print|druck|export|attachment|anhang|whatsapp|signal|telegram)"
        r"[\s_\-()]*[\d\s_\-.()]*$",
        r"^[\d\s_\-.()]+$",  # nur Ziffern/Datum
        r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$",  # UUID
        r"^[0-9a-f]{16,}$",  # Hash
        r"^[a-z0-9]{1,3}[\d_\-]{4,}$",
        r"^(rechnung|invoice|scan|dokument|document)[\s_\-]*\(?\d*\)?$",
    ]
]


def is_cryptic(name: str) -> bool:
    stem = Path(name).stem.strip()
    if len(stem) <= 3:
        return True
    return any(p.match(stem) for p in _CRYPTIC_PATTERNS)


def slug(value: str | None, max_len: int = 40) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFC", str(value)).strip()
    value = _INVALID.sub("", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[_]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-.")
    return value[:max_len].rstrip("-.")


def format_amount(amount: float | None, currency: str | None) -> str:
    if amount is None:
        return ""
    unit = {"EUR": "Euro", None: "Euro", "": "Euro"}.get(currency, (currency or "").upper())
    if float(amount).is_integer():
        return f"{int(amount)}{unit}"
    return f"{amount:.2f}".replace(".", ",") + unit


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


def template_fields(c: Classification, fallback_date: datetime) -> dict[str, str]:
    doc_date = None
    if c.date:
        try:
            doc_date = datetime.strptime(c.date[:10], "%Y-%m-%d")
        except ValueError:
            doc_date = None
    effective = doc_date or fallback_date
    return _SafeDict(
        date=doc_date.strftime("%Y-%m-%d") if doc_date else fallback_date.strftime("%Y-%m-%d"),
        year=effective.strftime("%Y"),
        month=effective.strftime("%m"),
        vendor=slug(c.vendor, 30),
        doc_type=slug(c.doc_type, 30),
        title=slug(c.title, 50),
        amount=format_amount(c.amount, c.currency),
        category=c.category,
    )


def build_filename(c: Classification, template: str, original: Path, fallback_date: datetime) -> str:
    fields = template_fields(c, fallback_date)
    raw = string.Formatter().vformat(template, (), fields)
    parts = [slug(p, 60) for p in raw.split("_")]
    stem = "_".join(p for p in parts if p)
    # Wenn außer dem Datum nichts übrig bleibt, den Titel/Originalnamen anhängen
    if not stem or stem == fields["date"]:
        extra = slug(c.title) or slug(original.stem)
        stem = "_".join(p for p in [fields["date"], extra] if p)
    return f"{stem[:120]}{original.suffix.lower()}"


def build_target_dir(c: Classification, template: str, root: Path, fallback_date: datetime) -> Path:
    fields = template_fields(c, fallback_date)
    rel = string.Formatter().vformat(template, (), fields)
    segments = (_INVALID.sub("", seg).strip(" .")[:60] for seg in rel.replace("\\", "/").split("/"))
    safe = [s for s in segments if s and s not in {".", ".."}]
    return root.joinpath(*safe) if safe else root


def unique_path(path: Path, reserved: set[str] | None = None) -> Path:
    """Hängt (1), (2)… an, damit nie etwas überschrieben wird."""
    reserved = reserved or set()
    candidate = path
    counter = 1
    while candidate.exists() or str(candidate) in reserved:
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        counter += 1
    return candidate
