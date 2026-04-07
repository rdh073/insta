"""Logging and dashboard use cases."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..dto.account_dto import AccountResponse
from ..ports import AccountRepository, ClientRepository, StatusRepository, JobRepository
from ..ports.log_reader import LogReaderPort


class LogsUseCases:
    """Activity logging and dashboard aggregation workflows."""

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        status_repo: StatusRepository,
        job_repo: JobRepository,
        log_reader: LogReaderPort | None = None,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.status_repo = status_repo
        self.job_repo = job_repo
        self._log_reader = log_reader

    def get_dashboard_data(self) -> dict:
        """Get aggregated fleet health for dashboard."""
        today_prefix = datetime.utcnow().date().isoformat()

        # Account stats
        all_account_ids = self.account_repo.list_all_ids()
        total = len(all_account_ids)
        active_ids = set(self.client_repo.list_active_ids())
        active = len(active_ids)
        error_count = sum(
            1 for aid in all_account_ids
            if self.status_repo.get(aid, "idle") == "error"
        )
        idle = total - active - error_count

        # Error accounts
        error_accounts = [
            {
                "id": aid,
                "username": meta.get("username", ""),
                "error": meta.get("error", ""),
                "proxy": meta.get("proxy"),
                "status": "error",
            }
            for aid, meta in self.account_repo.iter_all()
            if self.status_repo.get(aid, "idle") == "error"
        ]

        # Job stats
        all_jobs = self.job_repo.list_all()
        jobs_today_list = [
            job for job in all_jobs
            if job.get("createdAt", "").startswith(today_prefix)
        ]
        jobs_today = {
            "total": len(jobs_today_list),
            "completed": sum(1 for job in jobs_today_list if job["status"] == "completed"),
            "partial": sum(1 for job in jobs_today_list if job["status"] == "partial"),
            "failed": sum(1 for job in jobs_today_list if job["status"] == "failed"),
        }

        # Recent jobs
        recent_jobs = [
            {k: v for k, v in job.items() if not k.startswith("_")}
            for job in all_jobs[-5:]
        ]

        # Top accounts by followers
        top_accounts = sorted(
            [
                {
                    "id": aid,
                    "username": meta.get("username", ""),
                    "followers": meta.get("followers") or 0,
                    "status": "active" if self.client_repo.exists(aid) else self.status_repo.get(aid, "idle"),
                }
                for aid, meta in self.account_repo.iter_all()
            ],
            key=lambda x: x["followers"],
            reverse=True,
        )[:10]

        return {
            "accounts": {
                "total": total,
                "active": active,
                "idle": idle,
                "error": error_count,
                "errorAccounts": error_accounts,
            },
            "jobsToday": jobs_today,
            "recentJobs": recent_jobs,
            "topAccounts": top_accounts,
        }

    def read_log_entries(
        self,
        limit: int = 100,
        offset: int = 0,
        username: Optional[str] = None,
        event: Optional[str] = None,
    ) -> dict:
        """Read activity log entries with optional filtering.

        Returns ``{"entries": [...], "total": int}``.
        """
        if self._log_reader is None:
            return {"entries": [], "total": 0}
        return self._log_reader.read_entries(
            limit=limit, offset=offset, username=username, event=event,
        )
