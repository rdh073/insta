"""Core primitives for AI tool registry."""

from __future__ import annotations

import asyncio
from typing import Callable


class ToolRegistry:
    """Registry mapping tool names to handler functions."""

    def __init__(self):
        """Initialize with empty registry."""
        self._tools: dict[str, dict[str, object]] = {}
        self._schemas: list[dict] = []

    def register(
        self,
        name: str,
        handler: Callable[[dict], dict],
        schema: dict,
    ) -> None:
        """Register a tool.

        Args:
            name: Tool name
            handler: Sync or async function(args) -> dict
            schema: OpenAI function schema
        """
        self._tools[name] = {
            "handler": handler,
            "schema": schema,
        }
        self._schemas.append(schema)

    def get_schemas(self) -> list[dict]:
        """Get all tool schemas for AI provider."""
        return self._schemas

    async def execute(self, name: str, args: dict) -> dict:
        """Execute a tool by name.

        Args:
            name: Tool name
            args: Tool arguments

        Returns:
            Tool result dict

        Raises:
            ValueError: If tool not found
        """
        tool = self._tools.get(name)
        if not tool:
            return {"error": f"Unknown tool: {name}"}

        handler = tool["handler"]

        # Run handler (sync or async)
        try:
            if asyncio.iscoroutinefunction(handler):
                return await handler(args)

            # Run sync handler in thread pool to avoid blocking
            return await asyncio.to_thread(handler, args)
        except Exception as exc:
            return {"error": str(exc)}


def schema(
    name: str,
    description: str,
    properties: dict | None = None,
    required: list[str] | None = None,
) -> dict:
    """Build OpenAI function schema."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }
