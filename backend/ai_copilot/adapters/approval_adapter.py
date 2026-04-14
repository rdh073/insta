"""Approval adapter - implements ApprovalPort for approval gate.

OWNERSHIP: Concrete implementation of ApprovalPort interface.
Handle approval submission, status tracking, decision recording.

Bridges to external services (database, approval queue, webhooks).
Does not own approval logic - that's in graph's approval_gate node.

In-memory implementation for development. For production:
- Connect to database for persistence
- Integrate with message queue for async notification
- Add webhook callbacks to approval service
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Protocol, TypedDict

from ai_copilot.application.smart_engagement.ports import ApprovalPort
from ai_copilot.application.smart_engagement.state import (
    ProposedAction,
    RiskAssessment,
)


class ApprovalRecord(TypedDict):
    """Internal storage record for approval tracking."""

    approval_id: str
    status: str
    """pending, approved, rejected"""

    requested_at: float
    approved_at: float | None
    approver_notes: str
    action_id: str


class InMemoryApprovalAdapter(ApprovalPort):
    """In-memory approval storage (for development).

    Production should use database/queue backend.
    """

    def __init__(self):
        """Initialize with empty approval store."""
        self._approvals: dict[str, ApprovalRecord] = {}
        self._lock = asyncio.Lock()

    async def submit_for_approval(
        self,
        action: ProposedAction,
        risk_assessment: RiskAssessment,
        audit_trail: list[dict],
    ) -> str:
        """Submit action for human approval.

        Args:
            action: Proposed action
            risk_assessment: Risk evaluation
            audit_trail: Decision history

        Returns:
            Approval request ID
        """
        approval_id = str(uuid.uuid4())

        record: ApprovalRecord = {
            "approval_id": approval_id,
            "status": "pending",
            "requested_at": time.time(),
            "approved_at": None,
            "approver_notes": "",
            "action_id": f"{action['action_type']}:{action['target_id']}",
        }

        async with self._lock:
            self._approvals[approval_id] = record

        return approval_id

    async def get_approval_status(self, approval_id: str) -> ApprovalRecord:
        """Check approval status.

        Args:
            approval_id: Approval request ID

        Returns:
            ApprovalRecord with current status

        Raises:
            ValueError: If approval_id not found
        """
        if approval_id not in self._approvals:
            raise ValueError(f"Approval not found: {approval_id}")

        return self._approvals[approval_id]

    async def record_approval_decision(
        self,
        approval_id: str,
        approved: bool,
        approver_notes: str = "",
    ) -> ApprovalRecord:
        """Record human decision on approval.

        Args:
            approval_id: Approval ID
            approved: True if approved
            approver_notes: Decision notes

        Returns:
            Updated ApprovalRecord
        """
        async with self._lock:
            if approval_id not in self._approvals:
                raise ValueError(f"Approval not found: {approval_id}")

            record = self._approvals[approval_id]
            record["status"] = "approved" if approved else "rejected"
            record["approved_at"] = time.time()
            record["approver_notes"] = approver_notes

            return record

    def get_all_pending(self) -> list[ApprovalRecord]:
        """Get all pending approvals (for UI/dashboard).

        Returns:
            List of pending ApprovalRecords
        """
        return [
            r for r in self._approvals.values() if r["status"] == "pending"
        ]

    def clear(self):
        """Clear all approvals (for testing)."""
        self._approvals.clear()


class ApprovalRepository(Protocol):
    """Persistence contract used by DatabaseApprovalAdapter."""

    def create(self, record: dict[str, Any]) -> None:
        """Persist a new approval record."""

    def get(self, approval_id: str) -> dict[str, Any] | None:
        """Fetch a persisted approval record by id."""

    def set_decision(
        self,
        approval_id: str,
        *,
        status: str,
        approved_at: float,
        approver_notes: str,
    ) -> dict[str, Any] | None:
        """Update approval decision fields and return the updated record."""


def _normalize_action_id(action: ProposedAction | dict[str, Any] | None) -> str:
    if not isinstance(action, dict):
        return "unknown:unknown"
    action_type = str(action.get("action_type", "unknown"))
    target_id = str(action.get("target_id", "unknown"))
    return f"{action_type}:{target_id}"


def _as_approval_record(record: dict[str, Any]) -> ApprovalRecord:
    """Map repository data to the ApprovalRecord contract."""
    return ApprovalRecord(
        approval_id=str(record.get("approval_id", "")),
        status=str(record.get("status", "pending")),
        requested_at=float(record.get("requested_at", 0.0)),
        approved_at=(
            float(record["approved_at"])
            if record.get("approved_at") is not None
            else None
        ),
        approver_notes=str(record.get("approver_notes", "")),
        action_id=str(record.get("action_id", "")),
    )


class DatabaseApprovalAdapter(ApprovalPort):
    """Database-backed approval adapter."""

    def __init__(self, repository: ApprovalRepository):
        self._repository = repository

    async def submit_for_approval(
        self,
        action: ProposedAction,
        risk_assessment: RiskAssessment,
        audit_trail: list[dict],
    ) -> str:
        """Submit action for approval and persist to repository."""
        approval_id = str(uuid.uuid4())
        record = {
            "approval_id": approval_id,
            "status": "pending",
            "requested_at": time.time(),
            "approved_at": None,
            "approver_notes": "",
            "action_id": _normalize_action_id(action),
            "action_payload": dict(action or {}),
            "risk_payload": dict(risk_assessment or {}),
            "audit_payload": list(audit_trail or []),
        }
        try:
            self._repository.create(record)
        except Exception as exc:
            raise RuntimeError("Failed to persist approval request") from exc
        return approval_id

    async def get_approval_status(self, approval_id: str) -> ApprovalRecord:
        """Get approval status from repository."""
        try:
            stored = self._repository.get(approval_id)
        except Exception as exc:
            raise RuntimeError("Failed to load approval status") from exc
        if stored is None:
            raise ValueError(f"Approval not found: {approval_id}")
        return _as_approval_record(stored)

    async def record_approval_decision(
        self,
        approval_id: str,
        approved: bool,
        approver_notes: str = "",
    ) -> ApprovalRecord:
        """Record decision in repository."""
        status = "approved" if approved else "rejected"
        approved_at = time.time()
        try:
            updated = self._repository.set_decision(
                approval_id,
                status=status,
                approved_at=approved_at,
                approver_notes=approver_notes,
            )
        except Exception as exc:
            raise RuntimeError("Failed to persist approval decision") from exc
        if updated is None:
            raise ValueError(f"Approval not found: {approval_id}")
        return _as_approval_record(updated)
