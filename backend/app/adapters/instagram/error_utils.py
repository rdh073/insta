"""Shared error translation helpers for Instagram adapters."""

from __future__ import annotations

from app.adapters.instagram.exception_handler import instagram_exception_handler
from app.domain.instagram_failures import (
    InstagramAdapterError,
)  # re-export for adapter convenience

__all__ = [
    "translate_instagram_error",
    "check_rate_limit",
    "InstagramRateLimitError",
    "InstagramAdapterError",
]


class InstagramRateLimitError(Exception):
    """Raised when Instagram responds with repeated 429 rate-limit errors.

    Distinct from ValueError (not-found / validation) so HTTP handlers can
    return a proper 429 status code instead of 400/404.

    Attributes:
        retry_after: Seconds remaining in the cooldown period (0 if unknown).
    """

    def __init__(self, message: str = "", retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def translate_instagram_error(
    error: Exception,
    *,
    operation: str,
    account_id: str | None = None,
    username: str | None = None,
):
    """Translate a vendor exception using the catalog-driven handler.

    Side effect: if the translated failure has http_hint == 429 and
    ``account_id`` is provided, the account is automatically marked as
    rate-limited in the module-level ``rate_limit_guard`` so that subsequent
    calls are blocked during the cooldown window.
    """
    from app.adapters.instagram.rate_limit_guard import rate_limit_guard

    failure = instagram_exception_handler.handle(
        error,
        operation=operation,
        account_id=account_id,
        username=username,
    )

    if failure.http_hint == 429 and account_id:
        rate_limit_guard.mark_limited(
            account_id, failure_code=failure.code, username=username
        )

    return failure


def check_rate_limit(account_id: str) -> None:
    """Raise InstagramRateLimitError if the account is currently cooling down.

    Call this at the start of any adapter method that makes an Instagram API
    call to short-circuit immediately instead of wasting a network request.

    Args:
        account_id: The application account ID.

    Raises:
        InstagramRateLimitError: If the account is currently rate-limited.
    """
    from app.adapters.instagram.rate_limit_guard import rate_limit_guard

    limited, retry_after = rate_limit_guard.is_limited(account_id)
    if limited:
        raise InstagramRateLimitError(
            f"Account {account_id} is rate-limited. Retry in {retry_after:.0f}s.",
            retry_after=retry_after,
        )
