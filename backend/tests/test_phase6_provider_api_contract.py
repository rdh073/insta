"""Phase-6 API contract tests for provider capabilities and stable errors."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from ai_copilot.api import get_operator_copilot_usecase
from app.adapters.ai.llm_failure_catalog import LLMFailure, LLMFailureFamily
from app.adapters.http.routers.llm_config import get_auth_usecases
from app.main import app


class _FakeUseCaseDisabledProvider:
    class _Gateway:
        def get_default_model(self, provider: str) -> str:
            raise LLMFailure(
                family=LLMFailureFamily.INVALID_REQUEST,
                message=f"Provider {provider!r} is experimental and not enabled.",
                provider=provider,
            )

    llm_gateway = _Gateway()

    async def run(self, **_kwargs):
        yield {"type": "run_start"}

    async def resume(self, **_kwargs):
        yield {"type": "run_finish"}


def test_llm_providers_endpoint_exposes_capabilities_and_enabled_state(monkeypatch):
    monkeypatch.setenv("ENABLE_PROVIDER_OPENAI_CODEX", "false")
    monkeypatch.setenv("ENABLE_PROVIDER_CLAUDE_CODE", "true")
    with TestClient(app) as client:
        resp = client.get("/api/dashboard/llm-providers")
    assert resp.status_code == 200
    body = resp.json()
    codex = next(p for p in body if p["provider"] == "openai_codex")
    claude = next(p for p in body if p["provider"] == "claude_code")

    assert codex["transport"] == "codex_oauth"
    assert codex["requires_oauth"] is True
    assert codex["enabled"] is False
    assert codex["feature_flag"] == "ENABLE_PROVIDER_OPENAI_CODEX"

    assert claude["transport"] == "anthropic_messages"
    assert claude["requires_oauth"] is True
    assert claude["enabled"] is True
    assert claude["feature_flag"] == "ENABLE_PROVIDER_CLAUDE_CODE"


def test_provider_oauth_authorize_endpoint_returns_backend_callback_url(monkeypatch):
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    monkeypatch.delenv("OAUTH_STATE_SECRET", raising=False)
    app.dependency_overrides[get_auth_usecases] = lambda: _FakeDashboardAuthDisabled()
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/dashboard/llm-providers/openai_codex/oauth/authorize",
                json={"redirectUri": "http://localhost:5173/oauth/callback"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"] == "openai_codex"
        parsed = urlparse(body["authorization_url"])
        query = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert query["redirect_uri"][0].endswith("/api/dashboard/llm-providers/openai_codex/oauth/callback")
        assert query["code_challenge_method"] == ["S256"]
        assert query["state"][0]
    finally:
        app.dependency_overrides.pop(get_auth_usecases, None)


def test_provider_oauth_authorize_loopback_callback_uses_localhost(monkeypatch):
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    monkeypatch.delenv("OAUTH_STATE_SECRET", raising=False)
    monkeypatch.delenv("OAUTH_CALLBACK_BASE_URL", raising=False)
    app.dependency_overrides[get_auth_usecases] = lambda: _FakeDashboardAuthDisabled()
    try:
        with TestClient(app, base_url="http://127.0.0.1:8000") as client:
            resp = client.post(
                "/api/dashboard/llm-providers/claude_code/oauth/authorize",
                json={"redirectUri": "http://localhost:5173/oauth/callback"},
            )
        assert resp.status_code == 200
        query = parse_qs(urlparse(resp.json()["authorization_url"]).query)
        assert query["redirect_uri"] == [
            "http://localhost:8000/api/dashboard/llm-providers/claude_code/oauth/callback"
        ]
    finally:
        app.dependency_overrides.pop(get_auth_usecases, None)


class _FakeDashboardAuthDisabled:
    def is_enabled(self) -> bool:
        return False


class _FakeDashboardAuthEnabled:
    def is_enabled(self) -> bool:
        return True

    def validate(self, _token: str) -> bool:
        return False


def test_provider_oauth_authorize_endpoint_requires_bearer_when_dashboard_auth_enabled(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "test-secret")
    app.dependency_overrides[get_auth_usecases] = lambda: _FakeDashboardAuthEnabled()
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/dashboard/llm-providers/openai_codex/oauth/authorize",
                json={"redirectUri": "http://localhost:5173/oauth/callback"},
            )

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Missing Authorization: Bearer <token> header"
    finally:
        app.dependency_overrides.pop(get_auth_usecases, None)


def test_provider_oauth_callback_endpoint_redirects_to_frontend_after_exchange(monkeypatch):
    from app.adapters.ai.codex_oauth_client import CodexOAuthClient

    captured: dict[str, str] = {}
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    monkeypatch.delenv("OAUTH_STATE_SECRET", raising=False)

    async def _fake_exchange(self, *, code: str, code_verifier: str, state: str):
        captured["code"] = code
        captured["code_verifier"] = code_verifier
        captured["state"] = state
        return "ok-token"

    monkeypatch.setattr(CodexOAuthClient, "exchange_authorization_code", _fake_exchange)
    app.dependency_overrides[get_auth_usecases] = lambda: _FakeDashboardAuthDisabled()
    try:
        with TestClient(app) as client:
            auth_resp = client.post(
                "/api/dashboard/llm-providers/openai_codex/oauth/authorize",
                json={"redirectUri": "http://localhost:5173/oauth/callback"},
            )
            assert auth_resp.status_code == 200
            auth_query = parse_qs(urlparse(auth_resp.json()["authorization_url"]).query)
            state = auth_query["state"][0]

            callback_resp = client.get(
                "/api/dashboard/llm-providers/openai_codex/oauth/callback",
                params={"code": "abc", "state": state},
                follow_redirects=False,
            )

        assert callback_resp.status_code == 303
        location = callback_resp.headers["location"]
        parsed_location = urlparse(location)
        query = parse_qs(parsed_location.query)

        assert f"{parsed_location.scheme}://{parsed_location.netloc}{parsed_location.path}" == (
            "http://localhost:5173/oauth/callback"
        )
        assert query["provider"] == ["openai_codex"]
        assert query["status"] == ["connected"]
        assert captured["code"] == "abc"
        assert captured["code_verifier"]
        assert captured["state"] == state
    finally:
        app.dependency_overrides.pop(get_auth_usecases, None)


def test_graph_run_unknown_provider_returns_stable_error():
    with TestClient(app) as client:
        resp = client.post(
            "/api/ai/chat/graph",
            json={"message": "hello", "provider": "not-real"},
        )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "LLM_PROVIDER_UNKNOWN"
    assert detail["provider"] == "not-real"


def test_graph_run_disabled_provider_returns_stable_error():
    app.dependency_overrides[get_operator_copilot_usecase] = lambda: _FakeUseCaseDisabledProvider()
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/ai/chat/graph",
                json={"message": "hello", "provider": "openai_codex"},
            )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["code"] == "LLM_INVALID_REQUEST"
        assert detail["family"] == "invalid_request"
        assert detail["provider"] == "openai_codex"
    finally:
        app.dependency_overrides.pop(get_operator_copilot_usecase, None)
