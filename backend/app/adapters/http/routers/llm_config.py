"""HTTP router for LLM configuration management and dashboard auth.

Endpoints:
  POST /api/dashboard/auth/login       — unprotected, returns JWT
  GET    /api/dashboard/llm-configs    — list (api_key masked)
  POST   /api/dashboard/llm-configs    — create
  PUT    /api/dashboard/llm-configs/{id} — update
  DELETE /api/dashboard/llm-configs/{id} — 204
  POST   /api/dashboard/llm-configs/{id}/activate — set active

Authentication: Optional Bearer token when ENABLE_DASHBOARD_AUTH=true.
The api_key field is NEVER returned in full. Only masked form is exposed.
"""

from __future__ import annotations

import os
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256
import hmac
import json
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.adapters.ai.anthropic_oauth_client import AnthropicOAuthClient
from app.adapters.ai.codex_oauth_client import CodexOAuthClient
from app.adapters.ai.provider_catalog import PROVIDER_SPECS, provider_feature_flag_key, is_provider_enabled
from app.adapters.http.dependencies import get_oauth_token_store, get_services

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


def get_auth_usecases():
    """Get dashboard auth use cases from container."""
    services = get_services()
    return services.get("dashboard_auth")


def get_llm_config_usecases():
    """Get LLM config use cases from container."""
    services = get_services()
    return services.get("llm_config")


async def require_admin_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    auth_usecases=Depends(get_auth_usecases),
) -> None:
    """FastAPI dependency: validate Bearer token.

    Raises:
        HTTPException 401: If no token or invalid/expired token.
        HTTPException 503: If auth is not configured.
    """
    if auth_usecases is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard auth service not configured. Set ADMIN_PASSWORD and AUTH_SECRET env vars.",
        )

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization: Bearer <token> header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not auth_usecases.validate(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_admin_auth_if_enabled(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    auth_usecases=Depends(get_auth_usecases),
) -> None:
    """Validate Bearer token only when dashboard auth is enabled."""
    if auth_usecases is None or not auth_usecases.is_enabled():
        return

    await require_admin_auth(credentials=credentials, auth_usecases=auth_usecases)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    password: str = Field(..., description="Admin dashboard password")


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_in_hours: int = 24


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
    """Bulk provider settings payload: provider → settings map."""
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

_PROVIDER_OAUTH_STATE_TTL_MINUTES = 10


def _require_oauth_provider(provider: str) -> str:
    key = (provider or "").strip().lower()
    spec = PROVIDER_SPECS.get(key)
    if spec is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "LLM_PROVIDER_UNKNOWN",
                "provider": provider,
                "message": f"Unknown provider {provider!r}",
            },
        )
    if spec.transport not in {"codex_oauth", "anthropic_messages"}:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "LLM_PROVIDER_OAUTH_NOT_SUPPORTED",
                "provider": key,
                "message": f"Provider {key!r} does not use OAuth onboarding.",
            },
        )
    return key


def _normalize_frontend_redirect_uri(redirect_uri: str | None) -> str:
    value = (redirect_uri or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "LLM_PROVIDER_OAUTH_REDIRECT_INVALID",
                "message": "A full frontend redirectUri is required, e.g. http://localhost:5173/oauth/callback.",
            },
        )
    return value


def _get_registered_redirect_uri(provider: str) -> str:
    """Return the redirect_uri registered with the provider's OAuth server.

    These MUST match exactly what the OAuth server accepts for the client_id.
    They are the defaults baked into the OAuth client classes.
    """
    if provider == "openai_codex":
        from app.adapters.ai.codex_oauth_client import _DEFAULT_REDIRECT_URI
        return os.environ.get("OPENAI_CODEX_REDIRECT_URI", _DEFAULT_REDIRECT_URI)
    from app.adapters.ai.anthropic_oauth_client import _DEFAULT_REDIRECT_URI
    return os.environ.get("CLAUDE_CODE_REDIRECT_URI", _DEFAULT_REDIRECT_URI)


def _build_oauth_client(provider: str, *, redirect_uri: str | None = None, token_store=None):
    if provider == "openai_codex":
        if token_store is not None:
            return (
                CodexOAuthClient(token_store=token_store, redirect_uri=redirect_uri)
                if redirect_uri
                else CodexOAuthClient(token_store=token_store)
            )
        return CodexOAuthClient(redirect_uri=redirect_uri) if redirect_uri else CodexOAuthClient()

    if token_store is not None:
        return (
            AnthropicOAuthClient(token_store=token_store, redirect_uri=redirect_uri)
            if redirect_uri
            else AnthropicOAuthClient(token_store=token_store)
        )
    return AnthropicOAuthClient(redirect_uri=redirect_uri) if redirect_uri else AnthropicOAuthClient()


def _get_oauth_state_secret(request: Request) -> str:
    secret = getattr(request.app.state, "oauth_state_secret", "").strip()
    if secret:
        return secret

    secret = os.environ.get("OAUTH_STATE_SECRET", "").strip()
    if not secret:
        secret = os.environ.get("AUTH_SECRET", "").strip()
    if not secret:
        secret = secrets.token_urlsafe(32)

    request.app.state.oauth_state_secret = secret
    return secret


def _base64url_encode(data: bytes) -> str:
    return urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return urlsafe_b64decode(data + padding)


def _encode_oauth_state(
    request: Request,
    *,
    provider: str,
    frontend_redirect_uri: str,
    registered_redirect_uri: str,
    code_verifier: str,
) -> str:
    payload = {
        "sub": "provider_oauth",
        "provider": provider,
        "frontend_redirect_uri": frontend_redirect_uri,
        "registered_redirect_uri": registered_redirect_uri,
        "code_verifier": code_verifier,
        "nonce": secrets.token_hex(16),
        "iat": int(time.time()),
        "exp": int(time.time()) + (_PROVIDER_OAUTH_STATE_TTL_MINUTES * 60),
    }
    payload_segment = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        _get_oauth_state_secret(request).encode("utf-8"),
        payload_segment.encode("utf-8"),
        sha256,
    ).digest()
    return f"{payload_segment}.{_base64url_encode(signature)}"


def _decode_oauth_state(token: str, request: Request, *, verify_exp: bool = True) -> dict[str, Any]:
    try:
        payload_segment, signature_segment = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Malformed OAuth state token") from exc

    expected_signature = hmac.new(
        _get_oauth_state_secret(request).encode("utf-8"),
        payload_segment.encode("utf-8"),
        sha256,
    ).digest()
    actual_signature = _base64url_decode(signature_segment)
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise ValueError("Invalid OAuth state signature")

    payload = json.loads(_base64url_decode(payload_segment).decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("OAuth state payload must be an object")

    required_keys = {
        "sub",
        "provider",
        "frontend_redirect_uri",
        "registered_redirect_uri",
        "code_verifier",
        "nonce",
        "exp",
    }
    missing = required_keys.difference(payload.keys())
    if missing:
        raise ValueError(f"Missing OAuth state fields: {sorted(missing)!r}")
    if payload.get("sub") != "provider_oauth":
        raise ValueError("Unexpected OAuth state subject")
    if verify_exp and int(payload["exp"]) < int(time.time()):
        raise ValueError("OAuth state expired")
    return payload



# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/auth/login", response_model=LoginResponse, summary="Admin dashboard login")
async def login(
    request: LoginRequest,
    auth_usecases=Depends(get_auth_usecases),
):
    """Authenticate with admin password. Returns a JWT token valid for 24 hours."""
    if auth_usecases is None or not auth_usecases.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard auth is disabled. Set ENABLE_DASHBOARD_AUTH=true with ADMIN_PASSWORD and AUTH_SECRET to enable it.",
        )
    try:
        token = auth_usecases.login(request.password)
        return LoginResponse(token=token)
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )


@router.get(
    "/llm-configs",
    response_model=list[LLMConfigResponse],
    dependencies=[Depends(require_admin_auth_if_enabled)],
    summary="List LLM configurations",
)
async def list_llm_configs(
    llm_usecases=Depends(get_llm_config_usecases),
):
    """List all LLM provider configurations. API keys are masked."""
    if llm_usecases is None:
        raise HTTPException(status_code=503, detail="LLM config service not configured")
    configs = llm_usecases.list_all()
    return [LLMConfigResponse.from_entity(c) for c in configs]


@router.get(
    "/llm-providers",
    response_model=list[ProviderCapabilityResponse],
    dependencies=[Depends(require_admin_auth_if_enabled)],
    summary="List provider capabilities and rollout status",
)
async def list_llm_providers():
    """List provider capabilities for dashboard guardrails.

    Includes feature-flag and enabled state so operators know why a provider
    is unavailable before attempting chat runs.
    """
    providers = []
    for provider, spec in sorted(PROVIDER_SPECS.items()):
        providers.append(ProviderCapabilityResponse.from_spec(provider, spec))
    return providers


@router.post(
    "/llm-providers/{provider}/oauth/authorize",
    response_model=ProviderOAuthAuthorizeResponse,
    dependencies=[Depends(require_admin_auth_if_enabled)],
    summary="Generate OAuth authorize URL for provider onboarding",
)
async def create_provider_oauth_authorize_with_body(
    provider: str,
    request: ProviderOAuthAuthorizeRequest,
    http_request: Request,
):
    key = _require_oauth_provider(provider)
    frontend_redirect_uri = _normalize_frontend_redirect_uri(request.redirect_uri)

    # The redirect_uri sent to the OAuth server MUST match what is registered
    # for the client_id.  For Anthropic this is console.anthropic.com's code
    # display page; for Codex it is a localhost callback.
    # frontend_redirect_uri is stored in the state token so the frontend knows
    # where to show results, but it is NOT sent to the OAuth server.
    oauth_redirect_uri = _get_registered_redirect_uri(key)
    client = _build_oauth_client(key, redirect_uri=oauth_redirect_uri)
    code_verifier = client.generate_code_verifier()
    code_challenge = client.generate_code_challenge(code_verifier)
    state = _encode_oauth_state(
        http_request,
        provider=key,
        frontend_redirect_uri=frontend_redirect_uri,
        registered_redirect_uri=oauth_redirect_uri,
        code_verifier=code_verifier,
    )
    authorization_url = client.build_authorization_url(
        code_challenge=code_challenge,
        state=state,
    )
    return ProviderOAuthAuthorizeResponse(
        provider=key,
        authorization_url=authorization_url,
    )

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


@router.get(
    "/llm-providers/{provider}/oauth/status",
    dependencies=[Depends(require_admin_auth_if_enabled)],
    summary="Get OAuth connection status for a provider",
)
async def get_provider_oauth_status(
    provider: str,
    token_store=Depends(get_oauth_token_store),
):
    """Return whether a stored OAuth credential exists for the provider.

    Note: token refresh on near-expiry is not yet supported. The frontend
    should prompt the user to re-authenticate when the token is close to expiry.
    """
    key = _require_oauth_provider(provider)
    cred = token_store.get(key)
    if cred is None or cred.revoked:
        return {"provider": key, "connected": False, "expires_at_ms": None, "account_id": None}

    now_ms = int(time.time() * 1000)
    expires_at_ms: int | None = cred.expires_at_ms
    expired = expires_at_ms is not None and expires_at_ms < now_ms

    return {
        "provider": key,
        "connected": not expired,
        "expires_at_ms": expires_at_ms,
        "account_id": cred.account_id,
    }


@router.delete(
    "/llm-providers/{provider}/oauth/revoke",
    status_code=204,
    dependencies=[Depends(require_admin_auth_if_enabled)],
    summary="Revoke and clear stored OAuth credential for a provider",
)
async def revoke_provider_oauth(
    provider: str,
    token_store=Depends(get_oauth_token_store),
):
    """Clear the stored OAuth credential so the provider requires re-authentication."""
    key = _require_oauth_provider(provider)
    token_store.revoke(key)


@router.post(
    "/llm-providers/{provider}/oauth/exchange",
    summary="Exchange OAuth authorization code for tokens (called by frontend after redirect)",
)
async def provider_oauth_exchange(
    request: Request,
    provider: str,
    body: OAuthExchangeRequest,
    token_store=Depends(get_oauth_token_store),
):
    """Frontend captures ``code`` + ``state`` from the provider redirect and
    POSTs them here.  Backend decodes the HMAC-signed state to recover
    ``code_verifier`` and ``registered_redirect_uri``, then exchanges the code
    for access + refresh tokens.
    """
    key = _require_oauth_provider(provider)

    # Normalise the pasted input — accept full redirect URL, query string,
    # plain code, or Anthropic's code#state format.
    state_token = body.state
    code_value = body.code
    raw = (body.code or "").strip()

    # Full URL (http://localhost:1455/auth/callback?code=...&state=...)
    parsed_url = urlparse(raw)
    if parsed_url.scheme and parsed_url.netloc:
        qs = dict(parse_qsl(parsed_url.query))
        if qs.get("code"):
            code_value = qs["code"]
            state_token = qs.get("state") or body.state
    # Query string without scheme (code=...&state=...)
    elif "code=" in raw:
        qs = dict(parse_qsl(raw))
        if qs.get("code"):
            code_value = qs["code"]
            state_token = qs.get("state") or body.state
    # Anthropic paste format: {auth_code}#{state}
    elif "#" in raw:
        parts = raw.split("#", 1)
        code_value = parts[0]
        state_token = parts[1] or body.state

    try:
        oauth_state = _decode_oauth_state(state_token, request)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "LLM_PROVIDER_OAUTH_STATE_INVALID",
                "provider": key,
                "message": "OAuth state is invalid or expired. Start the connection again.",
            },
        ) from exc

    if str(oauth_state["provider"]) != key:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "LLM_PROVIDER_OAUTH_STATE_MISMATCH",
                "provider": key,
                "message": "OAuth state does not match the requested provider.",
            },
        )

    registered_redirect_uri = str(oauth_state["registered_redirect_uri"])
    try:
        client = _build_oauth_client(
            key,
            token_store=token_store,
            redirect_uri=registered_redirect_uri,
        )
        await client.exchange_authorization_code(
            code=code_value,
            code_verifier=str(oauth_state["code_verifier"]),
            state=state_token,
        )
        return {
            "provider": key,
            "status": "connected",
            "message": f"{key} OAuth connected successfully.",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "LLM_PROVIDER_OAUTH_EXCHANGE_FAILED",
                "provider": key,
                "message": f"Failed to exchange OAuth authorization code: {exc}",
            },
        ) from exc


@router.post(
    "/llm-configs",
    response_model=LLMConfigResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_auth_if_enabled)],
    summary="Create LLM configuration",
)
async def create_llm_config(
    request: LLMConfigCreate,
    llm_usecases=Depends(get_llm_config_usecases),
):
    """Create a new LLM provider configuration."""
    if llm_usecases is None:
        raise HTTPException(status_code=503, detail="LLM config service not configured")
    try:
        config = llm_usecases.create(
            label=request.label,
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
            activate=request.activate,
            base_url=request.base_url,
        )
        return LLMConfigResponse.from_entity(config)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.put(
    "/llm-configs/{config_id}",
    response_model=LLMConfigResponse,
    dependencies=[Depends(require_admin_auth_if_enabled)],
    summary="Update LLM configuration",
)
async def update_llm_config(
    config_id: UUID,
    request: LLMConfigUpdate,
    llm_usecases=Depends(get_llm_config_usecases),
):
    """Update fields on an existing LLM configuration."""
    if llm_usecases is None:
        raise HTTPException(status_code=503, detail="LLM config service not configured")
    try:
        config = llm_usecases.update(
            config_id,
            label=request.label,
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
            base_url=request.base_url,
        )
        return LLMConfigResponse.from_entity(config)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.delete(
    "/llm-configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_auth_if_enabled)],
    summary="Delete LLM configuration",
)
async def delete_llm_config(
    config_id: UUID,
    llm_usecases=Depends(get_llm_config_usecases),
):
    """Delete an LLM configuration by ID."""
    if llm_usecases is None:
        raise HTTPException(status_code=503, detail="LLM config service not configured")
    try:
        llm_usecases.delete(config_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/llm-configs/{config_id}/activate",
    response_model=LLMConfigResponse,
    dependencies=[Depends(require_admin_auth_if_enabled)],
    summary="Set active LLM configuration",
)
async def activate_llm_config(
    config_id: UUID,
    llm_usecases=Depends(get_llm_config_usecases),
):
    """Set a config as the active LLM provider. Deactivates all others."""
    if llm_usecases is None:
        raise HTTPException(status_code=503, detail="LLM config service not configured")
    try:
        config = llm_usecases.activate(config_id)
        return LLMConfigResponse.from_entity(config)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ---------------------------------------------------------------------------
# Provider settings bulk endpoints (flat per-provider key/model/base_url store)
# ---------------------------------------------------------------------------

@router.get(
    "/provider-settings",
    dependencies=[Depends(require_admin_auth_if_enabled)],
    summary="Get saved settings for all providers",
)
async def get_provider_settings(
    llm_usecases=Depends(get_llm_config_usecases),
) -> dict:
    """Return saved api_key (masked), model, and base_url per provider.

    Providers with no saved config are omitted from the response.
    The caller should merge with its own defaults for any missing providers.
    """
    if llm_usecases is None:
        return {"providers": {}}

    all_configs = llm_usecases.list_all()
    # Collect by label (provider name) — skip configs not matching a known provider label
    from app.adapters.ai.provider_catalog import PROVIDER_SPECS

    result: dict[str, dict] = {}
    for cfg in all_configs:
        label = cfg.label.lower()
        if label in PROVIDER_SPECS:
            result[label] = {
                "api_key_masked": cfg.masked_api_key(),
                "model": cfg.model,
                "base_url": cfg.base_url,
            }
    return {"providers": result}


@router.put(
    "/provider-settings",
    dependencies=[Depends(require_admin_auth_if_enabled)],
    summary="Save settings for all providers (bulk upsert)",
)
async def put_provider_settings(
    request: ProviderSettingsRequest,
    llm_usecases=Depends(get_llm_config_usecases),
) -> dict:
    """Upsert settings for each provider included in the payload.

    Each provider gets one canonical config entry (label == provider).
    Missing providers in the payload are left unchanged.
    The api_key sent here is the raw key; the masked form is returned for confirmation.
    """
    if llm_usecases is None:
        raise HTTPException(status_code=503, detail="LLM config service not configured")

    saved: dict[str, dict] = {}
    errors: dict[str, str] = {}

    for provider, entry in request.settings.items():
        try:
            cfg = llm_usecases.upsert_by_provider(
                provider=provider,
                api_key=entry.api_key,
                model=entry.model,
                base_url=entry.base_url,
            )
            saved[provider] = {
                "api_key_masked": cfg.masked_api_key(),
                "model": cfg.model,
                "base_url": cfg.base_url,
            }
        except ValueError as e:
            errors[provider] = str(e)

    response: dict = {"saved": saved}
    if errors:
        response["errors"] = errors
    return response
