"""Prüft die Requests an die KI-Provider gegen einen simulierten HTTP-Server (kein API-Key nötig)."""

from __future__ import annotations

import json

import httpx
import pytest
from conftest import INVOICE_TEXT, make_file

from dateisortieren.ai.base import FileContext

RESULT = {
    "category": "Finanzen/Rechnungen", "doc_type": "Rechnung", "title": "Mobilfunkrechnung September",
    "vendor": "Telekom", "date": "2026-09-12", "amount": 89.0, "currency": "EUR",
    "tags": ["rechnung", "telekom"], "confidence": 0.97, "summary": "Telekom-Rechnung über 89 €.",
}


def _ctx(cfg, text=INVOICE_TEXT):
    path = make_file(cfg.watch_dirs[0] / "SCAN_2026_09_12.txt", text)
    return FileContext(path=path, text=text, size=path.stat().st_size, modified="2026-09-12")


def test_anthropic_request_and_parsing(cfg, monkeypatch):
    anthropic = pytest.importorskip("anthropic")
    from dateisortieren.ai.anthropic_provider import AnthropicProvider

    seen: dict = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": json.dumps(RESULT)}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 10},
        })

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    cfg.ai.provider = "anthropic"
    provider = AnthropicProvider(cfg)
    httpx2 = pytest.importorskip("httpx2")  # anthropic>=1.0 nutzt httpx2
    provider.client = anthropic.Anthropic(api_key="test", http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    result = provider.classify(_ctx(cfg), [])

    body = seen["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["headers"]["anthropic-beta"]
    assert body["output_config"]["effort"] == "low"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "<dateiinhalt>" in body["messages"][0]["content"][-1]["text"]
    assert result.vendor == "Telekom" and result.amount == 89.0 and result.category == "Finanzen/Rechnungen"


def test_anthropic_sends_scanned_pdf_as_document(cfg):
    pytest.importorskip("anthropic")
    from dateisortieren.ai.anthropic_provider import AnthropicProvider

    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.cfg = cfg
    pdf = make_file(cfg.watch_dirs[0] / "scan.pdf", b"%PDF-1.4 fake")
    blocks = provider._content(FileContext(pdf, "", pdf.stat().st_size, "2026-01-01"), [])
    assert blocks[0]["type"] == "document"
    assert blocks[0]["source"]["media_type"] == "application/pdf"


def test_ollama_request(cfg, monkeypatch):
    from dateisortieren.ai.ollama_provider import OllamaProvider

    captured = {}

    def fake_post(url, json=None, timeout=None):  # noqa: A002
        captured.update(url=url, body=json)
        return httpx.Response(200, json={"message": {"content": __import__("json").dumps(RESULT)}},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr("dateisortieren.ai.ollama_provider.httpx.post", fake_post)
    result = OllamaProvider(cfg).classify(_ctx(cfg), [])
    assert captured["url"].endswith("/api/chat")
    assert captured["body"]["format"]["type"] == "object"
    assert result.doc_type == "Rechnung"


def test_ai_failure_falls_back_to_heuristic(cfg):
    from dateisortieren.classifier import Classifier

    class Broken:
        def classify(self, *_a, **_k):
            raise RuntimeError("API down")

    path = make_file(cfg.watch_dirs[0] / "SCAN_2026_09_12.txt", INVOICE_TEXT)
    classifier = Classifier(cfg)
    classifier._provider = Broken()
    c = classifier.classify(path).classification
    assert c.category == "Finanzen/Rechnungen"
    assert c.source.startswith("heuristic (Fallback")
