from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from dateisortieren.config import Config


@pytest.fixture()
def cfg(tmp_path: Path) -> Config:
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    config = Config(
        watch_dirs=[downloads],
        target_root=tmp_path / "Sortiert",
        state_dir=tmp_path / "state",
    )
    config.ensure_dirs()
    return config


def make_file(path: Path, content: str | bytes = "x", age_hours: float = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    if age_hours:
        ts = time.time() - age_hours * 3600
        os.utime(path, (ts, ts))
    return path


INVOICE_TEXT = (
    "Telekom Deutschland GmbH Rechnung Rechnungsnummer 123456 Rechnungsdatum 12.09.2026 "
    "Ihre Rechnung für September. Mobilfunk Grundgebühr. Gesamtbetrag 89,00 € zahlbar bis 30.09.2026. "
    "USt-IdNr DE123456789. Vielen Dank für Ihren Auftrag und freundliche Grüße aus Bonn heute."
)
