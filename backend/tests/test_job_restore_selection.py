"""Startup restore behavior for post jobs."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

# Minimal shim for backend/state.py import dependency.
if "instagrapi" not in sys.modules:
    instagrapi_module = types.ModuleType("instagrapi")
    exceptions_module = types.ModuleType("instagrapi.exceptions")

    class _StubClient:  # pragma: no cover - shim class
        pass

    class _StubException(Exception):  # pragma: no cover - shim class
        pass

    instagrapi_module.Client = _StubClient
    exceptions_module.LoginRequired = _StubException
    exceptions_module.BadPassword = _StubException
    exceptions_module.ChallengeRequired = _StubException
    exceptions_module.CaptchaChallengeRequired = _StubException
    exceptions_module.ReloginAttemptExceeded = _StubException
    exceptions_module.TwoFactorRequired = _StubException
    instagrapi_module.exceptions = exceptions_module
    sys.modules["instagrapi"] = instagrapi_module
    sys.modules["instagrapi.exceptions"] = exceptions_module

from app.application.ports.persistence_models import JobRecord
from app.main import _restore_pending_jobs


class _StubJobRepo:
    def __init__(self, jobs: list[JobRecord]):
        self._jobs = {job.id: job for job in jobs}
        self.set_calls: list[str] = []

    def list_all(self) -> list[JobRecord]:
        return list(self._jobs.values())

    def set(self, job_id: str, job: JobRecord) -> None:
        self._jobs[job_id] = job
        self.set_calls.append(job_id)


class _StubScheduler:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, str | None]] = []

    def enqueue(self, job_id: str, scheduled_at: str | None = None) -> None:
        self.enqueued.append((job_id, scheduled_at))


def _job(job_id: str, status: str, *, scheduled_at: str | None = None) -> JobRecord:
    return JobRecord(
        id=job_id,
        caption=f"job {job_id}",
        status=status,
        targets=[],
        results=[],
        created_at="2026-04-01T00:00:00Z",
        media_urls=[],
        media_type="photo",
        media_paths=[],
        scheduled_at=scheduled_at,
    )


@pytest.mark.asyncio
async def test_restore_hydrates_all_and_enqueues_only_pending_or_scheduled():
    repo = _StubJobRepo(
        [
            _job("job-pending", "pending"),
            _job("job-scheduled", "scheduled", scheduled_at="2026-05-01T12:00:00Z"),
            _job("job-stopped", "stopped"),
            _job("job-paused", "paused"),
            _job("job-completed", "completed"),
        ]
    )
    scheduler = _StubScheduler()
    sessions_ready = asyncio.Event()
    sessions_ready.set()

    await _restore_pending_jobs(repo, scheduler, sessions_ready)

    assert set(repo.set_calls) == {
        "job-pending",
        "job-scheduled",
        "job-stopped",
        "job-paused",
        "job-completed",
    }
    assert scheduler.enqueued == [
        ("job-pending", None),
        ("job-scheduled", "2026-05-01T12:00:00Z"),
    ]


@pytest.mark.asyncio
async def test_restore_skips_user_stopped_jobs():
    repo = _StubJobRepo(
        [
            _job("job-stopped", "stopped", scheduled_at="2026-05-01T12:00:00Z"),
            _job("job-pending", "pending"),
        ]
    )
    scheduler = _StubScheduler()
    sessions_ready = asyncio.Event()
    sessions_ready.set()

    await _restore_pending_jobs(repo, scheduler, sessions_ready)

    assert ("job-stopped", "2026-05-01T12:00:00Z") not in scheduler.enqueued
    assert scheduler.enqueued == [("job-pending", None)]
