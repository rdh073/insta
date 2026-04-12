"""Dependency wiring and shared transport helpers for ai_copilot HTTP adapters."""

from __future__ import annotations

import asyncio
import os

from app.adapters.ai.llm_failure_catalog import LLMFailure, LLMFailureFamily

# All factories use async double-checked-locking singleton patterns.
# @lru_cache cannot be used because AsyncSqliteSaver requires async initialization.
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


def _flag(env_var: str, default: bool = True) -> bool:
    """Read a boolean feature flag from environment."""
    value = os.getenv(env_var, "1" if default else "0").strip().lower()
    return value not in {"0", "false", "no", "off"}


def is_operator_copilot_enabled() -> bool:
    """Feature flag for /graph and /graph/resume endpoints."""
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


def llm_failure_detail(exc: LLMFailure) -> dict:
    return {
        "code": _llm_failure_code(exc.family),
        "family": exc.family.value,
        "provider": exc.provider,
        "message": exc.message,
    }


def resolve_operator_llm_config(
    provider: str | None,
    model: str | None,
    api_key: str | None,
    provider_base_url: str | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Resolve request LLM config with DB fallback.

    Order: request body → active DB config → environment fallback in gateway.
    """
    resolved_provider = provider
    resolved_model = model
    resolved_api_key = api_key
    resolved_base_url = provider_base_url

    if not resolved_provider or not resolved_api_key:
        try:
            from app.bootstrap.container import create_services

            services = create_services()
            llm_config_uc = services.get("llm_config")
            if llm_config_uc:
                active_config = llm_config_uc.get_active_or_none()
                if active_config:
                    resolved_provider = resolved_provider or active_config.provider.value
                    resolved_model = resolved_model or active_config.model
                    resolved_api_key = resolved_api_key or active_config.api_key
                    resolved_base_url = resolved_base_url or active_config.base_url
        except Exception:
            pass

    return resolved_provider, resolved_model, resolved_api_key, resolved_base_url


def resolve_content_pipeline_llm_config(
    provider: str | None,
    model: str | None,
    api_key: str | None,
) -> tuple[str, str | None, str | None]:
    """Resolve provider/model/api key with DB fallback and openai default."""
    resolved_provider = provider
    resolved_model = model
    resolved_api_key = api_key

    if not resolved_provider or not resolved_api_key:
        try:
            from app.bootstrap.container import create_services

            services = create_services()
            llm_config_uc = services.get("llm_config")
            if llm_config_uc:
                active = llm_config_uc.get_active_or_none()
                if active:
                    resolved_provider = resolved_provider or active.provider.value
                    resolved_model = resolved_model or active.model
                    resolved_api_key = resolved_api_key or active.api_key
        except Exception:
            pass

    return resolved_provider or "openai", resolved_model, resolved_api_key


async def get_operator_copilot_usecase():
    """Wire adapters and return RunOperatorCopilotUseCase (async singleton)."""
    global _copilot_instance
    if _copilot_instance is not None:
        return _copilot_instance
    async with _copilot_lock:
        if _copilot_instance is None:
            _copilot_instance = await _build_operator_copilot_usecase()
    return _copilot_instance


async def _build_operator_copilot_usecase():
    from langgraph.store.memory import InMemoryStore

    from app.adapters.ai.checkpoint_factory_adapter import ConfigurableCheckpointFactory
    from app.bootstrap.container import create_services
    from ai_copilot.adapters.copilot_memory_adapter import LangGraphCopilotMemoryAdapter
    from ai_copilot.adapters.operator_copilot_approval_adapter import (
        InMemoryOperatorApprovalAdapter,
    )
    from ai_copilot.adapters.operator_copilot_audit_log_adapter import (
        FileOperatorAuditLogAdapter,
    )
    from ai_copilot.adapters.tool_registry_bridge import ToolRegistryBridgeAdapter
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
    from app.adapters.ai.checkpoint_factory_adapter import ConfigurableCheckpointFactory
    from app.bootstrap.container import create_services
    from ai_copilot.adapters.followup_creator_adapter import FollowupCreatorAdapter
    from ai_copilot.adapters.job_monitor_adapter import JobMonitorAdapter
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


async def get_risk_control_usecase():
    global _risk_control_instance
    if _risk_control_instance is not None:
        return _risk_control_instance
    async with _risk_control_lock:
        if _risk_control_instance is None:
            _risk_control_instance = await _build_risk_control_usecase()
    return _risk_control_instance


async def _build_risk_control_usecase():
    from app.adapters.ai.checkpoint_factory_adapter import ConfigurableCheckpointFactory
    from app.bootstrap.container import create_services
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


async def get_account_recovery_usecase():
    global _account_recovery_instance
    if _account_recovery_instance is not None:
        return _account_recovery_instance
    async with _account_recovery_lock:
        if _account_recovery_instance is None:
            _account_recovery_instance = await _build_account_recovery_usecase()
    return _account_recovery_instance


async def _build_account_recovery_usecase():
    from app.adapters.ai.checkpoint_factory_adapter import ConfigurableCheckpointFactory
    from app.bootstrap.container import create_services
    from ai_copilot.adapters.account_diagnostics_adapter import AccountDiagnosticsAdapter
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


async def get_content_pipeline_usecase():
    global _content_pipeline_instance
    if _content_pipeline_instance is not None:
        return _content_pipeline_instance
    async with _content_pipeline_lock:
        if _content_pipeline_instance is None:
            _content_pipeline_instance = await _build_content_pipeline_usecase()
    return _content_pipeline_instance


async def _build_content_pipeline_usecase():
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
    postjob_usecases = services["postjobs"]

    return RunContentPipelineUseCase(
        caption_generator=CaptionGeneratorAdapter(llm_gateway),
        caption_validator=CaptionValidatorAdapter(),
        post_scheduler=PostSchedulerAdapter(postjob_usecases),
        account_usecases=services["accounts"],
        checkpointer=await ConfigurableCheckpointFactory.from_env().create_async(),
    )

