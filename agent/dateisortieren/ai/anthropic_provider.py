"""Klassifizierung über die Anthropic API (Claude) mit Structured Outputs."""

from __future__ import annotations

import base64
from typing import Any

from ..extract import IMAGE_EXTENSIONS
from ..models import Classification
from .base import SYSTEM_PROMPT, AIProvider, AIResult, FileContext, build_user_prompt, image_as_jpeg_base64, to_classification

DEFAULT_MODEL = "claude-opus-5-5"
MAX_PDF_BYTES = 20 * 1024 * 1024


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(self, cfg):
        super().__init__(cfg)
        import anthropic  # liest ANTHROPIC_API_KEY aus der Umgebung

        self.client = anthropic.Anthropic(timeout=cfg.ai.timeout_seconds)
        self.model = cfg.ai.model or DEFAULT_MODEL

    def _content(self, ctx: FileContext, extra_categories: list[str]) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        if self.cfg.ai.send_files and not ctx.text:
            if ctx.ext == ".pdf" and ctx.size <= MAX_PDF_BYTES:
                # Claude liest PDFs nativ (inkl. gescannter Seiten) – kein lokales OCR nötig
                data = base64.standard_b64encode(ctx.path.read_bytes()).decode()
                blocks.append({"type": "document",
                               "source": {"type": "base64", "media_type": "application/pdf", "data": data}})
            elif ctx.ext in IMAGE_EXTENSIONS:
                data = image_as_jpeg_base64(ctx.path)
                if data:
                    blocks.append({"type": "image",
                                   "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
        blocks.append({"type": "text", "text": build_user_prompt(ctx, self.cfg, extra_categories)})
        return blocks

    def classify(self, ctx: FileContext, extra_categories: list[str]) -> Classification:
        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            output_config={"effort": self.cfg.ai.effort},
            # Falls ein Sicherheitsfilter ablehnt, übernimmt serverseitig automatisch ein Ausweichmodell
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": self._content(ctx, extra_categories)}],
            output_format=AIResult,
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise RuntimeError(f"Claude hat keine verwertbare Antwort geliefert (stop_reason={response.stop_reason})")
        return to_classification(response.parsed_output, f"anthropic:{response.model}")
