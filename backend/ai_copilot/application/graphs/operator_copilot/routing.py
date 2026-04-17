"""Routing functions for operator copilot graph edges."""

from __future__ import annotations

import json

from ai_copilot.application.operator_copilot_policy import ToolPolicyRegistry
from ai_copilot.application.state import OperatorCopilotState

_REVIEW_SKIP_MAX_PAYLOAD_BYTES = 4096


def route_after_classify(state: OperatorCopilotState) -> str:
    """After classify_goal: llm_failed -> finish, blocked/conversational -> summarize_result, else -> plan_actions."""
    stop_reason = state.get("stop_reason")
    if stop_reason == "llm_failed":
        return "finish"
    if stop_reason in ("blocked", "responded"):
        return "summarize_result"
    return "plan_actions"


def route_after_plan(state: OperatorCopilotState) -> str:
    """After plan_actions: llm_failed -> finish, no valid calls -> summarize_result, else -> review_tool_policy."""
    if state.get("stop_reason") == "llm_failed":
        return "finish"
    proposed = state.get("proposed_tool_calls", [])
    if not proposed:
        return "summarize_result"
    return "review_tool_policy"


def route_after_policy(state: OperatorCopilotState, policy_registry: ToolPolicyRegistry) -> str:
    """After review_tool_policy route to execute, approval gate, or summary."""
    proposed = state.get("proposed_tool_calls", [])
    if not proposed:
        return "summarize_result"
    if policy_registry.all_read_only(proposed):
        return "execute_tools"
    if state.get("approval_attempted"):
        return "execute_tools"
    return "request_approval_if_needed"


def route_after_approval(state: OperatorCopilotState) -> str:
    """After approval: approved -> execute, edited -> revalidate, else summarize."""
    result = state.get("approval_result")
    if result == "approved":
        return "execute_tools"
    if result == "edited":
        return "review_tool_policy"
    return "summarize_result"


def route_after_execute_tools(state: OperatorCopilotState, policy_registry: ToolPolicyRegistry) -> str:
    """After execute_tools: skip review_results for small read-only successful runs.

    Routes to summarize_result directly when all three conditions hold:
    1. Every executed tool was classified READ_ONLY (no WRITE_SENSITIVE ran).
    2. No tool result contains a truthy error field.
    3. Total tool_results payload is below _REVIEW_SKIP_MAX_PAYLOAD_BYTES (4 KB).

    Any deviation routes to review_results for the full LLM-backed review.
    """
    approved_calls = state.get("approved_tool_calls") or []
    tool_policy_flags = state.get("tool_policy_flags") or {}
    tool_results = state.get("tool_results") or {}

    # Conservative fallback: if calls exist but policy data is absent, review.
    if approved_calls and not tool_policy_flags:
        return "review_results"

    # Condition 1: all executed tool calls must be READ_ONLY.
    for call in approved_calls:
        call_id = call.get("id", "")
        flag = tool_policy_flags.get(call_id, "write_sensitive")
        if flag != "read_only":
            return "review_results"

    # Condition 2: no tool result contains an error.
    for result in tool_results.values():
        if isinstance(result, dict) and result.get("error"):
            return "review_results"

    # Condition 3: total payload must be below the threshold.
    try:
        payload_bytes = len(json.dumps(tool_results).encode("utf-8"))
    except Exception:
        return "review_results"
    if payload_bytes >= _REVIEW_SKIP_MAX_PAYLOAD_BYTES:
        return "review_results"

    return "summarize_result"
