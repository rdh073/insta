"""Regression tests for canonical relogin wiring across account stacks."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from app.application.dto.account_dto import AccountResponse, BulkReloginRequest
from app.application.use_cases.account_auth import AccountAuthUseCases
from app.bootstrap.container import create_services


def _build_auth_usecases_with_relogin(relogin_usecases: Mock) -> AccountAuthUseCases:
    return AccountAuthUseCases(
        account_repo=Mock(),
        client_repo=Mock(),
        status_repo=Mock(),
        instagram=Mock(),
        logger=Mock(),
        totp=Mock(),
        session_store=Mock(),
        error_handler=Mock(),
        identity_reader=Mock(),
        uow=None,
        relogin_usecases=relogin_usecases,
    )


def test_account_auth_relogin_delegates_to_canonical_relogin_usecases():
    relogin_usecases = Mock()
    expected = AccountResponse(id="acc-1", username="alice", status="active")
    relogin_usecases.relogin_account.return_value = expected

    usecases = _build_auth_usecases_with_relogin(relogin_usecases)

    result = usecases.relogin_account("acc-1")

    assert result is expected
    relogin_usecases.relogin_account.assert_called_once_with("acc-1")


@pytest.mark.asyncio
async def test_account_auth_bulk_relogin_delegates_to_canonical_relogin_usecases():
    relogin_usecases = Mock()
    request = BulkReloginRequest(account_ids=["acc-1"], concurrency=3)
    expected = [AccountResponse(id="acc-1", username="alice", status="active")]
    relogin_usecases.bulk_relogin_accounts = AsyncMock(return_value=expected)

    usecases = _build_auth_usecases_with_relogin(relogin_usecases)

    result = await usecases.bulk_relogin_accounts(request)

    assert result is expected
    relogin_usecases.bulk_relogin_accounts.assert_called_once_with(request)


def test_account_auth_relogin_by_username_delegates_to_canonical_relogin_usecases():
    relogin_usecases = Mock()
    expected = {"success": True, "username": "alice", "status": "active"}
    relogin_usecases.relogin_account_by_username.return_value = expected

    usecases = _build_auth_usecases_with_relogin(relogin_usecases)

    result = usecases.relogin_account_by_username("alice")

    assert result is expected
    relogin_usecases.relogin_account_by_username.assert_called_once_with("alice")


def test_container_shares_single_relogin_instance_between_http_and_ai_stacks():
    services = create_services()

    account_usecases = services["accounts"]
    account_auth_usecases = services["account_auth"]
    startup_relogin_fn = services["_relogin_fn"]

    shared_relogin = getattr(account_usecases, "_relogin", None)
    assert shared_relogin is not None
    assert getattr(account_auth_usecases, "_relogin", None) is shared_relogin
    assert getattr(startup_relogin_fn, "__self__", None) is shared_relogin


def test_container_applies_restore_verify_policy_to_shared_relogin(monkeypatch):
    monkeypatch.setenv("ACCOUNT_VERIFY_SESSION_ON_RESTORE", "true")

    services = create_services()
    shared_relogin = getattr(services["accounts"], "_relogin", None)

    assert shared_relogin is not None
    assert shared_relogin.verify_session_on_restore is True
    assert getattr(services["_relogin_fn"], "__self__", None) is shared_relogin
