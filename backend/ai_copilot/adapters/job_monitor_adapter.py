"""Concrete adapter for JobMonitorPort — wraps PostJobUseCases, AccountUseCases, InsightUseCases."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from ai_copilot.application.campaign_monitor.ports import JobMonitorPort


class JobMonitorAdapter(JobMonitorPort):
    """Wraps app use cases to satisfy JobMonitorPort.

    Args:
        postjob_usecases: PostJobUseCases instance.
        account_usecases: AccountUseCases instance.
        insight_usecases: InsightUseCases instance (optional).
    """

    def __init__(
        self,
        postjob_usecases,
        account_usecases,
        insight_usecases=None,
    ):
        self._postjob = postjob_usecases
        self._account = account_usecases
        self._insight = insight_usecases

    async def load_recent_jobs(
        self,
        lookback_days: int,
        job_ids: list[str],
    ) -> list[dict]:
        """Load jobs from PostJobUseCases.

        If job_ids is provided, load those specific jobs.
        Otherwise list recent jobs within the lookback window.
        """
        if job_ids:
            jobs = await asyncio.to_thread(
                self._load_jobs_by_ids,
                job_ids,
            )
        else:
            cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
            jobs = await asyncio.to_thread(
                self._list_recent_jobs,
                cutoff,
            )
        return jobs

    def _load_jobs_by_ids(self, job_ids: list[str]) -> list[dict]:
        results = []
        for jid in job_ids:
            try:
                job = self._postjob.get_job(jid)
                if job:
                    results.append(_job_to_dict(job))
            except Exception:
                pass
        return results

    def _list_recent_jobs(self, cutoff: datetime) -> list[dict]:
        try:
            # Try paginated listing; fall back to simple list
            raw = self._postjob.list_post_jobs()
        except Exception:
            return []

        results = []
        for job in raw or []:
            job_dict = _job_to_dict(job)
            created_at = job_dict.get("created_at")
            if created_at:
                try:
                    if isinstance(created_at, str):
                        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    elif isinstance(created_at, (int, float)):
                        dt = datetime.fromtimestamp(created_at, tz=timezone.utc)
                    else:
                        dt = created_at
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt < cutoff:
                        continue
                except Exception:
                    pass
            results.append(job_dict)
        return results

    async def get_account_health_bulk(
        self,
        account_ids: list[str],
    ) -> dict:
        """Fetch health summary for multiple accounts."""
        result = {}
        for account_id in account_ids:
            try:
                health = await asyncio.to_thread(
                    self._get_single_account_health, account_id
                )
                result[account_id] = health
            except Exception:
                result[account_id] = {
                    "status": "unknown",
                    "login_state": "unknown",
                    "cooldown_until": None,
                    "proxy": None,
                }
        return result

    def _get_single_account_health(self, account_id: str) -> dict:
        try:
            info = self._account.get_account_info(account_id)
            return {
                "status": info.get("status", "unknown"),
                "login_state": info.get("login_state", "unknown"),
                "cooldown_until": info.get("cooldown_until"),
                "proxy": info.get("proxy"),
            }
        except Exception:
            return {
                "status": "unknown",
                "login_state": "unknown",
                "cooldown_until": None,
                "proxy": None,
            }

    async def get_post_insights(
        self,
        account_id: str,
        job_id: str,
    ) -> dict | None:
        """Fetch post insights if InsightUseCases is available."""
        if self._insight is None:
            return None
        try:
            result = await asyncio.to_thread(
                self._insight.get_media_insight,
                account_id=account_id,
                media_id=job_id,
            )
            if not result:
                return None
            return {
                "likes": result.get("like_count", 0),
                "comments": result.get("comment_count", 0),
                "reach": result.get("reach", 0),
                "saves": result.get("saved", 0),
            }
        except Exception:
            return None


def _job_to_dict(job: Any) -> dict:
    """Normalize a job object/dict to a plain dict."""
    if isinstance(job, dict):
        return job
    # Handle dataclass / pydantic model / named tuple
    if hasattr(job, "__dict__"):
        return {k: v for k, v in job.__dict__.items() if not k.startswith("_")}
    if hasattr(job, "_asdict"):
        return job._asdict()
    return {"id": str(job)}
