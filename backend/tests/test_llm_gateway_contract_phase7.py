"""Provider contract gate: all provider gateways must return same response shape."""

from __future__ import annotations

import asyncio

from app.adapters.ai.provider_router import ProviderRouter


class _OpenAIGatewayStub:
    async def request_completion(self, **_kwargs):
        return {"content": "openai", "finish_reason": "stop", "tool_calls": []}

    def get_default_model(self, _provider: str) -> str:
        return "gpt-4o-mini"


class _CodexGatewayStub:
    async def request_completion(self, **_kwargs):
        return {
            "content": "codex",
            "finish_reason": "stop",
            "tool_calls": [{"id": "t1", "type": "function", "function": {"name": "x", "arguments": "{}"}}],
        }

    def get_default_model(self, _provider: str) -> str:
        return "codex-mini-latest"


class _AnthropicGatewayStub:
    async def request_completion(self, **_kwargs):
        return {"content": "claude", "finish_reason": "end_turn", "tool_calls": []}

    def get_default_model(self, _provider: str) -> str:
        return "claude-sonnet-4-5"


def _assert_contract_shape(result: dict):
    assert set(result.keys()) == {"content", "finish_reason", "tool_calls"}
    assert isinstance(result["content"], str)
    assert isinstance(result["finish_reason"], str)
    assert isinstance(result["tool_calls"], list)


def test_provider_router_contract_shape_openai_compatible():
    router = ProviderRouter(openai_gateway=_OpenAIGatewayStub())
    result = asyncio.run(
        router.request_completion(
            messages=[{"role": "user", "content": "hi"}],
            provider="openai",
        )
    )
    _assert_contract_shape(result)


def test_provider_router_contract_shape_codex_oauth():
    router = ProviderRouter(
        openai_gateway=_OpenAIGatewayStub(),
        codex_gateway=_CodexGatewayStub(),
        feature_flags={"ENABLE_PROVIDER_OPENAI_CODEX": True},
    )
    result = asyncio.run(
        router.request_completion(
            messages=[{"role": "user", "content": "hi"}],
            provider="openai_codex",
        )
    )
    _assert_contract_shape(result)


def test_provider_router_contract_shape_anthropic_messages():
    router = ProviderRouter(
        openai_gateway=_OpenAIGatewayStub(),
        anthropic_gateway=_AnthropicGatewayStub(),
        feature_flags={"ENABLE_PROVIDER_CLAUDE_CODE": True},
    )
    result = asyncio.run(
        router.request_completion(
            messages=[{"role": "user", "content": "hi"}],
            provider="claude_code",
        )
    )
    _assert_contract_shape(result)
