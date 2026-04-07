"""Shared error translation helpers for Instagram adapters."""

from __future__ import annotations

from app.adapters.instagram.exception_handler import instagram_exception_handler
from app.domain.instagram_failures import (
    InstagramAdapterError,
)  # re-export for adapter convenience

__all__ = [
    "translate_instagram_error",
    "InstagramRateLimitError",
    "InstagramAdapterError",
]


class InstagramRateLimitError(Exception):
    """Raised when Instagram responds with repeated 429 rate-limit errors.

    Distinct from ValueError (not-found / validation) so HTTP handlers can
    return a proper 429 status code instead of 400/404.
    """


def translate_instagram_error(
    error: Exception,
    *,
    operation: str,
    account_id: str | None = None,
    username: str | None = None,
):
    """Translate a vendor exception using the catalog-driven handler."""
    return instagram_exception_handler.handle(
        error,
        operation=operation,
        account_id=account_id,
        username=username,
    )
