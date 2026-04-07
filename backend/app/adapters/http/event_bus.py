"""In-process pub-sub bus for server-sent account events.

Each SSE connection subscribes with an asyncio.Queue.  Background tasks
(e.g. hydrate_account_profile) call publish() after mutating account state.
The SSE endpoint drains the queue and yields events to the client.

Design: one module-level AccountEventBus singleton; no external dependencies.
Works correctly for a single-process FastAPI deployment.
"""

from __future__ import annotations

import asyncio
from typing import Any


class AccountEventBus:
    """Registry of per-connection asyncio queues for account events."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Eagerly set the event loop reference.

        Called at app startup so publish() works even before the first SSE
        client connects and subscribe() is called.
        """
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        """Create and register a new queue for one SSE connection.

        Always called from an async context (FastAPI endpoint), so we
        also capture the running event loop here as a fallback update.
        """
        self._loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a queue when the SSE connection closes."""
        self._subscribers.discard(q)

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Put an event on every active subscriber queue (non-blocking).

        Called from background tasks (sync context / threadpool).  Uses
        loop.call_soon_threadsafe so the put_nowait runs on the event-loop
        thread and correctly wakes up coroutines waiting in q.get().
        Direct put_nowait from a non-loop thread is not thread-safe and
        silently fails to notify waiting coroutines.
        """
        if self._loop is None:
            return
        event = {"type": event_type, **payload}
        for q in list(self._subscribers):
            self._loop.call_soon_threadsafe(q.put_nowait, event)


# Module-level singleton consumed by routes and use cases.
account_event_bus = AccountEventBus()
