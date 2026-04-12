"""Content pipeline HTTP endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ai_copilot.dependencies import (
    get_content_pipeline_usecase,
    resolve_content_pipeline_llm_config,
)
from ai_copilot.schemas import ContentPipelineResumeRequest, ContentPipelineRunRequest

router = APIRouter(tags=["ai-langgraph"])


@router.post("/content-pipeline/run")
async def content_pipeline_run(
    request: ContentPipelineRunRequest,
) -> StreamingResponse:
    """Start a content pipeline run and stream SSE events."""
    from app.adapters.ai.checkpoint_factory_adapter import ConfigurableCheckpointFactory
    from app.bootstrap.container import create_services
    from ai_copilot.adapters.caption_generator_adapter import CaptionGeneratorAdapter
    from ai_copilot.adapters.caption_validator_adapter import CaptionValidatorAdapter
    from ai_copilot.adapters.post_scheduler_adapter import PostSchedulerAdapter
    from ai_copilot.application.use_cases.run_content_pipeline import (
        RunContentPipelineUseCase,
    )

    services = create_services()
    llm_gateway = services.get("llm_gateway_port")

    resolved_provider, resolved_model, resolved_api_key = resolve_content_pipeline_llm_config(
        provider=request.provider,
        model=request.model,
        api_key=request.api_key,
    )

    use_case = RunContentPipelineUseCase(
        caption_generator=CaptionGeneratorAdapter(
            llm_gateway,
            provider=resolved_provider,
            model=resolved_model,
            api_key=resolved_api_key,
            provider_base_url=request.provider_base_url,
        ),
        caption_validator=CaptionValidatorAdapter(),
        post_scheduler=PostSchedulerAdapter(services["postjobs"]),
        account_usecases=services["accounts"],
        checkpointer=await ConfigurableCheckpointFactory.from_env().create_async(),
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

