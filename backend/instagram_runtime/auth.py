from __future__ import annotations

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
    """Reject interactive challenge code prompts in backend runtime."""
    challenge_kind = getattr(choice, "name", choice) or "unknown"
    raise ChallengeRequired(
        f"Challenge verification required for @{username} via {challenge_kind}."
    )


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
    # Skip post-login feed calls (get_reels_tray_feed + get_timeline_feed).
    # instagrapi's default login_flow() emulates app behaviour but is not
    # required for session validity — skipping it makes fresh-account login
    # faster and avoids unnecessary API exposure on new accounts.
    client.login_flow = lambda: True
    # Disable instagrapi's implicit interactive challenge flow. The defaults
    # can block on input() in non-interactive server contexts.
    client.handle_exception = _non_interactive_handle_exception
    client.challenge_code_handler = _non_interactive_challenge_code_handler
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
    *,
    ig_client_cls=IGClient,
    new_client_fn: Callable[[Optional[str]], object] | None = None,
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
        new_client_fn = lambda account_proxy: new_client(
            account_proxy,
            ig_client_cls=ig_client_cls,
        )

    session_file = SESSIONS_DIR / f"{username}.json"
    # Device UUIDs captured from the session file before the login attempt.
    # Re-applied to the fresh client when the session-restore path falls
    # through, so Instagram sees the same device fingerprint on re-auth.
    _saved_uuids: dict | None = None

    def _totp_code() -> str:
        """Generate a fresh TOTP code, or empty string if no secret."""
        if not totp_secret:
            return ""
        import pyotp

        return pyotp.TOTP(totp_secret).now()

    if session_file.exists():
        client = new_client_fn(proxy)
        client.load_settings(session_file)
        try:
            _saved_uuids = (client.get_settings() or {}).get("uuids")
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
            # Session expired — preserve device UUIDs, reset cookies, re-auth.
            try:
                old_settings = client.get_settings()
                client.set_settings({})
                client.set_uuids(old_settings["uuids"])
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
    # Restore device UUIDs from the prior session (captured above) so
    # Instagram recognises the same device fingerprint and does not flag
    # this as a new-device login, which would trigger security challenges.
    client = new_client_fn(proxy)
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
    *,
    ig_client_cls=IGClient,
    new_client_fn: Callable[[Optional[str]], object] | None = None,
):
    """Complete 2FA login for an account with a verification code."""
    if new_client_fn is None:
        new_client_fn = lambda account_proxy: new_client(
            account_proxy,
            ig_client_cls=ig_client_cls,
        )
    session_file = SESSIONS_DIR / f"{username}.json"
    client = pop_pending_2fa_client(username)
    if client is None:
        # Fallback: create fresh client (handles TOTP case where identifier can refresh)
        client = new_client_fn(proxy)
    client.login(username, password, verification_code=verification_code)
    client.dump_settings(session_file)
    return client
