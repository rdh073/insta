"""Audit log adapter - implements AuditLogPort for explicit event logging.

In-memory implementation for development. For production:
- Connect to database for persistence
- Integrate with logging service (Cloudwatch, ELK, etc.)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Protocol

from ai_copilot.application.smart_engagement.ports import AuditLogPort

logger = logging.getLogger(__name__)
from ai_copilot.application.smart_engagement.state import AuditEvent


def _normalize_event(event: AuditEvent) -> tuple[AuditEvent, str]:
    """Normalize event payload and return (normalized_event, thread_id)."""
    raw_event_data = event.get("event_data") or {}
    event_data = raw_event_data if isinstance(raw_event_data, dict) else {}

    normalized_data = dict(event_data)
    thread_id = normalized_data.get("thread_id") or event.get("thread_id") or "default"
    normalized_data.setdefault("thread_id", thread_id)

    normalized_event = AuditEvent(
        event_type=str(event.get("event_type", "")),
        node_name=str(event.get("node_name", "")),
        event_data=normalized_data,
        timestamp=float(event.get("timestamp", time.time())),
    )
    return normalized_event, str(thread_id)


class InMemoryAuditLogAdapter(AuditLogPort):
    """In-memory audit log storage (for development)."""

    def __init__(self):
        """Initialize with empty audit store."""
        self._events: dict[str, list[AuditEvent]] = {}

    async def log_event(self, event: AuditEvent) -> None:
        """Log an explicit workflow event.

        Args:
            event: AuditEvent with event_type, node_name, event_data, timestamp
        """
        try:
            normalized_event, thread_id = _normalize_event(event)
            logger.debug(
                "audit event=%s node=%s data=%s",
                normalized_event.get("event_type"),
                normalized_event.get("node_name"),
                normalized_event.get("event_data"),
            )

            if thread_id not in self._events:
                self._events[thread_id] = []

            self._events[thread_id].append(normalized_event)

        except Exception:
            logger.exception("Audit logging failed for event_type=%s", event.get("event_type"))

    async def get_audit_trail(self, thread_id: str) -> list[AuditEvent]:
        """Get audit trail for a thread.

        Args:
            thread_id: Execution thread ID

        Returns:
            List of AuditEvent in chronological order
        """
        return self._events.get(thread_id, [])

    def clear(self):
        """Clear all events (for testing)."""
        self._events.clear()

    def get_all_events(self) -> dict[str, list[AuditEvent]]:
        """Get all events (for testing/debugging)."""
        return self._events


class AuditLogRepository(Protocol):
    """Persistence contract used by DatabaseAuditLogAdapter."""

    def append(self, record: dict[str, Any]) -> None:
        """Persist an audit event record."""

    def list_by_thread(self, thread_id: str) -> list[dict[str, Any]]:
        """Return persisted events for one thread in chronological order."""


class DatabaseAuditLogAdapter(AuditLogPort):
    """Database-backed audit log adapter."""

    def __init__(self, repository: AuditLogRepository):
        self._repository = repository

    async def log_event(self, event: AuditEvent) -> None:
        """Log event to repository.

        Audit logging is best-effort: failures are reported but not re-raised.
        """
        normalized_event, thread_id = _normalize_event(event)
        record = {
            "thread_id": thread_id,
            "event_type": normalized_event.get("event_type"),
            "node_name": normalized_event.get("node_name"),
            "event_data": dict(normalized_event.get("event_data", {})),
            "timestamp": float(normalized_event.get("timestamp", time.time())),
        }
        try:
            self._repository.append(record)
        except Exception:
            logger.exception(
                "Audit logging failed for thread_id=%s event_type=%s",
                thread_id,
                normalized_event.get("event_type"),
            )

    async def get_audit_trail(self, thread_id: str) -> list[AuditEvent]:
        """Get audit trail from repository."""
        try:
            rows = self._repository.list_by_thread(thread_id)
        except Exception:
            logger.exception("Failed to load audit trail for thread_id=%s", thread_id)
            return []

        events: list[AuditEvent] = []
        for row in rows:
            row_data = row.get("event_data")
            event_data = row_data if isinstance(row_data, dict) else {}
            normalized_data = dict(event_data)
            normalized_data.setdefault("thread_id", thread_id)
            events.append(
                AuditEvent(
                    event_type=str(row.get("event_type", "")),
                    node_name=str(row.get("node_name", "")),
                    event_data=normalized_data,
                    timestamp=float(row.get("timestamp", 0.0)),
                )
            )
        return events
