"""Activity log endpoints."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from app.adapters.http.dependencies import get_logs_usecases
from app.adapters.http.utils import format_error

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
def get_logs(
    limit: int = 100,
    offset: int = 0,
    username: Optional[str] = None,
    event: Optional[str] = None,
    usecases=Depends(get_logs_usecases),
):
    """Read activity log entries with optional filtering."""
    try:
        return usecases.read_log_entries(
            limit=limit, offset=offset, username=username, event=event,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=format_error(exc, "Failed to read logs"))
