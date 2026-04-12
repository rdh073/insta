"""TOTP management use cases - setup, verify, disable.

Error propagation: Validation errors raise ValueError directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...ports import AccountRepository, ActivityLogger, TOTPManager


class TOTPUseCases:
    """TOTP setup and management."""

    def __init__(
        self,
        account_repo: AccountRepository,
        logger: ActivityLogger,
        totp: TOTPManager,
    ):
        self.account_repo = account_repo
        self.logger = logger
        self.totp = totp

    def setup_totp(self, account_id: str) -> dict:
        """Generate a new TOTP secret for an account.
        
        Raises:
            ValueError: Account not found.
        """
        if not self.account_repo.exists(account_id):
            raise ValueError("Account not found")

        secret = self.totp.generate_secret()
        account = self.account_repo.get(account_id) or {}
        username = account.get("username", account_id)
        provisioning_uri = self.totp.get_provisioning_uri(secret, username)

        return {
            "account_id": account_id,
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "manual_entry_key": secret,
        }

    def verify_totp_setup(self, account_id: str, secret: str, code: str) -> dict:
        """Verify TOTP secret by checking if provided code is valid.
        
        Raises:
            ValueError: Account not found or invalid TOTP code.
        """
        if not self.account_repo.exists(account_id):
            raise ValueError("Account not found")

        # Verify the code matches the secret
        if not self.totp.verify_code(secret, code):
            raise ValueError("Invalid TOTP code. Please check your secret and time synchronization.")

        # If verification successful, store the secret
        self.account_repo.update(account_id, totp_secret=secret, totp_enabled=True)

        account = self.account_repo.get(account_id) or {}
        username = account.get("username", "")
        self.logger.log_event(account_id, username, "totp_enabled", status="active")

        return {"status": "ok", "message": "TOTP enabled successfully"}

    def disable_totp(self, account_id: str) -> dict:
        """Disable TOTP for an account.
        
        Raises:
            ValueError: Account not found.
        """
        if not self.account_repo.exists(account_id):
            raise ValueError("Account not found")

        self.account_repo.update(account_id, totp_secret=None, totp_enabled=False)

        account = self.account_repo.get(account_id) or {}
        username = account.get("username", "")
        self.logger.log_event(account_id, username, "totp_disabled", status="active")

        return {"status": "ok", "message": "TOTP disabled"}
