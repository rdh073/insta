"""Account TOTP use cases - setup, verify, and disable TOTP."""

from __future__ import annotations

from contextlib import nullcontext

from ..ports import (
    AccountRepository,
    ActivityLogger,
    TOTPManager,
)
from ..ports.persistence_uow import PersistenceUnitOfWork


class AccountTOTPUseCases:
    """TOTP management workflows for accounts."""

    def __init__(
        self,
        account_repo: AccountRepository,
        logger: ActivityLogger,
        totp: TOTPManager,
        uow: PersistenceUnitOfWork | None = None,
    ):
        self.account_repo = account_repo
        self.logger = logger
        self.totp = totp
        self.uow = uow

    def _uow_scope(self):
        """Return transaction context when UoW is configured."""
        if self.uow is None:
            return nullcontext()
        return self.uow

    def setup_totp(self, account_id: str) -> dict:
        """Generate a new TOTP secret for an account."""
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
        """Verify TOTP secret by checking if provided code is valid."""
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
        """Disable TOTP for an account."""
        if not self.account_repo.exists(account_id):
            raise ValueError("Account not found")

        self.account_repo.update(account_id, totp_secret=None, totp_enabled=False)

        account = self.account_repo.get(account_id) or {}
        username = account.get("username", "")
        self.logger.log_event(account_id, username, "totp_disabled", status="active")

        return {"status": "ok", "message": "TOTP disabled"}
