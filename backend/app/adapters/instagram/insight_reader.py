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

    _METRIC_ALIASES = {
        "reach_count": ("reach", "reach_count"),
        "impression_count": ("impressions", "impression_count"),
        "like_count": ("likes", "like_count"),
        "comment_count": ("comments", "comment_count"),
        "share_count": ("shares", "share_count"),
        "save_count": ("saves", "save_count"),
        "video_view_count": ("video_views", "video_view_count"),
        "profile_view_count": ("profile_views", "profile_view_count"),
    }
    _MEDIA_PK_KEYS = ("media_pk", "pk", "media_id", "id", "instagram_media_id")

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
            insight_payload = client.insights_media_feed_all(
                post_type=post_type,
                time_frame=time_frame,
                data_ordering=ordering,
                count=count,
            )

            # Map each insight entry (flat dict or GraphQL edge/node payload) to DTO
            results = []
            for insight_dict in self._extract_insight_entries(insight_payload):
                media_pk = self._extract_media_pk(insight_dict)
                if media_pk is not None:
                    results.append(self._map_insight_to_summary(media_pk, insight_dict))

            return results

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="list_media_insights", account_id=account_id
            )
            raise ValueError(failure.user_message)

    @classmethod
    def _extract_insight_entries(cls, payload: Any) -> list[dict[str, Any]]:
        """Normalize vendor payload to a list of insight dicts."""
        if isinstance(payload, list):
            raw_entries = payload
        elif isinstance(payload, dict):
            raw_entries = cls._extract_entries_from_payload_dict(payload)
        else:
            return []

        entries: list[dict[str, Any]] = []
        for item in raw_entries:
            normalized = cls._coerce_insight_entry(item)
            if normalized is not None:
                entries.append(normalized)
        return entries

    @classmethod
    def _extract_entries_from_payload_dict(cls, payload: dict[str, Any]) -> list[Any]:
        """Extract insight entry lists from known GraphQL container shapes."""

        def _dig(data: Any, *path: str) -> Any:
            cur = data
            for key in path:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(key)
            return cur

        for path in (
            (
                "data",
                "shadow_instagram_user",
                "business_manager",
                "top_posts_unit",
                "top_posts",
                "edges",
            ),
            (
                "data",
                "shadow_instagram_user",
                "business_manager",
                "top_posts_unit",
                "top_posts",
                "nodes",
            ),
            ("top_posts", "edges"),
            ("top_posts", "nodes"),
            ("edges",),
            ("nodes",),
            ("medias",),
        ):
            entries = _dig(payload, *path)
            if isinstance(entries, list):
                return entries

        # Fallback for a single edge/node/flat insight dict payload
        return [payload]

    @classmethod
    def _coerce_insight_entry(cls, item: Any) -> Optional[dict[str, Any]]:
        """Normalize one entry, flattening GraphQL edge->node when present."""
        if not isinstance(item, dict):
            return None

        node = item.get("node")
        if isinstance(node, dict):
            # Keep node metrics authoritative, but retain edge-level fallback fields.
            merged = dict(node)
            for key, value in item.items():
                if key == "node":
                    continue
                if key not in merged:
                    merged[key] = value
            return cls._flatten_metric_containers(merged)

        return cls._flatten_metric_containers(item)

    @staticmethod
    def _flatten_metric_containers(insight_dict: dict[str, Any]) -> dict[str, Any]:
        """Flatten nested metric containers into top-level keys."""
        flattened = dict(insight_dict)
        for container_key in ("metrics", "insights", "organic_values", "values"):
            nested = flattened.get(container_key)
            if isinstance(nested, dict):
                for key, value in nested.items():
                    if key not in flattened:
                        flattened[key] = value
                flattened.pop(container_key, None)
        return flattened

    @classmethod
    def _extract_media_pk(cls, insight_dict: dict[str, Any]) -> Optional[int]:
        """Extract numeric media PK from flat or nested insight payload shapes."""
        for key in cls._MEDIA_PK_KEYS:
            media_pk = cls._parse_media_pk(insight_dict.get(key))
            if media_pk is not None:
                return media_pk

        media_obj = insight_dict.get("media")
        if isinstance(media_obj, dict):
            for key in cls._MEDIA_PK_KEYS:
                media_pk = cls._parse_media_pk(media_obj.get(key))
                if media_pk is not None:
                    return media_pk

        return None

    @classmethod
    def _parse_media_pk(cls, value: Any) -> Optional[int]:
        """Parse media PK from int/str variants including IGID-style '<pk>_<user>'."""
        if value is None or isinstance(value, bool):
            return None

        if isinstance(value, int):
            return value if value > 0 else None

        if isinstance(value, float):
            if value.is_integer() and value > 0:
                return int(value)
            return None

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            # GraphQL IDs can be "<media_pk>_<owner_pk>".
            if "_" in raw:
                raw = raw.split("_", 1)[0]
            if not raw.isdigit():
                return None
            parsed = int(raw)
            return parsed if parsed > 0 else None

        if isinstance(value, dict):
            for key in cls._MEDIA_PK_KEYS:
                parsed = cls._parse_media_pk(value.get(key))
                if parsed is not None:
                    return parsed

        return None

    @classmethod
    def _get_metric_value(
        cls, insight_dict: dict[str, Any], metric_name: str
    ) -> Optional[int]:
        """Resolve a metric value across alias keys."""
        for alias in cls._METRIC_ALIASES[metric_name]:
            if alias in insight_dict:
                return insight_dict.get(alias)
        return None

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
        insight = insight_dict if isinstance(insight_dict, dict) else {}

        # Collect all known vendor fields
        known_fields = {"media", "node", *InstagramInsightReaderAdapter._MEDIA_PK_KEYS}
        for aliases in InstagramInsightReaderAdapter._METRIC_ALIASES.values():
            known_fields.update(aliases)

        # Capture unknown metrics in extra_metrics
        extra_metrics = {}
        for key, value in insight.items():
            if key not in known_fields:
                extra_metrics[key] = value

        return MediaInsightSummary(
            media_pk=media_pk,
            reach_count=InstagramInsightReaderAdapter._get_metric_value(
                insight, "reach_count"
            ),
            impression_count=InstagramInsightReaderAdapter._get_metric_value(
                insight, "impression_count"
            ),
            like_count=InstagramInsightReaderAdapter._get_metric_value(
                insight, "like_count"
            ),
            comment_count=InstagramInsightReaderAdapter._get_metric_value(
                insight, "comment_count"
            ),
            share_count=InstagramInsightReaderAdapter._get_metric_value(
                insight, "share_count"
            ),
            save_count=InstagramInsightReaderAdapter._get_metric_value(
                insight, "save_count"
            ),
            video_view_count=InstagramInsightReaderAdapter._get_metric_value(
                insight, "video_view_count"
            ),
            profile_view_count=InstagramInsightReaderAdapter._get_metric_value(
                insight, "profile_view_count"
            ),
            extra_metrics=extra_metrics,
        )
