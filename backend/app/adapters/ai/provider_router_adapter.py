"""Adapter that wraps ProviderRouter to implement LLMGatewayPort.

This adapter:
- Implements the LangGraph port interface
- Delegates routing to ProviderRouter
- Translates LLMFailure exceptions to HTTPException (or application errors)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ai_copilot.application.ports import LLMGatewayPort
from .llm_failure_catalog import LLMFailure

if TYPE_CHECKING:
    from .provider_router import ProviderRouter


class ProviderRouterAdapter(LLMGatewayPort):
    """Adapter that wraps ProviderRouter and implements LLMGatewayPort.

    Translates LLMFailure exceptions from the router into application errors.
    All router functionality is delegated; this adapter is a thin wrapper.
    """

    def __init__(self, provider_router: ProviderRouter):
        """Initialize with provider router.

        Args:
            provider_router: The ProviderRouter that dispatches to adapters
        """
        self.provider_router = provider_router

    async def request_completion(
        self,
        messages: list[dict],
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
        provider_base_url: str | None = None,
    ) -> dict:
        """Request completion from LLM (routed to provider-specific adapter).

        Args:
            messages: Chat message history
            provider: AI provider name
            model: Model identifier
            api_key: API key override
            provider_base_url: Base URL override

        Returns:
            Dict with content, finish_reason, tool_calls

        Raises:
            LLMFailure: If provider unsupported, disabled, or request fails
            ValueError: If critical parameters missing (from underlying adapter)
        """
        result = await self.provider_router.request_completion(
            messages=messages,
            provider=provider,
            model=model,
            api_key=api_key,
            provider_base_url=provider_base_url,
        )
        # openai_gateway returns AIResponse (not dict); normalize to the dict contract
        # that LLMGatewayPort.request_completion promises.
        if not isinstance(result, dict):
            return {
                "content": result.content,
                "finish_reason": result.finish_reason,
                "tool_calls": result.tool_calls or [],
            }
        return result

    def get_default_model(self, provider: str) -> str:
        """Get default model for provider.

        Args:
            provider: Provider name

        Returns:
            Default model identifier

        Raises:
            LLMFailure: If provider unknown or disabled
        """
        return self.provider_router.get_default_model(provider)
