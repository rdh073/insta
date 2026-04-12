"""Smart engagement node stage: execution, outcome logging, and finish."""

from __future__ import annotations

import logging
import time

from ai_copilot.application.smart_engagement.state import (
    AuditEvent,
    ExecutionResult,
    SmartEngagementState,
)

logger = logging.getLogger(__name__)


class ExecutionOutcomeNodesMixin:
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
                result = await self.executor.execute_follow(
                    target_id=target_id, account_id=account_id
                )
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
                result = await self.executor.execute_like(
                    post_id=target_id, account_id=account_id
                )
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

            event = await self._emit(
                AuditEvent(
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
                )
            )

            return {"execution_result": result, "audit_trail": [event]}

        except Exception as e:
            logger.exception(
                "execute_action failed for action_type=%s account=%s",
                action_type,
                account_id,
            )
            result = ExecutionResult(
                success=False,
                action_id=None,
                reason=f"Execution error: {str(e)[:80]}",
                reason_code="execution_failed",
                timestamp=time.time(),
            )
            event = await self._emit(
                AuditEvent(
                    event_type="execution_error",
                    node_name="execute_action",
                    event_data={
                        "success": False,
                        "action_type": action_type,
                        "error": str(e)[:80],
                        "reason_code": "execution_failed",
                    },
                    timestamp=time.time(),
                )
            )
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
                    if action
                    else "No recommendation generated"
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

        event = await self._emit(
            AuditEvent(
                event_type="workflow_completed",
                node_name="log_outcome",
                event_data={
                    "stop_reason": stop_reason,
                    "outcome_reason": outcome_reason,
                    "mode": mode,
                    "thread_id": state.get("thread_id"),
                },
                timestamp=time.time(),
            )
        )

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
