"""Fake port implementations for operator copilot — for testing without real services.

These fakes implement the five ports in ai_copilot.application.ports and
are the canonical way to test the operator copilot graph without needing
a real LLM, tool registry, approval service, or database.

Contract compliance:
- Every fake implements the abstract base class (import will fail otherwise).
- FakeLLMGateway returns responses in the sequence provided, then falls back
  to a default. Callers can inspect call_log for assertions.
- FakeToolExecutor captures (name, args) pairs; raises ValueError for tools
  not in its results map (same behaviour as PolicyAwareToolExecutor).
- FakeApprovalPort accepts a configurable decision; captures submitted payload.
- FakeAuditLogPort stores all events; supports filtering by event_type.
- FakeCheckpointFactory wraps MemorySaver (no faking needed for in-memory).

Usage::

    from ai_copilot.adapters.fake_ports_operator_copilot import (
        FakeLLMGateway, FakeToolExecutor, FakeApprovalPort,
        FakeAuditLogPort, FakeCheckpointFactory,
    )
    import json

    llm = FakeLLMGateway(responses=[
        json.dumps({"normalized_goal": "list posts", "blocked": False, "block_reason": None}),
        json.dumps({"execution_plan": [], "proposed_tool_calls": [
            {"id": "c1", "name": "get_posts", "arguments": {"limit": 5}}
        ]}),
        json.dumps({"matched_intent": True, "warnings": [], "recommendation": "proceed_to_summary"}),
        "Here are your last 5 posts.",   # plain text for summarize node
    ])
    executor = FakeToolExecutor({"get_posts": {"posts": []}})
    approval = FakeApprovalPort(decision="approved")
    audit = FakeAuditLogPort()
    checkpoints = FakeCheckpointFactory()
"""

from __future__ import annotations

import json

from ai_copilot.application.ports import (
    LLMGatewayPort,
    ToolExecutorPort,
    ApprovalPort,
    AuditLogPort,
    CheckpointFactoryPort,
    validate_audit_event_payload,
)


# ── FakeLLMGateway ─────────────────────────────────────────────────────────────


class FakeLLMGateway(LLMGatewayPort):
    """Deterministic LLM stub for operator copilot tests.

    Returns responses in sequence. After the sequence is exhausted,
    returns the default_response for every subsequent call.

    Each response can be:
    - A plain string (used as content; finish_reason = "stop")
    - A dict matching LLMResponse shape directly

    Args:
        responses: Sequence of response contents (strings) or full response dicts.
        default_response: Returned once the sequence runs out.
        default_model: Returned by get_default_model().
    """

    def __init__(
        self,
        responses: list[str | dict] | None = None,
        default_response: str = "{}",
        default_model: str = "gpt-4o-mini",
    ) -> None:
        self._responses: list[str | dict] = list(responses or [])
        self._default_response = default_response
        self._default_model = default_model

        # Introspection helpers
        self.call_log: list[dict] = []
        """Each entry: {"messages": [...], "kwargs": {...}, "response": {...}}"""

    async def request_completion(
        self,
        messages: list[dict],
        provider: str = "openai",
        model: str | None = None,
        api_key: str | None = None,
        provider_base_url: str | None = None,
    ) -> dict:
        """Return the next response in sequence, or the default."""
        if self._responses:
            raw = self._responses.pop(0)
        else:
            raw = self._default_response

        if isinstance(raw, dict):
            response = raw
        else:
            response = {
                "content": raw,
                "finish_reason": "stop",
                "tool_calls": [],
            }

        self.call_log.append({
            "messages": messages,
            "kwargs": {"provider": provider, "model": model},
            "response": response,
        })

        return response

    def get_default_model(self, provider: str) -> str:
        return self._default_model

    # ── Helpers ────────────────────────────────────────────────────────────────

    @property
    def call_count(self) -> int:
        """Number of times request_completion was called."""
        return len(self.call_log)

    def last_messages(self) -> list[dict]:
        """Messages from the most recent call (empty list if never called)."""
        if not self.call_log:
            return []
        return self.call_log[-1]["messages"]

    def reset(self) -> None:
        """Clear call log and remaining responses."""
        self.call_log.clear()


# ── FakeToolExecutor ───────────────────────────────────────────────────────────


class FakeToolExecutor(ToolExecutorPort):
    """Deterministic tool executor stub for operator copilot tests.

    Args:
        results: Mapping of tool_name → result dict.
            Missing keys raise ValueError (mirrors PolicyAwareToolExecutor).
        schemas: Optional list of tool schema dicts returned by get_schemas().
    """

    def __init__(
        self,
        results: dict[str, dict] | None = None,
        schemas: list[dict] | None = None,
    ) -> None:
        self._results: dict[str, dict] = results or {}
        self._schemas: list[dict] = schemas or [
            {"function": {"name": name, "description": f"Fake {name}"}}
            for name in (results or {}).keys()
        ]

        # Introspection helpers
        self.calls: list[tuple[str, dict]] = []
        """List of (tool_name, args) in execution order."""

    async def execute(self, tool_name: str, args: dict) -> dict:
        self.calls.append((tool_name, args))
        if tool_name not in self._results:
            raise ValueError(f"FakeToolExecutor: tool '{tool_name}' not in results map")
        return self._results[tool_name]

    def get_schemas(self) -> list[dict]:
        return list(self._schemas)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def was_called_with(self, tool_name: str) -> bool:
        """True if execute() was called for tool_name at least once."""
        return any(name == tool_name for name, _ in self.calls)

    def reset(self) -> None:
        """Clear call log."""
        self.calls.clear()


# ── FakeApprovalPort ───────────────────────────────────────────────────────────


class FakeApprovalPort(ApprovalPort):
    """Deterministic approval port stub for operator copilot tests.

    NOTE: In the current operator copilot graph, approval happens via
    LangGraph interrupt() — not via submit_for_approval(). This fake
    exists to satisfy the constructor and to capture payloads in tests
    that call the port directly.

    Args:
        decision: Value returned by submit_for_approval().
                  Defaults to "approved".
    """

    def __init__(self, decision: str = "approved") -> None:
        self.decision = decision
        self.submitted_payloads: list[dict] = []
        """Payloads passed to submit_for_approval() in call order."""

    async def submit_for_approval(self, approval_request: dict) -> str:
        self.submitted_payloads.append(approval_request)
        return self.decision

    # ── Helpers ────────────────────────────────────────────────────────────────

    @property
    def call_count(self) -> int:
        return len(self.submitted_payloads)

    def last_payload(self) -> dict | None:
        """Most recent submitted payload, or None."""
        return self.submitted_payloads[-1] if self.submitted_payloads else None

    def reset(self) -> None:
        self.submitted_payloads.clear()


# ── FakeAuditLogPort ───────────────────────────────────────────────────────────


class FakeAuditLogPort(AuditLogPort):
    """Audit log port stub that captures events for assertion in tests.

    Captures every log() call with its event_type and data. In strict mode it
    validates the full canonical schema (event_type + payload fields).

    Args:
        strict: If True (default), raises ValueError for unknown event_types.
                Set to False to accept any event_type in legacy tests.
    """

    def __init__(self, strict: bool = True) -> None:
        self._strict = strict
        self.events: list[dict] = []
        """All logged events in order: [{"event_type": ..., "data": ...}, ...]"""

    async def log(self, event_type: str, data: dict) -> None:
        if self._strict:
            validate_audit_event_payload(event_type, data)
        self.events.append({"event_type": event_type, "data": data})

    # ── Helpers ────────────────────────────────────────────────────────────────

    def get_events(self, event_type: str | None = None) -> list[dict]:
        """Return events filtered by event_type (all events if None)."""
        if event_type is None:
            return list(self.events)
        return [e for e in self.events if e["event_type"] == event_type]

    def event_types(self) -> list[str]:
        """Return event_type for each event in order."""
        return [e["event_type"] for e in self.events]

    def has_event(self, event_type: str) -> bool:
        """True if at least one event of this type was logged."""
        return any(e["event_type"] == event_type for e in self.events)

    @property
    def call_count(self) -> int:
        return len(self.events)

    def reset(self) -> None:
        self.events.clear()


# ── FakeCheckpointFactory ──────────────────────────────────────────────────────


class FakeCheckpointFactory(CheckpointFactoryPort):
    """Checkpoint factory stub that returns a MemorySaver.

    MemorySaver is already an in-memory implementation so no faking is
    needed for unit/integration tests — this class exists to satisfy the
    port interface and to allow tests to control the checkpointer instance.

    Args:
        checkpointer: Optional pre-built checkpointer to return.
                      If None, a new MemorySaver is created on first call.
    """

    def __init__(self, checkpointer=None) -> None:
        self._checkpointer = checkpointer
        self._create_count = 0

    def create_checkpointer(self):
        """Return the configured checkpointer, or a fresh MemorySaver."""
        self._create_count += 1
        if self._checkpointer is not None:
            return self._checkpointer
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()

    @property
    def create_count(self) -> int:
        """Number of times create_checkpointer() was called."""
        return self._create_count
