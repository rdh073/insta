from __future__ import annotations

import datetime

from app.adapters.instagram.exception_handler import instagram_exception_handler
from state import (
    get_account,
    get_account_status_value,
    get_client,
    has_client,
    log_event,
    set_account_status,
    update_account,
)


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _utc_now_iso() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def _classify_exception(
    error: Exception,
    *,
    operation: str,
    account_id: str | None = None,
    username: str | None = None,
):
    """Translate an exception to the shared Instagram failure contract."""
    return instagram_exception_handler.handle(
        error,
        operation=operation,
        account_id=account_id,
        username=username,
    )


def _account_username(account_id: str, default: str = "") -> str:
    return (get_account(account_id) or {}).get("username", default)


def _apply_account_proxy(account_id: str, proxy: str) -> str:
    username = _account_username(account_id)
    update_account(account_id, proxy=proxy)
    client = get_client(account_id)
    if client:
        client.set_proxy(proxy)
    log_event(account_id, username, "proxy_changed", detail=proxy)
    return username


def get_account_status(account_id: str) -> str:
    if has_client(account_id):
        return "active"
    return get_account_status_value(account_id, "idle")


def _track_relogin_failure(account_id: str, exc: Exception, default_username: str = "") -> str:
    username = _account_username(account_id, default=default_username)
    failure = _classify_exception(
        exc,
        operation="relogin",
        account_id=account_id,
        username=username,
    )
    set_account_status(account_id, "error")
    log_event(account_id, username, "relogin_failed", detail=failure.user_message, status="error")
    return username
