"""Insight use cases - application orchestration for Instagram post analytics.

Enforces account preconditions and normalizes all filter parameters before
delegating to the InstagramInsightReader port. Consumers (router, tool_registry,
ai_copilot) must use this class instead of the adapter directly.

Filter normalization policy (owned here, not in router):
  - post_type, time_frame, ordering are uppercased and validated against
    known enum sets before the port is called.
  - Unknown values raise ValueError with a helpful message listing accepted values.
  - count=0 is passed through (means "all available").
"""

from __future__ import annotations

from app.application.dto.instagram_analytics_dto import MediaInsightSummary
from app.application.ports.instagram_insights import InstagramInsightReader
from app.application.ports.repositories import AccountRepository, ClientRepository

# ---------------------------------------------------------------------------
# Accepted filter sets (application-owned enums)
# ---------------------------------------------------------------------------

_VALID_POST_TYPES = frozenset({"ALL", "PHOTO", "VIDEO", "CAROUSEL"})
_VALID_TIME_FRAMES = frozenset({"TWO_YEARS", "ONE_YEAR", "SIX_MONTHS", "MONTH", "WEEK"})
_VALID_ORDERINGS = frozenset({
    "REACH_COUNT",
    "IMPRESSIONS",
    "ENGAGEMENT",
    "LIKE_COUNT",
    "COMMENT_COUNT",
    "SHARE_COUNT",
    "SAVE_COUNT",
})

_DEFAULT_POST_TYPE = "ALL"
_DEFAULT_TIME_FRAME = "TWO_YEARS"
_DEFAULT_ORDERING = "REACH_COUNT"


class InsightUseCases:
    """Application orchestration for Instagram post-level analytics.

    Owns precondition enforcement (account exists, authenticated),
    filter normalization (post_type / time_frame / ordering), and
    media_pk / count validation.
    The underlying InstagramInsightReader port handles vendor calls and DTO mapping.
    """

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        insight_reader: InstagramInsightReader,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.insight_reader = insight_reader

    # -------------------------------------------------------------------------
    # Precondition + normalization helpers
    # -------------------------------------------------------------------------

    def _require_authenticated(self, account_id: str) -> None:
        """Raise ValueError if account does not exist or is not authenticated."""
        if not self.account_repo.get(account_id):
            raise ValueError(f"Account {account_id!r} not found")
        if not self.client_repo.exists(account_id):
            raise ValueError(f"Account {account_id!r} is not authenticated")

    @staticmethod
    def _normalize_post_type(value: str) -> str:
        """Uppercase and validate post_type.

        Raises:
            ValueError: When value is not one of the accepted post types.
        """
        normalized = value.strip().upper()
        if normalized not in _VALID_POST_TYPES:
            accepted = ", ".join(sorted(_VALID_POST_TYPES))
            raise ValueError(
                f"Invalid post_type {value!r}. Accepted values: {accepted}"
            )
        return normalized

    @staticmethod
    def _normalize_time_frame(value: str) -> str:
        """Uppercase and validate time_frame.

        Raises:
            ValueError: When value is not one of the accepted time frames.
        """
        normalized = value.strip().upper()
        if normalized not in _VALID_TIME_FRAMES:
            accepted = ", ".join(sorted(_VALID_TIME_FRAMES))
            raise ValueError(
                f"Invalid time_frame {value!r}. Accepted values: {accepted}"
            )
        return normalized

    @staticmethod
    def _normalize_ordering(value: str) -> str:
        """Uppercase and validate ordering.

        Raises:
            ValueError: When value is not one of the accepted orderings.
        """
        normalized = value.strip().upper()
        if normalized not in _VALID_ORDERINGS:
            accepted = ", ".join(sorted(_VALID_ORDERINGS))
            raise ValueError(
                f"Invalid ordering {value!r}. Accepted values: {accepted}"
            )
        return normalized

    # -------------------------------------------------------------------------
    # Read operations
    # -------------------------------------------------------------------------

    def get_media_insight(
        self,
        account_id: str,
        media_pk: int,
    ) -> MediaInsightSummary:
        """Retrieve analytics for a specific post.

        Args:
            account_id: Application account ID.
            media_pk: Instagram media primary key (positive integer).

        Returns:
            MediaInsightSummary with normalized post metrics.

        Raises:
            ValueError: If account not found, not authenticated, or media_pk invalid.
        """
        self._require_authenticated(account_id)
        if not isinstance(media_pk, int) or media_pk <= 0:
            raise ValueError(f"media_pk must be a positive integer, got {media_pk!r}")
        return self.insight_reader.get_media_insight(account_id, media_pk)

    def list_media_insights(
        self,
        account_id: str,
        post_type: str = _DEFAULT_POST_TYPE,
        time_frame: str = _DEFAULT_TIME_FRAME,
        ordering: str = _DEFAULT_ORDERING,
        count: int = 0,
    ) -> list[MediaInsightSummary]:
        """List analytics for multiple posts, with filtering and ordering.

        Filter values are case-insensitive (normalized to uppercase internally).
        count=0 means "all available posts" — pass a positive integer to cap results.

        Args:
            account_id: Application account ID.
            post_type: Post type filter. One of: ALL, PHOTO, VIDEO, CAROUSEL.
            time_frame: Time window. One of: TWO_YEARS, ONE_YEAR, SIX_MONTHS, MONTH, WEEK.
            ordering: Sort order. One of: REACH_COUNT, IMPRESSIONS, ENGAGEMENT,
                      LIKE_COUNT, COMMENT_COUNT, SHARE_COUNT, SAVE_COUNT.
            count: Maximum posts to retrieve. 0 = all available.

        Returns:
            List of MediaInsightSummary sorted by ordering.

        Raises:
            ValueError: If account not found, not authenticated, or any filter is invalid.
        """
        self._require_authenticated(account_id)
        norm_post_type = self._normalize_post_type(post_type)
        norm_time_frame = self._normalize_time_frame(time_frame)
        norm_ordering = self._normalize_ordering(ordering)
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"count must be a non-negative integer, got {count!r}")
        return self.insight_reader.list_media_insights(
            account_id,
            post_type=norm_post_type,
            time_frame=norm_time_frame,
            ordering=norm_ordering,
            count=count,
        )
