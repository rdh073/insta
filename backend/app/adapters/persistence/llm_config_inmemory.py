"""In-memory LLM config repository for development and testing.

Not persistent across restarts. Use SQLLLMConfigRepository for production.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from app.domain.llm_config import LLMConfig


class InMemoryLLMConfigRepository:
    """In-memory implementation of LLMConfigRepository port.

    Useful for development (memory backend) and unit tests.
    Not persistent across restarts.
    """

    def __init__(self) -> None:
        self._configs: dict[str, LLMConfig] = {}

    def save(self, config: LLMConfig) -> LLMConfig:
        self._configs[str(config.id)] = config
        return config

    def find_by_id(self, config_id: UUID) -> Optional[LLMConfig]:
        return self._configs.get(str(config_id))

    def find_all(self) -> list[LLMConfig]:
        return sorted(
            self._configs.values(),
            key=lambda c: c.created_at,
            reverse=True,
        )

    def find_active(self) -> Optional[LLMConfig]:
        for config in self._configs.values():
            if config.is_active:
                return config
        return None

    def delete(self, config_id: UUID) -> None:
        self._configs.pop(str(config_id), None)

    def set_active(self, config_id: UUID) -> None:
        key = str(config_id)
        if key not in self._configs:
            raise KeyError(f"LLM config {config_id!r} not found")

        now = datetime.now(timezone.utc)
        for cid, config in list(self._configs.items()):
            from dataclasses import replace
            updated = replace(config, is_active=(cid == key), updated_at=now)
            self._configs[cid] = updated

    def find_by_provider(self, provider: str) -> Optional[LLMConfig]:
        """Find config whose label matches the provider string."""
        key = (provider or "").strip().lower()
        for config in self._configs.values():
            if config.label.lower() == key:
                return config
        return None
