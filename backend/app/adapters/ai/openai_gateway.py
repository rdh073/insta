"""OpenAI-compatible AI gateway adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from .provider_catalog import get_provider_spec, PROVIDER_SPECS, OPENAI_COMPATIBLE_TRANSPORTS


@dataclass
class ToolCall:
    """Tool call from AI response."""
    id: str
    function_name: str
    function_arguments: str

    def to_dict(self) -> dict:
        """Convert to dict format for messages."""
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.function_name,
                "arguments": self.function_arguments,
            },
        }


@dataclass
class AIResponse:
    """Response from AI provider."""
    content: str | None
    finish_reason: str  # "stop", "tool_calls", "error"
    tool_calls: list[dict] | None = None


class ProviderConfig:
    """Provider configuration for OpenAI-compatible APIs."""

    CONFIGS = {
        name: {
            "base_url": spec.base_url,
            "env_key": spec.env_key,
            "default_model": spec.default_model,
            "transport": spec.transport,
            "status": spec.status,
        }
        for name, spec in PROVIDER_SPECS.items()
    }

    @classmethod
    def get(cls, provider: str) -> dict:
        """Get provider config."""
        key = (provider or "").strip().lower()
        if key not in cls.CONFIGS:
            valid = ", ".join(sorted(cls.CONFIGS.keys()))
            raise ValueError(f"Unknown provider {provider!r}. Must be one of: {valid}")
        # Defensive copy so callers can't mutate shared class state.
        return dict(cls.CONFIGS[key])

    @classmethod
    def get_default_model(cls, provider: str) -> str:
        """Get default model for provider."""
        return cls.get(provider)["default_model"]


def _resolve_api_key_from_env(env_key: str) -> str:
    """Read an API key from the process environment, trimming whitespace.

    Env files loaded via docker-compose `env_file`, `--env-file`, or pasted by
    operators frequently smuggle in trailing newlines or spaces. The OpenAI SDK
    silently rejects such values, which surfaces here as "No API key" even when
    `cat /proc/1/environ` shows the variable is present. Trim at the boundary so
    the rest of the gateway only sees a clean value.
    """
    if not env_key:
        return ""
    raw = os.getenv(env_key)
    if raw is None:
        return ""
    return raw.strip()


class AIGateway:
    """OpenAI-compatible AI client adapter."""

    def __init__(self):
        """Initialize gateway (lazy-loads client on first use)."""
        self._clients: dict[tuple[str, str | None], object] = {}

    def _get_client(self, api_key: str, base_url: str | None = None):
        """Lazy-load and cache AsyncOpenAI client."""
        cache_key = (api_key, base_url)
        if cache_key in self._clients:
            return self._clients[cache_key]

        from openai import AsyncOpenAI

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        client = AsyncOpenAI(**kwargs)
        self._clients[cache_key] = client
        return client

    def get_default_model(self, provider: str) -> str:
        """Get default model for provider."""
        return ProviderConfig.get_default_model(provider)

    async def request_completion(
        self,
        messages: list[dict],
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
        provider_base_url: str | None = None,
        tools: list[dict] | None = None,
    ) -> AIResponse:
        """Request completion from AI provider.

        Args:
            messages: Message history
            provider: AI provider name
            model: Model name (uses provider default if None)
            api_key: API key (uses env var if None)
            provider_base_url: Override base URL
            tools: Tool schemas for function calling

        Returns:
            AIResponse with content, finish_reason, and tool_calls

        Raises:
            ValueError: If API key is missing or provider is invalid
        """
        config = ProviderConfig.get(provider)
        if config.get("transport") not in OPENAI_COMPATIBLE_TRANSPORTS:
            raise ValueError(
                f"Provider {provider!r} uses transport {config.get('transport')!r} "
                "and requires a dedicated gateway adapter. "
                "Current AIGateway supports only OpenAI-compatible providers."
            )
        effective_model = model or config["default_model"]
        env_key = config["env_key"]

        # Treat whitespace-only overrides as absent — operators paste keys with
        # trailing newlines, and docker-compose env_file parsers occasionally
        # attach stray whitespace. An unstripped " " would bypass the env
        # fallback entirely and reach the SDK as an invalid key.
        override = (api_key or "").strip()
        env_value = _resolve_api_key_from_env(env_key)
        effective_api_key = override or env_value

        if not effective_api_key:
            # Ollama ignores the Bearer token but the OpenAI SDK still requires
            # a non-empty string — inject a dummy so operators can run fully
            # unauthenticated against a self-hosted Ollama server.
            if (provider or "").strip().lower() == "ollama" or env_key == "OLLAMA_API_KEY":
                effective_api_key = "ollama"
            elif env_key:
                raise ValueError(
                    f"No API key for {provider}. Set {env_key} env var or provide via apiKey."
                )
            else:
                # No env_key (e.g. openai_compatible) — use a placeholder so the
                # OpenAI client library accepts the request. Servers like Ollama
                # and LM Studio accept any non-empty string.
                effective_api_key = "no-key"

        # Determine effective base URL
        effective_base_url = provider_base_url or config["base_url"]

        # Get or create client
        client = self._get_client(effective_api_key, effective_base_url)

        # Build request kwargs
        request_kwargs = {
            "model": effective_model,
            "messages": messages,
            "max_tokens": 1024,
        }

        if tools:
            request_kwargs["tools"] = tools
            request_kwargs["tool_choice"] = "auto"

        # Request from provider
        response = await client.chat.completions.create(**request_kwargs)
        choice = response.choices[0]

        # Parse response
        finish_reason = choice.finish_reason or "stop"
        content = choice.message.content or ""
        tool_calls = None

        if finish_reason == "tool_calls" and choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        return AIResponse(
            content=content,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
        )
