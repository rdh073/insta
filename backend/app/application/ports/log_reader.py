"""Port for reading activity-log entries.

Owned by the application layer.  Adapters provide the concrete I/O
(file-backed, database-backed, etc.).
"""

from __future__ import annotations

from typing import Optional, Protocol


class LogReaderPort(Protocol):
    """Read activity-log entries with optional filtering."""

    def read_entries(
        self,
        limit: int = 100,
        offset: int = 0,
        username: Optional[str] = None,
        event: Optional[str] = None,
    ) -> dict:
        """Return ``{"entries": [...], "total": int}``."""
        ...
