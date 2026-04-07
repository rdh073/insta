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

    async def run(self, operator_request, thread_id=None, provider="openai",
                  model=None, api_key=None, provider_base_url=None):
        yield {"type": "run_start", "run_id": "test-run-1", "thread_id": "test-thread"}
        yield {"type": "final_response", "text": "ok"}
        yield {"type": "run_finish", "run_id": "test-run-1", "stop_reason": "end"}

    async def resume(self, thread_id, approval_result, edited_calls=None,
                     provider=None, model=None, api_key=None, provider_base_url=None):
        yield {"type": "run_start", "run_id": "test-run-2", "thread_id": thread_id}
        yield {"type": "run_finish", "run_id": "test-run-2", "stop_reason": "end"}

    # Required attributes checked by the endpoint
    @property
    def llm_gateway(self):
        class _GW:
            def get_default_model(self, provider):
                return "test-model"
        return _GW()


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
