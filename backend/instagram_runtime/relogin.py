from __future__ import annotations

import time
from typing import Callable

from state import SESSIONS_DIR, TwoFactorRequired, log_event, pop_client, store_pending_2fa_client

from .auth import activate_account_client, classify_exception, create_authenticated_client, new_client

_MAX_RELOGIN_ATTEMPTS = 3

ReloginStrategy = Callable[[str, str, str | None, str | None], object]
CreateAuthenticatedClientFn = Callable[[str, str, str | None, str | None], object]
NewClientFn = Callable[[str | None], object]
ClassifyExceptionFn = Callable[..., object]


# ── Relogin strategies ────────────────────────────────────────────────────────
#
# Two concrete strategies share the same signature so relogin_account_sync
# can call either uniformly.
#
# SessionRestoreStrategy  — default; calls create_authenticated_client() which
#   tries to reload the existing session file first and only falls back to fresh
#   credential login on LoginRequired. Fastest when the session is still valid.
#
# FreshCredentialStrategy — skips the session file entirely; always creates a
#   new client and authenticates with the stored username + password + TOTP.
#   Required for Instagram server-side force-logouts (logout_reason:8) where
#   the existing session file is permanently invalidated and cannot be restored.


def _relogin_session_restore(
    username: str,
    password: str,
    proxy: str | None,
    totp_secret: str | None,
    *,
    create_authenticated_client_fn: CreateAuthenticatedClientFn = create_authenticated_client,
):
    """Relogin via session restore (try saved session, fall back to fresh login)."""
    return create_authenticated_client_fn(username, password, proxy, totp_secret)


def _relogin_fresh_credentials(
    username: str,
    password: str,
    proxy: str | None,
    totp_secret: str | None,
    *,
    new_client_fn: NewClientFn = new_client,
):
    """Relogin with fresh credentials, bypassing the existing session file."""
    session_file = SESSIONS_DIR / f"{username}.json"

    def _totp_code() -> str:
        if not totp_secret:
            return ""
        import pyotp

        return pyotp.TOTP(totp_secret).now()

    client = new_client_fn(proxy)
    # Preserve device fingerprint — load UUIDs from any existing session so
    # Instagram recognises the same device on fresh-credential logins.
    if session_file.exists():
        try:
            client.load_settings(session_file)
            old = client.get_settings() or {}
            client.set_settings({})  # discard stale cookies
            if old.get("uuids"):
                client.set_uuids(old["uuids"])  # restore device fingerprint
        except Exception:
            pass  # malformed session file — proceed with fresh device fingerprint

    try:
        client.login(username, password, verification_code=_totp_code())
    except TwoFactorRequired:
        store_pending_2fa_client(username, client)
        raise
    client.dump_settings(session_file)
    return client


_RELOGIN_STRATEGIES: dict[str, ReloginStrategy] = {
    "session_restore": _relogin_session_restore,
    "fresh_credentials": _relogin_fresh_credentials,
}


def _build_relogin_strategies(
    *,
    create_authenticated_client_fn: CreateAuthenticatedClientFn,
    new_client_fn: NewClientFn,
) -> dict[str, ReloginStrategy]:
    if (
        create_authenticated_client_fn is create_authenticated_client
        and new_client_fn is new_client
    ):
        return _RELOGIN_STRATEGIES

    return {
        "session_restore": lambda username, password, proxy, totp_secret: _relogin_session_restore(
            username,
            password,
            proxy,
            totp_secret,
            create_authenticated_client_fn=create_authenticated_client_fn,
        ),
        "fresh_credentials": lambda username, password, proxy, totp_secret: _relogin_fresh_credentials(
            username,
            password,
            proxy,
            totp_secret,
            new_client_fn=new_client_fn,
        ),
    }


def relogin_account_sync(
    account_id: str,
    *,
    username: str,
    password: str,
    proxy: str | None = None,
    totp_secret: str | None = None,
    mode: str = "session_restore",
    create_authenticated_client_fn: CreateAuthenticatedClientFn = create_authenticated_client,
    new_client_fn: NewClientFn = new_client,
    classify_exception_fn: ClassifyExceptionFn = classify_exception,
    relogin_strategies: dict[str, ReloginStrategy] | None = None,
) -> dict:
    """Synchronous relogin with retry for transient failures."""
    strategies = relogin_strategies or _build_relogin_strategies(
        create_authenticated_client_fn=create_authenticated_client_fn,
        new_client_fn=new_client_fn,
    )
    default_strategy = strategies.get("session_restore", _RELOGIN_STRATEGIES["session_restore"])
    strategy = strategies.get(mode, default_strategy)

    # Drop stale client reference without invalidating the server-side session.
    # Calling logout() here would invalidate the session file that
    # _relogin_session_restore is about to reuse, forcing a full re-auth.
    pop_client(account_id)

    cl = None
    for attempt in range(_MAX_RELOGIN_ATTEMPTS):
        if attempt > 0:
            time.sleep(2 ** (attempt - 1))  # 1s, then 2s
        try:
            cl = strategy(username, password, proxy, totp_secret)
            break  # success — exit retry loop
        except Exception as exc:
            failure = classify_exception_fn(
                exc, operation="relogin", account_id=account_id, username=username
            )
            if getattr(failure, "retryable", False) and attempt < _MAX_RELOGIN_ATTEMPTS - 1:
                continue  # transient — retry
            raise

    result = activate_account_client(account_id, cl)
    log_event(account_id, username, "relogin_success", status="active")
    return result
