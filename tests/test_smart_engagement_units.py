"""Unit tests for smart engagement - ranking, scoring, goal parsing, mode gating.

Tests cover:
- _parse_goal: keyword extraction, action_type, target_type
- _score_candidate: scoring function (engagement_rate, follower_count, recent_posts)
- rank_candidates_node: selects highest-scoring candidate
- score_risk_node: rule-based risk with fake RiskScoringPort
- gate_by_mode_node / route_by_mode: recommendation vs execute routing

Uses fake port implementations (no external services).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest

# ---------------------------------------------------------------------------
# Fake port helpers
# ---------------------------------------------------------------------------

from ai_copilot.application.smart_engagement.ports import (
    AccountContextPort,
    AuditLogPort,
    ApprovalPort,
    EngagementCandidatePort,
    EngagementExecutorPort,
    RiskScoringPort,
)
from ai_copilot.application.smart_engagement.state import (
    AccountHealth,
    AuditEvent,
    EngagementTarget,
    ExecutionResult,
    ProposedAction,
    RiskAssessment,
)


class _InMemoryAuditLog(AuditLogPort):
    def __init__(self):
        self.events: list[AuditEvent] = []

    async def log_event(self, event: AuditEvent) -> None:
        self.events.append(event)

    async def get_audit_trail(self, thread_id: str) -> list[AuditEvent]:
        return [e for e in self.events if e.get("event_data", {}).get("thread_id") == thread_id]


class _FakeAccountContext(AccountContextPort):
    def __init__(self, health: dict):
        self._health = health

    async def get_account_context(self, account_id: str) -> AccountHealth:
        return AccountHealth(**self._health)

    async def validate_account_ready(self, account_id: str) -> bool:
        return self._health.get("status") == "active"


class _FakeCandidates(EngagementCandidatePort):
    def __init__(self, candidates):
        self._candidates = candidates

    async def discover_candidates(self, account_id, goal, filters=None):
        return self._candidates

    async def get_target_metadata(self, target_id):
        return {}


class _FakeRisk(RiskScoringPort):
    def __init__(self, level="low", rule_hits=None, reasoning="ok"):
        self._level = level
        self._rule_hits = rule_hits or []
        self._reasoning = reasoning

    async def assess_risk(self, action, target, account_health) -> RiskAssessment:
        return RiskAssessment(
            risk_level=self._level,
            rule_hits=self._rule_hits,
            reasoning=self._reasoning,
            requires_approval=self._level in ("medium", "high"),
        )


class _FakeApproval(ApprovalPort):
    async def submit_for_approval(self, approval_request) -> str:
        return "fake_approval_id"

    async def get_approval_status(self, approval_id):
        return {"approval_id": approval_id, "decision": "pending"}


class _NoOpExecutor(EngagementExecutorPort):
    async def execute_follow(self, target_id, account_id) -> ExecutionResult:
        return ExecutionResult(success=False, action_id=None, reason="NoOp", timestamp=time.time())

    async def execute_dm(self, target_id, account_id, message) -> ExecutionResult:
        return ExecutionResult(success=False, action_id=None, reason="NoOp", timestamp=time.time())

    async def execute_comment(self, post_id, account_id, comment_text) -> ExecutionResult:
        return ExecutionResult(success=False, action_id=None, reason="NoOp", timestamp=time.time())

    async def execute_like(self, post_id, account_id) -> ExecutionResult:
        return ExecutionResult(success=False, action_id=None, reason="NoOp", timestamp=time.time())

    def is_write_action(self, action_type: str) -> bool:
        return True


def _make_nodes(
    account_health=None,
    candidates=None,
    risk_level="low",
    risk_hits=None,
    audit_log=None,
):
    from ai_copilot.application.smart_engagement.nodes import SmartEngagementNodes

    return SmartEngagementNodes(
        account_context=_FakeAccountContext(
            account_health or {"status": "active", "login_state": "logged_in", "cooldown_until": None, "proxy": None, "recent_actions": 0}
        ),
        candidate_discovery=_FakeCandidates(candidates or []),
        risk_scoring=_FakeRisk(risk_level, risk_hits),
        approval=_FakeApproval(),
        executor=_NoOpExecutor(),
        audit_log=audit_log or _InMemoryAuditLog(),
    )


def _base_state(**overrides):
    """Return a minimal SmartEngagementState dict."""
    state = {
        "messages": [],
        "current_tool_calls": None,
        "tool_results": {},
        "stop_reason": None,
        "step_count": 0,
        "thread_id": "test-thread",
        "mode": "recommendation",
        "goal": "follow accounts in tech space",
        "structured_goal": None,
        "account_id": "acc_1",
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


# ===========================================================================
# _parse_goal unit tests
# ===========================================================================

def test_parse_goal_comment():
    from ai_copilot.application.smart_engagement.nodes import _parse_goal

    result = _parse_goal("comment on educational posts")
    assert result["action_type"] == "comment"
    assert result["target_type"] == "post"
    assert result["constraints"].get("content_filter") == "educational"


def test_parse_goal_follow():
    from ai_copilot.application.smart_engagement.nodes import _parse_goal

    result = _parse_goal("follow accounts in tech space")
    assert result["action_type"] == "follow"
    assert result["target_type"] == "account"
    assert result["constraints"].get("niche") == "technology"


def test_parse_goal_dm():
    from ai_copilot.application.smart_engagement.nodes import _parse_goal

    result = _parse_goal("send direct message to influencers")
    assert result["action_type"] == "dm"
    assert result["target_type"] == "account"


def test_parse_goal_like():
    from ai_copilot.application.smart_engagement.nodes import _parse_goal

    result = _parse_goal("like recent posts in fitness niche")
    assert result["action_type"] == "like"
    assert result["target_type"] == "post"
    assert result["constraints"].get("niche") == "health/fitness"


def test_parse_goal_default_fallback():
    from ai_copilot.application.smart_engagement.nodes import _parse_goal

    result = _parse_goal("grow my audience")
    # Default: follow account
    assert result["action_type"] == "follow"
    assert result["target_type"] == "account"
    assert result["intent"] == "grow my audience"


# ===========================================================================
# _score_candidate unit tests
# ===========================================================================

def test_score_candidate_engagement_rate_primary():
    from ai_copilot.application.smart_engagement.nodes import _score_candidate

    high_engagement = EngagementTarget(
        target_id="a", target_type="account",
        metadata={"engagement_rate": 0.1, "follower_count": 100, "recent_posts": 0}
    )
    low_engagement = EngagementTarget(
        target_id="b", target_type="account",
        metadata={"engagement_rate": 0.01, "follower_count": 100, "recent_posts": 0}
    )
    goal = {"action_type": "follow"}
    assert _score_candidate(high_engagement, goal) > _score_candidate(low_engagement, goal)


def test_score_candidate_follower_count_secondary():
    from ai_copilot.application.smart_engagement.nodes import _score_candidate

    big_account = EngagementTarget(
        target_id="a", target_type="account",
        metadata={"engagement_rate": 0.0, "follower_count": 100000, "recent_posts": 0}
    )
    small_account = EngagementTarget(
        target_id="b", target_type="account",
        metadata={"engagement_rate": 0.0, "follower_count": 10, "recent_posts": 0}
    )
    goal = {}
    assert _score_candidate(big_account, goal) > _score_candidate(small_account, goal)


def test_score_candidate_recent_posts_bonus():
    from ai_copilot.application.smart_engagement.nodes import _score_candidate

    active = EngagementTarget(
        target_id="a", target_type="account",
        metadata={"engagement_rate": 0.0, "follower_count": 0, "recent_posts": 10}
    )
    inactive = EngagementTarget(
        target_id="b", target_type="account",
        metadata={"engagement_rate": 0.0, "follower_count": 0, "recent_posts": 0}
    )
    assert _score_candidate(active, {}) > _score_candidate(inactive, {})


def test_score_candidate_empty_metadata():
    from ai_copilot.application.smart_engagement.nodes import _score_candidate

    target = EngagementTarget(target_id="x", target_type="account", metadata={})
    score = _score_candidate(target, {})
    assert score == 0.0


# ===========================================================================
# rank_candidates_node unit tests
# ===========================================================================

@pytest.mark.asyncio
async def test_rank_candidates_selects_best():
    nodes = _make_nodes()

    candidates = [
        EngagementTarget(target_id="low", target_type="account", metadata={"engagement_rate": 0.01}),
        EngagementTarget(target_id="high", target_type="account", metadata={"engagement_rate": 0.2}),
        EngagementTarget(target_id="mid", target_type="account", metadata={"engagement_rate": 0.05}),
    ]
    state = _base_state(candidate_targets=candidates, structured_goal={"action_type": "follow"})
    result = await nodes.rank_candidates_node(state)

    assert result["selected_target"]["target_id"] == "high"
    assert len(result["audit_trail"]) == 1
    assert result["audit_trail"][0]["event_type"] == "target_selected"


@pytest.mark.asyncio
async def test_rank_candidates_empty_returns_none():
    nodes = _make_nodes()

    state = _base_state(candidate_targets=[])
    result = await nodes.rank_candidates_node(state)

    assert result["selected_target"] is None


# ===========================================================================
# score_risk_node unit tests
# ===========================================================================

@pytest.mark.asyncio
async def test_score_risk_low_risk_continues():
    nodes = _make_nodes(risk_level="low")

    state = _base_state(
        proposed_action=ProposedAction(action_type="follow", target_id="t1", content=None, reasoning="r", expected_outcome="e"),
        selected_target=EngagementTarget(target_id="t1", target_type="account", metadata={}),
        account_health=AccountHealth(status="active", login_state="logged_in", cooldown_until=None, proxy=None, recent_actions=0),
    )
    result = await nodes.score_risk_node(state)

    # Low risk: no stop_reason set (won't stop workflow)
    assert result.get("stop_reason") is None
    assert result["risk_assessment"]["risk_level"] == "low"
    assert len(result["audit_trail"]) == 1
    assert result["audit_trail"][0]["event_type"] == "scored"


@pytest.mark.asyncio
async def test_score_risk_high_risk_stops_workflow():
    nodes = _make_nodes(risk_level="high", risk_hits=["account_in_cooldown"])

    state = _base_state(
        proposed_action=ProposedAction(action_type="follow", target_id="t1", content=None, reasoning="r", expected_outcome="e"),
        selected_target=EngagementTarget(target_id="t1", target_type="account", metadata={}),
        account_health=AccountHealth(status="active", login_state="logged_in", cooldown_until=None, proxy=None, recent_actions=0),
    )
    result = await nodes.score_risk_node(state)

    assert result["stop_reason"] == "risk_threshold_exceeded"
    assert result["risk_assessment"]["risk_level"] == "high"
    assert "Risk too high" in result["outcome_reason"]


@pytest.mark.asyncio
async def test_score_risk_missing_action_stops():
    nodes = _make_nodes()

    # Missing proposed_action
    state = _base_state()
    result = await nodes.score_risk_node(state)

    assert result["stop_reason"] == "missing_data"


# ===========================================================================
# gate_by_mode_node / route_by_mode unit tests
# ===========================================================================

@pytest.mark.asyncio
async def test_gate_by_mode_recommendation_sets_stop_reason():
    nodes = _make_nodes()

    state = _base_state(
        mode="recommendation",
        proposed_action=ProposedAction(action_type="follow", target_id="user_1", content=None, reasoning="r", expected_outcome="e"),
    )
    result = await nodes.gate_by_mode_node(state)

    # Recommendation mode: sets stop_reason so route_by_mode routes to log_outcome
    assert result["stop_reason"] == "recommendation_only"
    assert "recommendation mode" in result["outcome_reason"].lower()


@pytest.mark.asyncio
async def test_gate_by_mode_execute_no_changes():
    nodes = _make_nodes()

    state = _base_state(mode="execute")
    result = await nodes.gate_by_mode_node(state)

    # Execute mode: no state changes, routing proceeds to request_approval
    assert result == {}


def test_route_by_mode_recommendation_routes_to_log_outcome():
    nodes = _make_nodes()

    state = _base_state(mode="recommendation", stop_reason="recommendation_only")
    assert nodes.route_by_mode(state) == "log_outcome"


def test_route_by_mode_execute_routes_to_request_approval():
    nodes = _make_nodes()

    state = _base_state(mode="execute")
    assert nodes.route_by_mode(state) == "request_approval"


# ===========================================================================
# Real RiskScoringAdapter unit tests
# ===========================================================================

@pytest.mark.asyncio
async def test_risk_adapter_cooldown_is_high_risk():
    from ai_copilot.adapters.risk_scoring_adapter import RiskScoringAdapter

    adapter = RiskScoringAdapter()
    action = ProposedAction(action_type="follow", target_id="t", content=None, reasoning="r", expected_outcome="e")
    target = EngagementTarget(target_id="t", target_type="account", metadata={})
    health = AccountHealth(status="active", login_state="logged_in", cooldown_until=999999.0, proxy=None, recent_actions=0)

    result = await adapter.assess_risk(action, target, health)
    assert result["risk_level"] == "high"
    assert "account_in_cooldown" in result["rule_hits"]
    assert result["reasoning"]  # Must have reasoning per port contract


@pytest.mark.asyncio
async def test_risk_adapter_healthy_account_write_is_medium():
    from ai_copilot.adapters.risk_scoring_adapter import RiskScoringAdapter

    adapter = RiskScoringAdapter()
    action = ProposedAction(action_type="follow", target_id="t", content=None, reasoning="r", expected_outcome="e")
    target = EngagementTarget(target_id="t", target_type="account", metadata={})
    health = AccountHealth(status="active", login_state="logged_in", cooldown_until=None, proxy=None, recent_actions=0)

    result = await adapter.assess_risk(action, target, health)
    # follow is a write action → medium (write_action_requires_approval rule)
    assert result["risk_level"] == "medium"
    assert "write_action_requires_approval" in result["rule_hits"]
    assert result["requires_approval"] is True


@pytest.mark.asyncio
async def test_risk_adapter_returns_reasoning_always():
    from ai_copilot.adapters.risk_scoring_adapter import RiskScoringAdapter

    adapter = RiskScoringAdapter()
    action = ProposedAction(action_type="follow", target_id="t", content=None, reasoning="r", expected_outcome="e")
    target = EngagementTarget(target_id="t", target_type="account", metadata={})
    health = AccountHealth(status="active", login_state="logged_in", cooldown_until=None, proxy=None, recent_actions=0)

    result = await adapter.assess_risk(action, target, health)
    # Port contract: reasoning MUST be present
    assert isinstance(result["reasoning"], str)
    assert len(result["reasoning"]) > 0


# ===========================================================================
# NoOpExecutor unit tests
# ===========================================================================

@pytest.mark.asyncio
async def test_noop_executor_blocks_all_writes():
    from ai_copilot.adapters.noop_executor_adapter import NoOpExecutorAdapter

    noop = NoOpExecutorAdapter()

    assert (await noop.execute_follow("t", "acc"))["success"] is False
    assert (await noop.execute_dm("t", "acc", "msg"))["success"] is False
    assert (await noop.execute_comment("p", "acc", "text"))["success"] is False
    assert (await noop.execute_like("p", "acc"))["success"] is False


def test_noop_executor_all_write_actions():
    from ai_copilot.adapters.noop_executor_adapter import NoOpExecutorAdapter

    noop = NoOpExecutorAdapter()
    for action_type in ("follow", "dm", "comment", "like", "arbitrary"):
        assert noop.is_write_action(action_type) is True


@pytest.mark.asyncio
async def test_noop_executor_reason_is_descriptive():
    from ai_copilot.adapters.noop_executor_adapter import NoOpExecutorAdapter

    noop = NoOpExecutorAdapter()
    result = await noop.execute_follow("target", "account")
    assert "recommendation" in result["reason"].lower() or "blocked" in result["reason"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
