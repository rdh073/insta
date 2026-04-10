"""HTTP API adapter for operator copilot — transport layer only.

Endpoints:
  POST /api/ai/chat/graph         — start a new operator copilot run
  POST /api/ai/chat/graph/resume  — resume a suspended run after approval

Ownership:
  This module owns: HTTP parsing, response formatting, feature flags, DI wiring.
  This module does NOT own: policy decisions, approval logic, tool classification,
  LLM prompts, graph topology, audit schema.

Dependency direction enforced:
  api.py → RunOperatorCopilotUseCase → graph → ports ← adapters

The DI factory (get_operator_copilot_usecase) wires adapters to the use case.
No business logic here — only HTTP concerns.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.adapters.ai.llm_failure_catalog import LLMFailure, LLMFailureFamily
from app.adapters.ai.provider_catalog import (
    get_provider_spec,
)

router = APIRouter(prefix="/api/ai", tags=["ai-langgraph"])


# ── Feature flags ──────────────────────────────────────────────────────────────


def _flag(env_var: str, default: bool = True) -> bool:
    """Read a boolean feature flag from env."""
    value = os.getenv(env_var, "1" if default else "0").strip().lower()
    return value not in {"0", "false", "no", "off"}


def is_operator_copilot_enabled() -> bool:
    """Feature flag: set ENABLE_OPERATOR_COPILOT=0 to disable.

    Controls both /graph and /graph/resume endpoints.
    """
    return _flag("ENABLE_OPERATOR_COPILOT", default=True)


def _llm_failure_code(family: LLMFailureFamily) -> str:
    if family == LLMFailureFamily.AUTH:
        return "LLM_AUTH_FAILED"
    if family == LLMFailureFamily.RATE_LIMIT:
        return "LLM_RATE_LIMITED"
    if family == LLMFailureFamily.PROVIDER_UNAVAILABLE:
        return "LLM_PROVIDER_UNAVAILABLE"
    if family == LLMFailureFamily.TRANSPORT_MISMATCH:
        return "LLM_PROVIDER_TRANSPORT_UNAVAILABLE"
    return "LLM_INVALID_REQUEST"


def _llm_failure_detail(exc: LLMFailure) -> dict:
    return {
        "code": _llm_failure_code(exc.family),
        "family": exc.family.value,
        "provider": exc.provider,
        "message": exc.message,
    }


# ── Request / Response models ──────────────────────────────────────────────────


class ProviderModelsRequest(BaseModel):
    """Request body for POST /api/ai/providers/models."""

    provider: str
    api_key: str | None = Field(default=None, alias="apiKey")
    provider_base_url: str | None = Field(default=None, alias="providerBaseUrl")

    model_config = {"populate_by_name": True}


class GraphChatRequest(BaseModel):
    """Request body for POST /api/ai/chat/graph."""

    message: str = Field(
        ...,
        min_length=1,
        description="Raw natural language request from the operator.",
    )
    thread_id: str | None = Field(
        default=None,
        alias="threadId",
        description="Optional stable thread id for checkpoint continuity. "
        "Auto-generated if omitted.",
    )
    provider: str | None = Field(
        default=None,
        description="AI provider for this run. Falls back to active DB config, then 'openai'.",
    )
    model: str | None = Field(
        default=None,
        description="Model override for this run. Falls back to active DB config.",
    )
    api_key: str | None = Field(
        default=None,
        alias="apiKey",
        description="API key override for this run. Falls back to active DB config.",
    )
    provider_base_url: str | None = Field(
        default=None,
        alias="providerBaseUrl",
        description="Base URL override for OpenAI-compatible providers.",
    )
    file_name: str | None = Field(
        default=None,
        alias="fileName",
        description="Original filename of an attached file (e.g. proxies.txt).",
    )
    file_content: str | None = Field(
        default=None,
        alias="fileContent",
        description="Plain-text content of the attached file. "
        "Injected into the message as inline context before running the graph.",
    )

    model_config = {"populate_by_name": True}

    def effective_message(self) -> str:
        """Return the message augmented with file content when an attachment is present."""
        if not self.file_content:
            return self.message
        name = self.file_name or "attachment"
        lines = self.file_content.splitlines()
        line_count = len(lines)
        return (
            f"{self.message}\n\n"
            f"--- Attached file: {name} ({line_count} line{'s' if line_count != 1 else ''}) ---\n"
            f"{self.file_content}\n"
            f"---"
        )


class GraphResumeRequest(BaseModel):
    """Request body for POST /api/ai/chat/graph/resume."""

    thread_id: str = Field(
        ...,
        alias="threadId",
        description="Thread id of the suspended run.",
    )
    approval_result: Literal["approved", "rejected", "edited"] = Field(
        ...,
        alias="approvalResult",
        description="Operator decision for the pending approval request.",
    )
    edited_calls: list[dict] | None = Field(
        default=None,
        alias="editedCalls",
        description="Required when approvalResult == 'edited'. "
        "List of modified tool call dicts [{id, name, arguments}, ...].",
    )

    model_config = {"populate_by_name": True}


# ── Dependency injection ───────────────────────────────────────────────────────
# All five factories use an async double-checked-locking singleton pattern.
# @lru_cache cannot be used because AsyncSqliteSaver (needed for await graph.ainvoke())
# requires async initialisation via aiosqlite.connect(), which in turn calls
# asyncio.get_running_loop() — incompatible with a sync factory.

_copilot_lock = asyncio.Lock()
_copilot_instance = None

_campaign_monitor_lock = asyncio.Lock()
_campaign_monitor_instance = None

_risk_control_lock = asyncio.Lock()
_risk_control_instance = None

_account_recovery_lock = asyncio.Lock()
_account_recovery_instance = None

_content_pipeline_lock = asyncio.Lock()
_content_pipeline_instance = None


async def get_operator_copilot_usecase():
    """Wire adapters and return a RunOperatorCopilotUseCase instance (async singleton).

    Dependency direction:
        api (this function) → RunOperatorCopilotUseCase
                            → OperatorCopilotNodes (graph)
                            → ports ← adapters (wired here)
    """
    global _copilot_instance
    if _copilot_instance is not None:
        return _copilot_instance
    async with _copilot_lock:
        if _copilot_instance is None:
            _copilot_instance = await _build_operator_copilot_usecase()
    return _copilot_instance


async def _build_operator_copilot_usecase():
    from langgraph.store.memory import InMemoryStore

    from app.bootstrap.container import create_services
    from app.adapters.ai.checkpoint_factory_adapter import ConfigurableCheckpointFactory
    from ai_copilot.adapters.copilot_memory_adapter import LangGraphCopilotMemoryAdapter
    from ai_copilot.adapters.tool_registry_bridge import ToolRegistryBridgeAdapter
    from ai_copilot.adapters.operator_copilot_approval_adapter import (
        InMemoryOperatorApprovalAdapter,
    )
    from ai_copilot.adapters.operator_copilot_audit_log_adapter import (
        FileOperatorAuditLogAdapter,
    )
    from ai_copilot.application.use_cases.run_operator_copilot import (
        RunOperatorCopilotUseCase,
    )

    services = create_services()

    llm_gateway = services.get("llm_gateway_port")
    if llm_gateway is None:
        raise RuntimeError("Missing llm_gateway_port in container services")

    tool_executor = ToolRegistryBridgeAdapter(services["tool_registry"])
    approval_port = InMemoryOperatorApprovalAdapter()
    audit_log = FileOperatorAuditLogAdapter()
    checkpointer = await ConfigurableCheckpointFactory.from_env().create_async()

    copilot_store = InMemoryStore()
    copilot_memory = LangGraphCopilotMemoryAdapter(copilot_store)

    return RunOperatorCopilotUseCase(
        llm_gateway=llm_gateway,
        tool_executor=tool_executor,
        approval_port=approval_port,
        audit_log=audit_log,
        checkpointer=checkpointer,
        copilot_memory=copilot_memory,
        store=copilot_store,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/providers/models")
async def list_provider_models(request: ProviderModelsRequest) -> dict:
    """Fetch available model IDs from an OpenAI-compatible provider.

    The API key is never persisted — it is used only for this request.
    Only OpenAI-compatible transports support model listing.
    """
    import os

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

    # Resolve LLM config: request body overrides DB config, DB config overrides env vars
    resolved_provider = request.provider
    resolved_model = request.model
    resolved_api_key = request.api_key
    resolved_base_url = request.provider_base_url

    if not resolved_provider or not resolved_api_key:
        try:
            from app.bootstrap.container import create_services

            services = create_services()
            llm_config_uc = services.get("llm_config")
            if llm_config_uc:
                active_config = llm_config_uc.get_active_or_none()
                if active_config:
                    resolved_provider = (
                        resolved_provider or active_config.provider.value
                    )
                    resolved_model = resolved_model or active_config.model
                    resolved_api_key = resolved_api_key or active_config.api_key
                    resolved_base_url = resolved_base_url or active_config.base_url
        except Exception:
            pass  # Fall through to env var defaults in the gateway

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
                raise HTTPException(
                    status_code=422, detail=_llm_failure_detail(exc)
                ) from exc

    async def generate():
        async for event in use_case.run(
            operator_request=request.effective_message(),
            thread_id=request.thread_id,
            provider=resolved_provider or "openai",
            model=resolved_model,
            api_key=resolved_api_key,
            provider_base_url=resolved_base_url,
        ):
            yield f"data: {json.dumps(event)}\n\n"

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
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# =============================================================================
# Campaign Monitor endpoints
# =============================================================================


async def get_campaign_monitor_usecase():
    """Wire and return RunCampaignMonitorUseCase (async singleton)."""
    global _campaign_monitor_instance
    if _campaign_monitor_instance is not None:
        return _campaign_monitor_instance
    async with _campaign_monitor_lock:
        if _campaign_monitor_instance is None:
            _campaign_monitor_instance = await _build_campaign_monitor_usecase()
    return _campaign_monitor_instance


async def _build_campaign_monitor_usecase():
    from app.bootstrap.container import create_services
    from app.adapters.ai.checkpoint_factory_adapter import ConfigurableCheckpointFactory
    from ai_copilot.adapters.job_monitor_adapter import JobMonitorAdapter
    from ai_copilot.adapters.followup_creator_adapter import FollowupCreatorAdapter
    from ai_copilot.application.use_cases.run_campaign_monitor import (
        RunCampaignMonitorUseCase,
    )

    services = create_services()
    postjob_usecases = services["postjobs"]
    account_usecases = services["accounts"]
    insight_usecases = services.get("insight")

    job_monitor = JobMonitorAdapter(
        postjob_usecases=postjob_usecases,
        account_usecases=account_usecases,
        insight_usecases=insight_usecases,
    )
    followup_creator = FollowupCreatorAdapter(postjob_usecases=postjob_usecases)
    checkpointer = await ConfigurableCheckpointFactory.from_env().create_async()

    return RunCampaignMonitorUseCase(
        job_monitor=job_monitor,
        followup_creator=followup_creator,
        checkpointer=checkpointer,
    )


class CampaignMonitorRunRequest(BaseModel):
    job_ids: list[str] = Field(default_factory=list, alias="jobIds")
    lookback_days: int = Field(default=7, alias="lookbackDays")
    request_decision: bool = Field(default=False, alias="requestDecision")
    thread_id: str | None = Field(default=None, alias="threadId")

    model_config = {"populate_by_name": True}


class CampaignMonitorResumeRequest(BaseModel):
    thread_id: str = Field(..., alias="threadId")
    decision: Literal["approve", "skip", "modify"] = "skip"
    parameters: dict | None = None

    model_config = {"populate_by_name": True}


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


# =============================================================================
# Risk Control endpoints
# =============================================================================


async def get_risk_control_usecase():
    global _risk_control_instance
    if _risk_control_instance is not None:
        return _risk_control_instance
    async with _risk_control_lock:
        if _risk_control_instance is None:
            _risk_control_instance = await _build_risk_control_usecase()
    return _risk_control_instance


async def _build_risk_control_usecase():
    from app.bootstrap.container import create_services
    from app.adapters.ai.checkpoint_factory_adapter import ConfigurableCheckpointFactory
    from ai_copilot.adapters.account_signal_adapter import AccountSignalAdapter
    from ai_copilot.adapters.policy_decision_adapter import PolicyDecisionAdapter
    from ai_copilot.adapters.proxy_rotation_adapter import ProxyRotationAdapter
    from ai_copilot.application.use_cases.run_risk_control import RunRiskControlUseCase

    services = create_services()
    account_usecases = services["accounts"]
    logs_usecases = services.get("logs")

    return RunRiskControlUseCase(
        account_signal=AccountSignalAdapter(account_usecases, logs_usecases),
        policy_decision=PolicyDecisionAdapter(account_usecases),
        proxy_rotation=ProxyRotationAdapter(account_usecases),
        checkpointer=await ConfigurableCheckpointFactory.from_env().create_async(),
    )


class RiskControlRunRequest(BaseModel):
    account_id: str = Field(..., alias="accountId")
    thread_id: str | None = Field(default=None, alias="threadId")

    model_config = {"populate_by_name": True}


class RiskControlResumeRequest(BaseModel):
    thread_id: str = Field(..., alias="threadId")
    decision: Literal["approve_policy", "override_policy", "abort"]
    override_policy: str | None = Field(default=None, alias="overridePolicy")
    notes: str | None = None

    model_config = {"populate_by_name": True}


@router.post("/risk-control/run")
async def risk_control_run(
    request: RiskControlRunRequest,
    use_case=Depends(get_risk_control_usecase),
) -> StreamingResponse:
    """Start a risk control assessment for an account. Streams SSE events."""

    async def generate():
        async for event in use_case.run(
            account_id=request.account_id,
            thread_id=request.thread_id,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/risk-control/resume")
async def risk_control_resume(
    request: RiskControlResumeRequest,
    use_case=Depends(get_risk_control_usecase),
) -> StreamingResponse:
    """Resume a risk control run after operator escalation."""

    async def generate():
        async for event in use_case.resume(
            thread_id=request.thread_id,
            decision=request.decision,
            override_policy=request.override_policy,
            notes=request.notes,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# =============================================================================
# Account Recovery endpoints
# =============================================================================


async def get_account_recovery_usecase():
    global _account_recovery_instance
    if _account_recovery_instance is not None:
        return _account_recovery_instance
    async with _account_recovery_lock:
        if _account_recovery_instance is None:
            _account_recovery_instance = await _build_account_recovery_usecase()
    return _account_recovery_instance


async def _build_account_recovery_usecase():
    from app.bootstrap.container import create_services
    from app.adapters.ai.checkpoint_factory_adapter import ConfigurableCheckpointFactory
    from ai_copilot.adapters.account_diagnostics_adapter import (
        AccountDiagnosticsAdapter,
    )
    from ai_copilot.adapters.recovery_executor_adapter import RecoveryExecutorAdapter
    from ai_copilot.application.use_cases.run_account_recovery import (
        RunAccountRecoveryUseCase,
    )

    services = create_services()
    account_usecases = services["accounts"]
    connectivity_usecases = services.get("account_connectivity")

    return RunAccountRecoveryUseCase(
        diagnostics=AccountDiagnosticsAdapter(account_usecases, connectivity_usecases),
        executor=RecoveryExecutorAdapter(account_usecases),
        checkpointer=await ConfigurableCheckpointFactory.from_env().create_async(),
    )


class AccountRecoveryRunRequest(BaseModel):
    account_id: str = Field(..., alias="accountId")
    username: str = ""
    thread_id: str | None = Field(default=None, alias="threadId")

    model_config = {"populate_by_name": True}


class AccountRecoveryResumeRequest(BaseModel):
    thread_id: str = Field(..., alias="threadId")
    decision: Literal["provide_2fa", "approve_proxy_swap", "abort"]
    two_fa_code: str | None = Field(default=None, alias="twoFaCode")
    proxy: str | None = None

    model_config = {"populate_by_name": True}


@router.post("/account-recovery/run")
async def account_recovery_run(
    request: AccountRecoveryRunRequest,
    use_case=Depends(get_account_recovery_usecase),
) -> StreamingResponse:
    """Start an account recovery workflow. Streams SSE events."""

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


# =============================================================================
# Content Pipeline endpoints
# =============================================================================


async def get_content_pipeline_usecase():
    global _content_pipeline_instance
    if _content_pipeline_instance is not None:
        return _content_pipeline_instance
    async with _content_pipeline_lock:
        if _content_pipeline_instance is None:
            _content_pipeline_instance = await _build_content_pipeline_usecase()
    return _content_pipeline_instance


async def _build_content_pipeline_usecase():
    from app.bootstrap.container import create_services
    from app.adapters.ai.checkpoint_factory_adapter import ConfigurableCheckpointFactory
    from ai_copilot.adapters.caption_generator_adapter import CaptionGeneratorAdapter
    from ai_copilot.adapters.caption_validator_adapter import CaptionValidatorAdapter
    from ai_copilot.adapters.post_scheduler_adapter import PostSchedulerAdapter
    from ai_copilot.application.use_cases.run_content_pipeline import (
        RunContentPipelineUseCase,
    )

    services = create_services()
    llm_gateway = services.get("llm_gateway_port")
    postjob_usecases = services["postjobs"]

    return RunContentPipelineUseCase(
        caption_generator=CaptionGeneratorAdapter(llm_gateway),
        caption_validator=CaptionValidatorAdapter(),
        post_scheduler=PostSchedulerAdapter(postjob_usecases),
        account_usecases=services["accounts"],
        checkpointer=await ConfigurableCheckpointFactory.from_env().create_async(),
    )


class ContentPipelineRunRequest(BaseModel):
    campaign_brief: str = Field(..., alias="campaignBrief")
    target_usernames: list[str] = Field(default_factory=list, alias="targetUsernames")
    media_refs: list[str] = Field(default_factory=list, alias="mediaRefs")
    scheduled_at: str | None = Field(default=None, alias="scheduledAt")
    thread_id: str | None = Field(default=None, alias="threadId")
    max_revisions: int = Field(default=3, alias="maxRevisions")
    provider: str | None = None
    model: str | None = None
    api_key: str | None = Field(default=None, alias="apiKey")
    provider_base_url: str | None = Field(default=None, alias="providerBaseUrl")

    model_config = {"populate_by_name": True}


class ContentPipelineResumeRequest(BaseModel):
    thread_id: str = Field(..., alias="threadId")
    decision: Literal["approved", "rejected", "edited"]
    edited_caption: str | None = Field(default=None, alias="editedCaption")
    reason: str | None = None

    model_config = {"populate_by_name": True}


def _resolve_llm_config(
    provider: str | None, model: str | None, api_key: str | None
) -> tuple[str, str | None, str | None]:
    """Resolve provider/model/api_key: request body → DB config → fallback 'openai'."""
    if not provider or not api_key:
        try:
            from app.bootstrap.container import create_services

            _svc = create_services()
            llm_config_uc = _svc.get("llm_config")
            if llm_config_uc:
                active = llm_config_uc.get_active_or_none()
                if active:
                    provider = provider or active.provider.value
                    model = model or active.model
                    api_key = api_key or active.api_key
        except Exception:
            pass
    return provider or "openai", model, api_key


@router.post("/content-pipeline/run")
async def content_pipeline_run(
    request: ContentPipelineRunRequest,
) -> StreamingResponse:
    """Start a content pipeline run. Streams SSE events."""
    from app.bootstrap.container import create_services
    from app.adapters.ai.checkpoint_factory_adapter import ConfigurableCheckpointFactory
    from ai_copilot.adapters.caption_generator_adapter import CaptionGeneratorAdapter
    from ai_copilot.adapters.caption_validator_adapter import CaptionValidatorAdapter
    from ai_copilot.adapters.post_scheduler_adapter import PostSchedulerAdapter
    from ai_copilot.application.use_cases.run_content_pipeline import (
        RunContentPipelineUseCase,
    )

    services = create_services()
    llm_gateway = services.get("llm_gateway_port")

    resolved_provider, resolved_model, resolved_api_key = _resolve_llm_config(
        request.provider, request.model, request.api_key
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
        checkpointer=ConfigurableCheckpointFactory.from_env().create(),
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
