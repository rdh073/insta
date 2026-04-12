"""Compatibility facade for ai_copilot HTTP transport.

The monolithic transport module has been split into:
- ``schemas.py`` for request contracts
- ``dependencies.py`` for DI wiring and shared helpers
- ``endpoints/*.py`` for domain endpoint handlers
- ``router.py`` for composed router registration

This module preserves historical import paths (``ai_copilot.api``).
"""

from __future__ import annotations

from ai_copilot.dependencies import (
    _account_recovery_lock,
    _build_account_recovery_usecase,
    _build_campaign_monitor_usecase,
    _build_content_pipeline_usecase,
    _build_operator_copilot_usecase,
    _build_risk_control_usecase,
    _campaign_monitor_lock,
    _content_pipeline_lock,
    _copilot_lock,
    _flag,
    _llm_failure_code,
    _risk_control_lock,
    get_account_recovery_usecase,
    get_campaign_monitor_usecase,
    get_content_pipeline_usecase,
    get_operator_copilot_usecase,
    get_risk_control_usecase,
    is_operator_copilot_enabled,
    llm_failure_detail as _llm_failure_detail,
    resolve_content_pipeline_llm_config as _resolve_llm_config,
)
from ai_copilot.endpoints.account_recovery import (
    account_recovery_resume,
    account_recovery_run,
)
from ai_copilot.endpoints.campaign_monitor import (
    campaign_monitor_resume,
    campaign_monitor_run,
)
from ai_copilot.endpoints.content_pipeline import (
    content_pipeline_resume,
    content_pipeline_run,
)
from ai_copilot.endpoints.operator_copilot import (
    list_provider_models,
    operator_copilot_resume,
    operator_copilot_run,
)
from ai_copilot.endpoints.risk_control import risk_control_resume, risk_control_run
from ai_copilot.router import router
from ai_copilot.schemas import (
    AccountRecoveryResumeRequest,
    AccountRecoveryRunRequest,
    CampaignMonitorResumeRequest,
    CampaignMonitorRunRequest,
    ContentPipelineResumeRequest,
    ContentPipelineRunRequest,
    GraphChatRequest,
    GraphResumeRequest,
    ProviderModelsRequest,
    RiskControlResumeRequest,
    RiskControlRunRequest,
)

# Keep historical route ownership metadata stable for introspection tests.
for _endpoint in (
    list_provider_models,
    operator_copilot_run,
    operator_copilot_resume,
    campaign_monitor_run,
    campaign_monitor_resume,
    risk_control_run,
    risk_control_resume,
    account_recovery_run,
    account_recovery_resume,
    content_pipeline_run,
    content_pipeline_resume,
):
    _endpoint.__module__ = __name__

__all__ = [
    "router",
    "_copilot_lock",
    "_campaign_monitor_lock",
    "_risk_control_lock",
    "_account_recovery_lock",
    "_content_pipeline_lock",
    "_flag",
    "_llm_failure_code",
    "_llm_failure_detail",
    "_resolve_llm_config",
    "_build_operator_copilot_usecase",
    "_build_campaign_monitor_usecase",
    "_build_risk_control_usecase",
    "_build_account_recovery_usecase",
    "_build_content_pipeline_usecase",
    "is_operator_copilot_enabled",
    "get_operator_copilot_usecase",
    "get_campaign_monitor_usecase",
    "get_risk_control_usecase",
    "get_account_recovery_usecase",
    "get_content_pipeline_usecase",
    "ProviderModelsRequest",
    "GraphChatRequest",
    "GraphResumeRequest",
    "CampaignMonitorRunRequest",
    "CampaignMonitorResumeRequest",
    "RiskControlRunRequest",
    "RiskControlResumeRequest",
    "AccountRecoveryRunRequest",
    "AccountRecoveryResumeRequest",
    "ContentPipelineRunRequest",
    "ContentPipelineResumeRequest",
    "list_provider_models",
    "operator_copilot_run",
    "operator_copilot_resume",
    "campaign_monitor_run",
    "campaign_monitor_resume",
    "risk_control_run",
    "risk_control_resume",
    "account_recovery_run",
    "account_recovery_resume",
    "content_pipeline_run",
    "content_pipeline_resume",
]
