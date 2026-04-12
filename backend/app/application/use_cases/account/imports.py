"""Import use cases - text import and session archive import.

Error propagation: Import errors are caught and returned as error status in results.
Individual account failures don't stop the batch import process.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...dto.account_dto import LoginRequest, AccountResponse
    from ...ports import (
        AccountRepository,
        StatusRepository,
        TOTPManager,
        SessionStore,
        ActivityLogger,
    )
    from ...ports.instagram_error_handling import InstagramExceptionHandler
    from ...ports.persistence_models import AccountRecord


class ImportsUseCases:
    """Account import workflows."""

    def __init__(
        self,
        account_repo: AccountRepository,
        status_repo: StatusRepository,
        totp: TOTPManager,
        session_store: SessionStore,
        logger: ActivityLogger,
        error_handler: InstagramExceptionHandler,
        login_usecase,  # AuthUseCases - avoid circular import
    ):
        self.account_repo = account_repo
        self.status_repo = status_repo
        self.totp = totp
        self.session_store = session_store
        self.logger = logger
        self.error_handler = error_handler
        self.login_usecase = login_usecase

    def _get_account_status(self, account_id: str, client_repo) -> str:
        """Determine current account status."""
        if client_repo.exists(account_id):
            return "active"
        return self.status_repo.get(account_id, "idle")

    def import_accounts_text(self, text: str) -> list[AccountResponse]:
        """Import accounts from text format (username:password:proxy|totp_secret).
        
        Format: username:password[:proxy][|totp_secret]
        Each line is processed independently - failures don't stop the batch.
        """
        from ...dto.account_dto import LoginRequest, AccountResponse

        results = []
        for line in text.strip().splitlines():
            # Extract TOTP secret (if present) using | delimiter
            totp_secret = None
            if "|" in line:
                line, totp_secret = line.rsplit("|", 1)
                totp_secret = totp_secret.strip()
                # Normalize TOTP secret
                if totp_secret:
                    totp_secret = self.totp.normalize_secret(totp_secret)

            parts = line.strip().split(":")
            if len(parts) < 2:
                continue

            username, password = parts[0], parts[1]
            proxy = parts[2] if len(parts) > 2 else None

            try:
                request = LoginRequest(
                    username=username,
                    password=password,
                    proxy=proxy,
                    totp_secret=totp_secret,
                )
                result = self.login_usecase.login_account(request)
                results.append(result)
            except Exception as exc:
                failure = self.error_handler.handle(
                    exc,
                    operation="login",
                    username=username,
                )
                failed_id = str(uuid.uuid4())
                self.logger.log_event(
                    failed_id,
                    username,
                    "login_failed",
                    detail=failure.user_message,
                    status="error",
                )
                results.append(AccountResponse(
                    id=failed_id,
                    username=username,
                    status="error",
                ))

        return results

    def import_session_archive(self, sessions: dict, client_repo) -> list[AccountResponse]:
        """Import accounts from session archive (dict of username -> session_data).
        
        Saves session data and creates account records without attempting login.
        """
        from ...dto.account_dto import AccountResponse
        from ...ports.persistence_models import AccountRecord

        results = []
        for username, session_data in sessions.items():
            # Save session using the session store adapter
            self.session_store.save_session(username, session_data)

            account_id = str(uuid.uuid4())
            self.account_repo.set(
                account_id,
                AccountRecord(
                    username=username,
                    password="",
                    proxy=None,
                ),
            )

            results.append(AccountResponse(
                id=account_id,
                username=username,
                status=self._get_account_status(account_id, client_repo),
            ))

        return results
