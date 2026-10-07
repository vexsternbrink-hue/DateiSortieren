"""Verbindung zum Web-Dashboard (Next.js API + Supabase).

Der Agent authentifiziert sich mit einem Agent-Token, das im Dashboard unter
"Agenten" erzeugt wird. Es werden nur Metadaten (Pfade, Vorschläge, Logs) übertragen –
niemals Dateiinhalte oder API-Keys.
"""

from __future__ import annotations

import logging
import platform
import socket
from typing import Any

import httpx

from . import __version__
from .config import Config
from .models import Action

log = logging.getLogger(__name__)


class CloudError(Exception):
    pass


class CloudClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.base = cfg.cloud.api_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base,
            headers={"Authorization": f"Bearer {cfg.cloud.agent_token}", "User-Agent": f"dateisortieren-agent/{__version__}"},
            timeout=30,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.base and self.cfg.cloud.agent_token)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(method, f"/api/agent/{path}", **kwargs)
        except httpx.HTTPError as exc:
            raise CloudError(f"Dashboard nicht erreichbar: {exc}") from exc
        if response.status_code == 401:
            raise CloudError("Agent-Token ungültig – bitte im Dashboard ein neues Token erzeugen")
        if response.status_code >= 400:
            raise CloudError(f"Dashboard-Fehler {response.status_code}: {response.text[:300]}")
        return response.json() if response.content else {}

    def get_config(self) -> dict[str, Any]:
        return self._request("GET", "config")

    def heartbeat(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "hostname": socket.gethostname(),
            "platform": f"{platform.system()} {platform.release()}",
            "version": __version__,
            "watch_dirs": [str(p) for p in self.cfg.watch_dirs],
            "target_root": str(self.cfg.target_root),
            "dry_run": self.cfg.dry_run,
            "ai_provider": self.cfg.ai.provider,
            **(extra or {}),
        }
        return self._request("POST", "heartbeat", json=payload)

    def push_actions(self, actions: list[Action]) -> None:
        if actions:
            self._request("POST", "actions", json={"actions": [a.to_cloud() for a in actions]})

    def fetch_commands(self) -> dict[str, Any]:
        """{'approved': [rows], 'undo': [rows], 'rejected': [ids]}"""
        return self._request("GET", "commands")

    def log(self, level: str, message: str, details: dict[str, Any] | None = None) -> None:
        try:
            self._request("POST", "logs", json={"level": level, "message": message, "details": details or {}})
        except CloudError as exc:
            log.debug("Log konnte nicht gesendet werden: %s", exc)
