"""Account recovery HTTP endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ai_copilot.dependencies import get_account_recovery_usecase
from ai_copilot.schemas import AccountRecoveryResumeRequest, AccountRecoveryRunRequest

router = APIRouter(tags=["ai-langgraph"])


@router.post("/account-recovery/run")
async def account_recovery_run(
    request: AccountRecoveryRunRequest,
    use_case=Depends(get_account_recovery_usecase),
) -> StreamingResponse:
    """Start an account recovery workflow and stream SSE events."""

    async def generate():
        async for event in use_case.run(
            account_id=request.account_id,
            username=request.username,
            thread_id=request.thread_id,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/account-recovery/resume")
async def account_recovery_resume(
    request: AccountRecoveryResumeRequest,
    use_case=Depends(get_account_recovery_usecase),
) -> StreamingResponse:
    """Resume an account recovery run after 2FA or proxy approval."""

    async def generate():
        async for event in use_case.resume(
            thread_id=request.thread_id,
            decision=request.decision,
            two_fa_code=request.two_fa_code,
            proxy=request.proxy,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

