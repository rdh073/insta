"""Audit log adapter - implements AuditLogPort for explicit event logging.

In-memory implementation for development. For production:
- Connect to database for persistence
- Integrate with logging service (Cloudwatch, ELK, etc.)
"""

from __future__ import annotations

import logging
import time
from typing import Any

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


class DatabaseAuditLogAdapter(AuditLogPort):
    """Database-backed audit log adapter (production template)."""

    def __init__(self, db_client: Any = None):
        """Initialize with database client.

        Args:
            db_client: Database connection (e.g., AsyncPg, SQLAlchemy)
        """
        self.db = db_client

    async def log_event(self, event: AuditEvent) -> None:
        """Log event to database."""
        # TODO: Insert into audit_events table
        # await self.db.execute(
        #     """INSERT INTO audit_events (thread_id, event_type, node_name, event_data, timestamp)
        #        VALUES ($1, $2, $3, $4, $5)""",
        #     event.get("event_data", {}).get("thread_id"),
        #     event.get("event_type"),
        #     event.get("node_name"),
        #     json.dumps(event.get("event_data")),
        #     event.get("timestamp"),
        # )

        raise NotImplementedError("DatabaseAuditLogAdapter is a template")

    async def get_audit_trail(self, thread_id: str) -> list[AuditEvent]:
        """Get audit trail from database."""
        # TODO: Query audit_events table
        # rows = await self.db.fetch(
        #     "SELECT * FROM audit_events WHERE thread_id = $1 ORDER BY timestamp",
        #     thread_id,
        # )

        raise NotImplementedError("DatabaseAuditLogAdapter is a template")
