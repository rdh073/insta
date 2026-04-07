"""Route ownership contract tests for LangGraph operator copilot endpoints."""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app


def _find_post_routes(path: str) -> list[APIRoute]:
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == path
        and "POST" in route.methods
    ]


def test_graph_primary_route_is_owned_by_ai_copilot():
    """Primary graph route must resolve to ai_copilot API only."""
    routes = _find_post_routes("/api/ai/chat/graph")

    assert len(routes) == 1
    assert routes[0].endpoint.__module__.endswith("ai_copilot.api")


def test_graph_alias_route_is_owned_by_ai_copilot():
    """Backward-compatible alias must resolve to ai_copilot API only."""
    routes = _find_post_routes("/api/ai/graph-chat")

    assert len(routes) == 1
    assert routes[0].endpoint.__module__.endswith("ai_copilot.api")


def test_no_legacy_ai_router_owns_graph_paths():
    """Legacy ai router must not expose active graph handlers."""
    legacy_modules = {"app.adapters.http.routers.ai", "backend.app.adapters.http.routers.ai"}
    graph_paths = {
        "/api/ai/chat/graph",
        "/api/ai/chat/graph/resume",
        "/api/ai/graph-chat",
        "/api/ai/graph-chat/resume",
    }

    leaked = [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path in graph_paths
        and route.endpoint.__module__ in legacy_modules
    ]

    assert leaked == []
