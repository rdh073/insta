"""SQL repositories for smart engagement approvals and audit events."""

from __future__ import annotations

from functools import wraps
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from .errors import PersistenceInfrastructureError
from .failure_catalog import build_persistence_failure_message
from .sql_store import (
    SmartEngagementApprovalRow,
    SmartEngagementAuditEventRow,
    SqlitePersistenceStore,
)


def _wrap_sql_error(func):
    """Translate SQLAlchemy errors into app-owned infrastructure failures."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SQLAlchemyError as exc:
            raise PersistenceInfrastructureError(
                build_persistence_failure_message(func.__name__)
            ) from exc

    return wrapper


class SqlSmartEngagementApprovalRepository:
    """SQL-backed repository for approval records."""

    def __init__(self, store: SqlitePersistenceStore):
        self.store = store

    @staticmethod
    def _to_record(row: SmartEngagementApprovalRow) -> dict[str, Any]:
        return {
            "approval_id": row.approval_id,
            "status": row.status,
            "requested_at": row.requested_at,
            "approved_at": row.approved_at,
            "approver_notes": row.approver_notes,
            "action_id": row.action_id,
            "action_payload": dict(row.action_payload or {}),
            "risk_payload": dict(row.risk_payload or {}),
            "audit_payload": list(row.audit_payload or []),
        }

    @_wrap_sql_error
    def create(self, record: dict[str, Any]) -> None:
        with self.store.session_scope() as session:
            row = SmartEngagementApprovalRow(
                approval_id=str(record["approval_id"]),
                status=str(record.get("status", "pending")),
                requested_at=float(record.get("requested_at", 0.0)),
                approved_at=(
                    float(record["approved_at"])
                    if record.get("approved_at") is not None
                    else None
                ),
                approver_notes=str(record.get("approver_notes", "")),
                action_id=str(record.get("action_id", "")),
                action_payload=dict(record.get("action_payload") or {}),
                risk_payload=dict(record.get("risk_payload") or {}),
                audit_payload=list(record.get("audit_payload") or []),
            )
            session.add(row)
            if self.store.get_active_session() is None:
                session.commit()

    @_wrap_sql_error
    def get(self, approval_id: str) -> dict[str, Any] | None:
        with self.store.session_scope() as session:
            row = session.get(SmartEngagementApprovalRow, approval_id)
            if row is None:
                return None
            return self._to_record(row)

    @_wrap_sql_error
    def set_decision(
        self,
        approval_id: str,
        *,
        status: str,
        approved_at: float,
        approver_notes: str,
    ) -> dict[str, Any] | None:
        with self.store.session_scope() as session:
            row = session.get(SmartEngagementApprovalRow, approval_id)
            if row is None:
                return None
            row.status = status
            row.approved_at = approved_at
            row.approver_notes = approver_notes
            if self.store.get_active_session() is None:
                session.commit()
            return self._to_record(row)


class SqlSmartEngagementAuditLogRepository:
    """SQL-backed repository for audit event records."""

    def __init__(self, store: SqlitePersistenceStore):
        self.store = store

    @staticmethod
    def _to_record(row: SmartEngagementAuditEventRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "thread_id": row.thread_id,
            "event_type": row.event_type,
            "node_name": row.node_name,
            "event_data": dict(row.event_data or {}),
            "timestamp": row.timestamp,
        }

    @_wrap_sql_error
    def append(self, record: dict[str, Any]) -> None:
        with self.store.session_scope() as session:
            row = SmartEngagementAuditEventRow(
                thread_id=str(record.get("thread_id", "default")),
                event_type=str(record.get("event_type", "")),
                node_name=str(record.get("node_name", "")),
                event_data=dict(record.get("event_data") or {}),
                timestamp=float(record.get("timestamp", 0.0)),
            )
            session.add(row)
            if self.store.get_active_session() is None:
                session.commit()

    @_wrap_sql_error
    def list_by_thread(self, thread_id: str) -> list[dict[str, Any]]:
        with self.store.session_scope() as session:
            rows = (
                session.query(SmartEngagementAuditEventRow)
                .filter(SmartEngagementAuditEventRow.thread_id == thread_id)
                .order_by(
                    SmartEngagementAuditEventRow.timestamp.asc(),
                    SmartEngagementAuditEventRow.id.asc(),
                )
                .all()
            )
            return [self._to_record(row) for row in rows]
