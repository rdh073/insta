"""Account endpoint request/response schemas."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Request schema for POST /api/accounts/login."""
    username: str
    password: str
    proxy: Optional[str] = None
    totp_secret: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[int] = None
    locale: Optional[str] = None
    timezone_offset: Optional[int] = None


class TwoFARequest(BaseModel):
    """Request schema for POST /api/accounts/login/2fa."""
    account_id: str
    code: str
    is_totp: Optional[bool] = False


class ProxyRequest(BaseModel):
    """Request schema for PATCH /api/accounts/{account_id}/proxy."""
    proxy: str


class BulkAccountIds(BaseModel):
    """Request schema for bulk account operations."""
    account_ids: list[str]


class BulkProxyRequest(BaseModel):
    """Request schema for PATCH /api/accounts/bulk/proxy."""
    account_ids: list[str]
    proxy: str


class TOTPSetupRequest(BaseModel):
    """Request schema for TOTP setup."""
    account_id: str
    secret: str
    code: str


class ImportAccountsRequest(BaseModel):
    """Request schema for POST /api/accounts/import."""
    text: str
