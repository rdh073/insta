from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.adapters.ai.provider_catalog import is_provider_enabled, provider_feature_flag_key


class LLMConfigCreate(BaseModel):
    label: str = Field(..., description="Human-readable name, e.g. 'My ChatGPT Plus'")
    provider: str = Field(
        ...,
        description=(
            "Provider: openai, gemini, deepseek, antigravity, openai_compatible, "
            "openai_codex, claude_code"
        ),
    )
    api_key: str = Field(default="", description="API key for the provider (empty for OAuth/no-key providers)")
    model: str = Field(default="", description="Model name, e.g. 'gpt-4o-mini'")
    base_url: Optional[str] = Field(None, description="Base URL override (for openai_compatible)")
    activate: bool = Field(False, description="Set as active config immediately")


class LLMConfigUpdate(BaseModel):
    label: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None


class LLMConfigResponse(BaseModel):
    id: str
    label: str
    provider: str
    api_key_masked: str = Field(..., description="Masked API key (last 4 chars only)")
    model: str
    base_url: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_entity(cls, config) -> "LLMConfigResponse":
        return cls(
            id=str(config.id),
            label=config.label,
            provider=config.provider.value,
            api_key_masked=config.masked_api_key(),
            model=config.model,
            base_url=config.base_url,
            is_active=config.is_active,
            created_at=config.created_at.isoformat(),
            updated_at=config.updated_at.isoformat(),
        )


class ProviderSettingsEntry(BaseModel):
    """Settings for a single provider in the bulk provider-settings endpoint."""

    api_key: str = Field(default="", description="API key (empty for OAuth/no-key providers)")
    model: str = Field(default="", description="Model name")
    base_url: Optional[str] = Field(None, description="Base URL override")


class ProviderSettingsRequest(BaseModel):
    """Bulk provider settings payload: provider -> settings map."""

    settings: dict[str, ProviderSettingsEntry]


class ProviderCapabilityResponse(BaseModel):
    provider: str
    status: str
    transport: str
    default_model: str
    enabled: bool
    feature_flag: str | None = None
    requires_oauth: bool
    supports_base_url_override: bool

    @classmethod
    def from_spec(cls, provider: str, spec) -> "ProviderCapabilityResponse":
        flag_key = provider_feature_flag_key(provider)
        return cls(
            provider=provider,
            status=spec.status,
            transport=spec.transport,
            default_model=spec.default_model,
            enabled=is_provider_enabled(provider),
            feature_flag=flag_key,
            requires_oauth=spec.transport in {"codex_oauth", "anthropic_messages"},
            supports_base_url_override=spec.transport == "openai_compatible",
        )


class ProviderOAuthAuthorizeResponse(BaseModel):
    provider: str
    authorization_url: str


class ProviderOAuthAuthorizeRequest(BaseModel):
    redirect_uri: str | None = Field(
        default=None,
        alias="redirectUri",
        description="Frontend callback/status page to redirect to after backend completes OAuth.",
    )

    model_config = {"populate_by_name": True}


class OllamaModel(BaseModel):
    id: str
    owned_by: str = Field(default="library")


class OllamaModelsResponse(BaseModel):
    base_url: str
    models: list[OllamaModel]


class OllamaHealthResponse(BaseModel):
    ok: bool
    base_url: str
    model_count: int
    latency_ms: int


class OAuthExchangeRequest(BaseModel):
    """Frontend sends code + state captured from the OAuth redirect.

    Accepted formats for the ``code`` field:
    - Plain auth code:            ``abc123``
    - Anthropic paste format:     ``{auth_code}#{state}``
    - Full redirect URL:          ``http://localhost:1455/auth/callback?code=abc&state=xyz``
    - Query string only:          ``code=abc&state=xyz``

    When a full redirect URL or query string is detected, ``code`` and ``state``
    are extracted automatically so the user can paste the address-bar URL directly.
    ``state`` from the body is used as fallback when not present in the pasted value.
    """

    code: str
    state: str
