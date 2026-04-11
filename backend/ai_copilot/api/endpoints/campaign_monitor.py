from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..dependencies import get_campaign_monitor_usecase
from ..schemas import CampaignMonitorResumeRequest, CampaignMonitorRunRequest


router = APIRouter()


@router.post("/campaign-monitor/run")
async def campaign_monitor_run(
    request: CampaignMonitorRunRequest,
    use_case=Depends(get_campaign_monitor_usecase),
) -> StreamingResponse:
    """Start a campaign monitor run. Streams SSE events."""

    async def generate():
        async for event in use_case.run(
            thread_id=request.thread_id,
            job_ids=request.job_ids,
            lookback_days=request.lookback_days,
            request_decision=request.request_decision,
        ):
            yield f"data: {json.dumps(event)}\\n\\n"

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
            yield f"data: {json.dumps(event)}\\n\\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


campaign_monitor_run.__module__ = "ai_copilot.api"
campaign_monitor_resume.__module__ = "ai_copilot.api"
