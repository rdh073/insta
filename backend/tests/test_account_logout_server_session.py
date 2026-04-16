"""Regression tests for server-side Instagram session invalidation on logout.

These tests cover both ``AccountAuthUseCases`` (wired to the HTTP router
via ``services["account_auth"]``) and ``AuthUseCases`` (used by the
``AccountUseCases`` facade).  Both paths must invoke ``client.logout()``
on the live instagrapi client so the server-side mobile session is
terminated, while still completing local cleanup when the network call
fails.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.application.dto.account_dto import AccountResponse
from app.application.use_cases.account.auth import AuthUseCases
from app.application.use_cases.account_auth import AccountAuthUseCases
from app.domain.instagram_failures import InstagramFailure


class _SpyClient:
    """Minimal double that records how many times ``logout()`` ran."""

    def __init__(self, raise_exc: Exception | None = None) -> None:
        self._raise_exc = raise_exc
        self.logout_calls = 0

    def logout(self) -> None:
        self.logout_calls += 1
        if self._raise_exc is not None:
            raise self._raise_exc


def _failure(code: str = "unknown_instagram_error") -> InstagramFailure:
    return InstagramFailure(
        code=code,
        family="network",
        retryable=True,
        requires_user_action=False,
        user_message="Server logout failed; local state cleared.",
        http_hint=500,
    )


def _make_account_auth_usecases(
    *,
    client,
    error_handler: Mock | None = None,
) -> tuple[AccountAuthUseCases, Mock, Mock, Mock, Mock, Mock]:
    account_repo = Mock()
    client_repo = Mock()
    status_repo = Mock()
    logger = Mock()
    session_store = Mock()
    handler = error_handler or Mock()

    account_repo.exists.return_value = True
    account_repo.get.return_value = {"username": "alice"}
    client_repo.remove.return_value = client

    usecase = AccountAuthUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        status_repo=status_repo,
        instagram=Mock(),
        logger=logger,
        totp=Mock(),
        session_store=session_store,
        error_handler=handler,
        identity_reader=Mock(),
        uow=None,
    )
    return usecase, account_repo, client_repo, status_repo, logger, session_store


def _make_auth_usecases(
    *,
    client,
    error_handler: Mock | None = None,
) -> tuple[AuthUseCases, Mock, Mock, Mock, Mock, Mock]:
    account_repo = Mock()
    client_repo = Mock()
    status_repo = Mock()
    logger = Mock()
    session_store = Mock()
    handler = error_handler or Mock()

    account_repo.exists.return_value = True
    account_repo.get.return_value = {"username": "alice"}
    client_repo.remove.return_value = client

    usecase = AuthUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        status_repo=status_repo,
        instagram=Mock(),
        logger=logger,
        totp=Mock(),
        session_store=session_store,
        error_handler=handler,
        identity_reader=Mock(),
        uow=None,
    )
    return usecase, account_repo, client_repo, status_repo, logger, session_store


# ── AccountAuthUseCases (HTTP path via services["account_auth"]) ────────────


def test_account_auth_logout_invokes_client_logout_exactly_once():
    client = _SpyClient()
    usecase, account_repo, client_repo, status_repo, _logger, session_store = (
        _make_account_auth_usecases(client=client)
    )

    result = usecase.logout_account("acc-1")

    assert client.logout_calls == 1
    client_repo.remove.assert_called_once_with("acc-1")
    session_store.delete_session.assert_called_once_with("alice")
    status_repo.clear.assert_called_once_with("acc-1")
    account_repo.remove.assert_called_once_with("acc-1")
    assert isinstance(result, AccountResponse)
    assert result.status == "removed"
    assert result.server_logout == "success"


def test_account_auth_logout_records_failed_and_still_cleans_up_on_http_error():
    import requests

    client = _SpyClient(raise_exc=requests.HTTPError("400 logout failed"))
    error_handler = Mock()
    error_handler.handle.return_value = _failure("unknown_instagram_error")

    usecase, account_repo, _client_repo, status_repo, logger, session_store = (
        _make_account_auth_usecases(client=client, error_handler=error_handler)
    )

    result = usecase.logout_account("acc-1")

    assert client.logout_calls == 1
    error_handler.handle.assert_called_once()
    assert error_handler.handle.call_args.kwargs["operation"] == "logout"
    # Local cleanup still runs even when server call fails.
    session_store.delete_session.assert_called_once_with("alice")
    status_repo.clear.assert_called_once_with("acc-1")
    account_repo.remove.assert_called_once_with("acc-1")
    assert result.status == "removed"
    assert result.server_logout == "failed"

    logged_details = [
        call.kwargs.get("detail") for call in logger.log_event.call_args_list
    ]
    assert any(
        isinstance(d, str) and d.startswith("server_logout_failed")
        for d in logged_details
    )


def test_account_auth_logout_records_failed_for_login_required():
    from instagrapi.exceptions import LoginRequired

    client = _SpyClient(raise_exc=LoginRequired("session already invalid"))
    error_handler = Mock()
    error_handler.handle.return_value = _failure("login_required")

    usecase, _account_repo, _client_repo, _status_repo, _logger, _session = (
        _make_account_auth_usecases(client=client, error_handler=error_handler)
    )

    result = usecase.logout_account("acc-1")

    assert client.logout_calls == 1
    assert result.server_logout == "failed"


def test_account_auth_logout_skips_network_when_client_not_present():
    usecase, account_repo, client_repo, status_repo, _logger, session_store = (
        _make_account_auth_usecases(client=None)
    )

    result = usecase.logout_account("acc-1")

    client_repo.remove.assert_called_once_with("acc-1")
    # With no client, no network call should happen.
    session_store.delete_session.assert_called_once_with("alice")
    status_repo.clear.assert_called_once_with("acc-1")
    account_repo.remove.assert_called_once_with("acc-1")
    assert result.server_logout == "not_present"
    assert result.status == "removed"


def test_account_auth_bulk_logout_preserves_server_logout_per_account():
    client_a = _SpyClient()
    client_b = _SpyClient(raise_exc=RuntimeError("boom"))
    error_handler = Mock()
    error_handler.handle.return_value = _failure("unknown_instagram_error")

    account_repo = Mock()
    client_repo = Mock()
    status_repo = Mock()
    logger = Mock()
    session_store = Mock()

    def _exists(aid: str) -> bool:
        return aid in {"acc-1", "acc-2"}

    def _get(aid: str):
        return {"acc-1": {"username": "alice"}, "acc-2": {"username": "bob"}}.get(aid)

    def _remove_client(aid: str):
        return {"acc-1": client_a, "acc-2": client_b}.get(aid)

    account_repo.exists.side_effect = _exists
    account_repo.get.side_effect = _get
    client_repo.remove.side_effect = _remove_client

    usecase = AccountAuthUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        status_repo=status_repo,
        instagram=Mock(),
        logger=logger,
        totp=Mock(),
        session_store=session_store,
        error_handler=error_handler,
        identity_reader=Mock(),
        uow=None,
    )

    results = usecase.bulk_logout_accounts(["acc-1", "acc-2", "missing"])

    assert len(results) == 3
    by_id = {r.id: r for r in results}
    assert by_id["acc-1"].server_logout == "success"
    assert by_id["acc-1"].status == "removed"
    assert by_id["acc-2"].server_logout == "failed"
    assert by_id["acc-2"].status == "removed"
    assert by_id["missing"].status == "not_found"
    assert by_id["missing"].server_logout is None
    assert client_a.logout_calls == 1
    assert client_b.logout_calls == 1


# ── AuthUseCases (facade path via AccountUseCases) ──────────────────────────


def test_auth_usecases_logout_invokes_client_logout_exactly_once():
    client = _SpyClient()
    usecase, account_repo, client_repo, status_repo, _logger, session_store = (
        _make_auth_usecases(client=client)
    )

    result = usecase.logout_account("acc-1")

    assert client.logout_calls == 1
    client_repo.remove.assert_called_once_with("acc-1")
    session_store.delete_session.assert_called_once_with("alice")
    status_repo.clear.assert_called_once_with("acc-1")
    account_repo.remove.assert_called_once_with("acc-1")
    assert result.server_logout == "success"


def test_auth_usecases_logout_still_cleans_up_on_http_error():
    import requests

    client = _SpyClient(raise_exc=requests.HTTPError("401"))
    error_handler = Mock()
    error_handler.handle.return_value = _failure("login_required")

    usecase, account_repo, _client_repo, status_repo, logger, session_store = (
        _make_auth_usecases(client=client, error_handler=error_handler)
    )

    result = usecase.logout_account("acc-1")

    session_store.delete_session.assert_called_once_with("alice")
    status_repo.clear.assert_called_once_with("acc-1")
    account_repo.remove.assert_called_once_with("acc-1")
    assert result.status == "removed"
    assert result.server_logout == "failed"
    details = [c.kwargs.get("detail") for c in logger.log_event.call_args_list]
    assert any(
        isinstance(d, str) and d.startswith("server_logout_failed") for d in details
    )


def test_auth_usecases_logout_skips_network_when_no_client():
    usecase, _account_repo, _client_repo, _status_repo, _logger, _session = (
        _make_auth_usecases(client=None)
    )

    result = usecase.logout_account("acc-1")

    assert result.server_logout == "not_present"


def test_auth_usecases_logout_not_found_raises_value_error():
    usecase, account_repo, _client_repo, _status_repo, _logger, _session = (
        _make_auth_usecases(client=None)
    )
    account_repo.exists.return_value = False

    with pytest.raises(ValueError, match="Account not found"):
        usecase.logout_account("missing")
