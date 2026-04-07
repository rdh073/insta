"""Phase C: purge legacy read-only graph stack and keep only operator copilot runtime."""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from ai_copilot.api import get_operator_copilot_usecase
from app.main import app


class _FakeOperatorCopilotUseCase:
    async def run(self, **kwargs):
        yield {"type": "run_start", "thread_id": kwargs.get("thread_id") or "generated"}
        yield {"type": "final_response", "text": "ok"}

    async def resume(self, **kwargs):
        yield {"type": "run_start", "thread_id": kwargs["thread_id"]}
        yield {"type": "run_finish", "stop_reason": kwargs["approval_result"]}


@pytest.fixture
def client_with_fake_usecase():
    app.dependency_overrides[get_operator_copilot_usecase] = lambda: _FakeOperatorCopilotUseCase()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_operator_copilot_usecase, None)


class TestPhaseCLegacyGraphPurge:
    def test_ai_graph_chat_not_wired_in_container(self):
        from app.bootstrap.container import create_services

        services = create_services()
        assert "ai_graph_chat" not in services

    @pytest.mark.parametrize(
        "module_name",
        [
            "app.application.use_cases.ai_graph_chat",
            "app.adapters.ai.graph_builder",
            "app.adapters.ai.graph_nodes",
            "app.adapters.ai.graph_state",
            "ai_copilot.application.use_cases.run_graph",
            "ai_copilot.application.graphs.read_only_operator_copilot",
        ],
    )
    def test_legacy_modules_removed(self, module_name: str):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)


class TestPhaseCSmokeRunResume:
    def test_run_endpoint_streams_events(self, client_with_fake_usecase: TestClient):
        response = client_with_fake_usecase.post(
            "/api/ai/chat/graph",
            json={"message": "hello"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert '"type": "run_start"' in response.text
        assert '"type": "final_response"' in response.text

    def test_resume_endpoint_streams_events(self, client_with_fake_usecase: TestClient):
        response = client_with_fake_usecase.post(
            "/api/ai/chat/graph/resume",
            json={"threadId": "thread-1", "approvalResult": "approved"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert '"type": "run_start"' in response.text
        assert '"type": "run_finish"' in response.text


class TestPhaseCExitCriteria:
    def test_only_run_operator_copilot_is_active_orchestrator(self):
        from app.bootstrap.container import create_services
        from ai_copilot.api import get_operator_copilot_usecase
        from ai_copilot.application.use_cases.run_operator_copilot import (
            RunOperatorCopilotUseCase,
        )

        services = create_services()
        assert isinstance(get_operator_copilot_usecase(), RunOperatorCopilotUseCase)
        assert "ai_graph_chat" not in services
