"""Tests for AccountDiagnosticsAdapter — verify_account_health with real connectivity probe."""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

from ai_copilot.adapters.account_diagnostics_adapter import AccountDiagnosticsAdapter
from backend.app.application.dto.account_dto import AccountResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_account_response(
    account_id: str = "acc-1",
    status: str = "active",
    **kwargs,
) -> AccountResponse:
    return AccountResponse(
        id=account_id,
        username="alice",
        status=status,
        last_verified_at=kwargs.get("last_verified_at"),
        last_error=kwargs.get("last_error"),
        last_error_code=kwargs.get("last_error_code"),
    )


def _make_account_usecases(account_id: str = "acc-1", status: str = "active"):
    account_usecases = Mock()
    account_usecases.find_by_username.return_value = None
    account_usecases.list_accounts.return_value = [
        _make_account_response(account_id, status)
    ]
    return account_usecases


def _make_connectivity_usecases(account_id: str = "acc-1", status: str = "active"):
    connectivity = Mock()
    connectivity.verify_account_connectivity.return_value = _make_account_response(
        account_id,
        status,
        last_verified_at="2024-01-01T00:00:00+00:00" if status == "active" else None,
        last_error="Session expired." if status == "error" else None,
        last_error_code="login_required" if status == "error" else None,
    )
    return connectivity


# ---------------------------------------------------------------------------
# Tests: without connectivity_usecases (legacy fallback)
# ---------------------------------------------------------------------------


def test_verify_health_fallback_active_when_no_connectivity():
    account_usecases = _make_account_usecases(status="active")
    adapter = AccountDiagnosticsAdapter(account_usecases)

    result = asyncio.run(adapter.verify_account_health("acc-1"))

    assert result["healthy"] is True
    assert result["login_state"] == "logged_in"
    assert result["status"] == "active"


def test_verify_health_fallback_unhealthy_when_no_connectivity_and_error_status():
    account_usecases = _make_account_usecases(status="error")
    adapter = AccountDiagnosticsAdapter(account_usecases)

    result = asyncio.run(adapter.verify_account_health("acc-1"))

    assert result["healthy"] is False
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Tests: with connectivity_usecases (real probe)
# ---------------------------------------------------------------------------


def test_verify_health_uses_connectivity_probe_when_injected():
    """When connectivity_usecases is provided, it must be called instead of local status read."""
    account_usecases = _make_account_usecases(status="active")
    connectivity = _make_connectivity_usecases(status="active")
    adapter = AccountDiagnosticsAdapter(account_usecases, connectivity)

    result = asyncio.run(adapter.verify_account_health("acc-1"))

    connectivity.verify_account_connectivity.assert_called_once_with("acc-1")
    assert result["healthy"] is True
    assert result["login_state"] == "logged_in"
    assert result["last_verified_at"] == "2024-01-01T00:00:00+00:00"


def test_verify_health_returns_unhealthy_on_probe_failure():
    account_usecases = _make_account_usecases(status="active")
    connectivity = _make_connectivity_usecases(status="error")
    adapter = AccountDiagnosticsAdapter(account_usecases, connectivity)

    result = asyncio.run(adapter.verify_account_health("acc-1"))

    assert result["healthy"] is False
    assert result["login_state"] == "error"
    assert result["last_error"] == "Session expired."
    assert result["last_error_code"] == "login_required"


def test_verify_health_handles_not_found_from_connectivity():
    account_usecases = _make_account_usecases()
    connectivity = Mock()
    connectivity.verify_account_connectivity.side_effect = ValueError(
        "Account not found"
    )
    adapter = AccountDiagnosticsAdapter(account_usecases, connectivity)

    result = asyncio.run(adapter.verify_account_health("acc-1"))

    assert result["healthy"] is False
    assert result["login_state"] == "not_found"


def test_verify_health_local_state_not_read_when_connectivity_injected():
    """list_accounts should only be called once (for resolution), not for health data."""
    account_usecases = Mock()
    account_usecases.find_by_username.return_value = None
    account_usecases.list_accounts.return_value = [
        _make_account_response("acc-1", "active")
    ]
    connectivity = _make_connectivity_usecases(status="active")
    adapter = AccountDiagnosticsAdapter(account_usecases, connectivity)

    asyncio.run(adapter.verify_account_health("acc-1"))

    # Connectivity probe was called
    connectivity.verify_account_connectivity.assert_called_once_with("acc-1")
    # list_accounts was only called once for the resolve step, not for health data
    assert account_usecases.list_accounts.call_count == 1


# ---------------------------------------------------------------------------
# Tests: not found
# ---------------------------------------------------------------------------


def test_verify_health_not_found_returns_unhealthy():
    account_usecases = Mock()
    account_usecases.find_by_username.return_value = None
    account_usecases.list_accounts.return_value = []
    adapter = AccountDiagnosticsAdapter(account_usecases)

    result = asyncio.run(adapter.verify_account_health("nonexistent"))

    assert result["healthy"] is False
    assert result["login_state"] == "not_found"
