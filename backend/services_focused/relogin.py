from __future__ import annotations

import asyncio
import inspect
from typing import Callable

import state
from instagram import relogin_account_sync as default_relogin_account_sync

from .account_query import find_account_id_by_username, get_account_username
from .common import classify_exception


ReloginSync = Callable[..., dict]


def _supports_credentials_signature(relogin_sync: ReloginSync) -> bool:
    try:
        params = inspect.signature(relogin_sync).parameters
    except (TypeError, ValueError):
        return False
    return "username" in params and "password" in params


def _invoke_relogin_sync(relogin_sync: ReloginSync, account_id: str) -> dict:
    if _supports_credentials_signature(relogin_sync):
        meta = state.get_account(account_id) or {}
        return relogin_sync(
            account_id,
            username=meta.get("username", ""),
            password=meta.get("password", ""),
            proxy=meta.get("proxy"),
            totp_secret=meta.get("totp_secret"),
            country=meta.get("country"),
            country_code=meta.get("country_code"),
            locale=meta.get("locale"),
            timezone_offset=meta.get("timezone_offset"),
        )
    return relogin_sync(account_id)


def track_relogin_failure(account_id: str, exc: Exception, default_username: str = "") -> str:
    username = get_account_username(account_id, default=default_username)
    failure = classify_exception(
        exc,
        operation="relogin",
        account_id=account_id,
        username=username,
    )
    state.set_account_status(account_id, "error")
    state.log_event(account_id, username, "relogin_failed", detail=failure.user_message, status="error")
    return username


async def bulk_relogin_accounts(
    account_ids: list[str],
    concurrency: int = 5,
    *,
    relogin_sync: ReloginSync = default_relogin_account_sync,
) -> list[dict]:
    semaphore = asyncio.Semaphore(concurrency)

    async def _one(account_id: str) -> dict:
        async with semaphore:
            try:
                return await asyncio.to_thread(_invoke_relogin_sync, relogin_sync, account_id)
            except Exception as exc:
                username = track_relogin_failure(account_id, exc, default_username=account_id)
                failure = classify_exception(
                    exc,
                    operation="relogin",
                    account_id=account_id,
                    username=username,
                )
                return {
                    "id": account_id,
                    "username": username,
                    "status": "error",
                    "error": failure.user_message,
                    "errorCode": failure.code,
                }

    return list(await asyncio.gather(*[_one(account_id) for account_id in account_ids]))


def relogin_account_with_tracking(
    account_id: str,
    *,
    relogin_sync: ReloginSync = default_relogin_account_sync,
) -> dict:
    try:
        return _invoke_relogin_sync(relogin_sync, account_id)
    except ValueError:
        raise
    except Exception as exc:
        track_relogin_failure(account_id, exc)
        raise


def relogin_account_by_username(
    username: str,
    *,
    relogin_sync: ReloginSync = default_relogin_account_sync,
) -> dict:
    normalized = username.lstrip("@")
    account_id = find_account_id_by_username(normalized)
    if not account_id:
        return {"error": f"Account @{normalized} not found"}

    try:
        relogin_account_with_tracking(account_id, relogin_sync=relogin_sync)
        return {
            "success": True,
            "username": normalized,
            "status": "active",
            "followers": (state.get_account(account_id) or {}).get("followers"),
            "message": f"@{normalized} re-logged in successfully",
        }
    except Exception as exc:
        failure = classify_exception(
            exc,
            operation="relogin",
            account_id=account_id,
            username=normalized,
        )
        return {"success": False, "username": normalized, "error": failure.user_message, "errorCode": failure.code}
