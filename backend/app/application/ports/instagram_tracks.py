"""Port for accessing Instagram music track catalog.

Provides stable contract for track search and lookup without exposing
vendor Track objects to application code.

Track selection and playback are read-only and informational.
Publishing adapters will construct vendor Track objects from TrackReference
only when reels/clips features are implemented.
"""

from typing import Protocol, Union

from app.application.dto.instagram_analytics_dto import TrackSummary, TrackDetail


class InstagramTrackCatalog(Protocol):
    """Protocol for searching and retrieving music tracks.

    All methods are read-only and stateless.
    """

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
        ...

    def get_track(
        self,
        account_id: str,
        canonical_id: Union[str, int],
    ) -> TrackDetail:
        """Get detailed information for a specific track.

        Args:
            account_id: The application account ID (for client lookup).
            canonical_id: Stable track identifier (string or int, depending on vendor).

        Returns:
            TrackDetail with full metadata.

        Raises:
            ValueError: If account not found, not authenticated, or track not found.
        """
        ...
