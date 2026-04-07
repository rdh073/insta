"""
Application services shared by HTTP routes and AI tool adapters.
Keeps transport thin while preserving the current in-memory design.

ARCHITECTURE NOTE:
- Smart engagement logic is NOT in this file
- It lives in: ai_copilot/application/ (graphs, use_cases, nodes)
- This file provides account/client services used by adapters
- Adapters may delegate to this module, but don't expose smart engagement decisions here
"""

from __future__ import annotations

import asyncio
import datetime
import json
import uuid
from typing import Optional

from instagram import (
    activate_account_client,
    complete_2fa_client,
    create_authenticated_client,
    relogin_account_sync,
)
from app.adapters.instagram.exception_handler import instagram_exception_handler
import pyotp as _pyotp


def generate_totp_code(secret: str) -> str:
    return _pyotp.TOTP(secret).now()


def generate_totp_secret() -> str:
    return _pyotp.random_base32()


def verify_totp_code(secret: str, code: str) -> bool:
    return _pyotp.TOTP(secret).verify(code, valid_window=1)


def normalize_totp_secret(secret: str) -> str:
    return secret.replace(" ", "").upper()
from state import (
    LOG_FILE,
    SESSIONS_DIR,
    TwoFactorRequired,
    account_ids,
    account_to_dict,
    clear_account_status,
    find_account_id_by_username as state_find_account_id_by_username,
    get_account,
    get_account_status_value,
    get_client,
    get_job,
    has_account,
    has_client,
    iter_account_items,
    iter_jobs_values,
    log_event,
    pop_account,
    pop_client,
    set_account,
    set_account_status,
    set_job,
    update_account,
    active_client_ids,
)


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _utc_now_iso() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def get_account_status(account_id: str) -> str:
    if has_client(account_id):
        return "active"
    return get_account_status_value(account_id, "idle")


def _account_username(account_id: str, default: str = "") -> str:
    return (get_account(account_id) or {}).get("username", default)


def _apply_account_proxy(account_id: str, proxy: str) -> str:
    username = _account_username(account_id)
    update_account(account_id, proxy=proxy)
    client = get_client(account_id)
    if client:
        client.set_proxy(proxy)
    log_event(account_id, username, "proxy_changed", detail=proxy)
    return username


def _track_relogin_failure(account_id: str, exc: Exception, default_username: str = "") -> str:
    username = _account_username(account_id, default=default_username)
    failure = _classify_exception(
        exc,
        operation="relogin",
        account_id=account_id,
        username=username,
    )
    set_account_status(account_id, "error")
    log_event(account_id, username, "relogin_failed", detail=failure.user_message, status="error")
    return username


def _classify_exception(
    error: Exception,
    *,
    operation: str,
    account_id: str | None = None,
    username: str | None = None,
):
    """Translate an exception to the shared Instagram failure contract."""
    return instagram_exception_handler.handle(
        error,
        operation=operation,
        account_id=account_id,
        username=username,
    )


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


def login_account(username: str, password: str, proxy: Optional[str] = None, totp_secret: Optional[str] = None) -> dict:
    existing = find_account_id_by_username(username)
    if existing and has_client(existing):
        return account_to_dict(existing, status="active")

    # Normalize TOTP secret: remove spaces and uppercase (allow user input "2OWR 5YTV..." format)
    if totp_secret:
        totp_secret = normalize_totp_secret(totp_secret) or None

    account_id = existing or str(uuid.uuid4())
    set_account(account_id, {
        "username": username,
        "password": password,
        "proxy": proxy,
        "totp_secret": totp_secret,
    })

    try:
        client = create_authenticated_client(username, password, proxy)
        result = activate_account_client(account_id, client)
        log_event(account_id, username, "login_success", status="active")
        return result
    except TwoFactorRequired:
        if totp_secret:
            # Auto-generate TOTP code and complete login
            try:
                code = generate_totp_code(totp_secret)
                client = complete_2fa_client(username, password, code, proxy)
                result = activate_account_client(account_id, client)
                log_event(account_id, username, "login_success_totp", status="active")
                return result
            except Exception as exc:
                failure = _classify_exception(
                    exc,
                    operation="complete_2fa",
                    account_id=account_id,
                    username=username,
                )
                log_event(
                    account_id,
                    username,
                    "login_totp_auto_failed",
                    detail=failure.user_message,
                    status="error",
                )
                pop_account(account_id)
                raise
        # No TOTP secret: require manual entry
        log_event(account_id, username, "login_2fa_required", status="2fa_required")
        return {"id": account_id, "username": username, "status": "2fa_required"}
    except Exception as exc:
        failure = _classify_exception(
            exc,
            operation="login",
            account_id=account_id,
            username=username,
        )
        log_event(account_id, username, "login_failed", detail=failure.user_message, status="error")
        pop_account(account_id)
        raise


def complete_2fa_login_account(account_id: str, code: str, is_totp: bool = False) -> dict:
    """
    Complete 2FA login for an account that is awaiting verification code.

    Parameters
    ----------
    account_id : str
        ID of the account awaiting 2FA verification
    code : str
        Verification code (SMS code, TOTP code, etc.)
    is_totp : bool
        If True, verify code as TOTP. If False, pass to instagrapi as SMS/Instagram 2FA code.

    Returns
    -------
    dict
        Account dictionary with status="active"
    """
    if not has_account(account_id):
        raise ValueError("Account not found")
    meta = get_account(account_id) or {}
    username = meta.get("username", "")
    password = meta.get("password", "")
    proxy = meta.get("proxy")

    # If TOTP verification is requested, verify the TOTP code first
    if is_totp:
        totp_secret = meta.get("totp_secret")
        if not totp_secret:
            raise ValueError("TOTP is not enabled for this account")
        if not verify_totp_code(totp_secret, code):
            log_event(account_id, username, "totp_verification_failed", status="error")
            raise ValueError("Invalid TOTP code")
        log_event(account_id, username, "totp_verified", status="active")
        # Note: TOTP is for user's own authentication, not Instagram 2FA
        # Still need to complete Instagram login if it required 2FA
        # The code parameter here would be the Instagram SMS/2FA code if applicable
        result = activate_account_client(account_id, complete_2fa_client(username, password, "", proxy))
        log_event(account_id, username, "login_success", status="active")
        return result

    try:
        client = complete_2fa_client(username, password, code, proxy)
        result = activate_account_client(account_id, client)
        log_event(account_id, username, "login_success", status="active")
        return result
    except Exception as exc:
        failure = _classify_exception(
            exc,
            operation="complete_2fa",
            account_id=account_id,
            username=username,
        )
        log_event(account_id, username, "login_2fa_failed", detail=failure.user_message, status="error")
        raise


def import_accounts_text(text: str) -> list[dict]:
    results = []
    for line in text.strip().splitlines():
        # Extract TOTP secret (if present) using | delimiter
        totp_secret = None
        if "|" in line:
            line, totp_secret = line.rsplit("|", 1)
            totp_secret = totp_secret.strip()
            # Normalize TOTP secret (remove spaces, uppercase)
            if totp_secret:
                totp_secret = normalize_totp_secret(totp_secret)

        parts = line.strip().split(":")
        if len(parts) < 2:
            continue

        username, password = parts[0], parts[1]
        proxy = parts[2] if len(parts) > 2 else None

        try:
            results.append(login_account(username=username, password=password, proxy=proxy, totp_secret=totp_secret))
        except Exception as exc:
            failure = _classify_exception(
                exc,
                operation="login",
                username=username,
            )
            results.append(
                {
                    "id": str(uuid.uuid4()),
                    "username": username,
                    "password": password,
                    "proxy": proxy,
                    "status": "error",
                    "error": failure.user_message,
                    "errorCode": failure.code,
                }
            )

    return results


def import_session_archive(sessions: dict) -> list[dict]:
    results = []
    for username, session_data in sessions.items():
        session_file = SESSIONS_DIR / f"{username}.json"
        session_file.write_text(json.dumps(session_data))

        account_id = str(uuid.uuid4())
        set_account(account_id, {"username": username, "password": "", "proxy": None})
        results.append(account_to_dict(account_id, status="idle"))

    return results


def logout_account(account_id: str, detail: str = "") -> dict:
    if not has_account(account_id):
        raise ValueError("Account not found")

    username = (get_account(account_id) or {}).get("username", "")
    client = pop_client(account_id)
    if client:
        try:
            client.logout()
        except Exception:
            pass

    log_event(account_id, username, "logout", detail=detail, status="removed")
    clear_account_status(account_id)
    pop_account(account_id)
    return {"id": account_id, "username": username, "status": "removed"}


def set_account_proxy(account_id: str, proxy: str) -> dict:
    if not has_account(account_id):
        raise ValueError("Account not found")

    _apply_account_proxy(account_id, proxy)
    return account_to_dict(account_id, status=get_account_status(account_id))


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
    """Relogin one account and keep state/log updates centralized in services."""
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


def bulk_logout_accounts(account_ids: list[str]) -> list[dict]:
    results = []
    for account_id in account_ids:
        try:
            results.append(logout_account(account_id, detail="bulk"))
        except ValueError:
            results.append({"id": account_id, "status": "not_found"})
    return results


def bulk_set_proxy(account_ids: list[str], proxy: str) -> list[dict]:
    results = []
    for account_id in account_ids:
        if not has_account(account_id):
            results.append({"id": account_id, "status": "not_found"})
            continue

        username = _apply_account_proxy(account_id, proxy)
        results.append(
            {
                "id": account_id,
                "username": username,
                "status": "ok",
                "proxy": proxy,
            }
        )
    return results


def get_dashboard_data() -> dict:
    today_prefix = _utc_now().date().isoformat()

    current_account_ids = account_ids()
    total = len(current_account_ids)
    active_ids = set(active_client_ids())
    active = len(active_ids)
    error_count = sum(1 for aid in current_account_ids if get_account_status_value(aid) == "error")
    idle = total - active - error_count

    error_accounts = [
        {
            "id": aid,
            "username": meta.get("username", ""),
            "error": meta.get("error", ""),
            "proxy": meta.get("proxy"),
            "status": "error",
        }
        for aid, meta in iter_account_items()
        if get_account_status_value(aid) == "error"
    ]

    jobs_today_list = [job for job in iter_jobs_values() if job.get("createdAt", "").startswith(today_prefix)]
    jobs_today = {
        "total": len(jobs_today_list),
        "completed": sum(1 for job in jobs_today_list if job["status"] == "completed"),
        "partial": sum(1 for job in jobs_today_list if job["status"] == "partial"),
        "failed": sum(1 for job in jobs_today_list if job["status"] == "failed"),
    }

    recent_jobs = [{k: v for k, v in job.items() if not k.startswith("_")} for job in list(iter_jobs_values())[-5:]]

    top_accounts = sorted(
        [
            {
                "id": aid,
                "username": meta.get("username", ""),
                "followers": meta.get("followers") or 0,
                "status": get_account_status(aid),
            }
            for aid, meta in iter_account_items()
        ],
        key=lambda item: item["followers"],
        reverse=True,
    )[:5]

    return {
        "accounts": {
            "total": total,
            "active": active,
            "error": error_count,
            "idle": idle,
        },
        "error_accounts": error_accounts,
        "jobs_today": jobs_today,
        "recent_jobs": recent_jobs,
        "top_accounts": top_accounts,
    }


def read_log_entries(
    limit: int = 100,
    offset: int = 0,
    username: Optional[str] = None,
    event: Optional[str] = None,
) -> dict:
    if not LOG_FILE.exists():
        return {"entries": [], "total": 0}

    entries = []
    try:
        for line_number, line in enumerate(LOG_FILE.read_text().splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON log entry in {LOG_FILE} at line {line_number}"
                ) from exc
    except OSError as exc:
        raise RuntimeError(f"Failed to read activity log at {LOG_FILE}") from exc

    entries.reverse()

    if username:
        entries = [entry for entry in entries if entry.get("username", "").lower() == username.lower()]
    if event:
        entries = [entry for entry in entries if entry.get("event") == event]

    total = len(entries)
    return {"entries": entries[offset : offset + limit], "total": total}


def list_posts_data() -> list[dict]:
    return [{k: v for k, v in job.items() if not k.startswith("_")} for job in iter_jobs_values()]


def list_recent_post_jobs(limit: int = 10, status_filter: Optional[str] = None) -> dict:
    jobs = list(iter_jobs_values())
    if status_filter:
        jobs = [job for job in jobs if job.get("status") == status_filter]
    jobs = jobs[-limit:]
    return {
        "jobs": [
            {
                "id": job["id"],
                "status": job["status"],
                "caption": (job["caption"][:80] + "…") if len(job["caption"]) > 80 else job["caption"],
                "targets": len(job["targets"]),
                "createdAt": job["createdAt"],
                "results": [
                    {"username": result["username"], "status": result["status"]}
                    for result in job.get("results", [])
                ],
            }
            for job in jobs
        ],
        "total": len(jobs),
    }


def _validate_caption(caption: str) -> str:
    """
    Validate and clean caption while preserving hashtags and mentions.
    Ensures hashtags (#) and mentions (@) are preserved.
    """
    if not caption:
        return ""

    # Strip leading/trailing whitespace but preserve internal content
    caption = caption.strip()

    return caption


def create_post_job(caption: str, account_ids: list[str], media_paths: list[str]) -> dict:
    # Validate caption to ensure hashtags/mentions are preserved
    caption = _validate_caption(caption)

    media_type = "video" if any(path.endswith((".mp4", ".mov")) for path in media_paths) else (
        "album" if len(media_paths) > 1 else "photo"
    )

    job_id = str(uuid.uuid4())
    results = []
    for account_id in account_ids:
        username = (get_account(account_id) or {}).get("username", account_id)
        results.append({"accountId": account_id, "username": username, "status": "pending"})

    job = {
        "id": job_id,
        "caption": caption,
        "mediaUrls": [],
        "mediaType": media_type,
        "targets": [{"accountId": account_id} for account_id in account_ids],
        "status": "pending",
        "results": results,
        "createdAt": _utc_now_iso(),
        "_media_paths": media_paths,
    }
    set_job(job_id, job)
    return job


def create_scheduled_post_draft(
    usernames: list[str],
    caption: str,
    scheduled_at: Optional[str] = None,
) -> dict:
    normalized_usernames = [username.lstrip("@") for username in usernames]

    account_ids = []
    not_found = []
    for username in normalized_usernames:
        account_id = find_account_id_by_username(username)
        if account_id:
            account_ids.append(account_id)
        else:
            not_found.append(username)

    if not account_ids:
        return {"error": "None of the specified accounts were found", "not_found": not_found}

    job_id = str(uuid.uuid4())
    results = [
        {
            "accountId": account_id,
            "username": (get_account(account_id) or {}).get("username", account_id),
            "status": "pending",
        }
        for account_id in account_ids
    ]
    job = {
        "id": job_id,
        "caption": caption,
        "mediaUrls": [],
        "mediaType": "photo",
        "targets": [{"accountId": account_id} for account_id in account_ids],
        "status": "needs_media" if not scheduled_at else "scheduled",
        "results": results,
        "createdAt": _utc_now_iso(),
        "_media_paths": [],
        "_scheduled_at": scheduled_at,
    }
    set_job(job_id, job)

    return {
        "success": True,
        "jobId": job_id,
        "status": job["status"],
        "targets": [(get_account(account_id) or {}).get("username") for account_id in account_ids],
        "not_found": not_found,
        "scheduled_at": scheduled_at,
        "message": (
            f"Post scheduled for {', '.join('@' + (get_account(account_id) or {}).get('username', '') for account_id in account_ids)} "
            f"at {scheduled_at}. Attach media via the Post page."
            if scheduled_at
            else f"Caption draft created for {', '.join('@' + (get_account(account_id) or {}).get('username', '') for account_id in account_ids)}. Attach media via the Post page to publish."
        ),
    }
