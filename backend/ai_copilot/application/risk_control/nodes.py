"""Node functions for Risk Control workflow.

OWNERSHIP: Business logic via ports. No HTTP, no SDK, no LLM.

Topology:
  load_account_signal
    [not found / error] → finish(error)
  → evaluate_risk
      [low]             → recheck_signal → finish(low_risk)
  → choose_policy
      [continue]        → recheck_signal → finish
      [cooldown]        → cooldown_action → recheck_signal → finish
      [rotate_proxy]    → rotate_proxy_action → recheck_signal → finish
      [escalate]        → escalate_to_operator  ← INTERRUPT
          [abort]                        → finish(aborted)
          [approve_policy / override]    → apply_operator_override → recheck_signal → finish
"""

from __future__ import annotations

import time

from langgraph.types import interrupt

from ai_copilot.application.risk_control.ports import (
    AccountSignalPort,
    PolicyDecisionPort,
    ProxyRotationPort,
)
from ai_copilot.application.risk_control.state import RiskControlState

# Risk thresholds
_LOW_RISK = "low"
_RISK_LEVELS = {"low": 0, "medium": 1, "high": 2, "critical": 3}

# Cooldown durations by risk level (seconds)
_COOLDOWN_DURATIONS = {
    "medium": 1800.0,    # 30 min
    "high": 7200.0,      # 2 hours
    "critical": 86400.0, # 24 hours
}


def _risk_score(level: str) -> int:
    return _RISK_LEVELS.get(level, 0)


class RiskControlNodes:
    def __init__(
        self,
        account_signal: AccountSignalPort,
        policy_decision: PolicyDecisionPort,
        proxy_rotation: ProxyRotationPort,
    ):
        self.account_signal = account_signal
        self.policy_decision = policy_decision
        self.proxy_rotation = proxy_rotation

    def _event(self, event_type: str, node_name: str, data: dict) -> dict:
        return {
            "event_type": event_type,
            "node_name": node_name,
            "event_data": data,
            "timestamp": time.time(),
        }

    # =========================================================================
    # Node 1: load_account_signal
    # =========================================================================

    async def load_account_signal_node(self, state: RiskControlState) -> dict:
        account_id = state["account_id"]
        try:
            status = await self.account_signal.get_account_status(account_id)
            events = await self.account_signal.get_recent_events(account_id, limit=20)
        except Exception as exc:
            reason = f"Failed to load account signal: {str(exc)[:120]}"
            return {
                "outcome_reason": reason,
                "stop_reason": "error",
                "step_count": state.get("step_count", 0) + 1,
                "audit_trail": [self._event("signal_load_failed", "load_account_signal", {"error": reason})],
            }

        if not status:
            return {
                "outcome_reason": f"Account not found: {account_id}",
                "stop_reason": "account_not_found",
                "step_count": state.get("step_count", 0) + 1,
                "audit_trail": [self._event("account_not_found", "load_account_signal", {"account_id": account_id})],
            }

        return {
            "account_status": status,
            "recent_events": events,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("signal_loaded", "load_account_signal", {
                "account_id": account_id,
                "status": status.get("status"),
                "event_count": len(events),
            })],
        }

    def route_after_load(self, state: RiskControlState) -> str:
        if state.get("stop_reason"):
            return "finish"
        return "evaluate_risk"

    # =========================================================================
    # Node 2: evaluate_risk
    # =========================================================================

    async def evaluate_risk_node(self, state: RiskControlState) -> dict:
        """Pure rule-based risk evaluation — no LLM."""
        status = state.get("account_status") or {}
        events = state.get("recent_events", [])

        risk_factors: list[str] = []
        risk_level = "low"

        # Rule: account not active
        if status.get("status") not in ("active", None):
            risk_factors.append(f"account_status:{status.get('status')}")
            risk_level = _max_risk(risk_level, "high")

        # Rule: not logged in
        if status.get("login_state") not in ("logged_in", None):
            risk_factors.append(f"login_state:{status.get('login_state')}")
            risk_level = _max_risk(risk_level, "critical")

        # Rule: already in cooldown
        if status.get("cooldown_until") and status["cooldown_until"] > time.time():
            risk_factors.append("in_cooldown")
            risk_level = _max_risk(risk_level, "medium")

        # Rule: recent error events
        error_events = [e for e in events if e.get("event_type") in ("login_error", "challenge", "blocked", "rate_limited")]
        if len(error_events) >= 3:
            risk_factors.append(f"error_burst:{len(error_events)}")
            risk_level = _max_risk(risk_level, "high")
        elif len(error_events) >= 1:
            risk_factors.append(f"recent_errors:{len(error_events)}")
            risk_level = _max_risk(risk_level, "medium")

        # Rule: challenge flag
        if status.get("error_flags") and "challenge" in status.get("error_flags", []):
            risk_factors.append("challenge_flag")
            risk_level = _max_risk(risk_level, "critical")

        reasoning = _build_reasoning(risk_level, risk_factors)

        return {
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "risk_reasoning": reasoning,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("risk_evaluated", "evaluate_risk", {
                "risk_level": risk_level,
                "risk_factors": risk_factors,
                "reasoning": reasoning,
            })],
        }

    def route_after_risk(self, state: RiskControlState) -> str:
        risk = state.get("risk_level", "low")
        if risk == _LOW_RISK:
            return "recheck_signal"
        return "choose_policy"

    # =========================================================================
    # Node 3: choose_policy
    # =========================================================================

    async def choose_policy_node(self, state: RiskControlState) -> dict:
        account_id = state["account_id"]
        risk_level = state.get("risk_level", "medium")
        risk_factors = state.get("risk_factors", [])
        recent_events = state.get("recent_events", [])

        try:
            decision = await self.policy_decision.evaluate(
                account_id=account_id,
                risk_level=risk_level,
                risk_factors=risk_factors,
                recent_events=recent_events,
            )
        except Exception as exc:
            decision = "escalate"

        # Fetch proxy candidate if rotation is possible option
        proxy_candidate = None
        if decision in ("rotate_proxy", "escalate"):
            try:
                proxy_candidate = await self.proxy_rotation.get_candidate_proxy(account_id)
            except Exception:
                pass

        return {
            "policy_decision": decision,
            "proxy_candidate": proxy_candidate,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("policy_chosen", "choose_policy", {
                "decision": decision,
                "risk_level": risk_level,
                "has_proxy_candidate": proxy_candidate is not None,
            })],
        }

    def route_after_policy(self, state: RiskControlState) -> str:
        decision = state.get("policy_decision", "escalate")
        if decision == "cooldown":
            return "cooldown_action"
        if decision == "rotate_proxy":
            return "rotate_proxy_action"
        if decision == "continue":
            return "recheck_signal"
        return "escalate_to_operator"  # default + explicit escalate

    # =========================================================================
    # Node 4a: cooldown_action
    # =========================================================================

    async def cooldown_action_node(self, state: RiskControlState) -> dict:
        account_id = state["account_id"]
        risk_level = state.get("risk_level", "medium")
        duration = _COOLDOWN_DURATIONS.get(risk_level, 1800.0)

        try:
            cooldown_until = await self.policy_decision.apply_cooldown(account_id, duration)
        except Exception as exc:
            cooldown_until = time.time() + duration

        return {
            "cooldown_until": cooldown_until,
            "final_policy": "cooldown",
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("cooldown_applied", "cooldown_action", {
                "account_id": account_id,
                "duration_seconds": duration,
                "cooldown_until": cooldown_until,
            })],
        }

    # =========================================================================
    # Node 4b: rotate_proxy_action
    # =========================================================================

    async def rotate_proxy_action_node(self, state: RiskControlState) -> dict:
        account_id = state["account_id"]
        proxy = state.get("proxy_candidate")

        if not proxy:
            # No proxy available — fall through as continue
            return {
                "proxy_rotation_result": {"success": False, "reason": "no_proxy_available"},
                "final_policy": "continue",
                "audit_trail": [self._event("proxy_rotation_skipped", "rotate_proxy_action", {
                    "reason": "no_proxy_available",
                })],
            }

        try:
            result = await self.proxy_rotation.apply_proxy(account_id, proxy)
        except Exception as exc:
            result = {"success": False, "reason": str(exc)[:80]}

        return {
            "proxy_rotation_result": result,
            "final_policy": "rotate_proxy",
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("proxy_rotated", "rotate_proxy_action", {
                "account_id": account_id,
                "proxy": proxy,
                "success": result.get("success", False),
            })],
        }

    # =========================================================================
    # Node 5: escalate_to_operator  (INTERRUPT)
    # =========================================================================

    async def escalate_to_operator_node(self, state: RiskControlState) -> dict:
        """Interrupt and ask operator to approve or override policy."""
        interrupt_payload = {
            "type": "risk_control_escalation",
            "thread_id": state.get("thread_id"),
            "account_id": state["account_id"],
            "risk_level": state.get("risk_level"),
            "risk_factors": state.get("risk_factors", []),
            "risk_reasoning": state.get("risk_reasoning"),
            "policy_decision": state.get("policy_decision"),
            "proxy_candidate": state.get("proxy_candidate"),
            "account_status": state.get("account_status"),
            "options": ["approve_policy", "override_policy", "abort"],
            "escalated_at": time.time(),
        }

        operator_response = interrupt(interrupt_payload)

        if not operator_response:
            operator_response = {"decision": "abort", "notes": "No response"}

        decision = operator_response.get("decision", "abort")
        audit = self._event("escalation_decided", "escalate_to_operator", {
            "decision": decision,
            "notes": operator_response.get("notes", ""),
        })

        if decision == "abort":
            return {
                "operator_override": operator_response,
                "outcome_reason": f"Operator aborted: {operator_response.get('notes', '')}",
                "stop_reason": "aborted",
                "audit_trail": [audit],
            }

        return {
            "operator_override": operator_response,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [audit],
        }

    def route_after_escalation(self, state: RiskControlState) -> str:
        if state.get("stop_reason") == "aborted":
            return "finish"
        return "apply_operator_override"

    # =========================================================================
    # Node 6: apply_operator_override
    # =========================================================================

    async def apply_operator_override_node(self, state: RiskControlState) -> dict:
        """Apply whatever policy the operator approved or overrode."""
        override = state.get("operator_override") or {}
        decision = override.get("decision", "approve_policy")
        override_policy = override.get("override_policy") or state.get("policy_decision") or "continue"
        account_id = state["account_id"]

        if decision == "override_policy":
            effective_policy = override_policy
        else:
            effective_policy = state.get("policy_decision", "continue")

        # Execute the effective policy
        result: dict = {}
        if effective_policy == "cooldown":
            duration = override.get("cooldown_duration") or _COOLDOWN_DURATIONS.get(
                state.get("risk_level", "medium"), 1800.0
            )
            try:
                cooldown_until = await self.policy_decision.apply_cooldown(account_id, duration)
                result = {"applied": "cooldown", "cooldown_until": cooldown_until}
            except Exception as exc:
                result = {"applied": "cooldown", "error": str(exc)[:80]}
        elif effective_policy == "rotate_proxy":
            proxy = state.get("proxy_candidate") or override.get("proxy")
            if proxy:
                try:
                    rot = await self.proxy_rotation.apply_proxy(account_id, proxy)
                    result = {"applied": "rotate_proxy", "result": rot}
                except Exception as exc:
                    result = {"applied": "rotate_proxy", "error": str(exc)[:80]}
        else:
            result = {"applied": effective_policy}

        return {
            "final_policy": effective_policy,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("override_applied", "apply_operator_override", {
                "effective_policy": effective_policy,
                "result": result,
            })],
        }

    # =========================================================================
    # Node 7: recheck_signal
    # =========================================================================

    async def recheck_signal_node(self, state: RiskControlState) -> dict:
        """Re-read account status after applying a policy."""
        account_id = state["account_id"]
        try:
            status = await self.account_signal.get_account_status(account_id)
        except Exception:
            status = state.get("account_status")

        # Re-evaluate risk based on fresh status
        recheck_risk = "low"
        if status:
            if status.get("login_state") not in ("logged_in", None):
                recheck_risk = "high"
            elif status.get("cooldown_until") and status["cooldown_until"] > time.time():
                recheck_risk = "medium"

        return {
            "recheck_status": status,
            "recheck_risk_level": recheck_risk,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("signal_rechecked", "recheck_signal", {
                "recheck_risk_level": recheck_risk,
                "account_status": status.get("status") if status else None,
            })],
        }

    # =========================================================================
    # Node 8: finish
    # =========================================================================

    async def finish_node(self, state: RiskControlState) -> dict:
        stop_reason = state.get("stop_reason")
        outcome_reason = state.get("outcome_reason")
        final_policy = state.get("final_policy")
        recheck_risk = state.get("recheck_risk_level")

        if not stop_reason:
            stop_reason = "completed"

        if not outcome_reason:
            if stop_reason == "aborted":
                outcome_reason = "Operator aborted risk control"
            elif stop_reason == "account_not_found":
                outcome_reason = f"Account not found: {state['account_id']}"
            elif stop_reason == "error":
                outcome_reason = "Risk control failed with an error"
            elif final_policy:
                recheck = f" (recheck: {recheck_risk})" if recheck_risk else ""
                outcome_reason = f"Policy applied: {final_policy}{recheck}"
            elif state.get("risk_level") == "low":
                outcome_reason = "Risk level is low — no action required"
            else:
                outcome_reason = f"Risk control completed: {stop_reason}"

        return {
            "stop_reason": stop_reason,
            "outcome_reason": outcome_reason,
        }


# =============================================================================
# Helpers
# =============================================================================

def _max_risk(current: str, candidate: str) -> str:
    if _risk_score(candidate) > _risk_score(current):
        return candidate
    return current


def _build_reasoning(risk_level: str, risk_factors: list[str]) -> str:
    if not risk_factors:
        return "No risk factors detected — account appears healthy."
    joined = ", ".join(risk_factors)
    return f"Risk level '{risk_level}' due to: {joined}."
