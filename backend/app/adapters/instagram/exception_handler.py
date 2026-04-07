"""
Instagrapi exception handler adapter.

Implements the application-facing error handler using the catalog registry.
Transforms vendor exceptions into stable application failures.
"""

from app.domain.instagram_failures import InstagramFailure
from app.adapters.instagram.exception_catalog import (
    EXCEPTION_REGISTRY,
    SPEC_CLIENT_UNKNOWN_ERROR,
    SPEC_RATE_LIMIT_ERROR,
)


class CatalogDrivenInstagramExceptionHandler:
    """
    Catalog-driven handler that maps vendor exceptions to application failures.

    Uses the exception registry to classify exceptions consistently across
    all Instagram flows. Unknown exceptions safely map to unknown_instagram_error.
    """

    def handle(
        self,
        error: Exception,
        *,
        operation: str,
        account_id: str | None = None,
        username: str | None = None,
    ) -> InstagramFailure:
        """
        Translate a vendor exception into an application failure.

        Args:
            error: The vendor exception to handle.
            operation: The Instagram operation that failed
                (e.g., "login", "post_media", "get_account_info").
            account_id: The account ID if available.
            username: The username if available.

        Returns:
            InstagramFailure: A stable, app-owned failure representation.

        Note:
            Unknown exceptions map to unknown_instagram_error.
            All returned failures include appropriate http_hint values.
        """
        error_class = type(error)

        # Check exact type match first
        if error_class in EXCEPTION_REGISTRY:
            spec = EXCEPTION_REGISTRY[error_class]
            return spec.to_failure(detail=str(error))

        # Check for base class matches
        for exc_class in EXCEPTION_REGISTRY:
            if isinstance(error, exc_class):
                spec = EXCEPTION_REGISTRY[exc_class]
                return spec.to_failure(detail=str(error))

        # urllib3 / requests retry exhaustion carrying repeated 429 responses.
        # These never reach instagrapi's exception layer, so we detect them by
        # message text before falling back to the generic unknown-error spec.
        error_str = str(error)
        if "429" in error_str and (
            "too many" in error_str.lower() or "retry" in error_str.lower()
        ):
            return SPEC_RATE_LIMIT_ERROR.to_failure(detail=error_str)

        # Unknown exception fallback
        detail = error_str if error_str else f"{error_class.__name__} (no message)"
        return SPEC_CLIENT_UNKNOWN_ERROR.to_failure(detail=detail)


# Singleton instance for dependency injection
instagram_exception_handler = CatalogDrivenInstagramExceptionHandler()
