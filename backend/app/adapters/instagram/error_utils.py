"""Shared error translation helpers for Instagram adapters."""

from __future__ import annotations

from app.adapters.instagram.exception_handler import instagram_exception_handler
from app.domain.instagram_failures import (
    InstagramAdapterError,
)  # re-export for adapter convenience

__all__ = [
    "translate_instagram_error",
    "attach_instagram_failure",
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


def attach_instagram_failure(error: Exception, failure) -> Exception:
    """Attach translated InstagramFailure metadata to an exception instance."""
    error._instagram_failure = failure  # type: ignore[attr-defined]
    return error


def translate_instagram_error(
    error: Exception,
    *,
    operation: str,
    account_id: str | None = None,
    username: str | None = None,
):
    """Translate a vendor exception using the catalog-driven handler.

    Side effects when ``account_id`` is provided:

    * **Rate-limit** (http_hint 429) — marks the account in the
      ``rate_limit_guard`` cooldown window.
    * **Dead session** (non-retryable + requires_user_action, e.g.
      ``login_required``) — evicts the stale client from
      ``client_repo`` so that ``_get_account_status()`` stops
      returning ``"active"`` for a broken session.
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

    if (
        account_id
        and not failure.retryable
        and failure.requires_user_action
        and failure.family == "private_auth"
    ):
        _evict_dead_session(account_id)

    return failure


def _evict_dead_session(account_id: str) -> None:
    """Remove a stale client + set status to 'error' after a fatal auth failure.

    Imported lazily to avoid circular imports at module load time.
    """
    try:
        from app.adapters.http.dependencies import get_services

        services = get_services()
        client_repo = services["_client_repo"]
        status_repo = services["_status_repo"]
        if client_repo.exists(account_id):
            client_repo.remove(account_id)
        status_repo.set(account_id, "error")
    except Exception:
        # Best-effort — never let eviction crash the error path.
        pass


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
