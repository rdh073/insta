"""LangGraph state definition for operator copilot.

Typed state container shared by read-only and full operator copilot workflows.
Independent of any framework or external dependency.

Contract constants (used by graph nodes and tests for validation):
- VALID_APPROVAL_RESULTS  — allowed values for approval_result field
- VALID_STOP_REASONS      — allowed values for stop_reason field

State factory:
- make_initial_state()    — canonical way to initialise a new run's state
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal, TypedDict

# Import from langgraph
from langgraph.graph import add_messages

# ── Contract constants ─────────────────────────────────────────────────────────

VALID_APPROVAL_RESULTS: frozenset[str] = frozenset({
    "approved",
    "rejected",
    "edited",
    "timeout",
})
"""Allowed values for the approval_result state field.

Nodes that set approval_result MUST use one of these values.
"""

VALID_STOP_REASONS: frozenset[str] = frozenset({
    "done",
    "max_steps",
    "rejected",
    "blocked",
    "error",
    "responded",   # legacy read-only copilot value
})
"""Allowed values for the stop_reason state field.

- done       — run completed successfully
- max_steps  — loop bound reached
- rejected   — operator rejected a proposed action
- blocked    — intent classified as blocked by policy
- error      — unrecoverable error in a node
- responded  — legacy value from read-only copilot (backward compat)
"""


class OperatorCopilotState(TypedDict):
    """Typed state for operator copilot workflow.

    Legacy fields (read-only copilot):
    - messages: Conversation history with role, content, optional tool_calls
    - current_tool_calls: In-flight tool calls awaiting execution
    - tool_results: Results from executed tools
    - stop_reason: Why workflow stopped (done, max_steps, rejected, error)
    - step_count: Current iteration number

    Extended fields (full operator copilot, todo-3 spec):
    - thread_id: Durable execution id for checkpoint and resume
    - operator_request: Raw intent from operator
    - normalized_goal: Cleaned intent for policy evaluation
    - execution_plan: Explainable list of planned steps
    - proposed_tool_calls: Tool calls proposed by LLM
    - approved_tool_calls: Tool calls that passed policy or approval
    - tool_policy_flags: Classification results per tool call id
    - risk_assessment: Risk reasoning (not just a number)
    - approval_request: Payload for operator when sensitive action is needed
    - approval_result: "approved", "rejected", "edited", or "timeout"
    - review_findings: Reviewer observations before final response
    - final_response: Final answer to operator
    """

    # ── Legacy fields (read-only copilot) ─────────────────────────────────────

    messages: Annotated[list[dict], add_messages]
    """Message history: [{role, content, [tool_calls]}, ...]

    Uses LangGraph's add_messages reducer to prevent duplication.
    """

    current_tool_calls: dict[str, dict] | None
    """In-flight tool calls: {call_id: {function, arguments}}"""

    tool_results: dict[str, dict]
    """Completed tool results: {call_id: result_dict}"""

    stop_reason: str | None
    """Workflow termination reason: done, max_steps, rejected, error"""

    step_count: int
    """Iteration counter (incremented each loop)"""

    # ── Extended fields (full operator copilot) ───────────────────────────────

    thread_id: str
    """Durable execution id used for checkpoint and resume."""

    provider: str | None
    """AI provider override for this thread (e.g. openai, gemini, deepseek)."""

    model: str | None
    """Model override for this thread."""

    api_key: str | None
    """API key override for this thread."""

    provider_base_url: str | None
    """Provider base URL override for this thread."""

    operator_request: str
    """Raw intent string from operator as entered."""

    normalized_goal: str | None
    """Intent cleaned and rewritten for policy evaluation by classify_goal."""

    mentions: list[str]
    """@usernames extracted from the operator request by classify_goal."""

    execution_plan: list[dict] | None
    """Explainable action plan: [{step, tool, reason, risk_level}, ...]"""

    proposed_tool_calls: list[dict]
    """Tool calls proposed by the planner LLM: [{id, name, arguments}, ...]"""

    approved_tool_calls: list[dict]
    """Tool calls that cleared policy gate or operator approval."""

    tool_policy_flags: dict[str, str]
    """Policy classification per tool call id: {call_id: "read_only"|"write_sensitive"|"blocked"}"""

    risk_assessment: dict | None
    """Risk reasoning: {level: "low"|"medium"|"high", reasons: [...], blocking: bool}"""

    approval_request: dict | None
    """Approval payload for operator: {operator_intent, proposed_tool_calls, tool_reasons,
    risk_assessment, options: ["approve","reject","edit"]}"""

    approval_result: str | None
    """Operator decision: "approved", "rejected", "edited", or "timeout"."""

    review_findings: dict | None
    """Reviewer observations: {matched_intent: bool, warnings: [...], recommendation: str}"""

    final_response: str | None
    """Final answer text to return to the operator."""

    approval_attempted: bool
    """True after request_approval_if_needed_node has run once this session.

    Loop-bound invariant: approval is requested at most once per run.
    If the operator edits calls and re-validation still sees write_sensitive
    tools, the graph routes to execute_tools directly (not back to approval).
    Set to True by request_approval_if_needed_node; reset to False by
    ingest_request_node at the start of each new run.
    """


# ── State factory ──────────────────────────────────────────────────────────────


def make_initial_state(
    operator_request: str,
    thread_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    provider_base_url: str | None = None,
) -> OperatorCopilotState:
    """Create a valid initial state for a new operator copilot run.

    This is the canonical initialisation point — all fields are set to
    their zero values so nodes never encounter missing keys.

    Args:
        operator_request: Raw natural language request from the operator.
        thread_id: Stable session id for checkpointing/resume.
                   Auto-generated (UUID4) if not provided.

    Returns:
        Fully-initialised OperatorCopilotState dict.

    Example::

        state = make_initial_state("Show my last 5 posts", thread_id="t-123")
        result = await graph.ainvoke(state, config={"configurable": {"thread_id": "t-123"}})
    """
    return OperatorCopilotState(
        # ── Legacy fields ──────────────────────────────────────────
        messages=[],
        current_tool_calls=None,
        tool_results={},
        stop_reason=None,
        step_count=0,
        # ── Extended fields ────────────────────────────────────────
        thread_id=thread_id or str(uuid.uuid4()),
        provider=provider,
        model=model,
        api_key=api_key,
        provider_base_url=provider_base_url,
        operator_request=operator_request,
        normalized_goal=None,
        mentions=[],
        execution_plan=None,
        proposed_tool_calls=[],
        approved_tool_calls=[],
        tool_policy_flags={},
        risk_assessment=None,
        approval_request=None,
        approval_result=None,
        review_findings=None,
        final_response=None,
        approval_attempted=False,
    )
