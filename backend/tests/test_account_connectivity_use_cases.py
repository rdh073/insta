"""Tests for AccountConnectivityUseCases — runtime health probing."""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

import pytest

from backend.app.application.dto.instagram_identity_dto import (
    AuthenticatedAccountProfile,
)
from backend.app.application.use_cases.account_connectivity import (
    AccountConnectivityUseCases,
    _connectivity_failure_status,
)
from backend.app.domain.instagram_failures import (
    InstagramFailure,
    InstagramAdapterError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_failure(
    *,
    code: str = "unknown_instagram_error",
    family: str = "unknown",
    retryable: bool = False,
    requires_user_action: bool = False,
    message: str = "Something went wrong",
) -> InstagramFailure:
    return InstagramFailure(
        code=code,
        family=family,
        retryable=retryable,
        requires_user_action=requires_user_action,
        user_message=message,
        http_hint=500,
    )


def _make_profile(**kwargs) -> AuthenticatedAccountProfile:
    defaults = dict(
        pk=1,
        username="alice",
        full_name="Alice",
        biography="",
        is_private=False,
        is_verified=False,
        is_business=False,
        email=None,
        phone_number=None,
        profile_pic_url="https://example.com/pic.jpg",
        follower_count=100,
        following_count=50,
    )
    defaults.update(kwargs)
    return AuthenticatedAccountProfile(**defaults)


def _build_usecase(
    *, client_exists: bool = True
) -> tuple[AccountConnectivityUseCases, Mock, Mock, Mock, Mock, Mock, Mock]:
    account_repo = Mock()
    client_repo = Mock()
    status_repo = Mock()
    identity_reader = Mock()
    error_handler = Mock()
    logger = Mock()

    account_repo.get.return_value = {"username": "alice", "proxy": None}
    account_repo.exists.return_value = True
    client_repo.exists.return_value = client_exists
    status_repo.get.return_value = "active" if client_exists else "idle"

    uc = AccountConnectivityUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        status_repo=status_repo,
        identity_reader=identity_reader,
        error_handler=error_handler,
        logger=logger,
    )
    return (
        uc,
        account_repo,
        client_repo,
        status_repo,
        identity_reader,
        error_handler,
        logger,
    )


# ---------------------------------------------------------------------------
# Unit: _connectivity_failure_status helper
# ---------------------------------------------------------------------------


def test_failure_status_challenge():
    f = _make_failure(family="challenge")
    assert _connectivity_failure_status(f) == "challenge"


def test_failure_status_two_factor():
    f = _make_failure(code="two_factor_required", family="auth")
    assert _connectivity_failure_status(f) == "2fa_required"


def test_failure_status_transient_returns_none():
    """Transient failures (retryable, no user action needed) must not overwrite status."""
    f = _make_failure(family="network", retryable=True, requires_user_action=False)
    assert _connectivity_failure_status(f) is None


def test_failure_status_auth_error():
    f = _make_failure(
        code="login_required", family="auth", retryable=False, requires_user_action=True
    )
    assert _connectivity_failure_status(f) == "error"


def test_failure_status_rate_limit_is_transient():
    f = _make_failure(family="rate_limit", retryable=True, requires_user_action=False)
    assert _connectivity_failure_status(f) is None


# ---------------------------------------------------------------------------
# Use-case: success probe
# ---------------------------------------------------------------------------


def test_verify_success_marks_verified_and_refreshes_metadata():
    (
        uc,
        account_repo,
        client_repo,
        status_repo,
        identity_reader,
        error_handler,
        logger,
    ) = _build_usecase()
    profile = _make_profile(
        full_name="Alice Smith", follower_count=200, following_count=80
    )
    identity_reader.get_authenticated_account.return_value = profile

    result = uc.verify_account_connectivity("acc-1")

    assert result.status == "active"
    assert result.last_error is None
    assert result.last_error_code is None

    # Verified timestamp stored
    first_call_kwargs = account_repo.update.call_args_list[0][1]
    assert "last_verified_at" in first_call_kwargs
    assert first_call_kwargs["last_error"] is None
    assert first_call_kwargs["last_error_code"] is None

    # Metadata refresh persisted
    calls_kwargs = [c[1] for c in account_repo.update.call_args_list]
    metadata_call = next((kw for kw in calls_kwargs if "full_name" in kw), None)
    assert metadata_call is not None
    assert metadata_call["full_name"] == "Alice Smith"
    assert metadata_call["followers"] == 200
    assert metadata_call["following"] == 80

    # Status set active
    status_repo.set.assert_called_with("acc-1", "active")

    # Logger called
    logger.log_event.assert_called_once_with(
        "acc-1", "alice", "connectivity_verified", status="active"
    )


def test_verify_success_does_not_call_instagram_client_directly():
    """Use case must not bypass the adapter boundary."""
    uc, _, _, _, identity_reader, _, _ = _build_usecase()
    identity_reader.get_authenticated_account.return_value = _make_profile()

    uc.verify_account_connectivity("acc-1")

    # Only the identity reader boundary is used — no raw client access.
    identity_reader.get_authenticated_account.assert_called_once_with("acc-1")


# ---------------------------------------------------------------------------
# Use-case: session expired / login required  (structured InstagramAdapterError path)
# ---------------------------------------------------------------------------


def test_verify_auth_failure_overwrites_status_to_error():
    """Structured auth failure from identity reader sets status=error without
    re-running the error handler."""
    (
        uc,
        account_repo,
        client_repo,
        status_repo,
        identity_reader,
        error_handler,
        logger,
    ) = _build_usecase()
    failure = _make_failure(
        code="login_required",
        family="auth",
        retryable=False,
        requires_user_action=True,
        message="Session expired. Please re-authenticate.",
    )
    identity_reader.get_authenticated_account.side_effect = InstagramAdapterError(
        failure
    )

    result = uc.verify_account_connectivity("acc-1")

    assert result.status == "error"
    status_repo.set.assert_called_with("acc-1", "error")
    account_repo.update.assert_called_with(
        "acc-1",
        last_error="Session expired. Please re-authenticate.",
        last_error_code="login_required",
    )
    logger.log_event.assert_called_once_with(
        "acc-1",
        "alice",
        "connectivity_failed",
        detail="Session expired. Please re-authenticate.",
        status="error",
    )
    # error_handler.handle must NOT be called — failure metadata is already preserved.
    error_handler.handle.assert_not_called()


# ---------------------------------------------------------------------------
# Use-case: challenge required  (structured InstagramAdapterError path)
# ---------------------------------------------------------------------------


def test_verify_challenge_failure_sets_challenge_status():
    uc, _, _, status_repo, identity_reader, error_handler, _ = _build_usecase()
    failure = _make_failure(
        code="challenge_required",
        family="challenge",
        retryable=False,
        requires_user_action=True,
        message="Challenge required.",
    )
    identity_reader.get_authenticated_account.side_effect = InstagramAdapterError(
        failure
    )

    result = uc.verify_account_connectivity("acc-1")

    assert result.status == "challenge"
    status_repo.set.assert_called_with("acc-1", "challenge")
    error_handler.handle.assert_not_called()


# ---------------------------------------------------------------------------
# Use-case: 2FA required  (structured InstagramAdapterError path)
# ---------------------------------------------------------------------------


def test_verify_two_factor_failure_sets_2fa_required_status():
    uc, _, _, status_repo, identity_reader, error_handler, _ = _build_usecase()
    failure = _make_failure(
        code="two_factor_required",
        family="auth",
        retryable=False,
        requires_user_action=True,
        message="Two-factor authentication required.",
    )
    identity_reader.get_authenticated_account.side_effect = InstagramAdapterError(
        failure
    )

    result = uc.verify_account_connectivity("acc-1")

    assert result.status == "2fa_required"
    status_repo.set.assert_called_with("acc-1", "2fa_required")
    error_handler.handle.assert_not_called()


# ---------------------------------------------------------------------------
# Use-case: transient / network / rate-limit failure  (structured path)
# ---------------------------------------------------------------------------


def test_verify_transient_failure_preserves_active_status():
    """Transient errors must not mark a healthy account as broken."""
    (
        uc,
        account_repo,
        client_repo,
        status_repo,
        identity_reader,
        error_handler,
        logger,
    ) = _build_usecase(client_exists=True)
    # Client exists so _get_account_status returns "active"
    client_repo.exists.return_value = True

    failure = _make_failure(
        code="network_error",
        family="network",
        retryable=True,
        requires_user_action=False,
        message="Network timeout. Please retry.",
    )
    identity_reader.get_authenticated_account.side_effect = InstagramAdapterError(
        failure
    )

    result = uc.verify_account_connectivity("acc-1")

    # Status must not be overwritten to "error"
    status_repo.set.assert_not_called()
    # last_error is still recorded
    account_repo.update.assert_called_with(
        "acc-1",
        last_error="Network timeout. Please retry.",
        last_error_code="network_error",
    )
    # Response status follows the current runtime status (active because client exists)
    assert result.status == "active"
    error_handler.handle.assert_not_called()


# ---------------------------------------------------------------------------
# Use-case: generic fallback — unexpected exceptions still handled safely
# ---------------------------------------------------------------------------


def test_verify_generic_exception_falls_back_to_error_handler():
    """Unexpected non-adapter exceptions still flow through error_handler as a safety net."""
    (
        uc,
        account_repo,
        client_repo,
        status_repo,
        identity_reader,
        error_handler,
        logger,
    ) = _build_usecase()
    identity_reader.get_authenticated_account.side_effect = RuntimeError("unexpected")
    error_handler.handle.return_value = _make_failure(
        code="unknown_instagram_error",
        family="unknown",
        retryable=False,
        requires_user_action=False,
        message="An unexpected error occurred.",
    )

    result = uc.verify_account_connectivity("acc-1")

    # Falls back to error_handler classification
    error_handler.handle.assert_called_once()
    assert result.status == "error"


# ---------------------------------------------------------------------------
# Use-case: guard rails — no client / account not found
# ---------------------------------------------------------------------------


def test_verify_raises_when_account_not_found():
    uc, account_repo, *_ = _build_usecase()
    account_repo.get.return_value = None

    with pytest.raises(ValueError, match="not found"):
        uc.verify_account_connectivity("nonexistent")


def test_verify_raises_when_no_active_client():
    uc, _, _, _, _, _, _ = _build_usecase(client_exists=False)

    with pytest.raises(ValueError, match="not logged in"):
        uc.verify_account_connectivity("acc-1")


# ---------------------------------------------------------------------------
# Use-case: bulk verify
# ---------------------------------------------------------------------------


def test_bulk_verify_returns_results_for_all_ids():
    (
        uc,
        account_repo,
        client_repo,
        status_repo,
        identity_reader,
        error_handler,
        logger,
    ) = _build_usecase()
    identity_reader.get_authenticated_account.return_value = _make_profile()

    results = asyncio.run(uc.bulk_verify_accounts(["acc-1", "acc-2"], concurrency=2))

    assert len(results) == 2
    assert all(r.status == "active" for r in results)


def test_bulk_verify_handles_not_found_gracefully():
    uc, account_repo, *_ = _build_usecase()

    def _get(account_id):
        return {"username": "alice"} if account_id == "acc-1" else None

    account_repo.get.side_effect = _get
    uc.identity_reader.get_authenticated_account.return_value = _make_profile()

    results = asyncio.run(
        uc.bulk_verify_accounts(["acc-1", "acc-nonexistent"], concurrency=2)
    )

    assert len(results) == 2
    acc1 = next(r for r in results if r.id == "acc-1")
    acc_bad = next(r for r in results if r.id == "acc-nonexistent")
    assert acc1.status == "active"
    assert acc_bad.status == "error"
