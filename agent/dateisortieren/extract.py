"""Text-Extraktion aus Dokumenten (PDF, DOCX, Text) inkl. optionaler OCR."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .config import Config

log = logging.getLogger(__name__)

TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm", ".rtf", ".log", ".eml"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".odt", ".doc"} | TEXT_EXTENSIONS


def extract_text(path: Path, cfg: Config) -> str:
    """Liefert den (gekürzten) Textinhalt einer Datei – leerer String, wenn nicht lesbar."""
    ext = path.suffix.lower()
    limit = cfg.ai.max_chars
    try:
        if ext == ".pdf":
            text = _pdf_text(path, cfg.ocr.max_pages + 2)
            if len(text.strip()) < 40 and cfg.ocr.enabled:
                text = _ocr_pdf(path, cfg) or text
        elif ext == ".docx":
            text = _docx_text(path)
        elif ext in TEXT_EXTENSIONS:
            text = path.read_text(encoding="utf-8", errors="ignore")[: limit * 2]
        elif ext in IMAGE_EXTENSIONS and cfg.ocr.enabled:
            text = _ocr_image(path, cfg)
        else:
            text = ""
    except Exception as exc:  # noqa: BLE001 – defekte Dateien dürfen den Agenten nicht stoppen
        log.warning("Text-Extraktion fehlgeschlagen für %s: %s", path, exc)
        text = ""
    return " ".join(text.split())[:limit]


def _pdf_text(path: Path, max_pages: int) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages[:max_pages]:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _docx_text(path: Path) -> str:
    try:
        import docx  # python-docx
    except ImportError:
        return ""
    document = docx.Document(str(path))
    return "\n".join(p.text for p in document.paragraphs)


def ocr_available() -> bool:
    if shutil.which("tesseract") is None:
        return False
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return True


def _ocr_image(path: Path, cfg: Config) -> str:
    if not ocr_available():
        return ""
    import pytesseract
    from PIL import Image

    with Image.open(path) as img:
        return pytesseract.image_to_string(img, lang=cfg.ocr.languages)


def _ocr_pdf(path: Path, cfg: Config) -> str:
    if not ocr_available():
        return ""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        log.info("pdf2image nicht installiert – OCR für PDFs übersprungen")
        return ""
    import pytesseract

    pages = convert_from_path(str(path), dpi=200, first_page=1, last_page=cfg.ocr.max_pages)
    return "\n".join(pytesseract.image_to_string(p, lang=cfg.ocr.languages) for p in pages)
