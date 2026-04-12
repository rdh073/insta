"""Campaign monitor HTTP endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.adapters.http.streaming import sse_response
from ai_copilot.dependencies import get_campaign_monitor_usecase
from ai_copilot.schemas import CampaignMonitorResumeRequest, CampaignMonitorRunRequest

router = APIRouter(tags=["ai-langgraph"])
logger = logging.getLogger(__name__)


@router.post("/campaign-monitor/run")
async def campaign_monitor_run(
    request: CampaignMonitorRunRequest,
    use_case=Depends(get_campaign_monitor_usecase),
) -> StreamingResponse:
    """Start a campaign monitor run and stream SSE events."""

    return sse_response(
        use_case.run(
            thread_id=request.thread_id,
            job_ids=request.job_ids,
            lookback_days=request.lookback_days,
            request_decision=request.request_decision,
        ),
        logger=logger,
    )


@router.post("/campaign-monitor/resume")
async def campaign_monitor_resume(
    request: CampaignMonitorResumeRequest,
    use_case=Depends(get_campaign_monitor_usecase),
) -> StreamingResponse:
    """Resume a campaign monitor run after operator decision interrupt."""

    return sse_response(
        use_case.resume(
            thread_id=request.thread_id,
            decision=request.decision,
            parameters=request.parameters,
        ),
        logger=logger,
    )
