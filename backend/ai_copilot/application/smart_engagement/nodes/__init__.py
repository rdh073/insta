"""Node functions for smart engagement workflow - todo-4: 11-node topology.

OWNERSHIP: Business logic via ports. No HTTP, no SDK, no LLM.
11 nodes: ingest_goal → load_account_context → discover_candidates → rank_candidates
          → draft_action → score_risk → gate_by_mode → request_approval
          → execute_action → log_outcome → finish

Routing rules (fail-fast):
- account not healthy → log_outcome → finish
- no candidates → log_outcome → finish
- risk too high (threshold) → log_outcome → finish
- mode=recommendation → gate_by_mode → log_outcome (skip approval/execute)
- only mode=execute → request_approval (interrupt)
- only approved → execute_action

Failure rules:
- max 1 discovery cycle per run (discovery_attempted flag)
- max 1 approval per run (approval_attempted flag)
- no infinite loops for finding "better" targets
- retry only for technical adapter errors (caught exceptions)
- approval timeout = rejected
"""

from __future__ import annotations

import time

from langgraph.types import interrupt

from ai_copilot.application.smart_engagement.goal_parser import (
    _account_not_healthy_reason,
    _expected_outcome,
    _parse_goal,
)
from ai_copilot.application.smart_engagement.nodes.approval import ApprovalNodesMixin
from ai_copilot.application.smart_engagement.nodes.context import ContextNodesMixin
from ai_copilot.application.smart_engagement.nodes.discovery import DiscoveryNodesMixin
from ai_copilot.application.smart_engagement.nodes.draft_risk import DraftRiskNodesMixin
from ai_copilot.application.smart_engagement.nodes.execution_outcome import (
    ExecutionOutcomeNodesMixin,
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
from ai_copilot.application.smart_engagement.scoring import _score_candidate
from ai_copilot.application.smart_engagement.state import (
    AuditEvent,
    ExecutionResult,
    SmartEngagementState,
)


class SmartEngagementNodes(
    ContextNodesMixin,
    DiscoveryNodesMixin,
    DraftRiskNodesMixin,
    ApprovalNodesMixin,
    ExecutionOutcomeNodesMixin,
):
    """11-node workflow for smart engagement (todo-4 topology).

    Uses 6 ports for decisions:
    1. AccountContextPort - Account health & constraints
    2. EngagementCandidatePort - Goal-based target discovery
    3. RiskScoringPort - Rule-based risk assessment (not LLM)
    4. ApprovalPort - Approval submission & tracking
    5. EngagementExecutorPort - Action execution (mode-guarded)
    6. AuditLogPort - Explicit event logging

    Invariants:
    - Default mode is 'recommendation' (no auto-execute)
    - Write actions require explicit approval
    - Max 1 discovery cycle and 1 approval per run
    - All decisions are auditable via explicit events
    - interrupt() used for approval (not polling)
    """

    def __init__(
        self,
        account_context: AccountContextPort,
        candidate_discovery: EngagementCandidatePort,
        risk_scoring: RiskScoringPort,
        approval: ApprovalPort,
        executor: EngagementExecutorPort,
        audit_log: AuditLogPort,
        engagement_memory: EngagementMemoryPort | None = None,
        max_steps: int = 11,
    ):
        self.account_context = account_context
        self.candidate_discovery = candidate_discovery
        self.risk_scoring = risk_scoring
        self.approval = approval
        self.executor = executor
        self.audit_log = audit_log
        self.engagement_memory = engagement_memory
        self.max_steps = max_steps

    async def _emit(
        self,
        state: SmartEngagementState,
        event: AuditEvent,
    ) -> AuditEvent:
        """Normalize + log event, then return it for state accumulation."""
        raw_event_data = event.get("event_data") or {}
        event_data = raw_event_data if isinstance(raw_event_data, dict) else {}

        normalized_data = dict(event_data)
        thread_id = state.get("thread_id")
        if isinstance(thread_id, str) and thread_id.strip():
            normalized_data.setdefault("thread_id", thread_id)

        account_id = state.get("account_id")
        if isinstance(account_id, str) and account_id.strip():
            normalized_data.setdefault("account_id", account_id)

        normalized_event = AuditEvent(
            event_type=str(event.get("event_type", "")),
            node_name=str(event.get("node_name", "")),
            event_data=normalized_data,
            timestamp=float(event.get("timestamp", time.time())),
        )
        await self.audit_log.log_event(normalized_event)
        return normalized_event

    def _normalize_execution_result(
        self,
        result: dict | None,
        *,
        default_reason: str,
        default_reason_code: str,
    ) -> ExecutionResult:
        """Normalize executor output into strict app-owned ExecutionResult shape."""
        payload = result or {}
        success = bool(payload.get("success", False))
        action_id_raw = payload.get("action_id")
        action_id = None if action_id_raw is None else str(action_id_raw)

        reason_raw = payload.get("reason")
        if isinstance(reason_raw, str) and reason_raw.strip():
            reason = reason_raw
        else:
            reason = "Action executed" if success else default_reason

        reason_code_raw = payload.get("reason_code")
        if isinstance(reason_code_raw, str) and reason_code_raw.strip():
            reason_code = reason_code_raw
        else:
            reason_code = "ok" if success else default_reason_code

        timestamp_raw = payload.get("timestamp")
        timestamp = (
            float(timestamp_raw)
            if isinstance(timestamp_raw, (int, float))
            else float(time.time())
        )

        return ExecutionResult(
            success=success,
            action_id=action_id,
            reason=reason,
            reason_code=reason_code,
            timestamp=timestamp,
        )


__all__ = [
    "SmartEngagementNodes",
    "_parse_goal",
    "_expected_outcome",
    "_account_not_healthy_reason",
    "_score_candidate",
    "interrupt",
]
