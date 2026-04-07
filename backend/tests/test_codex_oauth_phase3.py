"""Phase-3 tests for OpenAI Codex OAuth client/gateway/WHAM parsing."""

from __future__ import annotations

import asyncio
import base64
import json

import pytest

from app.adapters.ai.codex_oauth_client import (
    CodexOAuthClient,
    CodexOAuthError,
    extract_account_id,
)
from app.adapters.ai.codex_oauth_gateway import CodexOAuthGateway
from app.adapters.ai.codex_wham import parse_openai_codex_usage_payload
from app.adapters.ai.llm_failure_catalog import LLMFailure


def _make_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.sig"


def test_extract_account_id_from_id_token_claims():
    id_token = _make_jwt({"chatgpt_account_id": "acct_123"})
    account_id = extract_account_id({"id_token": id_token, "access_token": ""})
    assert account_id == "acct_123"


def test_build_authorization_url_contains_pkce_and_codex_params():
    client = CodexOAuthClient()
    verifier = client.generate_code_verifier()
    challenge = client.generate_code_challenge(verifier)
    state = client.generate_state()

    url = client.build_authorization_url(challenge, state)
    assert "code_challenge_method=S256" in url
    assert "codex_cli_simplified_flow=true" in url
    assert "originator=kilo-code" in url
    assert f"state={state}" in url


def test_refresh_token_updates_cached_bundle(monkeypatch):
    client = CodexOAuthClient()
    monkeypatch.setenv("OPENAI_CODEX_REFRESH_TOKEN", "refresh-1")

    def _fake_post_json(_url, _payload):
        return {
            "access_token": "access-2",
            "refresh_token": "refresh-2",
            "expires_in": 3600,
        }

    monkeypatch.setattr(client, "_post_json", _fake_post_json)
    token = asyncio.run(client.refresh_token())
    assert token == "access-2"
    assert client.get_account_id() is None


def test_refresh_token_persists_to_token_store(monkeypatch):
    class _Store:
        def __init__(self):
            self.saved = None

        def get(self, _provider):
            return None

        def save(self, credential):
            self.saved = credential

        def revoke(self, _provider):
            return None

    store = _Store()
    client = CodexOAuthClient(token_store=store)
    monkeypatch.setenv("OPENAI_CODEX_REFRESH_TOKEN", "refresh-1")

    def _fake_post_json(_url, _payload):
        return {
            "access_token": "access-2",
            "refresh_token": "refresh-2",
            "expires_in": 3600,
        }

    monkeypatch.setattr(client, "_post_json", _fake_post_json)
    token = asyncio.run(client.refresh_token())
    assert token == "access-2"
    assert store.saved is not None
    assert store.saved.provider == "openai_codex"
    assert store.saved.refresh_token == "refresh-2"


def test_refresh_token_missing_raises_clear_error(monkeypatch):
    client = CodexOAuthClient()
    monkeypatch.delenv("OPENAI_CODEX_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_CODEX_ACCESS_TOKEN", raising=False)

    with pytest.raises(CodexOAuthError, match="refresh_token is missing"):
        asyncio.run(client.refresh_token())


def test_parse_wham_usage_payload():
    payload = {
        "rate_limit": {
            "primary_window": {
                "limit_window_seconds": 1800,
                "used_percent": 55.1,
                "reset_at": 1710000,
            },
            "secondary_window": {
                "limit_window_seconds": 300,
                "used_percent": 12.4,
                "reset_at": 1710100,
            },
        },
        "plan_type": "plus",
    }
    parsed = parse_openai_codex_usage_payload(payload, fetched_at_ms=12345)
    assert parsed.fetched_at_ms == 12345
    assert parsed.primary is not None
    assert parsed.primary.window_minutes == 30
    assert parsed.secondary is not None
    assert parsed.plan_type == "plus"


class _StubOAuthClient:
    def __init__(self, token: str = "token-1", err: Exception | None = None):
        self.token = token
        self.err = err

    async def get_access_token(self) -> str:
        if self.err:
            raise self.err
        return self.token

    def get_account_id(self) -> str | None:
        return "acct_1"


def test_gateway_translates_oauth_errors_to_failure():
    gateway = CodexOAuthGateway(oauth_client=_StubOAuthClient(err=RuntimeError("RAW_VENDOR_AUTH")))

    with pytest.raises(LLMFailure) as exc:
        asyncio.run(
            gateway.request_completion(
                messages=[{"role": "user", "content": "hello"}],
                provider="openai_codex",
            )
        )

    assert exc.value.family.value == "auth"
    assert "RAW_VENDOR_AUTH" not in exc.value.message


def test_gateway_translates_request_errors_to_failure():
    gateway = CodexOAuthGateway(oauth_client=_StubOAuthClient())

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("429 raw upstream message")

    gateway._call_codex_api = _boom  # type: ignore[method-assign]

    with pytest.raises(LLMFailure) as exc:
        asyncio.run(
            gateway.request_completion(
                messages=[{"role": "user", "content": "hello"}],
                provider="openai_codex",
            )
        )

    assert exc.value.family.value == "rate_limit"
    assert "raw upstream" not in exc.value.message.lower()
