"""Account context adapter - implements AccountContextPort.

Bridges to account service for account health and status info.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

from ai_copilot.application.smart_engagement.ports import AccountContextPort
from ai_copilot.application.smart_engagement.state import AccountHealth


@runtime_checkable
class AccountSummaryProvider(Protocol):
    """Application seam for account summary data."""

    def get_accounts_summary(self) -> dict:
        """Return account summaries keyed by account metadata."""


class AccountContextAdapter(AccountContextPort):
    """Fetches account health and constraints from account service."""

    def __init__(self, account_service: AccountSummaryProvider):
        """Initialize with app-owned account summary seam.

        Args:
            account_service: Account use-case style provider
        """
        self.account_service = account_service

    async def get_account_context(self, account_id: str) -> AccountHealth:
        """Fetch account health and status.

        Args:
            account_id: Account ID

        Returns:
            AccountHealth with status, cooldown, proxy, login_state

        Raises:
            ValueError: If account not found
        """
        summaries = await asyncio.to_thread(self.account_service.get_accounts_summary)
        accounts = summaries.get("accounts", [])
        account = next((item for item in accounts if item.get("id") == account_id), None)
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        status = str(account.get("status", "idle") or "idle").lower()
        login_state = "logged_in" if status == "active" else "needs_relogin"
        normalized_status = "active" if status == "active" else "needs_relogin"

        return AccountHealth(
            status=normalized_status,
            cooldown_until=None,
            proxy=account.get("proxy"),
            login_state=login_state,
            recent_actions=0,
        )

    async def validate_account_ready(self, account_id: str) -> bool:
        """Check if account is ready for engagement.

        Args:
            account_id: Account ID

        Returns:
            True if account is active and not in cooldown
        """
        try:
            health = await self.get_account_context(account_id)
            return (
                health.get("status") == "active"
                and health.get("cooldown_until") is None
            )
        except ValueError:
            return False
