from __future__ import annotations

import inspect
import os
from typing import Callable, Optional

from state import (
    IGClient,
    BadPassword,
    ChallengeRequired,
    CaptchaChallengeRequired,
    LoginRequired,
    TwoFactorRequired,
    SESSIONS_DIR,
    account_to_dict,
    pop_pending_2fa_client,
    set_account_status,
    set_client,
    store_pending_2fa_client,
)
from app.adapters.instagram.device_pool import random_device_profile
from app.adapters.instagram.exception_handler import instagram_exception_handler

_ENV_COUNTRY = "INSTAGRAM_COUNTRY"
_ENV_COUNTRY_CODE = "INSTAGRAM_COUNTRY_CODE"
_ENV_LOCALE = "INSTAGRAM_LOCALE"
_ENV_TIMEZONE_OFFSET = "INSTAGRAM_TIMEZONE_OFFSET"

_DEFAULT_COUNTRY = "ID"
_DEFAULT_COUNTRY_CODE = 62
_DEFAULT_LOCALE = "id_ID"
_DEFAULT_TIMEZONE_OFFSET = 7 * 3600


def _normalized_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalized_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return int(cleaned)
        except ValueError:
            return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_geo_locale_settings(
    *,
    country: str | None = None,
    country_code: int | None = None,
    locale: str | None = None,
    timezone_offset: int | None = None,
) -> dict[str, str | int]:
    resolved_country = (
        _normalized_optional_text(country)
        or _normalized_optional_text(os.getenv(_ENV_COUNTRY))
        or _DEFAULT_COUNTRY
    )
    resolved_locale = (
        _normalized_optional_text(locale)
        or _normalized_optional_text(os.getenv(_ENV_LOCALE))
        or _DEFAULT_LOCALE
    )
    resolved_country_code = _normalized_optional_int(country_code)
    if resolved_country_code is None:
        resolved_country_code = _normalized_optional_int(os.getenv(_ENV_COUNTRY_CODE))
    if resolved_country_code is None:
        resolved_country_code = _DEFAULT_COUNTRY_CODE
    resolved_timezone_offset = _normalized_optional_int(timezone_offset)
    if resolved_timezone_offset is None:
        resolved_timezone_offset = _normalized_optional_int(os.getenv(_ENV_TIMEZONE_OFFSET))
    if resolved_timezone_offset is None:
        resolved_timezone_offset = _DEFAULT_TIMEZONE_OFFSET

    resolved: dict[str, str | int] = {}
    if resolved_country is not None:
        resolved["country"] = resolved_country
    if resolved_country_code is not None:
        resolved["country_code"] = resolved_country_code
    if resolved_locale is not None:
        resolved["locale"] = resolved_locale
    if resolved_timezone_offset is not None:
        resolved["timezone_offset"] = resolved_timezone_offset
    return resolved


def _apply_geo_locale_settings(client, geo_settings: dict[str, str | int]) -> None:
    country = geo_settings.get("country")
    if isinstance(country, str) and hasattr(client, "set_country"):
        client.set_country(country)
    country_code = geo_settings.get("country_code")
    if isinstance(country_code, int) and hasattr(client, "set_country_code"):
        client.set_country_code(country_code)
    locale = geo_settings.get("locale")
    if isinstance(locale, str) and hasattr(client, "set_locale"):
        client.set_locale(locale)
    timezone_offset = geo_settings.get("timezone_offset")
    if isinstance(timezone_offset, int) and hasattr(client, "set_timezone_offset"):
        client.set_timezone_offset(timezone_offset)


def _new_client_with_optional_geo(
    new_client_fn: Callable[..., object],
    proxy: str | None,
    *,
    country: str | None = None,
    country_code: int | None = None,
    locale: str | None = None,
    timezone_offset: int | None = None,
):
    geo_kwargs = _resolve_geo_locale_settings(
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
        key: value
        for key, value in geo_kwargs.items()
        if key in signature.parameters
    }
    if supported_kwargs:
        return new_client_fn(proxy, **supported_kwargs)
    return new_client_fn(proxy)


def _non_interactive_handle_exception(_client, error: Exception) -> None:
    """Force private_request() to surface errors instead of auto-resolving.

    instagrapi's default path auto-calls ``challenge_resolve()`` when
    ``handle_exception`` is unset and may invoke stdin-driven handlers. Raising
    immediately keeps backend flows deterministic and non-blocking.
    """
    raise error


def _non_interactive_challenge_code_handler(
    username: str,
    choice=None,
) -> str:
    """Reject interactive challenge code prompts in backend runtime.

    Legacy fallback: when no ``InstagramChallengeResolverAdapter`` has been
    seated (see ``app.adapters.instagram.challenge_resolver.set_current_resolver``),
    instagrapi's default handler would block on stdin. Raising preserves the
    deterministic non-blocking contract expected by early tests.
    """
    challenge_kind = getattr(choice, "name", choice) or "unknown"
    raise ChallengeRequired(
        f"Challenge verification required for @{username} via {challenge_kind}."
    )


def _challenge_code_handler(username: str, choice=None) -> str:
    """Route the SDK's challenge prompt to the seated resolver (if any).

    - When a resolver is seated via ``set_current_resolver``, the call blocks
      until the operator submits a code through the HTTP layer (or cancels /
      times out). Returns the submitted 6-digit code on success.
    - When no resolver is seated, falls back to the raising stub so legacy
      callers (tests, scripts) see the previous non-interactive behaviour.
    """
    # Imported lazily so the module stays importable in environments that
    # don't install the FastAPI-facing adapter layer.
    from app.adapters.instagram.challenge_resolver import (
        ChallengeCancelledError,
        ChallengeTimeoutError,
        get_current_resolver,
    )

    resolver = get_current_resolver()
    if resolver is None:
        return _non_interactive_challenge_code_handler(username, choice)
    try:
        return resolver.handle_challenge_code_request(username, choice)
    except ChallengeCancelledError as exc:
        raise ChallengeRequired(str(exc)) from exc
    except ChallengeTimeoutError as exc:
        raise ChallengeRequired(str(exc)) from exc


def _non_interactive_change_password_handler(username: str) -> str:
    """Reject interactive password-change prompts in backend runtime."""
    raise ChallengeRequired(
        f"Challenge password reset required for @{username}."
    )


def new_client(
    proxy: Optional[str] = None,
    *,
    ig_client_cls=IGClient,
    device_profile_factory: Callable[[], tuple[dict, str]] = random_device_profile,
    country: str | None = None,
    country_code: int | None = None,
    locale: str | None = None,
    timezone_offset: int | None = None,
):
    client = ig_client_cls()
    client.request_timeout = 60  # 60s per HTTP request — prevents challenge hang
    # Random inter-request delay mimics human behaviour and reduces the
    # likelihood of triggering Instagram rate-limits or bot detection.
    # Instagrapi best-practice: https://subzeroid.github.io/instagrapi/usage-guide/best-practices
    client.delay_range = [1, 3]
    if proxy:
        client.set_proxy(proxy)
    device, user_agent = device_profile_factory()
    client.set_device(device)
    client.set_user_agent(user_agent)
    _apply_geo_locale_settings(
        client,
        _resolve_geo_locale_settings(
            country=country,
            country_code=country_code,
            locale=locale,
            timezone_offset=timezone_offset,
        ),
    )
    # Skip post-login feed calls (get_reels_tray_feed + get_timeline_feed).
    # instagrapi's default login_flow() emulates app behaviour but is not
    # required for session validity — skipping it makes fresh-account login
    # faster and avoids unnecessary API exposure on new accounts.
    client.login_flow = lambda: True
    # Disable instagrapi's implicit interactive challenge flow. The defaults
    # can block on input() in non-interactive server contexts.
    client.handle_exception = _non_interactive_handle_exception
    client.challenge_code_handler = _challenge_code_handler
    client.change_password_handler = _non_interactive_change_password_handler
    return client


def classify_exception(
    error: Exception,
    *,
    operation: str,
    account_id: str | None = None,
    username: str | None = None,
):
    """Translate an exception to a stable Instagram failure."""
    return instagram_exception_handler.handle(
        error,
        operation=operation,
        account_id=account_id,
        username=username,
    )


def _classify_exception(
    error: Exception,
    *,
    operation: str,
    account_id: str | None = None,
    username: str | None = None,
):
    return classify_exception(
        error,
        operation=operation,
        account_id=account_id,
        username=username,
    )


def create_authenticated_client(
    username: str,
    password: str,
    proxy: Optional[str] = None,
    totp_secret: Optional[str] = None,
    verify_session: bool = False,
    country: str | None = None,
    country_code: int | None = None,
    locale: str | None = None,
    timezone_offset: int | None = None,
    *,
    ig_client_cls=IGClient,
    new_client_fn: Callable[..., object] | None = None,
):
    """Authenticate and return a ready client.

    Follows the official instagrapi best-practice pattern:

    SESSION PATH (session file exists):
      1. load_settings  — restore cookies + device UUIDs (no network)
      2. login()        — uses session, NOT credentials (no network, no TOTP)
      3. optional verification via account_info() when verify_session=True
         - OK             → dump_settings, return
         - LoginRequired  → session expired:
             a. preserve device UUIDs from old settings
             b. reset settings (clear stale cookies)
             c. login(verification_code=totp) — full re-auth, TOTP passed upfront
             d. dump_settings, return
         - TwoFactorRequired → SMS/email 2FA, store pending client, raise
         - BadPassword    → raise (fresh login won't help)
         - other          → fall through to fresh login

    FRESH LOGIN PATH (no session file, or session path failed non-terminally):
      1. new client, restoring device UUIDs from the saved session file when
         available (avoids "new device" detection that triggers challenges)
      2. login(verification_code=totp) — TOTP passed upfront in first call
         - TwoFactorRequired (no TOTP secret) → store pending, raise
      3. dump_settings, return
    """
    if new_client_fn is None:
        new_client_fn = lambda account_proxy, **geo_kwargs: new_client(
            account_proxy,
            ig_client_cls=ig_client_cls,
            **geo_kwargs,
        )

    session_file = SESSIONS_DIR / f"{username}.json"
    # Device fingerprint captured from the session file before the login
    # attempt. Re-applied to the fresh client when the session-restore path
    # falls through, so Instagram sees the SAME device on re-auth.
    #
    # Without this, _new_client_with_optional_geo() picks a random device
    # profile on every fresh-login retry (device_profile_factory returns
    # different user_agents and form factors), so a few transient errors
    # cause Instagram to see one account logging in from Samsung, then
    # OnePlus, then Xiaomi in minutes — guaranteed to trigger bad_password
    # decoys and escalate to ChallengeRequired.
    _saved_uuids: dict | None = None
    _saved_device_settings: dict | None = None
    _saved_user_agent: str | None = None

    def _totp_code() -> str:
        """Generate a fresh TOTP code, or empty string if no secret."""
        if not totp_secret:
            return ""
        import pyotp

        return pyotp.TOTP(totp_secret).now()

    if session_file.exists():
        client = _new_client_with_optional_geo(
            new_client_fn,
            proxy,
            country=country,
            country_code=country_code,
            locale=locale,
            timezone_offset=timezone_offset,
        )
        client.load_settings(session_file)
        try:
            loaded_settings = client.get_settings() or {}
            _saved_uuids = loaded_settings.get("uuids")
            _saved_device_settings = loaded_settings.get("device_settings")
            _saved_user_agent = loaded_settings.get("user_agent")
        except Exception:
            pass
        try:
            # Session restore — login() uses cookies, not credentials.
            client.login(username, password)
            if verify_session:
                # account_info() is lighter than get_timeline_feed() for
                # session validation: small response, no feed payload, and
                # returns useful profile data (follower/following counts).
                client.account_info()

        except LoginRequired:
            # Session expired — preserve the FULL device fingerprint (not just
            # UUIDs), reset cookies, re-auth. Without device_settings +
            # user_agent, set_settings({}) followed by init() resets device
            # to the SDK defaults — Instagram then sees a different device
            # than the saved session and flags re-auth as new-device.
            try:
                old_settings = client.get_settings() or {}
                _saved_uuids = old_settings.get("uuids") or _saved_uuids
                _old_device_settings = old_settings.get("device_settings") or _saved_device_settings
                _old_user_agent = old_settings.get("user_agent") or _saved_user_agent
                client.set_settings({})
                if _old_device_settings:
                    client.set_device(_old_device_settings)
                if _old_user_agent:
                    client.set_user_agent(_old_user_agent)
                if _saved_uuids:
                    client.set_uuids(_saved_uuids)
                client.login(username, password, verification_code=_totp_code())
            except TwoFactorRequired:
                store_pending_2fa_client(username, client)
                raise
            except BadPassword:
                raise
            except (ChallengeRequired, CaptchaChallengeRequired):
                # Challenge cannot be resolved by retrying — propagate immediately
                # so the caller can mark the account as "challenge" and stop.
                # Falling through to fresh login would only trigger the same
                # challenge again and waste an API call.
                raise
            except Exception:
                pass  # other transient failures → fall through to fresh login
            else:
                client.dump_settings(session_file)
                return client

        except TwoFactorRequired:
            # Only raised when totp_secret is absent (SMS/email 2FA).
            store_pending_2fa_client(username, client)
            raise

        except BadPassword:
            raise  # wrong credential — a fresh client won't help

        except (ChallengeRequired, CaptchaChallengeRequired):
            # Challenge required on initial session restore — propagate directly.
            raise

        except Exception:
            # Non-terminal failure (corruption, timeout, etc.).
            # Fall through to a completely fresh login below.
            pass

        else:
            client.dump_settings(session_file)
            return client

    # Fresh login — new client, stale cookies discarded.
    # Restore the FULL device fingerprint (UUIDs + device_settings +
    # user_agent) from the prior session so Instagram recognises the same
    # device and does not flag this as a new-device login.
    #
    # Carrying over only UUIDs (earlier behaviour) is not enough: each
    # _new_client_with_optional_geo() call picks a fresh random device via
    # device_profile_factory(), so bursts of relogin attempts look to
    # Instagram like the same account logging in from wildly different
    # devices. Instagram's anti-abuse responds with deceptive bad_password
    # replies that quickly escalate to ChallengeRequired.
    client = _new_client_with_optional_geo(
        new_client_fn,
        proxy,
        country=country,
        country_code=country_code,
        locale=locale,
        timezone_offset=timezone_offset,
    )
    if _saved_device_settings:
        try:
            client.set_device(_saved_device_settings)
        except Exception:
            pass  # unexpected device_settings shape — keep random fallback
    if _saved_user_agent:
        try:
            client.set_user_agent(_saved_user_agent)
        except Exception:
            pass  # unexpected user_agent shape — keep random fallback
    if _saved_uuids:
        try:
            client.set_uuids(_saved_uuids)
        except Exception:
            pass  # unexpected UUID shape — continue with fresh fingerprint
    try:
        # TOTP passed upfront in the initial login() call — the correct
        # instagrapi pattern for TOTP (avoids the two-step TwoFactorRequired flow).
        client.login(username, password, verification_code=_totp_code())
    except TwoFactorRequired:
        # Only reached when totp_secret is absent (SMS/email 2FA).
        store_pending_2fa_client(username, client)
        raise
    client.dump_settings(session_file)
    return client


def activate_account_client(account_id: str, client) -> dict:
    # Activate immediately — session already persisted by create_authenticated_client.
    # Profile enrichment (followers/following) is handled by the background task
    # scheduled in the HTTP route layer, so we don't fetch it here.
    set_client(account_id, client)
    set_account_status(account_id, "active")
    return account_to_dict(account_id, status="active")


def complete_2fa_client(
    username: str,
    password: str,
    verification_code: str,
    proxy: Optional[str] = None,
    country: str | None = None,
    country_code: int | None = None,
    locale: str | None = None,
    timezone_offset: int | None = None,
    *,
    ig_client_cls=IGClient,
    new_client_fn: Callable[..., object] | None = None,
):
    """Complete 2FA login for an account with a verification code."""
    if new_client_fn is None:
        new_client_fn = lambda account_proxy, **geo_kwargs: new_client(
            account_proxy,
            ig_client_cls=ig_client_cls,
            **geo_kwargs,
        )
    session_file = SESSIONS_DIR / f"{username}.json"
    client = pop_pending_2fa_client(username)
    if client is None:
        # Fallback: create fresh client (handles TOTP case where identifier can refresh)
        client = _new_client_with_optional_geo(
            new_client_fn,
            proxy,
            country=country,
            country_code=country_code,
            locale=locale,
            timezone_offset=timezone_offset,
        )
    client.login(username, password, verification_code=verification_code)
    client.dump_settings(session_file)
    return client
