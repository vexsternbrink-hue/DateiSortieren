"""Bild- und Video-Optimierung (lossless / lossy) mit Pillow und ffmpeg."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from .config import Config, MediaConfig

log = logging.getLogger(__name__)

IMAGE_FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
VIDEO_FORMATS = {".mp4", ".mov", ".m4v", ".mkv"}


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def is_candidate(path: Path, cfg: Config) -> str | None:
    """Liefert 'image' / 'video', wenn sich eine Optimierung lohnen könnte."""
    m = cfg.media
    if not m.enabled:
        return None
    ext = path.suffix.lower()
    size = path.stat().st_size
    if ext in IMAGE_FORMATS and size >= m.image_min_kb * 1024:
        return "image"
    if ext in VIDEO_FORMATS and m.video_enabled and size >= m.video_min_mb * 1024 * 1024 and ffmpeg_available():
        bitrate = _video_bitrate_kbps(path)
        if not bitrate or bitrate > 3000:  # bereits sparsam kodierte Videos auslassen
            return "video"
    return None


def estimate_savings(path: Path, cfg: Config, tmp_dir: Path) -> tuple[int, int] | None:
    """Für Bilder exakt (Probe-Komprimierung), für Videos eine Schätzung."""
    size = path.stat().st_size
    ext = path.suffix.lower()
    if ext in IMAGE_FORMATS:
        tmp = tmp_dir / f"probe{ext}"
        try:
            compress_image(path, tmp, cfg.media)
            new_size = tmp.stat().st_size
        except Exception as exc:  # noqa: BLE001
            log.debug("Probe-Komprimierung fehlgeschlagen %s: %s", path, exc)
            return None
        finally:
            tmp.unlink(missing_ok=True)
        return size, new_size
    bitrate = _video_bitrate_kbps(path)
    if bitrate:
        # grobe Schätzung: CRF 28 H.264 ≈ 2,5 Mbit/s für 1080p-Material
        target = min(bitrate, 2500)
        return size, int(size * target / bitrate)
    return size, int(size * 0.5)


def compress_image(src: Path, dst: Path, m: MediaConfig) -> None:
    from PIL import Image, ImageOps

    fmt = IMAGE_FORMATS[src.suffix.lower()]
    with Image.open(src) as img:
        exif = img.info.get("exif")
        icc = img.info.get("icc_profile")
        if m.max_image_dimension:
            img = ImageOps.exif_transpose(img)
            exif = None  # Ausrichtung bereits angewendet
            img.thumbnail((m.max_image_dimension, m.max_image_dimension))
        kwargs: dict = {}
        if icc:
            kwargs["icc_profile"] = icc
        if fmt == "JPEG":
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            kwargs.update(quality=m.jpeg_quality, optimize=True, progressive=True)
            if exif:
                kwargs["exif"] = exif
        elif fmt == "PNG":
            if m.png_lossy and img.mode in ("RGB", "RGBA"):
                img = img.quantize(colors=256, method=Image.Quantize.FASTOCTREE)
            kwargs.update(optimize=True)
        elif fmt == "WEBP":
            kwargs.update(quality=m.webp_quality, method=6)
            if exif:
                kwargs["exif"] = exif
        img.save(dst, format=fmt, **kwargs)


def compress_video(src: Path, dst: Path, m: MediaConfig) -> None:
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
        "-map", "0", "-map_metadata", "0",
        "-c:v", "libx264", "-crf", str(m.video_crf), "-preset", m.video_preset,
        "-c:a", "aac", "-b:a", "160k", "-c:s", "copy",
    ]
    if dst.suffix.lower() in {".mp4", ".m4v", ".mov"}:
        cmd += ["-movflags", "+faststart"]
    cmd.append(str(dst))
    subprocess.run(cmd, check=True, capture_output=True, timeout=60 * 60)


def compress(src: Path, dst: Path, cfg: Config) -> None:
    if src.suffix.lower() in IMAGE_FORMATS:
        compress_image(src, dst, cfg.media)
    else:
        compress_video(src, dst, cfg.media)


def _video_bitrate_kbps(path: Path) -> int | None:
    if shutil.which("ffprobe") is None:
        return None
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=bit_rate", "-of", "json", str(path)],
            check=True, capture_output=True, text=True, timeout=30,
        ).stdout
        return int(int(json.loads(out)["format"]["bit_rate"]) / 1000)
    except Exception:  # noqa: BLE001
        return None
