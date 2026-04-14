"""Concrete adapter for FollowupCreatorPort — wraps PostJobUseCases."""

from __future__ import annotations

import asyncio

from ai_copilot.adapters.post_job_scheduler_contract import PostJobSchedulerPort
from ai_copilot.application.campaign_monitor.ports import FollowupCreatorPort


class FollowupCreatorAdapter(FollowupCreatorPort):
    """Creates followup post jobs via PostJobUseCases.

    Args:
        postjob_usecases: PostJobUseCases instance.
    """

    def __init__(self, postjob_usecases: PostJobSchedulerPort):
        self._postjob = postjob_usecases

    async def create_followup(
        self,
        campaign_summary: dict,
        operator_decision: dict,
        original_job_ids: list[str],
    ) -> dict:
        """Schedule a followup job.

        Derives target usernames and scheduling parameters from the operator
        decision's 'parameters' sub-dict, falling back to reasonable defaults.
        """
        parameters = operator_decision.get("parameters") or {}
        usernames: list[str] = parameters.get("usernames") or []
        caption: str = parameters.get("caption") or _default_caption(campaign_summary)
        scheduled_at: str | None = parameters.get("scheduled_at")

        try:
            result = await asyncio.to_thread(
                self._create_job,
                usernames=usernames,
                caption=caption,
                scheduled_at=scheduled_at,
                original_job_ids=original_job_ids,
            )
            return result
        except Exception as exc:
            raise RuntimeError(f"FollowupCreatorAdapter.create_followup failed: {exc}") from exc

    def _create_job(
        self,
        usernames: list[str],
        caption: str,
        scheduled_at: str | None,
        original_job_ids: list[str],
    ) -> dict:
        """Blocking call to PostJobUseCases."""
        _ = original_job_ids
        return self._postjob.create_scheduled_post_for_usernames(
            usernames=usernames,
            caption=caption,
            scheduled_at=scheduled_at,
        )


def _default_caption(campaign_summary: dict) -> str:
    completion_rate = campaign_summary.get("completion_rate", 0.0)
    return (
        f"Following up on our recent campaign "
        f"(completion: {completion_rate:.0%}). Stay tuned for more!"
    )
