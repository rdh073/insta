"""Graph routing tests for operator copilot — all conditional edges.

Tests every conditional edge decision:
- route_after_classify:  blocked → summarize_result, normal → plan_actions
- route_after_plan:      no calls → summarize_result, has calls → review_tool_policy
- route_after_policy:    all read_only → execute_tools
                         write_sensitive + not attempted → request_approval_if_needed
                         write_sensitive + attempted → execute_tools (loop-bound bypass)
                         no executable calls → summarize_result
- route_after_approval:  approved → execute_tools
                         edited → review_tool_policy
                         rejected → summarize_result
                         timeout → summarize_result
                         missing result → summarize_result

Each test exercises the router function directly with crafted state.
No LangGraph pipeline required; state is passed as a plain dict.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest

from ai_copilot.adapters.fake_ports_operator_copilot import (
    FakeLLMGateway,
    FakeToolExecutor,
    FakeApprovalPort,
    FakeAuditLogPort,
)


def _make_nodes():
    from ai_copilot.application.graphs.operator_copilot import OperatorCopilotNodes

    return OperatorCopilotNodes(
        llm_gateway=FakeLLMGateway(),
        tool_executor=FakeToolExecutor(),
        approval_port=FakeApprovalPort(),
        audit_log=FakeAuditLogPort(),
    )


def _base_state(**overrides):
    state = {
        "messages": [],
        "current_tool_calls": None,
        "tool_results": {},
        "stop_reason": None,
        "step_count": 1,
        "thread_id": "test-thread",
        "operator_request": "show my accounts",
        "normalized_goal": "list all accounts",
        "execution_plan": None,
        "proposed_tool_calls": [],
        "approved_tool_calls": [],
        "tool_policy_flags": {},
        "risk_assessment": None,
        "approval_request": None,
        "approval_result": None,
        "review_findings": None,
        "final_response": None,
        "approval_attempted": False,
    }
    state.update(overrides)
    return state


# ===========================================================================
# route_after_classify
# ===========================================================================


def test_route_after_classify_blocked_routes_to_summarize():
    nodes = _make_nodes()
    state = _base_state(stop_reason="blocked")
    assert nodes.route_after_classify(state) == "summarize_result"


def test_route_after_classify_normal_routes_to_plan():
    nodes = _make_nodes()
    state = _base_state(stop_reason=None)
    assert nodes.route_after_classify(state) == "plan_actions"


def test_route_after_classify_non_blocked_reason_routes_to_plan():
    nodes = _make_nodes()
    # Any stop_reason that is not "blocked" should go to plan_actions
    state = _base_state(stop_reason="error")
    assert nodes.route_after_classify(state) == "plan_actions"


# ===========================================================================
# route_after_plan
# ===========================================================================


def test_route_after_plan_no_calls_routes_to_summarize():
    nodes = _make_nodes()
    state = _base_state(proposed_tool_calls=[])
    assert nodes.route_after_plan(state) == "summarize_result"


def test_route_after_plan_has_calls_routes_to_policy():
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[{"id": "c1", "name": "list_accounts", "arguments": {}}]
    )
    assert nodes.route_after_plan(state) == "review_tool_policy"


def test_route_after_plan_multiple_calls_routes_to_policy():
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[
            {"id": "c1", "name": "list_accounts"},
            {"id": "c2", "name": "get_posts"},
        ]
    )
    assert nodes.route_after_plan(state) == "review_tool_policy"


# ===========================================================================
# route_after_policy
# ===========================================================================


def test_route_after_policy_no_calls_routes_to_summarize():
    nodes = _make_nodes()
    state = _base_state(proposed_tool_calls=[])
    assert nodes.route_after_policy(state) == "summarize_result"


def test_route_after_policy_all_read_only_routes_to_execute():
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[
            {"id": "c1", "name": "list_accounts"},
            {"id": "c2", "name": "get_posts"},
        ]
    )
    assert nodes.route_after_policy(state) == "execute_tools"


def test_route_after_policy_write_sensitive_not_attempted_routes_to_approval():
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[{"id": "c1", "name": "follow_user"}],
        approval_attempted=False,
    )
    assert nodes.route_after_policy(state) == "request_approval_if_needed"


def test_route_after_policy_write_sensitive_attempted_routes_to_execute():
    """Loop-bound: if approval already attempted, bypass approval gate."""
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[{"id": "c1", "name": "follow_user"}],
        approval_attempted=True,
    )
    assert nodes.route_after_policy(state) == "execute_tools"


def test_route_after_policy_mixed_read_write_routes_to_approval():
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[
            {"id": "c1", "name": "list_accounts"},   # read_only
            {"id": "c2", "name": "follow_user"},     # write_sensitive
        ],
        approval_attempted=False,
    )
    assert nodes.route_after_policy(state) == "request_approval_if_needed"


# ===========================================================================
# route_after_approval
# ===========================================================================


def test_route_after_approval_approved_routes_to_execute():
    nodes = _make_nodes()
    state = _base_state(approval_result="approved")
    assert nodes.route_after_approval(state) == "execute_tools"


def test_route_after_approval_edited_routes_to_policy():
    nodes = _make_nodes()
    state = _base_state(approval_result="edited")
    assert nodes.route_after_approval(state) == "review_tool_policy"


def test_route_after_approval_rejected_routes_to_summarize():
    nodes = _make_nodes()
    state = _base_state(approval_result="rejected")
    assert nodes.route_after_approval(state) == "summarize_result"


def test_route_after_approval_timeout_routes_to_summarize():
    nodes = _make_nodes()
    state = _base_state(approval_result="timeout")
    assert nodes.route_after_approval(state) == "summarize_result"


def test_route_after_approval_none_routes_to_summarize():
    nodes = _make_nodes()
    state = _base_state(approval_result=None)
    assert nodes.route_after_approval(state) == "summarize_result"


def test_route_after_approval_unexpected_value_routes_to_summarize():
    nodes = _make_nodes()
    state = _base_state(approval_result="garbage_value")
    assert nodes.route_after_approval(state) == "summarize_result"


# ===========================================================================
# Routing invariants: comprehensive path coverage
# ===========================================================================


def test_blocked_path_bypasses_planning():
    """Blocked intent must skip plan_actions entirely."""
    nodes = _make_nodes()
    state = _base_state(stop_reason="blocked")
    # Verify classify routes directly to summarize
    assert nodes.route_after_classify(state) == "summarize_result"
    # summarize routes to finish (no conditional routing needed — linear edge)


def test_read_only_path_skips_approval():
    """All-read-only calls must never touch request_approval_if_needed."""
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[{"id": "c1", "name": "list_accounts"}],
        approval_attempted=False,
    )
    # Policy review routes directly to execute
    assert nodes.route_after_policy(state) == "execute_tools"


def test_write_sensitive_path_requires_approval_first_time():
    """Write-sensitive calls must go through approval on first attempt."""
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[{"id": "c1", "name": "follow_user"}],
        approval_attempted=False,
    )
    assert nodes.route_after_policy(state) == "request_approval_if_needed"


def test_edited_then_revalidated_skips_second_approval():
    """After edit re-validation, approval_attempted=True bypasses gate."""
    nodes = _make_nodes()
    # Simulate state after edited calls re-enter review_tool_policy:
    # approval_attempted is True (set by request_approval_if_needed_node)
    state = _base_state(
        proposed_tool_calls=[{"id": "c1", "name": "follow_user"}],
        approval_attempted=True,
    )
    assert nodes.route_after_policy(state) == "execute_tools"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
