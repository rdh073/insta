"""Tool executor adapter - implements port with read-only access control.

Adapts the app's tool registry to the LangGraph port interface.
Enforces read-only whitelist for operator copilot workflow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ai_copilot.application.ports import ToolExecutorPort

if TYPE_CHECKING:
    from app.adapters.ai.tool_registry import ToolRegistry


# Read-only tools allowed for operator copilot
ALLOWED_TOOLS = {
    "list_accounts",
    "get_account_info",
    "get_post_jobs",
}


class ReadOnlyToolExecutor(ToolExecutorPort):
    """Tool executor with read-only access control.

    Implements ToolExecutorPort using app's ToolRegistry.
    Enforces whitelist - blocks write operations.
    """

    def __init__(self, tool_registry: ToolRegistry):
        """Initialize with tool registry.

        Args:
            tool_registry: App's tool registry with execute() and get_schemas()
        """
        self.tool_registry = tool_registry

    async def execute(self, tool_name: str, args: dict) -> dict:
        """Execute tool with access control.

        Access control: Only allowed tools can be executed.

        Args:
            tool_name: Tool identifier
            args: Tool arguments

        Returns:
            Tool execution result dict

        Raises:
            ValueError: If tool not in allowlist
        """
        # Enforce access control
        if tool_name not in ALLOWED_TOOLS:
            raise ValueError(
                f"Access denied: '{tool_name}' is not in the read-only tool set. "
                f"Allowed tools: {', '.join(sorted(ALLOWED_TOOLS))}"
            )

        # Execute through registry
        try:
            result = await self.tool_registry.execute(tool_name, args)
            return result
        except Exception as e:
            # Re-raise with context
            raise ValueError(f"Tool execution failed: {str(e)}")

    def get_schemas(self) -> list[dict]:
        """Get tool schemas for LLM (read-only only).

        Returns:
            List of tool schema dicts for allowed tools only
        """
        all_schemas = self.tool_registry.get_schemas()
        # Filter to allowed tools
        # Active schema shape is {function: {name, ...}} — not top-level "name"
        allowed_schemas = [
            schema for schema in all_schemas
            if schema.get("function", {}).get("name") in ALLOWED_TOOLS
        ]
        return allowed_schemas
