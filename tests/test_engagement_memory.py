"""Tests for engagement memory — port contract, adapter behavior, node integration."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest

from ai_copilot.adapters.engagement_memory_adapter import InMemoryEngagementMemoryAdapter
from ai_copilot.application.smart_engagement.state import (
    AuditEvent,
    EngagementTarget,
    ExecutionResult,
    ProposedAction,
    RiskAssessment,
)
from ai_copilot.application.smart_engagement.ports import (
    AccountContextPort,
    ApprovalPort,
    AuditLogPort,
    EngagementCandidatePort,
    EngagementExecutorPort,
    EngagementMemoryPort,
    RiskScoringPort,
)
from ai_copilot.application.smart_engagement.nodes import SmartEngagementNodes


# ---------------------------------------------------------------------------
# Fake ports (same pattern as other test files)
# ---------------------------------------------------------------------------

class _FakeAuditLog(AuditLogPort):
    def __init__(self):
        self.events = []

    async def log_event(self, event):
        self.events.append(event)

    async def get_audit_trail(self, thread_id):
        return self.events


class _FakeAccountContext(AccountContextPort):
    async def get_account_context(self, account_id):
        return {"status": "active", "cooldown_until": None, "proxy": None, "login_state": "logged_in", "recent_actions": 0}

    async def validate_account_ready(self, account_id):
        return True


class _FakeCandidateDiscovery(EngagementCandidatePort):
    def __init__(self, candidates=None):
        self.candidates = candidates or []

    async def discover_candidates(self, account_id, goal, filters=None):
        return list(self.candidates)

    async def get_target_metadata(self, target_id):
        return {"target_id": target_id}


class _FakeRiskScoring(RiskScoringPort):
    async def assess_risk(self, action, target, account_health):
        return RiskAssessment(risk_level="low", rule_hits=[], reasoning="low risk", requires_approval=False)


class _FakeApproval(ApprovalPort):
    async def submit_for_approval(self, *a, **kw):
        return "apr_fake"

    async def get_approval_status(self, approval_id):
        return {"approval_id": approval_id, "status": "pending", "requested_at": 0, "approved_at": None}


class _FakeExecutor(EngagementExecutorPort):
    async def execute_follow(self, target_id, account_id):
        return ExecutionResult(success=True, action_id="f_1", reason="ok", reason_code="ok", timestamp=time.time())

    async def execute_dm(self, target_id, account_id, message):
        return ExecutionResult(success=True, action_id="d_1", reason="ok", reason_code="ok", timestamp=time.time())

    async def execute_comment(self, post_id, account_id, comment_text):
        return ExecutionResult(success=True, action_id="c_1", reason="ok", reason_code="ok", timestamp=time.time())

    async def execute_like(self, post_id, account_id):
        return ExecutionResult(success=True, action_id="l_1", reason="ok", reason_code="ok", timestamp=time.time())

    def is_write_action(self, action_type):
        return action_type in ("follow", "dm", "comment", "like")


def _make_nodes(*, memory=None, candidates=None):
    return SmartEngagementNodes(
        account_context=_FakeAccountContext(),
        candidate_discovery=_FakeCandidateDiscovery(candidates),
        risk_scoring=_FakeRiskScoring(),
        approval=_FakeApproval(),
        executor=_FakeExecutor(),
        audit_log=_FakeAuditLog(),
        engagement_memory=memory,
    )


def _base_state(**overrides):
    state = {
        "messages": [], "current_tool_calls": None, "tool_results": {},
        "stop_reason": None, "step_count": 0, "thread_id": "test-thread",
        "mode": "recommendation", "goal": "engage with relevant accounts",
        "structured_goal": None, "account_id": "acct_1",
        "account_health": None, "candidate_targets": [],
        "selected_target": None, "proposed_action": None,
        "draft_payload": None, "risk_assessment": None,
        "approval_request": None, "approval_result": None,
        "execution_result": None, "audit_trail": [],
        "discovery_attempted": False, "approval_attempted": False,
        "outcome_reason": None, "approval_timeout": 3600.0,
        "max_targets": 5, "max_actions_per_target": 3,
    }
    state.update(overrides)
    return state


# ===========================================================================
# InMemoryEngagementMemoryAdapter — port contract
# ===========================================================================

class TestInMemoryAdapter:
    @pytest.mark.asyncio
    async def test_store_and_recall(self):
        mem = InMemoryEngagementMemoryAdapter()
        await mem.store_engagement_outcome("acct_1", "user_a", "follow", "success")
        await mem.store_engagement_outcome("acct_1", "user_b", "dm", "failed")

        records = await mem.recall_recent_engagements("acct_1")
        assert len(records) == 2
        ids = {r["target_id"] for r in records}
        assert ids == {"user_a", "user_b"}

    @pytest.mark.asyncio
    async def test_recall_empty(self):
        mem = InMemoryEngagementMemoryAdapter()
        records = await mem.recall_recent_engagements("acct_1")
        assert records == []

    @pytest.mark.asyncio
    async def test_account_isolation(self):
        mem = InMemoryEngagementMemoryAdapter()
        await mem.store_engagement_outcome("acct_1", "user_a", "follow", "success")
        await mem.store_engagement_outcome("acct_2", "user_b", "dm", "success")

        records_1 = await mem.recall_recent_engagements("acct_1")
        records_2 = await mem.recall_recent_engagements("acct_2")
        assert len(records_1) == 1
        assert records_1[0]["target_id"] == "user_a"
        assert len(records_2) == 1
        assert records_2[0]["target_id"] == "user_b"

    @pytest.mark.asyncio
    async def test_rejected_targets(self):
        mem = InMemoryEngagementMemoryAdapter()
        await mem.store_engagement_outcome("acct_1", "user_a", "follow", "rejected")
        await mem.store_engagement_outcome("acct_1", "user_b", "dm", "success")

        rejected = await mem.recall_rejected_targets("acct_1")
        assert rejected == {"user_a"}

    @pytest.mark.asyncio
    async def test_limit_respected(self):
        mem = InMemoryEngagementMemoryAdapter()
        for i in range(10):
            await mem.store_engagement_outcome("acct_1", f"user_{i}", "follow", "success")

        records = await mem.recall_recent_engagements("acct_1", limit=3)
        assert len(records) == 3

    @pytest.mark.asyncio
    async def test_newest_first(self):
        mem = InMemoryEngagementMemoryAdapter()
        await mem.store_engagement_outcome("acct_1", "old_user", "follow", "success")
        await mem.store_engagement_outcome("acct_1", "new_user", "dm", "success")

        records = await mem.recall_recent_engagements("acct_1")
        assert records[0]["target_id"] == "new_user"


# ===========================================================================
# Node integration — discover_candidates filters via memory
# ===========================================================================

class TestDiscoverCandidatesMemoryFilter:
    @pytest.mark.asyncio
    async def test_filters_recently_engaged(self):
        mem = InMemoryEngagementMemoryAdapter()
        await mem.store_engagement_outcome("acct_1", "already_engaged", "follow", "success")

        candidates = [
            EngagementTarget(target_id="already_engaged", target_type="account", metadata={}),
            EngagementTarget(target_id="fresh_target", target_type="account", metadata={}),
        ]
        nodes = _make_nodes(memory=mem, candidates=candidates)
        state = _base_state()

        result = await nodes.discover_candidates_node(state)
        found_ids = [c["target_id"] for c in result["candidate_targets"]]
        assert "already_engaged" not in found_ids
        assert "fresh_target" in found_ids

    @pytest.mark.asyncio
    async def test_filters_rejected_targets(self):
        mem = InMemoryEngagementMemoryAdapter()
        await mem.store_engagement_outcome("acct_1", "rejected_user", "dm", "rejected")

        candidates = [
            EngagementTarget(target_id="rejected_user", target_type="account", metadata={}),
            EngagementTarget(target_id="good_user", target_type="account", metadata={}),
        ]
        nodes = _make_nodes(memory=mem, candidates=candidates)
        state = _base_state()

        result = await nodes.discover_candidates_node(state)
        found_ids = [c["target_id"] for c in result["candidate_targets"]]
        assert "rejected_user" not in found_ids
        assert "good_user" in found_ids

    @pytest.mark.asyncio
    async def test_all_filtered_returns_no_candidates(self):
        mem = InMemoryEngagementMemoryAdapter()
        await mem.store_engagement_outcome("acct_1", "only_user", "follow", "success")

        candidates = [
            EngagementTarget(target_id="only_user", target_type="account", metadata={}),
        ]
        nodes = _make_nodes(memory=mem, candidates=candidates)
        state = _base_state()

        result = await nodes.discover_candidates_node(state)
        assert result["stop_reason"] == "no_candidates"

    @pytest.mark.asyncio
    async def test_no_memory_port_passes_through(self):
        """When memory port is None, all candidates pass through unfiltered."""
        candidates = [
            EngagementTarget(target_id="user_a", target_type="account", metadata={}),
        ]
        nodes = _make_nodes(memory=None, candidates=candidates)
        state = _base_state()

        result = await nodes.discover_candidates_node(state)
        assert len(result["candidate_targets"]) == 1

    @pytest.mark.asyncio
    async def test_memory_failure_degrades_gracefully(self):
        """If memory recall fails, candidates pass through unfiltered."""
        class _BrokenMemory(EngagementMemoryPort):
            async def recall_recent_engagements(self, *a, **kw):
                raise RuntimeError("store down")
            async def store_engagement_outcome(self, *a, **kw):
                pass
            async def recall_rejected_targets(self, *a, **kw):
                raise RuntimeError("store down")

        candidates = [
            EngagementTarget(target_id="user_a", target_type="account", metadata={}),
        ]
        nodes = _make_nodes(memory=_BrokenMemory(), candidates=candidates)
        state = _base_state()

        result = await nodes.discover_candidates_node(state)
        assert len(result["candidate_targets"]) == 1


# ===========================================================================
# Node integration — log_outcome stores to memory
# ===========================================================================

class TestLogOutcomeMemoryStore:
    @pytest.mark.asyncio
    async def test_stores_success_outcome(self):
        mem = InMemoryEngagementMemoryAdapter()
        nodes = _make_nodes(memory=mem)

        state = _base_state(
            proposed_action=ProposedAction(
                action_type="follow", target_id="user_x",
                content=None, reasoning="test", expected_outcome="test",
            ),
            execution_result=ExecutionResult(
                success=True, action_id="f_1", reason="ok", reason_code="ok", timestamp=time.time(),
            ),
        )

        await nodes.log_outcome_node(state)

        records = await mem.recall_recent_engagements("acct_1")
        assert len(records) == 1
        assert records[0]["target_id"] == "user_x"
        assert records[0]["outcome"] == "success"

    @pytest.mark.asyncio
    async def test_stores_rejected_outcome(self):
        mem = InMemoryEngagementMemoryAdapter()
        nodes = _make_nodes(memory=mem)

        state = _base_state(
            proposed_action=ProposedAction(
                action_type="dm", target_id="user_y",
                content="hi", reasoning="test", expected_outcome="test",
            ),
            stop_reason="approval_rejected",
        )

        await nodes.log_outcome_node(state)

        records = await mem.recall_recent_engagements("acct_1")
        assert len(records) == 1
        assert records[0]["outcome"] == "rejected"

        rejected = await mem.recall_rejected_targets("acct_1")
        assert "user_y" in rejected

    @pytest.mark.asyncio
    async def test_no_memory_port_no_crash(self):
        """When memory port is None, log_outcome still works."""
        nodes = _make_nodes(memory=None)
        state = _base_state(
            proposed_action=ProposedAction(
                action_type="follow", target_id="user_z",
                content=None, reasoning="test", expected_outcome="test",
            ),
        )

        result = await nodes.log_outcome_node(state)
        assert "audit_trail" in result
