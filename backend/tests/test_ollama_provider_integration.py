"""Tests for the self-hosted Ollama provider integration.

Covers:
- PROVIDER_SPECS["ollama"] env override resolution (OLLAMA_BASE_URL / OLLAMA_DEFAULT_MODEL).
- GET /api/dashboard/providers/ollama/models happy path (httpx-mocked).
- GET /api/dashboard/providers/ollama/models timeout path -> HTTP 504.
- openai_gateway "no API key required" path for provider="ollama".
- Optional live smoke test against OLLAMA_LIVE_URL (skipped by default).
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from types import ModuleType, SimpleNamespace

import httpx
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from app.adapters.ai.openai_gateway import AIGateway
from app.adapters.http.routers.llm_config import provider_settings as provider_settings_module
from app.main import app


# ---------------------------------------------------------------------------
# 1. Provider catalog env-override test
# ---------------------------------------------------------------------------
def test_ollama_provider_spec_respects_env_overrides(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://example.internal:90/v1")
    monkeypatch.setenv("OLLAMA_DEFAULT_MODEL", "gpt-oss:120b")

    # Reimport the catalog so the frozen dataclass picks up the patched env.
    sys.modules.pop("app.adapters.ai.provider_catalog", None)
    catalog = importlib.import_module("app.adapters.ai.provider_catalog")

    spec = catalog.get_provider_spec("ollama")
    assert spec.transport == "openai_compatible"
    assert spec.base_url == "http://example.internal:90/v1"
    assert spec.default_model == "gpt-oss:120b"
    assert spec.env_key == "OLLAMA_API_KEY"
    assert spec.status == "active"

    # Restore the module so other tests see the default spec.
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_DEFAULT_MODEL", raising=False)
    sys.modules.pop("app.adapters.ai.provider_catalog", None)
    importlib.import_module("app.adapters.ai.provider_catalog")


# ---------------------------------------------------------------------------
# httpx.AsyncClient test double (context-managed, single GET).
# ---------------------------------------------------------------------------
class _StubResponse:
    def __init__(self, status_code: int, payload: dict | None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _StubAsyncClient:
    def __init__(self, handler, captured_urls: list[str]):
        self._handler = handler
        self._captured = captured_urls

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, **_kwargs):
        self._captured.append(url)
        return await self._handler(url)


def _install_stub_httpx(monkeypatch, handler) -> list[str]:
    """Replace httpx.AsyncClient in the provider_settings module with a stub."""
    captured: list[str] = []

    def _factory(*_args, **_kwargs):
        return _StubAsyncClient(handler, captured)

    fake_httpx = SimpleNamespace(
        AsyncClient=_factory,
        TimeoutException=httpx.TimeoutException,
        HTTPError=httpx.HTTPError,
    )
    monkeypatch.setattr(provider_settings_module, "httpx", fake_httpx)
    return captured


# ---------------------------------------------------------------------------
# 2. /providers/ollama/models happy path
# ---------------------------------------------------------------------------
def test_get_ollama_models_normalizes_payload(monkeypatch):
    # Shape mirrors http://86.38.238.106:90/v1/models (trimmed to 5 entries).
    live_payload = {
        "object": "list",
        "data": [
            {"id": "llama3.2:3b", "owned_by": "library"},
            {"id": "gpt-oss:120b", "owned_by": "library"},
            {"id": "gemma4:31b-it-q8_0", "owned_by": "library"},
            {"id": "bge-m3:latest", "owned_by": "library"},
            {"id": "nomic-embed-text:latest", "owned_by": "library"},
        ],
    }

    async def _handler(url):
        assert url == "http://example.internal:90/v1/models"
        return _StubResponse(200, live_payload)

    captured = _install_stub_httpx(monkeypatch, _handler)

    with TestClient(app) as client:
        resp = client.get(
            "/api/dashboard/providers/ollama/models",
            params={"base_url": "http://example.internal:90/v1"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["base_url"] == "http://example.internal:90/v1"
    ids = [m["id"] for m in body["models"]]
    # Sorted ascending by id.
    assert ids == sorted(ids)
    assert len(ids) == 5
    assert "llama3.2:3b" in ids
    assert captured == ["http://example.internal:90/v1/models"]


# ---------------------------------------------------------------------------
# 3. /providers/ollama/models timeout -> 504
# ---------------------------------------------------------------------------
def test_get_ollama_models_timeout_returns_504(monkeypatch):
    async def _handler(_url):
        raise httpx.ConnectTimeout("boom")

    _install_stub_httpx(monkeypatch, _handler)

    with TestClient(app) as client:
        resp = client.get(
            "/api/dashboard/providers/ollama/models",
            params={"base_url": "http://unreachable.invalid:90/v1"},
        )

    assert resp.status_code == 504, resp.text
    detail = resp.json()["detail"]
    assert detail["family"] == "provider_unavailable"
    assert detail["provider"] == "ollama"
    assert detail["code"] == "LLM_PROVIDER_UNAVAILABLE"


def test_get_ollama_models_rejects_malformed_base_url(monkeypatch):
    # No scheme => caught by _resolve_ollama_base_url before any httpx call.
    with TestClient(app) as client:
        resp = client.get(
            "/api/dashboard/providers/ollama/models",
            params={"base_url": "not-a-url"},
        )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["family"] == "invalid_request"
    assert detail["provider"] == "ollama"


# ---------------------------------------------------------------------------
# 4. openai_gateway no-API-key path for provider="ollama"
# ---------------------------------------------------------------------------
class _FakeCompletions:
    async def create(self, **_kwargs):
        choice = SimpleNamespace(
            finish_reason="stop",
            message=SimpleNamespace(content="ok", tool_calls=None),
        )
        return SimpleNamespace(choices=[choice])


class _FakeAsyncOpenAI:
    instances: list["_FakeAsyncOpenAI"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.chat = SimpleNamespace(completions=_FakeCompletions())
        self.__class__.instances.append(self)


def test_gateway_accepts_ollama_without_api_key(monkeypatch):
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)

    fake_module = ModuleType("openai")
    fake_module.AsyncOpenAI = _FakeAsyncOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_module)
    _FakeAsyncOpenAI.instances.clear()

    gateway = AIGateway()
    asyncio.run(
        gateway.request_completion(
            messages=[{"role": "user", "content": "hello"}],
            provider="ollama",
            provider_base_url="http://example.internal:90/v1",
        )
    )

    assert len(_FakeAsyncOpenAI.instances) == 1
    client = _FakeAsyncOpenAI.instances[0]
    assert client.kwargs["api_key"] == "ollama"
    assert client.kwargs["base_url"] == "http://example.internal:90/v1"


# ---------------------------------------------------------------------------
# 5. Optional live smoke test (skipped unless OLLAMA_LIVE_URL is set)
# ---------------------------------------------------------------------------
@pytest.mark.live
@pytest.mark.skipif(
    not os.getenv("OLLAMA_LIVE_URL"),
    reason="OLLAMA_LIVE_URL not set; skipping live Ollama smoke test.",
)
def test_live_ollama_round_trip_says_pong():
    base_url = os.environ["OLLAMA_LIVE_URL"].rstrip("/")
    gateway = AIGateway()
    response = asyncio.run(
        gateway.request_completion(
            messages=[{"role": "user", "content": "Reply with the single word: PONG"}],
            provider="ollama",
            model="llama3.2:3b",
            provider_base_url=base_url,
        )
    )
    assert response.finish_reason == "stop"
    assert "PONG" in (response.content or "").upper()
