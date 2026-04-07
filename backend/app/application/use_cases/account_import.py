"""Account import use cases - text import and session archive import."""

from __future__ import annotations

import uuid
from contextlib import nullcontext

from ..dto.account_dto import (
    LoginRequest,
    AccountResponse,
)
from ..ports import (
    AccountRepository,
    ClientRepository,
    StatusRepository,
    InstagramClient,
    ActivityLogger,
    TOTPManager,
    SessionStore,
)
from ..ports.instagram_error_handling import InstagramExceptionHandler
from ..ports.instagram_identity import InstagramIdentityReader
from ..ports.persistence_models import AccountRecord
from ..ports.persistence_uow import PersistenceUnitOfWork

from .account_auth import AccountAuthUseCases


def parse_account_lines(text: str) -> list[dict]:
    """Parse account text format into structured dicts.

    Each line: username:password[:proxy][|totp_secret]

    Returns list of dicts with keys: username, password, proxy, totp_secret.
    Lines with fewer than 2 colon-separated parts are skipped.
    """
    results = []
    for line in text.strip().splitlines():
        totp_secret = None
        if "|" in line:
            line, totp_secret = line.rsplit("|", 1)
            totp_secret = totp_secret.strip() or None

        parts = line.strip().split(":")
        if len(parts) < 2:
            continue

        results.append({
            "username": parts[0],
            "password": parts[1],
            "proxy": parts[2] if len(parts) > 2 else None,
            "totp_secret": totp_secret,
        })
    return results


class AccountImportUseCases:
    """Import workflows: text format and session archive."""

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        status_repo: StatusRepository,
        instagram: InstagramClient,
        logger: ActivityLogger,
        totp: TOTPManager,
        session_store: SessionStore,
        error_handler: InstagramExceptionHandler,
        identity_reader: InstagramIdentityReader,
        uow: PersistenceUnitOfWork | None = None,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.status_repo = status_repo
        self.instagram = instagram
        self.logger = logger
        self.totp = totp
        self.session_store = session_store
        self.error_handler = error_handler
        self.identity_reader = identity_reader
        self.uow = uow

        # Delegate login to auth use cases (avoids duplicating login logic)
        self._auth = AccountAuthUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            status_repo=status_repo,
            instagram=instagram,
            logger=logger,
            totp=totp,
            session_store=session_store,
            error_handler=error_handler,
            identity_reader=identity_reader,
            uow=uow,
        )

    def _uow_scope(self):
        """Return transaction context when UoW is configured."""
        if self.uow is None:
            return nullcontext()
        return self.uow

    def _get_account_status(self, account_id: str) -> str:
        """Determine current account status."""
        if self.client_repo.exists(account_id):
            return "active"
        return self.status_repo.get(account_id, "idle")

    def import_accounts_text(self, text: str) -> list[AccountResponse]:
        """Import accounts from text format (username:password:proxy|totp_secret)."""
        results = []
        parsed = parse_account_lines(text)
        for entry in parsed:
            username = entry["username"]
            totp_secret = entry["totp_secret"]

            # Normalize TOTP secret
            if totp_secret:
                totp_secret = self.totp.normalize_secret(totp_secret)

            try:
                request = LoginRequest(
                    username=username,
                    password=entry["password"],
                    proxy=entry["proxy"],
                    totp_secret=totp_secret,
                )
                result = self._auth.login_account(request)
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

    def import_session_archive(self, sessions: dict) -> list[AccountResponse]:
        """Import accounts from session archive (dict of username -> session_data)."""
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
                status=self._get_account_status(account_id),
            ))

        return results
