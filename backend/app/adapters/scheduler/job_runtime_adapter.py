"""JobRuntimePort adapter backed by ThreadSafeJobStore.

Phase 1 of the Robust Threaded Job Engine migration.

Wraps the existing in-memory job store so that future operation handlers
depend on the port contract, not on the legacy state module.

start() and heartbeat() are intentional no-ops in this phase.
Phase 5 will add worker_id bookkeeping and stale-detection sweep.
"""

from __future__ import annotations

from typing import Optional

from state import ThreadSafeJobStore, job_store

from app.application.ports.job_engine import JobSnapshot, JobState


class ThreadSafeJobRuntimeAdapter:
    """Implements JobRuntimePort by delegating to ThreadSafeJobStore.

    Constructed with the module-level singleton by default; tests inject
    their own store for isolation.
    """

    def __init__(self, store: ThreadSafeJobStore | None = None) -> None:
        self._store = store or job_store

    # ── JobRuntimePort ────────────────────────────────────────────────────

    def start(self, job_id: str, worker_id: str) -> None:
        # Phase 5: persist worker_id and started_at into the job record.
        pass

    def heartbeat(self, job_id: str, worker_id: str) -> None:
        # Phase 5: update last_heartbeat_at for stale-job detection.
        pass

    def transition(
        self,
        job_id: str,
        state: JobState,
        *,
        failure_category: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        """Write *state.value* (the status string) into the job record."""
        self._store.set_job_status(job_id, state.value)

    def request_pause(self, job_id: str) -> None:
        self._store.request_pause(job_id)

    def request_resume(self, job_id: str) -> None:
        self._store.request_resume(job_id)

    def request_cancel(self, job_id: str) -> None:
        self._store.request_stop(job_id)

    def snapshot(self, job_id: str) -> JobSnapshot:
        """Return a point-in-time snapshot; reads job dict and result tally."""
        job = self._store.get(job_id)
        raw_status = job.get("status", "pending")
        try:
            state = JobState(raw_status)
        except ValueError:
            # Graceful fallback for statuses outside the generic model (e.g. "needs_media").
            state = JobState.QUEUED
        try:
            tally = self._store.tally_results(job_id)
        except (KeyError, TypeError):
            tally = {}
        return JobSnapshot(
            job_id=job_id,
            state=state,
            result_tally=tally,
        )
