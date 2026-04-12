"""Campaign monitor HTTP endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ai_copilot.dependencies import get_campaign_monitor_usecase
from ai_copilot.schemas import CampaignMonitorResumeRequest, CampaignMonitorRunRequest

router = APIRouter(tags=["ai-langgraph"])


@router.post("/campaign-monitor/run")
async def campaign_monitor_run(
    request: CampaignMonitorRunRequest,
    use_case=Depends(get_campaign_monitor_usecase),
) -> StreamingResponse:
    """Start a campaign monitor run and stream SSE events."""

    async def generate():
        async for event in use_case.run(
            thread_id=request.thread_id,
            job_ids=request.job_ids,
            lookback_days=request.lookback_days,
            request_decision=request.request_decision,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/campaign-monitor/resume")
async def campaign_monitor_resume(
    request: CampaignMonitorResumeRequest,
    use_case=Depends(get_campaign_monitor_usecase),
) -> StreamingResponse:
    """Resume a campaign monitor run after operator decision interrupt."""

    async def generate():
        async for event in use_case.resume(
            thread_id=request.thread_id,
            decision=request.decision,
            parameters=request.parameters,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

