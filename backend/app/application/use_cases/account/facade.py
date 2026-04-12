"""Compatibility facade for AccountUseCases.

This facade preserves the original AccountUseCases class interface for backward
compatibility while delegating to the split sub-modules internally.

Error propagation pattern:
- All Instagram exceptions are translated via InstagramExceptionHandler to
  InstagramFailure domain objects before being re-raised.
- Callers can catch exceptions and extract the _instagram_failure attribute
  for structured error information.
- Some methods return error information in response objects (e.g., AccountInfoResponse.error).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from .auth import AuthUseCases
from .relogin import ReloginUseCases
from .profile import ProfileUseCases
from .totp import TOTPUseCases
from .imports import ImportsUseCases

from ...dto.account_dto import (
    LoginRequest,
    AccountResponse,
    BulkReloginRequest,
    AccountInfoResponse,
)
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
from ...ports.persistence_uow import PersistenceUnitOfWork
from ...ports.proxy_checker import ProxyCheckerPort, ProxyCheckResult

if TYPE_CHECKING:
    from ...ports.persistence_models import AccountRecord


class AccountUseCases:
    """Core account management workflows - compatibility facade.
    
    This class delegates to specialized sub-modules while preserving the
    original public API for existing callers.
    """

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
        relogin_usecases: ReloginUseCases | None = None,
    ):
        # Initialize sub-modules with only the dependencies they need
        self._auth = AuthUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            status_repo=status_repo,
            instagram=instagram,
            logger=logger,
            totp=totp,
            session_store=session_store,
            error_handler=error_handler,
            identity_reader=identity_reader,
            uow=uow,
        )

        self._relogin = relogin_usecases or ReloginUseCases(
            account_repo=account_repo,
            status_repo=status_repo,
            instagram=instagram,
            logger=logger,
            error_handler=error_handler,
            uow=uow,
        )

        self._profile = ProfileUseCases(
            account_repo=account_repo,
            client_repo=client_repo,
            status_repo=status_repo,
            logger=logger,
            error_handler=error_handler,
            identity_reader=identity_reader,
            uow=uow,
            proxy_checker=proxy_checker,
        )

        self._totp = TOTPUseCases(
            account_repo=account_repo,
            logger=logger,
            totp=totp,
        )

        self._imports = ImportsUseCases(
            account_repo=account_repo,
            status_repo=status_repo,
            totp=totp,
            session_store=session_store,
            logger=logger,
            error_handler=error_handler,
            login_usecase=self._auth,
        )

        # Store repos for legacy access patterns
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
        self._account_locks: dict[str, asyncio.Lock] = self._relogin._account_locks

    # Auth delegation
    def login_account(self, request: LoginRequest) -> AccountResponse:
        """Login an account."""
        return self._auth.login_account(request)

    def complete_2fa_login(self, account_id: str, code: str, is_totp: bool = False) -> AccountResponse:
        """Complete 2FA login."""
        return self._auth.complete_2fa_login(account_id, code, is_totp)

    def logout_account(self, account_id: str, detail: str = "") -> AccountResponse:
        """Logout an account."""
        return self._auth.logout_account(account_id, detail)

    def bulk_logout_accounts(self, account_ids: list[str]) -> list[AccountResponse]:
        """Logout multiple accounts."""
        return self._auth.bulk_logout_accounts(account_ids)

    # Relogin delegation
    def relogin_account(self, account_id: str) -> AccountResponse:
        """Relogin an account."""
        return self._relogin.relogin_account(account_id)

    async def bulk_relogin_accounts(self, request: BulkReloginRequest) -> list[AccountResponse]:
        """Relogin multiple accounts concurrently with per-account dedup."""
        return await self._relogin.bulk_relogin_accounts(request)

    def relogin_account_by_username(self, username: str) -> dict:
        """Relogin account by username, returning summary for AI tools."""
        return self._relogin.relogin_account_by_username(username)

    # Profile delegation
    def find_by_username(self, username: str) -> Optional[str]:
        """Find account ID by username."""
        return self._profile.find_by_username(username)

    def list_accounts(self) -> list[AccountResponse]:
        """List all accounts."""
        return self._profile.list_accounts()

    def get_accounts_summary(self) -> dict:
        """Get summary of all accounts for AI tools."""
        return self._profile.get_accounts_summary()

    def get_account_info(self, account_id: str) -> AccountInfoResponse:
        """Get detailed account info from Instagram."""
        return self._profile.get_account_info(account_id)

    def set_account_proxy(self, account_id: str, proxy: str) -> AccountResponse:
        """Set proxy for an account."""
        return self._profile.set_account_proxy(account_id, proxy)

    def bulk_set_proxy(self, account_ids: list[str], proxy: str) -> list[AccountResponse]:
        """Set proxy for multiple accounts."""
        return self._profile.bulk_set_proxy(account_ids, proxy)

    async def check_proxy(self, proxy_url: str) -> ProxyCheckResult:
        """Test if a proxy URL is reachable and measure its latency."""
        return await self._profile.check_proxy(proxy_url)

    # TOTP delegation
    def setup_totp(self, account_id: str) -> dict:
        """Generate a new TOTP secret for an account."""
        return self._totp.setup_totp(account_id)

    def verify_totp_setup(self, account_id: str, secret: str, code: str) -> dict:
        """Verify TOTP secret by checking if provided code is valid."""
        return self._totp.verify_totp_setup(account_id, secret, code)

    def disable_totp(self, account_id: str) -> dict:
        """Disable TOTP for an account."""
        return self._totp.disable_totp(account_id)

    # Imports delegation
    def import_accounts_text(self, text: str) -> list[AccountResponse]:
        """Import accounts from text format (username:password:proxy|totp_secret)."""
        return self._imports.import_accounts_text(text)

    def import_session_archive(self, sessions: dict) -> list[AccountResponse]:
        """Import accounts from session archive (dict of username -> session_data)."""
        return self._imports.import_session_archive(sessions, self.client_repo)

    # Legacy helper methods for backward compatibility
    def _get_account_lock(self, account_id: str) -> asyncio.Lock:
        """Get or create a per-account async lock to prevent concurrent mutations."""
        return self._relogin._get_account_lock(account_id)

    def _uow_scope(self):
        """Return transaction context when UoW is configured."""
        return self._auth._uow_scope()

    def _get_account_status(self, account_id: str) -> str:
        """Determine current account status."""
        return self._profile._get_account_status(account_id)

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
        return self._profile._build_account_response(
            account_id,
            account=account,
            status=status,
        )

    def _mark_verified(self, account_id: str) -> None:
        """Mark account as verified (successful Instagram interaction)."""
        self._auth._mark_verified(account_id)

    def _mark_error(self, account_id: str, error: str, code: str | None = None) -> None:
        """Mark account with error from failed Instagram interaction."""
        self._relogin._mark_error(account_id, error, code)

    def _activate_account_client(
        self,
        account_id: str,
        client,
        *,
        hydrate_profile: bool = True,
    ) -> None:
        """Store authenticated client and optionally fetch profile metadata."""
        self._auth._activate_account_client(
            account_id,
            client,
            hydrate_profile=hydrate_profile,
        )
