"""HTTP API adapter package for LangGraph copilot workflows."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.adapters.ai.llm_failure_catalog import LLMFailure, LLMFailureFamily
from app.adapters.ai.provider_catalog import get_provider_spec

from .dependencies import (
    _copilot_lock,
    get_account_recovery_usecase,
    get_campaign_monitor_usecase,
    get_content_pipeline_usecase,
    get_operator_copilot_usecase,
    get_risk_control_usecase,
    is_operator_copilot_enabled,
)
from .endpoints import (
    account_recovery_resume,
    account_recovery_run,
    campaign_monitor_resume,
    campaign_monitor_run,
    content_pipeline_resume,
    content_pipeline_run,
    list_provider_models,
    operator_copilot_resume,
    operator_copilot_run,
    risk_control_resume,
    risk_control_run,
)
from .router import router
from .schemas import (
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

__all__ = [
    "APIRouter",
    "AccountRecoveryResumeRequest",
    "AccountRecoveryRunRequest",
    "BaseModel",
    "CampaignMonitorResumeRequest",
    "CampaignMonitorRunRequest",
    "ContentPipelineResumeRequest",
    "ContentPipelineRunRequest",
    "Depends",
    "Field",
    "GraphChatRequest",
    "GraphResumeRequest",
    "HTTPException",
    "LLMFailure",
    "LLMFailureFamily",
    "Literal",
    "ProviderModelsRequest",
    "RiskControlResumeRequest",
    "RiskControlRunRequest",
    "StreamingResponse",
    "_copilot_lock",
    "account_recovery_resume",
    "account_recovery_run",
    "asyncio",
    "campaign_monitor_resume",
    "campaign_monitor_run",
    "content_pipeline_resume",
    "content_pipeline_run",
    "get_account_recovery_usecase",
    "get_campaign_monitor_usecase",
    "get_content_pipeline_usecase",
    "get_operator_copilot_usecase",
    "get_provider_spec",
    "get_risk_control_usecase",
    "is_operator_copilot_enabled",
    "json",
    "list_provider_models",
    "operator_copilot_resume",
    "operator_copilot_run",
    "os",
    "risk_control_resume",
    "risk_control_run",
    "router",
]
