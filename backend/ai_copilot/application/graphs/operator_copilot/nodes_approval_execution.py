"""Approval/execution-stage node implementations for operator copilot graph."""

from __future__ import annotations

import json
import logging

from langgraph.types import interrupt

from ai_copilot.application.ports import validate_approval_payload
from ai_copilot.application.state import OperatorCopilotState

from .nodes_plan_policy import OperatorCopilotPlanPolicyNodes
from .planning_guards import _sanitize_proposed_tool_calls
from .prompts import (
    _REVIEW_SYSTEM_PROMPT,
    _SUMMARIZE_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class OperatorCopilotApprovalExecutionNodes(OperatorCopilotPlanPolicyNodes):
    """Node mix for approval, execution, review, summarization, and finish."""

    async def request_approval_if_needed_node(self, state: OperatorCopilotState) -> dict:
        """Interrupt execution to request operator approval for write-sensitive calls."""
        if state.get("approval_attempted"):
            await self.audit_log.log("stop_reason", {
                "stop_reason": "approval_limit_reached",
                "thread_id": state.get("thread_id"),
                "reason": "Approval already attempted this run. Rejection is final.",
            })
            return {
                "stop_reason": "rejected",
                "final_response": (
                    "Cannot process: approval already attempted this run. "
                    "Rejection is final. Please start a new session."
                ),
                "approval_attempted": True,
            }

        proposed = state.get("proposed_tool_calls", [])
        risk = state.get("risk_assessment") or {}
        execution_plan = state.get("execution_plan") or []

        plan_by_tool: dict[str, str] = {}
        for step in execution_plan:
            name = step.get("tool", "")
            reason = step.get("reason", "")
            if name and reason:
                plan_by_tool[name] = reason

        tool_reasons = {
            call["id"]: plan_by_tool.get(call["name"], "no reason provided")
            for call in proposed
        }

        approval_request = {
            "operator_intent": state.get("normalized_goal") or state.get("operator_request", ""),
            "proposed_tool_calls": proposed,
            "tool_reasons": tool_reasons,
            "risk_assessment": risk,
            "options": ["approve", "reject", "edit"],
        }

        validate_approval_payload(approval_request)

        await self.audit_log.log("approval_submitted", {
            "approval_request": approval_request,
            "thread_id": state.get("thread_id"),
        })

        decision = interrupt(approval_request)
        approval_result = decision.get("result", "rejected") if isinstance(decision, dict) else str(decision)
        edited_calls = decision.get("edited_calls") if isinstance(decision, dict) else None

        await self.audit_log.log("approval_result", {
            "approval_result": approval_result,
            "thread_id": state.get("thread_id"),
        })

        updates: dict = {
            "approval_result": approval_result,
            "approval_request": approval_request,
            "approval_attempted": True,
        }

        if approval_result == "approved":
            pass
        elif approval_result == "edited" and edited_calls:
            tool_schemas = self.tool_executor.get_schemas()
            sanitized, dropped = _sanitize_proposed_tool_calls(edited_calls, tool_schemas)
            if dropped:
                await self.audit_log.log("edited_calls_sanitized", {
                    "dropped": dropped,
                    "thread_id": state.get("thread_id"),
                })
            updates["proposed_tool_calls"] = sanitized
            updates["approved_tool_calls"] = []
        elif approval_result in ("rejected", "timeout"):
            updates["stop_reason"] = "rejected"
            updates["approved_tool_calls"] = []
            updates["final_response"] = "Action cancelled by operator."

        return updates

    async def execute_tools_node(self, state: OperatorCopilotState) -> dict:
        """Execute approved tool calls via ToolExecutorPort."""
        approved = state.get("approved_tool_calls", [])
        results: dict[str, dict] = {}
        tool_names: dict[str, str] = {}

        for call in approved:
            call_id = call.get("id", "")
            tool_name = call.get("name", "")
            tool_names[call_id] = tool_name
            args = call.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (TypeError, json.JSONDecodeError):
                    results[call_id] = {
                        "error": f"malformed_arguments: could not parse string arguments for {tool_name!r}"
                    }
                    await self.audit_log.log("execution_skipped", {
                        "call_id": call_id,
                        "tool_name": tool_name,
                        "reason": "malformed_string_arguments",
                    })
                    continue

            try:
                result = await self.tool_executor.execute(tool_name, args)
                results[call_id] = result
                await self.audit_log.log("tool_execution", {
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "args": args,
                    "result_keys": list(result.keys()) if isinstance(result, dict) else None,
                })
            except Exception as exc:
                error_result = {"error": str(exc)}
                results[call_id] = error_result
                await self.audit_log.log("execution_failure", {
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "error": str(exc),
                })

        return {"tool_results": results, "tool_call_names": tool_names}

    async def review_results_node(self, state: OperatorCopilotState) -> dict:
        """Review tool results against original intent."""
        tool_results = state.get("tool_results", {})
        execution_plan = state.get("execution_plan") or []
        intent = state.get("normalized_goal") or state.get("operator_request", "")

        messages = [
            {"role": "system", "content": _REVIEW_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({
                    "operator_intent": intent,
                    "execution_plan": execution_plan,
                    "tool_results": tool_results,
                }),
            },
        ]

        try:
            response = await self.llm_gateway.request_completion(
                messages=messages,
                **self._llm_request_kwargs(state),
            )
            raw = response.get("content", "{}")
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                raw = raw.rsplit("```", 1)[0].strip()
            findings = json.loads(raw)
        except Exception as exc:
            findings = {
                "matched_intent": False,
                "warnings": [f"reviewer_parse_error: {exc}"],
                "recommendation": "proceed_to_summary",
                "_parse_error": str(exc),
            }

        await self.audit_log.log("review_finding", {
            "matched_intent": findings.get("matched_intent"),
            "warnings": findings.get("warnings", []),
            "recommendation": findings.get("recommendation"),
        })

        return {"review_findings": findings}

    async def summarize_result_node(self, state: OperatorCopilotState) -> dict:
        """Produce the final response for the operator."""
        existing = state.get("final_response")
        stop_reason = state.get("stop_reason")
        if existing and stop_reason in ("blocked", "rejected", "responded"):
            return {"final_response": existing}

        tool_results = state.get("tool_results", {})
        execution_plan = state.get("execution_plan") or []
        review_findings = state.get("review_findings") or {}
        intent = state.get("normalized_goal") or state.get("operator_request", "")
        warnings = review_findings.get("warnings", [])

        messages = [
            {"role": "system", "content": _SUMMARIZE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({
                    "operator_request": intent,
                    "execution_plan": execution_plan,
                    "tool_results": tool_results,
                    "warnings": warnings,
                }),
            },
        ]

        try:
            response = await self.llm_gateway.request_completion(
                messages=messages,
                **self._llm_request_kwargs(state),
            )
            final_response = response.get("content", "")
        except Exception as exc:
            final_response = f"Summary unavailable: {exc}"

        return {"final_response": final_response}

    async def finish_node(self, state: OperatorCopilotState) -> dict:
        """Mark run as complete, log stop_reason, and persist interaction to memory."""
        stop_reason = state.get("stop_reason") or "done"
        final_stop = stop_reason if stop_reason != "responded" else "done"

        await self.audit_log.log("stop_reason", {
            "stop_reason": final_stop,
            "thread_id": state.get("thread_id"),
        })

        if self.copilot_memory is not None:
            goal = state.get("normalized_goal") or state.get("operator_request", "")
            tools_used = [call.get("name", "") for call in state.get("approved_tool_calls", [])]
            outcome = "success" if final_stop == "done" and tools_used else final_stop
            try:
                memory_ns = state.get("thread_id", "default")[:36]
                await self.copilot_memory.store_interaction_summary(memory_ns, {
                    "goal": goal,
                    "tools_used": tools_used,
                    "outcome": outcome,
                    "stop_reason": final_stop,
                })
            except Exception:
                logger.warning("Failed to store copilot interaction to memory")

        return {"stop_reason": final_stop}


__all__ = ["OperatorCopilotApprovalExecutionNodes"]
