"""SQLAlchemy-based LLM configuration repository.

Implements LLMConfigRepository port.
API keys are encrypted at rest using Fernet (via CryptoService).
The application layer always sees plaintext values.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.adapters.persistence.sql_store import Base, SqlitePersistenceStore
from app.adapters.persistence.crypto import CryptoService
from app.domain.llm_config import LLMConfig, LLMProvider


# ---------------------------------------------------------------------------
# ORM model (adapter-internal)
# ---------------------------------------------------------------------------

class LLMConfigRow(Base):
    """ORM row for llm_configs table."""

    __tablename__ = "llm_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ---------------------------------------------------------------------------
# Repository adapter
# ---------------------------------------------------------------------------

class SQLLLMConfigRepository:
    """Implements LLMConfigRepository using SQLAlchemy.

    Encryption/decryption of api_key is handled transparently here.
    The application layer always receives plaintext LLMConfig entities.
    """

    def __init__(self, store: SqlitePersistenceStore, crypto: CryptoService) -> None:
        self._store = store
        self._crypto = crypto

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def _to_entity(self, row: LLMConfigRow) -> LLMConfig:
        """Convert ORM row to domain entity (decrypt api_key)."""
        return LLMConfig(
            id=UUID(row.id),
            label=row.label,
            provider=LLMProvider(row.provider),
            api_key=self._crypto.decrypt(row.api_key_encrypted),
            model=row.model,
            base_url=row.base_url,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _to_row(self, config: LLMConfig) -> LLMConfigRow:
        """Convert domain entity to ORM row (encrypt api_key)."""
        return LLMConfigRow(
            id=str(config.id),
            label=config.label,
            provider=config.provider.value,
            api_key_encrypted=self._crypto.encrypt(config.api_key),
            model=config.model,
            base_url=config.base_url,
            is_active=config.is_active,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    def save(self, config: LLMConfig) -> LLMConfig:
        """Create or update an LLM config row."""
        with self._store.session() as session:
            existing = session.get(LLMConfigRow, str(config.id))
            if existing:
                # Update in place
                existing.label = config.label
                existing.provider = config.provider.value
                existing.api_key_encrypted = self._crypto.encrypt(config.api_key)
                existing.model = config.model
                existing.base_url = config.base_url
                existing.is_active = config.is_active
                existing.updated_at = config.updated_at
            else:
                row = self._to_row(config)
                session.add(row)
            session.commit()
        return self.find_by_id(config.id) or config

    def find_by_id(self, config_id: UUID) -> Optional[LLMConfig]:
        """Retrieve by primary key."""
        with self._store.session() as session:
            row = session.get(LLMConfigRow, str(config_id))
            if row is None:
                return None
            return self._to_entity(row)

    def find_all(self) -> list[LLMConfig]:
        """Retrieve all configs, newest first."""
        from sqlalchemy import select, desc

        with self._store.session() as session:
            rows = session.execute(
                select(LLMConfigRow).order_by(desc(LLMConfigRow.created_at))
            ).scalars().all()
            return [self._to_entity(r) for r in rows]

    def find_active(self) -> Optional[LLMConfig]:
        """Retrieve the active config."""
        from sqlalchemy import select

        with self._store.session() as session:
            row = session.execute(
                select(LLMConfigRow).where(LLMConfigRow.is_active.is_(True))
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._to_entity(row)

    def delete(self, config_id: UUID) -> None:
        """Delete by primary key."""
        with self._store.session() as session:
            row = session.get(LLMConfigRow, str(config_id))
            if row:
                session.delete(row)
                session.commit()

    def find_by_provider(self, provider: str) -> Optional[LLMConfig]:
        """Find config whose label matches the provider string."""
        from sqlalchemy import select

        key = (provider or "").strip().lower()
        with self._store.session() as session:
            row = session.execute(
                select(LLMConfigRow).where(LLMConfigRow.label == key)
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._to_entity(row)

    def set_active(self, config_id: UUID) -> None:
        """Atomically deactivate all configs, then activate the target."""
        from sqlalchemy import update

        with self._store.session() as session:
            # Deactivate all
            session.execute(
                update(LLMConfigRow).values(is_active=False)
            )
            # Activate target
            target = session.get(LLMConfigRow, str(config_id))
            if target is None:
                session.rollback()
                raise KeyError(f"LLM config {config_id!r} not found")
            target.is_active = True
            target.updated_at = datetime.now(timezone.utc)
            session.commit()
