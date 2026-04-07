"""SQLAlchemy OAuth token store with encrypted token fields."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.ai.oauth_token_store import OAuthCredential, OAuthTokenStore
from app.adapters.persistence.crypto import CryptoService
from app.adapters.persistence.sql_store import Base, SqlitePersistenceStore


class OAuthCredentialRow(Base):
    __tablename__ = "oauth_credentials"

    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SQLOAuthTokenStore(OAuthTokenStore):
    def __init__(self, store: SqlitePersistenceStore, crypto: CryptoService) -> None:
        self._store = store
        self._crypto = crypto

    def get(self, provider: str) -> OAuthCredential | None:
        with self._store.session_scope() as session:
            row = session.get(OAuthCredentialRow, provider)
            if row is None or row.revoked:
                return None
            return OAuthCredential(
                provider=row.provider,
                refresh_token=self._crypto.decrypt(row.refresh_token_encrypted),
                access_token=self._crypto.decrypt(row.access_token_encrypted)
                if row.access_token_encrypted
                else None,
                expires_at_ms=row.expires_at_ms,
                account_id=row.account_id,
                revoked=row.revoked,
            )

    def save(self, credential: OAuthCredential) -> None:
        now = datetime.now(timezone.utc)
        with self._store.session_scope() as session:
            row = session.get(OAuthCredentialRow, credential.provider)
            if row is None:
                row = OAuthCredentialRow(
                    provider=credential.provider,
                    refresh_token_encrypted=self._crypto.encrypt(credential.refresh_token),
                    access_token_encrypted=self._crypto.encrypt(credential.access_token)
                    if credential.access_token
                    else None,
                    expires_at_ms=credential.expires_at_ms,
                    account_id=credential.account_id,
                    revoked=credential.revoked,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.refresh_token_encrypted = self._crypto.encrypt(credential.refresh_token)
                row.access_token_encrypted = (
                    self._crypto.encrypt(credential.access_token)
                    if credential.access_token
                    else None
                )
                row.expires_at_ms = credential.expires_at_ms
                row.account_id = credential.account_id
                row.revoked = credential.revoked
                row.updated_at = now
            session.commit()

    def revoke(self, provider: str) -> None:
        with self._store.session_scope() as session:
            row = session.get(OAuthCredentialRow, provider)
            if row is None:
                return
            row.revoked = True
            row.updated_at = datetime.now(timezone.utc)
            session.commit()
