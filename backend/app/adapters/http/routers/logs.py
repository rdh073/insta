"""Activity log endpoints."""

from __future__ import annotations

import logging
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.adapters.http.dependencies import get_logs_usecases
from app.adapters.http.streaming import sse_response
from app.adapters.http.utils import format_error

router = APIRouter(prefix="/api/logs", tags=["logs"])
logger = logging.getLogger(__name__)


class VerboseModeRequest(BaseModel):
    enabled: bool


@router.get("/verbose")
def get_verbose_mode():
    """Return whether instagrapi verbose (DEBUG) logging is currently active."""
    enabled = logging.getLogger("instagrapi").level <= logging.DEBUG
    return {"enabled": enabled}


@router.post("/verbose")
def set_verbose_mode(body: VerboseModeRequest):
    """Toggle instagrapi verbose logging at runtime without restarting the server.

    Sets INSTAGRAPI_LOG_LEVEL env var and re-runs configure_vendor_logging() so
    the change takes effect immediately for all subsequent Instagram API calls.
    """
    from app.bootstrap.logging_config import configure_vendor_logging

    os.environ["INSTAGRAPI_LOG_LEVEL"] = "DEBUG" if body.enabled else "WARNING"
    configure_vendor_logging()
    return {"enabled": body.enabled}


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


@router.get("/stream")
async def stream_logs():
    """SSE stream of live Python log records.

    Each event is a JSON object::

        {
          "ts":      "2026-04-10T12:34:56.789+00:00",
          "level":   "DEBUG",
          "levelno": 10,
          "name":    "instagrapi.private",
          "msg":     "POST /api/v1/..."
        }

    Keepalive heartbeat comments are emitted by the shared SSE transport.
    The stream requires ``INSTAGRAPI_LOG_LEVEL=DEBUG`` (or ``INSTAGRAPI_VERBOSE=1``)
    for instagrapi/httpx records to appear.
    """
    from app.adapters.http.log_stream_bus import log_stream_bus

    q = log_stream_bus.subscribe()

    async def generate():
        try:
            while True:
                record = await q.get()
                yield record
        finally:
            log_stream_bus.unsubscribe(q)

    return sse_response(
        generate(),
        logger=logger,
        error_event_name="run_error",
    )
