"""In-memory OAuth token store (non-durable fallback)."""

from __future__ import annotations

from app.adapters.ai.oauth_token_store import OAuthCredential, OAuthTokenStore


class InMemoryOAuthTokenStore(OAuthTokenStore):
    def __init__(self) -> None:
        self._store: dict[str, OAuthCredential] = {}

    def get(self, provider: str) -> OAuthCredential | None:
        credential = self._store.get(provider)
        if credential is None or credential.revoked:
            return None
        return credential

    def save(self, credential: OAuthCredential) -> None:
        self._store[credential.provider] = credential

    def revoke(self, provider: str) -> None:
        existing = self._store.get(provider)
        if existing is None:
            return
        existing.revoked = True
        self._store[provider] = existing

