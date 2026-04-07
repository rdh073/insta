"""Provider router adapter - dispatches LLM requests to transport-specific adapters.

Routes requests to appropriate adapter based on provider's transport type.
All adapters implement the same LLMGatewayPort contract.

Transport → Adapter mapping:
- openai_compatible → OpenAIGateway (existing, handles openai, gemini, deepseek, antigravity)
- codex_oauth → CodexOAuthGateway (OAuth + WHAM rate limits)
- anthropic_messages → AnthropicMessagesGateway (Anthropic Messages API + SSE)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .provider_catalog import get_provider_spec, OPENAI_COMPATIBLE_TRANSPORTS
from .llm_failure_catalog import LLMFailure, LLMFailureFamily

if TYPE_CHECKING:
    from app.adapters.ai.openai_gateway import AIGateway
    from app.adapters.ai.codex_oauth_gateway import CodexOAuthGateway
    from app.adapters.ai.anthropic_messages_gateway import AnthropicMessagesGateway


class ProviderRouter:
    """Routes LLM requests to transport-specific adapter implementations.

    Each adapter (OpenAI-compatible, Codex OAuth, Anthropic) implements
    the same LLMGatewayPort contract.  Router selects adapter and delegates.
    """

    def __init__(
        self,
        openai_gateway: AIGateway,
        codex_gateway: CodexOAuthGateway | None = None,
        anthropic_gateway: AnthropicMessagesGateway | None = None,
        feature_flags: dict[str, bool] | None = None,
    ):
        """Initialize router with transport-specific adapters.

        Args:
            openai_gateway: Adapter for openai_compatible transport
            codex_gateway: Adapter for codex_oauth transport (optional)
            anthropic_gateway: Adapter for anthropic_messages transport (optional)
            feature_flags: Feature flags for experimental providers
                - ENABLE_PROVIDER_OPENAI_CODEX: bool
                - ENABLE_PROVIDER_CLAUDE_CODE: bool
        """
        self.openai_gateway = openai_gateway
        self.codex_gateway = codex_gateway
        self.anthropic_gateway = anthropic_gateway
        self.feature_flags = feature_flags or {}

    def _get_adapter(self, provider: str):
        """Get the adapter for a provider based on its transport.

        Args:
            provider: Provider name (openai, gemini, codex, claude_code, etc.)

        Returns:
            The appropriate adapter instance

        Raises:
            LLMFailure: If provider unsupported, disabled, or adapter unavailable
        """
        try:
            spec = get_provider_spec(provider)
        except ValueError as e:
            raise LLMFailure(
                family=LLMFailureFamily.INVALID_REQUEST,
                message=str(e),
                provider=provider,
                cause=e,
            )

        # Check if experimental provider is enabled
        if spec.status == "experimental":
            flag_key = f"ENABLE_PROVIDER_{provider.upper()}"
            if not self.feature_flags.get(flag_key, False):
                raise LLMFailure(
                    family=LLMFailureFamily.INVALID_REQUEST,
                    message=f"Provider {provider!r} is experimental and not enabled. "
                    f"Set {flag_key}=true to enable.",
                    provider=provider,
                )

        # Select adapter by transport
        if spec.transport in OPENAI_COMPATIBLE_TRANSPORTS:
            return self.openai_gateway

        elif spec.transport == "codex_oauth":
            if not self.codex_gateway:
                raise LLMFailure(
                    family=LLMFailureFamily.TRANSPORT_MISMATCH,
                    message=f"Provider {provider!r} requires codex_oauth adapter (not installed)",
                    provider=provider,
                )
            return self.codex_gateway

        elif spec.transport == "anthropic_messages":
            if not self.anthropic_gateway:
                raise LLMFailure(
                    family=LLMFailureFamily.TRANSPORT_MISMATCH,
                    message=f"Provider {provider!r} requires anthropic_messages adapter (not installed)",
                    provider=provider,
                )
            return self.anthropic_gateway

        else:
            raise LLMFailure(
                family=LLMFailureFamily.TRANSPORT_MISMATCH,
                message=f"No adapter for transport {spec.transport!r}",
                provider=provider,
            )

    async def request_completion(
        self,
        messages: list[dict],
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
        provider_base_url: str | None = None,
    ) -> dict:
        """Request completion via provider-specific adapter.

        Args:
            messages: Chat message history
            provider: AI provider name
            model: Model identifier (overrides provider default)
            api_key: API key override
            provider_base_url: Base URL override for compatible providers

        Returns:
            Dict with content, finish_reason, and tool_calls

        Raises:
            LLMFailure: If provider unsupported, disabled, or request fails
        """
        try:
            adapter = self._get_adapter(provider)
        except LLMFailure:
            raise

        # Delegate to adapter; let it handle parameter validation
        return await adapter.request_completion(
            messages=messages,
            provider=provider,
            model=model,
            api_key=api_key,
            provider_base_url=provider_base_url,
        )

    def get_default_model(self, provider: str) -> str:
        """Get default model for provider.

        Args:
            provider: Provider name

        Returns:
            Default model identifier

        Raises:
            LLMFailure: If provider unknown or disabled
        """
        try:
            adapter = self._get_adapter(provider)
        except LLMFailure:
            raise

        return adapter.get_default_model(provider)
