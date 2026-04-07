"""Domain entity for LLM provider configuration.

Owns:
  - LLM provider identity and connection parameters
  - Business invariants: provider must be valid, api_key and model non-empty
  - Active config semantics (at most one active at a time enforced by use case)

No imports from framework, ORM, or vendor SDKs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class LLMProvider(Enum):
    """Supported LLM providers.

    Mirrors providers in openai_gateway.py ProviderConfig.CONFIGS.
    """
    OPENAI = "openai"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    ANTIGRAVITY = "antigravity"
    OPENAI_COMPATIBLE = "openai_compatible"
    OPENAI_CODEX = "openai_codex"
    CLAUDE_CODE = "claude_code"

    def is_no_key_provider(self) -> bool:
        """Return True if this provider does not require a stored API key."""
        return self.value in {"openai_codex", "claude_code", "openai_compatible"}

    @classmethod
    def from_string(cls, value: str) -> "LLMProvider":
        """Parse provider from string, case-insensitive.

        Raises:
            InvalidLLMConfig: If value is not a valid provider.
        """
        try:
            return cls(value.lower())
        except (ValueError, AttributeError):
            valid = ", ".join(m.value for m in cls)
            raise InvalidLLMConfig(
                f"LLMProvider: '{value}' is not valid. Must be one of: {valid}"
            )


class InvalidLLMConfig(ValueError):
    """Raised when an LLM config invariant is violated."""


class NoActiveLLMConfigError(RuntimeError):
    """Raised when no active LLM config is found and none is available."""


@dataclass
class LLMConfig:
    """LLM provider configuration aggregate root.

    Owns:
      - Provider identity (provider, model)
      - API key for provider authentication
      - Optional base URL override (for openai_compatible endpoints)
      - Activation status

    Invariants:
      - provider must be a valid LLMProvider
      - label must not be empty
      - api_key required unless provider.is_no_key_provider()
      - model may be empty for openai_compatible (user sets at runtime)
    """
    id: UUID
    label: str
    provider: LLMProvider
    api_key: str
    model: str
    is_active: bool = False
    base_url: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Enforce invariants."""
        if not self.label or not self.label.strip():
            raise InvalidLLMConfig("LLMConfig: label must not be empty")
        if not isinstance(self.provider, LLMProvider):
            raise InvalidLLMConfig(
                f"LLMConfig: provider must be LLMProvider enum, got {type(self.provider)}"
            )
        if not self.provider.is_no_key_provider() and not (self.api_key or "").strip():
            raise InvalidLLMConfig(
                f"LLMConfig: api_key required for provider '{self.provider.value}'"
            )

    @classmethod
    def create(
        cls,
        label: str,
        provider: str,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
    ) -> "LLMConfig":
        """Factory method that validates provider string and constructs entity.

        Args:
            label: Human-readable name for this config.
            provider: Provider string (e.g., 'openai', 'gemini').
            api_key: API key for provider authentication (empty allowed for OAuth/no-key providers).
            model: Model name (e.g., 'gpt-4o-mini').
            base_url: Optional base URL override for openai_compatible endpoints.

        Returns:
            LLMConfig with a new UUID and current timestamps.

        Raises:
            InvalidLLMConfig: If any invariant is violated.
        """
        return cls(
            id=uuid4(),
            label=label.strip() if label else "",
            provider=LLMProvider.from_string(provider),
            api_key=api_key.strip() if api_key else "",
            model=model.strip() if model else "",
            base_url=base_url.strip() if base_url else None,
        )

    def masked_api_key(self) -> str:
        """Return a masked version of the API key (last 4 chars only).

        Suitable for display in API responses without exposing the full key.

        Returns:
            Masked key like '...ab12', '***' if key is very short, or '' if no key.
        """
        if not self.api_key:
            return ""
        if len(self.api_key) <= 4:
            return "***"
        return f"...{self.api_key[-4:]}"

    def __str__(self) -> str:
        status = "active" if self.is_active else "inactive"
        return (
            f"LLMConfig(id={self.id}, label={self.label!r}, "
            f"provider={self.provider.value}, model={self.model}, status={status})"
        )
