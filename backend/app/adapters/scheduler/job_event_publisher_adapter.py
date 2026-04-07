"""JobEventPublisherPort adapter backed by PostJobEventBus.

Phase 1 of the Robust Threaded Job Engine migration.

Thin bridge between the generic engine port and the existing SSE event bus.
The payload argument is accepted but not forwarded — the current bus model
broadcasts event type only.  Full payload delivery is deferred to a future phase.
"""

from __future__ import annotations

from typing import Any, Optional

from app.adapters.scheduler.event_bus import PostJobEventBus, post_job_event_bus


class PostJobEventPublisherAdapter:
    """Implements JobEventPublisherPort using PostJobEventBus.

    Constructed with the module-level singleton by default; tests inject
    their own bus for isolation.
    """

    def __init__(self, bus: PostJobEventBus | None = None) -> None:
        self._bus = bus or post_job_event_bus

    def publish(
        self,
        job_id: str,
        event_type: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        """Broadcast *event_type* to all SSE listeners.  Thread-safe and non-blocking."""
        self._bus.notify(event_type)
