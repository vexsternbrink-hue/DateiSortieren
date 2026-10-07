"""KI-Provider: heuristic (offline), anthropic, openai, ollama (lokal)."""

from __future__ import annotations

from ..config import Config
from .base import AIProvider, AIResult, FileContext
from .heuristic import HeuristicProvider


def get_provider(cfg: Config) -> AIProvider:
    provider = cfg.ai.provider
    if provider == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(cfg)
    if provider == "openai":
        from .openai_provider import OpenAIProvider

        return OpenAIProvider(cfg)
    if provider == "ollama":
        from .ollama_provider import OllamaProvider

        return OllamaProvider(cfg)
    return HeuristicProvider(cfg)


__all__ = ["AIProvider", "AIResult", "FileContext", "HeuristicProvider", "get_provider"]
