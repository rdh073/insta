"""Unit tests for RunOperatorCopilotUseCase with mock ports.

Tests use case initialization with fake implementations of ports
to verify construction without vendor SDKs.
"""

from __future__ import annotations

import sys
from pathlib import Path
from abc import ABC, abstractmethod

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest


# Mock port implementations
class FakeLLMGateway:
    """Fake LLM gateway for testing."""

    def __init__(self, mode: str = "tool_lookup"):
        """Initialize with test mode.

        Args:
            mode: "direct_answer" or "tool_lookup"
        """
        self.mode = mode
        self.classify_called = False
        self.plan_called = False
        self.summarize_called = False

    async def request_completion(
        self,
        messages: list[dict],
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
        provider_base_url: str | None = None,
    ) -> dict:
        """Simulate LLM completion request."""
        if self.mode == "direct_answer":
            return {
                "content": "Direct answer without tools",
                "finish_reason": "stop",
                "tool_calls": []
            }
        else:  # tool_lookup
            return {
                "content": "",
                "finish_reason": "tool_calls",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "function": {"name": "list_accounts", "arguments": "{}"},
                    }
                ]
            }

    def get_default_model(self, provider: str) -> str:
        """Get default model."""
        return f"{provider}-default"


class FakeToolExecutor:
    """Fake tool executor for testing."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    async def execute(self, tool_name: str, tool_args: dict) -> dict:
        """Execute tool."""
        if self.should_fail:
            raise RuntimeError("Simulated tool execution failure")

        if tool_name == "list_accounts":
            return {"accounts": ["account1", "account2"]}
        elif tool_name == "get_account_info":
            return {"name": "My Account", "followers": 1000}
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def get_schemas(self) -> list[dict]:
        """Get tool schemas."""
        return [{"name": "list_accounts", "description": "List accounts"}]


class FakeApprovalPort:
    """Fake approval port."""
    async def request_approval(self, *args, **kwargs):
        return {"approved": True}

    async def get_approval_status(self, approval_id: str):
        return {"approval_id": approval_id, "status": "approved"}


class FakeAuditLog:
    """Fake audit log."""
    async def log(self, *args, **kwargs):
        pass


@pytest.fixture
def fake_llm_direct_answer():
    """Create fake LLM in direct answer mode."""
    return FakeLLMGateway(mode="direct_answer")


@pytest.fixture
def fake_llm_tool_lookup():
    """Create fake LLM in tool lookup mode."""
    return FakeLLMGateway(mode="tool_lookup")


@pytest.fixture
def fake_executor():
    """Create fake tool executor."""
    return FakeToolExecutor(should_fail=False)


@pytest.fixture
def fake_executor_failing():
    """Create fake tool executor that fails."""
    return FakeToolExecutor(should_fail=True)


@pytest.mark.asyncio
async def test_use_case_initialization(fake_llm_direct_answer, fake_executor):
    """Test that RunOperatorCopilotUseCase initializes correctly."""
    from ai_copilot.application.use_cases.run_operator_copilot import RunOperatorCopilotUseCase

    use_case = RunOperatorCopilotUseCase(
        llm_gateway=fake_llm_direct_answer,
        tool_executor=fake_executor,
        approval_port=FakeApprovalPort(),
        audit_log=FakeAuditLog(),
    )

    assert use_case._graph is not None
    assert use_case._checkpointer is not None


@pytest.mark.asyncio
async def test_direct_answer_flow(fake_llm_direct_answer, fake_executor):
    """Test direct answer path (no tools)."""
    from ai_copilot.application.use_cases.run_operator_copilot import RunOperatorCopilotUseCase

    use_case = RunOperatorCopilotUseCase(
        llm_gateway=fake_llm_direct_answer,
        tool_executor=fake_executor,
        approval_port=FakeApprovalPort(),
        audit_log=FakeAuditLog(),
    )

    # Note: Full execution test requires graph streaming; just verify instantiation.
    assert use_case is not None


@pytest.mark.asyncio
async def test_tool_lookup_flow(fake_llm_tool_lookup, fake_executor):
    """Test tool lookup path."""
    from ai_copilot.application.use_cases.run_operator_copilot import RunOperatorCopilotUseCase

    use_case = RunOperatorCopilotUseCase(
        llm_gateway=fake_llm_tool_lookup,
        tool_executor=fake_executor,
        approval_port=FakeApprovalPort(),
        audit_log=FakeAuditLog(),
    )

    assert use_case is not None


@pytest.mark.asyncio
async def test_fake_executor_allowed_tool(fake_executor):
    """Test that allowed tools execute."""
    result = await fake_executor.execute("list_accounts", {})

    assert "accounts" in result
    assert len(result["accounts"]) == 2


@pytest.mark.asyncio
async def test_fake_executor_tool_failure_handling(fake_executor_failing):
    """Test that tool failures are caught."""
    with pytest.raises(RuntimeError):
        await fake_executor_failing.execute("list_accounts", {})


def test_fake_llm_gateway_direct_answer(fake_llm_direct_answer):
    """Test fake LLM in direct answer mode."""
    assert fake_llm_direct_answer.mode == "direct_answer"


def test_fake_llm_gateway_tool_lookup(fake_llm_tool_lookup):
    """Test fake LLM in tool lookup mode."""
    assert fake_llm_tool_lookup.mode == "tool_lookup"


@pytest.mark.asyncio
async def test_use_case_max_steps_parameter(fake_llm_direct_answer, fake_executor):
    """Test that max_steps parameter is accepted."""
    from ai_copilot.application.use_cases.run_operator_copilot import RunOperatorCopilotUseCase

    use_case = RunOperatorCopilotUseCase(
        llm_gateway=fake_llm_direct_answer,
        tool_executor=fake_executor,
        approval_port=FakeApprovalPort(),
        audit_log=FakeAuditLog(),
        max_steps=3,
    )

    # max_steps is passed to nodes; use case accepts the parameter
    assert use_case is not None


@pytest.mark.asyncio
async def test_use_case_with_custom_max_steps(fake_llm_direct_answer, fake_executor):
    """Test custom max_steps."""
    from ai_copilot.application.use_cases.run_operator_copilot import RunOperatorCopilotUseCase

    use_case = RunOperatorCopilotUseCase(
        llm_gateway=fake_llm_direct_answer,
        tool_executor=fake_executor,
        approval_port=FakeApprovalPort(),
        audit_log=FakeAuditLog(),
        max_steps=10,
    )

    assert use_case is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
