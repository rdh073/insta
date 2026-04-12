"""Unit tests for job engine ports and scheduler adapters.

Tests cover:
  - JobState enum semantics (values, terminal/active classification)
  - ThreadSafeJobRuntimeAdapter behaviour (transition, pause/resume/cancel, runtime snapshot)
  - PostJobEventPublisherAdapter (delegates to bus)

All tests use injected stores/buses so no module-level singleton is touched.
"""

from __future__ import annotations

import datetime as dt

import pytest

# ── import the ports (pure Python, no side effects) ──────────────────────────

from app.application.ports.job_engine import (
    JobExecutionResult,
    JobSnapshot,
    JobState,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_job(status: str = "pending") -> dict:
    return {
        "status": status,
        "results": [
            {"accountId": "acc1", "status": "success"},
            {"accountId": "acc2", "status": "failed"},
        ],
    }


# ── JobState tests ────────────────────────────────────────────────────────────


class TestJobState:
    def test_values_match_legacy_status_strings(self) -> None:
        assert JobState.QUEUED.value == "pending"
        assert JobState.SCHEDULED.value == "scheduled"
        assert JobState.RUNNING.value == "running"
        assert JobState.PAUSED.value == "paused"
        assert JobState.CANCELLING.value == "cancelling"
        assert JobState.CANCELLED.value == "stopped"
        assert JobState.SUCCEEDED.value == "completed"
        assert JobState.FAILED.value == "failed"
        assert JobState.PARTIAL.value == "partial"

    def test_round_trip_from_status_string(self) -> None:
        for state in JobState:
            assert JobState(state.value) is state

    def test_terminal_states(self) -> None:
        terminal = JobState.terminal_states()
        assert JobState.SUCCEEDED in terminal
        assert JobState.FAILED in terminal
        assert JobState.CANCELLED in terminal
        assert JobState.PARTIAL in terminal
        assert JobState.RUNNING not in terminal
        assert JobState.QUEUED not in terminal

    def test_active_states(self) -> None:
        active = JobState.active_states()
        assert JobState.RUNNING in active
        assert JobState.QUEUED in active
        assert JobState.PAUSED in active
        assert JobState.SUCCEEDED not in active

    def test_is_terminal(self) -> None:
        assert JobState.SUCCEEDED.is_terminal()
        assert not JobState.RUNNING.is_terminal()

    def test_is_active(self) -> None:
        assert JobState.RUNNING.is_active()
        assert not JobState.SUCCEEDED.is_active()

    def test_unknown_status_raises(self) -> None:
        with pytest.raises(ValueError):
            JobState("nonexistent_status")


# ── ThreadSafeJobRuntimeAdapter tests ────────────────────────────────────────


class TestThreadSafeJobRuntimeAdapter:
    """Adapter must delegate to ThreadSafeJobStore without changing its interface."""

    def _make_adapter(self):
        from state import ThreadSafeJobStore
        from app.adapters.scheduler.job_runtime_adapter import ThreadSafeJobRuntimeAdapter

        store = ThreadSafeJobStore()
        store.put("job-1", _make_job("pending"))
        return ThreadSafeJobRuntimeAdapter(store=store), store

    def test_transition_writes_status_value(self) -> None:
        adapter, store = self._make_adapter()
        adapter.transition("job-1", JobState.RUNNING)
        assert store.get("job-1")["status"] == "running"

    def test_transition_succeeded_writes_completed(self) -> None:
        adapter, store = self._make_adapter()
        adapter.transition("job-1", JobState.SUCCEEDED)
        assert store.get("job-1")["status"] == "completed"

    def test_transition_cancelled_writes_stopped(self) -> None:
        adapter, store = self._make_adapter()
        adapter.transition("job-1", JobState.CANCELLED)
        assert store.get("job-1")["status"] == "stopped"

    def test_transition_accepts_failure_category(self) -> None:
        """failure_category remains optional context for current adapters."""
        adapter, store = self._make_adapter()
        adapter.transition("job-1", JobState.FAILED, failure_category="rate_limited")
        assert store.get("job-1")["status"] == "failed"

    def test_request_cancel_sets_stop_flag(self) -> None:
        adapter, store = self._make_adapter()
        adapter.request_cancel("job-1")
        assert store.is_stop_requested("job-1")

    def test_request_pause_and_resume(self) -> None:
        adapter, store = self._make_adapter()
        adapter.request_pause("job-1")
        # A background thread waiting should block; verify event is clear.
        event = store._pause_events.get("job-1")
        assert event is not None
        assert not event.is_set()

        adapter.request_resume("job-1")
        assert event.is_set()

    def test_start_and_heartbeat_persist_runtime_metadata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        adapter, store = self._make_adapter()
        times = iter(
            [
                dt.datetime(2026, 4, 12, 10, 0, tzinfo=dt.timezone.utc),
                dt.datetime(2026, 4, 12, 10, 0, 5, tzinfo=dt.timezone.utc),
            ]
        )
        monkeypatch.setattr(adapter, "_utcnow", lambda: next(times))
        adapter.start("job-1", "worker-0")
        adapter.heartbeat("job-1", "worker-0")
        snap = adapter.snapshot("job-1")
        assert store.get("job-1")["status"] == "pending"
        assert snap.worker_id == "worker-0"
        assert snap.started_at == dt.datetime(2026, 4, 12, 10, 0, tzinfo=dt.timezone.utc)
        assert snap.last_heartbeat_at == dt.datetime(2026, 4, 12, 10, 0, 5, tzinfo=dt.timezone.utc)

    def test_heartbeat_with_other_worker_does_not_override_owner(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        adapter, _ = self._make_adapter()
        times = iter(
            [
                dt.datetime(2026, 4, 12, 11, 0, tzinfo=dt.timezone.utc),
                dt.datetime(2026, 4, 12, 11, 0, 2, tzinfo=dt.timezone.utc),
                dt.datetime(2026, 4, 12, 11, 0, 4, tzinfo=dt.timezone.utc),
            ]
        )
        monkeypatch.setattr(adapter, "_utcnow", lambda: next(times))
        adapter.start("job-1", "worker-a")
        adapter.heartbeat("job-1", "worker-b")
        adapter.heartbeat("job-1", "worker-a")
        snap = adapter.snapshot("job-1")
        assert snap.worker_id == "worker-a"
        assert snap.started_at == dt.datetime(2026, 4, 12, 11, 0, tzinfo=dt.timezone.utc)
        assert snap.last_heartbeat_at == dt.datetime(2026, 4, 12, 11, 0, 4, tzinfo=dt.timezone.utc)

    def test_snapshot_returns_correct_state(self) -> None:
        adapter, store = self._make_adapter()
        store.set_job_status("job-1", "running")
        snap = adapter.snapshot("job-1")
        assert isinstance(snap, JobSnapshot)
        assert snap.state == JobState.RUNNING
        assert snap.job_id == "job-1"

    def test_snapshot_tally(self) -> None:
        adapter, _ = self._make_adapter()
        snap = adapter.snapshot("job-1")
        assert snap.result_tally == {"success": 1, "failed": 1, "skipped": 0}

    def test_snapshot_unknown_status_falls_back_to_queued(self) -> None:
        adapter, store = self._make_adapter()
        store.set_job_status("job-1", "needs_media")  # not in JobState
        snap = adapter.snapshot("job-1")
        assert snap.state == JobState.QUEUED

    def test_snapshot_missing_results_does_not_raise(self) -> None:
        from state import ThreadSafeJobStore
        from app.adapters.scheduler.job_runtime_adapter import ThreadSafeJobRuntimeAdapter

        store = ThreadSafeJobStore()
        store.put("job-x", {"status": "pending"})  # no "results" key
        adapter = ThreadSafeJobRuntimeAdapter(store=store)
        snap = adapter.snapshot("job-x")
        assert snap.result_tally == {}


# ── PostJobEventPublisherAdapter tests ───────────────────────────────────────


class TestPostJobEventPublisherAdapter:
    def _make_adapter(self):
        from app.adapters.scheduler.event_bus import PostJobEventBus
        from app.adapters.scheduler.job_event_publisher_adapter import PostJobEventPublisherAdapter

        bus = PostJobEventBus()
        return PostJobEventPublisherAdapter(bus=bus), bus

    def test_publish_notifies_bus(self) -> None:
        adapter, bus = self._make_adapter()
        import asyncio
        loop = asyncio.new_event_loop()
        bus.set_loop(loop)

        listener_id, queue = bus.subscribe()
        adapter.publish("job-1", "job_complete")

        # Flush the scheduled call
        loop.call_soon(loop.stop)
        loop.run_forever()
        loop.close()

        assert not queue.empty()
        assert queue.get_nowait() == "job_complete"
        bus.unsubscribe(listener_id)

    def test_publish_rejects_payload_argument(self) -> None:
        """Publisher contract is signal-only; payload is not accepted."""
        adapter, _ = self._make_adapter()
        with pytest.raises(TypeError):
            adapter.publish("job-1", "job_failed", payload={"reason": "timeout"})  # type: ignore[call-arg]


# ── JobExecutionResult ────────────────────────────────────────────────────────


class TestJobExecutionResult:
    def test_basic_construction(self) -> None:
        result = JobExecutionResult(job_id="j1", final_state=JobState.SUCCEEDED)
        assert result.job_id == "j1"
        assert result.final_state == JobState.SUCCEEDED
        assert result.failure_category is None
        assert result.detail is None

    def test_failed_with_category(self) -> None:
        result = JobExecutionResult(
            job_id="j1",
            final_state=JobState.FAILED,
            failure_category="rate_limited",
            detail="Too many requests",
        )
        assert result.failure_category == "rate_limited"
        assert result.detail == "Too many requests"


class TestContainerJobEngineWiring:
    def test_container_wires_scheduler_with_engine_adapters(self) -> None:
        from app.bootstrap.container import create_services

        services = create_services()
        scheduler = services["scheduler"]
        assert services["job_runtime"] is scheduler._runtime
        assert services["job_event_publisher"] is scheduler._event_publisher
