"""Klassifizierung über die OpenAI API (oder jeden OpenAI-kompatiblen Endpunkt, z. B. LM Studio)."""

from __future__ import annotations

from typing import Any

from ..extract import IMAGE_EXTENSIONS
from ..models import Classification
from .base import SYSTEM_PROMPT, AIProvider, AIResult, FileContext, build_user_prompt, image_as_jpeg_base64, to_classification

DEFAULT_MODEL = "gpt-4.1-mini"


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, cfg):
        super().__init__(cfg)
        import openai  # liest OPENAI_API_KEY aus der Umgebung

        kwargs: dict[str, Any] = {"timeout": cfg.ai.timeout_seconds}
        if cfg.ai.openai_base_url:
            kwargs["base_url"] = cfg.ai.openai_base_url
        self.client = openai.OpenAI(**kwargs)
        self.model = cfg.ai.model or DEFAULT_MODEL

    def classify(self, ctx: FileContext, extra_categories: list[str]) -> Classification:
        content: list[dict[str, Any]] = [{"type": "text", "text": build_user_prompt(ctx, self.cfg, extra_categories)}]
        if self.cfg.ai.send_files and not ctx.text and ctx.ext in IMAGE_EXTENSIONS:
            data = image_as_jpeg_base64(ctx.path)
            if data:
                content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}})
        completion = self.client.chat.completions.parse(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}],
            response_format=AIResult,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI hat keine verwertbare Antwort geliefert")
        return to_classification(parsed, f"openai:{self.model}")
