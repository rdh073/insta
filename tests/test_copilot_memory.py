"""Tests for copilot memory — port contract, adapter, node integration."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from ai_copilot.adapters.copilot_memory_adapter import InMemoryCopilotMemoryAdapter
from ai_copilot.application.ports import (
    CopilotMemoryPort,
    LLMGatewayPort,
    ToolExecutorPort,
    ApprovalPort,
    AuditLogPort,
)
from ai_copilot.application.graphs.operator_copilot import OperatorCopilotNodes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_audit_log():
    log = AsyncMock(spec=AuditLogPort)
    log.log = AsyncMock()
    return log


def _make_llm_gateway(response_content="{}"):
    gw = AsyncMock(spec=LLMGatewayPort)
    gw.request_completion = AsyncMock(return_value={"content": response_content, "finish_reason": "stop", "tool_calls": []})
    gw.get_default_model = MagicMock(return_value="gpt-4")
    return gw


def _make_tool_executor(schemas=None):
    te = AsyncMock(spec=ToolExecutorPort)
    te.get_schemas = MagicMock(return_value=schemas or [])
    te.execute = AsyncMock(return_value={"result": "ok"})
    return te


def _make_nodes(*, copilot_memory=None, llm_response="{}"):
    return OperatorCopilotNodes(
        llm_gateway=_make_llm_gateway(llm_response),
        tool_executor=_make_tool_executor(),
        approval_port=AsyncMock(spec=ApprovalPort),
        audit_log=_make_audit_log(),
        copilot_memory=copilot_memory,
    )


def _base_state(**overrides):
    state = {
        "messages": [], "current_tool_calls": None, "tool_results": {},
        "stop_reason": None, "step_count": 0, "thread_id": "t-test",
        "provider": None, "model": None, "api_key": None, "provider_base_url": None,
        "operator_request": "show my followers",
        "normalized_goal": "Show followers for the managed account",
        "mentions": [], "execution_plan": None, "proposed_tool_calls": [],
        "approved_tool_calls": [], "tool_policy_flags": {},
        "risk_assessment": None, "approval_request": None,
        "approval_result": None, "review_findings": None,
        "final_response": None, "approval_attempted": False,
    }
    state.update(overrides)
    return state


# ===========================================================================
# InMemoryCopilotMemoryAdapter — port contract
# ===========================================================================

class TestInMemoryCopilotMemoryAdapter:
    @pytest.mark.asyncio
    async def test_store_and_recall(self):
        mem = InMemoryCopilotMemoryAdapter()
        await mem.store_interaction_summary("op_1", {
            "goal": "show followers",
            "tools_used": ["get_followers"],
            "outcome": "success",
        })
        records = await mem.recall_recent_interactions("op_1")
        assert len(records) == 1
        assert records[0]["goal"] == "show followers"
        assert records[0]["outcome"] == "success"

    @pytest.mark.asyncio
    async def test_recall_empty(self):
        mem = InMemoryCopilotMemoryAdapter()
        records = await mem.recall_recent_interactions("op_1")
        assert records == []

    @pytest.mark.asyncio
    async def test_namespace_isolation(self):
        mem = InMemoryCopilotMemoryAdapter()
        await mem.store_interaction_summary("op_1", {"goal": "a", "tools_used": [], "outcome": "success"})
        await mem.store_interaction_summary("op_2", {"goal": "b", "tools_used": [], "outcome": "failed"})

        r1 = await mem.recall_recent_interactions("op_1")
        r2 = await mem.recall_recent_interactions("op_2")
        assert len(r1) == 1 and r1[0]["goal"] == "a"
        assert len(r2) == 1 and r2[0]["goal"] == "b"

    @pytest.mark.asyncio
    async def test_limit_respected(self):
        mem = InMemoryCopilotMemoryAdapter()
        for i in range(10):
            await mem.store_interaction_summary("op_1", {"goal": f"g{i}", "tools_used": [], "outcome": "success"})
        records = await mem.recall_recent_interactions("op_1", limit=3)
        assert len(records) == 3

    @pytest.mark.asyncio
    async def test_newest_first(self):
        mem = InMemoryCopilotMemoryAdapter()
        await mem.store_interaction_summary("op_1", {"goal": "old", "tools_used": [], "outcome": "success"})
        await mem.store_interaction_summary("op_1", {"goal": "new", "tools_used": [], "outcome": "success"})
        records = await mem.recall_recent_interactions("op_1")
        assert records[0]["goal"] == "new"

    @pytest.mark.asyncio
    async def test_timestamp_auto_set(self):
        mem = InMemoryCopilotMemoryAdapter()
        await mem.store_interaction_summary("op_1", {"goal": "x", "tools_used": [], "outcome": "success"})
        records = await mem.recall_recent_interactions("op_1")
        assert "timestamp" in records[0]
        assert records[0]["timestamp"] > 0


# ===========================================================================
# Node integration — plan_actions recalls memory
# ===========================================================================

class TestPlanActionsMemoryRecall:
    @pytest.mark.asyncio
    async def test_injects_recent_interactions_into_planner(self):
        """Memory recall results appear in the planner's user payload."""
        mem = InMemoryCopilotMemoryAdapter()
        await mem.store_interaction_summary("t-test", {
            "goal": "past goal", "tools_used": ["get_followers"], "outcome": "success",
        })

        captured_messages = []
        async def capture_completion(messages, **kwargs):
            captured_messages.extend(messages)
            return {"content": json.dumps({"execution_plan": [], "proposed_tool_calls": []}), "finish_reason": "stop", "tool_calls": []}

        nodes = _make_nodes(copilot_memory=mem)
        nodes.llm_gateway.request_completion = capture_completion
        state = _base_state()

        await nodes.plan_actions_node(state)

        # The user message should contain recent_interactions
        user_msg = next(m for m in captured_messages if m["role"] == "user")
        payload = json.loads(user_msg["content"])
        assert "recent_interactions" in payload
        assert payload["recent_interactions"][0]["goal"] == "past goal"

    @pytest.mark.asyncio
    async def test_no_memory_port_no_injection(self):
        """Without memory port, planner payload has no recent_interactions."""
        captured_messages = []
        async def capture_completion(messages, **kwargs):
            captured_messages.extend(messages)
            return {"content": json.dumps({"execution_plan": [], "proposed_tool_calls": []}), "finish_reason": "stop", "tool_calls": []}

        nodes = _make_nodes(copilot_memory=None)
        nodes.llm_gateway.request_completion = capture_completion
        state = _base_state()

        await nodes.plan_actions_node(state)

        user_msg = next(m for m in captured_messages if m["role"] == "user")
        payload = json.loads(user_msg["content"])
        assert "recent_interactions" not in payload

    @pytest.mark.asyncio
    async def test_memory_failure_degrades_gracefully(self):
        """If memory recall fails, plan_actions proceeds without crashing."""
        class _BrokenMemory(CopilotMemoryPort):
            async def recall_recent_interactions(self, *a, **kw):
                raise RuntimeError("store down")
            async def store_interaction_summary(self, *a, **kw):
                pass

        nodes = _make_nodes(copilot_memory=_BrokenMemory())
        state = _base_state()

        # Should not raise
        result = await nodes.plan_actions_node(state)
        assert "proposed_tool_calls" in result


# ===========================================================================
# Node integration — finish stores to memory
# ===========================================================================

class TestFinishStoresMemory:
    @pytest.mark.asyncio
    async def test_stores_interaction_summary(self):
        mem = InMemoryCopilotMemoryAdapter()
        nodes = _make_nodes(copilot_memory=mem)

        state = _base_state(
            normalized_goal="show followers",
            approved_tool_calls=[{"id": "c1", "name": "get_followers", "arguments": {}}],
        )

        await nodes.finish_node(state)

        records = await mem.recall_recent_interactions("t-test")
        assert len(records) == 1
        assert records[0]["goal"] == "show followers"
        assert records[0]["tools_used"] == ["get_followers"]
        assert records[0]["outcome"] == "success"

    @pytest.mark.asyncio
    async def test_stores_rejected_outcome(self):
        mem = InMemoryCopilotMemoryAdapter()
        nodes = _make_nodes(copilot_memory=mem)

        state = _base_state(stop_reason="rejected", normalized_goal="delete post")

        await nodes.finish_node(state)

        records = await mem.recall_recent_interactions("t-test")
        assert records[0]["outcome"] == "rejected"

    @pytest.mark.asyncio
    async def test_no_memory_port_no_crash(self):
        nodes = _make_nodes(copilot_memory=None)
        state = _base_state()

        result = await nodes.finish_node(state)
        assert result["stop_reason"] == "done"
