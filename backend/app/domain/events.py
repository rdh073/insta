"""Domain entities for activity event logging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ActivityEvent:
    """Core activity event for audit trail."""

    timestamp: str  # ISO 8601 format
    account_id: str
    username: str
    event: str  # Event type: "login_success", "logout", "relogin_failed", etc.
    detail: Optional[str] = None  # Optional detail message or structured info
    status: Optional[str] = None  # Optional status: "active", "error", "2fa_required", etc.

    def validate(self) -> None:
        """Validate event invariants."""
        if not self.timestamp:
            raise ValueError("Event must have a timestamp")
        if not self.account_id:
            raise ValueError("Event must have an account ID")
        if not self.event:
            raise ValueError("Event must have a type")
