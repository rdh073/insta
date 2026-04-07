"""Account proxy use cases - proxy assignment, bulk proxy, proxy checking."""

from __future__ import annotations

from contextlib import nullcontext

from ..dto.account_dto import AccountResponse
from ..ports import (
    AccountRepository,
    ClientRepository,
    StatusRepository,
    ActivityLogger,
)
from ..ports.persistence_uow import PersistenceUnitOfWork
from ..ports.proxy_checker import ProxyCheckerPort, ProxyCheckResult


class AccountProxyUseCases:
    """Proxy management workflows for accounts."""

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        status_repo: StatusRepository,
        logger: ActivityLogger,
        proxy_checker: ProxyCheckerPort | None = None,
        uow: PersistenceUnitOfWork | None = None,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.status_repo = status_repo
        self.logger = logger
        self.proxy_checker = proxy_checker
        self.uow = uow

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

    def set_account_proxy(self, account_id: str, proxy: str) -> AccountResponse:
        """Set proxy for an account."""
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
        if not self.proxy_checker:
            return ProxyCheckResult(
                proxy_url=proxy_url,
                reachable=False,
                error="proxy checker not configured",
            )
        return await self.proxy_checker.check(proxy_url)
