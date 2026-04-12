from __future__ import annotations

import asyncio
import datetime as dt
from types import SimpleNamespace

import pytest

import app.main as app_main
import state
from app.adapters.http.routers.posts import retry_post_job, stop_post_job
from app.adapters.persistence.post_job_control_adapter import PostJobControlAdapter
from app.adapters.scheduler.event_bus import post_job_event_bus
from app.adapters.scheduler.job_queue import PostJobQueue, _JobItem


def _make_job(
    job_id: str,
    *,
    status: str,
    media_paths: list[str] | None = None,
) -> dict:
    return {
        "id": job_id,
        "caption": "caption",
        "status": status,
        "mediaType": "photo",
        "targets": [{"accountId": "acc-1"}],
        "results": [{"accountId": "acc-1", "username": "alice", "status": "pending"}],
        "_media_paths": list(media_paths or []),
        "_usertags": [],
        "_extra_data": {},
    }


def _flush_loop(loop: asyncio.AbstractEventLoop) -> None:
    loop.call_soon(loop.stop)
    loop.run_forever()


class _ControlledClock:
    def __init__(self, start: dt.datetime) -> None:
        self.now = start


def _install_controlled_clock(monkeypatch: pytest.MonkeyPatch, *, start: dt.datetime) -> _ControlledClock:
    import app.adapters.scheduler.job_queue as queue_module

    clock = _ControlledClock(start)

    class _FakeDatetime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return clock.now.replace(tzinfo=None)
            return clock.now.astimezone(tz)

    monkeypatch.setattr(queue_module.datetime, "datetime", _FakeDatetime)
    return clock


def test_future_scheduled_job_does_not_block_immediate_job(monkeypatch: pytest.MonkeyPatch) -> None:
    run_order: list[str] = []
    delayed: list[tuple[str, float]] = []
    queue = PostJobQueue(run_fn=lambda job_id: run_order.append(job_id), workers=1)

    scheduled_job = "job-scheduled-first"
    immediate_job = "job-immediate-second"

    state.set_job(scheduled_job, _make_job(scheduled_job, status="pending", media_paths=["/tmp/media.jpg"]))
    state.set_job(immediate_job, _make_job(immediate_job, status="pending", media_paths=["/tmp/media.jpg"]))

    def _defer(job_id: str, delay: float) -> None:
        delayed.append((job_id, delay))

    monkeypatch.setattr(queue, "_schedule_delayed_enqueue", _defer)

    run_at = "2099-01-01T00:00:00Z"
    queue.enqueue(scheduled_job, scheduled_at=run_at)
    queue.enqueue(immediate_job)

    queue.start()
    queue._queue.join()
    assert run_order == [immediate_job]
    assert delayed and delayed[0][0] == scheduled_job

    queue.enqueue(scheduled_job, scheduled_at=None)
    queue._queue.join()
    queue.shutdown()

    assert run_order == [immediate_job, scheduled_job]


def test_invalid_scheduled_at_falls_back_to_immediate_execution() -> None:
    ran: list[str] = []
    queue = PostJobQueue(run_fn=lambda job_id: ran.append(job_id), workers=1)
    job_id = "job-schedule-parse-invalid"
    state.set_job(job_id, _make_job(job_id, status="pending", media_paths=["/tmp/media.jpg"]))

    queue.enqueue(job_id, scheduled_at="invalid")
    queue.start()
    queue._queue.join()
    queue.shutdown()

    assert ran == [job_id]


def test_naive_scheduled_at_is_treated_as_utc_without_type_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = dt.datetime(2026, 4, 12, 14, 0, tzinfo=dt.timezone.utc)
    _install_controlled_clock(monkeypatch, start=start)

    ran: list[str] = []
    delayed: list[tuple[str, float]] = []
    queue = PostJobQueue(run_fn=lambda job_id: ran.append(job_id), workers=1)
    job_id = "job-schedule-parse-naive"
    state.set_job(job_id, _make_job(job_id, status="pending", media_paths=["/tmp/media.jpg"]))

    def _defer(target_job_id: str, delay: float) -> None:
        delayed.append((target_job_id, delay))

    monkeypatch.setattr(queue, "_schedule_delayed_enqueue", _defer)

    queue.enqueue(job_id, scheduled_at="2026-04-12T14:00:02")
    assert delayed and delayed[0][0] == job_id
    assert delayed[0][1] > 0

    queue.start()
    queue._queue.join()
    assert ran == []

    queue.enqueue(job_id, scheduled_at=None)
    queue._queue.join()
    queue.shutdown()

    assert ran == [job_id]


@pytest.mark.parametrize("initial_status", ["pending", "scheduled"])
def test_stop_then_retry_resets_control_and_emits_sse_events(initial_status: str) -> None:
    job_id = f"job-stop-retry-{initial_status}"
    state.set_job(job_id, _make_job(job_id, status=initial_status, media_paths=["/tmp/media.jpg"]))
    control = PostJobControlAdapter()

    enqueued: list[tuple[str, str | None]] = []

    class _Scheduler:
        def enqueue(self, target_job_id: str, scheduled_at=None) -> None:
            enqueued.append((target_job_id, scheduled_at))

    class _UseCases:
        def retry_job(self, target_job_id: str) -> None:
            job = state.get_job(target_job_id)
            for result in job["results"]:
                if result.get("status") in ("failed", "pending", "skipped"):
                    result["status"] = "pending"
                    result.pop("error", None)
            job["status"] = "pending"
            state.set_job(target_job_id, job)

    loop = asyncio.new_event_loop()
    post_job_event_bus.set_loop(loop)
    listener_id, event_queue = post_job_event_bus.subscribe()
    try:
        payload = stop_post_job(job_id, control=control)
        _flush_loop(loop)

        assert payload == {"status": "stopped"}
        assert state.get_job(job_id)["status"] == "stopped"
        assert state.is_job_stop_requested(job_id)
        assert event_queue.get_nowait() == "job_stopped"

        retry_payload = retry_post_job(
            job_id,
            usecases=_UseCases(),
            scheduler=_Scheduler(),
            control=control,
        )
        _flush_loop(loop)

        assert retry_payload == {"status": "pending"}
        assert not state.is_job_stop_requested(job_id)
        assert enqueued == [(job_id, None)]
        assert event_queue.get_nowait() == "job_retried"

        ran: list[str] = []
        queue = PostJobQueue(run_fn=lambda queued_job_id: ran.append(queued_job_id))
        queue._handle(_JobItem(job_id=job_id))
        _flush_loop(loop)

        assert ran == [job_id]
        assert event_queue.get_nowait() == "job_complete"
    finally:
        post_job_event_bus.unsubscribe(listener_id)
        loop.close()


class _RestoreJobRepo:
    def __init__(self, jobs: list[SimpleNamespace]) -> None:
        self._jobs = list(jobs)
        self.hydrated: list[str] = []

    def list_all(self) -> list[SimpleNamespace]:
        return list(self._jobs)

    def set(self, job_id: str, job: SimpleNamespace) -> None:
        self.hydrated.append(job_id)


class _RestoreScheduler:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, str | None]] = []

    def enqueue(self, job_id: str, scheduled_at: str | None) -> None:
        self.enqueued.append((job_id, scheduled_at))


@pytest.mark.asyncio
async def test_startup_restore_only_hydrates_and_enqueues_pending_or_scheduled() -> None:
    repo = _RestoreJobRepo(
        [
            SimpleNamespace(id="job-pending", status="pending", scheduled_at=None),
            SimpleNamespace(id="job-scheduled", status="scheduled", scheduled_at="2026-04-12T17:00:00Z"),
            SimpleNamespace(id="job-stopped", status="stopped", scheduled_at=None),
            SimpleNamespace(id="job-needs-media", status="needs_media", scheduled_at="2026-04-12T18:00:00Z"),
        ]
    )
    scheduler = _RestoreScheduler()
    sessions_ready = asyncio.Event()
    sessions_ready.set()

    await app_main._restore_pending_jobs(
        job_repo=repo,
        scheduler=scheduler,
        session_restore_done=sessions_ready,
    )

    assert repo.hydrated == [
        "job-pending",
        "job-scheduled",
        "job-stopped",
        "job-needs-media",
    ]
    assert scheduler.enqueued == [
        ("job-pending", None),
        ("job-scheduled", "2026-04-12T17:00:00Z"),
    ]


def test_scheduled_draft_without_media_is_not_executed() -> None:
    job_id = "job-scheduled-no-media"
    state.set_job(job_id, _make_job(job_id, status="scheduled", media_paths=[]))

    ran: list[str] = []
    queue = PostJobQueue(run_fn=lambda queued_job_id: ran.append(queued_job_id))
    queue._handle(_JobItem(job_id=job_id))

    assert ran == []
    assert state.get_job(job_id)["status"] == "needs_media"
