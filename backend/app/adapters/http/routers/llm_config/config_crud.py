from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from .auth import get_llm_config_usecases, require_admin_auth_if_enabled
from .schemas import LLMConfigCreate, LLMConfigResponse, LLMConfigUpdate

router = APIRouter()


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
