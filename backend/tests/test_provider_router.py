"""Tests for provider router - validates provider dispatch logic.

Tests that ProviderRouter correctly:
- Routes providers to their transport-specific adapters
- Rejects unknown providers with LLMFailure
- Rejects experimental providers when disabled
- Delegates to correct adapter based on transport
"""

from __future__ import annotations

import pytest
from app.adapters.ai.provider_router import ProviderRouter
from app.adapters.ai.provider_router_adapter import ProviderRouterAdapter
from app.adapters.ai.llm_failure_catalog import (
    LLMFailure,
    LLMFailureFamily,
)


class StubOpenAIGateway:
    """Stub OpenAI-compatible gateway."""

    async def request_completion(
        self,
        messages: list[dict],
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
        provider_base_url: str | None = None,
    ) -> dict:
        return {
            "content": "test response",
            "finish_reason": "stop",
            "tool_calls": [],
        }

    def get_default_model(self, provider: str) -> str:
        return "gpt-4o-mini"


class TestProviderRouter:
    def test_openai_compatible_provider_routes_to_openai_gateway(self):
        """Test that openai provider routes to openai gateway."""
        stub_gateway = StubOpenAIGateway()
        router = ProviderRouter(openai_gateway=stub_gateway)

        # Should not raise
        adapter = router._get_adapter("openai")
        assert adapter is stub_gateway

    def test_gemini_routes_to_openai_gateway(self):
        """Test that gemini (openai-compatible) routes to openai gateway."""
        stub_gateway = StubOpenAIGateway()
        router = ProviderRouter(openai_gateway=stub_gateway)

        adapter = router._get_adapter("gemini")
        assert adapter is stub_gateway

    def test_unknown_provider_raises_llm_failure(self):
        """Test that unknown provider raises LLMFailure."""
        stub_gateway = StubOpenAIGateway()
        router = ProviderRouter(openai_gateway=stub_gateway)

        with pytest.raises(LLMFailure) as exc_info:
            router._get_adapter("unknown_provider")

        failure = exc_info.value
        assert failure.family == LLMFailureFamily.INVALID_REQUEST
        assert "unknown" in failure.message.lower()
        assert failure.provider == "unknown_provider"

    def test_experimental_provider_disabled_raises_llm_failure(self):
        """Test that disabled experimental provider raises LLMFailure."""
        stub_gateway = StubOpenAIGateway()
        router = ProviderRouter(
            openai_gateway=stub_gateway,
            feature_flags={"ENABLE_PROVIDER_OPENAI_CODEX": False},
        )

        with pytest.raises(LLMFailure) as exc_info:
            router._get_adapter("openai_codex")

        failure = exc_info.value
        assert failure.family == LLMFailureFamily.INVALID_REQUEST
        assert "experimental" in failure.message.lower()
        assert "not enabled" in failure.message.lower()

    def test_experimental_provider_enabled_passes(self):
        """Test that enabled experimental provider does not raise adapter error.

        (Adapter instantiation itself may fail, but router routing succeeds.)
        """
        stub_gateway = StubOpenAIGateway()
        router = ProviderRouter(
            openai_gateway=stub_gateway,
            codex_gateway=None,  # Not wired, will fail on call
            feature_flags={"ENABLE_PROVIDER_OPENAI_CODEX": True},
        )

        with pytest.raises(LLMFailure) as exc_info:
            router._get_adapter("openai_codex")

        # Should fail because codex_gateway is None, not because provider is disabled
        failure = exc_info.value
        assert failure.family == LLMFailureFamily.TRANSPORT_MISMATCH
        assert "codex_oauth" in failure.message

    def test_default_model_for_openai_compatible(self):
        """Test that default model is returned from openai gateway."""
        stub_gateway = StubOpenAIGateway()
        router = ProviderRouter(openai_gateway=stub_gateway)

        model = router.get_default_model("openai")
        assert model == "gpt-4o-mini"

    def test_default_model_unknown_provider_raises_llm_failure(self):
        """Test that unknown provider raises LLMFailure when getting default model."""
        stub_gateway = StubOpenAIGateway()
        router = ProviderRouter(openai_gateway=stub_gateway)

        with pytest.raises(LLMFailure):
            router.get_default_model("unknown_provider")


class TestProviderRouterAdapter:
    def test_adapter_implements_llm_gateway_port(self):
        """Test that ProviderRouterAdapter implements LLMGatewayPort."""
        from ai_copilot.application.ports import LLMGatewayPort

        stub_gateway = StubOpenAIGateway()
        router = ProviderRouter(openai_gateway=stub_gateway)
        adapter = ProviderRouterAdapter(router)

        assert isinstance(adapter, LLMGatewayPort)

    @pytest.mark.asyncio
    async def test_adapter_delegates_request_completion(self):
        """Test that adapter delegates request_completion to router."""
        stub_gateway = StubOpenAIGateway()
        router = ProviderRouter(openai_gateway=stub_gateway)
        adapter = ProviderRouterAdapter(router)

        result = await adapter.request_completion(
            messages=[{"role": "user", "content": "hello"}],
            provider="openai",
        )

        assert result["content"] == "test response"
        assert result["finish_reason"] == "stop"
        assert result["tool_calls"] == []

    def test_adapter_delegates_get_default_model(self):
        """Test that adapter delegates get_default_model to router."""
        stub_gateway = StubOpenAIGateway()
        router = ProviderRouter(openai_gateway=stub_gateway)
        adapter = ProviderRouterAdapter(router)

        model = adapter.get_default_model("openai")
        assert model == "gpt-4o-mini"
