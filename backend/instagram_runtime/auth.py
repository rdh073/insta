"""Authentication helpers extracted from the legacy Instagram boundary."""

from __future__ import annotations

import logging
from typing import Optional

from app.adapters.instagram.device_pool import random_device_profile
from app.adapters.instagram.exception_handler import instagram_exception_handler
from state import (
    IGClient,
    BadPassword,
    ChallengeRequired,
    LoginRequired,
    TwoFactorRequired,
    SESSIONS_DIR,
    account_to_dict,
    pop_pending_2fa_client,
    set_account_status,
    set_client,
    store_pending_2fa_client,
)


logger = logging.getLogger(__name__)


def _new_client(proxy: Optional[str] = None):
    client = IGClient()
    client.request_timeout = 60  # 60s per HTTP request - prevents challenge hang
    # Random inter-request delay mimics human behaviour and reduces the
    # likelihood of triggering Instagram rate-limits or bot detection.
    # Instagrapi best-practice: https://subzeroid.github.io/instagrapi/usage-guide/best-practices
    client.delay_range = [1, 3]
    if proxy:
        client.set_proxy(proxy)
    device, user_agent = random_device_profile()
    client.set_device(device)
    client.set_user_agent(user_agent)
    # Skip post-login feed calls (get_reels_tray_feed + get_timeline_feed).
    # instagrapi's default login_flow() emulates app behaviour but is not
    # required for session validity - skipping it makes fresh-account login
    # faster and avoids unnecessary API exposure on new accounts.
    client.login_flow = lambda: True
    return client


def _classify_exception(
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


def create_authenticated_client(
    username: str,
    password: str,
    proxy: Optional[str] = None,
    totp_secret: Optional[str] = None,
    verify_session: bool = False,
):
    """Authenticate and return a ready client."""
    session_file = SESSIONS_DIR / f"{username}.json"
    _saved_uuids: dict | None = None

    def _totp_code() -> str:
        """Generate a fresh TOTP code, or empty string if no secret."""
        if not totp_secret:
            return ""
        import pyotp

        return pyotp.TOTP(totp_secret).now()

    if session_file.exists():
        client = _new_client(proxy)
        client.load_settings(session_file)
        try:
            _saved_uuids = (client.get_settings() or {}).get("uuids")
        except Exception:
            pass
        try:
            client.login(username, password)
            if verify_session:
                client.account_info()

        except LoginRequired:
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
            except ChallengeRequired:
                raise
            except Exception:
                pass
            else:
                client.dump_settings(session_file)
                return client

        except TwoFactorRequired:
            store_pending_2fa_client(username, client)
            raise

        except BadPassword:
            raise

        except ChallengeRequired:
            raise

        except Exception:
            pass

        else:
            client.dump_settings(session_file)
            return client

    client = _new_client(proxy)
    if _saved_uuids:
        try:
            client.set_uuids(_saved_uuids)
        except Exception:
            pass
    try:
        client.login(username, password, verification_code=_totp_code())
    except TwoFactorRequired:
        store_pending_2fa_client(username, client)
        raise
    client.dump_settings(session_file)
    return client


def activate_account_client(account_id: str, client) -> dict:
    set_client(account_id, client)
    set_account_status(account_id, "active")
    return account_to_dict(account_id, status="active")


def complete_2fa_client(
    username: str,
    password: str,
    verification_code: str,
    proxy: Optional[str] = None,
):
    """Complete 2FA login for an account with a verification code."""
    session_file = SESSIONS_DIR / f"{username}.json"
    client = pop_pending_2fa_client(username)
    if client is None:
        client = _new_client(proxy)
    client.login(username, password, verification_code=verification_code)
    client.dump_settings(session_file)
    return client
