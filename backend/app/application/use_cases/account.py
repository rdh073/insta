"""Account management use cases - login, logout, proxy management, etc."""

from __future__ import annotations

import asyncio
import uuid
from contextlib import nullcontext
from typing import Optional

from ..dto.account_dto import (
    LoginRequest,
    AccountResponse,
    BulkReloginRequest,
    AccountInfoResponse,
)
from ..ports import (
    AccountRepository,
    ClientRepository,
    StatusRepository,
    InstagramClient,
    ActivityLogger,
    TOTPManager,
    SessionStore,
)


# ============================================================================
# Use Case Implementation
# ============================================================================


from ..ports.instagram_error_handling import InstagramExceptionHandler

from ..ports.instagram_identity import InstagramIdentityReader
from ..ports.persistence_models import AccountRecord
from ..ports.persistence_uow import PersistenceUnitOfWork
from ..ports.proxy_checker import ProxyCheckerPort, ProxyCheckResult

class AccountUseCases:
    """Core account management workflows."""

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
        proxy_checker: ProxyCheckerPort | None = None,
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
        self.proxy_checker = proxy_checker
        self._account_locks: dict[str, asyncio.Lock] = {}

    def _get_account_lock(self, account_id: str) -> asyncio.Lock:
        """Get or create a per-account async lock to prevent concurrent mutations."""
        if account_id not in self._account_locks:
            self._account_locks[account_id] = asyncio.Lock()
        return self._account_locks[account_id]

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

    def _account_username(self, account_id: str, default: str = "") -> str:
        """Get account username."""
        account = self.account_repo.get(account_id)
        return (account or {}).get("username", default)

    def _build_account_response(
        self,
        account_id: str,
        account: dict | AccountRecord | None = None,
        status: str | None = None,
    ) -> AccountResponse:
        """Build AccountResponse with session health fields."""
        if account is None:
            account = self.account_repo.get(account_id) or {}

        # Support both dict and AccountRecord
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

    def _mark_error(self, account_id: str, error: str, code: str | None = None) -> None:
        """Mark account with error from failed Instagram interaction."""
        self.account_repo.update(
            account_id,
            last_error=error,
            last_error_code=code,
        )

    def find_by_username(self, username: str) -> Optional[str]:
        """Find account ID by username."""
        return self.account_repo.find_by_username(username)

    def login_account(self, request: LoginRequest) -> AccountResponse:
        """Login an account."""
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
                # Translate vendor exception to application failure
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
        """Complete 2FA login."""
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
        """Logout an account."""
        with self._uow_scope():
            if not self.account_repo.exists(account_id):
                raise ValueError("Account not found")

            account = self.account_repo.get(account_id) or {}
            username = account.get("username", "")

            # Remove local runtime and persisted session state without waiting on
            # a remote Instagram logout request.
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

    def relogin_account(self, account_id: str) -> AccountResponse:
        """Relogin an account."""
        with self._uow_scope():
            # Mark as logging_in immediately so frontend sees status change
            self.status_repo.set(account_id, "logging_in")

            try:
                result = self.instagram.relogin_account(account_id)
                self._mark_verified(account_id)
                return self._build_account_response(
                    account_id,
                    status=result.get("status", "active"),
                )
            except Exception as exc:
                account = self.account_repo.get(account_id) or {}
                username = account.get("username", account_id)
                failure = self.error_handler.handle(
                    exc,
                    operation="relogin",
                    account_id=account_id,
                    username=username,
                )
                self.status_repo.set(account_id, "error")
                self._mark_error(account_id, failure.user_message, failure.code)
                self.logger.log_event(
                    account_id,
                    username,
                    "relogin_failed",
                    detail=failure.user_message,
                    status="error",
                )
                # Attach translated failure to the exception so the router can extract it
                exc._instagram_failure = failure  # type: ignore[attr-defined]
                raise

    async def bulk_relogin_accounts(self, request: BulkReloginRequest) -> list[AccountResponse]:
        """Relogin multiple accounts concurrently with per-account dedup."""
        semaphore = asyncio.Semaphore(request.concurrency)

        async def _relogin_one(account_id: str) -> AccountResponse:
            lock = self._get_account_lock(account_id)
            async with semaphore, lock:
                try:
                    result = await asyncio.to_thread(self.instagram.relogin_account, account_id)
                    self._mark_verified(account_id)
                    return self._build_account_response(
                        account_id,
                        status=result.get("status", "active"),
                    )
                except Exception as exc:
                    account = self.account_repo.get(account_id) or {}
                    username = account.get("username", account_id)
                    failure = self.error_handler.handle(
                        exc,
                        operation="relogin",
                        account_id=account_id,
                        username=username,
                    )
                    self.status_repo.set(account_id, "error")
                    self._mark_error(account_id, failure.user_message, failure.code)
                    self.logger.log_event(
                        account_id,
                        username,
                        "relogin_failed",
                        detail=failure.user_message,
                        status="error",
                    )
                    return self._build_account_response(
                        account_id,
                        status="error",
                    )

        # Deduplicate account_ids to prevent concurrent relogin on the same account
        unique_ids = list(dict.fromkeys(request.account_ids))
        return await asyncio.gather(
            *[_relogin_one(account_id) for account_id in unique_ids]
        )

    def bulk_logout_accounts(self, account_ids: list[str]) -> list[AccountResponse]:
        """Logout multiple accounts."""
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

    def list_accounts(self) -> list[AccountResponse]:
        """List all accounts."""
        results = []
        for account_id in self.account_repo.list_all_ids():
            account = self.account_repo.get(account_id) or {}
            results.append(self._build_account_response(account_id, account))
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
            # Get authenticated account profile via identity reader
            profile = self.identity_reader.get_authenticated_account(account_id)
            
            # Update cached account metadata with latest data
            self.account_repo.update(
                account_id,
                full_name=profile.full_name,
                followers=None,  # Account profile doesn't have follower_count
                following=None,  # Account profile doesn't have following_count
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
                    # True only when the Instagram client session is actually loaded in memory.
                    # An account can have status="active" in the DB but no live client (e.g.
                    # after a restart with a failed session reload).  Smart engagement uses
                    # this field to gate on real session availability, not just DB status.
                    "client_exists": self.client_repo.exists(account_dto.id),
                },
            })
        return {
            "accounts": accounts,
            "total": len(accounts),
            "active": sum(1 for acc in accounts if acc["status"] == "active"),
        }

    def setup_totp(self, account_id: str) -> dict:
        """Generate a new TOTP secret for an account."""
        if not self.account_repo.exists(account_id):
            raise ValueError("Account not found")

        secret = self.totp.generate_secret()
        account = self.account_repo.get(account_id) or {}
        username = account.get("username", account_id)
        provisioning_uri = self.totp.get_provisioning_uri(secret, username)

        return {
            "account_id": account_id,
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "manual_entry_key": secret,
        }

    def verify_totp_setup(self, account_id: str, secret: str, code: str) -> dict:
        """Verify TOTP secret by checking if provided code is valid."""
        if not self.account_repo.exists(account_id):
            raise ValueError("Account not found")

        # Verify the code matches the secret
        if not self.totp.verify_code(secret, code):
            raise ValueError("Invalid TOTP code. Please check your secret and time synchronization.")

        # If verification successful, store the secret
        self.account_repo.update(account_id, totp_secret=secret, totp_enabled=True)

        account = self.account_repo.get(account_id) or {}
        username = account.get("username", "")
        self.logger.log_event(account_id, username, "totp_enabled", status="active")

        return {"status": "ok", "message": "TOTP enabled successfully"}

    def disable_totp(self, account_id: str) -> dict:
        """Disable TOTP for an account."""
        if not self.account_repo.exists(account_id):
            raise ValueError("Account not found")

        self.account_repo.update(account_id, totp_secret=None, totp_enabled=False)

        account = self.account_repo.get(account_id) or {}
        username = account.get("username", "")
        self.logger.log_event(account_id, username, "totp_disabled", status="active")

        return {"status": "ok", "message": "TOTP disabled"}

    def relogin_account_by_username(self, username: str) -> dict:
        """Relogin account by username, returning summary for AI tools."""
        normalized = username.lstrip("@")
        account_id = self.find_by_username(normalized)
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

    def import_accounts_text(self, text: str) -> list[AccountResponse]:
        """Import accounts from text format (username:password:proxy|totp_secret)."""
        results = []
        for line in text.strip().splitlines():
            # Extract TOTP secret (if present) using | delimiter
            totp_secret = None
            if "|" in line:
                line, totp_secret = line.rsplit("|", 1)
                totp_secret = totp_secret.strip()
                # Normalize TOTP secret
                if totp_secret:
                    totp_secret = self.totp.normalize_secret(totp_secret)

            parts = line.strip().split(":")
            if len(parts) < 2:
                continue

            username, password = parts[0], parts[1]
            proxy = parts[2] if len(parts) > 2 else None

            try:
                request = LoginRequest(
                    username=username,
                    password=password,
                    proxy=proxy,
                    totp_secret=totp_secret,
                )
                result = self.login_account(request)
                results.append(result)
            except Exception as exc:
                failure = self.error_handler.handle(
                    exc,
                    operation="login",
                    username=username,
                )
                failed_id = str(uuid.uuid4())
                self.logger.log_event(
                    failed_id,
                    username,
                    "login_failed",
                    detail=failure.user_message,
                    status="error",
                )
                results.append(AccountResponse(
                    id=failed_id,
                    username=username,
                    status="error",
                ))

        return results

    def import_session_archive(self, sessions: dict) -> list[AccountResponse]:
        """Import accounts from session archive (dict of username -> session_data)."""
        results = []
        for username, session_data in sessions.items():
            # Save session using the session store adapter
            self.session_store.save_session(username, session_data)

            account_id = str(uuid.uuid4())
            self.account_repo.set(
                account_id,
                AccountRecord(
                    username=username,
                    password="",
                    proxy=None,
                ),
            )

            results.append(AccountResponse(
                id=account_id,
                username=username,
                status=self._get_account_status(account_id),
            ))

        return results
