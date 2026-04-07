"""Phase A Test: Verify route consolidation - no collision on graph endpoints.

PHASE A MIGRATION CRITERIA:
- /api/ai/chat/graph must resolve to ai_copilot RunOperatorCopilotUseCase only
- Legacy AIGraphChatUseCases handler must be disabled
"""

from __future__ import annotations

from app.main import app


class TestPhaseARouteSeparation:
    """Verify graph endpoint ownership is consolidated to ai_copilot/api.py."""

    def test_no_duplicate_graph_endpoints(self):
        routes = app.routes
        graph_endpoints = [
            route for route in routes
            if hasattr(route, "path") and "/graph" in route.path
            and hasattr(route, "methods") and "POST" in route.methods
        ]

        graph_post_routes = [r for r in graph_endpoints if r.path == "/api/ai/chat/graph"]
        assert len(graph_post_routes) == 1, (
            f"Expected 1 handler for /api/ai/chat/graph, got {len(graph_post_routes)}. "
            "This indicates route collision between app/ai.py and ai_copilot/api.py"
        )

    def test_legacy_graph_chat_handler_removed_from_app_routers(self):
        from app.adapters.http.routers import ai as ai_router_module

        router = ai_router_module.router
        routes_in_ai_router = [
            (route.path, route.methods)
            for route in router.routes
            if hasattr(route, "path") and hasattr(route, "methods")
        ]

        graph_routes = [
            (path, methods) for path, methods in routes_in_ai_router
            if "/graph" in path
        ]

        assert len(graph_routes) == 0, (
            f"Legacy graph routes found in app/routers/ai.py: {graph_routes}. "
            "Graph endpoints should be owned by ai_copilot/api.py only."
        )

    def test_ai_copilot_router_owns_graph_endpoints(self):
        from ai_copilot.api import router as copilot_router

        routes_in_copilot = [
            route.path for route in copilot_router.routes
            if hasattr(route, "path")
        ]

        assert any("/graph" in path for path in routes_in_copilot), (
            "ai_copilot router should own /graph endpoints"
        )


class TestPhaseAEndpointOwnership:
    """Verify endpoint ownership is clear and exclusive."""

    def test_route_map_shows_single_active_graph_path(self):
        routes_map = {}

        for route in app.routes:
            if hasattr(route, "path") and hasattr(route, "methods"):
                if "/ai" in route.path and "POST" in route.methods:
                    if route.path not in routes_map:
                        routes_map[route.path] = []
                    handler_name = getattr(route, "endpoint", "unknown").__name__
                    routes_map[route.path].append(handler_name)

        assert "/api/ai/chat/graph" in routes_map, "Graph endpoint must exist"
        assert len(routes_map["/api/ai/chat/graph"]) == 1, (
            "Graph endpoint should have exactly one handler after Phase A"
        )
        assert "/api/ai/chat" not in routes_map, (
            "Legacy /api/ai/chat endpoint should be removed in LangGraph-only mode"
        )


class TestPhaseAExitCriteria:
    """Verify Phase A completion criteria are met."""

    def test_criterion_single_graph_handler(self):
        from app.adapters.http.routers import ai as app_ai_router
        from ai_copilot.api import router as copilot_router

        app_graph_handlers = [
            route for route in app_ai_router.router.routes
            if hasattr(route, "path") and "/graph" in route.path
        ]
        assert len(app_graph_handlers) == 0, (
            f"Found {len(app_graph_handlers)} graph handlers in app/routers/ai.py "
            "but Phase A requires them to be disabled"
        )

        copilot_graph_handlers = [
            route for route in copilot_router.routes
            if hasattr(route, "path") and "/graph" in route.path
        ]
        assert len(copilot_graph_handlers) > 0, (
            "ai_copilot router must own the /graph endpoints after Phase A"
        )
