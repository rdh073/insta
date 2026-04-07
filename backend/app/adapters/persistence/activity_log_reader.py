"""Adapter that reads the JSONL activity log file.

Implements ``LogReaderPort`` by parsing the line-delimited JSON file
managed by ``state.py``'s ``log_event`` helper.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .state_gateway import default_state_gateway


class ActivityLogReaderAdapter:
    """File-backed log reader — mirrors the logic that was in services.py."""

    def __init__(self, log_file: Path | None = None) -> None:
        self._log_file = log_file or default_state_gateway.sessions_dir / "activity.log"

    def read_entries(
        self,
        limit: int = 100,
        offset: int = 0,
        username: Optional[str] = None,
        event: Optional[str] = None,
    ) -> dict:
        if not self._log_file.exists():
            return {"entries": [], "total": 0}

        entries: list[dict] = []
        try:
            for line_number, line in enumerate(
                self._log_file.read_text().splitlines(), start=1
            ):
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSON log entry in {self._log_file} at line {line_number}"
                    ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"Failed to read activity log at {self._log_file}"
            ) from exc

        entries.reverse()

        if username:
            entries = [
                e for e in entries if e.get("username", "").lower() == username.lower()
            ]
        if event:
            entries = [e for e in entries if e.get("event") == event]

        total = len(entries)
        return {"entries": entries[offset : offset + limit], "total": total}
