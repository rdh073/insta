from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.adapters.ai.provider_catalog import PROVIDER_SPECS

from .auth import get_llm_config_usecases, require_admin_auth_if_enabled
from .schemas import ProviderSettingsRequest

router = APIRouter()


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
