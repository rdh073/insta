"""Adapter port interfaces - external service contracts."""

from __future__ import annotations

from typing import Optional, Protocol


class InstagramClient(Protocol):
    """Interface for Instagram client operations."""

    def create_authenticated_client(
        self,
        username: str,
        password: str,
        proxy: Optional[str],
        totp_secret: Optional[str] = None,
        verify_session: bool = False,
    ):
        """Create and authenticate a new Instagram client.

        When totp_secret is provided the TOTP code is generated and sent in the
        initial login() call (single-step). TwoFactorRequired is only raised for
        SMS/email 2FA where the caller must supply the code manually.
        When verify_session is True, a restored session is validated with a
        lightweight authenticated API call before it is accepted.
        """
        ...

    def complete_2fa(self, username: str, password: str, code: str, proxy: Optional[str]):
        """Complete SMS/email 2FA authentication after TwoFactorRequired was raised."""
        ...

    def relogin_account(self, account_id: str) -> dict:
        """Relogin account and return account dict."""
        ...


class ActivityLogger(Protocol):
    """Interface for activity logging."""

    def log_event(
        self,
        account_id: str,
        username: str,
        event: str,
        detail: Optional[str] = None,
        status: Optional[str] = None,
    ) -> None:
        """Log an account event."""
        ...


class TOTPManager(Protocol):
    """Interface for TOTP operations."""

    def generate_code(self, secret: str) -> str:
        """Generate TOTP code from secret."""
        ...

    def generate_secret(self) -> str:
        """Generate a new TOTP secret."""
        ...

    def get_provisioning_uri(self, secret: str, name: str) -> str:
        """Get QR code provisioning URI for a TOTP secret."""
        ...

    def verify_code(self, secret: str, code: str) -> bool:
        """Verify TOTP code."""
        ...

    def normalize_secret(self, secret: str) -> Optional[str]:
        """Normalize TOTP secret."""
        ...


class SessionStore(Protocol):
    """Interface for Instagram session file storage."""

    def save_session(self, username: str, session_data: dict) -> None:
        """Save session file for a username."""
        ...

    def load_session(self, username: str) -> dict:
        """Load session file for a username."""
        ...

    def delete_session(self, username: str) -> None:
        """Delete session file for a username if it exists."""
        ...

    def export_all_sessions(self) -> dict:
        """Export all session files as a dict."""
        ...

    def import_sessions(self, sessions: dict) -> None:
        """Import multiple session files."""
        ...


class Scheduler(Protocol):
    """Interface for job scheduling."""

    def schedule_post_job(self, job_id: str, scheduled_at: Optional[str] = None) -> None:
        """Schedule a post job for execution."""
        ...
