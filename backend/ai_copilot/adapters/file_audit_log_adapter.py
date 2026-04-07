"""File-based audit log adapter - writes events to JSONL for persistence.

PURPOSE: Provide traceable, durable audit log without requiring a database.
Each line in the JSONL file is a self-contained audit event.

Format: One JSON object per line (JSONL / newline-delimited JSON).
Path: Configurable via SMART_ENGAGEMENT_AUDIT_LOG_PATH env var.
Default: /tmp/smart-engagement-audit.jsonl

Each event includes full context for traceability:
- source_account: who performed the action
- target: what was selected
- draft: what content was proposed/approved/edited
- approver: who made the approval decision
- executor_result: what happened when executed
- timestamp: when

In production, replace with a database-backed adapter without changing
the port interface (AuditLogPort).
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from ai_copilot.application.smart_engagement.ports import AuditLogPort

logger = logging.getLogger(__name__)
from ai_copilot.application.smart_engagement.state import AuditEvent

_DEFAULT_LOG_PATH = "/tmp/smart-engagement-audit.jsonl"


class FileAuditLogAdapter(AuditLogPort):
    """Audit log adapter that writes events to a JSONL file.

    Thread-safe for single-process use (Python GIL).
    For multi-process: switch to database-backed adapter.

    Traceable fields included per event:
    - event_type: what happened
    - node_name: which node emitted
    - thread_id: workflow execution ID (from event_data)
    - source_account: account_id (from event_data)
    - target_id: selected target (from event_data)
    - draft_content: proposed/approved content (from event_data)
    - approver_decision: approved/rejected/edited (from event_data)
    - executor_success: bool (from event_data)
    - timestamp: ISO 8601 string + unix float
    """

    def __init__(self, log_path: str | None = None):
        """Initialize file audit log.

        Args:
            log_path: Path to JSONL file. Defaults to
                      SMART_ENGAGEMENT_AUDIT_LOG_PATH env var or /tmp/smart-engagement-audit.jsonl
        """
        self.log_path = Path(
            log_path
            or os.getenv("SMART_ENGAGEMENT_AUDIT_LOG_PATH", _DEFAULT_LOG_PATH)
        )
        # Ensure parent directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    async def log_event(self, event: AuditEvent) -> None:
        """Write audit event to JSONL file.

        Enriches the event with traceable top-level fields extracted
        from event_data so the log is easy to query without parsing nested JSON.

        Args:
            event: AuditEvent with event_type, node_name, event_data, timestamp
        """
        event_data = event.get("event_data", {})

        # Build enriched log record with traceable top-level fields
        record = {
            # Core event fields
            "event_type": event.get("event_type"),
            "node_name": event.get("node_name"),
            "timestamp": event.get("timestamp", time.time()),
            # Traceable context fields (extracted from event_data)
            "thread_id": event_data.get("thread_id"),
            "source_account": event_data.get("account_id"),
            "target_id": event_data.get("target_id"),
            # Action details
            "action_type": event_data.get("action_type"),
            "draft_content": _extract_draft_content(event_data),
            # Approval traceability
            "approval_id": event_data.get("approval_id"),
            "approver_decision": event_data.get("decision"),
            "approver_notes": event_data.get("notes"),
            # Execution traceability
            "executor_success": event_data.get("success"),
            "executor_action_id": event_data.get("action_id"),
            "executor_reason": event_data.get("reason"),
            # Risk assessment
            "risk_level": event_data.get("risk_level"),
            "rule_hits": event_data.get("rule_hits"),
            # Full raw event_data for completeness
            "event_data": event_data,
        }

        # Remove None values to keep the file clean
        record = {k: v for k, v in record.items() if v is not None}

        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except OSError:
            logger.exception("Failed to write audit event to %s", self.log_path)

    async def get_audit_trail(self, thread_id: str) -> list[AuditEvent]:
        """Read audit trail for a thread from the JSONL file.

        Args:
            thread_id: Execution thread ID

        Returns:
            List of AuditEvent in chronological order
        """
        if not self.log_path.exists():
            return []

        events: list[AuditEvent] = []
        try:
            with self.log_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if record.get("thread_id") == thread_id:
                            events.append(
                                AuditEvent(
                                    event_type=record.get("event_type", "unknown"),
                                    node_name=record.get("node_name", ""),
                                    event_data=record.get("event_data", {}),
                                    timestamp=record.get("timestamp", 0.0),
                                )
                            )
                    except json.JSONDecodeError:
                        continue
        except OSError:
            logger.exception("Failed to read audit trail from %s", self.log_path)

        return sorted(events, key=lambda e: e.get("timestamp", 0))

    def read_all_records(self, limit: int = 100) -> list[dict]:
        """Read recent raw records from the log file (for debugging/monitoring).

        Args:
            limit: Maximum number of records to return (most recent first)

        Returns:
            List of raw record dicts
        """
        if not self.log_path.exists():
            return []

        records = []
        try:
            with self.log_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            logger.exception("Failed to read audit records from %s", self.log_path)

        return records[-limit:]

    def get_log_path(self) -> str:
        """Return the current log file path."""
        return str(self.log_path)


def _extract_draft_content(event_data: dict) -> str | None:
    """Extract draft content from event_data for traceability."""
    # From draft_action node
    if "draft_payload" in event_data:
        payload = event_data["draft_payload"]
        if isinstance(payload, dict):
            return payload.get("content")

    # From request_approval interrupt payload
    if "draft_action" in event_data:
        action = event_data["draft_action"]
        if isinstance(action, dict):
            return action.get("content")

    return None
