"""Graph routing tests for smart engagement workflow.

Tests every conditional edge decision:
- route_after_account_context: healthy → discover, unhealthy → log_outcome
- route_after_discovery: candidates found → rank, none → log_outcome
- route_after_risk: low/medium → gate_by_mode, high → log_outcome
- route_by_mode: recommendation → log_outcome, execute → request_approval
- route_after_approval: approved → execute, rejected/missing → log_outcome

Each routing test exercises the router function directly with crafted state
to verify fail-fast rules without running the full LangGraph pipeline.
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

class _InMemoryAuditLog(AuditLogPort):
    def __init__(self):
        self.events: list[AuditEvent] = []

    async def log_event(self, event: AuditEvent) -> None:
        self.events.append(event)

    async def get_audit_trail(self, thread_id: str) -> list[AuditEvent]:
        return self.events


class _FakeAccountContext(AccountContextPort):
    def __init__(self, health):
        self._health = health

    async def get_account_context(self, account_id) -> AccountHealth:
        return AccountHealth(**self._health)

    async def validate_account_ready(self, account_id) -> bool:
        return self._health.get("status") == "active"


class _FakeCandidates(EngagementCandidatePort):
    def __init__(self, candidates):
        self._candidates = candidates

    async def discover_candidates(self, account_id, goal, filters=None):
        return self._candidates

    async def get_target_metadata(self, target_id):
        return {}


class _FakeRisk(RiskScoringPort):
    def __init__(self, level="low"):
        self._level = level

    async def assess_risk(self, action, target, account_health) -> RiskAssessment:
        return RiskAssessment(
            risk_level=self._level,
            rule_hits=[] if self._level == "low" else [f"{self._level}_rule"],
            reasoning=f"risk={self._level}",
            requires_approval=self._level != "low",
        )


class _FakeApproval(ApprovalPort):
    async def submit_for_approval(self, approval_request) -> str:
        return "apr_test"

    async def get_approval_status(self, approval_id):
        return {"approval_id": approval_id, "decision": "pending"}


class _FakeExecutor(EngagementExecutorPort):
    async def execute_follow(self, target_id, account_id) -> ExecutionResult:
        return ExecutionResult(success=False, action_id=None, reason="NoOp", timestamp=time.time())

    async def execute_dm(self, target_id, account_id, message) -> ExecutionResult:
        return ExecutionResult(success=False, action_id=None, reason="NoOp", timestamp=time.time())

    async def execute_comment(self, post_id, account_id, comment_text) -> ExecutionResult:
        return ExecutionResult(success=False, action_id=None, reason="NoOp", timestamp=time.time())

    async def execute_like(self, post_id, account_id) -> ExecutionResult:
        return ExecutionResult(success=False, action_id=None, reason="NoOp", timestamp=time.time())

    def is_write_action(self, action_type) -> bool:
        return True


def _make_nodes(**kwargs):
    from ai_copilot.application.smart_engagement.nodes import SmartEngagementNodes

    return SmartEngagementNodes(
        account_context=kwargs.get("account_context", _FakeAccountContext(
            {"status": "active", "login_state": "logged_in", "cooldown_until": None, "proxy": None, "recent_actions": 0}
        )),
        candidate_discovery=kwargs.get("candidates", _FakeCandidates([])),
        risk_scoring=kwargs.get("risk", _FakeRisk("low")),
        approval=_FakeApproval(),
        executor=_FakeExecutor(),
        audit_log=_InMemoryAuditLog(),
    )


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
# route_after_account_context
# ===========================================================================

def test_route_healthy_account_to_discover():
    nodes = _make_nodes()
    health = AccountHealth(status="active", login_state="logged_in", cooldown_until=None, proxy=None, recent_actions=0)
    state = _state(account_health=health)
    assert nodes.route_after_account_context(state) == "discover_candidates"


def test_route_inactive_account_to_log_outcome():
    nodes = _make_nodes()
    health = AccountHealth(status="cooldown", login_state="logged_in", cooldown_until=None, proxy=None, recent_actions=0)
    state = _state(account_health=health)
    assert nodes.route_after_account_context(state) == "log_outcome"


def test_route_no_account_health_to_log_outcome():
    nodes = _make_nodes()
    state = _state(account_health=None)
    assert nodes.route_after_account_context(state) == "log_outcome"


def test_route_stop_reason_set_to_log_outcome():
    nodes = _make_nodes()
    health = AccountHealth(status="active", login_state="logged_in", cooldown_until=None, proxy=None, recent_actions=0)
    state = _state(account_health=health, stop_reason="error")
    assert nodes.route_after_account_context(state) == "log_outcome"


# ===========================================================================
# route_after_discovery
# ===========================================================================

def test_route_with_candidates_to_rank():
    nodes = _make_nodes()
    candidates = [EngagementTarget(target_id="u1", target_type="account", metadata={})]
    state = _state(candidate_targets=candidates)
    assert nodes.route_after_discovery(state) == "rank_candidates"


def test_route_empty_candidates_to_log_outcome():
    nodes = _make_nodes()
    state = _state(candidate_targets=[])
    assert nodes.route_after_discovery(state) == "log_outcome"


def test_route_discovery_with_stop_reason_to_log_outcome():
    nodes = _make_nodes()
    candidates = [EngagementTarget(target_id="u1", target_type="account", metadata={})]
    state = _state(candidate_targets=candidates, stop_reason="no_candidates")
    assert nodes.route_after_discovery(state) == "log_outcome"


# ===========================================================================
# route_after_risk
# ===========================================================================

def test_route_low_risk_to_gate_by_mode():
    nodes = _make_nodes()
    risk = RiskAssessment(risk_level="low", rule_hits=[], reasoning="ok", requires_approval=False)
    state = _state(risk_assessment=risk)
    assert nodes.route_after_risk(state) == "gate_by_mode"


def test_route_medium_risk_to_gate_by_mode():
    nodes = _make_nodes()
    risk = RiskAssessment(risk_level="medium", rule_hits=["write_action"], reasoning="write", requires_approval=True)
    state = _state(risk_assessment=risk)
    assert nodes.route_after_risk(state) == "gate_by_mode"


def test_route_high_risk_to_log_outcome():
    nodes = _make_nodes()
    risk = RiskAssessment(risk_level="high", rule_hits=["cooldown"], reasoning="cooldown", requires_approval=True)
    state = _state(risk_assessment=risk)
    assert nodes.route_after_risk(state) == "log_outcome"


def test_route_no_risk_assessment_to_log_outcome():
    nodes = _make_nodes()
    state = _state(risk_assessment=None)
    assert nodes.route_after_risk(state) == "log_outcome"


def test_route_risk_with_stop_reason_to_log_outcome():
    nodes = _make_nodes()
    risk = RiskAssessment(risk_level="low", rule_hits=[], reasoning="ok", requires_approval=False)
    state = _state(risk_assessment=risk, stop_reason="risk_threshold_exceeded")
    assert nodes.route_after_risk(state) == "log_outcome"


# ===========================================================================
# route_by_mode
# ===========================================================================

def test_route_recommendation_mode_to_log_outcome():
    nodes = _make_nodes()
    state = _state(mode="recommendation")
    assert nodes.route_by_mode(state) == "log_outcome"


def test_route_execute_mode_to_request_approval():
    nodes = _make_nodes()
    state = _state(mode="execute")
    assert nodes.route_by_mode(state) == "request_approval"


def test_route_default_mode_is_recommendation():
    nodes = _make_nodes()
    # No mode key: defaults to "recommendation"
    state = _state()
    state.pop("mode")
    assert nodes.route_by_mode(state) == "log_outcome"


# ===========================================================================
# route_after_approval
# ===========================================================================

def test_route_approved_to_execute():
    nodes = _make_nodes()
    approval_result = {"approval_id": "x", "decision": "approved", "approver_notes": "", "edited_content": None, "decided_at": time.time()}
    state = _state(approval_result=approval_result)
    assert nodes.route_after_approval(state) == "execute_action"


def test_route_rejected_to_log_outcome():
    nodes = _make_nodes()
    approval_result = {"approval_id": "x", "decision": "rejected", "approver_notes": "no", "edited_content": None, "decided_at": time.time()}
    state = _state(approval_result=approval_result, stop_reason="approval_rejected")
    assert nodes.route_after_approval(state) == "log_outcome"


def test_route_no_approval_result_to_log_outcome():
    nodes = _make_nodes()
    state = _state(approval_result=None)
    assert nodes.route_after_approval(state) == "log_outcome"


def test_route_stop_reason_always_to_log_outcome():
    nodes = _make_nodes()
    # Even if decision is approved, stop_reason preempts
    approval_result = {"approval_id": "x", "decision": "approved", "approver_notes": "", "edited_content": None, "decided_at": time.time()}
    state = _state(approval_result=approval_result, stop_reason="error")
    assert nodes.route_after_approval(state) == "log_outcome"


# ===========================================================================
# Node-level routing integration: load_account_context_node fail-fast
# ===========================================================================

@pytest.mark.asyncio
async def test_unhealthy_account_node_sets_stop_reason():
    from ai_copilot.application.smart_engagement.nodes import SmartEngagementNodes

    nodes = SmartEngagementNodes(
        account_context=_FakeAccountContext({
            "status": "suspended", "login_state": "needs_2fa",
            "cooldown_until": None, "proxy": None, "recent_actions": 0
        }),
        candidate_discovery=_FakeCandidates([]),
        risk_scoring=_FakeRisk("low"),
        approval=_FakeApproval(),
        executor=_FakeExecutor(),
        audit_log=_InMemoryAuditLog(),
    )

    state = _state()
    result = await nodes.load_account_context_node(state)

    assert result["stop_reason"] == "account_not_ready"
    assert result["outcome_reason"]
    # Refresh path emits: session_refresh_attempted + session_refresh_result + action_skipped
    event_types = [e["event_type"] for e in result["audit_trail"]]
    assert "action_skipped" in event_types
    assert "session_refresh_attempted" in event_types


@pytest.mark.asyncio
async def test_healthy_account_node_no_stop_reason():
    nodes = _make_nodes(account_context=_FakeAccountContext(
        {"status": "active", "login_state": "logged_in", "cooldown_until": None, "proxy": None, "recent_actions": 0}
    ))
    state = _state()
    result = await nodes.load_account_context_node(state)

    assert result.get("stop_reason") is None
    assert result["account_health"]["status"] == "active"
    assert len(result["audit_trail"]) == 1
    assert result["audit_trail"][0]["event_type"] == "account_loaded"


# ===========================================================================
# discover_candidates_node fail-fast
# ===========================================================================

@pytest.mark.asyncio
async def test_discover_no_candidates_sets_stop_reason():
    nodes = _make_nodes(candidates=_FakeCandidates([]))
    state = _state()
    result = await nodes.discover_candidates_node(state)

    assert result["stop_reason"] == "no_candidates"
    assert result["discovery_attempted"] is True
    assert result["audit_trail"][0]["event_type"] == "action_skipped"


@pytest.mark.asyncio
async def test_discover_candidates_sets_flag():
    candidates = [EngagementTarget(target_id="u1", target_type="account", metadata={})]
    nodes = _make_nodes(candidates=_FakeCandidates(candidates))
    state = _state()
    result = await nodes.discover_candidates_node(state)

    assert result["discovery_attempted"] is True
    assert len(result["candidate_targets"]) == 1
    assert result["audit_trail"][0]["event_type"] == "candidates_discovered"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
