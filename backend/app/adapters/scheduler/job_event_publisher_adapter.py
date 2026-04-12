"""JobEventPublisherPort adapter backed by PostJobEventBus.

Thin bridge between the generic engine port and the existing SSE event bus.
This adapter intentionally publishes type-only signals. Consumers resolve
full job state from storage when they receive an event.
"""

from __future__ import annotations

from app.adapters.scheduler.event_bus import PostJobEventBus, post_job_event_bus


class PostJobEventPublisherAdapter:
    """Implements JobEventPublisherPort using PostJobEventBus.

    Constructed with the module-level singleton by default; tests inject
    their own bus for isolation.
    """

    def __init__(self, bus: PostJobEventBus | None = None) -> None:
        self._bus = bus or post_job_event_bus

    def publish(self, job_id: str, event_type: str) -> None:
        """Broadcast *event_type* to all SSE listeners.  Thread-safe and non-blocking."""
        self._bus.notify(event_type)
