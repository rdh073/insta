"""Instagram client adapter wrapping instagrapi."""

from __future__ import annotations

from typing import Optional

import instagram as instagram_module
from app.application.ports.adapters import ReloginMode


class InstagramClientAdapter:
    """Adapts instagrapi operations to application layer.
    
    Focuses on authentication and session management.
    For reading identity data, use InstagramIdentityReaderAdapter instead.
    """

    def create_authenticated_client(
        self,
        username: str,
        password: str,
        proxy: Optional[str],
        totp_secret: Optional[str] = None,
        verify_session: bool = False,
        country: Optional[str] = None,
        country_code: Optional[int] = None,
        locale: Optional[str] = None,
        timezone_offset: Optional[int] = None,
    ):
        """Create and authenticate a new Instagram client."""
        return instagram_module.create_authenticated_client(
            username,
            password,
            proxy,
            totp_secret,
            verify_session=verify_session,
            country=country,
            country_code=country_code,
            locale=locale,
            timezone_offset=timezone_offset,
        )

    def complete_2fa(
        self,
        username: str,
        password: str,
        code: str,
        proxy: Optional[str],
        country: Optional[str] = None,
        country_code: Optional[int] = None,
        locale: Optional[str] = None,
        timezone_offset: Optional[int] = None,
    ):
        """Complete 2FA authentication."""
        return instagram_module.complete_2fa_client(
            username,
            password,
            code,
            proxy,
            country=country,
            country_code=country_code,
            locale=locale,
            timezone_offset=timezone_offset,
        )

    def relogin_account(
        self,
        account_id: str,
        *,
        username: str,
        password: str,
        proxy: Optional[str] = None,
        totp_secret: Optional[str] = None,
        country: Optional[str] = None,
        country_code: Optional[int] = None,
        locale: Optional[str] = None,
        timezone_offset: Optional[int] = None,
        mode: ReloginMode = ReloginMode.SESSION_RESTORE,
        verify_session: bool = False,
    ) -> dict:
        """Relogin account using *mode* strategy. Returns account dict.

        ``SESSION_RESTORE`` (default) tries the saved session file first.
        ``FRESH_CREDENTIALS`` skips the session file and always authenticates
        with stored username + password + TOTP — required after server-side
        force-logouts (Instagram logout_reason:8).
        """
        return instagram_module.relogin_account_sync(
            account_id,
            username=username,
            password=password,
            proxy=proxy,
            totp_secret=totp_secret,
            country=country,
            country_code=country_code,
            locale=locale,
            timezone_offset=timezone_offset,
            mode=mode.value,
            verify_session=verify_session,
        )

    def run_post_job(self, job_id: str) -> None:
        """Execute a post job (upload media to all target accounts)."""
        instagram_module.run_post_job(job_id)
