"""Transitional compatibility facade for legacy Instagram operations.

Implementation has been split into focused runtime modules under
``instagram_runtime/`` (circuit_breaker, auth, relogin, upload_payloads,
post_job_executor). This module remains the stable import surface while
adapters/tests migrate incrementally.
"""

from __future__ import annotations

import logging
from typing import Optional

from state import (
    IGClient,
    BadPassword,
    ChallengeRequired,
    CaptchaChallengeRequired,
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
from app.adapters.instagram.device_pool import random_device_profile
from app.adapters.instagram.error_utils import translate_instagram_error
from app.adapters.instagram.exception_handler import instagram_exception_handler

from instagram_runtime import auth as _auth
from instagram_runtime import relogin as _relogin
from instagram_runtime.circuit_breaker import SyncCircuitBreaker, _upload_circuit_breaker
from instagram_runtime.post_job_executor import (
    PostJobExecutor,
    _UPLOAD_TIMEOUT_BY_TYPE,
    _UPLOAD_TIMEOUT_DEFAULT,
    _executor,
)
from instagram_runtime.upload_payloads import (
    _DEFAULT_UPLOAD_STRATEGY,
    _UPLOAD_STRATEGIES,
    _UploadFn,
    _build_location,
    _build_usertags,
    _dispatch_upload,
    _upload_album,
    _upload_igtv,
    _upload_photo,
    _upload_reels,
)

logger = logging.getLogger(__name__)


def _new_client(proxy: Optional[str] = None):
    return _auth.new_client(
        proxy,
        ig_client_cls=IGClient,
        device_profile_factory=random_device_profile,
    )


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


def _translate_exception(
    error: Exception,
    *,
    operation: str,
    account_id: str | None = None,
    username: str | None = None,
):
    """Translate an exception and apply shared side effects."""
    return translate_instagram_error(
        error,
        operation=operation,
        account_id=account_id,
        username=username,
    )


def create_authenticated_client(
    username: str,
    password: str,
    proxy: Optional[str] = None,
    totp_secret: Optional[str] = None,
    verify_session: bool = False,
):
    return _auth.create_authenticated_client(
        username,
        password,
        proxy,
        totp_secret,
        verify_session=verify_session,
        ig_client_cls=IGClient,
        new_client_fn=_new_client,
    )


def activate_account_client(account_id: str, client) -> dict:
    return _auth.activate_account_client(account_id, client)


def complete_2fa_client(
    username: str,
    password: str,
    verification_code: str,
    proxy: Optional[str] = None,
):
    return _auth.complete_2fa_client(
        username,
        password,
        verification_code,
        proxy,
        ig_client_cls=IGClient,
        new_client_fn=_new_client,
    )


_MAX_RELOGIN_ATTEMPTS = _relogin._MAX_RELOGIN_ATTEMPTS


def _relogin_session_restore(
    username: str,
    password: str,
    proxy: str | None,
    totp_secret: str | None,
):
    return _relogin._relogin_session_restore(
        username,
        password,
        proxy,
        totp_secret,
        create_authenticated_client_fn=create_authenticated_client,
    )


def _relogin_fresh_credentials(
    username: str,
    password: str,
    proxy: str | None,
    totp_secret: str | None,
):
    return _relogin._relogin_fresh_credentials(
        username,
        password,
        proxy,
        totp_secret,
        new_client_fn=_new_client,
    )


# Maps the string mode value from the port layer to the concrete strategy fn.
_RELOGIN_STRATEGIES = {
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
    return _relogin.relogin_account_sync(
        account_id,
        username=username,
        password=password,
        proxy=proxy,
        totp_secret=totp_secret,
        mode=mode,
        create_authenticated_client_fn=create_authenticated_client,
        new_client_fn=_new_client,
        classify_exception_fn=_classify_exception,
        translate_exception_fn=_translate_exception,
        relogin_strategies=_RELOGIN_STRATEGIES,
    )


def run_post_job(job_id: str) -> None:
    """Legacy entry point — delegates to PostJobExecutor."""
    _executor.run(job_id)


__all__ = [
    "IGClient",
    "BadPassword",
    "ChallengeRequired",
    "CaptchaChallengeRequired",
    "LoginRequired",
    "TwoFactorRequired",
    "SESSIONS_DIR",
    "ThreadSafeJobStore",
    "account_to_dict",
    "get_account",
    "get_client",
    "get_job",
    "has_account",
    "job_store",
    "log_event",
    "pop_client",
    "pop_pending_2fa_client",
    "set_account_status",
    "set_client",
    "store_pending_2fa_client",
    "update_account",
    "instagram_exception_handler",
    "random_device_profile",
    "logger",
    "SyncCircuitBreaker",
    "_upload_circuit_breaker",
    "_UPLOAD_TIMEOUT_BY_TYPE",
    "_UPLOAD_TIMEOUT_DEFAULT",
    "_UploadFn",
    "_UPLOAD_STRATEGIES",
    "_DEFAULT_UPLOAD_STRATEGY",
    "_upload_reels",
    "_upload_igtv",
    "_upload_photo",
    "_upload_album",
    "_dispatch_upload",
    "_build_usertags",
    "_build_location",
    "_new_client",
    "_classify_exception",
    "create_authenticated_client",
    "activate_account_client",
    "complete_2fa_client",
    "_MAX_RELOGIN_ATTEMPTS",
    "_relogin_session_restore",
    "_relogin_fresh_credentials",
    "_RELOGIN_STRATEGIES",
    "relogin_account_sync",
    "PostJobExecutor",
    "_executor",
    "run_post_job",
]
