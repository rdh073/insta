"""Adapter-internal contract for OAuth token persistence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OAuthCredential:
    provider: str
    refresh_token: str
    access_token: str | None = None
    expires_at_ms: int | None = None
    account_id: str | None = None
    revoked: bool = False


class OAuthTokenStore:
    """Persistence contract for provider OAuth credentials."""

    def get(self, provider: str) -> OAuthCredential | None:
        raise NotImplementedError

    def save(self, credential: OAuthCredential) -> None:
        raise NotImplementedError

    def revoke(self, provider: str) -> None:
        raise NotImplementedError

