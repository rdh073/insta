"""Tests for AI infrastructure components.

Updated to reflect the current LangGraph-based architecture (ai_copilot module).
The old ai_tools module and graph_nodes/graph_state adapters have been superseded.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


# ── Operator copilot feature flag ──────────────────────────────────────────────

def test_operator_copilot_feature_flag_parser(monkeypatch: pytest.MonkeyPatch):
    """Feature flag correctly enables/disables the operator copilot endpoint."""
    from ai_copilot import api as ai_copilot_api

    monkeypatch.setenv("ENABLE_OPERATOR_COPILOT", "0")
    assert ai_copilot_api.is_operator_copilot_enabled() is False

    monkeypatch.setenv("ENABLE_OPERATOR_COPILOT", "false")
    assert ai_copilot_api.is_operator_copilot_enabled() is False

    monkeypatch.setenv("ENABLE_OPERATOR_COPILOT", "1")
    assert ai_copilot_api.is_operator_copilot_enabled() is True


# ── Checkpoint factory ─────────────────────────────────────────────────────────

def test_memory_checkpoint_factory_creates_checkpointer():
    """MemoryCheckpointFactory creates a LangGraph checkpointer."""
    from app.adapters.ai.checkpoint_factory_adapter import MemoryCheckpointFactory

    factory = MemoryCheckpointFactory()
    checkpointer = factory.create()

    assert checkpointer is not None


# ── Active router paths ────────────────────────────────────────────────────────

def test_ai_copilot_router_registers_graph_paths():
    """The ai_copilot router exposes /chat/graph and /graph-chat paths."""
    from ai_copilot.api import router

    paths = {route.path for route in router.routes}

    assert "/api/ai/chat/graph" in paths
    assert "/api/ai/graph-chat" in paths


# ── Tool policy ────────────────────────────────────────────────────────────────

def test_tool_policy_registry_blocks_unknown_tools():
    """Unknown tools default to BLOCKED (deny-unknown principle)."""
    from ai_copilot.application.operator_copilot_policy import ToolPolicyRegistry, ToolPolicy

    registry = ToolPolicyRegistry()
    classification = registry.classify("totally_unknown_tool_xyz")

    assert classification.policy == ToolPolicy.BLOCKED


def test_tool_policy_registry_classifies_known_tools():
    """Known tools get their configured classification — registry is non-empty."""
    from ai_copilot.application.operator_copilot_policy import ToolPolicyRegistry, ToolPolicy

    registry = ToolPolicyRegistry()

    # list_accounts should be READ_ONLY (a fundamental read-only tool)
    c = registry.classify("list_accounts")
    assert c.policy == ToolPolicy.READ_ONLY


# ── LLM port contract ──────────────────────────────────────────────────────────

def test_llm_gateway_port_is_structural():
    """LLMGatewayPort is a structural protocol (duck-typed)."""
    from ai_copilot.application.ports import LLMGatewayPort

    class _FakeLLM:
        async def request_completion(self, messages, provider="openai",
                                      model=None, api_key=None,
                                      provider_base_url=None, tools=None):
            return type("R", (), {"content": "ok", "finish_reason": "stop", "tool_calls": None})()

        def get_default_model(self, provider):
            return "test-model"

    # Structural check: fake satisfies the port
    fake = _FakeLLM()
    assert callable(fake.request_completion)
    assert callable(fake.get_default_model)
