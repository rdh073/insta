"""HTTP contract tests for Instagram router error semantics."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.http.dependencies import (
    get_comment_usecases,
    get_direct_usecases,
    get_highlight_usecases,
    get_media_usecases,
    get_relationship_usecases,
    get_story_usecases,
)
from app.adapters.http.routers.instagram.comment import router as comment_router
from app.adapters.http.routers.instagram.direct import router as direct_router
from app.adapters.http.routers.instagram.highlight import router as highlight_router
from app.adapters.http.routers.instagram.media import router as media_router
from app.adapters.http.routers.instagram.relationships import router as relationships_router
from app.adapters.http.routers.instagram.story import router as story_router
from app.adapters.instagram.error_utils import InstagramRateLimitError
from app.domain.instagram_failures import InstagramFailure


@dataclass(frozen=True)
class RouteCase:
    """One endpoint contract check for a router family."""

    name: str
    dependency: Callable[..., Any]
    method_name: str
    http_method: str
    path: str
    params: dict[str, Any] | None = None
    json_body: dict[str, Any] | None = None


ROUTE_CASES: tuple[RouteCase, ...] = (
    RouteCase(
        name="media",
        dependency=get_media_usecases,
        method_name="get_media_by_pk",
        http_method="GET",
        path="/api/instagram/media/acc-1/pk/123",
    ),
    RouteCase(
        name="direct",
        dependency=get_direct_usecases,
        method_name="list_inbox_threads",
        http_method="GET",
        path="/api/instagram/direct/acc-1/inbox",
        params={"amount": 20},
    ),
    RouteCase(
        name="comment",
        dependency=get_comment_usecases,
        method_name="list_comments",
        http_method="GET",
        path="/api/instagram/comment/acc-1/media-123",
        params={"amount": 0},
    ),
    RouteCase(
        name="story",
        dependency=get_story_usecases,
        method_name="get_story",
        http_method="GET",
        path="/api/instagram/story/acc-1/123",
        params={"use_cache": "true"},
    ),
    RouteCase(
        name="highlight",
        dependency=get_highlight_usecases,
        method_name="get_highlight",
        http_method="GET",
        path="/api/instagram/highlight/acc-1/123",
    ),
    RouteCase(
        name="relationships",
        dependency=get_relationship_usecases,
        method_name="list_followers",
        http_method="GET",
        path="/api/instagram/relationships/acc-1/followers",
        params={"username": "target", "amount": 1},
    ),
)


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    for router in (
        media_router,
        direct_router,
        comment_router,
        story_router,
        highlight_router,
        relationships_router,
    ):
        app.include_router(router, prefix="/api/instagram")
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _request(client: TestClient, case: RouteCase):
    if case.http_method == "GET":
        return client.get(case.path, params=case.params)
    return client.post(case.path, params=case.params, json=case.json_body)


def _translated_error(
    *,
    message: str,
    code: str,
    family: str,
    http_hint: int,
) -> ValueError:
    failure = InstagramFailure(
        code=code,
        family=family,
        retryable=http_hint in {429, 503, 504},
        requires_user_action=http_hint in {401, 403, 409},
        user_message=message,
        http_hint=http_hint,
    )
    error = ValueError(message)
    error._instagram_failure = failure  # type: ignore[attr-defined]
    return error


@pytest.mark.parametrize("case", ROUTE_CASES, ids=lambda case: case.name)
def test_translated_unauthorized_errors_return_401_and_structured_payload(
    app: FastAPI,
    client: TestClient,
    case: RouteCase,
):
    message = "Login required. Please re-authenticate."
    translated_error = _translated_error(
        message=message,
        code="login_required",
        family="private_auth",
        http_hint=401,
    )

    def _raise(*_args, **_kwargs):
        raise translated_error

    app.dependency_overrides[case.dependency] = lambda: SimpleNamespace(
        **{case.method_name: _raise}
    )
    try:
        response = _request(client, case)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"] == {
        "message": message,
        "code": "login_required",
        "family": "private_auth",
    }


@pytest.mark.parametrize("case", ROUTE_CASES, ids=lambda case: case.name)
def test_translated_rate_limit_errors_return_429_and_structured_payload(
    app: FastAPI,
    client: TestClient,
    case: RouteCase,
):
    message = "Rate limited. Please wait a moment."
    translated_error = _translated_error(
        message=message,
        code="rate_limit",
        family="common_client",
        http_hint=429,
    )

    def _raise(*_args, **_kwargs):
        raise translated_error

    app.dependency_overrides[case.dependency] = lambda: SimpleNamespace(
        **{case.method_name: _raise}
    )
    try:
        response = _request(client, case)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.json()["detail"] == {
        "message": message,
        "code": "rate_limit",
        "family": "common_client",
    }


def test_plain_validation_value_error_stays_400(app: FastAPI, client: TestClient):
    def _raise(*_args, **_kwargs):
        raise ValueError("media_pk must be a positive integer")

    app.dependency_overrides[get_media_usecases] = lambda: SimpleNamespace(
        get_media_by_pk=_raise
    )
    try:
        response = client.get("/api/instagram/media/acc-1/pk/123")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert isinstance(response.json()["detail"], str)


def test_legacy_instagram_rate_limit_error_still_returns_429(
    app: FastAPI,
    client: TestClient,
):
    def _raise(*_args, **_kwargs):
        raise InstagramRateLimitError("Too many requests")

    app.dependency_overrides[get_relationship_usecases] = lambda: SimpleNamespace(
        list_followers=_raise
    )
    try:
        response = client.get(
            "/api/instagram/relationships/acc-1/followers",
            params={"username": "target", "amount": 1},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
