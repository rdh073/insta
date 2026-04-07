"""
Instagram error handling port.

Defines the application-facing contract for translating vendor exceptions
into stable, app-owned failure semantics.
"""

from typing import Protocol

from app.domain.instagram_failures import InstagramFailure


class InstagramExceptionHandler(Protocol):
    """
    Application-facing error handler for Instagram operations.

    Transforms vendor exceptions into stable InstagramFailure objects.
    Implementations must handle all documented instagrapi exception families.
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
            Unknown exceptions must map to unknown_instagram_error.
            All returned failures must have http_hint set appropriately.
        """
        ...
