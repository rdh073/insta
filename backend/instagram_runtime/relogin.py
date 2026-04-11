"""Relogin strategies extracted from the legacy Instagram boundary."""

from __future__ import annotations

import time
from typing import Callable

from state import SESSIONS_DIR, TwoFactorRequired, log_event, pop_client, store_pending_2fa_client

from .auth import (
    _classify_exception,
    _new_client,
    activate_account_client,
    create_authenticated_client,
)


_MAX_RELOGIN_ATTEMPTS = 3


def _relogin_session_restore(
    username: str,
    password: str,
    proxy: str | None,
    totp_secret: str | None,
):
    """Relogin via session restore (try saved session, fall back to fresh login)."""
    return create_authenticated_client(username, password, proxy, totp_secret)


def _relogin_fresh_credentials(
    username: str,
    password: str,
    proxy: str | None,
    totp_secret: str | None,
):
    """Relogin with fresh credentials, bypassing the existing session file."""
    session_file = SESSIONS_DIR / f"{username}.json"

    def _totp_code() -> str:
        if not totp_secret:
            return ""
        import pyotp

        return pyotp.TOTP(totp_secret).now()

    client = _new_client(proxy)
    if session_file.exists():
        try:
            client.load_settings(session_file)
            old = client.get_settings() or {}
            client.set_settings({})
            if old.get("uuids"):
                client.set_uuids(old["uuids"])
        except Exception:
            pass

    try:
        client.login(username, password, verification_code=_totp_code())
    except TwoFactorRequired:
        store_pending_2fa_client(username, client)
        raise
    client.dump_settings(session_file)
    return client


_RELOGIN_STRATEGIES: dict[str, Callable] = {
    "session_restore": _relogin_session_restore,
    "fresh_credentials": _relogin_fresh_credentials,
}


def relogin_account_sync(
    account_id: str,
    *,
    username: str,
    password: str,
    proxy: str | None = None,
    totp_secret: str | None = None,
    mode: str = "session_restore",
) -> dict:
    """Synchronous relogin with retry for transient failures."""
    strategy = _RELOGIN_STRATEGIES.get(mode, _relogin_session_restore)

    pop_client(account_id)

    cl = None
    for attempt in range(_MAX_RELOGIN_ATTEMPTS):
        if attempt > 0:
            time.sleep(2 ** (attempt - 1))
        try:
            cl = strategy(username, password, proxy, totp_secret)
            break
        except Exception as exc:
            failure = _classify_exception(
                exc,
                operation="relogin",
                account_id=account_id,
                username=username,
            )
            if failure.retryable and attempt < _MAX_RELOGIN_ATTEMPTS - 1:
                continue
            raise

    result = activate_account_client(account_id, cl)
    log_event(account_id, username, "relogin_success", status="active")
    return result
