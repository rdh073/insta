"""Phase-4 tests for Claude Code OAuth/message filter/gateway."""

from __future__ import annotations

import asyncio

import pytest

from app.adapters.ai.anthropic_message_filter import AnthropicMessageFilter
from app.adapters.ai.anthropic_messages_gateway import AnthropicMessagesGateway
from app.adapters.ai.anthropic_oauth_client import AnthropicOAuthClient, AnthropicOAuthError
from app.adapters.ai.anthropic_streaming import (
    SSEParserState,
    normalize_anthropic_sse_events,
    parse_sse_chunk,
)
from app.adapters.ai.llm_failure_catalog import LLMFailure


def test_anthropic_oauth_build_authorization_url():
    client = AnthropicOAuthClient()
    state = client.generate_state()
    url = client.build_authorization_url(code_challenge="abc123", state=state)
    assert "code_challenge_method=S256" in url
    assert "response_type=code" in url
    assert f"state={state}" in url


def test_anthropic_oauth_refresh_token_missing(monkeypatch):
    client = AnthropicOAuthClient()
    monkeypatch.delenv("CLAUDE_CODE_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_ACCESS_TOKEN", raising=False)
    with pytest.raises(AnthropicOAuthError, match="refresh_token is missing"):
        asyncio.run(client.refresh_token())


def test_anthropic_oauth_refresh_token_success(monkeypatch):
    client = AnthropicOAuthClient()
    monkeypatch.setenv("CLAUDE_CODE_REFRESH_TOKEN", "refresh-token")

    def _fake_post_json(_url, _payload):
        return {"access_token": "access-token", "refresh_token": "refresh-next", "expires_in": 3600}

    monkeypatch.setattr(client, "_post_json", _fake_post_json)
    token = asyncio.run(client.refresh_token())
    assert token == "access-token"


def test_anthropic_oauth_persists_to_token_store(monkeypatch):
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
    client = AnthropicOAuthClient(token_store=store)
    monkeypatch.setenv("CLAUDE_CODE_REFRESH_TOKEN", "refresh-token")

    def _fake_post_json(_url, _payload):
        return {"access_token": "access-token", "refresh_token": "refresh-next", "expires_in": 3600}

    monkeypatch.setattr(client, "_post_json", _fake_post_json)
    token = asyncio.run(client.refresh_token())
    assert token == "access-token"
    assert store.saved is not None
    assert store.saved.provider == "claude_code"
    assert store.saved.refresh_token == "refresh-next"


def test_message_filter_allowlist_behavior():
    filterer = AnthropicMessageFilter()
    messages = [
        {"role": "user", "content": "hello"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "ok"},
                {"type": "reasoning", "text": "internal"},
                {"type": "tool_use", "id": "t1", "name": "x", "input": {}},
            ],
            "reasoning_details": {"ignored": True},
        },
    ]
    filtered = filterer.filter_messages(messages)
    assert filtered[0]["content"] == "hello"
    assert isinstance(filtered[1]["content"], list)
    block_types = [b["type"] for b in filtered[1]["content"]]
    assert "text" in block_types
    assert "tool_use" in block_types
    assert "reasoning" not in block_types
    assert "reasoning_details" not in filtered[1]


class _StubOAuth:
    def __init__(self, token: str = "tok", err: Exception | None = None):
        self.token = token
        self.err = err

    async def get_access_token(self) -> str:
        if self.err:
            raise self.err
        return self.token


def test_gateway_translates_oauth_error_to_failure():
    gateway = AnthropicMessagesGateway(
        oauth_client=_StubOAuth(err=RuntimeError("RAW_AUTH_ERROR")),
        message_filter=AnthropicMessageFilter(),
    )
    with pytest.raises(LLMFailure) as exc:
        asyncio.run(
            gateway.request_completion(
                messages=[{"role": "user", "content": "hello"}],
                provider="claude_code",
            )
        )
    assert exc.value.family.value == "auth"
    assert "RAW_AUTH_ERROR" not in exc.value.message


def test_gateway_normalizes_text_and_tool_use():
    gateway = AnthropicMessagesGateway(
        oauth_client=_StubOAuth(),
        message_filter=AnthropicMessageFilter(),
    )

    async def _fake_call(**_kwargs):
        return {
            "content": "hello world",
            "finish_reason": "stop",
            "tool_calls": [{"id": "t1", "type": "function", "function": {"name": "x", "arguments": "{}"}}],
        }

    gateway._call_anthropic_api = _fake_call  # type: ignore[method-assign]
    result = asyncio.run(
        gateway.request_completion(
            messages=[{"role": "user", "content": "hi"}],
            provider="claude_code",
        )
    )
    assert result["content"] == "hello world"
    assert result["finish_reason"] == "stop"
    assert result["tool_calls"][0]["id"] == "t1"


def test_gateway_translates_request_error_to_failure():
    gateway = AnthropicMessagesGateway(
        oauth_client=_StubOAuth(),
        message_filter=AnthropicMessageFilter(),
    )

    async def _boom(**_kwargs):
        raise RuntimeError("429 raw anth error")

    gateway._call_anthropic_api = _boom  # type: ignore[method-assign]

    with pytest.raises(LLMFailure) as exc:
        asyncio.run(
            gateway.request_completion(
                messages=[{"role": "user", "content": "hi"}],
                provider="claude_code",
            )
        )
    assert exc.value.family.value == "rate_limit"
    assert "raw anth error" not in exc.value.message.lower()


def test_sse_parser_and_normalizer():
    state = SSEParserState()
    chunk = (
        "event: content_block_delta\n"
        "data: {\"delta\": {\"text\": \"Hel\"}}\n\n"
        "event: content_block_delta\n"
        "data: {\"delta\": {\"text\": \"lo\"}}\n\n"
        "event: message_delta\n"
        "data: {\"delta\": {\"stop_reason\": \"end_turn\"}}\n\n"
    )
    events, _ = parse_sse_chunk(chunk, state)
    normalized = normalize_anthropic_sse_events(events)
    assert normalized["content"] == "Hello"
    assert normalized["finish_reason"] == "end_turn"
