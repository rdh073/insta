"""Instagram client adapter wrapping instagrapi."""

from __future__ import annotations

from typing import Optional

import instagram as instagram_module


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
    ):
        """Create and authenticate a new Instagram client."""
        return instagram_module.create_authenticated_client(
            username,
            password,
            proxy,
            totp_secret,
            verify_session=verify_session,
        )

    def complete_2fa(self, username: str, password: str, code: str, proxy: Optional[str]):
        """Complete 2FA authentication."""
        return instagram_module.complete_2fa_client(username, password, code, proxy)

    def relogin_account(
        self,
        account_id: str,
        *,
        username: str,
        password: str,
        proxy: Optional[str] = None,
        totp_secret: Optional[str] = None,
    ) -> dict:
        """Relogin account using stored credentials. Returns account dict."""
        return instagram_module.relogin_account_sync(
            account_id,
            username=username,
            password=password,
            proxy=proxy,
            totp_secret=totp_secret,
        )

    def run_post_job(self, job_id: str) -> None:
        """Execute a post job (upload media to all target accounts)."""
        instagram_module.run_post_job(job_id)
