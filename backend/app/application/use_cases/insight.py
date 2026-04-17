"""Insight use cases - application orchestration for Instagram post analytics.

Enforces account preconditions and normalizes all filter parameters before
delegating to the InstagramInsightReader port. Consumers (router, tool_registry,
ai_copilot) must use this class instead of the adapter directly.

Filter normalization policy (owned here, not in router):
  - post_type, time_frame, ordering are uppercased, alias-mapped, and validated
    against instagrapi-supported enum sets before the port is called.
  - Unknown values raise ValueError with a helpful message listing accepted values.
  - count=0 is passed through (means "all available").
"""

from __future__ import annotations

from app.application.dto.instagram_analytics_dto import (
    AccountInsightSummary,
    MediaInsightSummary,
)
from app.application.ports.instagram_insights import InstagramInsightReader
from app.application.ports.repositories import AccountRepository, ClientRepository

# ---------------------------------------------------------------------------
# Accepted filter sets (instagrapi 2.3.0 enums)
# ---------------------------------------------------------------------------

_VALID_POST_TYPES = frozenset({"ALL", "CAROUSEL_V2", "IMAGE", "SHOPPING", "VIDEO"})
_VALID_TIME_FRAMES = frozenset(
    {"ONE_WEEK", "ONE_MONTH", "THREE_MONTHS", "SIX_MONTHS", "ONE_YEAR", "TWO_YEARS"}
)
_VALID_ORDERINGS = frozenset({
    "BIO_LINK_CLICK",
    "COMMENT_COUNT",
    "FOLLOW",
    "IMPRESSION_COUNT",
    "LIKE_COUNT",
    "PROFILE_VIEW",
    "REACH_COUNT",
    "SHARE_COUNT",
    "SAVE_COUNT",
    "VIDEO_VIEW_COUNT",
})

_DEFAULT_POST_TYPE = "ALL"
_DEFAULT_TIME_FRAME = "TWO_YEARS"
_DEFAULT_ORDERING = "REACH_COUNT"

_POST_TYPE_ALIASES = {
    "PHOTO": "IMAGE",
    "CAROUSEL": "CAROUSEL_V2",
}

_TIME_FRAME_ALIASES = {
    "WEEK": "ONE_WEEK",
    "MONTH": "ONE_MONTH",
}

_ORDERING_ALIASES = {
    "IMPRESSIONS": "IMPRESSION_COUNT",
    # Legacy pseudo-ordering used by older clients. Policy: map to the closest
    # vendor-supported engagement proxy.
    "ENGAGEMENT": "LIKE_COUNT",
}


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
    def _normalize_enum(
        value: str,
        *,
        field: str,
        valid_values: frozenset[str],
        aliases: dict[str, str] | None = None,
    ) -> str:
        """Uppercase, alias-map, and validate enum-like string values."""
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string, got {value!r}")

        normalized = value.strip().upper()
        canonical = aliases.get(normalized, normalized) if aliases else normalized
        if canonical not in valid_values:
            accepted = ", ".join(sorted(valid_values))
            raise ValueError(
                f"Invalid {field} {value!r}. Accepted values: {accepted}"
            )
        return canonical

    @staticmethod
    def _normalize_post_type(value: str) -> str:
        """Normalize post_type to an instagrapi-supported value."""
        return InsightUseCases._normalize_enum(
            value,
            field="post_type",
            valid_values=_VALID_POST_TYPES,
            aliases=_POST_TYPE_ALIASES,
        )

    @staticmethod
    def _normalize_time_frame(value: str) -> str:
        """Normalize time_frame to an instagrapi-supported value."""
        return InsightUseCases._normalize_enum(
            value,
            field="time_frame",
            valid_values=_VALID_TIME_FRAMES,
            aliases=_TIME_FRAME_ALIASES,
        )

    @staticmethod
    def _normalize_ordering(value: str) -> str:
        """Normalize ordering to an instagrapi-supported value."""
        return InsightUseCases._normalize_enum(
            value,
            field="ordering",
            valid_values=_VALID_ORDERINGS,
            aliases=_ORDERING_ALIASES,
        )

    # -------------------------------------------------------------------------
    # Read operations
    # -------------------------------------------------------------------------

    def get_account_insight(self, account_id: str) -> AccountInsightSummary:
        """Retrieve account-level analytics (profile dashboard).

        Args:
            account_id: Application account ID.

        Returns:
            AccountInsightSummary with normalized account metrics.

        Raises:
            ValueError: If account not found or not authenticated.
        """
        self._require_authenticated(account_id)
        return self.insight_reader.get_account_insight(account_id)

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
            post_type: Post type filter. One of: ALL, CAROUSEL_V2, IMAGE, SHOPPING,
                       VIDEO. Legacy aliases: PHOTO -> IMAGE, CAROUSEL -> CAROUSEL_V2.
            time_frame: Time window. One of: ONE_WEEK, ONE_MONTH, THREE_MONTHS,
                        SIX_MONTHS, ONE_YEAR, TWO_YEARS.
                        Legacy aliases: WEEK -> ONE_WEEK, MONTH -> ONE_MONTH.
            ordering: Sort order. One of: REACH_COUNT, LIKE_COUNT, FOLLOW, SHARE_COUNT,
                      BIO_LINK_CLICK, COMMENT_COUNT, IMPRESSION_COUNT, PROFILE_VIEW,
                      VIDEO_VIEW_COUNT, SAVE_COUNT.
                      Legacy aliases: IMPRESSIONS -> IMPRESSION_COUNT,
                      ENGAGEMENT -> LIKE_COUNT.
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
