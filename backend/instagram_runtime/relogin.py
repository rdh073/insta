from __future__ import annotations

import inspect
import random
import time
from typing import Callable

from state import SESSIONS_DIR, TwoFactorRequired, log_event, pop_client, store_pending_2fa_client

from .auth import activate_account_client, classify_exception, create_authenticated_client, new_client

_MAX_RELOGIN_ATTEMPTS = 3
_COOLDOWN_FAILURE_CODES = frozenset({"rate_limit", "wait_required", "feedback_required"})
_COOLDOWN_RETRY_MIN_SECONDS = 30.0
_COOLDOWN_RETRY_MAX_SECONDS = 120.0
_COOLDOWN_RETRY_JITTER_MAX_SECONDS = 15.0

ReloginStrategy = Callable[..., object]
CreateAuthenticatedClientFn = Callable[..., object]
NewClientFn = Callable[..., object]
ClassifyExceptionFn = Callable[..., object]
SleepFn = Callable[[float], None]
JitterUniformFn = Callable[[float, float], float]


def _is_cooldown_worthy_failure(failure) -> bool:
    code = str(getattr(failure, "code", "") or "")
    if code in _COOLDOWN_FAILURE_CODES:
        return True
    return getattr(failure, "http_hint", None) == 429


def _rate_limit_retry_after_seconds(account_id: str) -> float:
    try:
        from app.adapters.instagram.rate_limit_guard import rate_limit_guard

        limited, retry_after = rate_limit_guard.is_limited(account_id)
        if limited:
            return max(float(retry_after), 0.0)
    except Exception:
        pass
    return 0.0


def _compute_retry_delay_seconds(
    *,
    failure,
    retry_index: int,
    account_id: str,
    jitter_uniform_fn: JitterUniformFn = random.uniform,
) -> float:
    if _is_cooldown_worthy_failure(failure):
        retry_after = _rate_limit_retry_after_seconds(account_id)
        cooldown_delay = retry_after if retry_after > 0 else _COOLDOWN_RETRY_MIN_SECONDS
        cooldown_delay = max(cooldown_delay, _COOLDOWN_RETRY_MIN_SECONDS)
        cooldown_delay = min(cooldown_delay, _COOLDOWN_RETRY_MAX_SECONDS)
        jitter = max(jitter_uniform_fn(0.0, _COOLDOWN_RETRY_JITTER_MAX_SECONDS), 0.0)
        return cooldown_delay + jitter
    return float(2 ** retry_index)


def _strategy_accepts_verify_session(strategy: ReloginStrategy) -> bool:
    """Return True when strategy supports the verify_session argument."""
    try:
        params = inspect.signature(strategy).parameters.values()
    except (TypeError, ValueError):
        return True

    positional_count = 0
    for param in params:
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            return True
        if param.name == "verify_session":
            return True
        if param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            positional_count += 1

    return positional_count >= 5


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
    verify_session: bool = False,
    *,
    country: str | None = None,
    country_code: int | None = None,
    locale: str | None = None,
    timezone_offset: int | None = None,
    create_authenticated_client_fn: CreateAuthenticatedClientFn = create_authenticated_client,
):
    """Relogin via session restore (try saved session, fall back to fresh login)."""
    geo_kwargs = _geo_kwargs(
        country=country,
        country_code=country_code,
        locale=locale,
        timezone_offset=timezone_offset,
    )
    try:
        signature = inspect.signature(create_authenticated_client_fn)
    except (TypeError, ValueError):
        return create_authenticated_client_fn(
            username,
            password,
            proxy,
            totp_secret,
            verify_session=verify_session,
            **geo_kwargs,
        )

    supports_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    supports_verify_session = supports_kwargs or "verify_session" in signature.parameters

    if supports_kwargs:
        payload_kwargs = dict(geo_kwargs)
        if supports_verify_session:
            payload_kwargs["verify_session"] = verify_session
        return create_authenticated_client_fn(
            username,
            password,
            proxy,
            totp_secret,
            **payload_kwargs,
        )

    supported_kwargs = {
        key: value for key, value in geo_kwargs.items() if key in signature.parameters
    }
    if supports_verify_session:
        supported_kwargs["verify_session"] = verify_session
    if supported_kwargs:
        return create_authenticated_client_fn(
            username,
            password,
            proxy,
            totp_secret,
            **supported_kwargs,
        )
    if supports_verify_session:
        return create_authenticated_client_fn(
            username,
            password,
            proxy,
            totp_secret,
            verify_session=verify_session,
        )
    return create_authenticated_client_fn(
        username,
        password,
        proxy,
        totp_secret,
    )


def _new_client_with_optional_geo(
    new_client_fn: NewClientFn,
    proxy: str | None,
    *,
    country: str | None = None,
    country_code: int | None = None,
    locale: str | None = None,
    timezone_offset: int | None = None,
):
    geo_kwargs = _geo_kwargs(
        country=country,
        country_code=country_code,
        locale=locale,
        timezone_offset=timezone_offset,
    )
    if not geo_kwargs:
        return new_client_fn(proxy)

    try:
        signature = inspect.signature(new_client_fn)
    except (TypeError, ValueError):
        return new_client_fn(proxy)

    if any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    ):
        return new_client_fn(proxy, **geo_kwargs)

    supported_kwargs = {
        key: value for key, value in geo_kwargs.items() if key in signature.parameters
    }
    if supported_kwargs:
        return new_client_fn(proxy, **supported_kwargs)
    return new_client_fn(proxy)


def _geo_kwargs(
    *,
    country: str | None = None,
    country_code: int | None = None,
    locale: str | None = None,
    timezone_offset: int | None = None,
) -> dict[str, str | int]:
    kwargs: dict[str, str | int] = {}
    if country is not None:
        kwargs["country"] = country
    if country_code is not None:
        kwargs["country_code"] = country_code
    if locale is not None:
        kwargs["locale"] = locale
    if timezone_offset is not None:
        kwargs["timezone_offset"] = timezone_offset
    return kwargs


def _relogin_fresh_credentials(
    username: str,
    password: str,
    proxy: str | None,
    totp_secret: str | None,
    verify_session: bool = False,
    *,
    country: str | None = None,
    country_code: int | None = None,
    locale: str | None = None,
    timezone_offset: int | None = None,
    new_client_fn: NewClientFn = new_client,
):
    """Relogin with fresh credentials, bypassing the existing session file."""
    del verify_session
    session_file = SESSIONS_DIR / f"{username}.json"

    def _totp_code() -> str:
        if not totp_secret:
            return ""
        import pyotp

        return pyotp.TOTP(totp_secret).now()

    client = _new_client_with_optional_geo(
        new_client_fn,
        proxy,
        country=country,
        country_code=country_code,
        locale=locale,
        timezone_offset=timezone_offset,
    )
    # Preserve device fingerprint — load UUIDs from any existing session so
    # Instagram recognises the same device on fresh-credential logins.
    # Per instagrapi best-practices guide, UUIDs are the device identity
    # Instagram actually checks; restoring them after set_settings({}) is
    # the canonical LoginRequired retry pattern.
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
    country: str | None = None,
    country_code: int | None = None,
    locale: str | None = None,
    timezone_offset: int | None = None,
) -> dict[str, ReloginStrategy]:
    geo_kwargs = _geo_kwargs(
        country=country,
        country_code=country_code,
        locale=locale,
        timezone_offset=timezone_offset,
    )
    if (
        create_authenticated_client_fn is create_authenticated_client
        and new_client_fn is new_client
        and not geo_kwargs
    ):
        return _RELOGIN_STRATEGIES

    return {
        "session_restore": lambda username, password, proxy, totp_secret, verify_session=False: _relogin_session_restore(
            username,
            password,
            proxy,
            totp_secret,
            verify_session,
            country=country,
            country_code=country_code,
            locale=locale,
            timezone_offset=timezone_offset,
            create_authenticated_client_fn=create_authenticated_client_fn,
        ),
        "fresh_credentials": lambda username, password, proxy, totp_secret, verify_session=False: _relogin_fresh_credentials(
            username,
            password,
            proxy,
            totp_secret,
            verify_session,
            country=country,
            country_code=country_code,
            locale=locale,
            timezone_offset=timezone_offset,
            new_client_fn=new_client_fn,
        ),
    }


def _strategy_supports_kwargs(strategy: ReloginStrategy) -> bool:
    try:
        signature = inspect.signature(strategy)
    except (TypeError, ValueError):
        return False
    return any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )


def _call_strategy_with_geo(
    strategy: ReloginStrategy,
    username: str,
    password: str,
    proxy: str | None,
    totp_secret: str | None,
    *,
    geo_kwargs: dict[str, str | int],
    verify_session: bool = False,
):
    strategy_accepts_verify = _strategy_accepts_verify_session(strategy)
    if not geo_kwargs:
        if strategy_accepts_verify:
            return strategy(username, password, proxy, totp_secret, verify_session)
        return strategy(username, password, proxy, totp_secret)

    if _strategy_supports_kwargs(strategy):
        payload_kwargs = dict(geo_kwargs)
        if strategy_accepts_verify:
            payload_kwargs["verify_session"] = verify_session
        return strategy(
            username,
            password,
            proxy,
            totp_secret,
            **payload_kwargs,
        )

    try:
        signature = inspect.signature(strategy)
    except (TypeError, ValueError):
        if strategy_accepts_verify:
            return strategy(username, password, proxy, totp_secret, verify_session)
        return strategy(username, password, proxy, totp_secret)

    supported = {key: value for key, value in geo_kwargs.items() if key in signature.parameters}
    if strategy_accepts_verify:
        supported["verify_session"] = verify_session
    if supported:
        return strategy(
            username,
            password,
            proxy,
            totp_secret,
            **supported,
        )
    if strategy_accepts_verify:
        return strategy(username, password, proxy, totp_secret, verify_session)
    return strategy(username, password, proxy, totp_secret)


def _wrap_relogin_strategies_with_geo(
    relogin_strategies: dict[str, ReloginStrategy],
    *,
    country: str | None = None,
    country_code: int | None = None,
    locale: str | None = None,
    timezone_offset: int | None = None,
) -> dict[str, ReloginStrategy]:
    geo_kwargs = _geo_kwargs(
        country=country,
        country_code=country_code,
        locale=locale,
        timezone_offset=timezone_offset,
    )
    if not geo_kwargs:
        return relogin_strategies

    wrapped: dict[str, ReloginStrategy] = {}
    for key, strategy in relogin_strategies.items():
        wrapped[key] = (
            lambda username, password, proxy, totp_secret, verify_session=False, _strategy=strategy: _call_strategy_with_geo(
                _strategy,
                username,
                password,
                proxy,
                totp_secret,
                geo_kwargs=geo_kwargs,
                verify_session=verify_session,
            )
        )
    return wrapped


def relogin_account_sync(
    account_id: str,
    *,
    username: str,
    password: str,
    proxy: str | None = None,
    totp_secret: str | None = None,
    country: str | None = None,
    country_code: int | None = None,
    locale: str | None = None,
    timezone_offset: int | None = None,
    mode: str = "session_restore",
    verify_session: bool = False,
    create_authenticated_client_fn: CreateAuthenticatedClientFn = create_authenticated_client,
    new_client_fn: NewClientFn = new_client,
    classify_exception_fn: ClassifyExceptionFn = classify_exception,
    translate_exception_fn: ClassifyExceptionFn | None = None,
    relogin_strategies: dict[str, ReloginStrategy] | None = None,
    sleep_fn: SleepFn = time.sleep,
    jitter_uniform_fn: JitterUniformFn = random.uniform,
) -> dict:
    """Synchronous relogin with retry for transient failures."""
    if relogin_strategies is None:
        strategies = _build_relogin_strategies(
            create_authenticated_client_fn=create_authenticated_client_fn,
            new_client_fn=new_client_fn,
            country=country,
            country_code=country_code,
            locale=locale,
            timezone_offset=timezone_offset,
        )
    else:
        strategies = _wrap_relogin_strategies_with_geo(
            relogin_strategies,
            country=country,
            country_code=country_code,
            locale=locale,
            timezone_offset=timezone_offset,
        )

    default_strategy = strategies.get("session_restore", _RELOGIN_STRATEGIES["session_restore"])
    strategy = strategies.get(mode, default_strategy)
    strategy_accepts_verify = _strategy_accepts_verify_session(strategy)

    # Drop stale client reference without invalidating the server-side session.
    # Calling logout() here would invalidate the session file that
    # _relogin_session_restore is about to reuse, forcing a full re-auth.
    pop_client(account_id)

    cl = None
    for attempt in range(_MAX_RELOGIN_ATTEMPTS):
        try:
            if strategy_accepts_verify:
                cl = strategy(username, password, proxy, totp_secret, verify_session)
            else:
                cl = strategy(username, password, proxy, totp_secret)
            break  # success — exit retry loop
        except Exception as exc:
            if translate_exception_fn is not None:
                failure = translate_exception_fn(
                    exc, operation="relogin", account_id=account_id, username=username
                )
            else:
                failure = classify_exception_fn(
                    exc, operation="relogin", account_id=account_id, username=username
                )
            if getattr(failure, "retryable", False) and attempt < _MAX_RELOGIN_ATTEMPTS - 1:
                delay = _compute_retry_delay_seconds(
                    failure=failure,
                    retry_index=attempt,
                    account_id=account_id,
                    jitter_uniform_fn=jitter_uniform_fn,
                )
                sleep_fn(delay)
                continue  # transient — retry
            raise

    result = activate_account_client(account_id, cl)
    log_event(account_id, username, "relogin_success", status="active")
    return result
