from __future__ import annotations

import datetime
import logging
import threading

from app.adapters.scheduler.job_queue import PostJobQueue
from state import set_job


_QUEUE_LOGGER = "app.adapters.scheduler.job_queue"


def _seed_pending_job(job_id: str) -> None:
    set_job(job_id, {"id": job_id, "status": "pending", "results": []})


def test_future_scheduled_job_does_not_block_immediate_job() -> None:
    executed: list[str] = []
    immediate_done = threading.Event()
    scheduled_marks: list[str] = []

    def run(job_id: str) -> None:
        executed.append(job_id)
        if job_id == "immediate-job":
            immediate_done.set()

    queue = PostJobQueue(
        run_fn=run,
        mark_scheduled_fn=scheduled_marks.append,
        workers=1,
    )
    queue.start()
    try:
        run_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        _seed_pending_job("scheduled-job")
        _seed_pending_job("immediate-job")
        queue.enqueue("scheduled-job", scheduled_at=run_at.isoformat())
        queue.enqueue("immediate-job")

        assert immediate_done.wait(timeout=0.5)
        assert executed == ["immediate-job"]
        assert scheduled_marks == ["scheduled-job"]
    finally:
        queue.shutdown(timeout=0.2)


def test_naive_scheduled_at_is_assumed_utc_and_not_dropped(caplog) -> None:
    executed: list[str] = []
    naive_done = threading.Event()
    followup_done = threading.Event()

    def run(job_id: str) -> None:
        executed.append(job_id)
        if job_id == "naive-job":
            naive_done.set()
        if job_id == "followup-job":
            followup_done.set()

    queue = PostJobQueue(run_fn=run, workers=1)
    queue.start()
    try:
        naive_past = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
        ).replace(tzinfo=None, microsecond=0).isoformat()
        _seed_pending_job("naive-job")
        _seed_pending_job("followup-job")

        with caplog.at_level(logging.WARNING, logger=_QUEUE_LOGGER):
            queue.enqueue("naive-job", scheduled_at=naive_past)
            queue.enqueue("followup-job")
            assert naive_done.wait(timeout=1.0)
            assert followup_done.wait(timeout=1.0)

        assert executed[:2] == ["naive-job", "followup-job"]
        assert "naive scheduled_at" in caplog.text
        assert "assuming UTC" in caplog.text
        assert "Unhandled error processing job naive-job" not in caplog.text
    finally:
        queue.shutdown(timeout=0.2)


def test_invalid_scheduled_at_logs_and_runs_job_immediately(caplog) -> None:
    executed: list[str] = []
    invalid_done = threading.Event()
    after_done = threading.Event()
    scheduled_marks: list[str] = []

    def run(job_id: str) -> None:
        executed.append(job_id)
        if job_id == "invalid-job":
            invalid_done.set()
        if job_id == "after-job":
            after_done.set()

    queue = PostJobQueue(
        run_fn=run,
        mark_scheduled_fn=scheduled_marks.append,
        workers=1,
    )
    queue.start()
    try:
        _seed_pending_job("invalid-job")
        _seed_pending_job("after-job")
        with caplog.at_level(logging.WARNING, logger=_QUEUE_LOGGER):
            queue.enqueue("invalid-job", scheduled_at="not-an-iso-datetime")
            queue.enqueue("after-job")
            assert invalid_done.wait(timeout=1.0)
            assert after_done.wait(timeout=1.0)

        assert executed[:2] == ["invalid-job", "after-job"]
        assert scheduled_marks == []
        assert "invalid scheduled_at" in caplog.text
        assert "executing immediately" in caplog.text
        assert "Unhandled error processing job invalid-job" not in caplog.text
    finally:
        queue.shutdown(timeout=0.2)


def test_queue_uses_runtime_port_and_event_publisher_port() -> None:
    executed: list[str] = []
    runtime_calls: list[tuple[str, str, str]] = []
    published_events: list[tuple[str, str]] = []
    completed = threading.Event()

    class _Runtime:
        def start(self, job_id: str, worker_id: str) -> None:
            runtime_calls.append(("start", job_id, worker_id))

        def heartbeat(self, job_id: str, worker_id: str) -> None:
            runtime_calls.append(("heartbeat", job_id, worker_id))

    class _Publisher:
        def publish(self, job_id: str, event_type: str) -> None:
            published_events.append((job_id, event_type))

    def run(job_id: str) -> None:
        executed.append(job_id)
        completed.set()

    queue = PostJobQueue(
        run_fn=run,
        workers=1,
        runtime=_Runtime(),
        event_publisher=_Publisher(),
    )
    queue.start()
    try:
        _seed_pending_job("runtime-job")
        queue.enqueue("runtime-job")
        assert completed.wait(timeout=1.0)
        queue._queue.join()
    finally:
        queue.shutdown(timeout=0.2)

    assert executed == ["runtime-job"]
    assert runtime_calls[0][0] == "start"
    assert runtime_calls[0][1] == "runtime-job"
    assert runtime_calls[0][2].startswith("post-job-worker-")
    heartbeat_calls = [c for c in runtime_calls if c[0] == "heartbeat"]
    assert len(heartbeat_calls) == 2
    assert published_events[-1] == ("runtime-job", "job_complete")
