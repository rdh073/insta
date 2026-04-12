"""Authentication use cases - login, 2FA completion, logout.

Error propagation: All Instagram exceptions are translated via InstagramExceptionHandler
to InstagramFailure domain objects before being re-raised. Callers can catch exceptions
and extract the _instagram_failure attribute for structured error information.
"""

from __future__ import annotations

import uuid
from contextlib import nullcontext
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...dto.account_dto import LoginRequest, AccountResponse
    from ...ports import (
        AccountRepository,
        ClientRepository,
        StatusRepository,
        InstagramClient,
        ActivityLogger,
        TOTPManager,
        SessionStore,
    )
    from ...ports.instagram_error_handling import InstagramExceptionHandler
    from ...ports.instagram_identity import InstagramIdentityReader
    from ...ports.persistence_models import AccountRecord
    from ...ports.persistence_uow import PersistenceUnitOfWork


class AuthUseCases:
    """Login, 2FA, and logout workflows."""

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
        )

    def _activate_account_client(
        self,
        account_id: str,
        client,
        *,
        hydrate_profile: bool = True,
    ) -> None:
        """Store authenticated client and optionally fetch profile metadata."""
        self.client_repo.set(account_id, client)
        self.status_repo.set(account_id, "active")
        if not hydrate_profile:
            return
        try:
            profile = self.identity_reader.get_authenticated_account(account_id)
            self.account_repo.update(
                account_id,
                full_name=profile.full_name,
                profile_pic_url=profile.profile_pic_url,
            )
        except Exception:
            pass

    def _mark_verified(self, account_id: str) -> None:
        """Mark account as verified (successful Instagram interaction)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        self.account_repo.update(
            account_id,
            last_verified_at=now,
            last_error=None,
            last_error_code=None,
        )

    def login_account(self, request: LoginRequest) -> AccountResponse:
        """Login an account.
        
        Raises:
            Exception with _instagram_failure attribute on Instagram errors.
        """
        from ...ports.persistence_models import AccountRecord

        with self._uow_scope():
            # Check if already logged in
            existing_id = self.account_repo.find_by_username(request.username)
            if existing_id and self.client_repo.exists(existing_id):
                account = self.account_repo.get(existing_id)
                return AccountResponse(
                    id=existing_id,
                    username=account["username"],
                    status="active",
                )

            # Normalize TOTP secret
            totp_secret = request.totp_secret
            if totp_secret:
                totp_secret = self.totp.normalize_secret(totp_secret)

            # Create or reuse account
            account_id = existing_id or str(uuid.uuid4())
            self.account_repo.set(
                account_id,
                AccountRecord(
                    username=request.username,
                    password=request.password,
                    proxy=request.proxy,
                    totp_secret=totp_secret,
                ),
            )

            try:
                # Create authenticated client
                client = self.instagram.create_authenticated_client(
                    request.username,
                    request.password,
                    request.proxy,
                )
                self._activate_account_client(account_id, client, hydrate_profile=False)
                self._mark_verified(account_id)
                self.logger.log_event(account_id, request.username, "login_success", status="active")
                return self._build_account_response(account_id, status="active")
            except Exception as exc:
                failure = self.error_handler.handle(
                    exc,
                    operation="login",
                    account_id=account_id,
                    username=request.username,
                )

                # Check if it's 2FA required
                if failure.code == "two_factor_required":
                    if totp_secret:
                        # Try auto-complete with TOTP
                        try:
                            code = self.totp.generate_code(totp_secret)
                            client = self.instagram.complete_2fa(
                                request.username,
                                request.password,
                                code,
                                request.proxy,
                            )
                            self._activate_account_client(account_id, client, hydrate_profile=False)
                            self._mark_verified(account_id)
                            self.logger.log_event(
                                account_id,
                                request.username,
                                "login_success_totp",
                                status="active",
                            )
                            return self._build_account_response(account_id, status="active")
                        except Exception as totp_exc:
                            totp_failure = self.error_handler.handle(
                                totp_exc,
                                operation="complete_2fa",
                                account_id=account_id,
                                username=request.username,
                            )
                            self.logger.log_event(
                                account_id,
                                request.username,
                                "login_totp_auto_failed",
                                detail=totp_failure.user_message,
                                status="error",
                            )
                            self.account_repo.remove(account_id)
                            raise

                    # Manual 2FA required
                    self.logger.log_event(
                        account_id,
                        request.username,
                        "login_2fa_required",
                        status="2fa_required",
                    )
                    return AccountResponse(
                        id=account_id,
                        username=request.username,
                        status="2fa_required",
                    )

                # Other error - clean up and raise
                self.logger.log_event(
                    account_id,
                    request.username,
                    "login_failed",
                    detail=failure.user_message,
                    status="error",
                )
                self.account_repo.remove(account_id)
                raise

    def complete_2fa_login(self, account_id: str, code: str, is_totp: bool = False) -> AccountResponse:
        """Complete 2FA login.
        
        Raises:
            ValueError: Account not found or invalid TOTP.
            Exception with _instagram_failure attribute on Instagram errors.
        """
        from ...dto.account_dto import AccountResponse

        if not self.account_repo.exists(account_id):
            raise ValueError("Account not found")

        account = self.account_repo.get(account_id) or {}
        username = account.get("username", "")
        password = account.get("password", "")
        proxy = account.get("proxy")

        if is_totp:
            totp_secret = account.get("totp_secret")
            if not totp_secret:
                raise ValueError("TOTP not enabled for this account")
            if not self.totp.verify_code(totp_secret, code):
                self.logger.log_event(
                    account_id,
                    username,
                    "totp_verification_failed",
                    status="error",
                )
                raise ValueError("Invalid TOTP code")
            self.logger.log_event(account_id, username, "totp_verified", status="active")
            # Continue with Instagram 2FA completion if needed
            code = ""

        try:
            client = self.instagram.complete_2fa(username, password, code, proxy)
            self._activate_account_client(account_id, client, hydrate_profile=False)
            self.logger.log_event(account_id, username, "login_success", status="active")
            return AccountResponse(
                id=account_id,
                username=username,
                status="active",
            )
        except Exception as exc:
            failure = self.error_handler.handle(
                exc,
                operation="complete_2fa",
                account_id=account_id,
                username=username,
            )
            self.logger.log_event(
                account_id,
                username,
                "login_2fa_failed",
                detail=failure.user_message,
                status="error",
            )
            raise

    def logout_account(self, account_id: str, detail: str = "") -> AccountResponse:
        """Logout an account.
        
        Raises:
            ValueError: Account not found.
        """
        from ...dto.account_dto import AccountResponse

        with self._uow_scope():
            if not self.account_repo.exists(account_id):
                raise ValueError("Account not found")

            account = self.account_repo.get(account_id) or {}
            username = account.get("username", "")

            # Remove local runtime and persisted session state
            self.client_repo.remove(account_id)
            self.session_store.delete_session(username)

            self.logger.log_event(account_id, username, "logout", detail=detail, status="removed")
            self.status_repo.clear(account_id)
            self.account_repo.remove(account_id)

            return AccountResponse(
                id=account_id,
                username=username,
                status="removed",
            )

    def bulk_logout_accounts(self, account_ids: list[str]) -> list[AccountResponse]:
        """Logout multiple accounts."""
        from ...dto.account_dto import AccountResponse

        results = []
        for account_id in account_ids:
            try:
                results.append(self.logout_account(account_id, detail="bulk"))
            except ValueError:
                results.append(AccountResponse(
                    id=account_id,
                    username="",
                    status="not_found",
                ))
        return results
