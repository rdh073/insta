from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..dependencies import (
    build_content_pipeline_run_usecase,
    get_content_pipeline_usecase,
)
from ..schemas import ContentPipelineResumeRequest, ContentPipelineRunRequest


router = APIRouter()


@router.post("/content-pipeline/run")
async def content_pipeline_run(
    request: ContentPipelineRunRequest,
) -> StreamingResponse:
    """Start a content pipeline run. Streams SSE events."""
    use_case = await build_content_pipeline_run_usecase(
        provider=request.provider,
        model=request.model,
        api_key=request.api_key,
        provider_base_url=request.provider_base_url,
    )

    async def generate():
        async for event in use_case.run(
            campaign_brief=request.campaign_brief,
            thread_id=request.thread_id,
            media_refs=request.media_refs,
            target_usernames=request.target_usernames,
            scheduled_at=request.scheduled_at,
            max_revisions=request.max_revisions,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/content-pipeline/resume")
async def content_pipeline_resume(
    request: ContentPipelineResumeRequest,
    use_case=Depends(get_content_pipeline_usecase),
) -> StreamingResponse:
    """Resume a content pipeline after operator approval/edit/rejection."""

    async def generate():
        async for event in use_case.resume(
            thread_id=request.thread_id,
            decision=request.decision,
            edited_caption=request.edited_caption,
            reason=request.reason,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


content_pipeline_run.__module__ = "ai_copilot.api"
content_pipeline_resume.__module__ = "ai_copilot.api"
