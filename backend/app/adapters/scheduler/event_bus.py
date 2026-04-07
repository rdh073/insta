"""Post job event bus — notifies SSE listeners when job state changes.

Architecture:
    PostJobQueue worker thread ──notify()──► EventBus ──► SSE listeners (async)

Thread-safe: notify() is called from worker threads, listeners are asyncio tasks.
Uses asyncio.Queue per listener for cross-thread → async bridging.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)


class PostJobEventBus:
    """Fan-out event bus for post job status changes.

    Worker threads call notify() to broadcast. SSE handlers call
    subscribe()/unsubscribe() and await events from their queue.
    """

    def __init__(self) -> None:
        self._listeners: dict[int, asyncio.Queue[str]] = {}
        self._lock = threading.Lock()
        self._counter = 0
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the asyncio event loop (call once at startup from async context)."""
        self._loop = loop

    def notify(self, event_type: str = "job_update") -> None:
        """Broadcast an event to all listeners. Thread-safe.

        Called from PostJobQueue worker threads after job completes or status changes.
        """
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        with self._lock:
            listeners = list(self._listeners.values())

        for q in listeners:
            try:
                loop.call_soon_threadsafe(q.put_nowait, event_type)
            except (RuntimeError, asyncio.QueueFull):
                pass  # loop closed or queue full — skip

    def subscribe(self) -> tuple[int, asyncio.Queue[str]]:
        """Register a new listener. Returns (listener_id, queue)."""
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=32)
        with self._lock:
            self._counter += 1
            listener_id = self._counter
            self._listeners[listener_id] = q
        logger.debug("post_event_bus.subscribe id=%d total=%d", listener_id, len(self._listeners))
        return listener_id, q

    def unsubscribe(self, listener_id: int) -> None:
        """Remove a listener."""
        with self._lock:
            self._listeners.pop(listener_id, None)
        logger.debug("post_event_bus.unsubscribe id=%d total=%d", listener_id, len(self._listeners))


# Singleton — shared between PostJobQueue and SSE endpoint
post_job_event_bus = PostJobEventBus()
