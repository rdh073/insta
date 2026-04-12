"""Operator copilot HTTP endpoints."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.adapters.ai.llm_failure_catalog import LLMFailure
from app.adapters.ai.provider_catalog import get_provider_spec
from app.adapters.http.streaming import sse_response
from ai_copilot.dependencies import (
    get_operator_copilot_usecase,
    is_operator_copilot_enabled,
    llm_failure_detail,
    resolve_operator_llm_config,
)
from ai_copilot.schemas import GraphChatRequest, GraphResumeRequest, ProviderModelsRequest

router = APIRouter(tags=["ai-langgraph"])
logger = logging.getLogger(__name__)


@router.post("/providers/models")
async def list_provider_models(request: ProviderModelsRequest) -> dict:
    """Fetch available model IDs from an OpenAI-compatible provider."""
    from app.adapters.ai.provider_catalog import (
        get_provider_spec,
        is_openai_compatible_provider,
    )

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
    """Start a new operator copilot run and stream SSE events."""
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
    ) = resolve_operator_llm_config(
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

    return sse_response(
        use_case.run(
            operator_request=request.effective_message(),
            thread_id=request.thread_id,
            provider=resolved_provider or "openai",
            model=resolved_model,
            api_key=resolved_api_key,
            provider_base_url=resolved_base_url,
        ),
        logger=logger,
    )


@router.post("/chat/graph/resume")
@router.post("/graph-chat/resume")
async def operator_copilot_resume(
    request: GraphResumeRequest,
    use_case=Depends(get_operator_copilot_usecase),
) -> StreamingResponse:
    """Resume a suspended operator copilot run with an approval decision."""
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

    return sse_response(
        use_case.resume(
            thread_id=request.thread_id,
            approval_result=request.approval_result,
            edited_calls=request.edited_calls,
        ),
        logger=logger,
    )
