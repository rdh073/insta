"""Failure specification model for Instagram exception translation."""

from dataclasses import dataclass

from app.domain.instagram_failures import InstagramFailure


@dataclass(frozen=True)
class FailureSpec:
    """Specification for an exception family mapping."""

    code: str
    """Stable failure code (e.g., 'two_factor_required')."""

    family: str
    """Failure family (e.g., 'auth', 'challenge', 'proxy')."""

    retryable: bool
    """Whether the operation can be safely retried."""

    requires_user_action: bool
    """Whether the user must take manual action."""

    user_message: str
    """User-friendly message for UI display."""

    http_hint: int | None = None
    """Suggested HTTP status code."""

    def to_failure(self, detail: str | None = None) -> InstagramFailure:
        """Convert spec to failure instance."""
        return InstagramFailure(
            code=self.code,
            family=self.family,
            retryable=self.retryable,
            requires_user_action=self.requires_user_action,
            user_message=self.user_message,
            http_hint=self.http_hint,
            detail=detail,
        )
