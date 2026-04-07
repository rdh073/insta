"""Unit tests for ReadOnlyToolExecutor access control.

Tests that the allowlist is enforced and only read-only tools can execute.
"""

from __future__ import annotations

import sys
from pathlib import Path
from abc import ABC, abstractmethod

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest


# Mock ToolRegistry for testing
class MockToolRegistry:
    """Mock tool registry for testing."""

    async def execute(self, tool_name: str, args: dict) -> dict:
        """Execute tool - only allows specific tools for testing."""
        # Simulate tool execution
        if tool_name == "list_accounts":
            return {"status": "success", "accounts": ["account1", "account2"]}
        elif tool_name == "get_account_info":
            return {
                "status": "success",
                "account": {"id": args.get("id"), "name": "My Account"}
            }
        elif tool_name == "get_post_jobs":
            return {"status": "success", "jobs": []}
        elif tool_name == "create_post":
            return {"status": "error", "message": "Write operation not available"}
        else:
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    def get_schemas(self) -> list[dict]:
        """Get tool schemas in OpenAI function-call format."""
        return [
            {"type": "function", "function": {"name": "list_accounts", "description": "List all accounts", "parameters": {}}},
            {"type": "function", "function": {"name": "get_account_info", "description": "Get account info", "parameters": {}}},
            {"type": "function", "function": {"name": "get_post_jobs", "description": "Get post jobs", "parameters": {}}},
            {"type": "function", "function": {"name": "create_post", "description": "Create a post (write operation)", "parameters": {}}},
        ]


@pytest.fixture
def tool_registry():
    """Create a mock tool registry."""
    return MockToolRegistry()


@pytest.fixture
def executor(tool_registry):
    """Create a ReadOnlyToolExecutor."""
    from ai_copilot.adapters.tool_executor import ReadOnlyToolExecutor

    return ReadOnlyToolExecutor(tool_registry=tool_registry)


@pytest.mark.asyncio
async def test_allowed_tool_list_accounts(executor):
    """Test that list_accounts is allowed."""
    result = await executor.execute("list_accounts", {})

    assert result["status"] == "success"
    assert "accounts" in result


@pytest.mark.asyncio
async def test_allowed_tool_get_account_info(executor):
    """Test that get_account_info is allowed."""
    result = await executor.execute("get_account_info", {"id": "123"})

    assert result["status"] == "success"
    assert result["account"]["id"] == "123"


@pytest.mark.asyncio
async def test_allowed_tool_get_post_jobs(executor):
    """Test that get_post_jobs is allowed."""
    result = await executor.execute("get_post_jobs", {})

    assert result["status"] == "success"
    assert "jobs" in result


@pytest.mark.asyncio
async def test_disallowed_tool_create_post(executor):
    """Test that write tools are blocked."""
    with pytest.raises(ValueError) as exc_info:
        await executor.execute("create_post", {})

    assert "Access denied" in str(exc_info.value)
    assert "create_post" in str(exc_info.value)


@pytest.mark.asyncio
async def test_disallowed_arbitrary_tool(executor):
    """Test that arbitrary tools outside allowlist are blocked."""
    with pytest.raises(ValueError) as exc_info:
        await executor.execute("delete_all_accounts", {})

    assert "Access denied" in str(exc_info.value)


@pytest.mark.asyncio
async def test_allowlist_error_message(executor):
    """Test error message lists allowed tools."""
    with pytest.raises(ValueError) as exc_info:
        await executor.execute("unauthorized_tool", {})

    error_msg = str(exc_info.value)
    assert "Allowed tools" in error_msg
    # Should mention some allowed tools
    assert any(tool in error_msg for tool in [
        "list_accounts", "get_account_info", "get_post_jobs"
    ])


def test_get_schemas_only_allowed(executor):
    """Test that get_schemas only returns allowed tools."""
    schemas = executor.get_schemas()

    schema_names = [s.get("function", {}).get("name") for s in schemas]

    # Should only have allowed tools
    assert "list_accounts" in schema_names
    assert "get_account_info" in schema_names
    assert "get_post_jobs" in schema_names
    # Should not have write tools
    assert "create_post" not in schema_names


def test_executor_initialization(executor):
    """Test that executor initializes correctly."""
    assert executor is not None
    # tool_registry attribute exists (set in __init__)
    assert hasattr(executor, "tool_registry")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
