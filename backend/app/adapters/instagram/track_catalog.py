"""Instagram track catalog adapter.

Maps instagrapi Track vendor objects from search_music() and track_info_by_canonical_id()
to stable TrackSummary and TrackDetail DTOs.
Keeps vendor Track objects inside the adapter only.
"""

from typing import Any, Optional, Union

from app.application.dto.instagram_analytics_dto import (
    TrackSummary,
    TrackDetail,
)
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.error_utils import translate_instagram_error


class InstagramTrackCatalogAdapter:
    """Adapter for searching and retrieving music tracks.

    Maps vendor Track objects to stable DTOs.
    Centralizes vendor-to-DTO translation for track catalog operations.
    """

    def __init__(self, client_repo: ClientRepository):
        """Initialize track catalog adapter.

        Args:
            client_repo: Repository for retrieving authenticated clients.
        """
        self.client_repo = client_repo

    def search_tracks(
        self,
        account_id: str,
        query: str,
        limit: int = 20,
    ) -> list[TrackSummary]:
        """Search for music tracks by query.

        Args:
            account_id: The application account ID (for client lookup).
            query: Search string (track name, artist, etc.).
            limit: Maximum tracks to return.

        Returns:
            List of TrackSummary results matching query.

        Raises:
            ValueError: If account not found or not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # instagrapi 2.3.0 search_music signature is query-only.
            tracks = client.search_music(query) or []
            safe_limit = max(limit, 0)
            limited_tracks = list(tracks)[:safe_limit]

            # Map each track to DTO
            return [self._map_track_to_summary(t) for t in limited_tracks]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="search_tracks", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def get_track(
        self,
        account_id: str,
        canonical_id: Union[str, int],
    ) -> TrackDetail:
        """Get detailed information for a specific track.

        Args:
            account_id: The application account ID (for client lookup).
            canonical_id: Stable track identifier (string or int).

        Returns:
            TrackDetail with full metadata.

        Raises:
            ValueError: If account not found, not authenticated, or track not found.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to get track info
            # canonical_id is typically an int for instagrapi, but we accept both
            track = client.track_info_by_canonical_id(canonical_id)

            # Map to detail DTO
            return self._map_track_to_detail(track)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_track", account_id=account_id
            )
            raise ValueError(failure.user_message)

    @staticmethod
    def _map_track_to_summary(track: Any) -> TrackSummary:
        """Map vendor Track object to TrackSummary DTO.

        Args:
            track: instagrapi Track object.

        Returns:
            TrackSummary DTO.
        """
        return TrackSummary(
            canonical_id=InstagramTrackCatalogAdapter._get_canonical_id(track),
            title=getattr(track, "title", None) or getattr(track, "name", None),
            artist_name=getattr(track, "artist_name", None),
            duration_in_ms=getattr(track, "duration_in_ms", None),
        )

    @staticmethod
    def _map_track_to_detail(track: Any) -> TrackDetail:
        """Map vendor Track object to TrackDetail DTO.

        Args:
            track: instagrapi Track object.

        Returns:
            TrackDetail DTO.
        """
        summary = InstagramTrackCatalogAdapter._map_track_to_summary(track)

        return TrackDetail(
            summary=summary,
            uri=getattr(track, "uri", None),
            display_artist=getattr(track, "display_artist", None)
            or getattr(track, "artist_name", None),
        )

    @staticmethod
    def _get_canonical_id(track: Any) -> str:
        """Extract canonical ID from vendor Track object.

        Handles vendor field name variations.

        Args:
            track: instagrapi Track object.

        Returns:
            Canonical ID as string.
        """
        # Try common field names used by instagrapi
        canonical_id = (
            getattr(track, "canonical_id", None)
            or getattr(track, "id", None)
            or getattr(track, "pk", None)
        )

        if canonical_id is None:
            raise ValueError("Track object has no canonical_id, id, or pk field")

        return str(canonical_id)
