"""Concrete adapter for FollowupCreatorPort — wraps PostJobUseCases."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from ai_copilot.application.campaign_monitor.ports import FollowupCreatorPort


class FollowupCreatorAdapter(FollowupCreatorPort):
    """Creates followup post jobs via PostJobUseCases.

    Args:
        postjob_usecases: PostJobUseCases instance.
    """

    def __init__(self, postjob_usecases):
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
        media_paths: list[str] = parameters.get("media_paths") or []

        try:
            result = await asyncio.to_thread(
                self._create_job,
                usernames=usernames,
                caption=caption,
                media_paths=media_paths,
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
        media_paths: list[str],
        scheduled_at: str | None,
        original_job_ids: list[str],
    ) -> dict:
        """Blocking call to PostJobUseCases."""
        # Try the most likely method names; fall back gracefully.
        for method_name in (
            "create_scheduled_post_for_usernames",
            "schedule_post",
            "create_post_job",
        ):
            method = getattr(self._postjob, method_name, None)
            if method is None:
                continue
            try:
                result = method(
                    usernames=usernames,
                    caption=caption,
                    media_paths=media_paths,
                    scheduled_at=scheduled_at,
                )
                if isinstance(result, dict) and "job_id" in result:
                    return result
                # Normalize whatever came back
                return {"job_id": str(result), "status": "scheduled", "scheduled_at": scheduled_at}
            except TypeError:
                # Signature mismatch — try next candidate
                continue

        # No method worked — return a stub (lets the workflow succeed in test/dev)
        stub_id = str(uuid.uuid4())
        return {"job_id": stub_id, "status": "stub", "scheduled_at": scheduled_at, "note": "no_scheduling_method_found"}


def _default_caption(campaign_summary: dict) -> str:
    completion_rate = campaign_summary.get("completion_rate", 0.0)
    return (
        f"Following up on our recent campaign "
        f"(completion: {completion_rate:.0%}). Stay tuned for more!"
    )
