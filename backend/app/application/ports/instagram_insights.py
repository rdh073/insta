"""Port for reading Instagram post-level insights.

Provides stable contract for accessing post analytics without exposing
instagrapi's analytics dict payloads to application code.
"""

from typing import Protocol

from app.application.dto.instagram_analytics_dto import (
    AccountInsightSummary,
    MediaInsightSummary,
)


class InstagramInsightReader(Protocol):
    """Protocol for reading post-level Instagram insights.

    All methods are read-only and stateless.
    """

    def get_account_insight(
        self,
        account_id: str,
    ) -> AccountInsightSummary:
        """Retrieve account-level insight metrics (profile dashboard).

        Args:
            account_id: The application account ID (for client lookup).

        Returns:
            AccountInsightSummary with profile-level metrics and any
            additional vendor fields captured in extra_metrics.

        Raises:
            ValueError: If account not found or not authenticated.
        """
        ...

    def get_media_insight(
        self,
        account_id: str,
        media_pk: int,
    ) -> MediaInsightSummary:
        """Retrieve insights for a specific post/media.

        Args:
            account_id: The application account ID (for client lookup).
            media_pk: Instagram media/post primary key.

        Returns:
            MediaInsightSummary with post metrics.

        Raises:
            ValueError: If account not found, not authenticated, or media not found.
        """
        ...

    def list_media_insights(
        self,
        account_id: str,
        post_type: str = "ALL",
        time_frame: str = "TWO_YEARS",
        ordering: str = "REACH_COUNT",
        count: int = 0,
    ) -> list[MediaInsightSummary]:
        """List insights for multiple media.

        Args:
            account_id: The application account ID (for client lookup).
            post_type: Type of posts to retrieve (e.g. "ALL", "IMAGE", "VIDEO", "CAROUSEL_V2").
            time_frame: Time window for insights (e.g. "TWO_YEARS", "ONE_YEAR", "ONE_MONTH").
            ordering: Sort order for results (e.g. "REACH_COUNT", "IMPRESSION_COUNT", "LIKE_COUNT").
            count: Maximum posts to retrieve (0 = all available).

        Returns:
            List of MediaInsightSummary sorted by ordering.

        Raises:
            ValueError: If account not found or not authenticated.
        """
        ...
