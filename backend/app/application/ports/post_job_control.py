"""Port for post-job lifecycle control (stop / pause / resume / status).

Owned by the application layer.  Adapters implement this to bridge
whatever concurrency / state-management backend is in use.
"""

from __future__ import annotations

from typing import Optional, Protocol


class PostJobControlPort(Protocol):
    """Read and mutate post-job runtime state."""

    def get_job(self, job_id: str) -> dict:
        """Return the live job dict.  Raises ``KeyError`` if missing."""
        ...

    def set_job_status(self, job_id: str, status: str) -> None:
        """Overwrite the job-level status field."""
        ...

    def request_stop(self, job_id: str) -> None:
        """Signal the executor to stop after the current account."""
        ...

    def request_pause(self, job_id: str) -> None:
        """Signal the executor to pause before the next account."""
        ...

    def request_resume(self, job_id: str) -> None:
        """Release a paused job so it continues uploading."""
        ...

    def clear_control(self, job_id: str) -> None:
        """Clear stop/pause runtime flags for a fresh enqueue/retry cycle."""
        ...


class PostJobQueuePort(Protocol):
    """Enqueue a job for background execution."""

    def enqueue(self, job_id: str, scheduled_at: Optional[str] = None) -> None:
        """Place *job_id* on the dispatch queue.  Non-blocking."""
        ...
