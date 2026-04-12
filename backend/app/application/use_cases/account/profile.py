"""Profile and listing use cases - account info, list, summary, proxy management.

Error propagation: All Instagram exceptions are translated via InstagramExceptionHandler
to InstagramFailure domain objects before being re-raised or returned in error fields.
"""

from __future__ import annotations

from contextlib import nullcontext
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...dto.account_dto import AccountResponse, AccountInfoResponse
    from ...ports import (
        AccountRepository,
        ClientRepository,
        StatusRepository,
        ActivityLogger,
    )
    from ...ports.instagram_error_handling import InstagramExceptionHandler
    from ...ports.instagram_identity import InstagramIdentityReader
    from ...ports.persistence_models import AccountRecord
    from ...ports.persistence_uow import PersistenceUnitOfWork
    from ...ports.proxy_checker import ProxyCheckerPort, ProxyCheckResult


class ProfileUseCases:
    """Account profile, listing, and proxy management."""

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        status_repo: StatusRepository,
        logger: ActivityLogger,
        error_handler: InstagramExceptionHandler,
        identity_reader: InstagramIdentityReader,
        uow: PersistenceUnitOfWork | None = None,
        proxy_checker: ProxyCheckerPort | None = None,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.status_repo = status_repo
        self.logger = logger
        self.error_handler = error_handler
        self.identity_reader = identity_reader
        self.uow = uow
        self.proxy_checker = proxy_checker

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

    def _build_account_response(
        self,
        account_id: str,
        account: dict | AccountRecord | None = None,
        status: str | None = None,
    ) -> AccountResponse:
        """Build AccountResponse with session health fields."""
        from ...dto.account_dto import AccountResponse

        if account is None:
            account = self.account_repo.get(account_id) or {}

        get = account.get if hasattr(account, "get") else lambda k, d=None: getattr(account, k, d)

        return AccountResponse(
            id=account_id,
            username=get("username", ""),
            status=status or self._get_account_status(account_id),
            proxy=get("proxy"),
            full_name=get("full_name"),
            followers=get("followers"),
            following=get("following"),
            avatar=get("profile_pic_url"),
            totp_enabled=get("totp_enabled", False),
            last_verified_at=get("last_verified_at"),
            last_error=get("last_error"),
            last_error_code=get("last_error_code"),
            last_error_family=get("last_error_family"),
        )

    def find_by_username(self, username: str) -> str | None:
        """Find account ID by username."""
        return self.account_repo.find_by_username(username)

    def list_accounts(self) -> list[AccountResponse]:
        """List all accounts."""
        results = []
        for account_id in self.account_repo.list_all_ids():
            account = self.account_repo.get(account_id) or {}
            results.append(self._build_account_response(account_id, account))
        return results

    def get_accounts_summary(self) -> dict:
        """Get summary of all accounts for AI tools."""
        accounts = []
        for account_dto in self.list_accounts():
            accounts.append({
                **{
                    "id": account_dto.id,
                    "username": account_dto.username,
                    "proxy": account_dto.proxy or "none",
                    "status": account_dto.status,
                    "fullName": account_dto.full_name,
                    "followers": account_dto.followers or 0,
                    "following": account_dto.following or 0,
                    "client_exists": self.client_repo.exists(account_dto.id),
                },
            })
        return {
            "accounts": accounts,
            "total": len(accounts),
            "active": sum(1 for acc in accounts if acc["status"] == "active"),
        }

    def get_account_info(self, account_id: str) -> AccountInfoResponse:
        """Get detailed account info from Instagram.
        
        Returns AccountInfoResponse with error field set on failure.
        """
        from ...dto.account_dto import AccountInfoResponse

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
            # Get authenticated account profile via identity reader
            profile = self.identity_reader.get_authenticated_account(account_id)
            
            # Update cached account metadata with latest data
            self.account_repo.update(
                account_id,
                full_name=profile.full_name,
                followers=None,
                following=None,
            )
            
            return AccountInfoResponse(
                username=profile.username,
                full_name=profile.full_name,
                biography=profile.biography,
                followers=None,
                following=None,
                media_count=None,
                is_private=profile.is_private,
                is_verified=profile.is_verified,
                is_business=profile.is_business,
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

    def set_account_proxy(self, account_id: str, proxy: str) -> AccountResponse:
        """Set proxy for an account.
        
        Raises:
            ValueError: Account not found.
        """
        from ...dto.account_dto import AccountResponse

        with self._uow_scope():
            if not self.account_repo.exists(account_id):
                raise ValueError("Account not found")

            account = self.account_repo.get(account_id) or {}
            username = account.get("username", "")

            self.account_repo.update(account_id, proxy=proxy)
            client = self.client_repo.get(account_id)
            if client:
                client.set_proxy(proxy)

            self.logger.log_event(account_id, username, "proxy_changed", detail=proxy)

            return AccountResponse(
                id=account_id,
                username=username,
                status=self._get_account_status(account_id),
                proxy=proxy,
            )

    def bulk_set_proxy(self, account_ids: list[str], proxy: str) -> list[AccountResponse]:
        """Set proxy for multiple accounts."""
        from ...dto.account_dto import AccountResponse

        results = []
        for account_id in account_ids:
            if not self.account_repo.exists(account_id):
                results.append(AccountResponse(
                    id=account_id,
                    username="",
                    status="not_found",
                ))
                continue

            account = self.account_repo.get(account_id) or {}
            username = account.get("username", "")
            self.account_repo.update(account_id, proxy=proxy)
            client = self.client_repo.get(account_id)
            if client:
                client.set_proxy(proxy)

            self.logger.log_event(account_id, username, "proxy_changed", detail=proxy)
            results.append(AccountResponse(
                id=account_id,
                username=username,
                status="ok",
                proxy=proxy,
            ))
        return results

    async def check_proxy(self, proxy_url: str) -> ProxyCheckResult:
        """Test if a proxy URL is reachable and measure its latency.

        Returns ProxyCheckResult with reachable=True and latency_ms on success,
        or reachable=False and error message on failure. Never raises.
        """
        from ...ports.proxy_checker import ProxyCheckResult

        if not self.proxy_checker:
            return ProxyCheckResult(
                proxy_url=proxy_url,
                reachable=False,
                error="proxy checker not configured",
            )
        return await self.proxy_checker.check(proxy_url)
