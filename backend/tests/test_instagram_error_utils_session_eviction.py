"""Tests for dead-session eviction side effects in Instagram error translation."""

from __future__ import annotations

import pytest

from app.adapters.instagram.error_utils import translate_instagram_error
from app.adapters.instagram.exception_catalog import SPEC_CLIENT_UNAUTHORIZED_ERROR
from app.domain.instagram_failures import InstagramFailure


class _StubClientRepo:
    def __init__(self, *, exists: bool = True) -> None:
        self._exists = exists
        self.removed: list[str] = []

    def exists(self, account_id: str) -> bool:
        return self._exists

    def remove(self, account_id: str) -> None:
        self.removed.append(account_id)


class _StubStatusRepo:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def set(self, account_id: str, status: str) -> None:
        self.calls.append((account_id, status))


class _StubAccountRepo:
    def __init__(self, username: str = "alice") -> None:
        self._account = {"username": username}
        self.lookups: list[str] = []

    def get(self, account_id: str) -> dict:
        self.lookups.append(account_id)
        return self._account


class _StubSessionStore:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete_session(self, username: str) -> None:
        self.deleted.append(username)


def _failure(
    *,
    code: str,
    family: str,
    retryable: bool = False,
    requires_user_action: bool = True,
    http_hint: int = 401,
    user_message: str = "Auth failure",
) -> InstagramFailure:
    return InstagramFailure(
        code=code,
        family=family,
        retryable=retryable,
        requires_user_action=requires_user_action,
        user_message=user_message,
        http_hint=http_hint,
    )


@pytest.mark.parametrize(
    ("code", "family", "requires_user_action"),
    [
        ("login_required", "private_auth", True),
        ("pre_login_required", "private_auth", True),
        ("unauthorized", "private_auth", True),
        # Regression guard: old unauthorized classification drift must still evict.
        ("unauthorized", "common_client", False),
    ],
)
def test_dead_auth_codes_evict_runtime_and_persisted_session(
    monkeypatch: pytest.MonkeyPatch,
    code: str,
    family: str,
    requires_user_action: bool,
) -> None:
    failure = _failure(
        code=code,
        family=family,
        requires_user_action=requires_user_action,
    )

    client_repo = _StubClientRepo(exists=True)
    status_repo = _StubStatusRepo()
    account_repo = _StubAccountRepo(username="alice")
    session_store = _StubSessionStore()
    services = {
        "_client_repo": client_repo,
        "_status_repo": status_repo,
        "_account_repo": account_repo,
        "session_store": session_store,
    }

    monkeypatch.setattr(
        "app.adapters.instagram.error_utils.instagram_exception_handler.handle",
        lambda *_args, **_kwargs: failure,
    )
    monkeypatch.setattr(
        "app.adapters.http.dependencies.get_services",
        lambda: services,
    )

    translated = translate_instagram_error(
        RuntimeError("upstream unauthorized"),
        operation="get_authenticated_account",
        account_id="acc-1",
        username="alice",
    )

    assert translated is failure
    assert client_repo.removed == ["acc-1"]
    assert status_repo.calls == [("acc-1", "error")]
    assert account_repo.lookups == ["acc-1"]
    assert session_store.deleted == ["alice"]


@pytest.mark.parametrize(
    ("code", "family", "requires_user_action", "http_hint"),
    [
        ("two_factor_required", "private_auth", True, 409),
        ("bad_password", "private_auth", True, 401),
        ("challenge_required", "challenge", True, 409),
    ],
)
def test_user_action_flows_do_not_auto_evict(
    monkeypatch: pytest.MonkeyPatch,
    code: str,
    family: str,
    requires_user_action: bool,
    http_hint: int,
) -> None:
    failure = _failure(
        code=code,
        family=family,
        requires_user_action=requires_user_action,
        http_hint=http_hint,
    )

    client_repo = _StubClientRepo(exists=True)
    status_repo = _StubStatusRepo()
    account_repo = _StubAccountRepo(username="alice")
    session_store = _StubSessionStore()
    services = {
        "_client_repo": client_repo,
        "_status_repo": status_repo,
        "_account_repo": account_repo,
        "session_store": session_store,
    }

    monkeypatch.setattr(
        "app.adapters.instagram.error_utils.instagram_exception_handler.handle",
        lambda *_args, **_kwargs: failure,
    )
    monkeypatch.setattr(
        "app.adapters.http.dependencies.get_services",
        lambda: services,
    )

    translated = translate_instagram_error(
        RuntimeError("manual-action failure"),
        operation="get_authenticated_account",
        account_id="acc-1",
        username="alice",
    )

    assert translated is failure
    assert client_repo.removed == []
    assert status_repo.calls == []
    assert account_repo.lookups == []
    assert session_store.deleted == []


def test_dead_auth_without_account_context_does_not_evict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = _failure(code="unauthorized", family="private_auth")

    monkeypatch.setattr(
        "app.adapters.instagram.error_utils.instagram_exception_handler.handle",
        lambda *_args, **_kwargs: failure,
    )

    get_services_called = False

    def _unexpected_services():
        nonlocal get_services_called
        get_services_called = True
        return {}

    monkeypatch.setattr(
        "app.adapters.http.dependencies.get_services",
        _unexpected_services,
    )

    translated = translate_instagram_error(
        RuntimeError("unauthorized"),
        operation="get_authenticated_account",
        account_id=None,
    )

    assert translated is failure
    assert get_services_called is False


def test_client_unauthorized_spec_is_classified_as_private_auth() -> None:
    assert SPEC_CLIENT_UNAUTHORIZED_ERROR.code == "unauthorized"
    assert SPEC_CLIENT_UNAUTHORIZED_ERROR.family == "private_auth"
    assert SPEC_CLIENT_UNAUTHORIZED_ERROR.retryable is False
    assert SPEC_CLIENT_UNAUTHORIZED_ERROR.requires_user_action is True
    assert SPEC_CLIENT_UNAUTHORIZED_ERROR.http_hint == 401
