"""Routing functions for operator copilot graph edges."""

from __future__ import annotations

from ai_copilot.application.operator_copilot_policy import ToolPolicyRegistry
from ai_copilot.application.state import OperatorCopilotState


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
