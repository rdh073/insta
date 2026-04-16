from __future__ import annotations

import time
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.adapters.ai.llm_failure_catalog import LLMFailure, LLMFailureFamily
from app.adapters.ai.provider_catalog import PROVIDER_SPECS

from .auth import get_llm_config_usecases, require_admin_auth_if_enabled
from .schemas import (
    OllamaHealthResponse,
    OllamaModel,
    OllamaModelsResponse,
    ProviderSettingsRequest,
)

router = APIRouter()

_OLLAMA_PROVIDER = "ollama"
_OLLAMA_PROBE_TIMEOUT_SECONDS = 6.0


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
    # Collect by label (provider name) - skip configs not matching a known provider label.
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


def _resolve_ollama_base_url(requested: str | None) -> str:
    """Resolve the Ollama base URL: request override first, then provider spec."""
    candidate = (requested or "").strip()
    if not candidate:
        spec = PROVIDER_SPECS.get(_OLLAMA_PROVIDER)
        candidate = (spec.base_url if spec else "") or ""
    candidate = candidate.rstrip("/")
    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        raise LLMFailure(
            family=LLMFailureFamily.INVALID_REQUEST,
            message=(
                "Ollama base_url is missing or malformed. "
                "Provide ?base_url=<scheme>://<host>:<port>/v1 or set OLLAMA_BASE_URL."
            ),
            provider=_OLLAMA_PROVIDER,
        )
    return candidate


def _failure_detail(exc: LLMFailure) -> dict:
    return {
        "code": {
            LLMFailureFamily.AUTH: "LLM_AUTH_FAILED",
            LLMFailureFamily.RATE_LIMIT: "LLM_RATE_LIMITED",
            LLMFailureFamily.PROVIDER_UNAVAILABLE: "LLM_PROVIDER_UNAVAILABLE",
            LLMFailureFamily.INVALID_REQUEST: "LLM_INVALID_REQUEST",
            LLMFailureFamily.TRANSPORT_MISMATCH: "LLM_PROVIDER_TRANSPORT_UNAVAILABLE",
        }.get(exc.family, "LLM_INVALID_REQUEST"),
        "family": exc.family.value,
        "provider": exc.provider,
        "message": exc.message,
    }


async def _probe_ollama_models(base_url: str) -> tuple[list[dict], int]:
    """Call <base_url>/models and return (raw_model_entries, latency_ms).

    Raises LLMFailure with the appropriate family on timeout/connection/HTTP failure.
    """
    url = f"{base_url}/models"
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=_OLLAMA_PROBE_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
    except httpx.TimeoutException as exc:
        raise LLMFailure(
            family=LLMFailureFamily.PROVIDER_UNAVAILABLE,
            message=f"Ollama server at {base_url} did not respond within "
            f"{int(_OLLAMA_PROBE_TIMEOUT_SECONDS)}s.",
            provider=_OLLAMA_PROVIDER,
            cause=exc,
        )
    except httpx.HTTPError as exc:
        raise LLMFailure(
            family=LLMFailureFamily.PROVIDER_UNAVAILABLE,
            message=f"Could not reach Ollama server at {base_url}.",
            provider=_OLLAMA_PROVIDER,
            cause=exc,
        )

    if response.status_code >= 400:
        raise LLMFailure(
            family=LLMFailureFamily.PROVIDER_UNAVAILABLE,
            message=f"Ollama server at {base_url} returned HTTP {response.status_code}.",
            provider=_OLLAMA_PROVIDER,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise LLMFailure(
            family=LLMFailureFamily.PROVIDER_UNAVAILABLE,
            message=f"Ollama server at {base_url} returned a non-JSON body.",
            provider=_OLLAMA_PROVIDER,
            cause=exc,
        )

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise LLMFailure(
            family=LLMFailureFamily.PROVIDER_UNAVAILABLE,
            message=f"Ollama server at {base_url} returned an unexpected /models shape.",
            provider=_OLLAMA_PROVIDER,
        )

    latency_ms = int((time.perf_counter() - started) * 1000)
    return data, latency_ms


def _status_for_failure(exc: LLMFailure) -> int:
    if exc.family == LLMFailureFamily.INVALID_REQUEST:
        return 400
    cause = exc.cause
    if isinstance(cause, httpx.TimeoutException):
        return 504
    return 502


@router.get(
    "/providers/ollama/models",
    response_model=OllamaModelsResponse,
    summary="List models installed on a self-hosted Ollama server",
)
async def list_ollama_models(
    base_url: str | None = Query(
        default=None,
        description="OpenAI-compatible root, e.g. http://host:port/v1. "
        "Falls back to provider_catalog OLLAMA base_url when omitted.",
    ),
) -> OllamaModelsResponse:
    try:
        resolved = _resolve_ollama_base_url(base_url)
        raw_models, _ = await _probe_ollama_models(resolved)
    except LLMFailure as exc:
        raise HTTPException(
            status_code=_status_for_failure(exc),
            detail=_failure_detail(exc),
        )

    models = [
        OllamaModel(
            id=str(entry.get("id", "")),
            owned_by=str(entry.get("owned_by", "library") or "library"),
        )
        for entry in raw_models
        if isinstance(entry, dict) and entry.get("id")
    ]
    models.sort(key=lambda m: m.id)
    return OllamaModelsResponse(base_url=resolved, models=models)


@router.get(
    "/providers/ollama/health",
    response_model=OllamaHealthResponse,
    summary="Probe a self-hosted Ollama server for availability",
)
async def ollama_health(
    base_url: str | None = Query(default=None),
) -> OllamaHealthResponse:
    try:
        resolved = _resolve_ollama_base_url(base_url)
        raw_models, latency_ms = await _probe_ollama_models(resolved)
    except LLMFailure as exc:
        raise HTTPException(
            status_code=_status_for_failure(exc),
            detail=_failure_detail(exc),
        )
    return OllamaHealthResponse(
        ok=True,
        base_url=resolved,
        model_count=len(raw_models),
        latency_ms=latency_ms,
    )
