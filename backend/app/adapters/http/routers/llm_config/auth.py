from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.adapters.http.dependencies import get_services

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
