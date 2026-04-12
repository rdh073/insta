"""HTTP transport schemas for ai_copilot endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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
        """Return message augmented with file content when an attachment is present."""
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

