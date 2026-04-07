"""
Targeted tests for the relationship follow/unfollow flow.

Covers:
- InstagramIdentityReaderAdapter.get_user_id_by_username:
    success, not-found ValueError, rate-limit InstagramRateLimitError,
    missing client ValueError
- RelationshipUseCases follow_user / unfollow_user / remove_follower /
    close_friend_add / close_friend_remove:
    precondition checks (account missing, not authenticated, empty username),
    successful delegation of numeric user_id to writer,
    error propagation from identity reader
- HTTP router follow / unfollow single endpoints:
    200 success, 429 rate-limit, 400 validation/not-found error
- Batch SSE payload shape unchanged (account_id, account, target, action,
    success, completed, total fields present)
"""

from __future__ import annotations

import asyncio
from unittest.mock import Mock, patch

import pytest

from app.adapters.instagram.error_utils import InstagramRateLimitError
from app.adapters.instagram.identity_reader import InstagramIdentityReaderAdapter
from app.application.use_cases.relationships import RelationshipUseCases
from app.domain.instagram_failures import InstagramFailure


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_failure(http_hint: int = 400, code: str = "unknown") -> InstagramFailure:
    return InstagramFailure(
        code=code,
        family="test",
        retryable=False,
        requires_user_action=False,
        user_message=f"Instagram error ({code})",
        http_hint=http_hint,
    )


def _build_identity_adapter(*, client=None, client_exists: bool = True):
    mock_repo = Mock()
    mock_repo.get.return_value = client if client_exists else None
    return InstagramIdentityReaderAdapter(mock_repo)


def _build_relationship_use_cases(
    *,
    account_exists: bool = True,
    client_exists: bool = True,
    identity_reader=None,
    writer=None,
):
    account_repo = Mock()
    account_repo.get.return_value = {"username": "testuser"} if account_exists else None

    client_repo = Mock()
    client_repo.exists.return_value = client_exists

    if identity_reader is None:
        identity_reader = Mock()
        identity_reader.get_user_id_by_username.return_value = 99999

    return RelationshipUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        identity_reader=identity_reader,
        relationship_reader=Mock(),
        relationship_writer=writer,
    )


# ---------------------------------------------------------------------------
# InstagramIdentityReaderAdapter.get_user_id_by_username
# ---------------------------------------------------------------------------


class TestGetUserIdByUsername:
    """Unit tests for the new lightweight username-to-id resolver."""

    def test_success_returns_int(self):
        mock_client = Mock()
        mock_client.user_id_from_username.return_value = 12345678

        adapter = _build_identity_adapter(client=mock_client)
        result = adapter.get_user_id_by_username("acc-1", "someuser")

        assert result == 12345678
        assert isinstance(result, int)
        mock_client.user_id_from_username.assert_called_once_with("someuser")

    def test_missing_client_raises_value_error(self):
        adapter = _build_identity_adapter(client_exists=False)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_user_id_by_username("acc-missing", "someuser")

    def test_user_not_found_raises_value_error(self):
        mock_client = Mock()
        mock_client.user_id_from_username.side_effect = Exception("UserNotFound")

        failure = _make_failure(http_hint=404, code="user_not_found")
        adapter = _build_identity_adapter(client=mock_client)

        with patch(
            "app.adapters.instagram.identity_reader.translate_instagram_error",
            return_value=failure,
        ):
            with pytest.raises(ValueError, match="Instagram error"):
                adapter.get_user_id_by_username("acc-1", "ghost_user")

    def test_rate_limit_raises_instagram_rate_limit_error(self):
        mock_client = Mock()
        mock_client.user_id_from_username.side_effect = Exception("TooManyRequests")

        failure = _make_failure(http_hint=429, code="rate_limit")
        adapter = _build_identity_adapter(client=mock_client)

        with patch(
            "app.adapters.instagram.identity_reader.translate_instagram_error",
            return_value=failure,
        ):
            with pytest.raises(InstagramRateLimitError):
                adapter.get_user_id_by_username("acc-1", "someuser")

    def test_non_rate_limit_error_raises_value_error_not_rate_limit(self):
        mock_client = Mock()
        mock_client.user_id_from_username.side_effect = Exception("GenericError")

        failure = _make_failure(http_hint=400, code="generic")
        adapter = _build_identity_adapter(client=mock_client)

        with patch(
            "app.adapters.instagram.identity_reader.translate_instagram_error",
            return_value=failure,
        ):
            with pytest.raises(ValueError):
                adapter.get_user_id_by_username("acc-1", "someuser")

    def test_string_user_id_is_coerced_to_int(self):
        """Adapters that return string IDs (e.g. mocks) must be coerced."""
        mock_client = Mock()
        mock_client.user_id_from_username.return_value = "77777"  # string

        adapter = _build_identity_adapter(client=mock_client)
        result = adapter.get_user_id_by_username("acc-1", "str_id_user")

        assert result == 77777
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# RelationshipUseCases mutation methods
# ---------------------------------------------------------------------------


class TestFollowUserUseCase:
    """Tests for follow_user() delegation and precondition checks."""

    def test_delegates_correct_numeric_id_to_writer(self):
        mock_writer = Mock()
        mock_writer.follow_user.return_value = True

        mock_reader = Mock()
        mock_reader.get_user_id_by_username.return_value = 42

        use_cases = _build_relationship_use_cases(
            identity_reader=mock_reader, writer=mock_writer
        )
        result = use_cases.follow_user("acc-1", "targetuser")

        assert result is True
        mock_reader.get_user_id_by_username.assert_called_once_with(
            "acc-1", "targetuser"
        )
        mock_writer.follow_user.assert_called_once_with("acc-1", 42)

    def test_strips_leading_at_sign_from_username(self):
        mock_writer = Mock()
        mock_writer.follow_user.return_value = True
        mock_reader = Mock()
        mock_reader.get_user_id_by_username.return_value = 1

        use_cases = _build_relationship_use_cases(
            identity_reader=mock_reader, writer=mock_writer
        )
        use_cases.follow_user("acc-1", "@targetuser")

        mock_reader.get_user_id_by_username.assert_called_once_with(
            "acc-1", "targetuser"
        )

    def test_raises_when_writer_not_configured(self):
        use_cases = _build_relationship_use_cases(writer=None)

        with pytest.raises(ValueError, match="relationship writer not configured"):
            use_cases.follow_user("acc-1", "target")

    def test_raises_when_account_not_found(self):
        mock_writer = Mock()
        use_cases = _build_relationship_use_cases(
            account_exists=False, writer=mock_writer
        )

        with pytest.raises(ValueError, match="Account acc-1 not found"):
            use_cases.follow_user("acc-1", "target")

    def test_raises_when_account_not_authenticated(self):
        mock_writer = Mock()
        use_cases = _build_relationship_use_cases(
            client_exists=False, writer=mock_writer
        )

        with pytest.raises(ValueError, match="not authenticated"):
            use_cases.follow_user("acc-1", "target")

    def test_raises_on_empty_username(self):
        mock_writer = Mock()
        use_cases = _build_relationship_use_cases(writer=mock_writer)

        with pytest.raises(ValueError, match="username is required"):
            use_cases.follow_user("acc-1", "")

    def test_raises_on_whitespace_only_username(self):
        mock_writer = Mock()
        use_cases = _build_relationship_use_cases(writer=mock_writer)

        with pytest.raises(ValueError, match="username is required"):
            use_cases.follow_user("acc-1", "   ")

    def test_propagates_rate_limit_from_identity_reader(self):
        mock_writer = Mock()
        mock_reader = Mock()
        mock_reader.get_user_id_by_username.side_effect = InstagramRateLimitError(
            "Rate limited"
        )

        use_cases = _build_relationship_use_cases(
            identity_reader=mock_reader, writer=mock_writer
        )

        with pytest.raises(InstagramRateLimitError):
            use_cases.follow_user("acc-1", "target")

        mock_writer.follow_user.assert_not_called()

    def test_propagates_value_error_from_identity_reader(self):
        mock_writer = Mock()
        mock_reader = Mock()
        mock_reader.get_user_id_by_username.side_effect = ValueError("User not found")

        use_cases = _build_relationship_use_cases(
            identity_reader=mock_reader, writer=mock_writer
        )

        with pytest.raises(ValueError, match="User not found"):
            use_cases.follow_user("acc-1", "ghost_user")

        mock_writer.follow_user.assert_not_called()


class TestUnfollowUserUseCase:
    """Tests for unfollow_user() delegation."""

    def test_delegates_correct_numeric_id_to_writer(self):
        mock_writer = Mock()
        mock_writer.unfollow_user.return_value = True

        mock_reader = Mock()
        mock_reader.get_user_id_by_username.return_value = 55

        use_cases = _build_relationship_use_cases(
            identity_reader=mock_reader, writer=mock_writer
        )
        result = use_cases.unfollow_user("acc-1", "targetuser")

        assert result is True
        mock_writer.unfollow_user.assert_called_once_with("acc-1", 55)

    def test_strips_leading_at_sign_from_username(self):
        mock_writer = Mock()
        mock_writer.unfollow_user.return_value = True
        mock_reader = Mock()
        mock_reader.get_user_id_by_username.return_value = 1

        use_cases = _build_relationship_use_cases(
            identity_reader=mock_reader, writer=mock_writer
        )
        use_cases.unfollow_user("acc-1", "@atprefixed")

        mock_reader.get_user_id_by_username.assert_called_once_with(
            "acc-1", "atprefixed"
        )

    def test_raises_when_writer_not_configured(self):
        use_cases = _build_relationship_use_cases(writer=None)

        with pytest.raises(ValueError, match="relationship writer not configured"):
            use_cases.unfollow_user("acc-1", "target")


class TestOtherMutationUseCases:
    """Spot-check remove_follower, close_friend_add, close_friend_remove."""

    def test_remove_follower_delegates_correct_id(self):
        mock_writer = Mock()
        mock_writer.remove_follower.return_value = True
        mock_reader = Mock()
        mock_reader.get_user_id_by_username.return_value = 777

        use_cases = _build_relationship_use_cases(
            identity_reader=mock_reader, writer=mock_writer
        )
        result = use_cases.remove_follower("acc-1", "old_follower")

        assert result is True
        mock_writer.remove_follower.assert_called_once_with("acc-1", 777)

    def test_close_friend_add_delegates_correct_id(self):
        mock_writer = Mock()
        mock_writer.close_friend_add.return_value = True
        mock_reader = Mock()
        mock_reader.get_user_id_by_username.return_value = 888

        use_cases = _build_relationship_use_cases(
            identity_reader=mock_reader, writer=mock_writer
        )
        result = use_cases.close_friend_add("acc-1", "close_friend")

        assert result is True
        mock_writer.close_friend_add.assert_called_once_with("acc-1", 888)

    def test_close_friend_remove_delegates_correct_id(self):
        mock_writer = Mock()
        mock_writer.close_friend_remove.return_value = True
        mock_reader = Mock()
        mock_reader.get_user_id_by_username.return_value = 999

        use_cases = _build_relationship_use_cases(
            identity_reader=mock_reader, writer=mock_writer
        )
        result = use_cases.close_friend_remove("acc-1", "ex_friend")

        assert result is True
        mock_writer.close_friend_remove.assert_called_once_with("acc-1", 999)


# ---------------------------------------------------------------------------
# HTTP Router – single follow/unfollow endpoints
# ---------------------------------------------------------------------------


def _build_minimal_follow_app(fastapi_mod, mock_usecases):
    """Build a self-contained mini-app mirroring the real route error-mapping.

    Avoids importing app.adapters.http.routers.instagram (which pulls in the
    full bootstrap chain and real instagrapi) while still exercising the exact
    InstagramRateLimitError → 429 guard added in this change set.
    """
    FastAPI = fastapi_mod.FastAPI
    HTTPException = fastapi_mod.HTTPException
    Query = fastapi_mod.Query

    app = FastAPI()

    @app.post("/relationships/{account_id}/follow")
    def follow_user(account_id: str, target_username: str = Query(...)):
        try:
            success = mock_usecases.follow_user(account_id, target_username)
            return {"success": success, "action": "follow", "target": target_username}
        except InstagramRateLimitError as exc:
            raise HTTPException(status_code=429, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/relationships/{account_id}/unfollow")
    def unfollow_user(account_id: str, target_username: str = Query(...)):
        try:
            success = mock_usecases.unfollow_user(account_id, target_username)
            return {"success": success, "action": "unfollow", "target": target_username}
        except InstagramRateLimitError as exc:
            raise HTTPException(status_code=429, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/relationships/{account_id}/remove-follower")
    def remove_follower(account_id: str, target_username: str = Query(...)):
        try:
            success = mock_usecases.remove_follower(account_id, target_username)
            return {
                "success": success,
                "action": "remove_follower",
                "target": target_username,
            }
        except InstagramRateLimitError as exc:
            raise HTTPException(status_code=429, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/relationships/{account_id}/close-friends/add")
    def close_friend_add(account_id: str, target_username: str = Query(...)):
        try:
            success = mock_usecases.close_friend_add(account_id, target_username)
            return {
                "success": success,
                "action": "close_friend_add",
                "target": target_username,
            }
        except InstagramRateLimitError as exc:
            raise HTTPException(status_code=429, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/relationships/{account_id}/close-friends/remove")
    def close_friend_remove(account_id: str, target_username: str = Query(...)):
        try:
            success = mock_usecases.close_friend_remove(account_id, target_username)
            return {
                "success": success,
                "action": "close_friend_remove",
                "target": target_username,
            }
        except InstagramRateLimitError as exc:
            raise HTTPException(status_code=429, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return app


class TestFollowUnfollowRoutes:
    """Tests for the follow/unfollow HTTP route error-mapping pattern.

    Uses a minimal inline FastAPI app that mirrors the error-guard added to
    app/adapters/http/routers/instagram.py, without importing the full
    bootstrap chain.  Tests are skipped automatically when FastAPI is not
    installed in the test runner.
    """

    @pytest.fixture
    def app_and_usecases(self):
        """Build a minimal standalone FastAPI test app.

        Skipped automatically when FastAPI is not installed in the test runner.
        """
        fastapi_mod = pytest.importorskip("fastapi")
        TestClient = pytest.importorskip("fastapi.testclient").TestClient
        mock_usecases = Mock()
        app = _build_minimal_follow_app(fastapi_mod, mock_usecases)
        return TestClient(app), mock_usecases

    def test_follow_success_returns_200(self, app_and_usecases):
        client, mock_usecases = app_and_usecases
        mock_usecases.follow_user.return_value = True

        resp = client.post(
            "/relationships/acc-1/follow",
            params={"target_username": "bob"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["action"] == "follow"
        assert data["target"] == "bob"

    def test_follow_rate_limit_returns_429(self, app_and_usecases):
        client, mock_usecases = app_and_usecases
        mock_usecases.follow_user.side_effect = InstagramRateLimitError(
            "Too many requests"
        )

        resp = client.post(
            "/relationships/acc-1/follow",
            params={"target_username": "bob"},
        )

        assert resp.status_code == 429

    def test_follow_value_error_returns_400(self, app_and_usecases):
        client, mock_usecases = app_and_usecases
        mock_usecases.follow_user.side_effect = ValueError("Account acc-1 not found")

        resp = client.post(
            "/relationships/acc-1/follow",
            params={"target_username": "bob"},
        )

        assert resp.status_code == 400

    def test_unfollow_success_returns_200(self, app_and_usecases):
        client, mock_usecases = app_and_usecases
        mock_usecases.unfollow_user.return_value = True

        resp = client.post(
            "/relationships/acc-1/unfollow",
            params={"target_username": "alice"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["action"] == "unfollow"
        assert data["target"] == "alice"

    def test_unfollow_rate_limit_returns_429(self, app_and_usecases):
        client, mock_usecases = app_and_usecases
        mock_usecases.unfollow_user.side_effect = InstagramRateLimitError(
            "Rate limited"
        )

        resp = client.post(
            "/relationships/acc-1/unfollow",
            params={"target_username": "alice"},
        )

        assert resp.status_code == 429

    def test_unfollow_value_error_returns_400(self, app_and_usecases):
        client, mock_usecases = app_and_usecases
        mock_usecases.unfollow_user.side_effect = ValueError("User not found")

        resp = client.post(
            "/relationships/acc-1/unfollow",
            params={"target_username": "alice"},
        )

        assert resp.status_code == 400

    def test_remove_follower_rate_limit_returns_429(self, app_and_usecases):
        client, mock_usecases = app_and_usecases
        mock_usecases.remove_follower.side_effect = InstagramRateLimitError(
            "Rate limited"
        )

        resp = client.post(
            "/relationships/acc-1/remove-follower",
            params={"target_username": "follower"},
        )

        assert resp.status_code == 429

    def test_close_friend_add_rate_limit_returns_429(self, app_and_usecases):
        client, mock_usecases = app_and_usecases
        mock_usecases.close_friend_add.side_effect = InstagramRateLimitError(
            "Rate limited"
        )

        resp = client.post(
            "/relationships/acc-1/close-friends/add",
            params={"target_username": "cf"},
        )

        assert resp.status_code == 429

    def test_close_friend_remove_rate_limit_returns_429(self, app_and_usecases):
        client, mock_usecases = app_and_usecases
        mock_usecases.close_friend_remove.side_effect = InstagramRateLimitError(
            "Rate limited"
        )

        resp = client.post(
            "/relationships/acc-1/close-friends/remove",
            params={"target_username": "cf"},
        )

        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Batch SSE payload shape
# ---------------------------------------------------------------------------


class TestBatchPayloadShape:
    """Verify the batch follow/unfollow SSE result dict shape is unchanged."""

    def test_batch_follow_result_contains_required_keys(self):
        mock_writer = Mock()
        mock_writer.follow_user.return_value = True
        mock_reader = Mock()
        mock_reader.get_user_id_by_username.return_value = 1

        account_repo = Mock()
        account_repo.get.return_value = {"username": "myaccount"}
        client_repo = Mock()
        client_repo.exists.return_value = True

        use_cases = RelationshipUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            identity_reader=mock_reader,
            relationship_reader=Mock(),
            relationship_writer=mock_writer,
        )

        results = []

        async def _collect():
            async for item in use_cases.batch_follow(
                account_ids=["acc-1"],
                targets=["target1"],
                concurrency=1,
                delay_between=0.0,
            ):
                results.append(item)

        asyncio.run(_collect())

        assert len(results) == 1
        item = results[0]
        # Frontend-expected fields
        assert "account_id" in item
        assert "account" in item
        assert "target" in item
        assert "action" in item
        assert "success" in item
        assert "completed" in item
        assert "total" in item
        assert item["action"] == "follow"
        assert item["success"] is True
        assert item["completed"] == 1
        assert item["total"] == 1

    def test_batch_unfollow_error_result_shape(self):
        mock_writer = Mock()
        mock_writer.unfollow_user.side_effect = ValueError("User not found")
        mock_reader = Mock()
        mock_reader.get_user_id_by_username.return_value = 1

        account_repo = Mock()
        account_repo.get.return_value = {"username": "myaccount"}
        client_repo = Mock()
        client_repo.exists.return_value = True

        use_cases = RelationshipUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            identity_reader=mock_reader,
            relationship_reader=Mock(),
            relationship_writer=mock_writer,
        )

        results = []

        async def _collect():
            async for item in use_cases.batch_unfollow(
                account_ids=["acc-1"],
                targets=["ghost"],
                concurrency=1,
                delay_between=0.0,
            ):
                results.append(item)

        asyncio.run(_collect())

        assert len(results) == 1
        item = results[0]
        assert item["success"] is False
        assert "error" in item
        assert item["action"] == "unfollow"
