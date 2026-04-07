"""Port: LLM configuration repository interface.

Defines the contract the application uses to persist and retrieve LLM configs.
Implemented by infrastructure adapters; never depended on by the domain layer.
"""

from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from app.domain.llm_config import LLMConfig


class LLMConfigRepository(Protocol):
    """Contract for persisting and retrieving LLM configurations."""

    def save(self, config: LLMConfig) -> LLMConfig:
        """Create or update an LLM config.

        Args:
            config: LLMConfig entity to persist.

        Returns:
            Persisted LLMConfig (with updated timestamps if applicable).
        """
        ...

    def find_by_id(self, config_id: UUID) -> Optional[LLMConfig]:
        """Retrieve a config by its ID.

        Args:
            config_id: UUID of the config to retrieve.

        Returns:
            LLMConfig if found, None otherwise.
        """
        ...

    def find_all(self) -> list[LLMConfig]:
        """Retrieve all configs ordered by created_at descending.

        Returns:
            List of all LLM configs.
        """
        ...

    def find_active(self) -> Optional[LLMConfig]:
        """Retrieve the currently active config.

        Returns:
            Active LLMConfig if one exists, None otherwise.
        """
        ...

    def delete(self, config_id: UUID) -> None:
        """Delete a config by ID.

        Args:
            config_id: UUID of the config to delete.
        """
        ...

    def set_active(self, config_id: UUID) -> None:
        """Atomically set one config as active, deactivating all others.

        Args:
            config_id: UUID of the config to activate.

        Raises:
            KeyError: If config_id does not exist.
        """
        ...

    def find_by_provider(self, provider: str) -> Optional[LLMConfig]:
        """Retrieve the config for a specific provider (by label == provider).

        Used for upsert-by-provider when syncing frontend settings.

        Args:
            provider: Provider string (e.g., 'openai', 'gemini').

        Returns:
            LLMConfig if one exists with label matching provider, None otherwise.
        """
        ...
