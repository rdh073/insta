"""PostSchedulerAdapter — wraps PostJobUseCases to schedule content."""

from __future__ import annotations

import asyncio
import uuid

from ai_copilot.application.content_pipeline.ports import PostSchedulerPort


class PostSchedulerAdapter(PostSchedulerPort):
    def __init__(self, postjob_usecases):
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
                    media_paths=media_refs,
                    scheduled_at=scheduled_at,
                )
                if isinstance(result, dict) and "job_id" in result:
                    return result
                return {"job_id": str(result), "status": "scheduled", "scheduled_at": scheduled_at}
            except TypeError:
                continue

        stub_id = str(uuid.uuid4())
        return {"job_id": stub_id, "status": "stub", "scheduled_at": scheduled_at}
