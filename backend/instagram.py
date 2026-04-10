"""
Instagram operations: relogin, run post job, schedule post job.
Depends on state only.

ARCHITECTURE NOTE:
- Smart engagement logic is NOT in this file
- It lives in: ai_copilot/application/ (graphs, use_cases, nodes)
- This file handles Instagram client lifecycle and posting
- Adapters may use Instagram client from this module via bridges
- Smart engagement decisions (scoring, approval, execution) happen in ai_copilot layer
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, wait as wait_futures
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Per-media-type upload timeouts (seconds).
# Photos are fast; videos require transcoding + chunked upload so get more time.
# These are hard per-account deadlines — each account gets its own independent timer.
_UPLOAD_TIMEOUT_BY_TYPE: dict[str, int] = {
    "photo": 90,
    "album": 240,
    "reels": 360,
    "video": 360,
    "igtv": 360,
}
_UPLOAD_TIMEOUT_DEFAULT = 240  # fallback for unknown media types

from state import (
    IGClient,
    BadPassword,
    ChallengeRequired,
    LoginRequired,
    TwoFactorRequired,
    SESSIONS_DIR,
    ThreadSafeJobStore,
    account_to_dict,
    get_account,
    get_client,
    get_job,
    has_account,
    job_store,
    log_event,
    pop_client,
    pop_pending_2fa_client,
    set_account_status,
    set_client,
    store_pending_2fa_client,
    update_account,
)
from app.adapters.instagram.exception_handler import instagram_exception_handler
from app.adapters.instagram.device_pool import random_device_profile


class SyncCircuitBreaker:
    """Thread-safe circuit breaker for synchronous (threaded) Instagram uploads.

    Only *retryable* failures (rate limits, transient API errors, timeouts) advance
    the failure counter. Terminal per-account errors (BadPassword, ChallengeRequired)
    do NOT trip the circuit — they are account-level problems, not API degradation.

    States:
        CLOSED    — normal, all requests allowed
        OPEN      — fast-fail, requests rejected until recovery_timeout elapses
        HALF_OPEN — one probe call allowed; success → CLOSED, failure → OPEN

    Thread-safety: all state mutations hold ``_lock``; the ``state`` property
    performs a single atomic read and may promote OPEN→HALF_OPEN without a lock
    (benign race — at most one extra probe call slips through).
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 120.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == self.OPEN:
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    return self.HALF_OPEN
            return self._state

    def allow_request(self) -> bool:
        """True when the circuit is CLOSED or entering HALF_OPEN probe."""
        return self.state != self.OPEN

    def record_success(self) -> None:
        with self._lock:
            was_recovering = self._state == self.OPEN
            self._failure_count = 0
            self._state = self.CLOSED
        if was_recovering:
            logger.info("Circuit %r recovered — CLOSED", self.name)

    def record_failure(self, *, retryable: bool) -> None:
        """Record a failure; only retryable failures progress toward tripping."""
        if not retryable:
            return
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.failure_threshold and self._state != self.OPEN:
                self._state = self.OPEN
                logger.error(
                    "Circuit %r tripped OPEN after %d retryable failures "
                    "(auto-recovery in %.0fs)",
                    self.name, self._failure_count, self.recovery_timeout,
                )

    def __repr__(self) -> str:
        return (
            f"SyncCircuitBreaker({self.name!r}, "
            f"state={self.state}, failures={self._failure_count})"
        )


# Module-level breaker shared across all jobs in this process.
# Opens after 5 consecutive retryable failures to stop hammering Instagram
# when its API is degraded. Recovers automatically after 120 s.
_upload_circuit_breaker = SyncCircuitBreaker(
    "instagram_upload",
    failure_threshold=5,
    recovery_timeout=120.0,
)


def _new_client(proxy: Optional[str] = None):
    client = IGClient()
    client.request_timeout = 60  # 60s per HTTP request — prevents challenge hang
    # Random inter-request delay mimics human behaviour and reduces the
    # likelihood of triggering Instagram rate-limits or bot detection.
    # Instagrapi best-practice: https://subzeroid.github.io/instagrapi/usage-guide/best-practices
    client.delay_range = [1, 3]
    if proxy:
        client.set_proxy(proxy)
    device, user_agent = random_device_profile()
    client.set_device(device)
    client.set_user_agent(user_agent)
    # Skip post-login feed calls (get_reels_tray_feed + get_timeline_feed).
    # instagrapi's default login_flow() emulates app behaviour but is not
    # required for session validity — skipping it makes fresh-account login
    # faster and avoids unnecessary API exposure on new accounts.
    client.login_flow = lambda: True
    return client


def _classify_exception(
    error: Exception,
    *,
    operation: str,
    account_id: str | None = None,
    username: str | None = None,
):
    """Translate an exception to a stable Instagram failure."""
    return instagram_exception_handler.handle(
        error,
        operation=operation,
        account_id=account_id,
        username=username,
    )


def create_authenticated_client(
    username: str, password: str, proxy: Optional[str] = None,
    totp_secret: Optional[str] = None,
    verify_session: bool = False,
):
    """Authenticate and return a ready client.

    Follows the official instagrapi best-practice pattern:

    SESSION PATH (session file exists):
      1. load_settings  — restore cookies + device UUIDs (no network)
      2. login()        — uses session, NOT credentials (no network, no TOTP)
      3. optional verification via account_info() when verify_session=True
         - OK             → dump_settings, return
         - LoginRequired  → session expired:
             a. preserve device UUIDs from old settings
             b. reset settings (clear stale cookies)
             c. login(verification_code=totp) — full re-auth, TOTP passed upfront
             d. dump_settings, return
         - TwoFactorRequired → SMS/email 2FA, store pending client, raise
         - BadPassword    → raise (fresh login won't help)
         - other          → fall through to fresh login

    FRESH LOGIN PATH (no session file, or session path failed non-terminally):
      1. new client
      2. login(verification_code=totp) — TOTP passed upfront in first call
         - TwoFactorRequired (no TOTP secret) → store pending, raise
      3. dump_settings, return
    """
    session_file = SESSIONS_DIR / f"{username}.json"

    def _totp_code() -> str:
        """Generate a fresh TOTP code, or empty string if no secret."""
        if not totp_secret:
            return ""
        import pyotp
        return pyotp.TOTP(totp_secret).now()

    if session_file.exists():
        client = _new_client(proxy)
        client.load_settings(session_file)
        try:
            # Session restore — login() uses cookies, not credentials.
            client.login(username, password)
            if verify_session:
                # account_info() is lighter than get_timeline_feed() for
                # session validation: small response, no feed payload, and
                # returns useful profile data (follower/following counts).
                client.account_info()

        except LoginRequired:
            # Session expired — preserve device UUIDs, reset cookies, re-auth.
            try:
                old_settings = client.get_settings()
                client.set_settings({})
                client.set_uuids(old_settings["uuids"])
                client.login(username, password, verification_code=_totp_code())
            except TwoFactorRequired:
                store_pending_2fa_client(username, client)
                raise
            except BadPassword:
                raise
            except ChallengeRequired:
                # Challenge cannot be resolved by retrying — propagate immediately
                # so the caller can mark the account as "challenge" and stop.
                # Falling through to fresh login would only trigger the same
                # challenge again and waste an API call.
                raise
            except Exception:
                pass  # other transient failures → fall through to fresh login
            else:
                client.dump_settings(session_file)
                return client

        except TwoFactorRequired:
            # Only raised when totp_secret is absent (SMS/email 2FA).
            store_pending_2fa_client(username, client)
            raise

        except BadPassword:
            raise  # wrong credential — a fresh client won't help

        except ChallengeRequired:
            # Challenge required on initial session restore — propagate directly.
            raise

        except Exception:
            # Non-terminal failure (corruption, timeout, etc.).
            # Fall through to a completely fresh login below.
            pass

        else:
            client.dump_settings(session_file)
            return client

    # Fresh login — new client, no stale session state.
    client = _new_client(proxy)
    try:
        # TOTP passed upfront in the initial login() call — the correct
        # instagrapi pattern for TOTP (avoids the two-step TwoFactorRequired flow).
        client.login(username, password, verification_code=_totp_code())
    except TwoFactorRequired:
        # Only reached when totp_secret is absent (SMS/email 2FA).
        store_pending_2fa_client(username, client)
        raise
    client.dump_settings(session_file)
    return client


def activate_account_client(account_id: str, client) -> dict:
    # Activate immediately — session already persisted by create_authenticated_client.
    # Profile enrichment (followers/following) is handled by the background task
    # scheduled in the HTTP route layer, so we don't fetch it here.
    set_client(account_id, client)
    set_account_status(account_id, "active")
    return account_to_dict(account_id, status="active")


def complete_2fa_client(
    username: str, password: str, verification_code: str, proxy: Optional[str] = None
):
    """Complete 2FA login for an account with a verification code."""
    session_file = SESSIONS_DIR / f"{username}.json"
    client = pop_pending_2fa_client(username)
    if client is None:
        # Fallback: create fresh client (handles TOTP case where identifier can refresh)
        client = _new_client(proxy)
    client.login(username, password, verification_code=verification_code)
    client.dump_settings(session_file)
    return client


_MAX_RELOGIN_ATTEMPTS = 3


# ── Relogin strategies ────────────────────────────────────────────────────────
#
# Two concrete strategies share the same signature so _relogin_with_strategy
# can call either uniformly.
#
# SessionRestoreStrategy  — default; calls create_authenticated_client() which
#   tries to reload the existing session file first and only falls back to fresh
#   credential login on LoginRequired.  Fastest when the session is still valid.
#
# FreshCredentialStrategy — skips the session file entirely; always creates a
#   new client and authenticates with the stored username + password + TOTP.
#   Required for Instagram server-side force-logouts (logout_reason:8) where
#   the existing session file is permanently invalidated and cannot be restored.


def _relogin_session_restore(
    username: str,
    password: str,
    proxy: str | None,
    totp_secret: str | None,
):
    """Relogin via session restore (try saved session, fall back to fresh login).

    Delegates to create_authenticated_client which implements the full
    session-file → LoginRequired → fresh-credential cascade.
    """
    return create_authenticated_client(username, password, proxy, totp_secret)


def _relogin_fresh_credentials(
    username: str,
    password: str,
    proxy: str | None,
    totp_secret: str | None,
):
    """Relogin with fresh credentials, bypassing the existing session file.

    Creates a new client and authenticates directly.  The resulting session is
    persisted over any stale file so subsequent restores use the fresh token.
    """
    session_file = SESSIONS_DIR / f"{username}.json"

    def _totp_code() -> str:
        if not totp_secret:
            return ""
        import pyotp
        return pyotp.TOTP(totp_secret).now()

    client = _new_client(proxy)
    try:
        client.login(username, password, verification_code=_totp_code())
    except TwoFactorRequired:
        store_pending_2fa_client(username, client)
        raise
    client.dump_settings(session_file)
    return client


# Maps the string mode value from the port layer to the concrete strategy fn.
_RELOGIN_STRATEGIES: dict[str, Callable] = {
    "session_restore": _relogin_session_restore,
    "fresh_credentials": _relogin_fresh_credentials,
}


def relogin_account_sync(
    account_id: str,
    *,
    username: str,
    password: str,
    proxy: str | None = None,
    totp_secret: str | None = None,
    mode: str = "session_restore",
) -> dict:
    """Synchronous relogin with retry for transient failures.

    Selects between ``session_restore`` and ``fresh_credentials`` strategy via
    *mode*.  Credentials are passed in by the caller (fetched from the
    persistent store) so this function does not depend on the legacy state.py
    _accounts dict.

    ``fresh_credentials`` is required when the account is in an error state due
    to a server-side force-logout (Instagram logout_reason:8) — the session file
    is permanently invalid and cannot be restored.
    """
    strategy = _RELOGIN_STRATEGIES.get(mode, _relogin_session_restore)

    # Drop stale client reference without invalidating the server-side session.
    # Calling logout() here would invalidate the session file that
    # _relogin_session_restore is about to reuse, forcing a full re-auth.
    pop_client(account_id)

    cl = None
    for attempt in range(_MAX_RELOGIN_ATTEMPTS):
        if attempt > 0:
            time.sleep(2 ** (attempt - 1))  # 1s, then 2s
        try:
            cl = strategy(username, password, proxy, totp_secret)
            break  # success — exit retry loop
        except Exception as exc:
            failure = _classify_exception(
                exc, operation="relogin", account_id=account_id, username=username
            )
            if failure.retryable and attempt < _MAX_RELOGIN_ATTEMPTS - 1:
                continue  # transient — retry
            raise

    result = activate_account_client(account_id, cl)
    log_event(account_id, username, "relogin_success", status="active")
    return result


def _build_usertags(specs: list[dict]):
    """Build instagrapi Usertag objects from [{user_id, username, x, y}] dicts."""
    from instagrapi.types import UserShort, Usertag

    tags = []
    for spec in specs:
        try:
            user = UserShort(
                pk=str(spec["user_id"]),
                username=spec.get("username", ""),
            )
            tags.append(
                Usertag(
                    user=user,
                    x=float(spec.get("x", 0.5)),
                    y=float(spec.get("y", 0.5)),
                )
            )
        except Exception:
            continue
    return tags


def _build_location(loc: dict | None):
    """Build an instagrapi Location from {name, lat, lng} dict, or None."""
    if not loc:
        return None
    from instagrapi.types import Location

    try:
        return Location(
            name=loc["name"],
            lat=loc.get("lat"),
            lng=loc.get("lng"),
        )
    except Exception:
        return None


# ── Media upload strategies ────────────────────────────────────────────────
#
# Each strategy is a plain function with a common signature:
#   (cl, media_paths, caption, thumbnail_path, igtv_title, usertags, location, extra_data) -> None
#
# The dispatcher replaces the if/elif chain in _upload_one and can be extended
# by adding a new function + registering it in _UPLOAD_STRATEGIES.


def _upload_reels(
    cl, media_paths, caption, thumbnail_path, igtv_title, usertags, location, extra_data
):
    cl.clip_upload(
        Path(media_paths[0]),
        caption=caption,
        thumbnail=Path(thumbnail_path) if thumbnail_path else None,
        usertags=usertags,
        location=location,
        extra_data=extra_data,
    )


def _upload_igtv(
    cl, media_paths, caption, thumbnail_path, igtv_title, usertags, location, extra_data
):
    cl.igtv_upload(
        Path(media_paths[0]),
        title=igtv_title or "",
        caption=caption,
        thumbnail=Path(thumbnail_path) if thumbnail_path else None,
        usertags=usertags,
        location=location,
        extra_data=extra_data,
    )


def _upload_photo(
    cl,
    media_paths,
    caption,
    thumbnail_path,  # unused: photos do not support custom thumbnails
    igtv_title,  # unused: N/A for photos
    usertags,
    location,
    extra_data,
):
    cl.photo_upload(
        Path(media_paths[0]),
        caption=caption,
        usertags=usertags,
        location=location,
        extra_data=extra_data,
    )


def _upload_album(
    cl,
    media_paths,
    caption,
    thumbnail_path,  # unused: albums do not support custom thumbnails
    igtv_title,  # unused: N/A for albums
    usertags,
    location,
    extra_data,
):
    cl.album_upload(
        [Path(p) for p in media_paths],
        caption=caption,
        usertags=usertags,
        location=location,
        extra_data=extra_data,
    )


# Type alias for all upload strategy functions.
# Each strategy receives the same 8 arguments so _dispatch_upload can call any of them uniformly.
_UploadFn = Callable[..., None]

# Maps media_type string → upload function.
# Add a new entry here to support future media types without touching _upload_one.
_UPLOAD_STRATEGIES: dict[str, _UploadFn] = {
    "reels": _upload_reels,
    "video": _upload_reels,  # alias — same behaviour as reels
    "igtv": _upload_igtv,
    "photo": _upload_photo,
    "album": _upload_album,
}

_DEFAULT_UPLOAD_STRATEGY: _UploadFn = _upload_album  # fallback for unknown types


def _dispatch_upload(
    cl,
    media_type: str,
    media_paths: list[str],
    caption: str,
    thumbnail_path: str | None,
    igtv_title: str | None,
    usertags,
    location,
    extra_data: dict,
) -> None:
    """Select and invoke the correct upload strategy for *media_type*."""
    strategy: _UploadFn = _UPLOAD_STRATEGIES.get(media_type, _DEFAULT_UPLOAD_STRATEGY)
    strategy(
        cl,
        media_paths,
        caption,
        thumbnail_path,
        igtv_title,
        usertags,
        location,
        extra_data,
    )


class PostJobExecutor:
    """Concurrent upload engine — posts the same media to N accounts in parallel.

    All job-state mutations go through ``ThreadSafeJobStore`` so that
    polling readers (GET /api/posts) and upload worker threads never race
    on raw dict access.
    """

    def __init__(
        self,
        store: ThreadSafeJobStore | None = None,
        upload_timeout: int | None = None,
    ) -> None:
        self._store = store or job_store
        # None = use per-media-type defaults from _UPLOAD_TIMEOUT_BY_TYPE.
        # Pass an int to override all types (useful in tests).
        self._upload_timeout = upload_timeout

    def _get_upload_timeout(self, media_type: str) -> int:
        if self._upload_timeout is not None:
            return self._upload_timeout
        return _UPLOAD_TIMEOUT_BY_TYPE.get(media_type, _UPLOAD_TIMEOUT_DEFAULT)

    # ── public entry point ────────────────────────────────────────────────

    @staticmethod
    def _notify_sse() -> None:
        """Fire an SSE push from a worker thread (best-effort, never raises)."""
        try:
            from app.adapters.scheduler.event_bus import post_job_event_bus
            post_job_event_bus.notify("job_update")
        except Exception:
            pass

    def run(self, job_id: str) -> None:
        """Execute all account uploads for *job_id* concurrently."""
        job = self._store.get(job_id)
        self._store.set_job_status(job_id, "running")
        self._notify_sse()

        try:
            media_paths: list[str] = job["_media_paths"]
            caption: str = job["caption"]
            media_type: str = job.get("mediaType", "photo")
            thumbnail_path: str | None = job.get("_thumbnail_path")
            igtv_title: str | None = job.get("_igtv_title")
            usertags_raw: list[dict] = job.get("_usertags") or []
            location_raw: dict | None = job.get("_location")
            extra_data: dict = job.get("_extra_data") or {}

            accounts = job["results"]
            if not accounts:
                self._store.set_job_status(job_id, "completed")
                self._store.clear_control(job_id)
                return

            # One thread per account — all uploads start simultaneously.
            # Each _upload_one enforces its own per-account, per-media-type
            # timeout internally (see _upload_one), so no batch deadline is needed.
            executor = ThreadPoolExecutor(max_workers=len(accounts))
            futures = {
                executor.submit(
                    self._upload_one,
                    job_id=job_id,
                    account_id=result["accountId"],
                    username=result["username"],
                    media_paths=media_paths,
                    caption=caption,
                    media_type=media_type,
                    thumbnail_path=thumbnail_path,
                    igtv_title=igtv_title,
                    usertags_raw=usertags_raw,
                    location_raw=location_raw,
                    extra_data=extra_data,
                ): result
                for result in accounts
            }

            # Outer safety-net timeout: per-account timeout + generous slack.
            # This should never fire in practice — _upload_one returns within its
            # own deadline. It guards against unforeseen hangs (e.g. OS-level I/O stall).
            outer_timeout = self._get_upload_timeout(media_type) + 60
            done, not_done = wait_futures(futures.keys(), timeout=outer_timeout)
            executor.shutdown(wait=False)

            # Safety net: mark any futures that didn't complete within the outer deadline.
            for future in not_done:
                result = futures[future]
                account_id = result["accountId"]
                current = self._store.get_result_status(job_id, account_id)
                if current not in ("success", "failed", "skipped"):
                    self._store.update_result(
                        job_id, account_id,
                        status="failed",
                        error="Upload worker stalled — killed by outer deadline",
                        error_code="worker_stall",
                    )
                    self._notify_sse()

            # Determine final job status from per-account tally.
            tally = self._store.tally_results(job_id)
            self._store.clear_control(job_id)

            if tally["skipped"] > 0 and tally["success"] == 0 and tally["failed"] == 0:
                final = "stopped"
            elif tally["skipped"] > 0:
                final = "partial"
            elif tally["failed"] == 0:
                final = "completed"
            elif tally["success"] == 0:
                final = "failed"
            else:
                final = "partial"
            self._store.set_job_status(job_id, final)
            self._notify_sse()

        except Exception:
            try:
                self._store.clear_control(job_id)
                self._store.set_job_status(job_id, "failed")
                self._notify_sse()
            except Exception:
                pass
            raise

        finally:
            self._cleanup_temp_files(job)

    # ── single-account worker (runs in thread) ────────────────────────────

    def _upload_one(
        self,
        *,
        job_id: str,
        account_id: str,
        username: str,
        media_paths: list[str],
        caption: str,
        media_type: str,
        thumbnail_path: str | None,
        igtv_title: str | None,
        usertags_raw: list[dict],
        location_raw: dict | None,
        extra_data: dict,
    ) -> None:
        store = self._store

        # ── pre-flight checks ─────────────────────────────────────────────

        if store.is_stop_requested(job_id):
            store.update_result(job_id, account_id, status="skipped")
            return

        store.wait_if_paused(job_id)

        if store.is_stop_requested(job_id):
            store.update_result(job_id, account_id, status="skipped")
            return

        # Circuit breaker: fast-fail if the Instagram API is currently degraded.
        # Only retryable failures (rate limits, timeouts, 5xx) trip the circuit;
        # account-level errors (bad password, challenge) do not.
        if not _upload_circuit_breaker.allow_request():
            store.update_result(
                job_id, account_id,
                status="failed",
                error="Instagram API circuit open — too many recent failures, will retry later",
                error_code="circuit_open",
            )
            self._notify_sse()
            logger.warning(
                "Circuit open: skipping upload for @%s (job=%s)", username, job_id
            )
            return

        cl = get_client(account_id)
        if not cl:
            store.update_result(
                job_id, account_id, status="failed", error="Account not logged in"
            )
            self._notify_sse()
            return

        store.update_result(job_id, account_id, status="uploading")
        self._notify_sse()
        print(
            f"[POST] Uploading for @{username}: "
            f"type={media_type} caption={repr(caption[:100])}",
            file=sys.stderr,
        )

        usertags = _build_usertags(usertags_raw)
        location = _build_location(location_raw)
        upload_timeout = self._get_upload_timeout(media_type)

        # ── per-account timed upload ──────────────────────────────────────
        #
        # Run _dispatch_upload (blocking instagrapi I/O) in a dedicated thread
        # so we can enforce a hard per-account deadline via Future.result(timeout=).
        # On TimeoutError we return immediately; the abandoned thread dies naturally
        # when instagrapi's own request_timeout fires (~60 s later).
        # _dispatch_upload has no reference to the store, so it cannot corrupt state.

        upload_exec = ThreadPoolExecutor(max_workers=1)
        upload_future = upload_exec.submit(
            _dispatch_upload,
            cl, media_type, media_paths, caption,
            thumbnail_path, igtv_title, usertags, location, extra_data,
        )

        try:
            upload_future.result(timeout=upload_timeout)

        except FuturesTimeoutError:
            store.update_result(
                job_id, account_id,
                status="failed",
                error=f"Upload timed out after {upload_timeout}s",
                error_code="upload_timeout",
            )
            self._notify_sse()
            _upload_circuit_breaker.record_failure(retryable=True)
            log_event(account_id, username, "post_failed", detail="upload_timeout")
            return

        except Exception as e:
            failure = _classify_exception(
                e, operation="post_media", account_id=account_id, username=username,
            )
            store.update_result(
                job_id, account_id,
                status="failed",
                error=failure.user_message,
                error_code=failure.code,
            )
            self._notify_sse()
            _upload_circuit_breaker.record_failure(retryable=failure.retryable)
            log_event(account_id, username, "post_failed",
                      detail=failure.detail or failure.user_message)
            return

        finally:
            # Non-blocking: let any still-running upload thread die on its own.
            upload_exec.shutdown(wait=False)

        # ── success ───────────────────────────────────────────────────────

        store.update_result(job_id, account_id, status="success")
        self._notify_sse()
        _upload_circuit_breaker.record_success()
        log_event(account_id, username, "post_success", detail=f"job={job_id}")

    # ── temp file cleanup ─────────────────────────────────────────────────

    @staticmethod
    def _cleanup_temp_files(job: dict) -> None:
        for path in job.get("_media_paths", []):
            Path(path).unlink(missing_ok=True)
            if path.endswith((".mp4", ".mov")):
                Path(path + ".jpg").unlink(missing_ok=True)
        thumb = job.get("_thumbnail_path")
        if thumb:
            Path(thumb).unlink(missing_ok=True)


# Module-level singleton for backward compatibility.
_executor = PostJobExecutor()


def run_post_job(job_id: str) -> None:
    """Legacy entry point — delegates to PostJobExecutor."""
    _executor.run(job_id)
