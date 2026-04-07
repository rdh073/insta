"""Tests for Phase 2 identity boundary in AccountUseCases."""

from __future__ import annotations

from unittest.mock import Mock

from backend.app.application.dto.instagram_identity_dto import AuthenticatedAccountProfile
from backend.app.application.use_cases.account import AccountUseCases
from backend.app.domain.instagram_failures import InstagramFailure


def _build_usecase() -> tuple[AccountUseCases, Mock, Mock, Mock, Mock, Mock, Mock, Mock, Mock]:
    """Create AccountUseCases with mocked dependencies."""
    account_repo = Mock()
    client_repo = Mock()
    status_repo = Mock()
    instagram = Mock()
    logger = Mock()
    totp = Mock()
    session_store = Mock()
    error_handler = Mock()
    identity_reader = Mock()

    usecase = AccountUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        status_repo=status_repo,
        instagram=instagram,
        logger=logger,
        totp=totp,
        session_store=session_store,
        error_handler=error_handler,
        identity_reader=identity_reader,
    )
    return (
        usecase,
        account_repo,
        client_repo,
        status_repo,
        instagram,
        logger,
        error_handler,
        identity_reader,
        session_store,
    )


def test_get_account_info_uses_identity_reader_for_authenticated_profile():
    """get_account_info must read self-account through identity reader boundary."""
    (
        usecase,
        account_repo,
        client_repo,
        _status_repo,
        instagram,
        _logger,
        _error_handler,
        identity_reader,
        _session_store,
    ) = _build_usecase()

    account_repo.get.return_value = {"username": "alice"}
    client_repo.exists.return_value = True
    identity_reader.get_authenticated_account.return_value = AuthenticatedAccountProfile(
        pk=123,
        username="alice",
        full_name="Alice Doe",
        biography="Hello",
        is_private=False,
        is_verified=True,
        is_business=False,
        email="alice@example.com",
        phone_number="+620000000",
    )

    result = usecase.get_account_info("acc-1")

    identity_reader.get_authenticated_account.assert_called_once_with("acc-1")
    instagram.assert_not_called()
    account_repo.update.assert_called_once_with(
        "acc-1",
        full_name="Alice Doe",
        followers=None,
        following=None,
    )
    assert result.username == "alice"
    assert result.full_name == "Alice Doe"
    assert result.biography == "Hello"
    assert result.followers is None
    assert result.following is None
    assert result.is_verified is True


def test_get_account_info_uses_error_handler_when_identity_read_fails():
    """Identity read failures must be translated via InstagramFailure."""
    (
        usecase,
        account_repo,
        client_repo,
        _status_repo,
        _instagram,
        _logger,
        error_handler,
        identity_reader,
        _session_store,
    ) = _build_usecase()

    account_repo.get.return_value = {"username": "alice"}
    client_repo.exists.return_value = True
    identity_reader.get_authenticated_account.side_effect = RuntimeError("raw vendor error")
    error_handler.handle.return_value = InstagramFailure(
        code="login_required",
        family="private_auth",
        retryable=False,
        requires_user_action=True,
        user_message="Login required. Please re-authenticate.",
        http_hint=401,
        detail="raw vendor error",
    )

    result = usecase.get_account_info("acc-1")

    error_handler.handle.assert_called_once()
    assert result.username == "alice"
    assert result.error == "Login required. Please re-authenticate."
