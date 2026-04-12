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
        self._timers: set[threading.Timer] = set()
        self._timers_lock = threading.Lock()
        self._n_workers = workers
        self._started = False
        self._stopping = False

    # ── lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Spawn daemon worker threads.  Idempotent."""
        if self._started:
            return
        self._stopping = False
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
        with self._timers_lock:
            self._stopping = True
            timers = list(self._timers)
            self._timers.clear()
        for timer in timers:
            timer.cancel()

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
        item = _JobItem(job_id=job_id, scheduled_at=scheduled_at)
        delay = self._parse_delay_seconds(item)
        if delay is None or delay <= 0:
            self._queue.put(_JobItem(job_id=job_id))
            return

        if self._mark_scheduled:
            try:
                self._mark_scheduled(job_id)
            except Exception:
                logger.exception("Failed to mark job %s as scheduled", job_id)
        self._schedule_delayed_enqueue(job_id, delay)

    @property
    def pending_count(self) -> int:
        with self._timers_lock:
            delayed_count = len(self._timers)
        return self._queue.qsize() + delayed_count

    # ── backward-compat shim (used by posts router) ──────────────────────

    def schedule_post_job_sync(self, job_id: str, scheduled_at: Optional[str] = None) -> None:
        """Drop-in replacement for ``AsyncioScheduler.schedule_post_job_sync``."""
        self.enqueue(job_id, scheduled_at)

    def _parse_delay_seconds(self, item: _JobItem) -> float | None:
        """Return delay in seconds, or ``None`` when job should run immediately."""
        if not item.scheduled_at:
            return None
        if not isinstance(item.scheduled_at, str):
            logger.warning(
                "Job %s has non-string scheduled_at=%r; executing immediately",
                item.job_id,
                item.scheduled_at,
            )
            return None

        try:
            run_at = datetime.datetime.fromisoformat(item.scheduled_at.replace("Z", "+00:00"))
        except (ValueError, OverflowError):
            logger.warning(
                "Job %s has invalid scheduled_at=%r; executing immediately",
                item.job_id,
                item.scheduled_at,
            )
            return None

        if run_at.tzinfo is None or run_at.tzinfo.utcoffset(run_at) is None:
            logger.warning(
                "Job %s has naive scheduled_at=%r; assuming UTC",
                item.job_id,
                item.scheduled_at,
            )
            run_at = run_at.replace(tzinfo=datetime.timezone.utc)
        else:
            run_at = run_at.astimezone(datetime.timezone.utc)

        return (run_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds()

    def _schedule_delayed_enqueue(self, job_id: str, delay: float) -> None:
        """Schedule delayed enqueue on a timer so workers never block on sleep."""
        timer = threading.Timer(delay, self._enqueue_due_job, args=(job_id,))
        timer.daemon = True

        enqueue_immediately = False
        with self._timers_lock:
            if self._stopping:
                enqueue_immediately = True
            else:
                self._timers.add(timer)

        if enqueue_immediately:
            logger.warning(
                "Queue is shutting down; job %s scheduled for delay %.1fs is enqueued immediately",
                job_id,
                delay,
            )
            self._queue.put(_JobItem(job_id=job_id))
            return

        logger.info("Job %s scheduled for %.1fs", job_id, delay)
        timer.start()

    def _enqueue_due_job(self, job_id: str) -> None:
        current = threading.current_thread()
        with self._timers_lock:
            if isinstance(current, threading.Timer):
                self._timers.discard(current)
            if self._stopping:
                logger.info("Skipping delayed enqueue for job %s during shutdown", job_id)
                return
        self._queue.put(_JobItem(job_id=job_id))

    # ── worker ────────────────────────────────────────────────────────────

    @staticmethod
    def _clear_stopped_control(job_id: str) -> None:
        try:
            from state import clear_job_control

            clear_job_control(job_id)
        except Exception:
            pass

    @staticmethod
    def _read_job_status(job_id: str) -> tuple[bool, str | None]:
        """Return ``(state_available, status_or_none)`` for *job_id*."""
        try:
            from state import get_job
        except Exception:
            return False, None

        try:
            job = get_job(job_id)
        except KeyError:
            return True, None

        raw = job.get("status")
        if raw is None:
            return True, ""
        return True, str(raw).lower()

    def _is_runnable_before_run(self, job_id: str) -> bool:
        state_available, status = self._read_job_status(job_id)
        if not state_available:
            # Fallback for environments that do not expose state.py.
            return True

        if status is None:
            logger.info("Skipping missing queued job %s", job_id)
            return False

        if status == "stopped":
            self._clear_stopped_control(job_id)
            logger.info("Skipping stopped queued job %s", job_id)
            return False

        if status not in ("pending", "scheduled"):
            logger.info("Skipping queued job %s with non-runnable status=%s", job_id, status)
            return False

        return True

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
        if not self._is_runnable_before_run(item.job_id):
            return
        logger.info("Executing job %s", item.job_id)
        self._run_fn(item.job_id)
        logger.info("Job %s finished", item.job_id)

        # Notify SSE listeners that job state changed
        try:
            from app.adapters.scheduler.event_bus import post_job_event_bus
            post_job_event_bus.notify("job_complete")
        except Exception:
            pass
