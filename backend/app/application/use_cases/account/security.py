"""Account security use cases.

Thin orchestration around the InstagramAccountSecurityReader port.
Enforces the same precondition as edit flows (account exists and is
authenticated) before reading the 2FA / trusted-device snapshot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.dto.instagram_account_dto import AccountSecurityInfo

if TYPE_CHECKING:
    from app.application.ports.instagram_account_security import (
        InstagramAccountSecurityReader,
    )
    from app.application.ports.repositories import (
        AccountRepository,
        ClientRepository,
    )


class AccountSecurityUseCases:
    """Read-only access to the authenticated account's security posture."""

    def __init__(
        self,
        account_repo: "AccountRepository",
        client_repo: "ClientRepository",
        security_reader: "InstagramAccountSecurityReader",
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.security_reader = security_reader

    def _require_authenticated(self, account_id: str) -> None:
        if not self.account_repo.get(account_id):
            raise ValueError(f"Account {account_id!r} not found")
        if not self.client_repo.exists(account_id):
            raise ValueError(f"Account {account_id!r} is not authenticated")

    def get_account_security_info(self, account_id: str) -> AccountSecurityInfo:
        self._require_authenticated(account_id)
        return self.security_reader.get_account_security_info(account_id)
