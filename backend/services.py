"""Transitional compatibility facade for legacy service imports.

Implementation has been split into focused modules under
``services_focused/`` (totp, account_query, account_auth, relogin,
post_job, dashboard). Keep this file as the stable import surface while
adapters/tests migrate incrementally.
"""

from __future__ import annotations

from typing import Optional

from instagram import relogin_account_sync as relogin_account_sync
from state import LOG_FILE, SESSIONS_DIR

from services_focused import account_auth as _account_auth
from services_focused import account_query as _account_query
from services_focused import common as _common
from services_focused import dashboard as _dashboard
from services_focused import post_job as _post_job
from services_focused import relogin as _relogin
from services_focused import totp as _totp


def generate_totp_code(secret: str) -> str:
    return _totp.generate_totp_code(secret)


def generate_totp_secret() -> str:
    return _totp.generate_totp_secret()


def verify_totp_code(secret: str, code: str) -> bool:
    return _totp.verify_totp_code(secret, code)


def normalize_totp_secret(secret: str) -> str:
    return _totp.normalize_totp_secret(secret)


def _utc_now():
    return _common.utc_now()


def _utc_now_iso() -> str:
    return _common.utc_now_iso()


def get_account_status(account_id: str) -> str:
    return _account_query.get_account_status(account_id)


def _account_username(account_id: str, default: str = "") -> str:
    return _account_query.get_account_username(account_id, default=default)


def _apply_account_proxy(account_id: str, proxy: str) -> str:
    return _account_auth.apply_account_proxy(account_id, proxy)


def _track_relogin_failure(account_id: str, exc: Exception, default_username: str = "") -> str:
    return _relogin.track_relogin_failure(account_id, exc, default_username=default_username)


def _classify_exception(
    error: Exception,
    *,
    operation: str,
    account_id: str | None = None,
    username: str | None = None,
):
    return _common.classify_exception(
        error,
        operation=operation,
        account_id=account_id,
        username=username,
    )


def find_account_id_by_username(username: str) -> Optional[str]:
    return _account_query.find_account_id_by_username(username)


def list_accounts_data() -> list[dict]:
    return _account_query.list_accounts_data()


def get_accounts_summary() -> dict:
    return _account_query.get_accounts_summary()


def get_account_info_by_username(username: str) -> dict:
    return _account_query.get_account_info_by_username(username)


def login_account(username: str, password: str, proxy: Optional[str] = None, totp_secret: Optional[str] = None) -> dict:
    return _account_auth.login_account(
        username=username,
        password=password,
        proxy=proxy,
        totp_secret=totp_secret,
    )


def complete_2fa_login_account(account_id: str, code: str, is_totp: bool = False) -> dict:
    return _account_auth.complete_2fa_login_account(account_id, code, is_totp=is_totp)


def import_accounts_text(text: str) -> list[dict]:
    return _account_auth.import_accounts_text(text)


def import_session_archive(sessions: dict) -> list[dict]:
    return _account_auth.import_session_archive(sessions, sessions_dir=SESSIONS_DIR)


def logout_account(account_id: str, detail: str = "") -> dict:
    return _account_auth.logout_account(account_id, detail=detail)


def set_account_proxy(account_id: str, proxy: str) -> dict:
    return _account_auth.set_account_proxy(account_id, proxy)


async def bulk_relogin_accounts(account_ids: list[str], concurrency: int = 5) -> list[dict]:
    return await _relogin.bulk_relogin_accounts(
        account_ids,
        concurrency=concurrency,
        relogin_sync=relogin_account_sync,
    )


def relogin_account_with_tracking(account_id: str) -> dict:
    return _relogin.relogin_account_with_tracking(
        account_id,
        relogin_sync=relogin_account_sync,
    )


def relogin_account_by_username(username: str) -> dict:
    return _relogin.relogin_account_by_username(
        username,
        relogin_sync=relogin_account_sync,
    )


def bulk_logout_accounts(account_ids: list[str]) -> list[dict]:
    return _account_auth.bulk_logout_accounts(account_ids)


def bulk_set_proxy(account_ids: list[str], proxy: str) -> list[dict]:
    return _account_auth.bulk_set_proxy(account_ids, proxy)


def get_dashboard_data() -> dict:
    return _dashboard.get_dashboard_data()


def read_log_entries(
    limit: int = 100,
    offset: int = 0,
    username: Optional[str] = None,
    event: Optional[str] = None,
) -> dict:
    return _dashboard.read_log_entries(
        limit=limit,
        offset=offset,
        username=username,
        event=event,
        log_file=LOG_FILE,
    )


def list_posts_data() -> list[dict]:
    return _post_job.list_posts_data()


def list_recent_post_jobs(limit: int = 10, status_filter: Optional[str] = None) -> dict:
    return _post_job.list_recent_post_jobs(limit=limit, status_filter=status_filter)


def _validate_caption(caption: str) -> str:
    return _post_job._validate_caption(caption)


def create_post_job(caption: str, account_ids: list[str], media_paths: list[str]) -> dict:
    return _post_job.create_post_job(caption, account_ids, media_paths)


def create_scheduled_post_draft(
    usernames: list[str],
    caption: str,
    scheduled_at: Optional[str] = None,
) -> dict:
    return _post_job.create_scheduled_post_draft(
        usernames,
        caption,
        scheduled_at=scheduled_at,
    )
