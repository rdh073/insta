"""HTTP router for LLM configuration management and dashboard auth.

Endpoints:
  GET    /api/dashboard/llm-configs    - list (api_key masked)
  POST   /api/dashboard/llm-configs    - create
  PUT    /api/dashboard/llm-configs/{id} - update
  DELETE /api/dashboard/llm-configs/{id} - 204
  POST   /api/dashboard/llm-configs/{id}/activate - set active

Authentication: Optional Bearer token when ENABLE_DASHBOARD_AUTH=true.
The api_key field is NEVER returned in full. Only masked form is exposed.

Canonical auth endpoints (`/api/dashboard/auth/status`, `/api/dashboard/auth/login`)
are owned by `app.adapters.http.routers.dashboard` to avoid duplicate route
registration ambiguity.
"""

from __future__ import annotations

from fastapi import APIRouter

from .auth import (
    get_auth_usecases,
    get_llm_config_usecases,
    require_admin_auth,
    require_admin_auth_if_enabled,
)
from .config_crud import router as config_crud_router
from .provider_oauth import router as provider_oauth_router
from .provider_settings import router as provider_settings_router

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
router.include_router(config_crud_router)
router.include_router(provider_oauth_router)
router.include_router(provider_settings_router)

__all__ = [
    "router",
    "get_auth_usecases",
    "get_llm_config_usecases",
    "require_admin_auth",
    "require_admin_auth_if_enabled",
]
