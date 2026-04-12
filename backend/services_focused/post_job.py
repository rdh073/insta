from __future__ import annotations

import uuid
from typing import Optional

from app.application.use_cases.post_job import (
    MEDIA_REQUIRED_ERROR_CODE,
    MEDIA_REQUIRED_ERROR_MESSAGE,
)
from state import get_account, iter_jobs_values, set_job

from .account_query import find_account_id_by_username
from .common import utc_now_iso


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
    if not caption:
        return ""
    return caption.strip()


def create_post_job(caption: str, account_ids: list[str], media_paths: list[str]) -> dict:
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
        "createdAt": utc_now_iso(),
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
            "error": MEDIA_REQUIRED_ERROR_MESSAGE,
            "errorCode": MEDIA_REQUIRED_ERROR_CODE,
        }
        for account_id in account_ids
    ]
    job = {
        "id": job_id,
        "caption": caption,
        "mediaUrls": [],
        "mediaType": "photo",
        "targets": [{"accountId": account_id} for account_id in account_ids],
        "status": "needs_media",
        "results": results,
        "createdAt": utc_now_iso(),
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
            f"Post draft created for {', '.join('@' + (get_account(account_id) or {}).get('username', '') for account_id in account_ids)} "
            f"at {scheduled_at}. Attach media via the Post page to activate scheduling."
            if scheduled_at
            else f"Caption draft created for {', '.join('@' + (get_account(account_id) or {}).get('username', '') for account_id in account_ids)}. Attach media via the Post page to publish."
        ),
    }
