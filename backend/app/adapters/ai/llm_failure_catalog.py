"""Application-owned failure families for LLM provider errors.

Maps vendor-specific exceptions to canonical failure types.
Prevents raw vendor error strings from leaking to application layer.

Failure families:
- auth: OAuth failures, token refresh failures, invalid credentials
- rate_limit: API rate limit exceeded, quota exceeded
- provider_unavailable: Service unreachable, 5xx errors, provider down
- invalid_request: Invalid model, bad parameters, unsupported feature
- transport_mismatch: Provider uses transport not supported by adapter
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass


class LLMFailureFamily(Enum):
    """Canonical failure families for LLM provider errors."""

    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_REQUEST = "invalid_request"
    TRANSPORT_MISMATCH = "transport_mismatch"


@dataclass(frozen=True)
class LLMFailure(Exception):
    """Application-owned failure type (never vendor-specific).

    Used by all adapters to translate provider-specific errors into
    canonical families. Application layer sees only these families,
    never raw vendor strings.

    Can be raised and caught as an exception. Always translates vendor
    details to canonical families before escaping adapter boundaries.
    """

    family: LLMFailureFamily
    """Canonical failure family."""

    message: str
    """Application-safe error message (no vendor details)."""

    provider: str
    """Provider name for context (openai, gemini, codex, claude_code, etc.)."""

    cause: Exception | None = None
    """Optional original exception (for logging, not for response)."""

    def __str__(self) -> str:
        return f"LLMFailure({self.family.value}, provider={self.provider}, msg={self.message!r})"


def translate_failure(
    original_error: Exception,
    family: LLMFailureFamily,
    provider: str,
    safe_message: str = None,
) -> LLMFailure:
    """Translate a vendor exception into an application-owned failure.

    Args:
        original_error: The original exception from vendor SDK
        family: Which failure family this maps to
        provider: Provider name (openai, gemini, claude_code, etc.)
        safe_message: Application-safe message. If None, uses str(original_error)

    Returns:
        LLMFailure with vendor exception hidden in cause
    """
    message = safe_message or f"{family.value} error from {provider}"
    return LLMFailure(
        family=family,
        message=message,
        provider=provider,
        cause=original_error,
    )
