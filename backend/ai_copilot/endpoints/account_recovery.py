"""Account recovery HTTP endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.adapters.http.streaming import sse_response
from ai_copilot.dependencies import get_account_recovery_usecase
from ai_copilot.schemas import AccountRecoveryResumeRequest, AccountRecoveryRunRequest

router = APIRouter(tags=["ai-langgraph"])
logger = logging.getLogger(__name__)


@router.post("/account-recovery/run")
async def account_recovery_run(
    request: AccountRecoveryRunRequest,
    use_case=Depends(get_account_recovery_usecase),
) -> StreamingResponse:
    """Start an account recovery workflow and stream SSE events."""

    return sse_response(
        use_case.run(
            account_id=request.account_id,
            username=request.username,
            thread_id=request.thread_id,
        ),
        logger=logger,
    )


@router.post("/account-recovery/resume")
async def account_recovery_resume(
    request: AccountRecoveryResumeRequest,
    use_case=Depends(get_account_recovery_usecase),
) -> StreamingResponse:
    """Resume an account recovery run after 2FA or proxy approval."""

    return sse_response(
        use_case.resume(
            thread_id=request.thread_id,
            decision=request.decision,
            two_fa_code=request.two_fa_code,
            proxy=request.proxy,
        ),
        logger=logger,
    )
