"""Anthropic Messages API gateway adapter.

Implements LLMGatewayPort for Claude Code provider using Anthropic Messages API.

Architecture:
- Uses separate OAuth credential manager (anthropic_oauth_client.py)
- Handles message block filtering and SSE parsing
- Translates AnthropicException → LLMFailure via catalog
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from .llm_failure_catalog import (
    LLMFailure,
    LLMFailureFamily,
    translate_failure,
)

if TYPE_CHECKING:
    from .anthropic_oauth_client import AnthropicOAuthClient
    from .anthropic_message_filter import AnthropicMessageFilter


class AnthropicMessagesGateway:
    """Anthropic Messages API gateway for Claude Code provider.

    Handles:
    - OAuth token management
    - Message block filtering (allowlist)
    - SSE parsing and normalization
    - Error translation to LLMFailure
    """

    def __init__(
        self,
        oauth_client: AnthropicOAuthClient,
        message_filter: AnthropicMessageFilter | None = None,
    ):
        """Initialize Anthropic gateway.

        Args:
            oauth_client: OAuth credential manager
            message_filter: Optional message block filter
        """
        self.oauth_client = oauth_client
        self.message_filter = message_filter

    async def request_completion(
        self,
        messages: list[dict],
        provider: str = "claude_code",
        model: str | None = None,
        api_key: str | None = None,
        provider_base_url: str | None = None,
    ) -> dict:
        """Request completion from Claude Code.

        Args:
            messages: Chat message history
            provider: Provider name (must be "claude_code")
            model: Model name (Anthropic-specific)
            api_key: Not used (OAuth token is fetched from store)
            provider_base_url: Base URL for Anthropic API

        Returns:
            Dict with content, finish_reason, tool_calls

        Raises:
            LLMFailure: If OAuth refresh fails, request fails, etc.
        """
        if provider != "claude_code":
            raise LLMFailure(
                family=LLMFailureFamily.INVALID_REQUEST,
                message=f"AnthropicMessagesGateway only handles claude_code, got {provider!r}",
                provider=provider,
            )

        model = model or "claude-sonnet-4-6"
        base_url = provider_base_url or "https://api.anthropic.com/v1/messages"

        # Refresh access token if needed
        try:
            access_token = await self.oauth_client.get_access_token()
        except Exception as e:
            raise translate_failure(
                e,
                LLMFailureFamily.AUTH,
                provider,
                f"Failed to obtain Anthropic access token: {e}",
            )

        # Filter messages if needed
        filtered_messages = messages
        if self.message_filter:
            filtered_messages = self.message_filter.filter_messages(messages)

        # Make request to Anthropic API
        try:
            response = await self._call_anthropic_api(
                messages=filtered_messages,
                model=model,
                access_token=access_token,
                base_url=base_url,
            )
        except Exception as e:
            # Translate vendor exception to LLMFailure — preserve the actual error detail
            family = self._classify_error(e, provider)
            raise translate_failure(
                e,
                family,
                provider,
                f"Anthropic request failed: {e}",
            )

        return {
            "content": response.get("content", ""),
            "finish_reason": response.get("finish_reason", "stop"),
            "tool_calls": response.get("tool_calls", []),
        }

    async def _call_anthropic_api(
        self,
        messages: list[dict],
        model: str,
        access_token: str,
        base_url: str,
    ) -> dict:
        """Call the Anthropic Messages API.

        Args:
            messages: Filtered chat messages
            model: Model name
            access_token: OAuth access token
            base_url: API base URL

        Returns:
            Dict with content, finish_reason, tool_calls

        Raises:
            Exception: If request fails
        """
        # Extract system messages from the array — Anthropic only accepts system
        # as a top-level parameter, not as role:"system" inside messages.
        system_texts: list[str] = []
        chat_messages: list[dict] = []
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")
                if isinstance(content, str):
                    system_texts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            system_texts.append(block.get("text", ""))
            else:
                chat_messages.append(msg)

        # Build system array: Claude Code identity prefix + any caller-provided system text
        system_blocks: list[dict] = [
            {"type": "text", "text": "You are Claude Code, Anthropic's official CLI for Claude."}
        ]
        for text in system_texts:
            if text.strip():
                system_blocks.append({"type": "text", "text": text})

        payload: dict = {
            "model": model,
            "messages": chat_messages,
            "stream": False,
            "system": system_blocks,
        }
        payload["max_tokens"] = int(os.getenv("CLAUDE_CODE_MAX_TOKENS", "8096"))
        return await asyncio.to_thread(
            self._post_json,
            base_url,
            payload,
            access_token,
        )

    def _classify_error(self, error: Exception, provider: str) -> LLMFailureFamily:
        """Classify an exception into a failure family.

        Args:
            error: The exception
            provider: Provider name

        Returns:
            LLMFailureFamily that maps the exception
        """
        error_msg = str(error).lower()

        # OAuth / auth errors
        if "auth" in error_msg or "token" in error_msg or "401" in error_msg:
            return LLMFailureFamily.AUTH

        # Rate limit errors
        if "rate" in error_msg or "quota" in error_msg or "429" in error_msg:
            return LLMFailureFamily.RATE_LIMIT

        # Provider unavailable
        if "503" in error_msg or "500" in error_msg or "timeout" in error_msg:
            return LLMFailureFamily.PROVIDER_UNAVAILABLE

        # Invalid request
        if "400" in error_msg or "invalid" in error_msg:
            return LLMFailureFamily.INVALID_REQUEST

        # Default to provider unavailable
        return LLMFailureFamily.PROVIDER_UNAVAILABLE

    def get_default_model(self, provider: str) -> str:
        """Get default model for Claude Code.

        Args:
            provider: Provider name (must be "claude_code")

        Returns:
            Default model identifier
        """
        if provider != "claude_code":
            raise LLMFailure(
                family=LLMFailureFamily.INVALID_REQUEST,
                message=f"AnthropicMessagesGateway only handles claude_code, got {provider!r}",
                provider=provider,
            )
        return "claude-sonnet-4-6"

    def _post_json(self, url: str, payload: dict, access_token: str) -> dict:
        # Default betas match the Claude Code streaming client spec:
        # - prompt-caching-2024-07-31  : enable prompt caching
        # - claude-code-20250219       : required for Claude Code OAuth flow
        # - oauth-2025-04-20           : required for Bearer token auth
        _DEFAULT_BETAS = "prompt-caching-2024-07-31,claude-code-20250219,oauth-2025-04-20"
        beta = os.getenv("CLAUDE_CODE_ANTHROPIC_BETA", _DEFAULT_BETAS).strip()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "anthropic-version": os.getenv("CLAUDE_CODE_ANTHROPIC_VERSION", "2023-06-01"),
            "anthropic-beta": beta,
        }

        # Append ?beta=true as required by the Claude Code API spec
        api_url = url if "?" in url else f"{url}?beta=true"
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        timeout_s = float(os.getenv("CLAUDE_CODE_API_TIMEOUT_SECONDS", "45"))

        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as response:
                raw = response.read().decode("utf-8")
                parsed = json.loads(raw) if raw else {}
                if not isinstance(parsed, dict):
                    return {"content": "", "finish_reason": "stop", "tool_calls": []}
                return self._normalize_response(parsed)
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"anthropic_http_{exc.code}: {text[:240]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"anthropic_network: {exc.reason}") from exc

    def _normalize_response(self, payload: dict) -> dict:
        content_blocks = payload.get("content")
        text_parts: list[str] = []
        tool_calls: list[dict] = []

        if isinstance(content_blocks, list):
            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    text_parts.append(block["text"])
                if block.get("type") == "tool_use":
                    tool_calls.append(
                        {
                            "id": block.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": block.get("name", ""),
                                "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                            },
                        }
                    )

        finish_reason = payload.get("stop_reason")
        if not isinstance(finish_reason, str):
            finish_reason = "stop"

        return {
            "content": "".join(text_parts).strip(),
            "finish_reason": finish_reason,
            "tool_calls": tool_calls,
        }
