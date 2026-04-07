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
from typing import Any

from typing import TypedDict

from ai_copilot.application.smart_engagement.ports import ApprovalPort
from ai_copilot.application.smart_engagement.state import (
    ApprovalRequest,
    ApprovalResult,
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


class DatabaseApprovalAdapter(ApprovalPort):
    """Database-backed approval adapter (production template).

    To use:
    1. Implement database client initialization
    2. Replace dict operations with database queries
    3. Add transaction support for consistency
    """

    def __init__(self, db_client: Any = None):
        """Initialize with database client.

        Args:
            db_client: Database connection (e.g., AsyncPg, SQLAlchemy)
        """
        self.db = db_client

    async def submit_for_approval(
        self,
        action: ProposedAction,
        risk_assessment: RiskAssessment,
        audit_trail: list[dict],
    ) -> str:
        """Submit action for approval to database."""
        raise NotImplementedError(
            "DatabaseApprovalAdapter requires a concrete approvals repository implementation"
        )

    async def get_approval_status(self, approval_id: str) -> ApprovalRecord:
        """Get approval status from database."""
        raise NotImplementedError(
            "DatabaseApprovalAdapter requires a concrete approvals repository implementation"
        )

    async def record_approval_decision(
        self,
        approval_id: str,
        approved: bool,
        approver_notes: str = "",
    ) -> ApprovalRecord:
        """Record decision in database."""
        raise NotImplementedError(
            "DatabaseApprovalAdapter requires a concrete approvals repository implementation"
        )
