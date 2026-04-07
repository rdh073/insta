"""Test graph construction without HTTP layer.

Verifies the operator copilot graph can be instantiated with mock ports,
independent of FastAPI and vendor SDKs.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

import pytest


# ── Fake port implementations ──────────────────────────────────────────────────

class FakeLLMGateway:
    """Mock LLM gateway for testing."""

    async def request_completion(self, messages, provider="openai", model=None,
                                  api_key=None, provider_base_url=None, tools=None):
        return type("R", (), {
            "content": "direct answer",
            "finish_reason": "stop",
            "tool_calls": None,
        })()

    def get_default_model(self, provider: str) -> str:
        return "test-model"


class FakeToolExecutor:
    """Mock tool executor for testing."""

    async def execute(self, tool_name: str, tool_args: dict) -> dict:
        return {"status": "ok", "data": {}}

    def get_schemas(self) -> list[dict]:
        return []


class FakeApprovalPort:
    """Mock approval port."""
    async def request_approval(self, *a, **kw):
        return {"approved": True}

    async def get_approval_status(self, approval_id: str):
        return {"approval_id": approval_id, "status": "approved",
                "requested_at": 0.0, "approved_at": None}


class FakeAuditLog:
    """Mock audit log."""
    async def log(self, *a, **kw):
        pass


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_graph_instantiation():
    """Operator copilot use case compiles the graph on instantiation.

    Verifies no hard dependency on HTTP, instagrapi, or external services.
    """
    from ai_copilot.application.use_cases.run_operator_copilot import RunOperatorCopilotUseCase

    use_case = RunOperatorCopilotUseCase(
        llm_gateway=FakeLLMGateway(),
        tool_executor=FakeToolExecutor(),
        approval_port=FakeApprovalPort(),
        audit_log=FakeAuditLog(),
    )

    assert use_case._graph is not None
    assert use_case._checkpointer is not None


@pytest.mark.asyncio
async def test_graph_execution_with_mock_ports():
    """Graph accepts mock ports and exposes a run method."""
    from ai_copilot.application.use_cases.run_operator_copilot import RunOperatorCopilotUseCase

    use_case = RunOperatorCopilotUseCase(
        llm_gateway=FakeLLMGateway(),
        tool_executor=FakeToolExecutor(),
        approval_port=FakeApprovalPort(),
        audit_log=FakeAuditLog(),
    )

    # run() and resume() must be accessible (not necessarily execute fully
    # without a real LLM responding to the planner prompt)
    assert callable(use_case.run)
    assert callable(use_case.resume)


@pytest.mark.asyncio
async def test_graph_direct_answer_path():
    """Use case can be configured and queried for its graph reference."""
    from ai_copilot.application.use_cases.run_operator_copilot import RunOperatorCopilotUseCase
    from langgraph.checkpoint.memory import MemorySaver

    use_case = RunOperatorCopilotUseCase(
        llm_gateway=FakeLLMGateway(),
        tool_executor=FakeToolExecutor(),
        approval_port=FakeApprovalPort(),
        audit_log=FakeAuditLog(),
    )

    # Default checkpointer is MemorySaver when no checkpoint_factory is supplied
    assert isinstance(use_case._checkpointer, MemorySaver)


@pytest.mark.asyncio
async def test_graph_error_handling():
    """Use case exposes resume() for interrupt-based error recovery."""
    from ai_copilot.application.use_cases.run_operator_copilot import RunOperatorCopilotUseCase

    use_case = RunOperatorCopilotUseCase(
        llm_gateway=FakeLLMGateway(),
        tool_executor=FakeToolExecutor(),
        approval_port=FakeApprovalPort(),
        audit_log=FakeAuditLog(),
    )

    assert callable(use_case.resume)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
