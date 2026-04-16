"""Account authentication use cases - login, logout, relogin, 2FA."""

from __future__ import annotations

import uuid
from contextlib import nullcontext

from .account.relogin import ReloginUseCases
from ..dto.account_dto import (
    LoginRequest,
    AccountResponse,
    BulkReloginRequest,
)
from ..ports import (
    AccountRepository,
    ClientRepository,
    StatusRepository,
    InstagramClient,
    ReloginMode,
    ActivityLogger,
    TOTPManager,
    SessionStore,
)
from ..ports.instagram_challenge import InstagramChallengeResolver
from ..ports.instagram_error_handling import InstagramExceptionHandler
from ..ports.instagram_identity import InstagramIdentityReader
from ..ports.persistence_models import AccountRecord
from ..ports.persistence_uow import PersistenceUnitOfWork
from ...domain.instagram_failures import InstagramFailure, InstagramAdapterError
from .account_status_policy import (
    is_challenge_failure,
    status_from_failure,
    should_use_fresh_credentials_relogin,
)


class AccountAuthUseCases:
    """Authentication workflows: login, logout, relogin, 2FA."""

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
        relogin_usecases: ReloginUseCases | None = None,
        verify_session_on_restore: bool = False,
        challenge_resolver: InstagramChallengeResolver | None = None,
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
        self.verify_session_on_restore = verify_session_on_restore
        self.challenge_resolver = challenge_resolver
        # Canonical relogin semantics shared with AccountUseCases facade.
        self._relogin = relogin_usecases or ReloginUseCases(
            account_repo=account_repo,
            status_repo=status_repo,
            instagram=instagram,
            logger=logger,
            error_handler=error_handler,
            uow=uow,
            verify_session_on_restore=verify_session_on_restore,
        )

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

    @staticmethod
    def _geo_kwargs(
        *,
        country: str | None = None,
        country_code: int | None = None,
        locale: str | None = None,
        timezone_offset: int | None = None,
    ) -> dict[str, str | int]:
        kwargs: dict[str, str | int] = {}
        if country is not None:
            kwargs["country"] = country
        if country_code is not None:
            kwargs["country_code"] = country_code
        if locale is not None:
            kwargs["locale"] = locale
        if timezone_offset is not None:
            kwargs["timezone_offset"] = timezone_offset
        return kwargs

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
            updates = {
                "full_name": profile.full_name,
                "profile_pic_url": profile.profile_pic_url,
            }
            if profile.follower_count is not None:
                updates["followers"] = profile.follower_count
            if profile.following_count is not None:
                updates["following"] = profile.following_count
            self.account_repo.update(account_id, **updates)
        except Exception:
            pass

    def _activate_and_respond(
        self,
        account_id: str,
        username: str,
        client,
        event: str = "login_success",
    ) -> AccountResponse:
        """Activate client, log success, and return an active AccountResponse.

        Consolidates the repeated activate → log → respond triple that appears
        across login, TOTP auto-login, and 2FA completion paths.
        """
        self._activate_account_client(account_id, client, hydrate_profile=False)
        self.logger.log_event(account_id, username, event, status="active")
        return AccountResponse(id=account_id, username=username, status="active")

    def hydrate_account_profile(self, account_id: str) -> dict | None:
        """Fetch and persist profile data for an active account.

        Designed to run as a background task after login/2FA/relogin so the
        HTTP response is not delayed.

        Returns the updated fields dict (including ``id``) so the caller can
        forward them to an event bus without accessing internal state.
        Returns ``None`` on any failure.

        Failure handling uses the same shared policy as connectivity probes so
        challenge-family failures consistently map to ``status="challenge"``.
        Transient failures (rate-limit, network) are swallowed without
        overwriting status.
        """
        try:
            # account_info() validates the session and returns name/pic.
            # follower/following counts are NOT fetched here — use
            # refresh_follower_counts() for that (separate user_info call).
            profile = self.identity_reader.get_authenticated_account(account_id)
            updates: dict = {"full_name": profile.full_name}
            if profile.profile_pic_url:
                updates["profile_pic_url"] = profile.profile_pic_url
            self.account_repo.update(account_id, **updates)
            return {"id": account_id, **updates}
        except InstagramAdapterError as exc:
            failure = exc.failure
            new_status = status_from_failure(failure, keep_transient=True)
            if new_status is not None:
                # Hard failure (auth/challenge/2FA) — evict the dead client so
                # this account drops out of the active runtime pool.
                self.status_repo.set(account_id, new_status)
                if self.client_repo.exists(account_id):
                    self.client_repo.remove(account_id)
                self.account_repo.update(
                    account_id,
                    last_error=failure.user_message,
                    last_error_code=failure.code,
                    last_error_family=failure.family,
                )
            return None
        except Exception:
            return None  # transient — leave status untouched

    def refresh_follower_counts(self, account_id: str) -> dict | None:
        """Fetch follower/following counts via user_info() and persist them.

        Separate from hydrate_account_profile — user_info() is a heavier call
        that returns public profile data. Called when the user selects an
        account in the frontend, or during bulk startup hydration.

        Returns the updated fields dict (including ``id``) for SSE publishing,
        or None on any failure.
        """
        try:
            data = self.identity_reader.get_profile_for_hydration(account_id)
            if not data:
                return None
            updates: dict = {}
            if data.get("follower_count") is not None:
                updates["followers"] = data["follower_count"]
            if data.get("following_count") is not None:
                updates["following"] = data["following_count"]
            if not updates:
                return None
            self.account_repo.update(account_id, **updates)
            return {"id": account_id, **updates}
        except Exception:
            return None

    @staticmethod
    def _relogin_failure_status(failure: InstagramFailure) -> str | None:
        """Determine the account status to set after a relogin failure.

        Returns None when the failure is transient and the account status should
        be left unchanged (credentials may still be valid).
        """
        return status_from_failure(failure, keep_transient=True)

    @staticmethod
    def _select_relogin_mode(account: dict) -> ReloginMode:
        """Choose the relogin strategy based on the account's persisted state.

        ``FRESH_CREDENTIALS`` is selected when:
        - ``last_error_code="login_required"`` — server-side force-logout
          (Instagram logout_reason:8).  Session file is permanently invalid.
        - the previous failure is challenge-family (including
          ``checkpoint_required``, ``consent_required``, ``geo_blocked``,
          ``captcha_challenge_required``, etc.).

        All other accounts use ``SESSION_RESTORE`` — the faster path that reuses
        the saved session token when the session is still valid.
        """
        if should_use_fresh_credentials_relogin(
            last_error_code=account.get("last_error_code"),
            last_error_family=account.get("last_error_family"),
        ):
            return ReloginMode.FRESH_CREDENTIALS
        return ReloginMode.SESSION_RESTORE

    def login_account(self, request: LoginRequest) -> AccountResponse:
        """Login an account."""
        totp_secret = request.totp_secret
        account_id: str

        # Phase 1: fast persistence only — UoW released before any network I/O.
        # Holding a DB transaction across a 5-30s Instagram network call would
        # block all other DB operations (reads, writes, other account actions).
        with self._uow_scope():
            existing_id = self.account_repo.find_by_username(request.username)
            if existing_id and self.client_repo.exists(existing_id):
                account = self.account_repo.get(existing_id)
                return AccountResponse(
                    id=existing_id,
                    username=account["username"],
                    status="active",
                )

            if totp_secret:
                totp_secret = self.totp.normalize_secret(totp_secret)

            # Create or reuse account — merge credentials into any existing record
            # so profile data (full_name, followers, etc.) is never wiped.
            account_id = existing_id or str(uuid.uuid4())
            existing = self.account_repo.get(account_id)
            if existing:
                self.account_repo.update(
                    account_id,
                    username=request.username,
                    password=request.password,
                    proxy=request.proxy,
                    country=request.country,
                    country_code=request.country_code,
                    locale=request.locale,
                    timezone_offset=request.timezone_offset,
                    totp_secret=totp_secret,
                )
            else:
                self.account_repo.set(
                    account_id,
                    AccountRecord(
                        username=request.username,
                        password=request.password,
                        proxy=request.proxy,
                        country=request.country,
                        country_code=request.country_code,
                        locale=request.locale,
                        timezone_offset=request.timezone_offset,
                        totp_secret=totp_secret,
                    ),
                )

        # Phase 2: Instagram network I/O — outside the UoW so the DB lock is not
        # held during the slow login call. Fresh accounts go straight to a full
        # credential login; existing session files attempt a restore first.
        if self.challenge_resolver is not None:
            self.challenge_resolver.register_account(account_id, request.username)
        try:
            client = self.instagram.create_authenticated_client(
                request.username,
                request.password,
                request.proxy,
                totp_secret,
                verify_session=self.verify_session_on_restore,
                **self._geo_kwargs(
                    country=request.country,
                    country_code=request.country_code,
                    locale=request.locale,
                    timezone_offset=request.timezone_offset,
                ),
            )
            return self._activate_and_respond(account_id, request.username, client)
        except Exception as exc:
            failure = self.error_handler.handle(
                exc,
                operation="login",
                account_id=account_id,
                username=request.username,
            )

            # 2FA required — only happens for SMS/email (no totp_secret)
            if failure.code == "two_factor_required":
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

            # Challenge (email/SMS code) — keep the account record so the
            # operator can submit the code via /api/accounts/{id}/challenge.
            if (
                is_challenge_failure(code=failure.code, family=failure.family)
                and self.challenge_resolver is not None
                and self.challenge_resolver.has_pending(account_id)
            ):
                self.status_repo.set(account_id, "challenge_pending")
                self.account_repo.update(
                    account_id,
                    last_error=failure.user_message,
                    last_error_code="challenge_pending",
                    last_error_family="challenge",
                )
                self.logger.log_event(
                    account_id,
                    request.username,
                    "login_challenge_pending",
                    detail=failure.user_message,
                    status="challenge_pending",
                )
                return AccountResponse(
                    id=account_id,
                    username=request.username,
                    status="challenge_pending",
                    last_error=failure.user_message,
                    last_error_code="challenge_pending",
                    last_error_family="challenge",
                )

            # Other error — clean up the account record and raise
            self.logger.log_event(
                account_id,
                request.username,
                "login_failed",
                detail=failure.user_message,
                status="error",
            )
            self.account_repo.remove(account_id)
            raise InstagramAdapterError(failure) from exc

    def complete_2fa_login(
        self, account_id: str, code: str, is_totp: bool = False
    ) -> AccountResponse:
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
            self.logger.log_event(
                account_id, username, "totp_verified", status="active"
            )
            # Continue with Instagram 2FA completion if needed
            code = ""

        try:
            client = self.instagram.complete_2fa(
                username,
                password,
                code,
                proxy,
                **self._geo_kwargs(
                    country=account.get("country"),
                    country_code=account.get("country_code"),
                    locale=account.get("locale"),
                    timezone_offset=account.get("timezone_offset"),
                ),
            )
            return self._activate_and_respond(account_id, username, client)
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
            raise InstagramAdapterError(failure) from exc

    def logout_account(self, account_id: str, detail: str = "") -> AccountResponse:
        """Logout an account.

        Invalidates the Instagram server-side mobile session by invoking
        the live client's logout() before local teardown. Local cleanup
        (session file, status, account record) always runs, even if the
        server-side call fails, so the operator never sees a stuck
        account.
        """
        with self._uow_scope():
            if not self.account_repo.exists(account_id):
                raise ValueError("Account not found")

            account = self.account_repo.get(account_id) or {}
            username = account.get("username", "")

            # Pop the live client first so the server-side logout call can
            # run against it. remove() returns the client if one was
            # attached, or None when no runtime client exists.
            client = self.client_repo.remove(account_id)
            server_logout = self._invalidate_server_session(
                client, account_id=account_id, username=username
            )

            self.session_store.delete_session(username)
            self.logger.log_event(
                account_id, username, "logout", detail=detail, status="removed"
            )
            self.status_repo.clear(account_id)
            self.account_repo.remove(account_id)

            return AccountResponse(
                id=account_id,
                username=username,
                status="removed",
                server_logout=server_logout,
            )

    def _invalidate_server_session(
        self, client, *, account_id: str, username: str
    ) -> str:
        """Call client.logout() to invalidate the server-side session.

        Returns one of "success", "failed", or "not_present". Exceptions
        raised by the vendor client are routed through error_handler to
        preserve translated failure semantics; the caller continues with
        local cleanup regardless.
        """
        if client is None:
            return "not_present"

        try:
            client.logout()
        except Exception as exc:
            failure = self.error_handler.handle(
                exc,
                operation="logout",
                account_id=account_id,
                username=username,
            )
            self.logger.log_event(
                account_id,
                username,
                "logout",
                detail=f"server_logout_failed: {failure.code}",
                status="removed",
            )
            return "failed"

        self.logger.log_event(
            account_id,
            username,
            "logout",
            detail="server_logout_ok",
            status="removed",
        )
        return "success"

    def relogin_account(self, account_id: str) -> AccountResponse:
        """Relogin an account via canonical split-path relogin semantics."""
        return self._relogin.relogin_account(account_id)

    def relogin_account_by_username(self, username: str) -> dict:
        """Relogin account by username, returning summary for AI tools."""
        return self._relogin.relogin_account_by_username(username)

    def find_by_username(self, username: str) -> str | None:
        """Find account ID by username."""
        return self.account_repo.find_by_username(username)

    async def bulk_relogin_accounts(
        self, request: BulkReloginRequest
    ) -> list[AccountResponse]:
        """Relogin multiple accounts with canonical relogin semantics."""
        return await self._relogin.bulk_relogin_accounts(request)

    def bulk_logout_accounts(self, account_ids: list[str]) -> list[AccountResponse]:
        """Logout multiple accounts."""
        results = []
        for account_id in account_ids:
            try:
                results.append(self.logout_account(account_id, detail="bulk"))
            except ValueError:
                results.append(
                    AccountResponse(
                        id=account_id,
                        username="",
                        status="not_found",
                    )
                )
        return results
