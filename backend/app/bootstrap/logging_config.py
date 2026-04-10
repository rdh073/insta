"""Vendor logger configuration for the InstaManager backend.

Configures log levels for instagrapi and its HTTP transport so that
verbose request/response traces can be enabled without touching uvicorn
or application loggers.

Environment variables
---------------------
INSTAGRAPI_LOG_LEVEL  DEBUG | INFO | WARNING | ERROR  (default DEBUG)
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
    # Guarantee a console StreamHandler on root so logs reach docker/terminal
    # even before uvicorn's own dictConfig runs.  basicConfig is a no-op when
    # root already has handlers, so this only fires on the very first call.
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )

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
    """Attach the SSE log-stream handler to key loggers (idempotent).

    Safe to call multiple times — replaces any stale LogStreamHandler instances
    so that the freshest handler (pointing to the live log_stream_bus) is always
    the one that's wired.  Re-applies level overrides on every call because
    uvicorn's dictConfig may reset them between the first call (at import time)
    and the lifespan call (after dictConfig completes).

    uvicorn.access has propagate=False so we add the handler directly there;
    all other loggers flow through the root handler.
    """
    from app.adapters.http.log_stream_handler import LogStreamHandler

    handler = LogStreamHandler()
    handler.setLevel(logging.DEBUG)

    def _replace(lg: logging.Logger) -> None:
        """Remove stale LogStreamHandler instances then add the fresh one."""
        for h in list(lg.handlers):
            if isinstance(h, LogStreamHandler):
                lg.removeHandler(h)
        lg.addHandler(handler)

    # Root logger — catches all propagating loggers.
    root = logging.getLogger()
    _replace(root)
    if root.level == 0 or root.level > logging.INFO:
        root.setLevel(logging.INFO)

    # uvicorn.access is propagate=False — must be wired directly.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        lg = logging.getLogger(name)
        _replace(lg)
        if lg.level == 0 or lg.level > logging.INFO:
            lg.setLevel(logging.INFO)


def _resolve_level() -> int:
    explicit = os.getenv("INSTAGRAPI_LOG_LEVEL", "").strip().upper()
    if explicit:
        return getattr(logging, explicit, logging.DEBUG)
    if os.getenv("INSTAGRAPI_VERBOSE", "").strip().lower() in ("0", "false", "no", "off"):
        return logging.WARNING
    return logging.DEBUG
