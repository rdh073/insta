"""Regression tests for relationship batch SSE transport/error framing."""

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


class _FailingRelationshipUseCases:
    async def batch_follow(self, **_kwargs):
        yield {
            "account_id": "acc-1",
            "account": "alpha",
            "target": "target1",
            "action": "follow",
            "success": True,
            "completed": 1,
            "total": 2,
        }
        raise RuntimeError("simulated batch follow failure")

    async def batch_unfollow(self, **_kwargs):
        raise RuntimeError("simulated batch unfollow failure")
        yield  # pragma: no cover


def _build_app(usecases) -> FastAPI:
    from app.adapters.http.dependencies import get_relationship_usecases
    from app.adapters.http.routers.instagram.relationships import router as relationships_router

    app = FastAPI()
    app.include_router(relationships_router)
    app.dependency_overrides[get_relationship_usecases] = lambda: usecases
    return app


def _parse_data_lines(response_text: str) -> list[str]:
    return [
        line.removeprefix("data: ").strip()
        for line in response_text.splitlines()
        if line.startswith("data: ")
    ]


def test_batch_follow_stream_emits_run_error_and_done_sentinel():
    app = _build_app(_FailingRelationshipUseCases())
    client = TestClient(app)

    response = client.post("/relationships/batch/follow", json={
        "account_ids": ["acc-1"],
        "targets": ["target1", "target2"],
        "concurrency": 1,
        "delay_between": 0.0,
    })

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    payloads = _parse_data_lines(response.text)
    assert payloads[-1] == "[DONE]"

    events = [json.loads(item) for item in payloads if item != "[DONE]"]
    assert events[0]["success"] is True
    assert any(event.get("type") == "run_error" for event in events)


def test_batch_unfollow_stream_emits_run_error_and_done_sentinel():
    app = _build_app(_FailingRelationshipUseCases())
    client = TestClient(app)

    response = client.post("/relationships/batch/unfollow", json={
        "account_ids": ["acc-1"],
        "targets": ["target1"],
        "concurrency": 1,
        "delay_between": 0.0,
    })

    assert response.status_code == 200
    payloads = _parse_data_lines(response.text)
    assert payloads[-1] == "[DONE]"

    events = [json.loads(item) for item in payloads if item != "[DONE]"]
    assert len(events) == 1
    assert events[0].get("type") == "run_error"
