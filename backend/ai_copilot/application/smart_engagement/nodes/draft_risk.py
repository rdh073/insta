"""Smart engagement node stage: action drafting and risk scoring."""

from __future__ import annotations

import logging
import time

from ai_copilot.application.smart_engagement.goal_parser import _expected_outcome
from ai_copilot.application.smart_engagement.scoring import HIGH_RISK_THRESHOLD
from ai_copilot.application.smart_engagement.state import (
    AuditEvent,
    DraftPayload,
    ProposedAction,
    SmartEngagementState,
)

logger = logging.getLogger(__name__)


class DraftRiskNodesMixin:
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

        event = await self._emit(
            AuditEvent(
                event_type="action_drafted",
                node_name="draft_action",
                event_data={
                    "action_type": action_type,
                    "target_id": target_id,
                    "has_content": content is not None,
                },
                timestamp=time.time(),
            )
        )

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

            event = await self._emit(
                AuditEvent(
                    event_type="scored",
                    node_name="score_risk",
                    event_data={
                        "action_type": proposed_action.get("action_type"),
                        "risk_level": risk.get("risk_level"),
                        "rule_hits": risk.get("rule_hits", []),
                        "reasoning": risk.get("reasoning"),
                    },
                    timestamp=time.time(),
                )
            )

            # Fail-fast: high risk → log_outcome
            if risk.get("risk_level") == HIGH_RISK_THRESHOLD:
                return {
                    "risk_assessment": risk,
                    "outcome_reason": f"Risk too high: {risk.get('reasoning')}",
                    "stop_reason": "risk_threshold_exceeded",
                    "audit_trail": [event],
                }

            return {"risk_assessment": risk, "audit_trail": [event]}

        except Exception as e:
            reason = f"Risk scoring error: {str(e)[:80]}"
            logger.exception(
                "score_risk failed for action_type=%s", proposed_action.get("action_type")
            )
            event = await self._emit(
                AuditEvent(
                    event_type="node_error",
                    node_name="score_risk",
                    event_data={"error": reason, "action_type": proposed_action.get("action_type")},
                    timestamp=time.time(),
                )
            )
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
        if stop or not risk or risk.get("risk_level") == HIGH_RISK_THRESHOLD:
            return "log_outcome"
        return "gate_by_mode"
