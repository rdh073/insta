"""Relogin use cases - single and bulk relogin with concurrency control.

Error propagation: All Instagram exceptions are translated via InstagramExceptionHandler
to InstagramFailure domain objects. The failure is attached to the exception as
_instagram_failure attribute and also stored in account metadata (last_error fields).
"""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from typing import TYPE_CHECKING

from ...ports import ReloginMode
from ..account_status_policy import (
    should_use_fresh_credentials_relogin,
    status_from_failure,
)

if TYPE_CHECKING:
    from ...dto.account_dto import AccountResponse, BulkReloginRequest
    from ...ports import (
        AccountRepository,
        StatusRepository,
        InstagramClient,
        ActivityLogger,
    )
    from ...ports.instagram_error_handling import InstagramExceptionHandler


class ReloginUseCases:
    """Relogin workflows with per-account locking."""

    def __init__(
        self,
        account_repo: AccountRepository,
        status_repo: StatusRepository,
        instagram: InstagramClient,
        logger: ActivityLogger,
        error_handler: InstagramExceptionHandler,
        uow=None,
    ):
        self.account_repo = account_repo
        self.status_repo = status_repo
        self.instagram = instagram
        self.logger = logger
        self.error_handler = error_handler
        self.uow = uow
        self._account_locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def _select_relogin_mode(account: dict) -> ReloginMode:
        """Choose relogin strategy from persisted account error metadata."""
        if should_use_fresh_credentials_relogin(
            last_error_code=account.get("last_error_code"),
            last_error_family=account.get("last_error_family"),
        ):
            return ReloginMode.FRESH_CREDENTIALS
        return ReloginMode.SESSION_RESTORE

    def _relogin_context(self, account_id: str) -> tuple[dict, str, str, ReloginMode]:
        """Load account metadata required by relogin and validate credentials."""
        account = self.account_repo.get(account_id) or {}
        username = account.get("username", account_id)
        password = account.get("password", "")
        if not password:
            raise ValueError(
                f"No stored password for @{username}. Login manually via the Accounts page."
            )
        mode = self._select_relogin_mode(account)
        return account, username, password, mode

    def _get_account_lock(self, account_id: str) -> asyncio.Lock:
        """Get or create a per-account async lock to prevent concurrent mutations."""
        if account_id not in self._account_locks:
            self._account_locks[account_id] = asyncio.Lock()
        return self._account_locks[account_id]

    @staticmethod
    def _geo_kwargs(account: dict) -> dict[str, str | int]:
        kwargs: dict[str, str | int] = {}
        country = account.get("country")
        if country is not None:
            kwargs["country"] = country
        country_code = account.get("country_code")
        if country_code is not None:
            kwargs["country_code"] = country_code
        locale = account.get("locale")
        if locale is not None:
            kwargs["locale"] = locale
        timezone_offset = account.get("timezone_offset")
        if timezone_offset is not None:
            kwargs["timezone_offset"] = timezone_offset
        return kwargs

    def _uow_scope(self):
        """Return transaction context when UoW is configured."""
        if self.uow is None:
            return nullcontext()
        return self.uow

    def _mark_verified(self, account_id: str) -> None:
        """Mark account as verified (successful Instagram interaction)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        self.account_repo.update(
            account_id,
            last_verified_at=now,
            last_error=None,
            last_error_code=None,
            last_error_family=None,
        )

    def _mark_error(
        self,
        account_id: str,
        error: str,
        code: str | None = None,
        family: str | None = None,
    ) -> None:
        """Mark account with error from failed Instagram interaction."""
        self.account_repo.update(
            account_id,
            last_error=error,
            last_error_code=code,
            last_error_family=family,
        )

    def _build_account_response(
        self,
        account_id: str,
        account: dict | None = None,
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
            status=status or "idle",
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

    def relogin_account(self, account_id: str) -> AccountResponse:
        """Relogin an account.
        
        Raises:
            Exception with _instagram_failure attribute on Instagram errors.
        """
        with self._uow_scope():
            account, username, password, mode = self._relogin_context(account_id)
            # Mark as logging_in immediately so frontend sees status change
            self.status_repo.set(account_id, "logging_in")

            try:
                result = self.instagram.relogin_account(
                    account_id,
                    username=username,
                    password=password,
                    proxy=account.get("proxy"),
                    totp_secret=account.get("totp_secret"),
                    **self._geo_kwargs(account),
                    mode=mode,
                )
                self.status_repo.set(account_id, "active")
                self._mark_verified(account_id)
                return self._build_account_response(
                    account_id,
                    status=result.get("status") or "active",
                )
            except Exception as exc:
                failure = self.error_handler.handle(
                    exc,
                    operation="relogin",
                    account_id=account_id,
                    username=username,
                )
                new_status = status_from_failure(failure, keep_transient=True)
                if new_status is not None:
                    self.status_repo.set(account_id, new_status)
                self._mark_error(
                    account_id,
                    failure.user_message,
                    failure.code,
                    failure.family,
                )
                self.logger.log_event(
                    account_id,
                    username,
                    "relogin_failed",
                    detail=failure.user_message,
                    status=new_status or account.get("status", "unknown"),
                )
                # Attach translated failure to the exception
                exc._instagram_failure = failure  # type: ignore[attr-defined]
                raise

    async def bulk_relogin_accounts(self, request: BulkReloginRequest) -> list[AccountResponse]:
        """Relogin multiple accounts concurrently with per-account dedup.
        
        Uses semaphore for concurrency control and per-account locks to prevent
        duplicate relogin attempts on the same account.
        """
        semaphore = asyncio.Semaphore(request.concurrency)

        async def _relogin_one(account_id: str) -> AccountResponse:
            from ...dto.account_dto import AccountResponse

            lock = self._get_account_lock(account_id)
            async with semaphore, lock:
                try:
                    account, username, password, mode = self._relogin_context(account_id)
                except ValueError as exc:
                    account = self.account_repo.get(account_id) or {}
                    return AccountResponse(
                        id=account_id,
                        username=account.get("username", account_id),
                        status="error",
                        last_error=str(exc),
                    )

                self.status_repo.set(account_id, "logging_in")
                try:
                    result = await asyncio.to_thread(
                        self.instagram.relogin_account,
                        account_id,
                        username=username,
                        password=password,
                        proxy=account.get("proxy"),
                        totp_secret=account.get("totp_secret"),
                        **self._geo_kwargs(account),
                        mode=mode,
                    )
                    self.status_repo.set(account_id, "active")
                    self._mark_verified(account_id)
                    return self._build_account_response(
                        account_id,
                        status=result.get("status") or "active",
                    )
                except Exception as exc:
                    failure = self.error_handler.handle(
                        exc,
                        operation="relogin",
                        account_id=account_id,
                        username=username,
                    )
                    new_status = status_from_failure(failure, keep_transient=True)
                    if new_status is not None:
                        self.status_repo.set(account_id, new_status)
                    self._mark_error(
                        account_id,
                        failure.user_message,
                        failure.code,
                        failure.family,
                    )
                    self.logger.log_event(
                        account_id,
                        username,
                        "relogin_failed",
                        detail=failure.user_message,
                        status=new_status or account.get("status", "unknown"),
                    )
                    return self._build_account_response(
                        account_id,
                        status=new_status or "error",
                    )

        # Deduplicate account_ids to prevent concurrent relogin on the same account
        unique_ids = list(dict.fromkeys(request.account_ids))
        return await asyncio.gather(
            *[_relogin_one(account_id) for account_id in unique_ids]
        )

    def relogin_account_by_username(self, username: str) -> dict:
        """Relogin account by username, returning summary for AI tools."""
        normalized = username.lstrip("@")
        account_id = self.account_repo.find_by_username(normalized)
        if not account_id:
            return {"error": f"Account @{normalized} not found"}

        try:
            self.relogin_account(account_id)
            account = self.account_repo.get(account_id) or {}
            return {
                "success": True,
                "username": normalized,
                "status": "active",
                "followers": account.get("followers"),
                "message": f"@{normalized} re-logged in successfully",
            }
        except Exception as exc:
            failure = self.error_handler.handle(
                exc,
                operation="relogin",
                account_id=account_id,
                username=normalized,
            )
            return {"success": False, "username": normalized, "error": failure.user_message}
