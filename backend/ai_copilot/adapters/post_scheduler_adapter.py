"""PostSchedulerAdapter — wraps PostJobUseCases to schedule content."""

from __future__ import annotations

import asyncio

from ai_copilot.adapters.post_job_scheduler_contract import PostJobSchedulerPort
from ai_copilot.application.content_pipeline.ports import PostSchedulerPort


class PostSchedulerAdapter(PostSchedulerPort):
    def __init__(self, postjob_usecases: PostJobSchedulerPort):
        self._postjob = postjob_usecases

    async def schedule(
        self,
        usernames: list[str],
        caption: str,
        media_refs: list[str],
        scheduled_at: str | None = None,
    ) -> dict:
        try:
            result = await asyncio.to_thread(
                self._call_schedule,
                usernames=usernames,
                caption=caption,
                media_refs=media_refs,
                scheduled_at=scheduled_at,
            )
            return result
        except Exception as exc:
            raise RuntimeError(f"PostSchedulerAdapter.schedule failed: {exc}") from exc

    def _call_schedule(self, usernames, caption, media_refs, scheduled_at):
        _ = media_refs
        return self._postjob.create_scheduled_post_for_usernames(
            usernames=usernames,
            caption=caption,
            scheduled_at=scheduled_at,
        )
