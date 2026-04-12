"""Regression tests for unified account status and relogin policy."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.application.ports import ReloginMode
from app.application.use_cases.account_auth import AccountAuthUseCases
from app.application.use_cases.account_connectivity import _connectivity_failure_status
from app.application.use_cases.account_status_policy import status_from_failure
from app.domain.instagram_failures import InstagramAdapterError, InstagramFailure


def _failure(
    *,
    code: str,
    family: str,
    retryable: bool = False,
    requires_user_action: bool = True,
    message: str = "failure",
) -> InstagramFailure:
    return InstagramFailure(
        code=code,
        family=family,
        retryable=retryable,
        requires_user_action=requires_user_action,
        user_message=message,
        http_hint=409,
    )


@pytest.mark.parametrize(
    "code",
    [
        "challenge_required",
        "checkpoint_required",
        "consent_required",
        "geo_blocked",
        "captcha_challenge_required",
    ],
)
def test_status_policy_maps_challenge_codes_without_prefix_dependency(code: str):
    failure = _failure(code=code, family="unknown", requires_user_action=False)
    assert status_from_failure(failure, keep_transient=True) == "challenge"
    assert _connectivity_failure_status(failure) == "challenge"
    assert AccountAuthUseCases._relogin_failure_status(failure) == "challenge"


def test_hydration_uses_same_challenge_status_policy_as_connectivity():
    account_repo = Mock()
    client_repo = Mock()
    status_repo = Mock()
    identity_reader = Mock()

    client_repo.exists.return_value = True

    failure = _failure(
        code="geo_blocked",
        family="challenge",
        requires_user_action=False,  # regression: must still map to challenge
        message="Your location is not supported.",
    )
    identity_reader.get_authenticated_account.side_effect = InstagramAdapterError(failure)

    usecase = AccountAuthUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        status_repo=status_repo,
        instagram=Mock(),
        logger=Mock(),
        totp=Mock(),
        session_store=Mock(),
        error_handler=Mock(),
        identity_reader=identity_reader,
        uow=None,
    )

    result = usecase.hydrate_account_profile("acc-1")

    assert result is None
    status_repo.set.assert_called_once_with("acc-1", "challenge")
    client_repo.remove.assert_called_once_with("acc-1")
    account_repo.update.assert_called_once_with(
        "acc-1",
        last_error="Your location is not supported.",
        last_error_code="geo_blocked",
        last_error_family="challenge",
    )


@pytest.mark.parametrize(
    "last_error_code",
    [
        "challenge_required",
        "checkpoint_required",
        "consent_required",
        "geo_blocked",
        "captcha_challenge_required",
    ],
)
def test_relogin_mode_uses_fresh_credentials_for_challenge_family_codes(
    last_error_code: str,
):
    mode = AccountAuthUseCases._select_relogin_mode({"last_error_code": last_error_code})
    assert mode is ReloginMode.FRESH_CREDENTIALS


def test_relogin_mode_uses_session_restore_for_non_challenge_code():
    mode = AccountAuthUseCases._select_relogin_mode({"last_error_code": "network_error"})
    assert mode is ReloginMode.SESSION_RESTORE


def test_relogin_mode_uses_fresh_credentials_for_challenge_family_metadata():
    mode = AccountAuthUseCases._select_relogin_mode(
        {"last_error_code": "network_error", "last_error_family": "challenge"}
    )
    assert mode is ReloginMode.FRESH_CREDENTIALS
