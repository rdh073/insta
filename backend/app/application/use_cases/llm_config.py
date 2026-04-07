"""LLM configuration use cases.

Orchestrates LLM config lifecycle: create, list, activate, update, delete.
The active config is loaded by the AI copilot before invoking a LangGraph run.

Owns:
  - Input validation via domain entity invariants
  - Active config selection logic
  - Error translation to app-level errors
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from app.application.ports.llm_config import LLMConfigRepository
from app.domain.llm_config import (
    LLMConfig,
    LLMProvider,
    InvalidLLMConfig,
    NoActiveLLMConfigError,
)


class LLMConfigUseCases:
    """Application orchestration for LLM provider configuration."""

    def __init__(self, repo: LLMConfigRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(
        self,
        label: str,
        provider: str,
        api_key: str,
        model: str,
        activate: bool = False,
        base_url: Optional[str] = None,
    ) -> LLMConfig:
        """Create a new LLM config and optionally activate it.

        Args:
            label: Human-readable name (e.g., 'My ChatGPT Plus').
            provider: Provider string (openai, gemini, deepseek, antigravity).
            api_key: API key for authentication.
            model: Model name (e.g., 'gpt-4o-mini').
            activate: If True, set this config as active immediately.
            base_url: Optional base URL override (for openai_compatible).

        Returns:
            Created LLMConfig entity.

        Raises:
            ValueError: If any invariant is violated.
        """
        try:
            config = LLMConfig.create(
                label=label,
                provider=provider,
                api_key=api_key,
                model=model,
                base_url=base_url,
            )
        except InvalidLLMConfig as e:
            raise ValueError(str(e)) from e

        saved = self._repo.save(config)

        if activate:
            self._repo.set_active(saved.id)
            saved = self._repo.find_by_id(saved.id) or saved

        return saved

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def list_all(self) -> list[LLMConfig]:
        """List all LLM configs ordered by creation date (newest first).

        Returns:
            List of all LLM configs.
        """
        return self._repo.find_all()

    def get_active(self) -> LLMConfig:
        """Get the currently active LLM config.

        Returns:
            Active LLMConfig.

        Raises:
            NoActiveLLMConfigError: If no config is marked active.
        """
        config = self._repo.find_active()
        if config is None:
            raise NoActiveLLMConfigError(
                "No active LLM config found. "
                "Configure one via the dashboard at POST /api/dashboard/llm-configs."
            )
        return config

    def get_active_or_none(self) -> Optional[LLMConfig]:
        """Get the active config or None if not configured.

        Useful for graceful fallback to env var config.

        Returns:
            Active LLMConfig or None.
        """
        return self._repo.find_active()

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(
        self,
        config_id: UUID,
        *,
        label: Optional[str] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> LLMConfig:
        """Update fields on an existing config.

        Only provided (non-None) fields are updated.

        Args:
            config_id: ID of config to update.
            label: New label if changing.
            provider: New provider string if changing.
            api_key: New API key if changing.
            model: New model if changing.

        Returns:
            Updated LLMConfig entity.

        Raises:
            KeyError: If config_id does not exist.
            ValueError: If updated values violate invariants.
        """
        existing = self._repo.find_by_id(config_id)
        if existing is None:
            raise KeyError(f"LLM config {config_id!r} not found")

        try:
            from datetime import datetime, timezone

            updated = LLMConfig(
                id=existing.id,
                label=(label.strip() if label else existing.label),
                provider=(
                    existing.provider if provider is None
                    else LLMProvider.from_string(provider)
                ),
                api_key=(api_key.strip() if api_key is not None else existing.api_key),
                model=(model.strip() if model is not None else existing.model),
                base_url=(base_url.strip() if base_url else existing.base_url),
                is_active=existing.is_active,
                created_at=existing.created_at,
                updated_at=datetime.now(timezone.utc),
            )
        except InvalidLLMConfig as e:
            raise ValueError(str(e)) from e

        return self._repo.save(updated)

    # ------------------------------------------------------------------
    # Upsert by provider (used for bulk provider-settings sync)
    # ------------------------------------------------------------------

    def upsert_by_provider(
        self,
        provider: str,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
    ) -> LLMConfig:
        """Create or update the config for a given provider (label == provider).

        Uses provider string as the label so each provider has at most one
        canonical config entry.  The active flag is not changed on update.

        Args:
            provider: Provider string (e.g., 'openai', 'openai_compatible').
            api_key: API key (may be empty for OAuth/no-key providers).
            model: Model name (may be empty for openai_compatible).
            base_url: Optional base URL override.

        Returns:
            Created or updated LLMConfig entity.

        Raises:
            ValueError: If provider string is invalid.
        """
        existing = self._repo.find_by_provider(provider)
        if existing is not None:
            from datetime import datetime, timezone

            try:
                updated = LLMConfig(
                    id=existing.id,
                    label=existing.label,
                    provider=existing.provider,
                    api_key=api_key.strip() if api_key is not None else existing.api_key,
                    model=model.strip() if model is not None else existing.model,
                    base_url=base_url.strip() if base_url else None,
                    is_active=existing.is_active,
                    created_at=existing.created_at,
                    updated_at=datetime.now(timezone.utc),
                )
            except InvalidLLMConfig as e:
                raise ValueError(str(e)) from e
            return self._repo.save(updated)

        return self.create(
            label=provider.strip().lower(),
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )

    # ------------------------------------------------------------------
    # Activate
    # ------------------------------------------------------------------

    def activate(self, config_id: UUID) -> LLMConfig:
        """Set a config as the active LLM config.

        Atomically deactivates all other configs.

        Args:
            config_id: ID of the config to activate.

        Returns:
            The newly activated config.

        Raises:
            KeyError: If config_id does not exist.
        """
        existing = self._repo.find_by_id(config_id)
        if existing is None:
            raise KeyError(f"LLM config {config_id!r} not found")

        self._repo.set_active(config_id)
        return self._repo.find_by_id(config_id) or existing

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, config_id: UUID) -> None:
        """Delete a config.

        Args:
            config_id: ID of config to delete.

        Raises:
            KeyError: If config_id does not exist.
        """
        existing = self._repo.find_by_id(config_id)
        if existing is None:
            raise KeyError(f"LLM config {config_id!r} not found")

        self._repo.delete(config_id)
