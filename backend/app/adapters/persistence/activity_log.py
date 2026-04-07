"""Activity log writer adapter."""

from __future__ import annotations

from typing import Optional

from .state_gateway import default_state_gateway


class ActivityLogWriter:
    """Writes activity events to log file."""

    def __init__(self, gateway=default_state_gateway):
        self.gateway = gateway

    def log_event(
        self,
        account_id: str,
        username: str,
        event: str,
        detail: Optional[str] = None,
        status: Optional[str] = None,
    ) -> None:
        """Log an account event to activity log."""
        self.gateway.log_event(
            account_id,
            username,
            event,
            detail=detail or "",
            status=status or "",
        )
