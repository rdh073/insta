from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import state

from .account_query import get_account_status
from .common import utc_now


def get_dashboard_data() -> dict:
    today_prefix = utc_now().date().isoformat()

    current_account_ids = state.account_ids()
    total = len(current_account_ids)
    active_ids = set(state.active_client_ids())
    active = len(active_ids)
    error_count = sum(1 for aid in current_account_ids if state.get_account_status_value(aid) == "error")
    idle = total - active - error_count

    error_accounts = [
        {
            "id": aid,
            "username": meta.get("username", ""),
            "error": meta.get("error", ""),
            "proxy": meta.get("proxy"),
            "status": "error",
        }
        for aid, meta in state.iter_account_items()
        if state.get_account_status_value(aid) == "error"
    ]

    jobs_today_list = [job for job in state.iter_jobs_values() if job.get("createdAt", "").startswith(today_prefix)]
    jobs_today = {
        "total": len(jobs_today_list),
        "completed": sum(1 for job in jobs_today_list if job["status"] == "completed"),
        "partial": sum(1 for job in jobs_today_list if job["status"] == "partial"),
        "failed": sum(1 for job in jobs_today_list if job["status"] == "failed"),
    }

    recent_jobs = [{k: v for k, v in job.items() if not k.startswith("_")} for job in list(state.iter_jobs_values())[-5:]]

    top_accounts = sorted(
        [
            {
                "id": aid,
                "username": meta.get("username", ""),
                "followers": meta.get("followers") or 0,
                "status": get_account_status(aid),
            }
            for aid, meta in state.iter_account_items()
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
    *,
    log_file: Path | None = None,
) -> dict:
    target_log_file = log_file or state.LOG_FILE
    if not target_log_file.exists():
        return {"entries": [], "total": 0}

    entries = []
    try:
        for line_number, line in enumerate(target_log_file.read_text().splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON log entry in {target_log_file} at line {line_number}"
                ) from exc
    except OSError as exc:
        raise RuntimeError(f"Failed to read activity log at {target_log_file}") from exc

    entries.reverse()

    if username:
        entries = [entry for entry in entries if entry.get("username", "").lower() == username.lower()]
    if event:
        entries = [entry for entry in entries if entry.get("event") == event]

    total = len(entries)
    return {"entries": entries[offset : offset + limit], "total": total}

