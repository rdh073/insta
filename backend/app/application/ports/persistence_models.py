"""Typed persistence records for repository ports (Phase 0 frozen contracts).

These records are app-owned contracts between use cases and persistence adapters.
AccountRecord, JobRecord, and Status are production-grade contracts and must not
change without explicit architecture review.

They intentionally support legacy key access (`get`, `__getitem__`) to keep
incremental migration safe while moving away from free-form dict contracts.

Modifications to these contracts must:
  - Update corresponding SQL schema (alembic migration)
  - Update all adapter implementations
  - Validate against backward compatibility constraints
  - Pass full test matrix across persistence backends
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AccountRecord:
    """Canonical account persistence record."""

    username: str
    password: str = ""
    proxy: str | None = None
    country: str | None = None
    country_code: int | None = None
    locale: str | None = None
    timezone_offset: int | None = None
    totp_secret: str | None = None
    totp_enabled: bool = False
    full_name: str | None = None
    followers: int | None = None
    following: int | None = None
    profile_pic_url: str | None = None
    # Session health tracking
    last_verified_at: str | None = None  # ISO timestamp of last successful Instagram interaction
    last_error: str | None = None  # Last error message
    last_error_code: str | None = None  # Structured error code (e.g., "session_expired", "challenge")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccountRecord:
        def _optional_int(value: Any) -> int | None:
            if value is None:
                return None
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                cleaned = value.strip()
                if not cleaned:
                    return None
                try:
                    return int(cleaned)
                except ValueError:
                    return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        return cls(
            username=str(data.get("username", "")),
            password=str(data.get("password", "")),
            proxy=data.get("proxy"),
            country=data.get("country"),
            country_code=_optional_int(data.get("country_code")),
            locale=data.get("locale"),
            timezone_offset=_optional_int(data.get("timezone_offset")),
            totp_secret=data.get("totp_secret"),
            totp_enabled=bool(data.get("totp_enabled", False)),
            full_name=data.get("full_name"),
            followers=data.get("followers"),
            following=data.get("following"),
            profile_pic_url=data.get("profile_pic_url"),
            last_verified_at=data.get("last_verified_at"),
            last_error=data.get("last_error"),
            last_error_code=data.get("last_error_code"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "password": self.password,
            "proxy": self.proxy,
            "country": self.country,
            "country_code": self.country_code,
            "locale": self.locale,
            "timezone_offset": self.timezone_offset,
            "totp_secret": self.totp_secret,
            "totp_enabled": self.totp_enabled,
            "full_name": self.full_name,
            "followers": self.followers,
            "following": self.following,
            "profile_pic_url": self.profile_pic_url,
            "last_verified_at": self.last_verified_at,
            "last_error": self.last_error,
            "last_error_code": self.last_error_code,
        }

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        if not hasattr(self, key):
            raise KeyError(key)
        return getattr(self, key)


@dataclass
class JobRecord:
    """Canonical post job persistence record."""

    id: str
    caption: str
    status: str
    targets: list[dict] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    created_at: str = ""
    media_urls: list[str] = field(default_factory=list)
    media_type: str = "photo"
    media_paths: list[str] = field(default_factory=list)
    scheduled_at: str | None = None
    thumbnail_path: str | None = None
    igtv_title: str | None = None
    usertags: list[dict] = field(default_factory=list)
    location: dict | None = None
    extra_data: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobRecord:
        return cls(
            id=str(data.get("id", "")),
            caption=str(data.get("caption", "")),
            status=str(data.get("status", "")),
            targets=list(data.get("targets", [])),
            results=list(data.get("results", [])),
            created_at=str(data.get("createdAt", "")),
            media_urls=list(data.get("mediaUrls", [])),
            media_type=str(data.get("mediaType", "photo")),
            media_paths=list(data.get("_media_paths", [])),
            scheduled_at=data.get("_scheduled_at"),
            thumbnail_path=data.get("_thumbnail_path"),
            igtv_title=data.get("_igtv_title"),
            usertags=list(data.get("_usertags", [])),
            location=data.get("_location"),
            extra_data=dict(data.get("_extra_data") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "caption": self.caption,
            "status": self.status,
            "targets": self.targets,
            "results": self.results,
            "createdAt": self.created_at,
            "mediaUrls": self.media_urls,
            "mediaType": self.media_type,
            "_media_paths": self.media_paths,
            "_scheduled_at": self.scheduled_at,
            "_thumbnail_path": self.thumbnail_path,
            "_igtv_title": self.igtv_title,
            "_usertags": self.usertags,
            "_location": self.location,
            "_extra_data": self.extra_data,
        }

    def get(self, key: str, default: Any = None) -> Any:
        key_map = {
            "createdAt": "created_at",
            "mediaUrls": "media_urls",
            "mediaType": "media_type",
            "_media_paths": "media_paths",
            "_scheduled_at": "scheduled_at",
            "_thumbnail_path": "thumbnail_path",
            "_igtv_title": "igtv_title",
            "_usertags": "usertags",
            "_location": "location",
            "_extra_data": "extra_data",
        }
        attr = key_map.get(key, key)
        return getattr(self, attr, default)

    def __getitem__(self, key: str) -> Any:
        _nullable = ("_scheduled_at", "_thumbnail_path", "_igtv_title", "_location")
        _known = (
            "createdAt", "mediaUrls", "mediaType", "_media_paths",
            "_scheduled_at", "_thumbnail_path", "_igtv_title",
            "_usertags", "_location", "_extra_data",
        )
        if key in _known:
            value = self.get(key, None)
            if value is None and key not in _nullable:
                raise KeyError(key)
            return value
        if not hasattr(self, key):
            raise KeyError(key)
        return getattr(self, key)

    def items(self):
        """Dict-like items() — delegates to to_dict() for caller compatibility."""
        return self.to_dict().items()


@dataclass
class ProxyRecord:
    """Canonical proxy persistence record."""

    host:       str
    port:       int
    protocol:   str   # ProxyProtocol value string
    anonymity:  str   # ProxyAnonymity value string
    latency_ms: float
    url:        str
