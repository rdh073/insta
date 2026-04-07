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
