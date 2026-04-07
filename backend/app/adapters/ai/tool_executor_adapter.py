"""Concrete ToolExecutorPort backed by ToolRegistry.

Enforces the allowlist configured at construction time.
Nodes never import ToolRegistry directly; they receive a ToolExecutorPort.
"""

from __future__ import annotations

from app.adapters.ai.tool_registry import ToolRegistry


class ToolExecutorAdapter:
    """ToolExecutorPort implementation that wraps ToolRegistry.

    Args:
        tool_registry: Populated registry with handler functions.
        allowed_tools: Names of tools this graph instance may invoke.
            Any name absent from this list will be rejected before reaching
            the registry.
    """

    def __init__(self, tool_registry: ToolRegistry, allowed_tools: list[str]) -> None:
        self._registry = tool_registry
        self._allowed: frozenset[str] = frozenset(allowed_tools)

    async def execute(self, name: str, args: dict) -> dict:
        """Execute *name* tool after enforcing the allowlist.

        Raises:
            ValueError: If *name* is not in the configured allowlist.

        Returns:
            Result dict.  Tool-level errors are returned as {"error": "..."}.
        """
        if name not in self._allowed:
            raise ValueError(
                f"Tool '{name}' is not in the allowlist {sorted(self._allowed)}"
            )
        return await self._registry.execute(name, args)
