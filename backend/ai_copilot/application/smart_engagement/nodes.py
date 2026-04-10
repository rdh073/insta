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

import logging
import time
import uuid
from typing import Any

from langgraph.types import interrupt

logger = logging.getLogger(__name__)

from ai_copilot.application.smart_engagement.ports import (
    AccountContextPort,
    ApprovalPort,
    AuditLogPort,
    EngagementCandidatePort,
    EngagementExecutorPort,
    EngagementMemoryPort,
    RiskScoringPort,
)
from ai_copilot.application.smart_engagement.state import (
    ApprovalRequest,
    AuditEvent,
    DraftPayload,
    ExecutionResult,
    ProposedAction,
    SmartEngagementState,
)

# Risk threshold: "high" stops workflow without approval
_HIGH_RISK_THRESHOLD = "high"


class SmartEngagementNodes:
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

    async def _emit(self, event: AuditEvent) -> AuditEvent:
        """Log event to AuditLogPort AND return it for state accumulation."""
        await self.audit_log.log_event(event)
        return event

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

    # =========================================================================
    # Node 1: ingest_goal
    # =========================================================================

    async def ingest_goal_node(self, state: SmartEngagementState) -> dict:
        """Parse operator goal into structured form.

        Pure parsing - no external calls. Extracts:
        - intent: what action type (comment, follow, like, dm)
        - target_type: account/post/hashtag
        - action_type: follow/comment/like/dm
        - constraints: content filters, audience criteria
        """
        goal = state.get("goal", "")

        structured_goal = _parse_goal(goal)

        event = await self._emit(AuditEvent(
            event_type="goal_ingested",
            node_name="ingest_goal",
            event_data={"goal": goal, "structured_goal": structured_goal, "thread_id": state.get("thread_id")},
            timestamp=time.time(),
        ))

        return {
            "structured_goal": structured_goal,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [event],
        }

    # =========================================================================
    # Node 2: load_account_context
    # =========================================================================

    async def load_account_context_node(self, state: SmartEngagementState) -> dict:
        """Fetch account health and constraints.

        If the account's session is missing/expired the node attempts one
        automatic relogin via AccountContextPort.try_refresh_session() before
        giving up.  This lets smart engagement recover from stale sessions
        (e.g. after a server restart) without operator intervention.

        Fail-fast: if account still not healthy after refresh attempt →
        outcome_reason set for log_outcome.
        Routing: route_after_account_context() → 'discover_candidates' or 'log_outcome'
        """
        account_id = state.get("account_id", "")

        try:
            health = await self.account_context.get_account_context(account_id)

            is_healthy = (
                health.get("status") == "active"
                and health.get("login_state") == "logged_in"
                and health.get("cooldown_until") is None
            )

            # Session not ready — try one automatic relogin before giving up.
            # try_refresh_session() returns False by default (no-op for adapters
            # that don't support it) so this is always safe to call.
            if not is_healthy and health.get("login_state") != "logged_in":
                refresh_event = await self._emit(AuditEvent(
                    event_type="session_refresh_attempted",
                    node_name="load_account_context",
                    event_data={"account_id": account_id, "reason": "session_not_loaded"},
                    timestamp=time.time(),
                ))
                refreshed = await self.account_context.try_refresh_session(account_id)
                if refreshed:
                    # Re-fetch health after successful refresh
                    health = await self.account_context.get_account_context(account_id)
                    is_healthy = (
                        health.get("status") == "active"
                        and health.get("login_state") == "logged_in"
                        and health.get("cooldown_until") is None
                    )
                    refresh_status = "success" if is_healthy else "partial"
                else:
                    refresh_status = "failed"

                refresh_done_event = await self._emit(AuditEvent(
                    event_type="session_refresh_result",
                    node_name="load_account_context",
                    event_data={
                        "account_id": account_id,
                        "result": refresh_status,
                        "now_healthy": is_healthy,
                    },
                    timestamp=time.time(),
                ))

                if not is_healthy:
                    reason = _account_not_healthy_reason(health)
                    skip_event = await self._emit(AuditEvent(
                        event_type="action_skipped",
                        node_name="load_account_context",
                        event_data={"reason": reason},
                        timestamp=time.time(),
                    ))
                    return {
                        "account_health": health,
                        "outcome_reason": reason,
                        "stop_reason": "account_not_ready",
                        "audit_trail": [refresh_event, refresh_done_event, skip_event],
                    }

                return {
                    "account_health": health,
                    "audit_trail": [
                        refresh_event,
                        refresh_done_event,
                        await self._emit(AuditEvent(
                            event_type="account_loaded",
                            node_name="load_account_context",
                            event_data={"account_id": account_id, "status": health.get("status"), "login_state": health.get("login_state"), "session_refreshed": True},
                            timestamp=time.time(),
                        )),
                    ],
                }

            if not is_healthy:
                reason = _account_not_healthy_reason(health)
                event = await self._emit(AuditEvent(
                    event_type="action_skipped",
                    node_name="load_account_context",
                    event_data={"reason": reason},
                    timestamp=time.time(),
                ))
                return {
                    "account_health": health,
                    "outcome_reason": reason,
                    "stop_reason": "account_not_ready",
                    "audit_trail": [event],
                }

            event = await self._emit(AuditEvent(
                event_type="account_loaded",
                node_name="load_account_context",
                event_data={"account_id": account_id, "status": health.get("status"), "login_state": health.get("login_state")},
                timestamp=time.time(),
            ))

            return {"account_health": health, "audit_trail": [event]}

        except Exception as e:
            reason = f"Account context error: {str(e)[:80]}"
            logger.exception("load_account_context failed for account=%s", account_id)
            event = await self._emit(AuditEvent(
                event_type="node_error",
                node_name="load_account_context",
                event_data={"error": reason, "account_id": account_id},
                timestamp=time.time(),
            ))
            return {
                "account_health": None,
                "outcome_reason": reason,
                "stop_reason": "error",
                "audit_trail": [event],
            }

    def route_after_account_context(self, state: SmartEngagementState) -> str:
        """Route: healthy account → discover_candidates, else → log_outcome."""
        health = state.get("account_health")
        stop = state.get("stop_reason")
        if stop or not health or health.get("status") != "active":
            return "log_outcome"
        return "discover_candidates"

    # =========================================================================
    # Node 3: discover_candidates
    # =========================================================================

    async def discover_candidates_node(self, state: SmartEngagementState) -> dict:
        """Discover engagement candidates based on operator goal.

        Bounded: max 1 discovery per run (discovery_attempted flag).
        Fail-fast: no candidates → outcome_reason set.
        Routing: route_after_discovery() → 'rank_candidates' or 'log_outcome'
        """
        # Failure rule: max 1 discovery per run
        if state.get("discovery_attempted"):
            return {
                "outcome_reason": "Discovery already attempted this run",
                "stop_reason": "discovery_limit_reached",
            }

        account_id = state.get("account_id", "")
        goal = state.get("goal", "")
        max_targets = state.get("max_targets", 5)

        try:
            candidates = await self.candidate_discovery.discover_candidates(
                account_id=account_id,
                goal=goal,
                filters={"max_results": max_targets},
            )

            # Filter out recently engaged and rejected targets via memory
            excluded_ids: set[str] = set()
            if self.engagement_memory is not None and candidates:
                try:
                    recent = await self.engagement_memory.recall_recent_engagements(account_id, limit=50)
                    excluded_ids.update(r["target_id"] for r in recent)
                    rejected = await self.engagement_memory.recall_rejected_targets(account_id)
                    excluded_ids.update(rejected)
                except Exception:
                    logger.warning("Memory recall failed for account=%s, proceeding without filter", account_id)

            if excluded_ids:
                before = len(candidates)
                candidates = [c for c in candidates if c.get("target_id") not in excluded_ids]
                filtered_count = before - len(candidates)
                if filtered_count > 0:
                    logger.info("Filtered %d recently-engaged/rejected targets for account=%s", filtered_count, account_id)

            if not candidates:
                reason = f"No candidates found for goal: {goal!r}"
                event = await self._emit(AuditEvent(
                    event_type="action_skipped",
                    node_name="discover_candidates",
                    event_data={"reason": reason, "goal": goal, "excluded_count": len(excluded_ids)},
                    timestamp=time.time(),
                ))
                return {
                    "candidate_targets": [],
                    "discovery_attempted": True,
                    "outcome_reason": reason,
                    "stop_reason": "no_candidates",
                    "audit_trail": [event],
                }

            event = await self._emit(AuditEvent(
                event_type="candidates_discovered",
                node_name="discover_candidates",
                event_data={"count": len(candidates), "goal": goal, "excluded_count": len(excluded_ids)},
                timestamp=time.time(),
            ))

            return {
                "candidate_targets": candidates,
                "discovery_attempted": True,
                "audit_trail": [event],
            }

        except Exception as e:
            reason = f"Discovery error: {str(e)[:80]}"
            logger.exception("discover_candidates failed for account=%s goal=%r", account_id, goal)
            event = await self._emit(AuditEvent(
                event_type="node_error",
                node_name="discover_candidates",
                event_data={"error": reason, "account_id": account_id, "goal": goal},
                timestamp=time.time(),
            ))
            return {
                "candidate_targets": [],
                "discovery_attempted": True,
                "outcome_reason": reason,
                "stop_reason": "error",
                "audit_trail": [event],
            }

    def route_after_discovery(self, state: SmartEngagementState) -> str:
        """Route: candidates found → rank_candidates, else → log_outcome."""
        stop = state.get("stop_reason")
        candidates = state.get("candidate_targets", [])
        if stop or not candidates:
            return "log_outcome"
        return "rank_candidates"

    # =========================================================================
    # Node 4: rank_candidates
    # =========================================================================

    async def rank_candidates_node(self, state: SmartEngagementState) -> dict:
        """Rank and select the best candidate target.

        Scores by: engagement_rate (primary), follower_count (secondary).
        Selects top-ranked candidate as selected_target.
        """
        candidates = state.get("candidate_targets", [])
        structured_goal = state.get("structured_goal") or {}

        if not candidates:
            return {"selected_target": None}

        # Score candidates by relevance and engagement
        scored = sorted(
            candidates,
            key=lambda c: _score_candidate(c, structured_goal),
            reverse=True,
        )

        selected = scored[0]

        event = await self._emit(AuditEvent(
            event_type="target_selected",
            node_name="rank_candidates",
            event_data={"target_id": selected.get("target_id"), "total_candidates": len(candidates), "reason": "Top-ranked by engagement_rate and goal fit"},
            timestamp=time.time(),
        ))

        return {"selected_target": selected, "audit_trail": [event]}

    # =========================================================================
    # Node 5: draft_action
    # =========================================================================

    async def draft_action_node(self, state: SmartEngagementState) -> dict:
        """Propose engagement action based on structured goal.

        Derives action_type from structured_goal.action_type.
        Creates ProposedAction + DraftPayload (self-contained).
        """
        selected_target = state.get("selected_target")
        structured_goal = state.get("structured_goal") or {}
        goal = state.get("goal", "")

        if not selected_target:
            return {"proposed_action": None, "draft_payload": None}

        target_id = selected_target.get("target_id", "")
        action_type = structured_goal.get("action_type", "follow")
        intent = structured_goal.get("intent", goal)

        # Build draft payload for DM/comment actions
        content = None
        if action_type in ("comment", "dm"):
            content = f"[Draft {action_type} for goal: {intent}]"

        draft_payload = DraftPayload(
            content=content,
            reasoning=f"Goal: {intent}. Target: {target_id}",
            tone="professional",
        )

        proposed_action = ProposedAction(
            action_type=action_type,
            target_id=target_id,
            content=content,
            reasoning=f"Relevant to goal: {intent}",
            expected_outcome=_expected_outcome(action_type),
        )

        event = await self._emit(AuditEvent(
            event_type="action_drafted",
            node_name="draft_action",
            event_data={"action_type": action_type, "target_id": target_id, "has_content": content is not None},
            timestamp=time.time(),
        ))

        return {
            "proposed_action": proposed_action,
            "draft_payload": draft_payload,
            "audit_trail": [event],
        }

    # =========================================================================
    # Node 6: score_risk
    # =========================================================================

    async def score_risk_node(self, state: SmartEngagementState) -> dict:
        """Rule-based risk assessment of proposed action.

        Uses RiskScoringPort (not LLM). Returns rule_hits + reasoning.
        Fail-fast: risk_level == 'high' → log_outcome.
        Routing: route_after_risk() → 'gate_by_mode' or 'log_outcome'
        """
        proposed_action = state.get("proposed_action")
        selected_target = state.get("selected_target")
        account_health = state.get("account_health")

        if not proposed_action or not selected_target or not account_health:
            return {
                "risk_assessment": None,
                "outcome_reason": "Missing action or target for risk scoring",
                "stop_reason": "missing_data",
            }

        try:
            risk = await self.risk_scoring.assess_risk(
                action=proposed_action,
                target=selected_target,
                account_health=account_health,
            )

            event = await self._emit(AuditEvent(
                event_type="scored",
                node_name="score_risk",
                event_data={"action_type": proposed_action.get("action_type"), "risk_level": risk.get("risk_level"), "rule_hits": risk.get("rule_hits", []), "reasoning": risk.get("reasoning")},
                timestamp=time.time(),
            ))

            # Fail-fast: high risk → log_outcome
            if risk.get("risk_level") == _HIGH_RISK_THRESHOLD:
                return {
                    "risk_assessment": risk,
                    "outcome_reason": f"Risk too high: {risk.get('reasoning')}",
                    "stop_reason": "risk_threshold_exceeded",
                    "audit_trail": [event],
                }

            return {"risk_assessment": risk, "audit_trail": [event]}

        except Exception as e:
            reason = f"Risk scoring error: {str(e)[:80]}"
            logger.exception("score_risk failed for action_type=%s", proposed_action.get("action_type"))
            event = await self._emit(AuditEvent(
                event_type="node_error",
                node_name="score_risk",
                event_data={"error": reason, "action_type": proposed_action.get("action_type")},
                timestamp=time.time(),
            ))
            return {
                "risk_assessment": None,
                "outcome_reason": reason,
                "stop_reason": "error",
                "audit_trail": [event],
            }

    def route_after_risk(self, state: SmartEngagementState) -> str:
        """Route: risk acceptable → gate_by_mode, high risk → log_outcome."""
        stop = state.get("stop_reason")
        risk = state.get("risk_assessment")
        if stop or not risk or risk.get("risk_level") == _HIGH_RISK_THRESHOLD:
            return "log_outcome"
        return "gate_by_mode"

    # =========================================================================
    # Node 7: gate_by_mode
    # =========================================================================

    async def gate_by_mode_node(self, state: SmartEngagementState) -> dict:
        """Pure mode gate - routes recommendation vs execute paths.

        No side effects. Routing only.
        - mode=recommendation → log_outcome (with recommendation data)
        - mode=execute → request_approval
        """
        mode = state.get("mode", "recommendation")
        proposed_action = state.get("proposed_action")

        if mode == "recommendation":
            action_type = proposed_action.get("action_type", "?") if proposed_action else "?"
            target_id = proposed_action.get("target_id", "?") if proposed_action else "?"
            return {
                "outcome_reason": (
                    f"Recommendation mode: {action_type} on {target_id} "
                    "(not executed - mode=recommendation)"
                ),
                "stop_reason": "recommendation_only",
            }

        # mode=execute: continue to request_approval (no state changes here)
        return {}

    def route_by_mode(self, state: SmartEngagementState) -> str:
        """Route: recommendation → log_outcome, execute → request_approval."""
        mode = state.get("mode", "recommendation")
        if mode == "recommendation":
            return "log_outcome"
        return "request_approval"

    # =========================================================================
    # Node 8: request_approval  (INTERRUPT)
    # =========================================================================

    async def request_approval_node(self, state: SmartEngagementState) -> dict:
        """Request human approval via LangGraph interrupt().

        Failure rule: max 1 approval per run (approval_attempted flag).
        Uses interrupt() to pause execution and wait for human decision.

        Interrupt payload is self-contained (UI renders without state lookup):
        - account_id, target, draft_action, relevance_reason, risk_reason
        - options: approve / reject / edit

        On resume: decision = interrupt return value (dict with 'decision' key).
        - 'approved' → route to execute_action
        - 'rejected' / 'timeout' → route to log_outcome
        """
        # Failure rule: max 1 approval per run
        if state.get("approval_attempted"):
            return {
                "outcome_reason": "Approval already attempted this run (rejection is final)",
                "stop_reason": "approval_limit_reached",
            }

        proposed_action = state.get("proposed_action")
        risk_assessment = state.get("risk_assessment")
        thread_id = state.get("thread_id", str(uuid.uuid4()))
        account_id = state.get("account_id", "")
        goal = state.get("goal", "")
        draft_payload = state.get("draft_payload")
        approval_timeout = state.get("approval_timeout", 3600.0)

        if not proposed_action or not risk_assessment:
            return {
                "approval_attempted": True,
                "outcome_reason": "Missing action or risk assessment for approval",
                "stop_reason": "missing_data",
            }

        approval_id = f"apr_{thread_id}_{int(time.time())}"

        # Build self-contained interrupt payload (UI reads this without state)
        interrupt_payload = {
            "approval_id": approval_id,
            "thread_id": thread_id,
            "account_id": account_id,
            "target": state.get("selected_target"),
            "draft_action": {
                "action_type": proposed_action.get("action_type"),
                "target_id": proposed_action.get("target_id"),
                "content": proposed_action.get("content"),
            },
            "draft_payload": draft_payload,
            "relevance_reason": proposed_action.get("reasoning", ""),
            "risk_reason": risk_assessment.get("reasoning", ""),
            "rule_hits": risk_assessment.get("rule_hits", []),
            "risk_level": risk_assessment.get("risk_level"),
            "operator_intent": goal,
            "options": ["approve", "reject", "edit"],
            "timeout_at": time.time() + approval_timeout,
            "requested_at": time.time(),
        }

        req_event = await self._emit(AuditEvent(
            event_type="approval_requested",
            node_name="request_approval",
            event_data={"approval_id": approval_id, "action_type": proposed_action.get("action_type"), "risk_level": risk_assessment.get("risk_level"), "thread_id": thread_id},
            timestamp=time.time(),
        ))

        # Store the ApprovalRequest in state (also saved to ApprovalPort for tracking)
        approval_request = ApprovalRequest(
            approval_id=approval_id,
            thread_id=thread_id,
            account_id=account_id,
            target_id=proposed_action.get("target_id", ""),
            action_type=proposed_action.get("action_type", ""),
            draft_payload=draft_payload or DraftPayload(content=None, reasoning="", tone=""),
            risk_level=risk_assessment.get("risk_level", "medium"),
            risk_reasoning=risk_assessment.get("reasoning", ""),
            operator_intent=goal,
            requested_at=time.time(),
        )

        # Submit to approval port for tracking
        await self.approval.submit_for_approval(
            action=proposed_action,
            risk_assessment=risk_assessment,
            audit_trail=state.get("audit_trail", []),
        )

        # INTERRUPT: pause here and wait for human decision
        # The caller receives interrupt_payload; resumes with decision dict
        decision = interrupt(interrupt_payload)

        # --- Resumed here with decision ---
        # decision is the value passed via Command(resume=...)

        # Handle timeout: if decision is not provided or timed out
        if not decision:
            decision_value = "timeout"
            notes = "No decision received (timeout)"
        else:
            decision_value = decision.get("decision", "timeout")
            notes = decision.get("notes", "")

        # Treat timeout as rejected
        if decision_value == "timeout":
            decision_value = "rejected"
            notes = notes or "Approval timed out"

        # Handle edit: update draft content if provided
        edited_content = None
        if decision_value == "edited":
            edited_content = decision.get("content")
            decision_value = "approved"  # Edit implies approval with modifications

        approval_result = {
            "approval_id": approval_id,
            "decision": decision_value,
            "approver_notes": notes,
            "edited_content": edited_content,
            "decided_at": time.time(),
        }

        dec_event = await self._emit(AuditEvent(
            event_type="approval_decided",
            node_name="request_approval",
            event_data={"approval_id": approval_id, "decision": decision_value, "notes": notes},
            timestamp=time.time(),
        ))

        # If edited, update proposed_action content
        updates: dict = {
            "approval_request": approval_request,
            "approval_result": approval_result,
            "approval_attempted": True,
            "audit_trail": [req_event, dec_event],
        }

        if decision_value == "approved" and edited_content and proposed_action:
            updated_action = dict(proposed_action)
            updated_action["content"] = edited_content
            updates["proposed_action"] = updated_action

        if decision_value == "rejected":
            updates["outcome_reason"] = f"Approval rejected: {notes}"
            updates["stop_reason"] = "approval_rejected"

        return updates

    def route_after_approval(self, state: SmartEngagementState) -> str:
        """Route: approved → execute_action, else → log_outcome."""
        stop = state.get("stop_reason")
        if stop:
            return "log_outcome"

        approval_result = state.get("approval_result")
        if approval_result and approval_result.get("decision") == "approved":
            return "execute_action"
        return "log_outcome"

    # =========================================================================
    # Node 9: execute_action
    # =========================================================================

    async def execute_action_node(self, state: SmartEngagementState) -> dict:
        """Execute approved engagement action.

        Invariants:
        - mode MUST be 'execute' (checked in gate_by_mode routing)
        - approval_result.decision MUST be 'approved'
        - Never called in recommendation mode (graph topology enforces this)
        """
        mode = state.get("mode", "recommendation")
        proposed_action = state.get("proposed_action")
        account_id = state.get("account_id", "")
        approval_result = state.get("approval_result")

        # Safety invariant: mode must be execute (should be guaranteed by graph)
        if mode != "execute":
            return {
                "execution_result": ExecutionResult(
                    success=False,
                    action_id=None,
                    reason="Mode invariant violated: not in execute mode",
                    reason_code="invariant_violated",
                    timestamp=time.time(),
                ),
                "stop_reason": "invariant_violated",
            }

        # Safety invariant: must be approved
        if not approval_result or approval_result.get("decision") != "approved":
            return {
                "execution_result": ExecutionResult(
                    success=False,
                    action_id=None,
                    reason="Not approved for execution",
                    reason_code="not_approved",
                    timestamp=time.time(),
                ),
                "stop_reason": "not_approved",
            }

        if not proposed_action:
            return {
                "execution_result": ExecutionResult(
                    success=False,
                    action_id=None,
                    reason="No action to execute",
                    reason_code="missing_action",
                    timestamp=time.time(),
                ),
            }

        try:
            action_type = proposed_action.get("action_type", "")
            target_id = proposed_action.get("target_id", "")

            if action_type == "follow":
                result = await self.executor.execute_follow(target_id=target_id, account_id=account_id)
            elif action_type == "dm":
                result = await self.executor.execute_dm(
                    target_id=target_id,
                    account_id=account_id,
                    message=proposed_action.get("content", ""),
                )
            elif action_type == "comment":
                result = await self.executor.execute_comment(
                    post_id=target_id,
                    account_id=account_id,
                    comment_text=proposed_action.get("content", ""),
                )
            elif action_type == "like":
                result = await self.executor.execute_like(post_id=target_id, account_id=account_id)
            else:
                result = ExecutionResult(
                    success=False,
                    action_id=None,
                    reason=f"Unknown action type: {action_type}",
                    reason_code="unsupported_action",
                    timestamp=time.time(),
                )

            result = self._normalize_execution_result(
                result,
                default_reason="Execution failed",
                default_reason_code="execution_failed",
            )

            event = await self._emit(AuditEvent(
                event_type="action_executed",
                node_name="execute_action",
                event_data={
                    "success": result.get("success", False),
                    "action_type": action_type,
                    "action_id": result.get("action_id"),
                    "reason": result.get("reason"),
                    "reason_code": result.get("reason_code"),
                },
                timestamp=time.time(),
            ))

            return {"execution_result": result, "audit_trail": [event]}

        except Exception as e:
            logger.exception("execute_action failed for action_type=%s account=%s", action_type, account_id)
            result = ExecutionResult(
                success=False,
                action_id=None,
                reason=f"Execution error: {str(e)[:80]}",
                reason_code="execution_failed",
                timestamp=time.time(),
            )
            event = await self._emit(AuditEvent(
                event_type="execution_error",
                node_name="execute_action",
                event_data={"success": False, "action_type": action_type, "error": str(e)[:80], "reason_code": "execution_failed"},
                timestamp=time.time(),
            ))
            return {"execution_result": result, "audit_trail": [event]}

    # =========================================================================
    # Node 10: log_outcome
    # =========================================================================

    async def log_outcome_node(self, state: SmartEngagementState) -> dict:
        """Explicit outcome logging node.

        All paths (success, failure, recommendation, rejection) pass through here.
        Sets final outcome_reason if not already set.
        Logs workflow_completed event.
        """
        stop_reason = state.get("stop_reason", "completed")
        outcome_reason = state.get("outcome_reason")
        execution_result = state.get("execution_result")
        mode = state.get("mode", "recommendation")

        # Derive outcome_reason if not set
        if not outcome_reason:
            if execution_result and execution_result.get("success"):
                outcome_reason = f"Action executed: {execution_result.get('action_id')}"
            elif execution_result and not execution_result.get("success"):
                outcome_reason = f"Action failed: {execution_result.get('reason')}"
            elif stop_reason == "recommendation_only":
                action = state.get("proposed_action")
                outcome_reason = (
                    f"Recommendation: {action.get('action_type')} on {action.get('target_id')}"
                    if action else "No recommendation generated"
                )
            else:
                outcome_reason = f"Workflow ended: {stop_reason}"

        # Store engagement outcome to cross-thread memory
        if self.engagement_memory is not None:
            proposed = state.get("proposed_action")
            account_id = state.get("account_id", "")
            if proposed and account_id:
                target_id = proposed.get("target_id", "")
                action_type = proposed.get("action_type", "")
                if execution_result and execution_result.get("success"):
                    outcome_val = "success"
                elif execution_result and not execution_result.get("success"):
                    outcome_val = "failed"
                elif stop_reason == "approval_rejected":
                    outcome_val = "rejected"
                elif stop_reason == "recommendation_only":
                    outcome_val = "skipped"
                else:
                    outcome_val = "skipped"
                try:
                    await self.engagement_memory.store_engagement_outcome(
                        account_id=account_id,
                        target_id=target_id,
                        action_type=action_type,
                        outcome=outcome_val,
                    )
                except Exception:
                    logger.warning("Failed to store engagement outcome to memory")

        event = await self._emit(AuditEvent(
            event_type="workflow_completed",
            node_name="log_outcome",
            event_data={"stop_reason": stop_reason, "outcome_reason": outcome_reason, "mode": mode, "thread_id": state.get("thread_id")},
            timestamp=time.time(),
        ))

        return {
            "outcome_reason": outcome_reason,
            "stop_reason": stop_reason,
            "audit_trail": [event],
        }

    # =========================================================================
    # Node 11: finish
    # =========================================================================

    async def finish_node(self, state: SmartEngagementState) -> dict:
        """Final state formatting. No side effects.

        Ensures stop_reason is set to a terminal value.
        Graph routes to END after this node.
        """
        stop_reason = state.get("stop_reason", "completed")

        # Normalize to terminal stop reasons
        if stop_reason not in (
            "recommendation_only",
            "action_executed",
            "approval_rejected",
            "account_not_ready",
            "no_candidates",
            "risk_threshold_exceeded",
            "approval_limit_reached",
            "discovery_limit_reached",
            "error",
            "invariant_violated",
            "not_approved",
            "missing_data",
            "completed",
        ):
            stop_reason = "completed"

        return {"stop_reason": stop_reason}


# =============================================================================
# Helpers
# =============================================================================

def _parse_goal(goal: str) -> dict:
    """Parse operator goal string into structured form.

    Examples:
        "comment on educational posts" → {intent: comment, action_type: comment, target_type: post}
        "follow accounts in tech space" → {intent: follow, action_type: follow, target_type: account}
        "like recent posts" → {intent: like, action_type: like, target_type: post}
    """
    goal_lower = goal.lower()

    # Derive action_type from goal keywords
    if "comment" in goal_lower:
        action_type = "comment"
        target_type = "post"
    elif "dm" in goal_lower or "direct message" in goal_lower or "message" in goal_lower:
        action_type = "dm"
        target_type = "account"
    elif "like" in goal_lower:
        action_type = "like"
        target_type = "post"
    elif "follow" in goal_lower:
        action_type = "follow"
        target_type = "account"
    else:
        # Default: follow account
        action_type = "follow"
        target_type = "account"

    # Extract content constraints from goal
    constraints: dict[str, Any] = {}
    if "educational" in goal_lower:
        constraints["content_filter"] = "educational"
    elif "tech" in goal_lower or "technology" in goal_lower:
        constraints["niche"] = "technology"
    elif "fitness" in goal_lower or "health" in goal_lower:
        constraints["niche"] = "health/fitness"

    return {
        "intent": goal,
        "action_type": action_type,
        "target_type": target_type,
        "constraints": constraints,
    }


def _account_not_healthy_reason(health: dict) -> str:
    """Return human-readable reason why account is not healthy."""
    if health.get("login_state") != "logged_in":
        return "Account session not loaded — please log in again from the Accounts page"
    if health.get("cooldown_until") is not None:
        return f"Account in cooldown until {health.get('cooldown_until')}"
    if health.get("status") != "active":
        return f"Account status: {health.get('status')} — account is not active"
    return "Account not ready"


def _score_candidate(candidate: dict, structured_goal: dict) -> float:
    """Score a candidate by goal relevance and engagement quality."""
    metadata = candidate.get("metadata", {})
    score = 0.0

    # Engagement rate is primary signal
    engagement_rate = metadata.get("engagement_rate", 0.0)
    score += engagement_rate * 100

    # Follower count (log scale - prefer mid-size accounts)
    followers = metadata.get("follower_count", 0)
    if followers > 0:
        import math
        score += min(math.log10(followers), 5)  # cap at 5 points

    # Recent activity bonus
    recent_posts = metadata.get("recent_posts", 0)
    score += min(recent_posts * 0.5, 3)  # cap at 3 points

    return score


def _expected_outcome(action_type: str) -> str:
    """Return expected outcome string for action type."""
    outcomes = {
        "follow": "Account followed; may receive follow-back",
        "dm": "Direct message sent; awaiting reply",
        "comment": "Comment posted; increases visibility",
        "like": "Post liked; increases account visibility",
        "skip": "Action skipped; no engagement taken",
    }
    return outcomes.get(action_type, "Unknown outcome")
