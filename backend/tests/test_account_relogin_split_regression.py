"""Regression coverage for split-path ReloginUseCases credential kwargs."""

from __future__ import annotations

from unittest.mock import Mock, call

import pytest

from app.application.ports import ReloginMode
from app.application.use_cases.account.relogin import ReloginUseCases
from app.domain.instagram_failures import InstagramFailure


class _KwOnlyInstagramClient:
    """Test double with kw-only relogin signature matching the real port."""

    def __init__(self, *, result: dict | None = None, error: Exception | None = None):
        self._result = result or {"status": "active"}
        self._error = error
        self.calls: list[dict] = []

    def relogin_account(
        self,
        account_id: str,
        *,
        username: str,
        password: str,
        proxy: str | None = None,
        totp_secret: str | None = None,
        mode: ReloginMode = ReloginMode.SESSION_RESTORE,
        verify_session: bool = False,
    ) -> dict:
        self.calls.append(
            {
                "account_id": account_id,
                "username": username,
                "password": password,
                "proxy": proxy,
                "totp_secret": totp_secret,
                "mode": mode,
                "verify_session": verify_session,
            }
        )
        if self._error is not None:
            raise self._error
        return dict(self._result)


def _build_usecase(instagram: _KwOnlyInstagramClient, *, verify_session_on_restore: bool = False):
    account_repo = Mock()
    status_repo = Mock()
    logger = Mock()
    error_handler = Mock()

    usecase = ReloginUseCases(
        account_repo=account_repo,
        status_repo=status_repo,
        instagram=instagram,
        logger=logger,
        error_handler=error_handler,
        verify_session_on_restore=verify_session_on_restore,
    )
    return usecase, account_repo, status_repo, logger, error_handler


def test_relogin_account_passes_required_kwargs_and_returns_active():
    """Regression: split relogin must satisfy kw-only signature (no TypeError)."""
    instagram = _KwOnlyInstagramClient()
    usecase, account_repo, status_repo, logger, error_handler = _build_usecase(instagram)

    account_repo.get.return_value = {
        "username": "alice",
        "password": "s3cret",
        "proxy": "http://proxy:8080",
        "totp_secret": "TOTPSECRET",
        "last_error_code": "login_required",
    }

    result = usecase.relogin_account("acc-1")

    assert result.status == "active"
    assert instagram.calls == [
        {
            "account_id": "acc-1",
            "username": "alice",
            "password": "s3cret",
            "proxy": "http://proxy:8080",
            "totp_secret": "TOTPSECRET",
            "mode": ReloginMode.FRESH_CREDENTIALS,
            "verify_session": False,
        }
    ]
    status_repo.set.assert_has_calls([call("acc-1", "logging_in"), call("acc-1", "active")])
    error_handler.handle.assert_not_called()
    logger.log_event.assert_not_called()


def test_relogin_account_uses_fresh_credentials_when_last_error_family_is_challenge():
    instagram = _KwOnlyInstagramClient()
    usecase, account_repo, status_repo, logger, error_handler = _build_usecase(instagram)

    account_repo.get.return_value = {
        "username": "alice",
        "password": "s3cret",
        "proxy": None,
        "totp_secret": None,
        "last_error_code": "network_error",
        "last_error_family": "challenge",
    }

    result = usecase.relogin_account("acc-1")

    assert result.status == "active"
    assert instagram.calls[0]["mode"] is ReloginMode.FRESH_CREDENTIALS
    status_repo.set.assert_has_calls([call("acc-1", "logging_in"), call("acc-1", "active")])
    error_handler.handle.assert_not_called()
    logger.log_event.assert_not_called()


def test_relogin_account_attaches_structured_failure_and_sets_policy_status():
    instagram = _KwOnlyInstagramClient(error=RuntimeError("checkpoint"))
    usecase, account_repo, status_repo, logger, error_handler = _build_usecase(instagram)

    account_repo.get.return_value = {
        "username": "alice",
        "password": "s3cret",
        "proxy": "http://proxy:8080",
        "totp_secret": "TOTPSECRET",
    }
    failure = InstagramFailure(
        code="checkpoint_required",
        family="challenge",
        retryable=False,
        requires_user_action=True,
        user_message="Challenge required. Complete verification in Instagram app.",
        http_hint=403,
    )
    error_handler.handle.return_value = failure

    with pytest.raises(RuntimeError) as exc_info:
        usecase.relogin_account("acc-1")

    assert getattr(exc_info.value, "_instagram_failure") == failure
    status_repo.set.assert_has_calls([call("acc-1", "logging_in"), call("acc-1", "challenge")])
    account_repo.update.assert_called_with(
        "acc-1",
        last_error=failure.user_message,
        last_error_code=failure.code,
        last_error_family=failure.family,
    )
    logger.log_event.assert_called_once_with(
        "acc-1",
        "alice",
        "relogin_failed",
        detail=failure.user_message,
        status="challenge",
    )


def test_relogin_account_enables_verify_session_for_restore_mode_when_policy_enabled():
    instagram = _KwOnlyInstagramClient()
    usecase, account_repo, status_repo, logger, error_handler = _build_usecase(
        instagram,
        verify_session_on_restore=True,
    )

    account_repo.get.return_value = {
        "username": "alice",
        "password": "s3cret",
        "proxy": "http://proxy:8080",
        "totp_secret": "TOTPSECRET",
        "last_error_code": "network_error",
    }

    result = usecase.relogin_account("acc-1")

    assert result.status == "active"
    assert instagram.calls[0]["mode"] is ReloginMode.SESSION_RESTORE
    assert instagram.calls[0]["verify_session"] is True
    error_handler.handle.assert_not_called()
    logger.log_event.assert_not_called()
    status_repo.set.assert_has_calls([call("acc-1", "logging_in"), call("acc-1", "active")])


def test_relogin_account_keeps_verify_session_disabled_when_policy_off():
    instagram = _KwOnlyInstagramClient()
    usecase, account_repo, status_repo, logger, error_handler = _build_usecase(instagram)

    account_repo.get.return_value = {
        "username": "alice",
        "password": "s3cret",
        "proxy": "http://proxy:8080",
        "totp_secret": "TOTPSECRET",
        "last_error_code": "network_error",
    }

    result = usecase.relogin_account("acc-1")

    assert result.status == "active"
    assert instagram.calls[0]["mode"] is ReloginMode.SESSION_RESTORE
    assert instagram.calls[0]["verify_session"] is False
    error_handler.handle.assert_not_called()
    logger.log_event.assert_not_called()
    status_repo.set.assert_has_calls([call("acc-1", "logging_in"), call("acc-1", "active")])


def test_relogin_account_persists_error_when_verify_session_enabled_and_restore_fails():
    instagram = _KwOnlyInstagramClient(error=RuntimeError("restore session invalid"))
    usecase, account_repo, status_repo, logger, error_handler = _build_usecase(
        instagram,
        verify_session_on_restore=True,
    )

    account_repo.get.return_value = {
        "username": "alice",
        "password": "s3cret",
        "proxy": "http://proxy:8080",
        "totp_secret": "TOTPSECRET",
        "last_error_code": "network_error",
    }
    failure = InstagramFailure(
        code="login_required",
        family="private_auth",
        retryable=False,
        requires_user_action=True,
        user_message="Session expired, relogin required.",
        http_hint=401,
    )
    error_handler.handle.return_value = failure

    with pytest.raises(RuntimeError):
        usecase.relogin_account("acc-1")

    assert instagram.calls[0]["mode"] is ReloginMode.SESSION_RESTORE
    assert instagram.calls[0]["verify_session"] is True
    status_repo.set.assert_has_calls([call("acc-1", "logging_in"), call("acc-1", "error")])
    account_repo.update.assert_called_with(
        "acc-1",
        last_error=failure.user_message,
        last_error_code=failure.code,
        last_error_family=failure.family,
    )
    logger.log_event.assert_called_once_with(
        "acc-1",
        "alice",
        "relogin_failed",
        detail=failure.user_message,
        status="error",
    )
