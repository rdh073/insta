"""Adapter-level quality gate: LLM adapter errors must be app-owned and sanitized."""

from __future__ import annotations

import asyncio

import pytest

from app.adapters.ai.anthropic_messages_gateway import AnthropicMessagesGateway
from app.adapters.ai.codex_oauth_gateway import CodexOAuthGateway
from app.adapters.ai.llm_failure_catalog import LLMFailure
from app.adapters.ai.provider_router import ProviderRouter


class _StubOAuth:
    def __init__(self, token: str = "tok", err: Exception | None = None):
        self.token = token
        self.err = err

    async def get_access_token(self) -> str:
        if self.err:
            raise self.err
        return self.token

    def get_account_id(self) -> str | None:
        return None


class _StubOpenAIGateway:
    async def request_completion(self, **_kwargs):
        return {"content": "ok", "finish_reason": "stop", "tool_calls": []}

    def get_default_model(self, _provider: str) -> str:
        return "gpt-4o-mini"


def test_codex_gateway_sanitizes_vendor_error_string():
    raw_vendor = "RAW_VENDOR_INTERNAL_CODE_999"
    gateway = CodexOAuthGateway(oauth_client=_StubOAuth())

    async def _boom(**_kwargs):
        raise RuntimeError(raw_vendor)

    gateway._call_codex_api = _boom  # type: ignore[method-assign]

    with pytest.raises(LLMFailure) as exc:
        asyncio.run(
            gateway.request_completion(
                messages=[{"role": "user", "content": "hello"}],
                provider="openai_codex",
            )
        )

    assert exc.value.provider == "openai_codex"
    assert raw_vendor not in exc.value.message
    assert raw_vendor not in str(exc.value)


def test_anthropic_gateway_sanitizes_vendor_error_string():
    raw_vendor = "ANTHROPIC_UPSTREAM_TRACE_ABC"
    gateway = AnthropicMessagesGateway(oauth_client=_StubOAuth())

    async def _boom(**_kwargs):
        raise RuntimeError(raw_vendor)

    gateway._call_anthropic_api = _boom  # type: ignore[method-assign]

    with pytest.raises(LLMFailure) as exc:
        asyncio.run(
            gateway.request_completion(
                messages=[{"role": "user", "content": "hello"}],
                provider="claude_code",
            )
        )

    assert exc.value.provider == "claude_code"
    assert raw_vendor not in exc.value.message
    assert raw_vendor not in str(exc.value)


def test_provider_router_unknown_provider_returns_app_owned_failure():
    router = ProviderRouter(openai_gateway=_StubOpenAIGateway())
    with pytest.raises(LLMFailure) as exc:
        asyncio.run(
            router.request_completion(
                messages=[{"role": "user", "content": "hello"}],
                provider="not-real-provider",
            )
        )

    assert exc.value.provider == "not-real-provider"
    assert "Unknown provider" in exc.value.message
