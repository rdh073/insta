"""Tests for AI provider catalog and OpenAI-compatible gateway guardrails."""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.adapters.ai.openai_gateway import AIGateway
from app.adapters.ai.provider_catalog import (
    get_provider_spec,
    is_openai_compatible_provider,
)


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


def _install_fake_openai(monkeypatch):
    fake_module = ModuleType("openai")
    fake_module.AsyncOpenAI = _FakeAsyncOpenAI
    monkeypatch.setitem(sys.modules, "openai", fake_module)


def test_provider_catalog_transport_flags():
    assert is_openai_compatible_provider("openai") is True
    assert is_openai_compatible_provider("openai_codex") is False
    assert is_openai_compatible_provider("claude_code") is False


def test_provider_catalog_unknown_provider():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider_spec("unknown-provider")


def test_gateway_blocks_non_openai_compatible_transport():
    gateway = AIGateway()
    with pytest.raises(ValueError, match="requires a dedicated gateway adapter"):
        asyncio.run(
            gateway.request_completion(
                messages=[{"role": "user", "content": "hello"}],
                provider="openai_codex",
            )
        )


def test_gateway_unknown_provider_fails_fast():
    gateway = AIGateway()
    with pytest.raises(ValueError, match="Unknown provider"):
        asyncio.run(
            gateway.request_completion(
                messages=[{"role": "user", "content": "hello"}],
                provider="not-real",
            )
        )


def test_gateway_client_cache_is_scoped_by_key_and_base_url(monkeypatch):
    _install_fake_openai(monkeypatch)
    _FakeAsyncOpenAI.instances.clear()

    gateway = AIGateway()
    messages = [{"role": "user", "content": "cache-test"}]

    asyncio.run(
        gateway.request_completion(
            messages=messages,
            provider="openai",
            api_key="key-a",
            provider_base_url="https://example-a.test/v1",
        )
    )
    asyncio.run(
        gateway.request_completion(
            messages=messages,
            provider="openai",
            api_key="key-a",
            provider_base_url="https://example-a.test/v1",
        )
    )
    asyncio.run(
        gateway.request_completion(
            messages=messages,
            provider="openai",
            api_key="key-b",
            provider_base_url="https://example-a.test/v1",
        )
    )
    asyncio.run(
        gateway.request_completion(
            messages=messages,
            provider="openai",
            api_key="key-a",
            provider_base_url="https://example-b.test/v1",
        )
    )

    # one client for (key-a, url-a), one for (key-b, url-a), one for (key-a, url-b)
    assert len(_FakeAsyncOpenAI.instances) == 3


def test_gateway_falls_back_to_env_when_api_key_omitted(monkeypatch):
    """Without an explicit api_key, the gateway must read OPENAI_API_KEY from env.

    Regression guard for the prod container bug where summarize_result raised
    "No API key for openai" despite OPENAI_API_KEY being present in PID 1's
    environment. The gateway must resolve the env value at call time.
    """
    _install_fake_openai(monkeypatch)
    _FakeAsyncOpenAI.instances.clear()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")

    gateway = AIGateway()
    response = asyncio.run(
        gateway.request_completion(
            messages=[{"role": "user", "content": "hi"}],
            provider="openai",
        )
    )

    assert response.content == "ok"
    assert len(_FakeAsyncOpenAI.instances) == 1
    assert _FakeAsyncOpenAI.instances[0].kwargs["api_key"] == "sk-from-env"


def test_gateway_strips_whitespace_from_env_api_key(monkeypatch):
    """Env files (docker-compose env_file, --env-file) sometimes carry stray
    newlines/spaces around the value. The gateway must trim them so the OpenAI
    SDK doesn't silently reject an otherwise-valid key."""
    _install_fake_openai(monkeypatch)
    _FakeAsyncOpenAI.instances.clear()
    monkeypatch.setenv("OPENAI_API_KEY", "  sk-padded\n")

    gateway = AIGateway()
    asyncio.run(
        gateway.request_completion(
            messages=[{"role": "user", "content": "hi"}],
            provider="openai",
        )
    )

    assert _FakeAsyncOpenAI.instances[0].kwargs["api_key"] == "sk-padded"


def test_gateway_whitespace_only_override_falls_back_to_env(monkeypatch):
    """A whitespace-only api_key override must not block the env fallback."""
    _install_fake_openai(monkeypatch)
    _FakeAsyncOpenAI.instances.clear()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")

    gateway = AIGateway()
    asyncio.run(
        gateway.request_completion(
            messages=[{"role": "user", "content": "hi"}],
            provider="openai",
            api_key="   ",
        )
    )

    assert _FakeAsyncOpenAI.instances[0].kwargs["api_key"] == "sk-from-env"


def test_gateway_raises_when_env_and_override_both_absent(monkeypatch):
    """Without any key source, the gateway must surface a clear error."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    gateway = AIGateway()
    with pytest.raises(ValueError, match="No API key for openai"):
        asyncio.run(
            gateway.request_completion(
                messages=[{"role": "user", "content": "hi"}],
                provider="openai",
            )
        )


def test_provider_config_get_returns_defensive_copy():
    """Callers must not be able to mutate the shared ProviderConfig state."""
    from app.adapters.ai.openai_gateway import ProviderConfig

    config = ProviderConfig.get("openai")
    config["env_key"] = "TAMPERED"

    assert ProviderConfig.get("openai")["env_key"] == "OPENAI_API_KEY"
