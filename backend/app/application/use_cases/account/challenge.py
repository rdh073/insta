"""Challenge use cases — operator-facing surface for Instagram login challenges.

These use cases are thin wrappers over
:class:`~app.application.ports.instagram_challenge.InstagramChallengeResolver`
that validate input and translate adapter responses into DTOs suitable for the
HTTP layer. They do not require the account to be authenticated — the
challenge is part of the login flow itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...dto.instagram_challenge_dto import (
    ChallengePending,
    ChallengeResolution,
)

if TYPE_CHECKING:
    from ...ports.instagram_challenge import InstagramChallengeResolver
    from ...ports.repositories import AccountRepository


class ChallengeUseCases:
    """Expose pending login challenges to the HTTP layer."""

    def __init__(
        self,
        *,
        resolver: InstagramChallengeResolver,
        account_repo: AccountRepository,
    ) -> None:
        self._resolver = resolver
        self._account_repo = account_repo

    def _require_account(self, account_id: str) -> None:
        if not account_id:
            raise ValueError("account_id is required")
        if not self._account_repo.exists(account_id):
            raise ValueError("Account not found")

    def list_pending(self) -> list[ChallengePending]:
        """Return every in-flight challenge across all accounts."""
        return list(self._resolver.list_pending())

    def get(self, account_id: str) -> ChallengePending | None:
        """Return the pending challenge for ``account_id`` or None."""
        self._require_account(account_id)
        return self._resolver.get_pending(account_id)

    def submit_code(self, account_id: str, code: str) -> ChallengeResolution:
        """Submit an operator-entered code to unblock a pending login."""
        self._require_account(account_id)
        return self._resolver.submit_code(account_id, code)

    def cancel(self, account_id: str) -> ChallengeResolution:
        """Abort a pending challenge; the SDK's login() call will raise."""
        self._require_account(account_id)
        return self._resolver.cancel(account_id)
