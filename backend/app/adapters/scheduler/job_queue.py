"""Post-job dispatch queue backed by ``queue.Queue`` + daemon workers.

Replaces the fragile asyncio.create_task / BackgroundTasks dance with a
simple, reliable concurrency model:

    HTTP router  ─── enqueue(job_id) ───►  Queue  ───►  Worker thread
                                                          │
                                                  PostJobExecutor.run()

Workers are daemon threads so they die automatically when the process
exits, but ``shutdown()`` is provided for graceful drain.
"""

from __future__ import annotations

import datetime
import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _JobItem:
    """Immutable work item placed on the queue."""
    job_id: str
    scheduled_at: Optional[str] = None


class PostJobQueue:
    """Thread-safe job dispatch queue with configurable worker count.

    Parameters
    ----------
    run_fn:
        Callable that executes a single post job.  Signature: ``(job_id: str) -> None``.
        Default: ``instagram.run_post_job`` (injected at bootstrap to avoid circular import).
    mark_scheduled_fn:
        Optional callable to mark a job as "scheduled" before the delay.
        Signature: ``(job_id: str) -> None``.
    workers:
        Number of concurrent worker threads.  Default ``1`` is intentional —
        Instagram rate-limits make parallel *jobs* risky; within each job
        the ``PostJobExecutor`` already uploads to all accounts concurrently.
    """

    def __init__(
        self,
        run_fn: Callable[[str], None],
        mark_scheduled_fn: Callable[[str], None] | None = None,
        workers: int = 1,
    ) -> None:
        self._run_fn = run_fn
        self._mark_scheduled = mark_scheduled_fn
        self._queue: queue.Queue[_JobItem | None] = queue.Queue()
        self._workers: list[threading.Thread] = []
        self._n_workers = workers
        self._started = False

    # ── lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Spawn daemon worker threads.  Idempotent."""
        if self._started:
            return
        for i in range(self._n_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"post-job-worker-{i}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)
        self._started = True
        logger.info("PostJobQueue started with %d worker(s)", self._n_workers)

    def shutdown(self, timeout: float = 10.0) -> None:
        """Signal workers to stop and wait up to *timeout* seconds."""
        for _ in self._workers:
            self._queue.put(None)  # poison pill
        for t in self._workers:
            t.join(timeout=timeout)
        self._workers.clear()
        self._started = False
        logger.info("PostJobQueue shut down")

    # ── public API ────────────────────────────────────────────────────────

    def enqueue(self, job_id: str, scheduled_at: Optional[str] = None) -> None:
        """Add a job to the dispatch queue.  Non-blocking."""
        self._queue.put(_JobItem(job_id=job_id, scheduled_at=scheduled_at))

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()

    # ── backward-compat shim (used by posts router) ──────────────────────

    def schedule_post_job_sync(self, job_id: str, scheduled_at: Optional[str] = None) -> None:
        """Drop-in replacement for ``AsyncioScheduler.schedule_post_job_sync``."""
        self.enqueue(job_id, scheduled_at)

    # ── worker ────────────────────────────────────────────────────────────

    def _worker_loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                break  # poison pill → exit

            try:
                self._handle(item)
            except Exception:
                logger.exception("Unhandled error processing job %s", item.job_id)
            finally:
                self._queue.task_done()

    def _handle(self, item: _JobItem) -> None:
        # Optional delay for scheduled posts.
        if item.scheduled_at:
            try:
                run_at = datetime.datetime.fromisoformat(
                    item.scheduled_at.replace("Z", "+00:00"),
                )
                delay = (run_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
                if delay > 0:
                    if self._mark_scheduled:
                        self._mark_scheduled(item.job_id)
                    logger.info("Job %s scheduled, sleeping %.1fs", item.job_id, delay)
                    time.sleep(delay)
            except (ValueError, OverflowError):
                pass  # bad timestamp — run immediately

        logger.info("Executing job %s", item.job_id)
        self._run_fn(item.job_id)
        logger.info("Job %s finished", item.job_id)

        # Notify SSE listeners that job state changed
        try:
            from app.adapters.scheduler.event_bus import post_job_event_bus
            post_job_event_bus.notify("job_complete")
        except Exception:
            pass
