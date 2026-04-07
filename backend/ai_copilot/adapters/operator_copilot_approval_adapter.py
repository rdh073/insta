"""Approval adapter for operator copilot — implements application.ports.ApprovalPort.

NOTE on design: The graph's request_approval_if_needed_node uses LangGraph's
native interrupt() mechanism for synchronous approval gating. ApprovalPort
is injected into OperatorCopilotNodes but is NOT the primary approval path
in the current implementation — interrupt() is.

This adapter exists to:
1. Satisfy the port contract (required by OperatorCopilotNodes constructor).
2. Provide a store for pending approvals that API or dashboard code can poll.
3. Serve as the extension point when migrating to async external approval
   (e.g., Slack bot, database queue, webhook service).

Does NOT own approval policy decisions. Those live in the graph nodes.
"""

from __future__ import annotations

import time
import uuid

from ai_copilot.application.ports import ApprovalPort


class InMemoryOperatorApprovalAdapter(ApprovalPort):
    """In-memory approval store for operator copilot.

    Stores submitted approval requests keyed by thread_id so dashboard or
    polling endpoints can inspect pending approvals without a database.

    Thread-safe for single-process use (Python GIL).
    For multi-process deployments, replace with a database-backed adapter.
    """

    def __init__(self) -> None:
        # {thread_id: approval_record}
        self._pending: dict[str, dict] = {}
        # history of all submitted requests (for audit/debugging)
        self._history: list[dict] = []

    async def submit_for_approval(self, approval_request: dict) -> str:
        """Store the approval request and return a stub decision.

        In the operator copilot graph, the actual operator decision comes via
        LangGraph interrupt/resume, NOT via this method's return value.
        This method is called for side-effects (persistence) only.

        Args:
            approval_request: Self-contained approval payload from the graph node.
                Contains: operator_intent, proposed_tool_calls, tool_reasons,
                risk_assessment, options.

        Returns:
            "pending" — the real decision arrives via graph resume.
        """
        record = {
            "approval_id": str(uuid.uuid4()),
            "submitted_at": time.time(),
            "status": "pending",
            "approval_request": approval_request,
        }

        thread_id = _extract_thread_id(approval_request)
        if thread_id:
            self._pending[thread_id] = record

        self._history.append(record)

        return "pending"

    # ── Inspection helpers (for API/dashboard) ─────────────────────────────────

    def get_pending(self, thread_id: str) -> dict | None:
        """Return the pending approval record for a thread, or None."""
        return self._pending.get(thread_id)

    def get_all_pending(self) -> list[dict]:
        """Return all pending approval records."""
        return [r for r in self._pending.values() if r["status"] == "pending"]

    def mark_resolved(self, thread_id: str, decision: str) -> None:
        """Mark a pending approval as resolved (called after resume completes).

        Args:
            thread_id: Thread whose approval was resolved.
            decision: The operator's decision ("approved", "rejected", "edited").
        """
        record = self._pending.get(thread_id)
        if record:
            record["status"] = decision
            record["resolved_at"] = time.time()

    def clear(self) -> None:
        """Clear all records (for testing)."""
        self._pending.clear()
        self._history.clear()


def _extract_thread_id(approval_request: dict) -> str | None:
    """Best-effort extraction of thread_id from the approval payload."""
    if "thread_id" in approval_request:
        return approval_request["thread_id"]
    # Sometimes nested under risk_assessment or other sub-dicts
    for value in approval_request.values():
        if isinstance(value, dict) and "thread_id" in value:
            return value["thread_id"]
    return None
