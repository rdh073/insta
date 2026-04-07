"""Phase-2 tests for provider router transport dispatch and feature flags."""

from __future__ import annotations

import asyncio

import pytest

from app.adapters.ai.llm_failure_catalog import LLMFailure, LLMFailureFamily
from app.adapters.ai.provider_router import ProviderRouter


class _FakeGateway:
    def __init__(self, name: str, default_model: str):
        self.name = name
        self.default_model = default_model
        self.calls: list[dict] = []

    async def request_completion(
        self,
        messages: list[dict],
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
        provider_base_url: str | None = None,
    ) -> dict:
        self.calls.append(
            {
                "messages": messages,
                "provider": provider,
                "model": model,
                "api_key": api_key,
                "provider_base_url": provider_base_url,
            }
        )
        return {"content": self.name, "finish_reason": "stop", "tool_calls": []}

    def get_default_model(self, provider: str) -> str:
        return self.default_model


def test_router_routes_openai_compatible_provider_to_openai_gateway():
    openai_gateway = _FakeGateway("openai-path", "gpt-4o-mini")
    router = ProviderRouter(openai_gateway=openai_gateway)

    result = asyncio.run(
        router.request_completion(
            messages=[{"role": "user", "content": "hello"}],
            provider="openai",
            model="gpt-4.1-mini",
            api_key="k1",
            provider_base_url="https://example.test/v1",
        )
    )

    assert result["content"] == "openai-path"
    assert len(openai_gateway.calls) == 1
    assert openai_gateway.calls[0]["provider"] == "openai"


def test_router_blocks_experimental_provider_when_feature_flag_disabled():
    openai_gateway = _FakeGateway("openai-path", "gpt-4o-mini")
    router = ProviderRouter(
        openai_gateway=openai_gateway,
        feature_flags={"ENABLE_PROVIDER_OPENAI_CODEX": False},
    )

    with pytest.raises(LLMFailure) as exc:
        asyncio.run(
            router.request_completion(
                messages=[{"role": "user", "content": "hello"}],
                provider="openai_codex",
            )
        )

    assert exc.value.family == LLMFailureFamily.INVALID_REQUEST
    assert "ENABLE_PROVIDER_OPENAI_CODEX" in exc.value.message


def test_router_fails_with_transport_mismatch_when_adapter_not_installed():
    openai_gateway = _FakeGateway("openai-path", "gpt-4o-mini")
    router = ProviderRouter(
        openai_gateway=openai_gateway,
        feature_flags={"ENABLE_PROVIDER_OPENAI_CODEX": True},
    )

    with pytest.raises(LLMFailure) as exc:
        asyncio.run(
            router.request_completion(
                messages=[{"role": "user", "content": "hello"}],
                provider="openai_codex",
            )
        )

    assert exc.value.family == LLMFailureFamily.TRANSPORT_MISMATCH
    assert "codex_oauth adapter" in exc.value.message


def test_router_routes_experimental_provider_when_enabled_and_adapter_available():
    openai_gateway = _FakeGateway("openai-path", "gpt-4o-mini")
    codex_gateway = _FakeGateway("codex-path", "codex-mini-latest")
    router = ProviderRouter(
        openai_gateway=openai_gateway,
        codex_gateway=codex_gateway,
        feature_flags={"ENABLE_PROVIDER_OPENAI_CODEX": True},
    )

    result = asyncio.run(
        router.request_completion(
            messages=[{"role": "user", "content": "hello"}],
            provider="openai_codex",
            model="codex-mini-latest",
        )
    )

    assert result["content"] == "codex-path"
    assert len(codex_gateway.calls) == 1
    assert codex_gateway.calls[0]["provider"] == "openai_codex"


def test_router_unknown_provider_uses_app_owned_failure():
    openai_gateway = _FakeGateway("openai-path", "gpt-4o-mini")
    router = ProviderRouter(openai_gateway=openai_gateway)

    with pytest.raises(LLMFailure) as exc:
        asyncio.run(
            router.request_completion(
                messages=[{"role": "user", "content": "hello"}],
                provider="not-real-provider",
            )
        )

    assert exc.value.family == LLMFailureFamily.INVALID_REQUEST
    assert "Unknown provider" in exc.value.message


def test_router_get_default_model_for_existing_provider():
    openai_gateway = _FakeGateway("openai-path", "gpt-4o-mini")
    router = ProviderRouter(openai_gateway=openai_gateway)

    model = router.get_default_model("gemini")
    assert model == "gpt-4o-mini"
