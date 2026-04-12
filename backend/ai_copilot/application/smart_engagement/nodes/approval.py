"""Smart engagement node stage: mode gating and approval interrupt handling."""

from __future__ import annotations

import time
import uuid

from ai_copilot.application.smart_engagement.state import (
    ApprovalRequest,
    AuditEvent,
    DraftPayload,
    SmartEngagementState,
)


class ApprovalNodesMixin:
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

        req_event = await self._emit(
            state,
            AuditEvent(
                event_type="approval_requested",
                node_name="request_approval",
                event_data={
                    "approval_id": approval_id,
                    "action_type": proposed_action.get("action_type"),
                    "risk_level": risk_assessment.get("risk_level"),
                    "thread_id": thread_id,
                },
                timestamp=time.time(),
            )
        )

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
        from ai_copilot.application.smart_engagement import (
            nodes as smart_engagement_nodes_module,
        )

        decision = smart_engagement_nodes_module.interrupt(interrupt_payload)

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

        dec_event = await self._emit(
            state,
            AuditEvent(
                event_type="approval_decided",
                node_name="request_approval",
                event_data={
                    "approval_id": approval_id,
                    "decision": decision_value,
                    "notes": notes,
                },
                timestamp=time.time(),
            )
        )

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
