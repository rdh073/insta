"""Contract tests for smart engagement payload structures.

Verifies:
1. Interrupt payload is self-contained: has all UI-required fields
   (account_id, target, draft_action, relevance_reason, risk_reason, options, timeout_at)
2. Audit events have traceable top-level fields extracted by FileAuditLogAdapter
   (thread_id, source_account, target_id, action_type, approval_id, risk_level, rule_hits)
3. ApprovalPort contract: submit returns id, get_approval_status returns full record
4. Audit trail reducer: events accumulate via _append_audit_events (no deduplication, no drop)

These contract tests do NOT run the full graph.
They verify the payload structure at node and adapter level.
"""

from __future__ import annotations

import sys
import time
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest

from ai_copilot.application.smart_engagement.state import (
    AccountHealth,
    AuditEvent,
    ApprovalRequest,
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

class _InMemoryAuditLog(AuditLogPort):
    def __init__(self):
        self.events: list[AuditEvent] = []

    async def log_event(self, event: AuditEvent) -> None:
        self.events.append(event)

    async def get_audit_trail(self, thread_id: str) -> list[AuditEvent]:
        return self.events


class _FakeAccountContext(AccountContextPort):
    async def get_account_context(self, account_id) -> AccountHealth:
        return AccountHealth(status="active", login_state="logged_in", cooldown_until=None, proxy=None, recent_actions=0)

    async def validate_account_ready(self, account_id) -> bool:
        return True


class _FakeCandidates(EngagementCandidatePort):
    def __init__(self, candidates: list[EngagementTarget] | None = None):
        self._candidates = candidates or []

    async def discover_candidates(self, account_id, goal, filters=None):
        return list(self._candidates)

    async def get_target_metadata(self, target_id):
        return {}


class _FakeRisk(RiskScoringPort):
    async def assess_risk(self, action, target, account_health) -> RiskAssessment:
        return RiskAssessment(risk_level="medium", rule_hits=["write_action"], reasoning="write op", requires_approval=True)


class _FakeApproval(ApprovalPort):
    async def submit_for_approval(self, action=None, risk_assessment=None, audit_trail=None, approval_request=None) -> str:
        return "apr_contract_test"

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


def _make_nodes(
    audit_log=None,
    candidate_discovery: EngagementCandidatePort | None = None,
    executor: EngagementExecutorPort | None = None,
):
    from ai_copilot.application.smart_engagement.nodes import SmartEngagementNodes

    return SmartEngagementNodes(
        account_context=_FakeAccountContext(),
        candidate_discovery=candidate_discovery or _FakeCandidates(),
        risk_scoring=_FakeRisk(),
        approval=_FakeApproval(),
        executor=executor or _FakeExecutor(),
        audit_log=audit_log or _InMemoryAuditLog(),
    )


def _base_state(**overrides):
    state = {
        "messages": [], "current_tool_calls": None, "tool_results": {}, "stop_reason": None, "step_count": 0,
        "thread_id": "contract-thread", "mode": "execute", "goal": "comment on educational posts", "structured_goal": None,
        "account_id": "acc_1", "account_health": AccountHealth(status="active", login_state="logged_in", cooldown_until=None, proxy=None, recent_actions=0),
        "candidate_targets": [], "selected_target": None,
        "proposed_action": ProposedAction(action_type="comment", target_id="post_123", content="Great post!", reasoning="educational content", expected_outcome="visibility"),
        "draft_payload": DraftPayload(content="Great post!", reasoning="educational", tone="professional"),
        "risk_assessment": RiskAssessment(risk_level="medium", rule_hits=["write_action"], reasoning="write op", requires_approval=True),
        "approval_request": None, "approval_result": None, "execution_result": None,
        "audit_trail": [], "discovery_attempted": False, "approval_attempted": False,
        "outcome_reason": None, "approval_timeout": 3600.0, "max_targets": 5, "max_actions_per_target": 3,
    }
    state.update(overrides)
    return state


def _merge_state(state: dict, updates: dict) -> dict:
    """Merge node updates while preserving append-only audit trail semantics."""
    merged = dict(state)
    existing_trail = list(state.get("audit_trail", []))
    merged.update(updates)
    new_trail = updates.get("audit_trail")
    if isinstance(new_trail, list):
        merged["audit_trail"] = existing_trail + new_trail
    return merged


async def _run_mixed_trace_flow(nodes, state: dict) -> dict:
    """Run a mixed-node sequence to produce a full traceable audit trail."""
    state = _merge_state(state, await nodes.ingest_goal_node(state))
    state = _merge_state(state, await nodes.load_account_context_node(state))
    state = _merge_state(state, await nodes.discover_candidates_node(state))
    state = _merge_state(state, await nodes.rank_candidates_node(state))
    state = _merge_state(state, await nodes.draft_action_node(state))
    state = _merge_state(state, await nodes.score_risk_node(state))

    from unittest.mock import patch

    with patch(
        "ai_copilot.application.smart_engagement.nodes.interrupt",
        return_value={"decision": "approved", "notes": "contract trace"},
    ):
        state = _merge_state(state, await nodes.request_approval_node(state))

    state = _merge_state(state, await nodes.execute_action_node(state))
    state = _merge_state(state, await nodes.log_outcome_node(state))
    return state


# ===========================================================================
# Interrupt payload contract
# ===========================================================================

@pytest.mark.asyncio
async def test_interrupt_payload_has_all_required_ui_fields():
    """Interrupt payload must be self-contained for UI rendering.

    UI contract (operator sees without additional state lookup):
    - account_id, target, draft_action (action_type, target_id, content)
    - relevance_reason, risk_reason, risk_level, rule_hits
    - options: [approve, reject, edit]
    - timeout_at, requested_at
    - thread_id (needed to resume)
    - approval_id (for tracking)
    """
    audit_log = _InMemoryAuditLog()
    nodes = _make_nodes(audit_log=audit_log)
    state = _base_state()

    # We need to capture the interrupt payload without actually running LangGraph
    # by inspecting what request_approval_node builds before calling interrupt()
    # We use a patched interrupt to intercept the payload
    captured = {}

    from unittest.mock import patch

    def _capture_interrupt(payload):
        captured["payload"] = payload
        # Return a rejection to avoid continuing execution
        return {"decision": "rejected", "notes": "contract test"}

    with patch("ai_copilot.application.smart_engagement.nodes.interrupt", side_effect=_capture_interrupt):
        result = await nodes.request_approval_node(state)

    payload = captured.get("payload")
    assert payload is not None, "interrupt() was not called"

    # Required UI fields
    assert "account_id" in payload
    assert "target" in payload
    assert "draft_action" in payload
    assert "action_type" in payload["draft_action"]
    assert "target_id" in payload["draft_action"]
    assert "content" in payload["draft_action"]
    assert "relevance_reason" in payload
    assert "risk_reason" in payload
    assert "risk_level" in payload
    assert "rule_hits" in payload
    assert "options" in payload
    assert "approve" in payload["options"]
    assert "reject" in payload["options"]
    assert "edit" in payload["options"]
    assert "timeout_at" in payload
    assert "requested_at" in payload
    assert "thread_id" in payload
    assert "approval_id" in payload


@pytest.mark.asyncio
async def test_interrupt_payload_values_from_state():
    """Interrupt payload values must reflect the current state."""
    audit_log = _InMemoryAuditLog()
    nodes = _make_nodes(audit_log=audit_log)
    state = _base_state(
        account_id="specific_account",
        mode="execute",
    )

    captured = {}

    from unittest.mock import patch

    def _capture(payload):
        captured["payload"] = payload
        return {"decision": "rejected", "notes": ""}

    with patch("ai_copilot.application.smart_engagement.nodes.interrupt", side_effect=_capture):
        await nodes.request_approval_node(state)

    payload = captured["payload"]
    assert payload["account_id"] == "specific_account"
    assert payload["draft_action"]["action_type"] == "comment"
    assert payload["draft_action"]["target_id"] == "post_123"
    assert payload["draft_action"]["content"] == "Great post!"
    assert payload["operator_intent"] == "comment on educational posts"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("incoming", "expected"),
    [
        ("approve", "approved"),
        ("reject", "rejected"),
        ("edit", "approved"),
    ],
)
async def test_request_approval_normalizes_resume_decision_aliases(
    incoming: str,
    expected: str,
):
    """Alias decisions from interrupt resume must normalize to canonical state values."""
    audit_log = _InMemoryAuditLog()
    nodes = _make_nodes(audit_log=audit_log)
    state = _base_state(mode="execute")

    from unittest.mock import patch

    with patch(
        "ai_copilot.application.smart_engagement.nodes.interrupt",
        return_value={"decision": incoming, "notes": "normalized", "content": "Edited draft"},
    ):
        result = await nodes.request_approval_node(state)

    assert result["approval_result"]["decision"] == expected

    if incoming == "edit":
        assert result["approval_result"]["edited_content"] == "Edited draft"
        assert result["proposed_action"]["content"] == "Edited draft"
    if incoming == "reject":
        assert result["stop_reason"] == "approval_rejected"


# ===========================================================================
# Audit event payload contract
# ===========================================================================

@pytest.mark.asyncio
async def test_audit_event_has_required_fields():
    """Each audit event must have event_type, node_name, event_data, timestamp."""
    audit_log = _InMemoryAuditLog()
    nodes = _make_nodes(audit_log=audit_log)
    state = _base_state()

    # Trigger a node that produces audit events
    await nodes.ingest_goal_node(state)

    assert len(audit_log.events) > 0
    event = audit_log.events[0]

    # AuditEvent contract
    assert "event_type" in event
    assert "node_name" in event
    assert "event_data" in event
    assert "timestamp" in event
    assert isinstance(event["timestamp"], float)
    assert isinstance(event["event_data"], dict)


@pytest.mark.asyncio
async def test_audit_events_accumulate_in_state():
    """Audit events must accumulate via _append_audit_events reducer."""
    from ai_copilot.application.smart_engagement.state import _append_audit_events

    existing = [
        AuditEvent(event_type="goal_ingested", node_name="ingest_goal", event_data={}, timestamp=1.0),
    ]
    new_events = [
        AuditEvent(event_type="account_loaded", node_name="load_account_context", event_data={}, timestamp=2.0),
        AuditEvent(event_type="candidates_discovered", node_name="discover_candidates", event_data={}, timestamp=3.0),
    ]

    result = _append_audit_events(existing, new_events)

    assert len(result) == 3
    assert result[0]["event_type"] == "goal_ingested"
    assert result[1]["event_type"] == "account_loaded"
    assert result[2]["event_type"] == "candidates_discovered"


def test_audit_reducer_ignores_non_list():
    """Reducer must not crash if new value is not a list."""
    from ai_copilot.application.smart_engagement.state import _append_audit_events

    existing = [AuditEvent(event_type="x", node_name="n", event_data={}, timestamp=1.0)]
    result = _append_audit_events(existing, None)
    assert result == existing

    result = _append_audit_events(existing, "not_a_list")
    assert result == existing


def test_audit_reducer_preserves_order():
    """Reducer must preserve chronological order."""
    from ai_copilot.application.smart_engagement.state import _append_audit_events

    e1 = AuditEvent(event_type="a", node_name="n", event_data={}, timestamp=1.0)
    e2 = AuditEvent(event_type="b", node_name="n", event_data={}, timestamp=2.0)
    e3 = AuditEvent(event_type="c", node_name="n", event_data={}, timestamp=3.0)

    result = _append_audit_events([e1], [e2, e3])
    assert [e["event_type"] for e in result] == ["a", "b", "c"]


# ===========================================================================
# FileAuditLogAdapter contract: traceable top-level fields
# ===========================================================================

@pytest.mark.asyncio
async def test_file_audit_log_writes_traceable_fields():
    """FileAuditLogAdapter must extract traceable fields to top-level for queryability."""
    from ai_copilot.adapters.file_audit_log_adapter import FileAuditLogAdapter

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        tmp_path = f.name

    adapter = FileAuditLogAdapter(log_path=tmp_path)

    event = AuditEvent(
        event_type="action_executed",
        node_name="execute_action",
        event_data={
            "thread_id": "thr_123",
            "account_id": "acc_1",
            "target_id": "user_xyz",
            "action_type": "follow",
            "success": True,
            "action_id": "act_456",
            "risk_level": "medium",
            "rule_hits": ["write_action"],
            "decision": "approved",
            "notes": "LGTM",
            "approval_id": "apr_789",
        },
        timestamp=time.time(),
    )

    await adapter.log_event(event)

    # Read back raw record
    records = adapter.read_all_records(limit=10)
    assert len(records) == 1
    record = records[0]

    # Top-level traceable fields (extracted from event_data)
    assert record["thread_id"] == "thr_123"
    assert record["source_account"] == "acc_1"
    assert record["target_id"] == "user_xyz"
    assert record["action_type"] == "follow"
    assert record["executor_success"] is True
    assert record["executor_action_id"] == "act_456"
    assert record["risk_level"] == "medium"
    assert record["approver_decision"] == "approved"
    assert record["approver_notes"] == "LGTM"
    assert record["approval_id"] == "apr_789"

    # Core event fields
    assert record["event_type"] == "action_executed"
    assert record["node_name"] == "execute_action"
    assert "timestamp" in record

    # Full event_data also present
    assert "event_data" in record

    Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_file_audit_log_get_audit_trail_filters_by_thread():
    """get_audit_trail must return only events for the requested thread_id."""
    from ai_copilot.adapters.file_audit_log_adapter import FileAuditLogAdapter

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        tmp_path = f.name

    adapter = FileAuditLogAdapter(log_path=tmp_path)

    await adapter.log_event(AuditEvent(
        event_type="goal_ingested", node_name="ingest_goal",
        event_data={"thread_id": "thread_A"}, timestamp=time.time(),
    ))
    await adapter.log_event(AuditEvent(
        event_type="goal_ingested", node_name="ingest_goal",
        event_data={"thread_id": "thread_B"}, timestamp=time.time(),
    ))
    await adapter.log_event(AuditEvent(
        event_type="account_loaded", node_name="load_account_context",
        event_data={"thread_id": "thread_A"}, timestamp=time.time() + 1,
    ))

    trail_a = await adapter.get_audit_trail("thread_A")
    trail_b = await adapter.get_audit_trail("thread_B")
    trail_c = await adapter.get_audit_trail("thread_C")

    assert len(trail_a) == 2
    assert len(trail_b) == 1
    assert len(trail_c) == 0

    Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_file_audit_log_none_values_excluded():
    """FileAuditLogAdapter must not write None values to keep log clean."""
    from ai_copilot.adapters.file_audit_log_adapter import FileAuditLogAdapter

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        tmp_path = f.name

    adapter = FileAuditLogAdapter(log_path=tmp_path)

    # Event with minimal data (most traceable fields will be None)
    await adapter.log_event(AuditEvent(
        event_type="goal_ingested", node_name="ingest_goal",
        event_data={"thread_id": "t1"}, timestamp=1.0,
    ))

    records = adapter.read_all_records()
    record = records[0]

    # None values should be excluded
    for key, val in record.items():
        assert val is not None, f"Field {key!r} should not be None in log record"

    Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_inmemory_adapter_mixed_nodes_preserve_thread_traceability():
    """In-memory retrieval returns a complete mixed-node trail with thread_id on all events."""
    from ai_copilot.adapters.audit_log_adapter import InMemoryAuditLogAdapter

    thread_id = "thread_trace_inmemory"
    audit_log = InMemoryAuditLogAdapter()
    candidates = [
        EngagementTarget(
            target_id="user_trace",
            target_type="account",
            metadata={"engagement_rate": 0.12, "follower_count": 500},
        )
    ]
    nodes = _make_nodes(
        audit_log=audit_log,
        candidate_discovery=_FakeCandidates(candidates=candidates),
    )
    state = _base_state(
        thread_id=thread_id,
        mode="execute",
        goal="comment on educational posts",
    )

    await _run_mixed_trace_flow(nodes, state)
    trail = await audit_log.get_audit_trail(thread_id)

    expected_types = [
        "goal_ingested",
        "account_loaded",
        "candidates_discovered",
        "target_selected",
        "action_drafted",
        "scored",
        "approval_requested",
        "approval_decided",
        "action_executed",
        "workflow_completed",
    ]
    assert [event["event_type"] for event in trail] == expected_types
    assert all(event["event_data"].get("thread_id") == thread_id for event in trail)
    timestamps = [event["timestamp"] for event in trail]
    assert timestamps == sorted(timestamps)


@pytest.mark.asyncio
async def test_file_adapter_mixed_nodes_preserve_thread_traceability():
    """File-backed retrieval returns a complete mixed-node trail with thread_id on all events."""
    from ai_copilot.adapters.file_audit_log_adapter import FileAuditLogAdapter

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        tmp_path = f.name

    thread_id = "thread_trace_file"
    audit_log = FileAuditLogAdapter(log_path=tmp_path)
    candidates = [
        EngagementTarget(
            target_id="user_trace_file",
            target_type="account",
            metadata={"engagement_rate": 0.08, "follower_count": 900},
        )
    ]
    nodes = _make_nodes(
        audit_log=audit_log,
        candidate_discovery=_FakeCandidates(candidates=candidates),
    )
    state = _base_state(
        thread_id=thread_id,
        mode="execute",
        goal="comment on educational posts",
    )

    await _run_mixed_trace_flow(nodes, state)
    trail = await audit_log.get_audit_trail(thread_id)

    expected_types = [
        "goal_ingested",
        "account_loaded",
        "candidates_discovered",
        "target_selected",
        "action_drafted",
        "scored",
        "approval_requested",
        "approval_decided",
        "action_executed",
        "workflow_completed",
    ]
    assert [event["event_type"] for event in trail] == expected_types
    assert all(event["event_data"].get("thread_id") == thread_id for event in trail)
    timestamps = [event["timestamp"] for event in trail]
    assert timestamps == sorted(timestamps)

    records = audit_log.read_all_records(limit=50)
    thread_records = [r for r in records if r.get("thread_id") == thread_id]
    assert len(thread_records) == len(expected_types)

    Path(tmp_path).unlink(missing_ok=True)


# ===========================================================================
# ApprovalPort contract
# ===========================================================================

@pytest.mark.asyncio
async def test_approval_adapter_submit_returns_string_id():
    from ai_copilot.adapters.approval_adapter import InMemoryApprovalAdapter

    adapter = InMemoryApprovalAdapter()
    action = ProposedAction(action_type="follow", target_id="t", content=None, reasoning="r", expected_outcome="e")
    risk = RiskAssessment(risk_level="medium", rule_hits=[], reasoning="write op", requires_approval=True)

    approval_id = await adapter.submit_for_approval(action=action, risk_assessment=risk, audit_trail=[])

    assert isinstance(approval_id, str)
    assert len(approval_id) > 0


@pytest.mark.asyncio
async def test_approval_adapter_initial_status_is_pending():
    from ai_copilot.adapters.approval_adapter import InMemoryApprovalAdapter

    adapter = InMemoryApprovalAdapter()
    action = ProposedAction(action_type="follow", target_id="t", content=None, reasoning="r", expected_outcome="e")
    risk = RiskAssessment(risk_level="medium", rule_hits=[], reasoning="write op", requires_approval=True)

    approval_id = await adapter.submit_for_approval(action=action, risk_assessment=risk, audit_trail=[])
    record = await adapter.get_approval_status(approval_id)

    assert record["status"] == "pending"
    assert record["approval_id"] == approval_id
    assert "requested_at" in record


@pytest.mark.asyncio
async def test_approval_adapter_approve_changes_status():
    from ai_copilot.adapters.approval_adapter import InMemoryApprovalAdapter

    adapter = InMemoryApprovalAdapter()
    action = ProposedAction(action_type="dm", target_id="t", content="hi", reasoning="r", expected_outcome="e")
    risk = RiskAssessment(risk_level="low", rule_hits=[], reasoning="ok", requires_approval=False)

    approval_id = await adapter.submit_for_approval(action=action, risk_assessment=risk, audit_trail=[])
    result = await adapter.record_approval_decision(approval_id=approval_id, approved=True, approver_notes="Looks good")

    assert result["status"] == "approved"
    assert result["approver_notes"] == "Looks good"
    assert result["approved_at"] is not None


@pytest.mark.asyncio
async def test_approval_adapter_reject_changes_status():
    from ai_copilot.adapters.approval_adapter import InMemoryApprovalAdapter

    adapter = InMemoryApprovalAdapter()
    action = ProposedAction(action_type="dm", target_id="t", content="hi", reasoning="r", expected_outcome="e")
    risk = RiskAssessment(risk_level="low", rule_hits=[], reasoning="ok", requires_approval=False)

    approval_id = await adapter.submit_for_approval(action=action, risk_assessment=risk, audit_trail=[])
    result = await adapter.record_approval_decision(approval_id=approval_id, approved=False, approver_notes="Rejected")

    assert result["status"] == "rejected"


@pytest.mark.asyncio
async def test_approval_adapter_not_found_raises():
    from ai_copilot.adapters.approval_adapter import InMemoryApprovalAdapter

    adapter = InMemoryApprovalAdapter()
    with pytest.raises((ValueError, KeyError)):
        await adapter.get_approval_status("nonexistent_id")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
