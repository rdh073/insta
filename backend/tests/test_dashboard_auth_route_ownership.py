"""Route ownership and contract tests for dashboard auth endpoints."""

from __future__ import annotations

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.adapters.http.dependencies import get_dashboard_auth_usecases
from app.adapters.http.routers.llm_config import get_auth_usecases
from app.main import app


def _find_post_routes(path: str) -> list[APIRoute]:
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == path
        and "POST" in route.methods
    ]


def test_dashboard_auth_login_single_owner():
    """Dashboard login path must have exactly one POST handler."""
    routes = _find_post_routes("/api/dashboard/auth/login")

    assert len(routes) == 1
    assert routes[0].endpoint.__module__.endswith("app.adapters.http.routers.dashboard")


class _FakeDashboardAuth:
    TOKEN_EXPIRY_HOURS = 12

    def login(self, password: str) -> str:
        if password != "top-secret":
            raise PermissionError("Invalid password")
        return "jwt-token"


def test_dashboard_auth_login_response_contract_stable():
    """Login response must preserve the frontend contract shape."""
    app.dependency_overrides[get_dashboard_auth_usecases] = lambda: _FakeDashboardAuth()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/dashboard/auth/login",
                json={"password": "top-secret"},
            )

        assert response.status_code == 200
        assert response.json() == {
            "token": "jwt-token",
            "token_type": "bearer",
            "expires_in_hours": 12,
        }
    finally:
        app.dependency_overrides.pop(get_dashboard_auth_usecases, None)


def test_provider_oauth_authorize_route_single_owner():
    """OAuth authorize path must keep a single POST owner."""
    routes = _find_post_routes("/api/dashboard/llm-providers/{provider}/oauth/authorize")

    assert len(routes) == 1
    assert routes[0].endpoint.__module__.endswith(
        "app.adapters.http.routers.llm_config.provider_oauth"
    )


class _FakeDashboardAuthDisabled:
    def is_enabled(self) -> bool:
        return False


def test_provider_oauth_authorize_still_works_with_auth_disabled():
    """Removing duplicate login route must not break OAuth authorize flow."""
    app.dependency_overrides[get_auth_usecases] = lambda: _FakeDashboardAuthDisabled()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/dashboard/llm-providers/openai_codex/oauth/authorize",
                json={"redirectUri": "http://localhost:5173/oauth/callback"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["provider"] == "openai_codex"
        assert isinstance(body.get("authorization_url"), str)
        assert body["authorization_url"]
    finally:
        app.dependency_overrides.pop(get_auth_usecases, None)
