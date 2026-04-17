"""Abstract ports for LangGraph operator copilot.

Ports define what external capabilities the graph needs without importing
concrete implementations. Adapters provide implementations of these ports.

Contract constants exported from this module:
- AUDIT_EVENT_TYPES              — canonical event_type values for AuditLogPort
- AUDIT_EVENT_SCHEMA             — per-event required/optional payload fields
- APPROVAL_PAYLOAD_REQUIRED_KEYS — minimum keys an approval_request must have
- LLMResponse                    — TypedDict shape for LLMGatewayPort responses

Contract helpers:
- validate_approval_payload()    — raises ValueError if payload is incomplete
- validate_audit_event_payload() — raises ValueError for unknown/malformed audit events
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypedDict

# ── Contract constants ─────────────────────────────────────────────────────────

class AuditEventSchema(TypedDict):
    """Allowed payload keys for one audit event type."""

    required: frozenset[str]
    optional: frozenset[str]


AUDIT_EVENT_SCHEMA: dict[str, AuditEventSchema] = {
    "operator_request": {
        "required": frozenset({"thread_id", "operator_request", "step"}),
        "optional": frozenset(),
    },
    "planner_decision": {
        "required": frozenset({"thread_id", "stage"}),
        "optional": frozenset({
            "normalized_goal",
            "blocked",
            "block_reason",
            "conversational",
            "mentions",
            "execution_plan",
            "proposed_tool_calls",
            "dropped_tool_calls",
            "runtime_context_keys",
            "copilot_memory_namespace",
            "context_available",
            "error",
        }),
    },
    "policy_gate": {
        "required": frozenset({
            "thread_id",
            "proposed_count",
            "blocked_names",
            "executable_count",
            "flags",
            "risk_assessment",
        }),
        "optional": frozenset(),
    },
    "approval_submitted": {
        "required": frozenset({"thread_id", "approval_request"}),
        "optional": frozenset(),
    },
    "approval_result": {
        "required": frozenset({"thread_id", "approval_result"}),
        "optional": frozenset({
            "edited_call_count",
            "sanitized_call_count",
            "dropped_tool_calls",
            "reason",
        }),
    },
    "tool_execution": {
        "required": frozenset({"thread_id", "call_id", "tool_name", "args", "result_keys"}),
        "optional": frozenset({"status", "error"}),
    },
    "execution_failure": {
        "required": frozenset({"thread_id", "call_id", "tool_name", "error"}),
        "optional": frozenset({"failure_kind", "status"}),
    },
    "review_finding": {
        "required": frozenset({"thread_id", "matched_intent", "warnings", "recommendation"}),
        "optional": frozenset({"parse_error"}),
    },
    "stop_reason": {
        "required": frozenset({"thread_id", "stop_reason"}),
        "optional": frozenset({"reason"}),
    },
}
"""Canonical operator-copilot audit schema.

`required` keys must always exist for that event_type.
`optional` keys are documented and allowed when relevant.
"""

AUDIT_EVENT_TYPES: frozenset[str] = frozenset(AUDIT_EVENT_SCHEMA.keys())
"""Canonical event_type values for AuditLogPort.log().

Callers MUST use one of these values.  Tests should reject unknown types.
"""

APPROVAL_PAYLOAD_REQUIRED_KEYS: frozenset[str] = frozenset({
    "operator_intent",
    "proposed_tool_calls",
    "tool_reasons",
    "risk_assessment",
    "options",
})
"""Minimum keys that every approval_request payload must contain.

ApprovalPort.submit_for_approval() and the interrupt() payload must both
include all of these keys so the operator has full context.
"""


class LLMResponse(TypedDict):
    """Expected shape returned by LLMGatewayPort.request_completion().

    LLMGatewayPort does NOT own business logic.  It returns raw completion
    results; callers are responsible for interpreting content as JSON.
    """

    content: str
    """Model response text. May be JSON string for structured-output nodes."""

    finish_reason: str
    """Why the model stopped: "stop" or "tool_calls"."""

    tool_calls: list[dict]
    """Tool calls requested by the model (empty list if finish_reason == "stop")."""


# ── Contract helpers ───────────────────────────────────────────────────────────


def validate_approval_payload(payload: dict) -> None:
    """Assert that an approval payload satisfies the port contract.

    Raises:
        ValueError: Listing every missing required key.

    Usage::

        validate_approval_payload(approval_request)   # before interrupt()
        validate_approval_payload(approval_request)   # in ApprovalPort.submit_for_approval
    """
    missing = APPROVAL_PAYLOAD_REQUIRED_KEYS - payload.keys()
    if missing:
        raise ValueError(
            f"Approval payload missing required keys: {sorted(missing)}. "
            f"Required: {sorted(APPROVAL_PAYLOAD_REQUIRED_KEYS)}"
        )


def validate_audit_event_payload(
    event_type: str,
    data: dict,
    *,
    allow_extra_fields: bool = False,
) -> None:
    """Assert that an audit event obeys the canonical schema.

    Args:
        event_type: Canonical audit event_type.
        data: Event payload dict.
        allow_extra_fields: If True, skip unknown-field checks.

    Raises:
        ValueError: For unknown event_type, missing required fields, or
            undocumented payload keys.
    """
    schema = AUDIT_EVENT_SCHEMA.get(event_type)
    if schema is None:
        raise ValueError(
            f"Unknown audit event_type: '{event_type}'. "
            f"Expected one of: {sorted(AUDIT_EVENT_TYPES)}"
        )
    if not isinstance(data, dict):
        raise ValueError(f"Audit event data for '{event_type}' must be dict, got {type(data).__name__}")

    required = schema["required"]
    optional = schema["optional"]

    missing = required - data.keys()
    if missing:
        raise ValueError(
            f"Audit event '{event_type}' missing required fields: {sorted(missing)}. "
            f"Required: {sorted(required)}"
        )

    if not allow_extra_fields:
        unknown = data.keys() - required - optional
        if unknown:
            raise ValueError(
                f"Audit event '{event_type}' has undocumented fields: {sorted(unknown)}. "
                f"Allowed: {sorted(required | optional)}"
            )


class LLMGatewayPort(ABC):
    """Port for LLM interaction - abstracts AI provider client."""

    @abstractmethod
    async def request_completion(
        self,
        messages: list[dict],
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
        provider_base_url: str | None = None,
    ) -> dict:
        """Request completion from LLM.

        Args:
            messages: Chat message history with role/content/tool_calls
            provider: AI provider name (openai, gemini, etc.)
            model: Model identifier (overrides provider default)
            api_key: API key (overrides env var)
            provider_base_url: Base URL override for compatible providers

        Returns:
            Dict with:
            - content: Response text
            - finish_reason: "stop" or "tool_calls"
            - tool_calls: List of tool call dicts if finish_reason == "tool_calls"
        """

    @abstractmethod
    def get_default_model(self, provider: str) -> str:
        """Get default model for a provider.

        Args:
            provider: Provider name

        Returns:
            Default model identifier
        """


class ToolExecutorPort(ABC):
    """Port for tool execution - abstracts tool invocation and access control."""

    @abstractmethod
    async def execute(self, tool_name: str, args: dict) -> dict:
        """Execute a tool by name with arguments.

        Implementation MUST enforce access control (read-only whitelist).

        Args:
            tool_name: Tool identifier
            args: Tool arguments dict

        Returns:
            Dict with tool result data or error

        Raises:
            ValueError: If tool not found or access denied
            Exception: If execution fails
        """

    @abstractmethod
    def get_schemas(self) -> list[dict]:
        """Get tool schema definitions for LLM.

        Returns:
            List of tool schema dicts (OpenAI format)
        """


class CheckpointFactoryPort(ABC):
    """Port for state checkpointing - abstracts persistence mechanism."""

    @abstractmethod
    def create_checkpointer(self) -> Any:
        """Create a checkpointer instance for graph state persistence.

        Returns:
            LangGraph-compatible checkpointer
        """


class ApprovalPort(ABC):
    """Port for operator approval - abstracts interrupt/resume mechanism.

    Receives a self-contained payload with tool, arguments, reasoning, and
    risk level. Returns operator decision. Does NOT own policy classification.
    """

    @abstractmethod
    async def submit_for_approval(self, approval_request: dict) -> str:
        """Submit proposed tool calls for operator approval.

        Args:
            approval_request: Self-contained dict with:
                - operator_intent: str — original request from operator
                - proposed_tool_calls: list[dict] — [{id, name, arguments}, ...]
                - tool_reasons: dict[str, str] — {call_id: reason_string}
                - risk_assessment: dict — {level, reasons, blocking}
                - options: list[str] — always ["approve", "reject", "edit"]

        Returns:
            One of: "approved", "rejected", "edited"

        Note:
            "edited" means operator has modified arguments; updated
            approved_tool_calls must be read from state after resume.
        """


class CopilotMemoryPort(ABC):
    """Port for cross-thread copilot memory.

    Stores and retrieves interaction summaries so the planner can
    provide continuity across sessions — avoid repeating failed actions,
    reference prior results, and adapt to operator patterns.

    Port Contract:
    - Namespace isolation per operator context (e.g. operator_id or "default")
    - Recent interactions returned newest-first
    - store_interaction_summary is fire-and-forget (must not block workflow)
    """

    @abstractmethod
    async def recall_recent_interactions(
        self,
        namespace: str,
        limit: int = 5,
    ) -> list[dict]:
        """Recall recent copilot interaction summaries.

        Args:
            namespace: Operator or session namespace
            limit: Max records to return (newest first)

        Returns:
            List of interaction summary dicts with at least:
            - goal: normalized goal string
            - tools_used: list of tool names
            - outcome: success/partial/failed/blocked/rejected
            - timestamp: float
        """

    @abstractmethod
    async def store_interaction_summary(
        self,
        namespace: str,
        summary: dict,
    ) -> None:
        """Store a copilot interaction summary for future recall.

        Args:
            namespace: Operator or session namespace
            summary: Dict with goal, tools_used, outcome, timestamp, etc.
        """


class AuditLogPort(ABC):
    """Port for audit logging - records every decision, gate, and execution.

    LLMGatewayPort does not own this. Policy gate and approval are the primary
    callers. All decision points must log before acting.
    """

    @abstractmethod
    async def log(self, event_type: str, data: dict) -> None:
        """Record an audit event.

        Args:
            event_type: One of the canonical event types:
                - "operator_request"  — raw intent received
                - "planner_decision"  — LLM proposed tool calls
                - "policy_gate"       — tool policy classification result
                - "approval_submitted" — payload sent to approval port
                - "approval_result"   — operator decision received
                - "tool_execution"    — tool executed with result
                - "execution_failure" — tool raised or returned an error payload
                - "review_finding"    — reviewer finding before final response
                - "stop_reason"       — why the run ended
            data: Event-specific payload (all fields must be JSON-serialisable)
        """
