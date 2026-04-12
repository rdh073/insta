from __future__ import annotations

from fastapi.testclient import TestClient

from app.bootstrap.runtime import DEFAULT_CORS_METHODS, load_runtime_settings
from app.main import create_app


def test_runtime_settings_default_to_production_safe_values(monkeypatch):
    monkeypatch.delenv("APP_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("APP_CORS_ALLOW_METHODS", raising=False)
    monkeypatch.delenv("APP_CORS_ALLOW_HEADERS", raising=False)
    monkeypatch.delenv("APP_CORS_ALLOW_CREDENTIALS", raising=False)
    monkeypatch.delenv("APP_REQUEST_LOGGING_ENABLED", raising=False)
    monkeypatch.delenv("APP_UVICORN_RELOAD", raising=False)

    settings = load_runtime_settings()

    assert settings.cors_origins == ()
    assert settings.cors_methods == DEFAULT_CORS_METHODS
    assert settings.request_logging_enabled is True
    assert settings.uvicorn_reload is False


def test_health_endpoint_reports_in_memory_backend(monkeypatch):
    monkeypatch.delenv("PERSISTENCE_BACKEND", raising=False)
    monkeypatch.delenv("PERSISTENCE_DATABASE_URL", raising=False)
    monkeypatch.delenv("PERSISTENCE_SQLITE_PATH", raising=False)

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "healthy"
    assert payload["components"]["persistence"] == {
        "status": "up",
        "backend": "memory",
        "mode": "in-memory",
    }
    assert response.headers["x-request-id"]


def test_health_endpoint_probes_sql_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "sql")
    monkeypatch.setenv(
        "PERSISTENCE_DATABASE_URL",
        f"sqlite+pysqlite:///{tmp_path / 'health.sqlite3'}",
    )

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")

    payload = response.json()
    assert response.status_code == 200
    assert payload["components"]["persistence"]["status"] == "up"
    assert payload["components"]["persistence"]["backend"] == "sql"


def test_cors_uses_explicit_origin_list(monkeypatch):
    monkeypatch.setenv("APP_CORS_ORIGINS", "https://dashboard.example.com")

    app = create_app()
    with TestClient(app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "https://dashboard.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://dashboard.example.com"
    assert response.headers["access-control-allow-methods"]


def test_exception_handler_hides_internal_errors(monkeypatch):
    monkeypatch.delenv("APP_CORS_ORIGINS", raising=False)

    app = create_app()

    @app.get("/_boom")
    def boom():
        raise RuntimeError("sensitive stack detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/_boom")

    payload = response.json()
    assert response.status_code == 500
    assert payload["detail"] == "Internal server error"
    assert "sensitive stack detail" not in response.text
    assert payload["request_id"]


def test_api_key_middleware_returns_structured_auth_error(monkeypatch):
    monkeypatch.setenv("API_KEY", "expected-key")

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/accounts")

    assert response.status_code == 401
    assert response.json() == {
        "detail": {
            "message": "Invalid or missing API key",
            "code": "backend_api_key_invalid",
            "family": "auth",
        }
    }
