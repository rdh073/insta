"""Generic job engine ports — owner: application layer.

These ports are narrow contracts for background-job lifecycle management.
Adapters implement them using threads, queues, and persistence backends.
The goal is to keep orchestration code (use cases, handlers) free of
threading primitives and legacy state-module imports.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Protocol


class JobState(str, Enum):
    """Generic job lifecycle states.

    String values match the existing post-job status strings so the
    frontend contract is unchanged during migration.
    """

    QUEUED = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLING = "cancelling"
    CANCELLED = "stopped"
    SUCCEEDED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"

    @classmethod
    def terminal_states(cls) -> frozenset[JobState]:
        return frozenset({cls.CANCELLED, cls.SUCCEEDED, cls.FAILED, cls.PARTIAL})

    @classmethod
    def active_states(cls) -> frozenset[JobState]:
        return frozenset({cls.QUEUED, cls.SCHEDULED, cls.RUNNING, cls.PAUSED, cls.CANCELLING})

    def is_terminal(self) -> bool:
        return self in self.terminal_states()

    def is_active(self) -> bool:
        return self in self.active_states()


@dataclass
class JobSnapshot:
    """Point-in-time view of a job's runtime state."""

    job_id: str
    state: JobState
    worker_id: Optional[str] = None
    started_at: Optional[datetime.datetime] = None
    last_heartbeat_at: Optional[datetime.datetime] = None
    result_tally: dict[str, int] = field(default_factory=dict)


@dataclass
class JobExecutionResult:
    """Final outcome returned by a JobOperationHandlerPort.execute() call."""

    job_id: str
    final_state: JobState
    failure_category: Optional[str] = None
    detail: Optional[str] = None


class JobDispatcherPort(Protocol):
    """Enqueue a job for background execution."""

    def submit(self, job_id: str, run_at: Optional[datetime.datetime] = None) -> None:
        """Place *job_id* on the dispatch queue.  Non-blocking."""
        ...


class JobRuntimePort(Protocol):
    """Mutable view of a single job's runtime state.

    Passed into operation handlers so they can report progress without
    importing threading primitives or the legacy state module.
    """

    def start(self, job_id: str, worker_id: str) -> None:
        """Record that *worker_id* has begun executing *job_id*."""
        ...

    def heartbeat(self, job_id: str, worker_id: str) -> None:
        """Update the last-heartbeat timestamp.  Called periodically by long-running workers."""
        ...

    def transition(
        self,
        job_id: str,
        state: JobState,
        *,
        failure_category: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        """Move *job_id* to *state*, optionally recording failure context."""
        ...

    def request_pause(self, job_id: str) -> None:
        """Signal the executor to pause before the next unit of work."""
        ...

    def request_resume(self, job_id: str) -> None:
        """Release a paused job so it continues."""
        ...

    def request_cancel(self, job_id: str) -> None:
        """Signal the executor to stop after the current unit of work."""
        ...

    def snapshot(self, job_id: str) -> JobSnapshot:
        """Return a point-in-time snapshot of runtime state.  Read-only."""
        ...


class JobEventPublisherPort(Protocol):
    """Publish job lifecycle events to consumers (SSE, audit log, metrics)."""

    def publish(self, job_id: str, event_type: str) -> None:
        """Broadcast *event_type* for *job_id*.  Consumers fetch details separately."""
        ...


class JobOperationHandlerPort(Protocol):
    """Executes the business logic for one job operation type.

    Registered with the engine; dispatched when a job matching
    operation_name() is dequeued.
    """

    def operation_name(self) -> str:
        """Unique identifier for this operation type, e.g. ``'post_publish'``."""
        ...

    def execute(self, job_id: str, runtime: JobRuntimePort) -> JobExecutionResult:
        """Perform the operation.

        Must call runtime.transition() for every significant state change.
        The engine catches unhandled exceptions and produces a terminal transition.
        """
        ...
