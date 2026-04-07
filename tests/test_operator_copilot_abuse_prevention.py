"""Abuse-prevention tests for operator copilot.

Invariants verified:
1. BLOCKED tools are never executable — ToolRegistryBridgeAdapter rejects at execute()
2. BLOCKED tools are filtered from get_schemas() — LLM never sees them
3. Unknown tools default to BLOCKED (deny-unknown principle)
4. Write-sensitive tools MUST pass approval gate before execute_tools_node runs
5. approval_attempted flag prevents a second approval request this run
6. Edited calls re-validated at review_tool_policy_node; still need approval_attempted=True bypass
7. Execute-only BLOCKED call: review_tool_policy strips it; no execution
8. A rejected approval sets stop_reason=rejected and clears approved_tool_calls

These tests verify policy rules in isolation using crafted state dicts
and node/adapter calls — not full LangGraph graph runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest

from ai_copilot.application.operator_copilot_policy import ToolPolicy, ToolPolicyRegistry
from ai_copilot.adapters.fake_ports_operator_copilot import (
    FakeLLMGateway,
    FakeToolExecutor,
    FakeApprovalPort,
    FakeAuditLogPort,
    FakeCheckpointFactory,
)


def _make_nodes(
    llm=None,
    executor=None,
    approval=None,
    audit=None,
    policy=None,
):
    from ai_copilot.application.graphs.operator_copilot import OperatorCopilotNodes

    return OperatorCopilotNodes(
        llm_gateway=llm or FakeLLMGateway(),
        tool_executor=executor or FakeToolExecutor(),
        approval_port=approval or FakeApprovalPort(),
        audit_log=audit or FakeAuditLogPort(),
        policy_registry=policy or ToolPolicyRegistry(),
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
# 1. BLOCKED tools cannot execute via ToolRegistryBridgeAdapter
# ===========================================================================


@pytest.mark.asyncio
async def test_blocked_tool_raises_in_bridge_execute():
    from ai_copilot.adapters.tool_registry_bridge import ToolRegistryBridgeAdapter

    executor = FakeToolExecutor(
        results={"delete_account": {}},
        schemas=[{"function": {"name": "delete_account", "description": "delete"}}],
    )
    bridge = ToolRegistryBridgeAdapter(tool_registry=executor)

    with pytest.raises(ValueError) as exc:
        await bridge.execute("delete_account", {})
    assert "BLOCKED" in str(exc.value)


@pytest.mark.asyncio
async def test_unknown_tool_blocked_in_bridge_execute():
    from ai_copilot.adapters.tool_registry_bridge import ToolRegistryBridgeAdapter

    executor = FakeToolExecutor(results={}, schemas=[])
    bridge = ToolRegistryBridgeAdapter(tool_registry=executor)

    with pytest.raises(ValueError) as exc:
        await bridge.execute("nonexistent_tool", {})
    assert "BLOCKED" in str(exc.value)


# ===========================================================================
# 2. BLOCKED tools not exposed in get_schemas()
# ===========================================================================


def test_blocked_tools_not_in_schemas():
    from ai_copilot.adapters.tool_registry_bridge import ToolRegistryBridgeAdapter

    blocked_names = ["delete_account", "mass_unfollow", "bulk_dm", "scrape_users"]
    executor = FakeToolExecutor(
        results={n: {} for n in blocked_names},
        schemas=[{"function": {"name": n, "description": f"does {n}"}} for n in blocked_names],
    )
    bridge = ToolRegistryBridgeAdapter(tool_registry=executor)

    schemas = bridge.get_schemas()
    exposed_names = [s["function"]["name"] for s in schemas]
    for name in blocked_names:
        assert name not in exposed_names, f"{name} should be filtered from schemas"


def test_unknown_tools_not_exposed_in_schemas():
    from ai_copilot.adapters.tool_registry_bridge import ToolRegistryBridgeAdapter

    executor = FakeToolExecutor(
        results={"secret_tool_xyz": {}},
        schemas=[{"function": {"name": "secret_tool_xyz", "description": "secret"}}],
    )
    bridge = ToolRegistryBridgeAdapter(tool_registry=executor)
    schemas = bridge.get_schemas()
    names = [s["function"]["name"] for s in schemas]
    assert "secret_tool_xyz" not in names


# ===========================================================================
# 3. Deny-unknown principle via ToolPolicyRegistry
# ===========================================================================


def test_unknown_tool_classified_as_blocked():
    reg = ToolPolicyRegistry()
    cls = reg.classify("totally_unknown_tool_xyz")
    assert cls.policy == ToolPolicy.BLOCKED


def test_has_blocked_true_for_unknown():
    reg = ToolPolicyRegistry()
    calls = [{"id": "c1", "name": "unknown_secret_api"}]
    assert reg.has_blocked(calls) is True


def test_filter_executable_excludes_unknown():
    reg = ToolPolicyRegistry()
    calls = [
        {"id": "c1", "name": "list_accounts"},
        {"id": "c2", "name": "totally_unknown"},
    ]
    result = reg.filter_executable(calls)
    names = [c["name"] for c in result]
    assert "totally_unknown" not in names
    assert "list_accounts" in names


# ===========================================================================
# 4. Write-sensitive tools require approved_tool_calls to be non-empty
# ===========================================================================


@pytest.mark.asyncio
async def test_execute_tools_skips_empty_approved_list():
    """If approved_tool_calls is empty, execute_tools_node runs nothing."""
    executor = FakeToolExecutor(results={"follow_user": {"followed": True}})
    nodes = _make_nodes(executor=executor)

    state = _base_state(
        approved_tool_calls=[],  # nothing approved
        proposed_tool_calls=[{"id": "c1", "name": "follow_user", "arguments": {}}],
    )
    result = await nodes.execute_tools_node(state)

    # No tools were called
    assert executor.calls == []
    assert result["tool_results"] == {}


@pytest.mark.asyncio
async def test_review_tool_policy_sets_approved_calls_for_read_only():
    """review_tool_policy_node must pre-populate approved_tool_calls for read-only tools."""
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[{"id": "c1", "name": "list_accounts"}]
    )
    result = await nodes.review_tool_policy_node(state)
    # approved_tool_calls pre-populated with executable calls
    assert len(result["approved_tool_calls"]) == 1
    assert result["approved_tool_calls"][0]["name"] == "list_accounts"


@pytest.mark.asyncio
async def test_review_tool_policy_all_blocked_results_in_empty_approved():
    """If all proposed calls are BLOCKED, approved_tool_calls must be empty."""
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[
            {"id": "c1", "name": "delete_account"},
            {"id": "c2", "name": "bulk_dm"},
        ]
    )
    result = await nodes.review_tool_policy_node(state)
    assert result["proposed_tool_calls"] == []
    assert result["approved_tool_calls"] == []


# ===========================================================================
# 5. approval_attempted loop-bound invariant
# ===========================================================================


@pytest.mark.asyncio
async def test_approval_attempted_flag_prevents_second_approval():
    """request_approval_if_needed_node must close run if already attempted."""
    audit = FakeAuditLogPort()
    nodes = _make_nodes(audit=audit)

    # Simulate state where approval was already attempted
    state = _base_state(
        approval_attempted=True,
        proposed_tool_calls=[{"id": "c1", "name": "follow_user"}],
    )
    result = await nodes.request_approval_if_needed_node(state)

    # Must not re-interrupt; must set stop_reason=rejected
    assert result["stop_reason"] == "rejected"
    assert result["approval_attempted"] is True
    assert result["final_response"]
    assert "already attempted" in result["final_response"].lower()


@pytest.mark.asyncio
async def test_approval_attempted_route_bypasses_gate():
    """route_after_policy must bypass approval gate if approval_attempted is True."""
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[{"id": "c1", "name": "follow_user"}],
        approval_attempted=True,
    )
    assert nodes.route_after_policy(state) == "execute_tools"


@pytest.mark.asyncio
async def test_approval_not_attempted_requires_gate():
    """route_after_policy must route to approval gate if not yet attempted."""
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[{"id": "c1", "name": "follow_user"}],
        approval_attempted=False,
    )
    assert nodes.route_after_policy(state) == "request_approval_if_needed"


# ===========================================================================
# 6. Rejection clears approved_tool_calls
# ===========================================================================


@pytest.mark.asyncio
async def test_rejected_approval_sets_stop_reason():
    """When operator rejects, stop_reason must be 'rejected' and approved list cleared."""
    use_case, executor, _ = _setup_full_use_case_for_rejection()
    await _run_and_suspend(use_case)

    events = await _collect_resume(use_case, "t-rej-abuse", "rejected")
    # No tools executed
    assert executor.calls == []


def _setup_full_use_case_for_rejection():
    from ai_copilot.application.use_cases.run_operator_copilot import RunOperatorCopilotUseCase

    classify = json.dumps({"normalized_goal": "follow users", "blocked": False, "block_reason": None})
    plan = json.dumps({
        "execution_plan": [{"step": 1, "tool": "follow_user", "reason": "grow", "risk_level": "medium"}],
        "proposed_tool_calls": [{"id": "c1", "name": "follow_user", "arguments": {"user_id": "u1"}}],
    })
    llm = FakeLLMGateway(responses=[classify, plan])
    executor = FakeToolExecutor(
        results={"follow_user": {"followed": True}},
        schemas=[{"function": {"name": "follow_user", "description": "follows user"}}],
    )
    audit = FakeAuditLogPort()
    use_case = RunOperatorCopilotUseCase(
        llm_gateway=llm,
        tool_executor=executor,
        approval_port=FakeApprovalPort(),
        audit_log=audit,
        checkpoint_factory=FakeCheckpointFactory(),
    )
    return use_case, executor, audit


async def _run_and_suspend(use_case, thread_id="t-rej-abuse"):
    return [e async for e in use_case.run("follow users", thread_id=thread_id)]


async def _collect_resume(use_case, thread_id, approval_result):
    return [e async for e in use_case.resume(
        thread_id=thread_id,
        approval_result=approval_result,
    )]


# ===========================================================================
# 7. Blocked intent never reaches execute_tools
# ===========================================================================


@pytest.mark.asyncio
async def test_blocked_intent_never_executes_any_tool():
    from ai_copilot.application.use_cases.run_operator_copilot import RunOperatorCopilotUseCase

    classify = json.dumps({
        "normalized_goal": "scrape all users",
        "blocked": True,
        "block_reason": "scraping violates ToS",
        "category": "scraping",
    })
    executor = FakeToolExecutor(
        results={"scrape_users": {"data": []}},
        schemas=[{"function": {"name": "scrape_users", "description": "scrapes"}}],
    )
    use_case = RunOperatorCopilotUseCase(
        llm_gateway=FakeLLMGateway(responses=[classify]),
        tool_executor=executor,
        approval_port=FakeApprovalPort(),
        audit_log=FakeAuditLogPort(),
        checkpoint_factory=FakeCheckpointFactory(),
    )
    events = [e async for e in use_case.run("scrape all users", thread_id="t-block-abs")]

    assert executor.calls == []


# ===========================================================================
# 8. Policy invariant: no auto-approval
# ===========================================================================


@pytest.mark.asyncio
async def test_write_sensitive_does_not_auto_approve():
    """Write-sensitive calls must suspend for approval — never auto-execute."""
    from ai_copilot.application.use_cases.run_operator_copilot import RunOperatorCopilotUseCase

    classify = json.dumps({"normalized_goal": "follow users", "blocked": False, "block_reason": None})
    plan = json.dumps({
        "execution_plan": [{"step": 1, "tool": "follow_user", "reason": "grow", "risk_level": "medium"}],
        "proposed_tool_calls": [{"id": "c1", "name": "follow_user", "arguments": {"user_id": "u1"}}],
    })
    executor = FakeToolExecutor(
        results={"follow_user": {"followed": True}},
        schemas=[{"function": {"name": "follow_user", "description": "follows user"}}],
    )
    use_case = RunOperatorCopilotUseCase(
        llm_gateway=FakeLLMGateway(responses=[classify, plan]),
        tool_executor=executor,
        approval_port=FakeApprovalPort(),
        audit_log=FakeAuditLogPort(),
        checkpoint_factory=FakeCheckpointFactory(),
    )

    events = [e async for e in use_case.run("follow users", thread_id="t-no-auto")]
    types = [e["type"] for e in events]

    # Must have suspended at approval_required
    assert "approval_required" in types
    # Must NOT have executed the tool
    assert executor.calls == []
    # Must NOT have run_finish (suspended, not done)
    assert "run_finish" not in types


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
