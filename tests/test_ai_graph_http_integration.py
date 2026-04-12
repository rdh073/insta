"""Integration test for /api/ai/chat/graph SSE contract.

Uses a real FastAPI TestClient with a fake RunOperatorCopilotUseCase injected
via dependency_overrides to validate route wiring and SSE payload shape.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("fastapi.testclient")

from fastapi.testclient import TestClient


class _FakeUseCase:
    """Fake RunOperatorCopilotUseCase that yields deterministic SSE events."""

    def __init__(self):
        self.last_resume_call: dict | None = None

    async def run(self, operator_request, thread_id=None, provider="openai",
                  model=None, api_key=None, provider_base_url=None):
        yield {"type": "run_start", "run_id": "test-run-1", "thread_id": "test-thread"}
        yield {"type": "final_response", "text": "ok"}
        yield {"type": "run_finish", "run_id": "test-run-1", "stop_reason": "end"}

    async def resume(self, thread_id, approval_result, edited_calls=None,
                     provider=None, model=None, api_key=None, provider_base_url=None):
        self.last_resume_call = {
            "thread_id": thread_id,
            "approval_result": approval_result,
            "edited_calls": edited_calls,
        }
        yield {"type": "run_start", "run_id": "test-run-2", "thread_id": thread_id}
        yield {"type": "run_finish", "run_id": "test-run-2", "stop_reason": "end"}

    # Required attributes checked by the endpoint
    @property
    def llm_gateway(self):
        class _GW:
            def get_default_model(self, provider):
                return "test-model"
        return _GW()


class _FailingUseCase(_FakeUseCase):
    """Fake use case that raises mid-stream to verify run_error framing."""

    async def run(self, operator_request, thread_id=None, provider="openai",
                  model=None, api_key=None, provider_base_url=None):
        yield {"type": "run_start", "run_id": "test-run-fail", "thread_id": "thread-fail"}
        raise RuntimeError("simulated stream failure")


def test_ai_graph_chat_route_sse_contract_end_to_end():
    """POST /api/ai/chat/graph streams SSE with correct event types."""
    from app.main import app
    from ai_copilot.api import get_operator_copilot_usecase

    app.dependency_overrides[get_operator_copilot_usecase] = lambda: _FakeUseCase()
    client = TestClient(app)

    try:
        response = client.post("/api/ai/chat/graph", json={
            "message": "list accounts",
        })
    finally:
        app.dependency_overrides.pop(get_operator_copilot_usecase, None)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    payload_lines = [
        line.removeprefix("data: ").strip()
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    events = [json.loads(line) for line in payload_lines]
    event_types = [event["type"] for event in events]

    assert event_types[0] == "run_start"
    assert event_types[-1] == "run_finish"
    assert "final_response" in event_types


def test_ai_graph_legacy_alias_sse_contract_end_to_end():
    """/api/ai/graph-chat is an alias for /api/ai/chat/graph."""
    from app.main import app
    from ai_copilot.api import get_operator_copilot_usecase

    app.dependency_overrides[get_operator_copilot_usecase] = lambda: _FakeUseCase()
    client = TestClient(app)

    try:
        response = client.post("/api/ai/graph-chat", json={
            "message": "list accounts",
        })
    finally:
        app.dependency_overrides.pop(get_operator_copilot_usecase, None)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    payload_lines = [
        line.removeprefix("data: ").strip()
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    events = [json.loads(line) for line in payload_lines]
    assert len(events) > 0
    assert all("type" in e for e in events)


def test_ai_graph_chat_frames_stream_exception_as_run_error():
    from app.main import app
    from ai_copilot.api import get_operator_copilot_usecase

    app.dependency_overrides[get_operator_copilot_usecase] = lambda: _FailingUseCase()
    client = TestClient(app)

    try:
        response = client.post("/api/ai/chat/graph", json={"message": "list accounts"})
    finally:
        app.dependency_overrides.pop(get_operator_copilot_usecase, None)

    assert response.status_code == 200
    payload_lines = [
        line.removeprefix("data: ").strip()
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    events = [json.loads(line) for line in payload_lines if line != "[DONE]"]
    assert any(event.get("type") == "run_error" for event in events)


def test_ai_graph_resume_edited_requires_edited_calls():
    from app.main import app
    from ai_copilot.api import get_operator_copilot_usecase

    fake_use_case = _FakeUseCase()
    app.dependency_overrides[get_operator_copilot_usecase] = lambda: fake_use_case
    client = TestClient(app)

    try:
        response = client.post(
            "/api/ai/chat/graph/resume",
            json={"threadId": "thread-1", "approvalResult": "edited"},
        )
    finally:
        app.dependency_overrides.pop(get_operator_copilot_usecase, None)

    assert response.status_code == 422
    assert response.json()["detail"] == "editedCalls is required when approvalResult == 'edited'."
    assert fake_use_case.last_resume_call is None


def test_ai_graph_resume_edited_forwards_valid_edited_calls():
    from app.main import app
    from ai_copilot.api import get_operator_copilot_usecase

    fake_use_case = _FakeUseCase()
    edited_calls = [{"id": "c1", "name": "follow_user", "arguments": {"user_id": "u123"}}]
    app.dependency_overrides[get_operator_copilot_usecase] = lambda: fake_use_case
    client = TestClient(app)

    try:
        response = client.post(
            "/api/ai/chat/graph/resume",
            json={
                "threadId": "thread-2",
                "approvalResult": "edited",
                "editedCalls": edited_calls,
            },
        )
    finally:
        app.dependency_overrides.pop(get_operator_copilot_usecase, None)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert fake_use_case.last_resume_call == {
        "thread_id": "thread-2",
        "approval_result": "edited",
        "edited_calls": edited_calls,
    }

    payload_lines = [
        line.removeprefix("data: ").strip()
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    events = [json.loads(line) for line in payload_lines]
    event_types = [event["type"] for event in events]
    assert event_types[0] == "run_start"
    assert event_types[-1] == "run_finish"
