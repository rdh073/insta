"""Regression tests for SSE transport consistency on long-lived endpoints."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("fastapi.testclient")

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _parse_sse_data_lines(response_text: str) -> list[tuple[str | None, str]]:
    parsed: list[tuple[str | None, str]] = []
    pending_event: str | None = None

    for raw_line in response_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("event: "):
            pending_event = line.removeprefix("event: ").strip() or None
            continue
        if line.startswith("data: "):
            parsed.append((pending_event, line.removeprefix("data: ").strip()))
            pending_event = None

    return parsed


def _assert_common_sse_headers(response) -> None:
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"


class _FailingQueue:
    async def get(self):
        raise RuntimeError("sensitive internal failure")


def test_accounts_events_uses_named_run_error_and_sanitized_payload(monkeypatch):
    from app.adapters.http.event_bus import account_event_bus
    from app.adapters.http.routers.accounts import router as accounts_router

    app = FastAPI()
    app.include_router(accounts_router)

    q = _FailingQueue()
    monkeypatch.setattr(account_event_bus, "subscribe", lambda: q)
    monkeypatch.setattr(account_event_bus, "unsubscribe", lambda _q: None)

    client = TestClient(app)
    response = client.get("/api/accounts/events")

    _assert_common_sse_headers(response)
    frames = _parse_sse_data_lines(response.text)
    named_errors = [
        json.loads(payload)
        for event_name, payload in frames
        if event_name == "run_error"
    ]
    assert len(named_errors) == 1
    assert named_errors[0]["type"] == "run_error"
    assert named_errors[0]["code"] == "stream_error"
    assert "sensitive internal failure" not in named_errors[0]["message"]


def test_posts_stream_uses_named_run_error_and_sanitized_payload(monkeypatch):
    from app.adapters.http.dependencies import get_postjob_usecases
    from app.adapters.http.routers.posts import router as posts_router
    from app.adapters.scheduler.event_bus import post_job_event_bus

    class _FakePostUseCases:
        def list_posts(self):
            return []

    app = FastAPI()
    app.include_router(posts_router)
    app.dependency_overrides[get_postjob_usecases] = lambda: _FakePostUseCases()

    q = _FailingQueue()
    monkeypatch.setattr(post_job_event_bus, "subscribe", lambda: (1, q))
    monkeypatch.setattr(post_job_event_bus, "unsubscribe", lambda _listener_id: None)

    client = TestClient(app)
    response = client.get("/api/posts/stream")

    _assert_common_sse_headers(response)
    frames = _parse_sse_data_lines(response.text)
    assert any(event_name is None and payload == "[]" for event_name, payload in frames)

    named_errors = [
        json.loads(payload)
        for event_name, payload in frames
        if event_name == "run_error"
    ]
    assert len(named_errors) == 1
    assert named_errors[0]["type"] == "run_error"
    assert named_errors[0]["code"] == "stream_error"
    assert "sensitive internal failure" not in named_errors[0]["message"]


def test_logs_stream_uses_named_run_error_and_sanitized_payload(monkeypatch):
    from app.adapters.http.log_stream_bus import log_stream_bus
    from app.adapters.http.routers.logs import router as logs_router

    app = FastAPI()
    app.include_router(logs_router)

    q = _FailingQueue()
    monkeypatch.setattr(log_stream_bus, "subscribe", lambda: q)
    monkeypatch.setattr(log_stream_bus, "unsubscribe", lambda _q: None)

    client = TestClient(app)
    response = client.get("/api/logs/stream")

    _assert_common_sse_headers(response)
    frames = _parse_sse_data_lines(response.text)
    named_errors = [
        json.loads(payload)
        for event_name, payload in frames
        if event_name == "run_error"
    ]
    assert len(named_errors) == 1
    assert named_errors[0]["type"] == "run_error"
    assert named_errors[0]["code"] == "stream_error"
    assert "sensitive internal failure" not in named_errors[0]["message"]
