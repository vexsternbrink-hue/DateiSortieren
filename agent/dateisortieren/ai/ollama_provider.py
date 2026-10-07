"""Klassifizierung über ein lokales LLM mit Ollama – keine Daten verlassen den Rechner."""

from __future__ import annotations

import httpx

from ..extract import IMAGE_EXTENSIONS
from ..models import Classification
from .base import SYSTEM_PROMPT, AIProvider, AIResult, FileContext, build_user_prompt, image_as_jpeg_base64, to_classification

DEFAULT_MODEL = "llama3.2"


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.model = cfg.ai.model or DEFAULT_MODEL
        self.url = cfg.ai.ollama_url.rstrip("/") + "/api/chat"

    def classify(self, ctx: FileContext, extra_categories: list[str]) -> Classification:
        message: dict = {"role": "user", "content": build_user_prompt(ctx, self.cfg, extra_categories)}
        if self.cfg.ai.send_files and not ctx.text and ctx.ext in IMAGE_EXTENSIONS:
            data = image_as_jpeg_base64(ctx.path, max_side=1024)
            if data:
                message["images"] = [data]  # nur relevant für Vision-Modelle (z. B. llava, llama3.2-vision)
        response = httpx.post(
            self.url,
            json={
                "model": self.model,
                "stream": False,
                "format": AIResult.model_json_schema(),
                "options": {"temperature": 0},
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}, message],
            },
            timeout=self.cfg.ai.timeout_seconds,
        )
        response.raise_for_status()
        result = AIResult.model_validate_json(response.json()["message"]["content"])
        return to_classification(result, f"ollama:{self.model}")
