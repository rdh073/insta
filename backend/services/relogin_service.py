from __future__ import annotations

import asyncio

from instagram import relogin_account_sync
from state import get_account

from ._common import _classify_exception, _track_relogin_failure
from .account_query_service import find_account_id_by_username


async def bulk_relogin_accounts(account_ids: list[str], concurrency: int = 5) -> list[dict]:
    semaphore = asyncio.Semaphore(concurrency)

    async def _one(account_id: str) -> dict:
        async with semaphore:
            try:
                return await asyncio.to_thread(relogin_account_sync, account_id)
            except Exception as exc:
                username = _track_relogin_failure(account_id, exc, default_username=account_id)
                failure = _classify_exception(
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


def relogin_account_with_tracking(account_id: str) -> dict:
    try:
        return relogin_account_sync(account_id)
    except ValueError:
        raise
    except Exception as exc:
        _track_relogin_failure(account_id, exc)
        raise


def relogin_account_by_username(username: str) -> dict:
    normalized = username.lstrip("@")
    account_id = find_account_id_by_username(normalized)
    if not account_id:
        return {"error": f"Account @{normalized} not found"}

    try:
        relogin_account_with_tracking(account_id)
        return {
            "success": True,
            "username": normalized,
            "status": "active",
            "followers": (get_account(account_id) or {}).get("followers"),
            "message": f"@{normalized} re-logged in successfully",
        }
    except Exception as exc:
        failure = _classify_exception(
            exc,
            operation="relogin",
            account_id=account_id,
            username=normalized,
        )
        return {"success": False, "username": normalized, "error": failure.user_message, "errorCode": failure.code}
