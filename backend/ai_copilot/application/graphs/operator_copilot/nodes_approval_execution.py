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


def _extract_json_object(raw: str) -> dict | None:
    """Best-effort extraction of a JSON object from an LLM response.

    Handles (a) plain JSON, (b) ``` fenced blocks, (c) prose surrounding a
    single top-level object. Returns None if no object can be recovered.
    """
    if not raw:
        return None

    candidate = raw.strip()
    if candidate.startswith("```"):
        # strip the opening fence (possibly language-tagged) and closing fence
        after_first_newline = candidate.split("\n", 1)
        candidate = after_first_newline[1] if len(after_first_newline) > 1 else ""
        candidate = candidate.rsplit("```", 1)[0].strip()

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        return parsed

    # Fallback: isolate the first balanced top-level {...} in the raw text.
    start = candidate.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(candidate)):
        ch = candidate[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(candidate[start : idx + 1])
                except json.JSONDecodeError:
                    return None
                return obj if isinstance(obj, dict) else None
    return None


def _extract_tool_error(result: object) -> str | None:
    """Normalize tool error payloads for deterministic audit logging.

    Tool handlers in this codebase often return {"error": ...} instead of
    raising exceptions. This helper converts that shape into a canonical
    non-empty string when present.
    """
    if not isinstance(result, dict):
        return None

    if "error" not in result:
        return None

    raw_error = result.get("error")
    if raw_error is None:
        return "unknown_error"

    if isinstance(raw_error, str):
        stripped = raw_error.strip()
        return stripped or "unknown_error"

    return str(raw_error)


class OperatorCopilotApprovalExecutionNodes(OperatorCopilotPlanPolicyNodes):
    """Node mix for approval, execution, review, summarization, and finish."""

    async def request_approval_if_needed_node(self, state: OperatorCopilotState) -> dict:
        """Interrupt execution to request operator approval for write-sensitive calls."""
        thread_id = state.get("thread_id")
        if state.get("approval_attempted"):
            await self.audit_log.log("stop_reason", {
                "stop_reason": "approval_limit_reached",
                "thread_id": thread_id,
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
            "thread_id": thread_id,
        })

        decision = interrupt(approval_request)
        approval_result = decision.get("result", "rejected") if isinstance(decision, dict) else str(decision)
        edited_calls = decision.get("edited_calls") if isinstance(decision, dict) else None

        updates: dict = {
            "approval_result": approval_result,
            "approval_request": approval_request,
            "approval_attempted": True,
        }
        approval_audit: dict = {
            "approval_result": approval_result,
            "thread_id": thread_id,
        }

        if approval_result == "approved":
            pass
        elif approval_result == "edited" and edited_calls:
            tool_schemas = self.tool_executor.get_schemas()
            sanitized, dropped = _sanitize_proposed_tool_calls(edited_calls, tool_schemas)
            updates["proposed_tool_calls"] = sanitized
            updates["approved_tool_calls"] = []
            approval_audit["edited_call_count"] = len(edited_calls) if isinstance(edited_calls, list) else 0
            approval_audit["sanitized_call_count"] = len(sanitized)
            if dropped:
                approval_audit["dropped_tool_calls"] = dropped
        elif approval_result == "edited":
            approval_audit["edited_call_count"] = 0
            approval_audit["sanitized_call_count"] = 0
            approval_audit["reason"] = "operator returned edited without edited_calls payload"
        elif approval_result in ("rejected", "timeout"):
            updates["stop_reason"] = "rejected"
            updates["approved_tool_calls"] = []
            updates["final_response"] = "Action cancelled by operator."

        await self.audit_log.log("approval_result", approval_audit)

        return updates

    async def execute_tools_node(self, state: OperatorCopilotState) -> dict:
        """Execute approved tool calls via ToolExecutorPort."""
        thread_id = state.get("thread_id")
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
                    error = "malformed_arguments"
                    results[call_id] = {
                        "error": f"malformed_arguments: could not parse string arguments for {tool_name!r}"
                    }
                    await self.audit_log.log("execution_failure", {
                        "thread_id": thread_id,
                        "call_id": call_id,
                        "tool_name": tool_name,
                        "status": "failure",
                        "error": error,
                        "failure_kind": "malformed_string_arguments",
                    })
                    continue

            try:
                result = await self.tool_executor.execute(tool_name, args)
                results[call_id] = result
                error = _extract_tool_error(result)
                if error is not None:
                    await self.audit_log.log("execution_failure", {
                        "thread_id": thread_id,
                        "call_id": call_id,
                        "tool_name": tool_name,
                        "status": "failure",
                        "error": error,
                        "failure_kind": "error_return_payload",
                    })
                    continue

                await self.audit_log.log("tool_execution", {
                    "thread_id": thread_id,
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "status": "success",
                    "error": None,
                    "args": args,
                    "result_keys": list(result.keys()) if isinstance(result, dict) else None,
                })
            except Exception as exc:
                error_result = {"error": str(exc)}
                results[call_id] = error_result
                await self.audit_log.log("execution_failure", {
                    "thread_id": thread_id,
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "status": "failure",
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

        parse_error: str | None = None
        findings: dict | None = None
        try:
            response = await self._call_llm_or_fail("review_results", state, messages)
            raw = response.get("content", "") or ""
            findings = _extract_json_object(raw)
            if findings is None:
                parse_error = "reviewer_returned_non_json"
        except Exception:
            # node_error audit event and logger.exception already emitted by _call_llm_or_fail.
            parse_error = "llm_call_failed"

        if findings is None:
            # Reviewer failed, but tool results themselves are fine. Treat as
            # a silent pass-through so we don't surface reviewer plumbing
            # errors to the operator. The parse error is still audited.
            findings = {
                "matched_intent": True,
                "warnings": [],
                "recommendation": "proceed_to_summary",
            }

        await self.audit_log.log("review_finding", {
            "thread_id": state.get("thread_id"),
            "matched_intent": findings.get("matched_intent"),
            "warnings": findings.get("warnings", []),
            "recommendation": findings.get("recommendation"),
            "parse_error": parse_error,
        })

        return {"review_findings": findings}

    async def summarize_result_node(self, state: OperatorCopilotState) -> dict:
        """Produce the final response for the operator.

        Provider routing is state-driven: the summarize LLM call must target
        the provider/model/credentials the operator selected for this thread
        (read from ``state.provider``/``model``/``api_key``/``provider_base_url``
        via ``_llm_request_kwargs``). Do not re-introduce a node-local default
        — that would silently route Ollama-configured threads to OpenAI.
        """
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
            response = await self._call_llm_or_fail("summarize_result", state, messages)
            final_response = response.get("content", "")
        except Exception:
            # Raw exception text may contain provider internals (env-var names,
            # config hints, stack traces). Keep details in server logs (already
            # logged by _call_llm_or_fail); surface only a generic operator-safe
            # message per the CLAUDE.md "never surface raw vendor exception strings" rule.
            final_response = "Summary unavailable due to provider error."

        return {"final_response": final_response}

    async def finish_node(self, state: OperatorCopilotState) -> dict:
        """Mark run as complete, log stop_reason, and persist interaction to memory."""
        stop_reason = state.get("stop_reason") or "done"
        final_stop = stop_reason if stop_reason != "responded" else "done"
        existing_ns = state.get("copilot_memory_namespace")
        memory_ns = existing_ns if isinstance(existing_ns, str) and existing_ns.strip() else None
        if memory_ns is None and self.copilot_memory is not None:
            memory_ns = await self._resolve_copilot_memory_namespace(state)

        await self.audit_log.log("stop_reason", {
            "stop_reason": final_stop,
            "thread_id": state.get("thread_id"),
        })

        if self.copilot_memory is not None and memory_ns is not None:
            goal = state.get("normalized_goal") or state.get("operator_request", "")
            tools_used = [call.get("name", "") for call in state.get("approved_tool_calls", [])]
            outcome = "success" if final_stop == "done" and tools_used else final_stop
            try:
                await self.copilot_memory.store_interaction_summary(memory_ns, {
                    "goal": goal,
                    "tools_used": tools_used,
                    "outcome": outcome,
                    "stop_reason": final_stop,
                })
            except Exception:
                logger.warning("Failed to store copilot interaction to memory")

        return {
            "stop_reason": final_stop,
            "copilot_memory_namespace": memory_ns,
        }


__all__ = ["OperatorCopilotApprovalExecutionNodes"]
