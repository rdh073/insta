from __future__ import annotations

from app.adapters.http.routers.posts import retry_post_job
from app.adapters.scheduler.job_queue import PostJobQueue, _JobItem
from app.application.use_cases.post_job import (
    INVALID_SCHEDULE_ERROR_CODE,
    MEDIA_REQUIRED_ERROR_CODE,
)
from instagram_runtime.post_job_executor import PostJobExecutor
from state import ThreadSafeJobStore


def _make_job(
    job_id: str,
    *,
    status: str = "pending",
    account_ids: tuple[str, ...] = ("acc1",),
    media_paths: list[str] | None = None,
    scheduled_at: str | None = None,
) -> dict:
    return {
        "id": job_id,
        "caption": "hello",
        "status": status,
        "mediaType": "photo",
        "targets": [{"accountId": account_id} for account_id in account_ids],
        "results": [
            {
                "accountId": account_id,
                "username": f"user_{account_id}",
                "status": "pending",
            }
            for account_id in account_ids
        ],
        "_media_paths": list(media_paths or []),
        "_scheduled_at": scheduled_at,
        "_usertags": [],
        "_extra_data": {},
    }


def test_retry_route_clears_control_before_reenqueue() -> None:
    calls: list[tuple] = []

    class _UseCases:
        def retry_job(self, job_id: str) -> None:
            calls.append(("retry", job_id))

    class _Scheduler:
        def enqueue(self, job_id: str, scheduled_at=None) -> None:
            calls.append(("enqueue", job_id, scheduled_at))

    class _Control:
        def clear_control(self, job_id: str) -> None:
            calls.append(("clear", job_id))

    payload = retry_post_job(
        "job-1",
        usecases=_UseCases(),
        scheduler=_Scheduler(),
        control=_Control(),
    )

    assert payload == {"status": "pending"}
    assert calls == [
        ("clear", "job-1"),
        ("retry", "job-1"),
        ("enqueue", "job-1", None),
    ]


def test_stop_pending_retry_execute_runs_without_auto_skip(monkeypatch, tmp_path) -> None:
    import instagram_runtime.post_job_executor as executor_module

    store = ThreadSafeJobStore()
    job_id = "job-lifecycle"
    media = tmp_path / "media.jpg"
    media.write_bytes(b"x")
    store.put(
        job_id,
        _make_job(
            job_id,
            status="stopped",
            account_ids=("acc1", "acc2"),
            media_paths=[str(media)],
        ),
    )

    # Simulate stop/pause/resume lifecycle before retry.
    store.request_pause(job_id)
    paused_event = store._pause_events[job_id]
    assert not paused_event.is_set()
    store.request_resume(job_id)
    assert paused_event.is_set()
    store.request_stop(job_id)
    assert store.is_stop_requested(job_id)

    # Retry cycle must reset control flags before enqueue/run.
    store.clear_control(job_id)
    assert not store.is_stop_requested(job_id)
    assert job_id not in store._pause_events
    store.set_job_status(job_id, "pending")

    uploaded_clients: list[object] = []
    clients_by_account = {
        "acc1": object(),
        "acc2": object(),
    }

    monkeypatch.setattr(executor_module, "get_client", lambda account_id: clients_by_account[account_id])
    monkeypatch.setattr(
        executor_module,
        "_dispatch_upload",
        lambda client, *_args, **_kwargs: uploaded_clients.append(client),
    )
    monkeypatch.setattr(executor_module, "log_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(executor_module._upload_circuit_breaker, "allow_request", lambda: True)
    monkeypatch.setattr(executor_module._upload_circuit_breaker, "record_success", lambda: None)
    monkeypatch.setattr(executor_module._upload_circuit_breaker, "record_failure", lambda *_args, **_kwargs: None)

    PostJobExecutor(store=store).run(job_id)

    assert len(uploaded_clients) == 2
    assert set(uploaded_clients) == set(clients_by_account.values())
    assert store.get(job_id)["status"] == "completed"
    assert [r["status"] for r in store.get(job_id)["results"]] == ["success", "success"]


def test_queue_skips_stopped_jobs_and_consumes_stop_flag() -> None:
    import state

    job_id = "job-stopped-in-queue"
    state.set_job(job_id, _make_job(job_id, status="stopped"))
    state.request_job_stop(job_id)
    assert state.is_job_stop_requested(job_id)

    ran: list[str] = []
    queue = PostJobQueue(run_fn=lambda queued_job_id: ran.append(queued_job_id))
    queue._handle(_JobItem(job_id=job_id))

    assert ran == []
    assert not state.is_job_stop_requested(job_id)


def test_active_stop_flag_still_skips_worker_upload(monkeypatch) -> None:
    import instagram_runtime.post_job_executor as executor_module

    store = ThreadSafeJobStore()
    job_id = "job-running-stop"
    store.put(job_id, _make_job(job_id, status="running", account_ids=("acc1",)))
    store.request_stop(job_id)
    assert store.is_stop_requested(job_id)

    monkeypatch.setattr(executor_module, "get_client", lambda _account_id: object())
    monkeypatch.setattr(
        executor_module,
        "_dispatch_upload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("upload must not run")),
    )

    executor = PostJobExecutor(store=store)
    executor._upload_one(
        job_id=job_id,
        account_id="acc1",
        username="user_acc1",
        media_paths=[],
        caption="hello",
        media_type="photo",
        thumbnail_path=None,
        igtv_title=None,
        usertags_raw=[],
        location_raw=None,
        extra_data={},
    )

    assert store.get(job_id)["results"][0]["status"] == "skipped"


def test_executor_marks_scheduled_job_without_media_as_needs_media(monkeypatch) -> None:
    import instagram_runtime.post_job_executor as executor_module

    store = ThreadSafeJobStore()
    job_id = "job-scheduled-no-media"
    store.put(
        job_id,
        _make_job(
            job_id,
            status="scheduled",
            account_ids=("acc1",),
            media_paths=[],
            scheduled_at="2026-05-01T12:00:00Z",
        ),
    )

    monkeypatch.setattr(
        executor_module,
        "_dispatch_upload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("upload must not run")),
    )

    PostJobExecutor(store=store).run(job_id)

    job = store.get(job_id)
    assert job["status"] == "needs_media"
    assert job["results"][0]["status"] == "pending"
    assert job["results"][0]["errorCode"] == MEDIA_REQUIRED_ERROR_CODE


def test_executor_marks_invalid_scheduled_time_as_failed(monkeypatch) -> None:
    import instagram_runtime.post_job_executor as executor_module

    store = ThreadSafeJobStore()
    job_id = "job-scheduled-invalid-time"
    store.put(
        job_id,
        _make_job(
            job_id,
            status="scheduled",
            account_ids=("acc1",),
            media_paths=["/tmp/media.jpg"],
            scheduled_at="invalid",
        ),
    )

    monkeypatch.setattr(
        executor_module,
        "_dispatch_upload",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("upload must not run")),
    )

    PostJobExecutor(store=store).run(job_id)

    job = store.get(job_id)
    assert job["status"] == "failed"
    assert job["results"][0]["status"] == "failed"
    assert job["results"][0]["errorCode"] == INVALID_SCHEDULE_ERROR_CODE
