"""Risk control HTTP endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.adapters.http.streaming import sse_response
from ai_copilot.dependencies import get_risk_control_usecase
from ai_copilot.schemas import RiskControlResumeRequest, RiskControlRunRequest

router = APIRouter(tags=["ai-langgraph"])
logger = logging.getLogger(__name__)


@router.post("/risk-control/run")
async def risk_control_run(
    request: RiskControlRunRequest,
    use_case=Depends(get_risk_control_usecase),
) -> StreamingResponse:
    """Start a risk control assessment and stream SSE events."""

    return sse_response(
        use_case.run(
            account_id=request.account_id,
            thread_id=request.thread_id,
        ),
        logger=logger,
    )


@router.post("/risk-control/resume")
async def risk_control_resume(
    request: RiskControlResumeRequest,
    use_case=Depends(get_risk_control_usecase),
) -> StreamingResponse:
    """Resume a risk control run after operator escalation."""

    return sse_response(
        use_case.resume(
            thread_id=request.thread_id,
            decision=request.decision,
            override_policy=request.override_policy,
            notes=request.notes,
        ),
        logger=logger,
    )
