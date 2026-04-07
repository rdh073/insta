"""Integration tests for smart engagement workflow.

Tests verify invariants:
- Default mode is 'recommendation' (no auto-execute)
- Write actions require approval
- Every decision is auditable
- Loop bounded
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ai_copilot.application.smart_engagement.state import (
    SmartEngagementState,
    EngagementTarget,
    ProposedAction,
    RiskAssessment,
    DraftPayload,
    ExecutionResult,
)
from ai_copilot.application.smart_engagement.nodes import SmartEngagementNodes
from ai_copilot.application.smart_engagement.ports import (
    AccountContextPort,
    ApprovalPort,
    AuditLogPort,
    EngagementCandidatePort,
    EngagementExecutorPort,
    RiskScoringPort,
)
from ai_copilot.application.use_cases.run_smart_engagement import SmartEngagementUseCase
from ai_copilot.adapters.approval_adapter import InMemoryApprovalAdapter


def _make_ports(
    *,
    account_context=None,
    candidate_discovery=None,
    risk_scoring=None,
    approval=None,
    executor=None,
    audit_log=None,
):
    """Build mock ports dict, filling in defaults for any not provided."""
    if account_context is None:
        account_context = AsyncMock(spec=AccountContextPort)
        account_context.get_account_context = AsyncMock(return_value={
            "status": "active",
            "cooldown_until": None,
            "proxy": None,
            "login_state": "logged_in",
            "recent_actions": 0,
        })
        account_context.validate_account_ready = AsyncMock(return_value=True)

    if candidate_discovery is None:
        candidate_discovery = AsyncMock(spec=EngagementCandidatePort)
        candidate_discovery.discover_candidates = AsyncMock(return_value=[
            EngagementTarget(
                target_id="test_user",
                target_type="account",
                metadata={"follower_count": 1000, "engagement_rate": 0.05},
            ),
        ])
        candidate_discovery.get_target_metadata = AsyncMock(
            return_value={"follower_count": 1000, "has_posts": True},
        )

    if risk_scoring is None:
        risk_scoring = AsyncMock(spec=RiskScoringPort)
        risk_scoring.assess_risk = AsyncMock(return_value=RiskAssessment(
            risk_level="low",
            rule_hits=[],
            reasoning="low risk account",
            requires_approval=True,
        ))

    if approval is None:
        approval = InMemoryApprovalAdapter()

    if executor is None:
        executor = AsyncMock(spec=EngagementExecutorPort)
        executor.execute_follow = AsyncMock(
            return_value={"success": True, "result": {"followed": True}},
        )
        executor.execute_dm = AsyncMock(
            return_value={"success": True, "dm_id": "123"},
        )
        executor.execute_comment = AsyncMock(
            return_value={"success": True, "comment_id": "456"},
        )
        executor.execute_like = AsyncMock(return_value={"success": True})
        executor.is_write_action = MagicMock(
            side_effect=lambda x: x in ("follow", "dm", "comment", "like"),
        )

    if audit_log is None:
        audit_log = AsyncMock(spec=AuditLogPort)
        audit_log.log_event = AsyncMock()
        audit_log.get_audit_trail = AsyncMock(return_value=[])

    return {
        "account_context": account_context,
        "candidate_discovery": candidate_discovery,
        "risk_scoring": risk_scoring,
        "approval": approval,
        "executor": executor,
        "audit_log": audit_log,
    }


def _make_nodes(**overrides):
    """Build SmartEngagementNodes from mock ports."""
    ports = _make_ports(**overrides)
    return SmartEngagementNodes(**ports), ports


def _base_state(**overrides) -> SmartEngagementState:
    """Return a minimal valid SmartEngagementState dict with sane defaults."""
    state: SmartEngagementState = {
        "messages": [],
        "current_tool_calls": None,
        "tool_results": {},
        "stop_reason": None,
        "step_count": 0,
        "thread_id": "test-thread",
        "mode": "recommendation",
        "goal": "engage with relevant accounts",
        "structured_goal": None,
        "account_id": "acct_1",
        "account_health": None,
        "candidate_targets": [],
        "selected_target": None,
        "proposed_action": None,
        "draft_payload": None,
        "risk_assessment": None,
        "approval_request": None,
        "approval_result": None,
        "execution_result": None,
        "audit_trail": [],
        "discovery_attempted": False,
        "approval_attempted": False,
        "outcome_reason": None,
        "approval_timeout": 3600.0,
        "max_targets": 5,
        "max_actions_per_target": 3,
    }
    state.update(overrides)
    return state


# ── Invariant: recommendation mode never executes ─────────────────────


@pytest.mark.asyncio
async def test_recommendation_mode_no_execution():
    """Recommendation mode never triggers the executor.

    Invariant: Default mode is 'recommendation' (no auto-execute).
    """
    nodes, ports = _make_nodes()

    # gate_by_mode in recommendation mode sets stop_reason
    state = _base_state(mode="recommendation", proposed_action=ProposedAction(
        action_type="follow",
        target_id="test_user",
        content=None,
        reasoning="test",
        expected_outcome="follow successful",
    ))

    result = await nodes.gate_by_mode_node(state)

    assert result.get("stop_reason") == "recommendation_only"
    # Executor should NOT have been called
    ports["executor"].execute_follow.assert_not_called()
    ports["executor"].execute_dm.assert_not_called()


# ── Invariant: execute mode requires approval ─────────────────────────


@pytest.mark.asyncio
async def test_execute_mode_blocks_without_approval():
    """Execute action node refuses if approval_result is missing or not approved."""
    nodes, ports = _make_nodes()

    state = _base_state(
        mode="execute",
        proposed_action=ProposedAction(
            action_type="follow",
            target_id="test_user",
            content=None,
            reasoning="test",
            expected_outcome="follow successful",
        ),
        approval_result=None,
    )

    result = await nodes.execute_action_node(state)

    assert result["execution_result"]["success"] is False
    assert result["execution_result"]["reason_code"] == "not_approved"
    ports["executor"].execute_follow.assert_not_called()


@pytest.mark.asyncio
async def test_execute_mode_blocks_when_rejected():
    """Execute action node refuses if approval was rejected."""
    nodes, ports = _make_nodes()

    state = _base_state(
        mode="execute",
        proposed_action=ProposedAction(
            action_type="follow",
            target_id="test_user",
            content=None,
            reasoning="test",
            expected_outcome="follow successful",
        ),
        approval_result={
            "approval_id": "apr_123",
            "decision": "rejected",
            "approver_notes": "Not now",
            "edited_content": None,
            "decided_at": 0.0,
        },
    )

    result = await nodes.execute_action_node(state)

    assert result["execution_result"]["success"] is False
    assert result["execution_result"]["reason_code"] == "not_approved"
    ports["executor"].execute_follow.assert_not_called()


# ── Invariant: approval adapter submit/status/decision cycle ──────────


@pytest.mark.asyncio
async def test_approval_gate_blocks_execution_until_approved():
    """Approval adapter tracks pending -> approved lifecycle."""
    approval = InMemoryApprovalAdapter()

    approval_id = await approval.submit_for_approval(
        action=ProposedAction(
            action_type="follow",
            target_id="test_user",
            content=None,
            reasoning="test",
            expected_outcome="test",
        ),
        risk_assessment=RiskAssessment(
            risk_level="high",
            rule_hits=["follow_daily_limit"],
            reasoning="test",
            requires_approval=True,
        ),
        audit_trail=[],
    )

    record = await approval.get_approval_status(approval_id)
    assert record["status"] == "pending"
    assert record["approval_id"] == approval_id

    approved_record = await approval.record_approval_decision(
        approval_id=approval_id,
        approved=True,
        approver_notes="Looks good",
    )

    assert approved_record["status"] == "approved"
    assert approved_record["approver_notes"] == "Looks good"


# ── Invariant: every decision is auditable ────────────────────────────


@pytest.mark.asyncio
async def test_audit_trail_generation():
    """Nodes emit audit events into the trail.

    Invariant: Every decision is auditable with reasoning and timestamps.
    """
    nodes, ports = _make_nodes()

    # Run ingest_goal — should produce an audit event
    state = _base_state(goal="comment on educational posts")
    result = await nodes.ingest_goal_node(state)

    assert "audit_trail" in result
    assert isinstance(result["audit_trail"], list)
    assert len(result["audit_trail"]) >= 1
    event = result["audit_trail"][0]
    assert event["event_type"] == "goal_ingested"
    assert event["node_name"] == "ingest_goal"
    assert "timestamp" in event


# ── Invariant: high risk stops workflow ───────────────────────────────


@pytest.mark.asyncio
async def test_high_risk_action_stops_workflow():
    """High-risk score from the risk port stops the workflow."""
    risk_scoring = AsyncMock(spec=RiskScoringPort)
    risk_scoring.assess_risk = AsyncMock(return_value=RiskAssessment(
        risk_level="high",
        rule_hits=["spam_content"],
        reasoning="spam content detected",
        requires_approval=True,
    ))

    nodes, _ports = _make_nodes(risk_scoring=risk_scoring)

    state = _base_state(
        proposed_action=ProposedAction(
            action_type="dm",
            target_id="test_user",
            content="Buy now!",
            reasoning="spam",
            expected_outcome="sales",
        ),
        selected_target=EngagementTarget(
            target_id="test_user",
            target_type="account",
            metadata={},
        ),
        account_health={
            "status": "active",
            "cooldown_until": None,
            "proxy": None,
            "login_state": "logged_in",
            "recent_actions": 0,
        },
    )

    result = await nodes.score_risk_node(state)

    assert result["risk_assessment"]["risk_level"] == "high"
    assert result["stop_reason"] == "risk_threshold_exceeded"


# ── Invariant: loop bounded ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_discovery_attempted_blocks_second_run():
    """Discovery only runs once per workflow execution.

    Invariant: max 1 discovery cycle per run.
    """
    nodes, _ports = _make_nodes()

    state = _base_state(discovery_attempted=True)

    result = await nodes.discover_candidates_node(state)

    assert result["stop_reason"] == "discovery_limit_reached"


@pytest.mark.asyncio
async def test_approval_attempted_blocks_second_run():
    """Approval only runs once per workflow execution.

    Invariant: max 1 approval per run (rejection is final).
    """
    nodes, _ports = _make_nodes()

    state = _base_state(
        mode="execute",
        approval_attempted=True,
        proposed_action=ProposedAction(
            action_type="follow",
            target_id="test_user",
            content=None,
            reasoning="test",
            expected_outcome="follow successful",
        ),
        risk_assessment=RiskAssessment(
            risk_level="low",
            rule_hits=[],
            reasoning="ok",
            requires_approval=True,
        ),
    )

    result = await nodes.request_approval_node(state)

    assert result["stop_reason"] == "approval_limit_reached"


# ── Error handling ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_error_handling_in_discovery():
    """Discovery adapter errors are caught gracefully."""
    candidate_discovery = AsyncMock(spec=EngagementCandidatePort)
    candidate_discovery.discover_candidates = AsyncMock(
        side_effect=Exception("Instagram API error"),
    )

    nodes, _ports = _make_nodes(candidate_discovery=candidate_discovery)

    state = _base_state()

    result = await nodes.discover_candidates_node(state)

    assert result["stop_reason"] == "error"
    assert "audit_trail" in result
    assert len(result["audit_trail"]) >= 1


# ── Low-risk read action can proceed without approval ─────────────────


@pytest.mark.asyncio
async def test_low_risk_read_action_route():
    """Low-risk actions route through gate_by_mode correctly."""
    nodes, _ports = _make_nodes()

    state = _base_state(
        mode="execute",
        risk_assessment=RiskAssessment(
            risk_level="low",
            rule_hits=[],
            reasoning="just viewing",
            requires_approval=False,
        ),
    )

    # route_after_risk should allow continuing to gate_by_mode
    route = nodes.route_after_risk(state)
    assert route == "gate_by_mode"


# ── Recommendation response format ───────────────────────────────────


@pytest.mark.asyncio
async def test_gate_by_mode_recommendation_sets_outcome():
    """Recommendation mode sets a descriptive outcome_reason."""
    nodes, _ports = _make_nodes()

    state = _base_state(
        mode="recommendation",
        proposed_action=ProposedAction(
            action_type="follow",
            target_id="test_user",
            content=None,
            reasoning="test",
            expected_outcome="follow successful",
        ),
    )

    result = await nodes.gate_by_mode_node(state)

    assert result["stop_reason"] == "recommendation_only"
    assert "test_user" in result["outcome_reason"]
    assert "follow" in result["outcome_reason"]
