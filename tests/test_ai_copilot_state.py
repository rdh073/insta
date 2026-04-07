"""Unit tests for ai_copilot state transitions.

Tests the OperatorCopilotState TypedDict and graph state flow.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest


@pytest.fixture
def initial_state():
    """Create an initial OperatorCopilotState."""
    from ai_copilot.application.state import OperatorCopilotState

    state: OperatorCopilotState = {
        "messages": [{"role": "user", "content": "List my accounts"}],
        "current_tool_calls": None,
        "tool_results": {},
        "stop_reason": None,
        "step_count": 0,
    }
    return state


def test_state_creation(initial_state):
    """Test that OperatorCopilotState can be created."""
    assert initial_state["messages"]
    assert initial_state["current_tool_calls"] is None
    assert initial_state["tool_results"] == {}
    assert initial_state["stop_reason"] is None
    assert initial_state["step_count"] == 0


def test_state_messages_accumulation(initial_state):
    """Test messages can accumulate (for add_messages reducer)."""
    state = initial_state

    # Add an assistant response
    new_msg = {"role": "assistant", "content": "Here are your accounts..."}
    state["messages"].append(new_msg)

    assert len(state["messages"]) == 2
    assert state["messages"][-1]["role"] == "assistant"


def test_state_tool_calls_flow(initial_state):
    """Test tool call planning flow."""
    state = initial_state

    # Simulate plan phase
    state["current_tool_calls"] = {
        "call-1": {
            "function": "list_accounts",
            "arguments": {}
        }
    }

    assert state["current_tool_calls"] is not None
    assert "call-1" in state["current_tool_calls"]


def test_state_tool_results_accumulation(initial_state):
    """Test tool results accumulate."""
    state = initial_state

    # Simulate execution
    state["tool_results"]["call-1"] = {
        "tool": "list_accounts",
        "status": "success",
        "result": {"accounts": ["account1", "account2"]}
    }

    assert len(state["tool_results"]) == 1
    assert state["tool_results"]["call-1"]["status"] == "success"


def test_state_step_count(initial_state):
    """Test step counter for iteration limit."""
    state = initial_state

    # Simulate loop iterations
    for i in range(1, 4):
        state["step_count"] = i
        assert state["step_count"] == i

    # Should stop at max_steps
    assert state["step_count"] == 3


def test_state_stop_reason(initial_state):
    """Test stop_reason field."""
    state = initial_state

    # Test different stop reasons
    for reason in ["stop", "max_steps", "error"]:
        state["stop_reason"] = reason
        assert state["stop_reason"] == reason


def test_state_direct_answer_path(initial_state):
    """Test state for direct answer path (no tools)."""
    state = initial_state

    # Direct answer doesn't set current_tool_calls
    assert state["current_tool_calls"] is None
    assert state["tool_results"] == {}
    # Only messages accumulate
    state["messages"].append({
        "role": "assistant",
        "content": "Direct answer without tools"
    })

    assert len(state["messages"]) == 2


def test_state_tool_lookup_path(initial_state):
    """Test state for tool lookup path."""
    state = initial_state

    # Tool lookup path: plan, execute, summarize
    state["current_tool_calls"] = {
        "call-1": {"function": "get_account_info", "arguments": {"id": "123"}}
    }
    state["tool_results"]["call-1"] = {"account_name": "My Account"}
    state["messages"].append({
        "role": "assistant",
        "content": "Your account is My Account"
    })

    assert state["current_tool_calls"] is not None
    assert len(state["tool_results"]) == 1
    assert len(state["messages"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
