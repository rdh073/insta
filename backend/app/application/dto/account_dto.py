"""Account-related DTOs for request/response boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class LoginRequest:
    """Input for account login use case."""

    username: str
    password: str
    proxy: Optional[str] = None
    totp_secret: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[int] = None
    locale: Optional[str] = None
    timezone_offset: Optional[int] = None


@dataclass
class AccountResponse:
    """Output for account operations."""

    id: str
    username: str
    status: str
    password: Optional[str] = None
    proxy: Optional[str] = None
    full_name: Optional[str] = None
    followers: Optional[int] = None
    following: Optional[int] = None
    avatar: Optional[str] = None
    totp_enabled: Optional[bool] = None
    # Session health tracking
    last_verified_at: Optional[str] = (
        None  # ISO timestamp of last successful Instagram interaction
    )
    last_error: Optional[str] = None
    last_error_code: Optional[str] = None
    last_error_family: Optional[str] = None
    # Server-side logout outcome for logout/bulk-logout flows.
    # One of "success" | "failed" | "not_present"; None for non-logout responses.
    server_logout: Optional[str] = None


@dataclass
class AccountListResponse:
    """Output for listing accounts."""

    accounts: list[AccountResponse]
    total: int
    active: int


@dataclass
class AccountInfoResponse:
    """Output for detailed account info from Instagram."""

    username: str
    full_name: Optional[str] = None
    biography: Optional[str] = None
    followers: Optional[int] = None
    following: Optional[int] = None
    media_count: Optional[int] = None
    is_private: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_business: Optional[bool] = None
    error: Optional[str] = None


@dataclass
class BulkReloginRequest:
    """Input for bulk relogin use case."""

    account_ids: list[str]
    concurrency: int = 5


@dataclass
class BulkVerifyRequest:
    """Input for bulk connectivity verification use case."""

    account_ids: list[str]
    concurrency: int = 3
