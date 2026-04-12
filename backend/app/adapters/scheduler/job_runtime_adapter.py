"""JobRuntimePort adapter backed by ThreadSafeJobStore.

Wraps the in-memory job store so operation handlers depend on a stable
runtime contract, not direct ``state.py`` imports.
"""

from __future__ import annotations

import datetime as dt
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

    @staticmethod
    def _utcnow() -> dt.datetime:
        return dt.datetime.now(dt.timezone.utc)

    @staticmethod
    def _to_iso8601(value: dt.datetime) -> str:
        return value.astimezone(dt.timezone.utc).isoformat()

    @staticmethod
    def _parse_iso8601(value: object) -> Optional[dt.datetime]:
        if value is None:
            return None
        if isinstance(value, dt.datetime):
            parsed = value
        else:
            try:
                parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
        if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
            return parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)

    # ── JobRuntimePort ────────────────────────────────────────────────────

    def start(self, job_id: str, worker_id: str) -> None:
        now = self._utcnow()
        self._store.mark_started(job_id, worker_id, self._to_iso8601(now))

    def heartbeat(self, job_id: str, worker_id: str) -> None:
        now = self._utcnow()
        self._store.mark_heartbeat(job_id, worker_id, self._to_iso8601(now))

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
        runtime_meta = self._store.get_runtime_metadata(job_id)
        return JobSnapshot(
            job_id=job_id,
            state=state,
            worker_id=runtime_meta.get("worker_id"),
            started_at=self._parse_iso8601(runtime_meta.get("started_at")),
            last_heartbeat_at=self._parse_iso8601(runtime_meta.get("last_heartbeat_at")),
            result_tally=tally,
        )
