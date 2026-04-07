"""LLM gateway adapter - implements port using existing AIGateway.

Adapts the app/adapters/ai/openai_gateway.py to the LangGraph port interface.
Handles vendor-specific concerns (OpenAI, Gemini, etc.).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ai_copilot.application.ports import LLMGatewayPort

if TYPE_CHECKING:
    from app.adapters.ai.openai_gateway import AIGateway


class LLMGatewayAdapter(LLMGatewayPort):
    """Adapter for LLM interaction via existing AIGateway.

    Implements LLMGatewayPort using the refactored app's AIGateway.
    """

    def __init__(self, ai_gateway: AIGateway):
        """Initialize with AIGateway dependency.

        Args:
            ai_gateway: Existing app's OpenAI-compatible gateway
        """
        self.ai_gateway = ai_gateway

    async def request_completion(
        self,
        messages: list[dict],
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
        provider_base_url: str | None = None,
    ) -> dict:
        """Request completion from LLM.

        Args:
            messages: Chat message history
            provider: AI provider (openai, gemini, deepseek, antigravity)
            model: Model identifier
            api_key: API key override
            provider_base_url: Base URL override

        Returns:
            Dict with content, finish_reason, and optional tool_calls
        """
        response = await self.ai_gateway.request_completion(
            messages=messages,
            provider=provider,
            model=model,
            api_key=api_key,
            provider_base_url=provider_base_url,
        )

        # Transform to dict format for graph
        return {
            "content": response.content,
            "finish_reason": response.finish_reason,
            "tool_calls": response.tool_calls or [],
        }

    def get_default_model(self, provider: str) -> str:
        """Get default model for provider.

        Args:
            provider: Provider name

        Returns:
            Default model identifier
        """
        return self.ai_gateway.get_default_model(provider)
