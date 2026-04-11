from __future__ import annotations

from typing import Optional

from state import (
    account_ids,
    account_to_dict,
    find_account_id_by_username as state_find_account_id_by_username,
    get_account,
    get_client,
    has_client,
    update_account,
)

from ._common import _classify_exception, get_account_status


def find_account_id_by_username(username: str) -> Optional[str]:
    return state_find_account_id_by_username(username)


def list_accounts_data() -> list[dict]:
    return [account_to_dict(aid, status=get_account_status(aid)) for aid in account_ids()]


def get_accounts_summary() -> dict:
    accounts = [
        {
            **account,
            "proxy": account.get("proxy") or "none",
            "fullName": account.get("fullName"),
        }
        for account in list_accounts_data()
    ]
    return {
        "accounts": accounts,
        "total": len(account_ids()),
        "active": sum(1 for account_id in account_ids() if has_client(account_id)),
    }


def get_account_info_by_username(username: str) -> dict:
    normalized = username.lstrip("@")
    account_id = find_account_id_by_username(normalized)
    if not account_id:
        return {"error": f"Account @{normalized} not found"}

    client = get_client(account_id)
    if not client:
        return {"error": f"@{normalized} is not logged in", "status": "idle"}

    try:
        user = client.user_info(client.user_id)
        update_account(
            account_id,
            full_name=user.full_name,
            followers=user.follower_count,
            following=user.following_count,
        )
        return {
            "username": user.username,
            "fullName": user.full_name,
            "biography": user.biography,
            "followers": user.follower_count,
            "following": user.following_count,
            "mediaCount": user.media_count,
            "isPrivate": user.is_private,
            "isVerified": user.is_verified,
            "isBusiness": user.is_business,
        }
    except Exception as exc:
        failure = _classify_exception(
            exc,
            operation="get_account_info",
            account_id=account_id,
            username=normalized,
        )
        return {"error": failure.user_message, "errorCode": failure.code}
