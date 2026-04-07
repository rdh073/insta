"""Dashboard endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.adapters.http.dependencies import get_dashboard_auth_usecases, get_logs_usecases
from app.adapters.http.utils import format_error

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ── Auth endpoints ────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    password: str


@router.get("/auth/status")
def auth_status(usecases=Depends(get_dashboard_auth_usecases)):
    """Return whether dashboard password auth is enabled on this server.

    Frontend calls this once on startup to decide whether to show the
    login page.  When ``enabled`` is false all routes are freely accessible.
    """
    return {"enabled": usecases.is_enabled()}


@router.post("/auth/login")
def auth_login(body: LoginRequest, usecases=Depends(get_dashboard_auth_usecases)):
    """Validate admin password and return a signed JWT.

    Returns 403 for wrong password, 500 if server is not configured.
    """
    try:
        token = usecases.login(body.password)
        return {
            "token": token,
            "token_type": "bearer",
            "expires_in_hours": usecases.TOKEN_EXPIRY_HOURS,
        }
    except PermissionError:
        raise HTTPException(status_code=403, detail="Invalid password")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=format_error(e, "Auth not configured"))


# ── Dashboard data ─────────────────────────────────────────────────────────────


@router.get("")
def get_dashboard(usecases=Depends(get_logs_usecases)):
    """Aggregated fleet health for the dashboard page."""
    try:
        return usecases.get_dashboard_data()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=format_error(e, "Failed to load dashboard")
        )
