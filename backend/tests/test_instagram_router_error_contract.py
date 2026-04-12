"""HTTP contract tests for Instagram router error semantics.

Coverage notes (route-contract matrix):
- media: 4 endpoints
- direct: 12 endpoints
- comment: 8 endpoints
- story: 6 endpoints
- highlight: 8 endpoints
- relationships (read routes): 4 endpoints

Each endpoint is asserted for translated 401/429 status mapping and structured
error detail payload shape (message/code/family).
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import Mock

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
from app.application.use_cases.relationships import RelationshipUseCases
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
    # Media router
    RouteCase(
        name="media:get_media_by_pk",
        dependency=get_media_usecases,
        method_name="get_media_by_pk",
        http_method="GET",
        path="/api/instagram/media/acc-1/pk/123",
    ),
    RouteCase(
        name="media:get_media_by_code",
        dependency=get_media_usecases,
        method_name="get_media_by_code",
        http_method="GET",
        path="/api/instagram/media/acc-1/code/ABC123",
    ),
    RouteCase(
        name="media:get_user_medias",
        dependency=get_media_usecases,
        method_name="get_user_medias",
        http_method="GET",
        path="/api/instagram/media/acc-1/user/777",
        params={"amount": 5},
    ),
    RouteCase(
        name="media:get_media_oembed",
        dependency=get_media_usecases,
        method_name="get_media_oembed",
        http_method="GET",
        path="/api/instagram/media/acc-1/oembed",
        params={"url": "https://www.instagram.com/p/ABC123/"},
    ),
    # Direct router
    RouteCase(
        name="direct:send_to_username",
        dependency=get_direct_usecases,
        method_name="send_to_username",
        http_method="POST",
        path="/api/instagram/direct/send",
        json_body={"account_id": "acc-1", "username": "target", "text": "hello"},
    ),
    RouteCase(
        name="direct:find_or_create_thread",
        dependency=get_direct_usecases,
        method_name="find_or_create_thread",
        http_method="POST",
        path="/api/instagram/direct/find-or-create",
        json_body={"account_id": "acc-1", "participant_user_ids": [1, 2]},
    ),
    RouteCase(
        name="direct:send_to_thread",
        dependency=get_direct_usecases,
        method_name="send_to_thread",
        http_method="POST",
        path="/api/instagram/direct/send-thread",
        json_body={
            "account_id": "acc-1",
            "direct_thread_id": "thread-1",
            "text": "hello thread",
        },
    ),
    RouteCase(
        name="direct:send_to_users",
        dependency=get_direct_usecases,
        method_name="send_to_users",
        http_method="POST",
        path="/api/instagram/direct/send-users",
        json_body={"account_id": "acc-1", "user_ids": [1, 2], "text": "hello users"},
    ),
    RouteCase(
        name="direct:delete_message",
        dependency=get_direct_usecases,
        method_name="delete_message",
        http_method="POST",
        path="/api/instagram/direct/delete-message",
        json_body={
            "account_id": "acc-1",
            "direct_thread_id": "thread-1",
            "direct_message_id": "msg-1",
        },
    ),
    RouteCase(
        name="direct:approve_pending_thread",
        dependency=get_direct_usecases,
        method_name="approve_pending_thread",
        http_method="POST",
        path="/api/instagram/direct/approve-pending",
        json_body={"account_id": "acc-1", "direct_thread_id": "thread-1"},
    ),
    RouteCase(
        name="direct:mark_thread_seen",
        dependency=get_direct_usecases,
        method_name="mark_thread_seen",
        http_method="POST",
        path="/api/instagram/direct/mark-seen",
        json_body={"account_id": "acc-1", "direct_thread_id": "thread-1"},
    ),
    RouteCase(
        name="direct:list_inbox_threads",
        dependency=get_direct_usecases,
        method_name="list_inbox_threads",
        http_method="GET",
        path="/api/instagram/direct/acc-1/inbox",
        params={"amount": 20},
    ),
    RouteCase(
        name="direct:list_pending_threads",
        dependency=get_direct_usecases,
        method_name="list_pending_threads",
        http_method="GET",
        path="/api/instagram/direct/acc-1/pending",
        params={"amount": 20},
    ),
    RouteCase(
        name="direct:get_thread",
        dependency=get_direct_usecases,
        method_name="get_thread",
        http_method="GET",
        path="/api/instagram/direct/acc-1/thread/thread-1",
        params={"amount": 20},
    ),
    RouteCase(
        name="direct:list_messages",
        dependency=get_direct_usecases,
        method_name="list_messages",
        http_method="GET",
        path="/api/instagram/direct/acc-1/thread/thread-1/messages",
        params={"amount": 20},
    ),
    RouteCase(
        name="direct:search_threads",
        dependency=get_direct_usecases,
        method_name="search_threads",
        http_method="GET",
        path="/api/instagram/direct/acc-1/search",
        params={"query": "target"},
    ),
    # Comment router
    RouteCase(
        name="comment:create_comment",
        dependency=get_comment_usecases,
        method_name="create_comment",
        http_method="POST",
        path="/api/instagram/comment",
        json_body={"account_id": "acc-1", "media_id": "media-1", "text": "nice post"},
    ),
    RouteCase(
        name="comment:list_comments",
        dependency=get_comment_usecases,
        method_name="list_comments",
        http_method="GET",
        path="/api/instagram/comment/acc-1/media-123",
        params={"amount": 0},
    ),
    RouteCase(
        name="comment:list_comments_page",
        dependency=get_comment_usecases,
        method_name="list_comments_page",
        http_method="GET",
        path="/api/instagram/comment/acc-1/media-123/page",
        params={"page_size": 20, "cursor": "cursor-1"},
    ),
    RouteCase(
        name="comment:delete_comment",
        dependency=get_comment_usecases,
        method_name="delete_comment",
        http_method="POST",
        path="/api/instagram/comment/delete",
        json_body={"account_id": "acc-1", "media_id": "media-1", "comment_id": 99},
    ),
    RouteCase(
        name="comment:like_comment",
        dependency=get_comment_usecases,
        method_name="like_comment",
        http_method="POST",
        path="/api/instagram/comment/like",
        json_body={"account_id": "acc-1", "comment_id": 99},
    ),
    RouteCase(
        name="comment:unlike_comment",
        dependency=get_comment_usecases,
        method_name="unlike_comment",
        http_method="POST",
        path="/api/instagram/comment/unlike",
        json_body={"account_id": "acc-1", "comment_id": 99},
    ),
    RouteCase(
        name="comment:pin_comment",
        dependency=get_comment_usecases,
        method_name="pin_comment",
        http_method="POST",
        path="/api/instagram/comment/pin",
        json_body={"account_id": "acc-1", "media_id": "media-1", "comment_id": 99},
    ),
    RouteCase(
        name="comment:unpin_comment",
        dependency=get_comment_usecases,
        method_name="unpin_comment",
        http_method="POST",
        path="/api/instagram/comment/unpin",
        json_body={"account_id": "acc-1", "media_id": "media-1", "comment_id": 99},
    ),
    # Story router
    RouteCase(
        name="story:get_story_pk_from_url",
        dependency=get_story_usecases,
        method_name="get_story_pk_from_url",
        http_method="GET",
        path="/api/instagram/story/pk-from-url",
        params={"url": "https://www.instagram.com/stories/user/123/"},
    ),
    RouteCase(
        name="story:get_story",
        dependency=get_story_usecases,
        method_name="get_story",
        http_method="GET",
        path="/api/instagram/story/acc-1/123",
        params={"use_cache": "true"},
    ),
    RouteCase(
        name="story:list_user_stories",
        dependency=get_story_usecases,
        method_name="list_user_stories",
        http_method="GET",
        path="/api/instagram/story/acc-1/user/777",
        params={"amount": 5},
    ),
    RouteCase(
        name="story:publish_story",
        dependency=get_story_usecases,
        method_name="publish_story",
        http_method="POST",
        path="/api/instagram/story/publish",
        json_body={
            "account_id": "acc-1",
            "media_kind": "photo",
            "media_path": "/tmp/story.jpg",
            "caption": "story",
            "audience": "default",
        },
    ),
    RouteCase(
        name="story:delete_story",
        dependency=get_story_usecases,
        method_name="delete_story",
        http_method="POST",
        path="/api/instagram/story/delete",
        json_body={"account_id": "acc-1", "story_pk": 123},
    ),
    RouteCase(
        name="story:mark_seen",
        dependency=get_story_usecases,
        method_name="mark_seen",
        http_method="POST",
        path="/api/instagram/story/mark-seen",
        json_body={"account_id": "acc-1", "story_pks": [1, 2], "skipped_story_pks": [3]},
    ),
    # Highlight router
    RouteCase(
        name="highlight:get_highlight_pk_from_url",
        dependency=get_highlight_usecases,
        method_name="get_highlight_pk_from_url",
        http_method="GET",
        path="/api/instagram/highlight/pk-from-url",
        params={"url": "https://www.instagram.com/stories/highlights/123/"},
    ),
    RouteCase(
        name="highlight:get_highlight",
        dependency=get_highlight_usecases,
        method_name="get_highlight",
        http_method="GET",
        path="/api/instagram/highlight/acc-1/123",
    ),
    RouteCase(
        name="highlight:list_user_highlights",
        dependency=get_highlight_usecases,
        method_name="list_user_highlights",
        http_method="GET",
        path="/api/instagram/highlight/acc-1/user/777",
        params={"amount": 1},
    ),
    RouteCase(
        name="highlight:create_highlight",
        dependency=get_highlight_usecases,
        method_name="create_highlight",
        http_method="POST",
        path="/api/instagram/highlight/create",
        json_body={
            "account_id": "acc-1",
            "title": "Best",
            "story_ids": [1, 2],
            "cover_story_id": 1,
        },
    ),
    RouteCase(
        name="highlight:change_title",
        dependency=get_highlight_usecases,
        method_name="change_title",
        http_method="POST",
        path="/api/instagram/highlight/change-title",
        json_body={"account_id": "acc-1", "highlight_pk": 123, "title": "Updated"},
    ),
    RouteCase(
        name="highlight:add_stories",
        dependency=get_highlight_usecases,
        method_name="add_stories",
        http_method="POST",
        path="/api/instagram/highlight/add-stories",
        json_body={"account_id": "acc-1", "highlight_pk": 123, "story_ids": [3]},
    ),
    RouteCase(
        name="highlight:remove_stories",
        dependency=get_highlight_usecases,
        method_name="remove_stories",
        http_method="POST",
        path="/api/instagram/highlight/remove-stories",
        json_body={"account_id": "acc-1", "highlight_pk": 123, "story_ids": [3]},
    ),
    RouteCase(
        name="highlight:delete_highlight",
        dependency=get_highlight_usecases,
        method_name="delete_highlight",
        http_method="POST",
        path="/api/instagram/highlight/delete",
        json_body={"account_id": "acc-1", "highlight_pk": 123},
    ),
    # Relationship read routes
    RouteCase(
        name="relationships:list_followers",
        dependency=get_relationship_usecases,
        method_name="list_followers",
        http_method="GET",
        path="/api/instagram/relationships/acc-1/followers",
        params={"username": "target", "amount": 1},
    ),
    RouteCase(
        name="relationships:list_following",
        dependency=get_relationship_usecases,
        method_name="list_following",
        http_method="GET",
        path="/api/instagram/relationships/acc-1/following",
        params={"username": "target", "amount": 1},
    ),
    RouteCase(
        name="relationships:search_followers",
        dependency=get_relationship_usecases,
        method_name="search_followers",
        http_method="GET",
        path="/api/instagram/relationships/acc-1/followers/search",
        params={"username": "target", "query": "ta"},
    ),
    RouteCase(
        name="relationships:search_following",
        dependency=get_relationship_usecases,
        method_name="search_following",
        http_method="GET",
        path="/api/instagram/relationships/acc-1/following/search",
        params={"username": "target", "query": "ta"},
    ),
)

RELATIONSHIP_READ_REQUESTS: tuple[tuple[str, dict[str, Any]], ...] = (
    (
        "/api/instagram/relationships/acc-1/followers",
        {"username": "target", "amount": 1},
    ),
    (
        "/api/instagram/relationships/acc-1/following",
        {"username": "target", "amount": 1},
    ),
    (
        "/api/instagram/relationships/acc-1/followers/search",
        {"username": "target", "query": "ta"},
    ),
    (
        "/api/instagram/relationships/acc-1/following/search",
        {"username": "target", "query": "ta"},
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


def _build_relationship_usecases_with_wrapped_resolution_failure(
    *,
    failure: InstagramFailure,
) -> tuple[RelationshipUseCases, Mock, Mock]:
    account_repo = Mock()
    account_repo.get.return_value = {"username": "operator"}
    client_repo = Mock()
    client_repo.exists.return_value = True
    identity_reader = Mock()
    relationship_reader = Mock()

    def _raise_wrapped(*_args, **_kwargs):
        source = ValueError(failure.user_message)
        source._instagram_failure = failure  # type: ignore[attr-defined]
        raise ValueError(failure.user_message) from source

    identity_reader.get_public_user_by_username.side_effect = _raise_wrapped

    return (
        RelationshipUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            identity_reader=identity_reader,
            relationship_reader=relationship_reader,
        ),
        identity_reader,
        relationship_reader,
    )


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


@pytest.mark.parametrize(
    ("path", "params"),
    RELATIONSHIP_READ_REQUESTS,
    ids=(
        "relationships:list_followers",
        "relationships:list_following",
        "relationships:search_followers",
        "relationships:search_following",
    ),
)
def test_relationship_read_username_resolution_wrapped_rate_limit_maps_to_429(
    app: FastAPI,
    client: TestClient,
    path: str,
    params: dict[str, Any],
):
    failure = InstagramFailure(
        code="rate_limit",
        family="common_client",
        retryable=True,
        requires_user_action=False,
        user_message="Rate limited. Please wait a moment.",
        http_hint=429,
    )
    usecases, identity_reader, relationship_reader = (
        _build_relationship_usecases_with_wrapped_resolution_failure(failure=failure)
    )
    app.dependency_overrides[get_relationship_usecases] = lambda: usecases
    try:
        response = client.get(path, params=params)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.json()["detail"] == {
        "message": "Rate limited. Please wait a moment.",
        "code": "rate_limit",
        "family": "common_client",
    }
    identity_reader.get_public_user_by_username.assert_called_once_with(
        "acc-1", "target"
    )
    assert relationship_reader.mock_calls == []


@pytest.mark.parametrize(
    ("path", "params"),
    RELATIONSHIP_READ_REQUESTS,
    ids=(
        "relationships:list_followers",
        "relationships:list_following",
        "relationships:search_followers",
        "relationships:search_following",
    ),
)
def test_relationship_read_username_resolution_wrapped_unauthorized_maps_to_401(
    app: FastAPI,
    client: TestClient,
    path: str,
    params: dict[str, Any],
):
    failure = InstagramFailure(
        code="login_required",
        family="private_auth",
        retryable=False,
        requires_user_action=True,
        user_message="Login required. Please re-authenticate.",
        http_hint=401,
    )
    usecases, identity_reader, relationship_reader = (
        _build_relationship_usecases_with_wrapped_resolution_failure(failure=failure)
    )
    app.dependency_overrides[get_relationship_usecases] = lambda: usecases
    try:
        response = client.get(path, params=params)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"] == {
        "message": "Login required. Please re-authenticate.",
        "code": "login_required",
        "family": "private_auth",
    }
    identity_reader.get_public_user_by_username.assert_called_once_with(
        "acc-1", "target"
    )
    assert relationship_reader.mock_calls == []
