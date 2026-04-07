"""Runtime settings and defaults for the FastAPI delivery edge."""

from __future__ import annotations

from dataclasses import dataclass
import os


APP_VERSION = "2.0.0"

DEFAULT_CORS_METHODS = (
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
)

DEFAULT_CORS_HEADERS = (
    "Authorization",
    "Content-Type",
    "Accept",
    "X-Requested-With",
)


@dataclass(frozen=True)
class RuntimeSettings:
    """Runtime configuration for HTTP delivery concerns."""

    cors_origins: tuple[str, ...]
    cors_methods: tuple[str, ...]
    cors_headers: tuple[str, ...]
    cors_allow_credentials: bool
    request_logging_enabled: bool
    uvicorn_reload: bool


def load_runtime_settings() -> RuntimeSettings:
    """Load runtime settings from environment variables."""
    cors_origins = _csv_env("APP_CORS_ORIGINS")
    cors_methods = _csv_env("APP_CORS_ALLOW_METHODS", DEFAULT_CORS_METHODS)
    cors_headers = _csv_env("APP_CORS_ALLOW_HEADERS", DEFAULT_CORS_HEADERS)
    cors_allow_credentials = _bool_env("APP_CORS_ALLOW_CREDENTIALS", True)

    if "*" in cors_origins and cors_allow_credentials:
        cors_allow_credentials = False

    return RuntimeSettings(
        cors_origins=cors_origins,
        cors_methods=cors_methods,
        cors_headers=cors_headers,
        cors_allow_credentials=cors_allow_credentials,
        request_logging_enabled=_bool_env("APP_REQUEST_LOGGING_ENABLED", True),
        uvicorn_reload=_bool_env("APP_UVICORN_RELOAD", False),
    )


def _csv_env(name: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    return values or default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
