"""Duplikat-Erkennung: exakt (SHA-256) und inhaltlich ähnlich (pHash für Bilder, SimHash für Texte/PDFs)."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .extract import IMAGE_EXTENSIONS, extract_text
from .manifest import Manifest

log = logging.getLogger(__name__)

TEXT_SIMILARITY_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def image_phash(path: Path) -> str | None:
    try:
        import imagehash
        from PIL import Image

        with Image.open(path) as img:
            return str(imagehash.phash(img))
    except Exception:  # noqa: BLE001 – kein imagehash / defektes Bild
        return None


def simhash(text: str, width: int = 64) -> str | None:
    words = re.findall(r"\w+", text.lower())
    if len(words) < 20:
        return None
    shingles = [" ".join(words[i:i + 3]) for i in range(len(words) - 2)]
    vector = [0] * width
    for sh in shingles:
        h = int.from_bytes(hashlib.md5(sh.encode()).digest()[:8], "big")
        for bit in range(width):
            vector[bit] += 1 if h >> bit & 1 else -1
    value = sum(1 << bit for bit in range(width) if vector[bit] > 0)
    return f"{value:016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


@dataclass
class DuplicateMatch:
    original: Path
    kind: str  # exact | image | text
    distance: int = 0

    @property
    def label(self) -> str:
        return {"exact": "identisch (SHA-256)", "image": f"visuell ähnlich (pHash Δ{self.distance})",
                "text": f"inhaltlich ähnlich (SimHash Δ{self.distance})"}[self.kind]


class DuplicateIndex:
    """Persistenter Fingerabdruck-Index im Manifest."""

    def __init__(self, cfg: Config, manifest: Manifest):
        self.cfg = cfg
        self.manifest = manifest

    def fingerprint(self, path: Path, text: str | None = None) -> dict[str, str | None]:
        stat = path.stat()
        cached = self.manifest.index_get(str(path))
        if cached and cached["size"] == stat.st_size and abs(cached["mtime"] - stat.st_mtime) < 1:
            return {"sha256": cached["sha256"], "phash": cached["phash"], "simhash": cached["simhash"]}
        ext = path.suffix.lower()
        digest = sha256_file(path)
        phash = image_phash(path) if ext in IMAGE_EXTENSIONS else None
        shash = None
        if ext in TEXT_SIMILARITY_EXTENSIONS:
            shash = simhash(text if text is not None else extract_text(path, self.cfg))
        self.manifest.index_put(str(path), stat.st_size, stat.st_mtime, digest, phash, shash)
        return {"sha256": digest, "phash": phash, "simhash": shash}

    def find_duplicate(self, path: Path, text: str | None = None) -> DuplicateMatch | None:
        if not self.cfg.duplicates.enabled:
            return None
        fp = self.fingerprint(path, text)
        candidates: list[DuplicateMatch] = []
        for row in self.manifest.index_by_sha(fp["sha256"] or ""):
            other = Path(row["path"])
            if other != path and other.exists():
                candidates.append(DuplicateMatch(other, "exact"))
        if not candidates and fp["phash"]:
            for row in self.manifest.index_with("phash"):
                other = Path(row["path"])
                if other == path or not other.exists():
                    continue
                d = hamming(fp["phash"], row["phash"])
                if d <= self.cfg.duplicates.image_hash_distance:
                    candidates.append(DuplicateMatch(other, "image", d))
        if not candidates and fp["simhash"]:
            for row in self.manifest.index_with("simhash"):
                other = Path(row["path"])
                if other == path or not other.exists() or other.suffix.lower() != path.suffix.lower():
                    continue
                d = hamming(fp["simhash"], row["simhash"])
                if d <= self.cfg.duplicates.text_hash_distance:
                    candidates.append(DuplicateMatch(other, "text", d))
        if not candidates:
            return None
        # Behalte bevorzugt: Datei im Zielordner > ältere Datei > exakter Treffer
        return sorted(candidates, key=lambda m: (m.kind != "exact", m.distance, not self._in_target(m.original),
                                                 _mtime(m.original)))[0]

    def should_keep_other(self, path: Path, match: DuplicateMatch) -> bool:
        """True, wenn `path` gelöscht werden soll (und `match.original` behalten)."""
        if self._in_target(match.original) and not self._in_target(path):
            return True
        if self._in_target(path) and not self._in_target(match.original):
            return False
        # Ältere Datei bleibt; bei Gleichstand entscheidet der Pfad (deterministisch, nie beide löschen)
        return (_mtime(match.original), str(match.original)) < (_mtime(path), str(path))

    def _in_target(self, p: Path) -> bool:
        root = self.cfg.target_root
        return root == p or root in p.parents

    def build(self, files: list[Path]) -> None:
        for f in files:
            try:
                self.fingerprint(f)
            except OSError as exc:
                log.debug("Index übersprungen %s: %s", f, exc)


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return float("inf")
