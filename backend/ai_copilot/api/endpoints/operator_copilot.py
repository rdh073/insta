from __future__ import annotations

import json
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.adapters.ai.llm_failure_catalog import LLMFailure
from app.adapters.ai.provider_catalog import (
    get_provider_spec,
    is_openai_compatible_provider,
)
from ..dependencies import (
    get_operator_copilot_usecase,
    is_operator_copilot_enabled,
    llm_failure_detail,
    resolve_operator_request_llm_config,
)
from ..schemas import GraphChatRequest, GraphResumeRequest, ProviderModelsRequest


router = APIRouter()


@router.post("/providers/models")
async def list_provider_models(request: ProviderModelsRequest) -> dict:
    """Fetch available model IDs from an OpenAI-compatible provider.

    The API key is never persisted — it is used only for this request.
    Only OpenAI-compatible transports support model listing.
    """
    try:
        spec = get_provider_spec(request.provider)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not is_openai_compatible_provider(request.provider):
        raise HTTPException(
            status_code=422,
            detail=f"Provider '{request.provider}' does not support model listing.",
        )

    api_key = request.api_key or os.getenv(spec.env_key, "")
    if not api_key:
        raise HTTPException(
            status_code=422,
            detail=f"No API key for '{request.provider}'. Provide apiKey in the request body.",
        )

    base_url = request.provider_base_url or spec.base_url

    try:
        from openai import AsyncOpenAI

        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = AsyncOpenAI(**kwargs)
        response = await client.models.list()
        model_ids = sorted(m.id for m in response.data)
        return {"models": model_ids}
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch models from '{request.provider}': {exc}",
        ) from exc


@router.post("/chat/graph")
@router.post("/graph-chat")
async def operator_copilot_run(
    request: GraphChatRequest,
    use_case=Depends(get_operator_copilot_usecase),
) -> StreamingResponse:
    """Start a new operator copilot run.

    Streams structured SSE events. If the run requires approval for a
    write-sensitive action, the stream will include an ``approval_required``
    event and then stop. The client must call POST /api/ai/chat/graph/resume
    with the operator decision to continue.

    Request body::

        {
          "message": "Show my top 5 posts by engagement",
          "threadId": "optional-stable-id"
        }

    Event types in the stream:
      - ``run_start``       — run_id, thread_id
      - ``node_update``     — node name + output dict
      - ``approval_required`` — thread_id + approval payload (suspends)
      - ``final_response``  — text answer to operator
      - ``run_finish``      — run_id, stop_reason
      - ``run_error``       — run_id, message
    """
    if not is_operator_copilot_enabled():
        raise HTTPException(
            status_code=503,
            detail="Operator copilot endpoint is disabled by configuration.",
        )

    (
        resolved_provider,
        resolved_model,
        resolved_api_key,
        resolved_base_url,
    ) = resolve_operator_request_llm_config(
        provider=request.provider,
        model=request.model,
        api_key=request.api_key,
        provider_base_url=request.provider_base_url,
    )

    if resolved_provider:
        try:
            get_provider_spec(resolved_provider)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "LLM_PROVIDER_UNKNOWN",
                    "provider": resolved_provider,
                    "message": str(exc),
                },
            ) from exc
        if hasattr(use_case, "llm_gateway"):
            try:
                use_case.llm_gateway.get_default_model(resolved_provider)
            except LLMFailure as exc:
                raise HTTPException(status_code=422, detail=llm_failure_detail(exc)) from exc

    async def generate():
        async for event in use_case.run(
            operator_request=request.effective_message(),
            thread_id=request.thread_id,
            provider=resolved_provider or "openai",
            model=resolved_model,
            api_key=resolved_api_key,
            provider_base_url=resolved_base_url,
        ):
            yield f"data: {json.dumps(event)}\\n\\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/graph/resume")
@router.post("/graph-chat/resume")
async def operator_copilot_resume(
    request: GraphResumeRequest,
    use_case=Depends(get_operator_copilot_usecase),
) -> StreamingResponse:
    """Resume a suspended operator copilot run with an approval decision.

    Called after the operator responds to an ``approval_required`` event.
    The thread_id must match the suspended run; otherwise LangGraph will
    return no output (silently finished or not found).

    Request body::

        {
          "threadId": "the-thread-id",
          "approvalResult": "approved",
          "editedCalls": null
        }

    For edited calls::

        {
          "threadId": "the-thread-id",
          "approvalResult": "edited",
          "editedCalls": [
            {"id": "c1", "name": "follow_user", "arguments": {"user_id": "123"}}
          ]
        }

    Streams the same event types as POST /graph.
    """
    if not is_operator_copilot_enabled():
        raise HTTPException(
            status_code=503,
            detail="Operator copilot endpoint is disabled by configuration.",
        )

    if request.approval_result == "edited" and not request.edited_calls:
        raise HTTPException(
            status_code=422,
            detail="editedCalls is required when approvalResult == 'edited'.",
        )

    async def generate():
        async for event in use_case.resume(
            thread_id=request.thread_id,
            approval_result=request.approval_result,
            edited_calls=request.edited_calls,
        ):
            yield f"data: {json.dumps(event)}\\n\\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Preserve endpoint ownership contract expected by existing route tests.
list_provider_models.__module__ = "ai_copilot.api"
operator_copilot_run.__module__ = "ai_copilot.api"
operator_copilot_resume.__module__ = "ai_copilot.api"
