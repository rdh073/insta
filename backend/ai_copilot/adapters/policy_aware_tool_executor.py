"""Policy-aware tool executor — bridges app ToolRegistry with ToolPolicyRegistry.

This adapter provides a second-line defense: even if a blocked tool somehow
reaches execute_tools_node, it cannot be executed here.

Primary defense: graph's review_tool_policy_node strips blocked tools.
Secondary defense: this adapter rejects BLOCKED tools at execution time.

The adapter exposes ALL non-blocked tools in get_schemas() so the LLM
planner can propose any read_only or write_sensitive tool. The policy gate
in the graph then classifies and routes them correctly.

Contrast with ReadOnlyToolExecutor (hardcoded 3-tool whitelist), which is
kept for the legacy read-only copilot. This adapter serves the full
operator copilot with write-sensitive capability.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ai_copilot.application.ports import ToolExecutorPort
from ai_copilot.application.operator_copilot_policy import ToolPolicy, ToolPolicyRegistry

if TYPE_CHECKING:
    from app.adapters.ai.tool_registry import ToolRegistry


class PolicyAwareToolExecutor(ToolExecutorPort):
    """Tool executor that defers access control to ToolPolicyRegistry.

    Two-layer access control:
    1. Graph's review_tool_policy_node (primary): classifies and routes calls.
    2. This adapter (secondary): rejects BLOCKED tools as a final guard.

    READ_ONLY and WRITE_SENSITIVE tools can both be executed here; the graph
    ensures write_sensitive calls only arrive after operator approval.
    """

    def __init__(
        self,
        tool_registry: "ToolRegistry",
        policy_registry: ToolPolicyRegistry | None = None,
    ) -> None:
        """Initialise with app tool registry and optional policy registry.

        Args:
            tool_registry: App's tool registry (provides execute() + get_schemas()).
            policy_registry: Tool classification registry.
                             Defaults to ToolPolicyRegistry() if not supplied.
        """
        self._tool_registry = tool_registry
        self._policy_registry = policy_registry or ToolPolicyRegistry()

    async def execute(self, tool_name: str, args: dict) -> dict:
        """Execute a tool after second-line policy check.

        Raises ValueError for BLOCKED tools. READ_ONLY and WRITE_SENSITIVE
        tools are passed through to the app registry (the graph ensures
        write_sensitive tools arrive here only after approval).

        Args:
            tool_name: Tool identifier.
            args: Tool arguments dict.

        Returns:
            Tool execution result dict.

        Raises:
            ValueError: If tool is BLOCKED or not found in registry.
        """
        classification = self._policy_registry.classify(tool_name)

        if classification.policy == ToolPolicy.BLOCKED:
            raise ValueError(
                f"Execution blocked: '{tool_name}' is a BLOCKED tool "
                f"({classification.reason}). This call should never reach "
                "the executor — check graph policy gate."
            )

        try:
            return await self._tool_registry.execute(tool_name, args)
        except Exception as exc:
            raise ValueError(f"Tool execution failed for '{tool_name}': {exc}") from exc

    def get_schemas(self) -> list[dict]:
        """Return schemas for all non-BLOCKED tools.

        Filters out BLOCKED tools so the LLM never sees them as options.
        Both READ_ONLY and WRITE_SENSITIVE tools are included — the graph
        handles the routing decision.

        Returns:
            List of tool schema dicts (OpenAI function-calling format).
        """
        all_schemas = self._tool_registry.get_schemas()

        return [
            schema
            for schema in all_schemas
            if not _is_blocked(schema, self._policy_registry)
        ]


def _is_blocked(schema: dict, policy_registry: ToolPolicyRegistry) -> bool:
    """True if the schema's tool name is BLOCKED."""
    # Schema may be in OpenAI format: {"type": "function", "function": {"name": ...}}
    # or flat format: {"name": ...}
    name = (
        schema.get("function", {}).get("name")
        or schema.get("name")
        or ""
    )
    if not name:
        return False
    return policy_registry.classify(name).policy == ToolPolicy.BLOCKED
