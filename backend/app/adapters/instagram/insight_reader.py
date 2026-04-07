"""Instagram insight reader adapter.

Maps instagrapi insights_media() and insights_media_feed_all() dict payloads
to stable MediaInsightSummary DTOs.
Normalizes vendor metric names and captures unknown metrics separately.
"""

from typing import Any, Optional

from app.application.dto.instagram_analytics_dto import MediaInsightSummary
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.error_utils import translate_instagram_error


class InstagramInsightReaderAdapter:
    """Adapter for reading Instagram post-level insights.

    Maps vendor analytics dicts to stable DTOs.
    Normalizes common metric names and preserves vendor variance in extra_metrics.
    """

    def __init__(self, client_repo: ClientRepository):
        """Initialize insight reader.

        Args:
            client_repo: Repository for retrieving authenticated clients.
        """
        self.client_repo = client_repo

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
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to get media insights
            insight_dict = client.insights_media(media_pk)

            # Map to DTO
            return self._map_insight_to_summary(media_pk, insight_dict)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_media_insight", account_id=account_id
            )
            raise ValueError(failure.user_message)

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
            post_type: Type of posts to retrieve.
            time_frame: Time window for insights.
            ordering: Sort order for results.
            count: Maximum posts to retrieve (0 = all available).

        Returns:
            List of MediaInsightSummary sorted by ordering.

        Raises:
            ValueError: If account not found or not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to list media insights
            insight_list = client.insights_media_feed_all(
                post_type=post_type,
                time_frame=time_frame,
                data_ordering=ordering,
                count=count,
            )

            # Map each insight to DTO
            results = []
            for insight_dict in insight_list:
                # Extract media_pk from vendor dict (varies by version)
                media_pk = insight_dict.get("media_pk") or insight_dict.get("pk")
                if media_pk:
                    results.append(self._map_insight_to_summary(media_pk, insight_dict))

            return results

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="list_media_insights", account_id=account_id
            )
            raise ValueError(failure.user_message)

    @staticmethod
    def _map_insight_to_summary(
        media_pk: int,
        insight_dict: Any,
    ) -> MediaInsightSummary:
        """Map vendor insight dict to MediaInsightSummary DTO.

        Args:
            media_pk: The media primary key.
            insight_dict: Vendor analytics dict from instagrapi.

        Returns:
            MediaInsightSummary with normalized metrics.
        """
        # Normalize common vendor metric names
        # instagrapi returns dicts with keys like 'impressions', 'reach', etc.
        reach_count = insight_dict.get("reach")
        impression_count = insight_dict.get("impressions")
        like_count = insight_dict.get("likes")
        comment_count = insight_dict.get("comments")
        share_count = insight_dict.get("shares")
        save_count = insight_dict.get("saves")
        video_view_count = insight_dict.get("video_views")
        profile_view_count = insight_dict.get("profile_views")

        # Collect all known vendor fields
        known_fields = {
            "reach",
            "impressions",
            "likes",
            "comments",
            "shares",
            "saves",
            "video_views",
            "profile_views",
            "media_pk",
            "pk",
        }

        # Capture unknown metrics in extra_metrics
        extra_metrics = {}
        if isinstance(insight_dict, dict):
            for key, value in insight_dict.items():
                if key not in known_fields:
                    extra_metrics[key] = value

        return MediaInsightSummary(
            media_pk=media_pk,
            reach_count=reach_count,
            impression_count=impression_count,
            like_count=like_count,
            comment_count=comment_count,
            share_count=share_count,
            save_count=save_count,
            video_view_count=video_view_count,
            profile_view_count=profile_view_count,
            extra_metrics=extra_metrics,
        )
