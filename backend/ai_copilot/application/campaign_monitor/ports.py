"""Ports (abstract interfaces) for Campaign Monitor workflow.

Ports define what the nodes need from the outside world.
Adapters provide concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class JobMonitorPort(ABC):
    """Port for reading job status and account health data."""

    @abstractmethod
    async def load_recent_jobs(
        self,
        lookback_days: int,
        job_ids: list[str],
    ) -> list[dict]:
        """Load recent post jobs.

        Args:
            lookback_days: How many days to scan back.
            job_ids: Specific job IDs to load. Empty = load all recent.

        Returns:
            List of job status dicts with at least:
            {id, account_id, status, created_at, campaign_tag, username}
        """

    @abstractmethod
    async def get_account_health_bulk(
        self,
        account_ids: list[str],
    ) -> dict:
        """Fetch health summary for multiple accounts.

        Args:
            account_ids: Account IDs to check.

        Returns:
            Dict mapping account_id → health summary dict
            {status, login_state, cooldown_until, proxy}
        """

    @abstractmethod
    async def get_post_insights(
        self,
        account_id: str,
        job_id: str,
    ) -> dict | None:
        """Fetch engagement analytics for a post job.

        Args:
            account_id: Account that published the post.
            job_id: Job ID to look up.

        Returns:
            Insight dict {likes, comments, reach, saves} or None if unavailable.
        """


class FollowupCreatorPort(ABC):
    """Port for creating followup campaign tasks."""

    @abstractmethod
    async def create_followup(
        self,
        campaign_summary: dict,
        operator_decision: dict,
        original_job_ids: list[str],
    ) -> dict:
        """Schedule a followup post job based on campaign outcome.

        Args:
            campaign_summary: Aggregated campaign metrics and summary.
            operator_decision: Operator approval dict {decision, parameters}.
            original_job_ids: Job IDs this followup is based on.

        Returns:
            Dict with {job_id, scheduled_at, status}.
        """
