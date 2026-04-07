"""Phase D: Verify legacy non-graph assistant is fully purged (LangGraph-only)."""

from __future__ import annotations

import importlib

from app.main import app


class TestPhaseDLegacyPurge:
    def test_ai_chat_usecases_not_in_container(self):
        from app.bootstrap.container import create_services

        services = create_services()
        assert "ai_chat" not in services

    def test_ai_chat_import_removed_from_container(self):
        with open("/home/xtrzy/Workspace/insta/backend/app/bootstrap/container.py") as f:
            content = f.read()

        assert "from app.application.use_cases.ai_chat import" not in content
        assert "AIChartUseCases(" not in content

    def test_get_ai_chat_usecases_removed_from_dependencies(self):
        with open("/home/xtrzy/Workspace/insta/backend/app/adapters/http/dependencies.py") as f:
            content = f.read()

        assert "def get_ai_chat_usecases():" not in content

    def test_legacy_non_graph_module_removed(self):
        try:
            importlib.import_module("app.application.use_cases.ai_chat")
            assert False, "app.application.use_cases.ai_chat must be removed in Phase D"
        except ModuleNotFoundError:
            pass


class TestPhaseDRoutingArchitecture:
    def test_no_legacy_chat_endpoint(self):
        ai_post_routes = [
            route
            for route in app.routes
            if hasattr(route, "path")
            and "/ai" in route.path
            and hasattr(route, "methods")
            and "POST" in route.methods
        ]

        legacy_chat = [r for r in ai_post_routes if getattr(r, "path", "") == "/api/ai/chat"]
        assert legacy_chat == []

    def test_only_graph_ai_paths_are_active(self):
        ai_post_routes = [
            route
            for route in app.routes
            if hasattr(route, "path")
            and "/ai" in route.path
            and hasattr(route, "methods")
            and "POST" in route.methods
        ]

        assert ai_post_routes, "Expected active AI routes from ai_copilot"
        forbidden = [r.path for r in ai_post_routes if r.path == "/api/ai/chat"]
        assert forbidden == [], f"Legacy non-graph chat endpoint must not exist: {forbidden}"

    def test_legacy_router_is_doc_only(self):
        with open("/home/xtrzy/Workspace/insta/backend/app/adapters/http/routers/ai.py") as f:
            content = f.read()

        assert "DEPRECATED" in content or "PHASE D" in content
        assert "async def ai_chat(" not in content


class TestPhaseDExitCriteria:
    def test_only_langgraph_runtime_path(self):
        from app.bootstrap.container import create_services

        services = create_services()
        assert "ai_chat" not in services
        assert "ai_graph_chat" not in services

    def test_frontend_targets_graph_endpoint(self):
        with open("/home/xtrzy/Workspace/insta/frontend/src/api/operator-copilot.ts") as f:
            content = f.read()

        assert "/ai/chat/graph" in content
        assert "/ai/chat/graph/resume" in content
        assert "/ai/chat'" not in content and '"/ai/chat"' not in content
