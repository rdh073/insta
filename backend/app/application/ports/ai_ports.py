"""Port contracts for AI graph nodes.

Nodes only call these ports — they never import vendor SDKs directly.
All vendor-to-state mapping happens inside the adapters.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMGatewayPort(Protocol):
    """LLM operations needed by the graph nodes.

    Implementations must map vendor-specific responses to plain Python types
    before returning — nodes must never see raw OpenAI/Gemini objects.
    """

    async def classify_request(
        self,
        user_request: str,
        messages: list[dict],
    ) -> str:
        """Classify operator request into routing decision.

        Returns:
            "direct_answer" – LLM can answer from context alone.
            "tool_lookup"   – a backend tool must be called first.
        """
        ...

    async def plan_read_only_action(
        self,
        user_request: str,
        allowed_tools: list[str],
        messages: list[dict],
    ) -> tuple[str, dict]:
        """Pick a single tool and produce its arguments.

        Args:
            user_request: Normalised operator input.
            allowed_tools: Tool names this skeleton may use.
            messages: Conversation context.

        Returns:
            (tool_name, tool_args) where tool_name is one of allowed_tools.
        """
        ...

    async def summarize_result(
        self,
        user_request: str,
        tool_results: list[dict],
        messages: list[dict],
    ) -> str:
        """Produce the final natural-language answer.

        Args:
            user_request: Original operator request.
            tool_results: Results collected by execute_node.
            messages: Conversation context.

        Returns:
            Human-readable answer string.
        """
        ...


@runtime_checkable
class ToolExecutorPort(Protocol):
    """Tool execution contract.

    Implementations must reject any tool not in the configured allowlist
    before forwarding to the backend handler.
    """

    async def execute(self, name: str, args: dict) -> dict:
        """Execute a named tool.

        Args:
            name: Tool name.  Must be in the configured allowlist.
            args: Parsed argument dict.

        Returns:
            Result dict (always a plain dict, never raises for tool errors —
            errors are returned as {"error": "..."}).

        Raises:
            ValueError: If *name* is not in the allowlist.
        """
        ...


@runtime_checkable
class CheckpointFactoryPort(Protocol):
    """Factory for graph checkpointers.

    Keeping this as a port prevents graph builders/use cases from directly
    depending on specific persistence implementations.
    """

    def create(self):
        """Create and return a LangGraph-compatible checkpointer instance."""
        ...
