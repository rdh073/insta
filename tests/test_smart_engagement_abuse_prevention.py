"""Abuse-prevention tests for smart engagement workflow.

Invariants verified:
1. Graph can't auto-loop — discovery_attempted flag blocks second discovery
2. Graph can't auto-loop — approval_attempted flag blocks second approval
3. Graph can't execute in recommendation mode — NoOpExecutorAdapter rejects all writes
4. Graph can't bypass approval — execute_action_node checks approval_result.decision
5. Mode invariant — execute_action_node checks mode == 'execute'
6. Discovery limit: discover_candidates_node returns stop_reason when discovery_attempted=True
7. Approval limit: request_approval_node returns stop_reason when approval_attempted=True

These tests verify the policy rules in isolation (not full graph runs) so they
don't require LangGraph's state machine or MemorySaver.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest

from ai_copilot.application.smart_engagement.state import (
    AccountHealth,
    AuditEvent,
    DraftPayload,
    EngagementTarget,
    ExecutionResult,
    ProposedAction,
    RiskAssessment,
)
from ai_copilot.application.smart_engagement.ports import (
    AccountContextPort,
    AuditLogPort,
    ApprovalPort,
    EngagementCandidatePort,
    EngagementExecutorPort,
    RiskScoringPort,
)


# ---------------------------------------------------------------------------
# Fake ports
# ---------------------------------------------------------------------------

class _NullAuditLog(AuditLogPort):
    async def log_event(self, event: AuditEvent) -> None:
        pass

    async def get_audit_trail(self, thread_id: str) -> list[AuditEvent]:
        return []


class _FakeAccountContext(AccountContextPort):
    async def get_account_context(self, account_id) -> AccountHealth:
        return AccountHealth(status="active", login_state="logged_in", cooldown_until=None, proxy=None, recent_actions=0)

    async def validate_account_ready(self, account_id) -> bool:
        return True


class _FakeCandidates(EngagementCandidatePort):
    def __init__(self, candidates=None):
        self._candidates = candidates or []

    async def discover_candidates(self, account_id, goal, filters=None):
        return self._candidates

    async def get_target_metadata(self, target_id):
        return {}


class _FakeRisk(RiskScoringPort):
    async def assess_risk(self, action, target, account_health) -> RiskAssessment:
        return RiskAssessment(risk_level="medium", rule_hits=["write_action"], reasoning="write op", requires_approval=True)


class _FakeApproval(ApprovalPort):
    async def submit_for_approval(self, approval_request) -> str:
        return "apr_test"

    async def get_approval_status(self, approval_id):
        return {"approval_id": approval_id, "decision": "pending"}


def _make_nodes(executor=None, candidates=None):
    from ai_copilot.application.smart_engagement.nodes import SmartEngagementNodes

    return SmartEngagementNodes(
        account_context=_FakeAccountContext(),
        candidate_discovery=_FakeCandidates(candidates),
        risk_scoring=_FakeRisk(),
        approval=_FakeApproval(),
        executor=executor or _make_real_noop(),
        audit_log=_NullAuditLog(),
    )


def _make_real_noop():
    from ai_copilot.adapters.noop_executor_adapter import NoOpExecutorAdapter
    return NoOpExecutorAdapter()


def _state(**overrides):
    state = {
        "messages": [], "current_tool_calls": None, "tool_results": {}, "stop_reason": None, "step_count": 0,
        "thread_id": "t1", "mode": "recommendation", "goal": "follow tech accounts", "structured_goal": None,
        "account_id": "acc1", "account_health": None, "candidate_targets": [], "selected_target": None,
        "proposed_action": None, "draft_payload": None, "risk_assessment": None,
        "approval_request": None, "approval_result": None, "execution_result": None,
        "audit_trail": [], "discovery_attempted": False, "approval_attempted": False,
        "outcome_reason": None, "approval_timeout": 3600.0, "max_targets": 5, "max_actions_per_target": 3,
    }
    state.update(overrides)
    return state


# ===========================================================================
# Test 1: discovery_attempted flag blocks re-discovery
# ===========================================================================

@pytest.mark.asyncio
async def test_discovery_attempted_blocks_second_discovery():
    """discover_candidates_node must stop if discovery_attempted=True."""
    nodes = _make_nodes()

    state = _state(discovery_attempted=True)
    result = await nodes.discover_candidates_node(state)

    assert result["stop_reason"] == "discovery_limit_reached"
    assert "already attempted" in result["outcome_reason"].lower()


@pytest.mark.asyncio
async def test_discovery_not_attempted_allows_first_run():
    """First discovery run must proceed (discovery_attempted=False)."""
    candidates = [EngagementTarget(target_id="u1", target_type="account", metadata={})]
    nodes = _make_nodes(candidates=candidates)

    state = _state(discovery_attempted=False)
    result = await nodes.discover_candidates_node(state)

    # Should succeed and set the flag
    assert result["discovery_attempted"] is True
    assert result.get("stop_reason") is None


# ===========================================================================
# Test 2: approval_attempted flag blocks second approval
# ===========================================================================

@pytest.mark.asyncio
async def test_approval_attempted_blocks_second_approval():
    """request_approval_node must stop if approval_attempted=True (rejection is final)."""
    nodes = _make_nodes()

    state = _state(
        mode="execute",
        approval_attempted=True,
        proposed_action=ProposedAction(action_type="follow", target_id="u1", content=None, reasoning="r", expected_outcome="e"),
        risk_assessment=RiskAssessment(risk_level="medium", rule_hits=[], reasoning="ok", requires_approval=True),
    )
    result = await nodes.request_approval_node(state)

    assert result["stop_reason"] == "approval_limit_reached"
    assert "already attempted" in result["outcome_reason"].lower()


# ===========================================================================
# Test 3: NoOp executor rejects all writes
# ===========================================================================

@pytest.mark.asyncio
async def test_noop_executor_blocks_follow_in_execute_mode():
    """NoOpExecutorAdapter must reject follow even when mode='execute' and approved."""
    nodes = _make_nodes(executor=_make_real_noop())

    state = _state(
        mode="execute",
        proposed_action=ProposedAction(action_type="follow", target_id="u1", content=None, reasoning="r", expected_outcome="e"),
        approval_result={"approval_id": "x", "decision": "approved", "approver_notes": "", "edited_content": None, "decided_at": time.time()},
    )
    result = await nodes.execute_action_node(state)

    assert result["execution_result"]["success"] is False
    assert "blocked" in result["execution_result"]["reason"].lower() or "noop" in result["execution_result"]["reason"].lower() or "recommendation" in result["execution_result"]["reason"].lower()


@pytest.mark.asyncio
async def test_noop_executor_blocks_dm():
    from ai_copilot.adapters.noop_executor_adapter import NoOpExecutorAdapter

    noop = NoOpExecutorAdapter()
    result = await noop.execute_dm("target", "account", "hello")
    assert result["success"] is False


@pytest.mark.asyncio
async def test_noop_executor_blocks_comment():
    from ai_copilot.adapters.noop_executor_adapter import NoOpExecutorAdapter

    noop = NoOpExecutorAdapter()
    result = await noop.execute_comment("post_id", "account", "nice!")
    assert result["success"] is False


@pytest.mark.asyncio
async def test_noop_executor_blocks_like():
    from ai_copilot.adapters.noop_executor_adapter import NoOpExecutorAdapter

    noop = NoOpExecutorAdapter()
    result = await noop.execute_like("post_id", "account")
    assert result["success"] is False


# ===========================================================================
# Test 4: execute_action_node checks approval_result before executing
# ===========================================================================

@pytest.mark.asyncio
async def test_execute_action_blocked_without_approval():
    """execute_action_node must refuse to execute if approval is missing."""
    nodes = _make_nodes()

    state = _state(
        mode="execute",
        proposed_action=ProposedAction(action_type="follow", target_id="u1", content=None, reasoning="r", expected_outcome="e"),
        approval_result=None,  # No approval result
    )
    result = await nodes.execute_action_node(state)

    assert result["execution_result"]["success"] is False
    assert result["stop_reason"] == "not_approved"


@pytest.mark.asyncio
async def test_execute_action_blocked_with_rejected_approval():
    """execute_action_node must refuse to execute if approval was rejected."""
    nodes = _make_nodes()

    state = _state(
        mode="execute",
        proposed_action=ProposedAction(action_type="follow", target_id="u1", content=None, reasoning="r", expected_outcome="e"),
        approval_result={"approval_id": "x", "decision": "rejected", "approver_notes": "no", "edited_content": None, "decided_at": time.time()},
    )
    result = await nodes.execute_action_node(state)

    assert result["execution_result"]["success"] is False
    assert result["stop_reason"] == "not_approved"


# ===========================================================================
# Test 5: mode invariant in execute_action_node
# ===========================================================================

@pytest.mark.asyncio
async def test_execute_action_mode_invariant_recommendation_mode():
    """execute_action_node must refuse to execute in recommendation mode."""
    nodes = _make_nodes()

    state = _state(
        mode="recommendation",  # Wrong mode
        proposed_action=ProposedAction(action_type="follow", target_id="u1", content=None, reasoning="r", expected_outcome="e"),
        approval_result={"approval_id": "x", "decision": "approved", "approver_notes": "", "edited_content": None, "decided_at": time.time()},
    )
    result = await nodes.execute_action_node(state)

    assert result["execution_result"]["success"] is False
    assert result["stop_reason"] == "invariant_violated"
    assert "invariant" in result["execution_result"]["reason"].lower()


# ===========================================================================
# Test 6: gate_by_mode_node routes recommendation to log_outcome (skip executor)
# ===========================================================================

@pytest.mark.asyncio
async def test_recommendation_mode_never_reaches_executor():
    """In recommendation mode, gate_by_mode_node sets stop_reason=recommendation_only,
    which causes route_by_mode to return 'log_outcome', bypassing executor entirely."""
    nodes = _make_nodes()

    state = _state(
        mode="recommendation",
        proposed_action=ProposedAction(action_type="follow", target_id="u1", content=None, reasoning="r", expected_outcome="e"),
    )

    # gate_by_mode sets stop_reason
    gate_result = await nodes.gate_by_mode_node(state)
    assert gate_result["stop_reason"] == "recommendation_only"

    # route_by_mode sees mode=recommendation → log_outcome
    merged_state = {**state, **gate_result}
    route = nodes.route_by_mode(merged_state)
    assert route == "log_outcome"


# ===========================================================================
# Test 7: full end-to-end recommendation mode never calls executor
# ===========================================================================

@pytest.mark.asyncio
async def test_recommendation_workflow_with_noop_executor():
    """SmartEngagementUseCase in recommendation mode must produce recommendation
    with audit trail — NoOp executor injected so writes are physically blocked."""
    from langgraph.checkpoint.memory import MemorySaver
    from ai_copilot.application.use_cases.run_smart_engagement import SmartEngagementUseCase
    from ai_copilot.adapters.noop_executor_adapter import NoOpExecutorAdapter
    from ai_copilot.adapters.approval_adapter import InMemoryApprovalAdapter
    from ai_copilot.adapters.risk_scoring_adapter import RiskScoringAdapter

    candidates = [
        EngagementTarget(target_id="user_tech", target_type="account",
                         metadata={"engagement_rate": 0.1, "follower_count": 5000, "recent_posts": 5}),
    ]

    class _HealthyAccount(AccountContextPort):
        async def get_account_context(self, account_id) -> AccountHealth:
            return AccountHealth(status="active", login_state="logged_in", cooldown_until=None, proxy=None, recent_actions=0)

        async def validate_account_ready(self, account_id) -> bool:
            return True

    class _StaticCandidates(EngagementCandidatePort):
        async def discover_candidates(self, account_id, goal, filters=None):
            return candidates

        async def get_target_metadata(self, target_id):
            return {}

    class _CapturingAuditLog(AuditLogPort):
        def __init__(self):
            self.events = []

        async def log_event(self, event: AuditEvent) -> None:
            self.events.append(event)

        async def get_audit_trail(self, thread_id) -> list[AuditEvent]:
            return self.events

    audit_log = _CapturingAuditLog()

    use_case = SmartEngagementUseCase(
        account_context=_HealthyAccount(),
        candidate_discovery=_StaticCandidates(),
        risk_scoring=RiskScoringAdapter(),
        approval=InMemoryApprovalAdapter(),
        executor=NoOpExecutorAdapter(),
        audit_log=audit_log,
        checkpointer=MemorySaver(),
        max_steps=11,
    )

    result = await use_case.run(
        execution_mode="recommendation",
        goal="follow tech accounts",
        account_id="acc_1",
        max_targets=3,
    )

    # Mode preserved
    assert result["mode"] == "recommendation"
    # Should stop with recommendation_only
    assert result["status"] == "recommendation_only"
    # Has recommendation
    assert result.get("recommendation") is not None
    assert result["recommendation"]["action_type"] == "follow"
    assert result["recommendation"]["target"] == "user_tech"
    # Has risk assessment
    assert result.get("risk_assessment") is not None
    # No execution occurred
    assert result.get("execution") is None
    # Audit trail populated
    assert len(result.get("audit_trail", [])) > 0
    # Audit log received events
    assert len(audit_log.events) > 0

    # Verify no execution event was emitted (NoOp: writes blocked)
    exec_events = [e for e in audit_log.events if e["event_type"] == "action_executed"]
    assert len(exec_events) == 0, "No execution should occur in recommendation mode"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
