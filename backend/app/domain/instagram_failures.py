"""
Instagram failure domain model.

Application-owned failure semantics for Instagram integration.
These DTOs form the stable failure contract between infrastructure adapters
and application/HTTP layers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstagramFailure:
    """
    Represents a stable, application-owned Instagram failure.

    This model isolates application code from vendor exception classes
    and enables consistent failure handling across all Instagram flows.
    """

    code: str
    """Stable failure code (e.g., 'two_factor_required', 'bad_password')."""

    family: str
    """Failure family for grouping (e.g., 'auth', 'challenge', 'proxy')."""

    retryable: bool
    """Whether the operation can be safely retried."""

    requires_user_action: bool
    """Whether the user must take action to resolve (e.g., enter 2FA code)."""

    user_message: str
    """User-friendly message suitable for UI display."""

    http_hint: int | None = None
    """Suggested HTTP status code for REST responses."""

    detail: str | None = None
    """Additional context for logging/debugging (not user-facing)."""


class InstagramAdapterError(Exception):
    """Raised by Instagram adapters to carry translated failure metadata across
    the adapter boundary.

    Callers (use cases) can catch this directly and read ``exc.failure`` to
    distinguish auth/challenge/2FA/transient failures without re-running the
    error handler, preserving the original ``InstagramFailure`` semantics.
    """

    def __init__(self, failure: InstagramFailure) -> None:
        super().__init__(failure.user_message)
        self.failure = failure
