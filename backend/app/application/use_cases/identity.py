"""Identity use cases for Instagram account and user profile reads."""

from __future__ import annotations

from app.application.dto.instagram_identity_dto import (
    AuthenticatedAccountProfile,
    PublicUserProfile,
)
from app.application.ports.instagram_identity import InstagramIdentityReader
from app.application.ports.repositories import AccountRepository, ClientRepository


class IdentityUseCases:
    """Application orchestration for identity reads."""

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        identity_reader: InstagramIdentityReader,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.identity_reader = identity_reader

    def get_authenticated_account(self, account_id: str) -> AuthenticatedAccountProfile:
        """Read authenticated profile for a logged-in account."""
        account = self.account_repo.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        if not self.client_repo.exists(account_id):
            raise ValueError(f"Account {account_id} is not authenticated")
        return self.identity_reader.get_authenticated_account(account_id)

    def get_public_user_by_id(self, account_id: str, user_id: int) -> PublicUserProfile:
        """Read public user profile by numeric Instagram user ID."""
        account = self.account_repo.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        if not self.client_repo.exists(account_id):
            raise ValueError(f"Account {account_id} is not authenticated")
        return self.identity_reader.get_public_user_by_id(account_id, user_id)

    def get_public_user_by_username(
        self,
        account_id: str,
        username: str,
    ) -> PublicUserProfile:
        """Read public user profile by username."""
        clean_username = username.strip().lstrip("@")
        if not clean_username:
            raise ValueError("username is required")
        account = self.account_repo.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        if not self.client_repo.exists(account_id):
            raise ValueError(f"Account {account_id} is not authenticated")
        return self.identity_reader.get_public_user_by_username(account_id, clean_username)
