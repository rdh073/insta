"""In-process pub-sub bus for streaming Python log records to SSE clients.

One module-level singleton.  The lifespan sets the event loop once;
publish() is a thread-safe no-op until then.
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Any


class LogStreamBus:
    """Registry of per-connection asyncio queues for log-record events."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        self._loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        # Emit an immediate marker so the client sees the stream is live right away.
        q.put_nowait({
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds"),
            "level": "INFO",
            "levelno": 20,
            "name": "instamanager.log_stream",
            "msg": f"Log stream connected — {len(self._subscribers)} active subscriber(s).",
        })
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def publish(self, record: dict[str, Any]) -> None:
        """Push a log record to all active SSE subscribers.

        Thread-safe — called from any logging thread via call_soon_threadsafe.
        No-op if the event loop has not been wired yet.
        """
        if self._loop is None or not self._subscribers:
            return
        for q in list(self._subscribers):
            self._loop.call_soon_threadsafe(q.put_nowait, record)


log_stream_bus = LogStreamBus()
