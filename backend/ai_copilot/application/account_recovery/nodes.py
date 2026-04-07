"""Node functions for Account Recovery workflow.

OWNERSHIP: Business logic via ports. No HTTP, no SDK, no LLM.

Topology:
  detect_issue
    [no issue]         → verify_account_health → finish(already_healthy)
    [unrecoverable]    → finish(unrecoverable)
  → classify_issue
  → choose_recovery_path
  → attempt_recovery   ← executes relogin or proxy swap
      [requires_2fa / approve_proxy_swap needed] → human_approval_or_2fa  ← INTERRUPT
          [abort]                → finish(aborted)
          [provide_2fa]          → attempt_recovery (with code)
          [approve_proxy_swap]   → attempt_recovery (proxy swap)
  → verify_account_health
      [healthy]                  → finish(recovered)
      [unhealthy + attempts < max] → choose_recovery_path (retry)
      [attempts >= max]          → finish(failed)

Loop guard: recovery_attempts < max_recovery_attempts
"""

from __future__ import annotations

import time

from langgraph.types import interrupt

from ai_copilot.application.account_recovery.ports import (
    AccountDiagnosticsPort,
    RecoveryExecutorPort,
)
from ai_copilot.application.account_recovery.state import AccountRecoveryState


class AccountRecoveryNodes:
    def __init__(
        self,
        diagnostics: AccountDiagnosticsPort,
        executor: RecoveryExecutorPort,
    ):
        self.diagnostics = diagnostics
        self.executor = executor

    def _event(self, event_type: str, node_name: str, data: dict) -> dict:
        return {"event_type": event_type, "node_name": node_name, "event_data": data, "timestamp": time.time()}

    # =========================================================================
    # Node 1: detect_issue
    # =========================================================================

    async def detect_issue_node(self, state: AccountRecoveryState) -> dict:
        account_id = state["account_id"]
        try:
            error_state = await self.diagnostics.read_error_state(account_id)
        except Exception as exc:
            return {
                "error_details": {"error": str(exc)[:120]},
                "outcome_reason": f"Failed to read error state: {str(exc)[:80]}",
                "stop_reason": "error",
                "step_count": state.get("step_count", 0) + 1,
                "audit_trail": [self._event("detect_failed", "detect_issue", {"error": str(exc)[:80]})],
            }

        has_error = error_state.get("has_error", False)
        if not has_error:
            return {
                "error_details": error_state,
                "error_type": "none",
                "current_proxy": error_state.get("proxy"),
                "stop_reason": "no_issue",
                "step_count": state.get("step_count", 0) + 1,
                "audit_trail": [self._event("no_issue_detected", "detect_issue", {"account_id": account_id})],
            }

        return {
            "error_details": error_state,
            "current_proxy": error_state.get("proxy"),
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("issue_detected", "detect_issue", {
                "account_id": account_id,
                "login_state": error_state.get("login_state"),
            })],
        }

    def route_after_detect(self, state: AccountRecoveryState) -> str:
        stop = state.get("stop_reason")
        if stop == "error":
            return "finish"
        if stop == "no_issue":
            return "verify_account_health"
        return "classify_issue"

    # =========================================================================
    # Node 2: classify_issue
    # =========================================================================

    async def classify_issue_node(self, state: AccountRecoveryState) -> dict:
        error_state = state.get("error_details") or {}
        try:
            error_type = await self.diagnostics.classify_issue(error_state)
        except Exception:
            error_type = "unknown"

        if error_type == "none":
            return {
                "error_type": "none",
                "stop_reason": "no_issue",
                "audit_trail": [self._event("classified_no_issue", "classify_issue", {})],
            }

        return {
            "error_type": error_type,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("issue_classified", "classify_issue", {"error_type": error_type})],
        }

    def route_after_classify(self, state: AccountRecoveryState) -> str:
        error_type = state.get("error_type")
        stop = state.get("stop_reason")
        if stop == "no_issue":
            return "verify_account_health"
        if error_type == "blocked":
            # Blocked accounts cannot be self-recovered
            return "finish_unrecoverable"
        return "choose_recovery_path"

    # =========================================================================
    # Node 3: choose_recovery_path
    # =========================================================================

    async def choose_recovery_path_node(self, state: AccountRecoveryState) -> dict:
        error_type = state.get("error_type", "unknown")
        attempts = state.get("recovery_attempts", 0)
        max_attempts = state.get("max_recovery_attempts", 3)

        # Loop guard
        if attempts >= max_attempts:
            return {
                "recovery_path": None,
                "outcome_reason": f"Max recovery attempts reached ({attempts}/{max_attempts})",
                "stop_reason": "max_attempts_reached",
                "audit_trail": [self._event("max_attempts", "choose_recovery_path", {
                    "attempts": attempts, "max": max_attempts,
                })],
            }

        # Path selection
        if error_type in ("session_expired", "unknown"):
            path = "relogin"
        elif error_type == "2fa_required":
            path = "relogin"  # will trigger 2FA interrupt
        elif error_type == "challenge":
            # Challenge — try proxy swap first, then relogin
            path = "swap_proxy" if attempts == 0 else "relogin"
        else:
            path = "relogin"

        return {
            "recovery_path": path,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("path_chosen", "choose_recovery_path", {
                "path": path, "error_type": error_type, "attempt": attempts + 1,
            })],
        }

    def route_after_choose(self, state: AccountRecoveryState) -> str:
        stop = state.get("stop_reason")
        if stop:
            return "finish"
        return "attempt_recovery"

    # =========================================================================
    # Node 4: attempt_recovery
    # =========================================================================

    async def attempt_recovery_node(self, state: AccountRecoveryState) -> dict:
        """Execute relogin or proxy swap, then interrupt if 2FA or proxy approval needed."""
        path = state.get("recovery_path", "relogin")
        account_id = state["account_id"]
        attempts = state.get("recovery_attempts", 0)
        op_decision = state.get("operator_decision")
        op_payload = state.get("operator_payload") or {}

        # ── Proxy swap path ────────────────────────────────────────────────────
        if path == "swap_proxy":
            # If operator already approved, do the swap
            if op_decision == "approve_proxy_swap":
                proxy = op_payload.get("proxy") or await self.executor.get_available_proxy(account_id)
                if not proxy:
                    return {
                        "recovery_path": "relogin",  # fallback
                        "audit_trail": [self._event("no_proxy", "attempt_recovery", {})],
                    }
                result = await self.executor.swap_proxy(account_id, proxy)
                return {
                    "proxy_swap_result": result,
                    "recovery_attempts": attempts + 1,
                    "operator_decision": None,
                    "step_count": state.get("step_count", 0) + 1,
                    "audit_trail": [self._event("proxy_swapped", "attempt_recovery", {
                        "success": result.get("success"), "proxy": proxy,
                    })],
                }
            else:
                # Need operator approval for proxy swap — interrupt
                candidate = await self.executor.get_available_proxy(account_id)
                interrupt_payload = {
                    "type": "account_recovery_approval",
                    "thread_id": state.get("thread_id"),
                    "account_id": account_id,
                    "username": state.get("username"),
                    "error_type": state.get("error_type"),
                    "recovery_path": "swap_proxy",
                    "proxy_candidate": candidate,
                    "options": ["approve_proxy_swap", "abort"],
                    "requested_at": time.time(),
                }
                decision = interrupt(interrupt_payload)
                decision = decision or {"decision": "abort"}
                d = decision.get("decision", "abort")
                audit = self._event("approval_received", "attempt_recovery", {"decision": d})
                if d == "abort":
                    return {
                        "operator_decision": "abort",
                        "operator_payload": decision,
                        "outcome_reason": "Operator aborted recovery",
                        "stop_reason": "aborted",
                        "audit_trail": [audit],
                    }
                return {
                    "operator_decision": d,
                    "operator_payload": decision,
                    "audit_trail": [audit],
                }

        # ── Relogin path ───────────────────────────────────────────────────────
        two_fa_code = op_payload.get("two_fa_code") if op_decision == "provide_2fa" else None
        result = await self.executor.relogin(account_id, two_fa_code=two_fa_code)

        if result.get("requires_2fa") and not two_fa_code:
            # Need 2FA code — interrupt
            interrupt_payload = {
                "type": "account_recovery_approval",
                "thread_id": state.get("thread_id"),
                "account_id": account_id,
                "username": state.get("username"),
                "error_type": "2fa_required",
                "recovery_path": "relogin",
                "options": ["provide_2fa", "abort"],
                "requested_at": time.time(),
            }
            decision = interrupt(interrupt_payload)
            decision = decision or {"decision": "abort"}
            d = decision.get("decision", "abort")
            audit = self._event("2fa_decision", "attempt_recovery", {"decision": d})
            if d == "abort":
                return {
                    "operator_decision": "abort",
                    "operator_payload": decision,
                    "outcome_reason": "Operator aborted 2FA",
                    "stop_reason": "aborted",
                    "audit_trail": [audit],
                }
            return {
                "operator_decision": d,
                "operator_payload": decision,
                "requires_2fa": True,
                "audit_trail": [audit],
            }

        return {
            "relogin_result": result,
            "recovery_attempts": attempts + 1,
            "operator_decision": None,
            "requires_2fa": result.get("requires_2fa", False),
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("relogin_attempted", "attempt_recovery", {
                "success": result.get("success"), "requires_2fa": result.get("requires_2fa"),
            })],
        }

    def route_after_attempt(self, state: AccountRecoveryState) -> str:
        stop = state.get("stop_reason")
        if stop:
            return "finish"
        # If operator_decision is set but not acted on yet (loop back for execution)
        op = state.get("operator_decision")
        if op in ("provide_2fa", "approve_proxy_swap"):
            return "attempt_recovery"
        return "verify_account_health"

    # =========================================================================
    # Node 5: verify_account_health
    # =========================================================================

    async def verify_account_health_node(self, state: AccountRecoveryState) -> dict:
        account_id = state["account_id"]
        try:
            health = await self.diagnostics.verify_account_health(account_id)
        except Exception as exc:
            health = {"healthy": False, "error": str(exc)[:80]}

        healthy = health.get("healthy", False)
        attempts = state.get("recovery_attempts", 0)
        max_attempts = state.get("max_recovery_attempts", 3)

        updates: dict = {
            "health_check_result": health,
            "step_count": state.get("step_count", 0) + 1,
            "audit_trail": [self._event("health_checked", "verify_account_health", {
                "healthy": healthy,
                "login_state": health.get("login_state"),
            })],
        }

        if healthy:
            updates["recovery_successful"] = True
            updates["result"] = "recovered"
            updates["stop_reason"] = "recovered"
            updates["outcome_reason"] = "Account successfully recovered"
        elif attempts >= max_attempts:
            updates["recovery_successful"] = False
            updates["result"] = "failed"
            updates["stop_reason"] = "max_attempts_reached"
            updates["outcome_reason"] = f"Recovery failed after {attempts} attempts"
        # else: unhealthy but can retry → route back to choose_recovery_path

        return updates

    def route_after_health(self, state: AccountRecoveryState) -> str:
        stop = state.get("stop_reason")
        if stop in ("recovered", "max_attempts_reached"):
            return "finish"
        if state.get("recovery_successful"):
            return "finish"
        attempts = state.get("recovery_attempts", 0)
        max_attempts = state.get("max_recovery_attempts", 3)
        if attempts < max_attempts:
            return "choose_recovery_path"
        return "finish"

    # =========================================================================
    # Node 6: finish_unrecoverable  (inline terminal for blocked accounts)
    # =========================================================================

    async def finish_unrecoverable_node(self, state: AccountRecoveryState) -> dict:
        return {
            "recovery_successful": False,
            "result": "unrecoverable",
            "stop_reason": "unrecoverable",
            "outcome_reason": f"Account is blocked — cannot be self-recovered: {state['account_id']}",
        }

    # =========================================================================
    # Node 7: finish
    # =========================================================================

    async def finish_node(self, state: AccountRecoveryState) -> dict:
        stop_reason = state.get("stop_reason") or "completed"
        outcome_reason = state.get("outcome_reason")
        result = state.get("result")

        if not outcome_reason:
            if stop_reason == "no_issue":
                outcome_reason = "Account is already healthy — no recovery needed"
            elif stop_reason == "aborted":
                outcome_reason = "Recovery aborted by operator"
            elif stop_reason == "recovered":
                outcome_reason = "Account successfully recovered"
            elif stop_reason == "unrecoverable":
                outcome_reason = f"Account blocked — manual intervention required"
            elif stop_reason == "max_attempts_reached":
                outcome_reason = "Recovery failed — max attempts reached"
            else:
                outcome_reason = f"Recovery ended: {stop_reason}"

        return {
            "stop_reason": stop_reason,
            "outcome_reason": outcome_reason,
            "result": result or stop_reason,
        }
