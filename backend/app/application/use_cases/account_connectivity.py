"""Account connectivity use cases - runtime health probing via Instagram API."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from ..dto.account_dto import AccountResponse
from ..ports import (
    AccountRepository,
    ClientRepository,
    StatusRepository,
    ActivityLogger,
)
from ..ports.instagram_error_handling import InstagramExceptionHandler
from ..ports.instagram_identity import InstagramIdentityReader
from ...domain.instagram_failures import InstagramFailure, InstagramAdapterError


def _connectivity_failure_status(failure: InstagramFailure) -> str | None:
    """Determine the account status to set after a connectivity probe failure.

    Returns None when the failure is transient and the account status should
    be left unchanged (credentials may still be valid).
    """
    if failure.family == "challenge":
        return "challenge"
    if failure.code == "two_factor_required":
        return "2fa_required"
    if failure.retryable and not failure.requires_user_action:
        # Transient failure (network, rate-limit) — do not overwrite a potentially valid status.
        return None
    return "error"


class AccountConnectivityUseCases:
    """Runtime connectivity probing for already-active Instagram accounts.

    Distinct from session restore/relogin: uses ``account_info()`` (via
    ``identity_reader``) as a lightweight authenticated read to confirm the
    current session is still usable.  Updates ``last_verified_at``,
    ``last_error``, and ``last_error_code`` after each probe, and only
    overwrites ``status`` when the failure indicates the session is truly
    broken (auth/challenge/2FA), not for transient network/rate-limit errors.
    """

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        status_repo: StatusRepository,
        identity_reader: InstagramIdentityReader,
        error_handler: InstagramExceptionHandler,
        logger: ActivityLogger,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.status_repo = status_repo
        self.identity_reader = identity_reader
        self.error_handler = error_handler
        self.logger = logger

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_account_status(self, account_id: str) -> str:
        if self.client_repo.exists(account_id):
            return "active"
        return self.status_repo.get(account_id, "idle")

    def _mark_verified(self, account_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.account_repo.update(
            account_id,
            last_verified_at=now,
            last_error=None,
            last_error_code=None,
        )

    def _mark_error(self, account_id: str, error: str, code: str | None = None) -> None:
        self.account_repo.update(
            account_id,
            last_error=error,
            last_error_code=code,
        )

    def _build_response(
        self, account_id: str, status: str | None = None
    ) -> AccountResponse:
        account = self.account_repo.get(account_id) or {}
        get = (
            account.get
            if isinstance(account, dict)
            else lambda k, d=None: getattr(account, k, d)
        )
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
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def verify_account_connectivity(self, account_id: str) -> AccountResponse:
        """Probe Instagram connectivity for an already-active account.

        Calls ``account_info()`` via the identity reader as a lightweight
        authenticated read.  On success the health-tracking fields are
        refreshed and profile metadata is updated.  On failure the error is
        classified and only truly broken sessions have their status overwritten.

        Args:
            account_id: The application account ID.

        Returns:
            AccountResponse with updated health fields.

        Raises:
            ValueError: If account does not exist or no live client is present.
        """
        account = self.account_repo.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        get = (
            account.get
            if isinstance(account, dict)
            else lambda k, d=None: getattr(account, k, d)
        )
        username = get("username", "")

        if not self.client_repo.exists(account_id):
            raise ValueError(f"{username} is not logged in")

        try:
            profile = self.identity_reader.get_authenticated_account(account_id)

            # Success path — refresh health fields and metadata.
            self._mark_verified(account_id)
            updates: dict = {"full_name": profile.full_name}
            if profile.profile_pic_url:
                updates["profile_pic_url"] = profile.profile_pic_url
            if profile.follower_count is not None:
                updates["followers"] = profile.follower_count
            if profile.following_count is not None:
                updates["following"] = profile.following_count
            self.account_repo.update(account_id, **updates)
            self.status_repo.set(account_id, "active")
            self.logger.log_event(
                account_id, username, "connectivity_verified", status="active"
            )
            return self._build_response(account_id, status="active")

        except InstagramAdapterError as exc:
            # Structured failure from identity reader — use metadata directly
            # without re-running the error handler (preserves auth/challenge/2FA/transient semantics).
            failure = exc.failure
            new_status = _connectivity_failure_status(failure)
            if new_status is not None:
                self.status_repo.set(account_id, new_status)
                # Evict the dead client so _get_account_status() falls through
                # to status_repo instead of returning "active" from a stale entry.
                if self.client_repo.exists(account_id):
                    self.client_repo.remove(account_id)
            self._mark_error(account_id, failure.user_message, failure.code)
            self.logger.log_event(
                account_id,
                username,
                "connectivity_failed",
                detail=failure.user_message,
                status=new_status or self._get_account_status(account_id),
            )
            return self._build_response(
                account_id,
                status=new_status or self._get_account_status(account_id),
            )

        except Exception as exc:
            # Generic fallback for unexpected exceptions — re-classify via error handler.
            failure = self.error_handler.handle(
                exc,
                operation="verify_connectivity",
                account_id=account_id,
                username=username,
            )
            new_status = _connectivity_failure_status(failure)
            if new_status is not None:
                self.status_repo.set(account_id, new_status)
                if self.client_repo.exists(account_id):
                    self.client_repo.remove(account_id)
            self._mark_error(account_id, failure.user_message, failure.code)
            self.logger.log_event(
                account_id,
                username,
                "connectivity_failed",
                detail=failure.user_message,
                status=new_status or self._get_account_status(account_id),
            )
            return self._build_response(
                account_id,
                status=new_status or self._get_account_status(account_id),
            )

    async def bulk_verify_accounts(
        self, account_ids: list[str], concurrency: int = 3
    ) -> list[AccountResponse]:
        """Probe connectivity for multiple accounts with limited concurrency.

        Concurrency is deliberately low (default 3) to avoid triggering
        Instagram rate-limits when probing many accounts at once.

        Args:
            account_ids: List of account IDs to probe.
            concurrency: Maximum number of simultaneous probes.

        Returns:
            List of AccountResponse in the same order as input.
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def _probe_one(account_id: str) -> AccountResponse:
            async with semaphore:
                try:
                    return await asyncio.to_thread(
                        self.verify_account_connectivity, account_id
                    )
                except ValueError as exc:
                    # Account not found or not logged in — return lightweight error response.
                    account = self.account_repo.get(account_id) or {}
                    username = (
                        account.get("username", "")
                        if isinstance(account, dict)
                        else getattr(account, "username", "")
                    )
                    return AccountResponse(
                        id=account_id,
                        username=username,
                        status="error",
                        last_error=str(exc),
                    )

        return list(await asyncio.gather(*[_probe_one(aid) for aid in account_ids]))
