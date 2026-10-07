"""Konfiguration des lokalen Agenten (YAML + Umgebungsvariablen + Cloud-Overrides)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, PrivateAttr, field_validator

DEFAULT_STATE_DIR = Path(os.environ.get("DATEISORTIEREN_HOME", "~/.dateisortieren")).expanduser()
DEFAULT_CONFIG_PATH = DEFAULT_STATE_DIR / "config.yaml"


def _expand(value: str | Path) -> Path:
    return Path(os.path.expandvars(str(value))).expanduser()


class AIConfig(BaseModel):
    # heuristic = ohne KI (Schlüsselwörter), funktioniert immer offline
    provider: Literal["heuristic", "anthropic", "openai", "ollama"] = "heuristic"
    model: str | None = None
    effort: Literal["low", "medium", "high"] = "low"
    ollama_url: str = "http://localhost:11434"
    openai_base_url: str | None = None
    max_chars: int = 6000
    send_files: bool = True  # Bilder / gescannte PDFs direkt an das (Cloud-)Modell schicken
    custom_instructions: str = ""
    timeout_seconds: float = 60.0


class OCRConfig(BaseModel):
    enabled: bool = False
    languages: str = "deu+eng"
    max_pages: int = 3


class RenameConfig(BaseModel):
    enabled: bool = True
    only_cryptic: bool = True
    template: str = "{date}_{vendor}_{doc_type}_{amount}"


class OrganizeConfig(BaseModel):
    enabled: bool = True
    template: str = "{category}/{year}"
    min_confidence: float = 0.55
    unknown_category: str = "Unsortiert"


class DuplicateConfig(BaseModel):
    enabled: bool = True
    image_hash_distance: int = 5  # pHash Hamming-Distanz (0 = identisch)
    text_hash_distance: int = 3  # SimHash Hamming-Distanz für PDFs/Texte


class MediaConfig(BaseModel):
    enabled: bool = False
    image_min_kb: int = 300
    jpeg_quality: int = 85
    webp_quality: int = 80
    png_lossy: bool = False
    max_image_dimension: int | None = None
    video_enabled: bool = True
    video_min_mb: int = 50
    video_crf: int = 28
    video_preset: str = "medium"
    min_savings_percent: float = 10.0


class CleanupConfig(BaseModel):
    enabled: bool = True
    installer_max_age_days: int = 14
    incomplete_max_age_hours: int = 48
    temp_max_age_hours: int = 24
    remove_empty_dirs: bool = True
    auto_delete: bool = False  # Löschungen IMMER erst nach Freigabe, außer explizit erlaubt
    installer_extensions: list[str] = [".dmg", ".exe", ".msi", ".pkg", ".deb", ".rpm", ".appimage", ".msix"]
    incomplete_extensions: list[str] = [".crdownload", ".part", ".partial", ".download", ".opdownload", ".!ut"]
    temp_patterns: list[str] = ["~$*", "*.tmp", "*.temp", ".DS_Store", "Thumbs.db", "desktop.ini", "*.~lock*", "._*"]


class SafeListConfig(BaseModel):
    paths: list[str] = []
    globs: list[str] = []
    extensions: list[str] = []
    tags: list[str] = []


class TrashConfig(BaseModel):
    retention_days: int = 30


class CloudConfig(BaseModel):
    api_url: str = ""
    agent_token: str = ""
    poll_interval_seconds: int = 15
    heartbeat_interval_seconds: int = 60


class Config(BaseModel):
    watch_dirs: list[Path] = Field(default_factory=lambda: [_expand("~/Downloads")])
    target_root: Path = Field(default_factory=lambda: _expand("~/Dokumente/Sortiert"))
    state_dir: Path = DEFAULT_STATE_DIR
    dry_run: bool = True
    auto_apply_min_confidence: float = 0.85
    settle_seconds: float = 5.0
    scan_interval_minutes: int = 60
    recursive: bool = True
    ai: AIConfig = AIConfig()
    ocr: OCRConfig = OCRConfig()
    rename: RenameConfig = RenameConfig()
    organize: OrganizeConfig = OrganizeConfig()
    duplicates: DuplicateConfig = DuplicateConfig()
    media: MediaConfig = MediaConfig()
    cleanup: CleanupConfig = CleanupConfig()
    safelist: SafeListConfig = SafeListConfig()
    trash: TrashConfig = TrashConfig()
    cloud: CloudConfig = CloudConfig()
    # Regeln aus dem Dashboard (werden beim Sync gesetzt)
    rules: list[dict[str, Any]] = []
    _local_safelist: SafeListConfig | None = PrivateAttr(default=None)

    @field_validator("watch_dirs", mode="before")
    @classmethod
    def _expand_list(cls, v: Any) -> Any:
        return [_expand(p) for p in (v or [])]

    @field_validator("target_root", "state_dir", mode="before")
    @classmethod
    def _expand_path(cls, v: Any) -> Any:
        return _expand(v)

    @property
    def trash_dir(self) -> Path:
        return self.state_dir / "trash"

    @property
    def db_path(self) -> Path:
        return self.state_dir / "manifest.db"

    def ensure_dirs(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.trash_dir.mkdir(parents=True, exist_ok=True)

    def apply_cloud_settings(self, remote: dict[str, Any]) -> None:
        """Übernimmt Einstellungen, Regeln und Safe-List aus dem Web-Dashboard.

        API-Keys werden NIE aus der Cloud übernommen – die bleiben lokal.
        """
        settings = remote.get("settings") or {}
        if "dry_run" in settings:
            self.dry_run = bool(settings["dry_run"])
        if "auto_apply_min_confidence" in settings:
            self.auto_apply_min_confidence = float(settings["auto_apply_min_confidence"])
        if settings.get("ai_instructions") is not None:
            self.ai.custom_instructions = str(settings["ai_instructions"])
        if settings.get("rename_template"):
            self.rename.template = str(settings["rename_template"])
        if settings.get("organize_template"):
            self.organize.template = str(settings["organize_template"])
        if "installer_max_age_days" in settings:
            self.cleanup.installer_max_age_days = int(settings["installer_max_age_days"])
        for key, section in (("media_enabled", self.media), ("duplicates_enabled", self.duplicates),
                             ("cleanup_enabled", self.cleanup), ("rename_enabled", self.rename)):
            if key in settings:
                section.enabled = bool(settings[key])

        self.rules = [r for r in remote.get("rules") or [] if r.get("enabled", True)]

        # Lokale Safe-List (config.yaml) bleibt Basis, damit Cloud-Einträge sich nicht stapeln
        if self._local_safelist is None:
            self._local_safelist = self.safelist.model_copy(deep=True)
        local = self._local_safelist.model_copy(deep=True)
        for entry in remote.get("safelist") or []:
            kind, value = entry.get("kind"), entry.get("value")
            if not value:
                continue
            target = {"path": local.paths, "glob": local.globs, "extension": local.extensions, "tag": local.tags}.get(kind)
            if target is not None and value not in target:
                target.append(value)
        self.safelist = local


def load_env_file(path: Path) -> None:
    """Lädt KEY=VALUE-Zeilen (z. B. API-Keys) aus ~/.dateisortieren/.env, ohne bestehende Variablen zu überschreiben."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip().removeprefix("export ").strip(), value.strip().strip('"').strip("'"))


def load_config(path: Path | None = None) -> Config:
    load_env_file(DEFAULT_STATE_DIR / ".env")
    path = path or Path(os.environ.get("DATEISORTIEREN_CONFIG", DEFAULT_CONFIG_PATH)).expanduser()
    data: dict[str, Any] = {}
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg = Config.model_validate(data)
    # Umgebungsvariablen überschreiben die Datei (praktisch für Docker / CI)
    if os.environ.get("DATEISORTIEREN_API_URL"):
        cfg.cloud.api_url = os.environ["DATEISORTIEREN_API_URL"]
    if os.environ.get("DATEISORTIEREN_AGENT_TOKEN"):
        cfg.cloud.agent_token = os.environ["DATEISORTIEREN_AGENT_TOKEN"]
    if os.environ.get("DATEISORTIEREN_AI_PROVIDER"):
        cfg.ai.provider = os.environ["DATEISORTIEREN_AI_PROVIDER"]  # type: ignore[assignment]
    cfg.ensure_dirs()
    return cfg
