"""Vendor logger configuration for the InstaManager backend.

Configures log levels for instagrapi and its HTTP transport so that
verbose request/response traces can be enabled without touching uvicorn
or application loggers.

Environment variables
---------------------
INSTAGRAPI_LOG_LEVEL  DEBUG | INFO | WARNING | ERROR  (default WARNING)
INSTAGRAPI_VERBOSE    1 | true | yes                  shorthand for DEBUG
"""

from __future__ import annotations

import logging
import os


def configure_vendor_logging() -> None:
    """Apply log-level overrides for instagrapi and its HTTP transport.

    Called once at app startup (before any Instagram client is constructed)
    so the levels take effect for all subsequent SDK calls.
    Also attaches the SSE log-stream handler to the root logger.
    """
    level = _resolve_level()

    # instagrapi core + private-API module
    for name in ("instagrapi", "private"):
        logging.getLogger(name).setLevel(level)

    # HTTP transport used by instagrapi (httpx + httpcore)
    # Only enable at DEBUG when instagrapi itself is DEBUG to avoid
    # drowning the output with raw socket-level traces at INFO.
    http_level = level if level <= logging.DEBUG else logging.WARNING
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(http_level)

    if level <= logging.DEBUG:
        logging.getLogger(__name__).debug(
            "instagrapi verbose logging enabled "
            "(instagrapi=DEBUG, httpx=DEBUG)"
        )

    _attach_sse_handler()


def _attach_sse_handler() -> None:
    """Attach the SSE log-stream handler to key loggers (idempotent)."""
    from app.adapters.http.log_stream_handler import LogStreamHandler

    root = logging.getLogger()
    if any(isinstance(h, LogStreamHandler) for h in root.handlers):
        return  # already attached (e.g. uvicorn --reload re-imports)

    handler = LogStreamHandler()
    handler.setLevel(logging.DEBUG)

    # Lower root logger to INFO so application logs flow through.
    if root.level == logging.WARNING or root.level == 0:
        root.setLevel(logging.INFO)
    root.addHandler(handler)

    # Uvicorn loggers have propagate=True by default but their levels may be
    # set higher; ensure they forward to the root handler at INFO.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        lg = logging.getLogger(name)
        if lg.level == 0 or lg.level > logging.INFO:
            lg.setLevel(logging.INFO)


def _resolve_level() -> int:
    explicit = os.getenv("INSTAGRAPI_LOG_LEVEL", "").strip().upper()
    if explicit:
        return getattr(logging, explicit, logging.WARNING)
    if os.getenv("INSTAGRAPI_VERBOSE", "").strip().lower() in ("1", "true", "yes", "on"):
        return logging.DEBUG
    return logging.WARNING
