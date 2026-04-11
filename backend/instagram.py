"""Backwards-compatible facade for the split Instagram runtime package.

Legacy callers still import `instagram`; the implementation now lives in the
`instagram_runtime` sibling package.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, wait as wait_futures
from pathlib import Path
from typing import Callable, Optional

from app.adapters.instagram.device_pool import random_device_profile
from app.adapters.instagram.exception_handler import instagram_exception_handler
from instagram_runtime import auth as _auth_runtime
from instagram_runtime import post_job_executor as _post_job_runtime
from instagram_runtime import relogin as _relogin_runtime
from instagram_runtime.circuit_breaker import SyncCircuitBreaker
from instagram_runtime.post_job_executor import PostJobExecutor as _RuntimePostJobExecutor
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


logger = logging.getLogger(__name__)


def _sync_runtime_globals() -> None:
    _auth_runtime.IGClient = IGClient
    _auth_runtime.BadPassword = BadPassword
    _auth_runtime.ChallengeRequired = ChallengeRequired
    _auth_runtime.LoginRequired = LoginRequired
    _auth_runtime.TwoFactorRequired = TwoFactorRequired
    _auth_runtime.SESSIONS_DIR = SESSIONS_DIR
    _auth_runtime.account_to_dict = account_to_dict
    _auth_runtime.pop_pending_2fa_client = pop_pending_2fa_client
    _auth_runtime.set_account_status = set_account_status
    _auth_runtime.set_client = set_client
    _auth_runtime.store_pending_2fa_client = store_pending_2fa_client
    _auth_runtime.instagram_exception_handler = instagram_exception_handler
    _auth_runtime.logger = logger
    _auth_runtime.random_device_profile = random_device_profile

    _relogin_runtime.SESSIONS_DIR = SESSIONS_DIR
    _relogin_runtime.TwoFactorRequired = TwoFactorRequired
    _relogin_runtime.log_event = log_event
    _relogin_runtime.pop_client = pop_client
    _relogin_runtime.store_pending_2fa_client = store_pending_2fa_client
    _relogin_runtime.time = time

    _post_job_runtime.FuturesTimeoutError = FuturesTimeoutError
    _post_job_runtime.Path = Path
    _post_job_runtime.ThreadPoolExecutor = ThreadPoolExecutor
    _post_job_runtime.ThreadSafeJobStore = ThreadSafeJobStore
    _post_job_runtime.get_client = get_client
    _post_job_runtime.job_store = job_store
    _post_job_runtime.log_event = log_event
    _post_job_runtime.logger = logger
    _post_job_runtime.sys = sys
    _post_job_runtime.wait_futures = wait_futures


_sync_runtime_globals()


def create_authenticated_client(
    username: str,
    password: str,
    proxy: Optional[str] = None,
    totp_secret: Optional[str] = None,
    verify_session: bool = False,
):
    _sync_runtime_globals()
    return _auth_runtime.create_authenticated_client(
        username,
        password,
        proxy,
        totp_secret,
        verify_session=verify_session,
    )


def activate_account_client(account_id: str, client) -> dict:
    _sync_runtime_globals()
    return _auth_runtime.activate_account_client(account_id, client)


def complete_2fa_client(
    username: str,
    password: str,
    verification_code: str,
    proxy: Optional[str] = None,
):
    _sync_runtime_globals()
    return _auth_runtime.complete_2fa_client(username, password, verification_code, proxy)


def relogin_account_sync(
    account_id: str,
    *,
    username: str,
    password: str,
    proxy: str | None = None,
    totp_secret: str | None = None,
    mode: str = "session_restore",
) -> dict:
    _sync_runtime_globals()
    return _relogin_runtime.relogin_account_sync(
        account_id,
        username=username,
        password=password,
        proxy=proxy,
        totp_secret=totp_secret,
        mode=mode,
    )


class PostJobExecutor(_RuntimePostJobExecutor):
    """Facade subclass that keeps runtime globals aligned with legacy patches."""

    def __init__(
        self,
        store: ThreadSafeJobStore | None = None,
        upload_timeout: int | None = None,
    ) -> None:
        _sync_runtime_globals()
        super().__init__(store=store, upload_timeout=upload_timeout)

    def run(self, job_id: str) -> None:
        _sync_runtime_globals()
        super().run(job_id)


_executor = PostJobExecutor()


def run_post_job(job_id: str) -> None:
    _sync_runtime_globals()
    _executor.run(job_id)


__all__ = [
    "BadPassword",
    "Callable",
    "ChallengeRequired",
    "FuturesTimeoutError",
    "IGClient",
    "LoginRequired",
    "Optional",
    "Path",
    "PostJobExecutor",
    "SESSIONS_DIR",
    "SyncCircuitBreaker",
    "ThreadPoolExecutor",
    "ThreadSafeJobStore",
    "TwoFactorRequired",
    "account_to_dict",
    "activate_account_client",
    "annotations",
    "complete_2fa_client",
    "create_authenticated_client",
    "get_account",
    "get_client",
    "get_job",
    "has_account",
    "instagram_exception_handler",
    "job_store",
    "log_event",
    "logger",
    "logging",
    "pop_client",
    "pop_pending_2fa_client",
    "random_device_profile",
    "relogin_account_sync",
    "run_post_job",
    "set_account_status",
    "set_client",
    "store_pending_2fa_client",
    "sys",
    "threading",
    "time",
    "update_account",
    "wait_futures",
]
