"""Audit log adapter for operator copilot — implements application.ports.AuditLogPort.

Two implementations:
- InMemoryOperatorAuditLogAdapter — for dev/test (no I/O)
- FileOperatorAuditLogAdapter — JSONL file (dev/staging, easy to grep)

The interface is log(event_type: str, data: dict) → None, matching
the canonical taxonomy in application.ports (AUDIT_EVENT_TYPES /
AUDIT_EVENT_SCHEMA):
  operator_request, planner_decision, policy_gate, approval_submitted,
  approval_result, tool_execution, execution_failure, review_finding,
  stop_reason

Does NOT own event schema decisions — those belong to the callers in
graph nodes. The adapter just persists whatever is passed.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from ai_copilot.application.ports import AuditLogPort, validate_audit_event_payload

_DEFAULT_LOG_PATH = "/tmp/operator-copilot-audit.jsonl"


class InMemoryOperatorAuditLogAdapter(AuditLogPort):
    """In-memory audit log — no I/O, suitable for dev and test.

    Events are stored in a flat list in insertion order and can be
    queried by thread_id for per-run audit trails.
    """

    def __init__(self) -> None:
        self._events: list[dict] = []

    async def log(self, event_type: str, data: dict) -> None:
        """Append an audit event.

        Args:
            event_type: Canonical event type string.
            data: Event payload (must be JSON-serialisable in production).
        """
        validate_audit_event_payload(event_type, data)
        self._events.append({
            "event_type": event_type,
            "timestamp": time.time(),
            "data": data,
        })

    # ── Inspection helpers ─────────────────────────────────────────────────────

    def get_trail(self, thread_id: str) -> list[dict]:
        """Return events for a specific thread in insertion order."""
        return [
            e for e in self._events
            if e.get("data", {}).get("thread_id") == thread_id
        ]

    def all_events(self) -> list[dict]:
        """Return all events (for debugging)."""
        return list(self._events)

    def clear(self) -> None:
        """Clear all events (for testing)."""
        self._events.clear()


class FileOperatorAuditLogAdapter(AuditLogPort):
    """JSONL file audit log — persistent across restarts, easy to grep.

    Each line is a self-contained JSON record with top-level fields for
    common query patterns (thread_id, event_type, timestamp) plus the
    full event data payload.

    Configure path with OPERATOR_COPILOT_AUDIT_LOG_PATH env var.
    Default: /tmp/operator-copilot-audit.jsonl
    """

    def __init__(self, log_path: str | None = None) -> None:
        self.log_path = Path(
            log_path
            or os.getenv("OPERATOR_COPILOT_AUDIT_LOG_PATH", _DEFAULT_LOG_PATH)
        )
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    async def log(self, event_type: str, data: dict) -> None:
        """Write a single audit event as a JSON line.

        Top-level fields thread_id and timestamp are extracted for
        easy log querying without parsing nested JSON.

        Args:
            event_type: Canonical event type string.
            data: Event payload dict.
        """
        validate_audit_event_payload(event_type, data)
        record = {
            "event_type": event_type,
            "timestamp": time.time(),
            "thread_id": data.get("thread_id"),
            "data": data,
        }

        # Remove None top-level fields to keep records clean
        record = {k: v for k, v in record.items() if v is not None}

        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except OSError as exc:
            import sys
            print(
                f"[OPERATOR-AUDIT-ERROR] Failed to write to {self.log_path}: {exc}",
                file=sys.stderr,
            )

    def get_trail(self, thread_id: str) -> list[dict]:
        """Read events for a thread from the JSONL file.

        Args:
            thread_id: Execution thread ID.

        Returns:
            Events in chronological order.
        """
        if not self.log_path.exists():
            return []

        events = []
        try:
            with self.log_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if record.get("thread_id") == thread_id:
                            events.append(record)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

        return sorted(events, key=lambda e: e.get("timestamp", 0))

    def get_log_path(self) -> str:
        """Return the current log file path."""
        return str(self.log_path)
