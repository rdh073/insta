"""Account profile use cases - listing, info, and summary queries."""

from __future__ import annotations

from typing import Optional

from ..dto.account_dto import (
    AccountResponse,
    AccountInfoResponse,
)
from ..ports import (
    AccountRepository,
    ClientRepository,
    StatusRepository,
)
from ..ports.instagram_error_handling import InstagramExceptionHandler
from ..ports.instagram_identity import InstagramIdentityReader
from ...domain.instagram_failures import InstagramAdapterError


class AccountProfileUseCases:
    """Read-only account profile queries."""

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        status_repo: StatusRepository,
        identity_reader: InstagramIdentityReader,
        error_handler: InstagramExceptionHandler,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.status_repo = status_repo
        self.identity_reader = identity_reader
        self.error_handler = error_handler

    def _get_account_status(self, account_id: str) -> str:
        """Determine current account status."""
        if self.client_repo.exists(account_id):
            return "active"
        return self.status_repo.get(account_id, "idle")

    def find_by_username(self, username: str) -> Optional[str]:
        """Find account ID by username."""
        return self.account_repo.find_by_username(username)

    def list_accounts(self) -> list[AccountResponse]:
        """List all accounts."""
        results = []
        for account_id in self.account_repo.list_all_ids():
            account = self.account_repo.get(account_id) or {}
            results.append(
                AccountResponse(
                    id=account_id,
                    username=account.get("username", ""),
                    status=self._get_account_status(account_id),
                    proxy=account.get("proxy"),
                    full_name=account.get("full_name"),
                    followers=account.get("followers"),
                    following=account.get("following"),
                    avatar=account.get("profile_pic_url"),
                    totp_enabled=account.get("totp_enabled", False),
                    last_verified_at=account.get("last_verified_at"),
                    last_error=account.get("last_error"),
                    last_error_code=account.get("last_error_code"),
                    last_error_family=account.get("last_error_family"),
                )
            )
        return results

    def get_account_info(self, account_id: str) -> AccountInfoResponse:
        """Get detailed account info from Instagram."""
        account = self.account_repo.get(account_id)
        if not account:
            return AccountInfoResponse(
                username="",
                error=f"Account {account_id} not found",
            )

        username = account.get("username", "")
        if not self.client_repo.exists(account_id):
            return AccountInfoResponse(
                username=username,
                error=f"{username} is not logged in",
            )

        try:
            # Use user_info(user_id) → /api/v1/users/{id}/info/ which returns
            # follower_count, following_count, and media_count.  The older
            # account_info() call hit accounts/current_user/?edit=true, an edit
            # endpoint that never includes engagement stats.
            profile = self.identity_reader.get_own_user_info(account_id)

            self.account_repo.update(
                account_id,
                full_name=profile.full_name,
                followers=profile.follower_count,
                following=profile.following_count,
            )

            return AccountInfoResponse(
                username=profile.username,
                full_name=profile.full_name,
                biography=profile.biography,
                followers=profile.follower_count,
                following=profile.following_count,
                media_count=profile.media_count,
                is_private=profile.is_private,
                is_verified=profile.is_verified,
                is_business=profile.is_business,
            )
        except InstagramAdapterError as exc:
            # Structured failure from adapter — use preserved message directly.
            return AccountInfoResponse(
                username=username,
                error=exc.failure.user_message,
            )
        except Exception as exc:
            failure = self.error_handler.handle(
                exc,
                operation="get_account_info",
                account_id=account_id,
                username=username,
            )
            return AccountInfoResponse(
                username=username,
                error=failure.user_message,
            )

    def get_accounts_summary(self) -> dict:
        """Get summary of all accounts for AI tools."""
        accounts = []
        for account_dto in self.list_accounts():
            accounts.append(
                {
                    **{
                        "id": account_dto.id,
                        "username": account_dto.username,
                        "proxy": account_dto.proxy or "none",
                        "status": account_dto.status,
                        "fullName": account_dto.full_name,
                        "followers": account_dto.followers or 0,
                        "following": account_dto.following or 0,
                    },
                }
            )
        return {
            "accounts": accounts,
            "total": len(accounts),
            "active": sum(1 for acc in accounts if acc["status"] == "active"),
        }
