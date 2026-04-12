from __future__ import annotations

import os
import time
from urllib.parse import parse_qsl, urlparse

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.ai.anthropic_oauth_client import AnthropicOAuthClient
from app.adapters.ai.codex_oauth_client import CodexOAuthClient
from app.adapters.ai.provider_catalog import PROVIDER_SPECS
from app.adapters.http.dependencies import get_oauth_token_store

from .auth import require_admin_auth_if_enabled
from .oauth_state import decode_oauth_state, encode_oauth_state
from .schemas import (
    OAuthExchangeRequest,
    ProviderCapabilityResponse,
    ProviderOAuthAuthorizeRequest,
    ProviderOAuthAuthorizeResponse,
)

router = APIRouter()


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
    # for the client_id. For Anthropic this is console.anthropic.com's code
    # display page; for Codex it is a localhost callback.
    # frontend_redirect_uri is stored in the state token so the frontend knows
    # where to show results, but it is NOT sent to the OAuth server.
    oauth_redirect_uri = _get_registered_redirect_uri(key)
    client = _build_oauth_client(key, redirect_uri=oauth_redirect_uri)
    code_verifier = client.generate_code_verifier()
    code_challenge = client.generate_code_challenge(code_verifier)
    state = encode_oauth_state(
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
    POSTs them here. Backend decodes the HMAC-signed state to recover
    ``code_verifier`` and ``registered_redirect_uri``, then exchanges the code
    for access + refresh tokens.
    """
    key = _require_oauth_provider(provider)

    # Normalise the pasted input - accept full redirect URL, query string,
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
        oauth_state = decode_oauth_state(state_token, request)
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
