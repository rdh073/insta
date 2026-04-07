"""
Instagram discovery reader port.

Defines the application-facing contract for reading Location and Hashtag discovery data.
Separates public discovery reads from authenticated session management.
All media results use the shared MediaSummary DTO, never raw vendor Media.
"""

from typing import Protocol

from app.application.dto.instagram_discovery_dto import (
    LocationSummary,
    HashtagSummary,
)
from app.application.dto.instagram_media_dto import MediaSummary


class InstagramDiscoveryReader(Protocol):
    """
    Port for reading Instagram discovery data (Location and Hashtag).

    Handles location/hashtag searches and post retrieval for these discovery entities.
    Implementation depends on instagrapi; application layer depends on DTOs.
    All media results are returned as MediaSummary to prevent vendor leakage.
    """

    def search_locations(
        self,
        account_id: str,
        query: str,
        lat: float | None = None,
        lng: float | None = None,
    ) -> list[LocationSummary]:
        """
        Search for locations by name and optional coordinates.

        Args:
            account_id: The application account ID (for client lookup).
            query: Location name to search for.
            lat: Optional latitude for location-aware search.
            lng: Optional longitude for location-aware search.

        Returns:
            List of LocationSummary matching the search.

        Raises:
            Exception: If search fails or account not authenticated.
        """
        ...

    def get_location(self, account_id: str, location_pk: int) -> LocationSummary:
        """
        Get location metadata by primary key.

        Args:
            account_id: The application account ID (for client lookup).
            location_pk: The Instagram location primary key.

        Returns:
            LocationSummary with full metadata.

        Raises:
            Exception: If location not found or read fails.
        """
        ...

    def get_location_top_posts(
        self, account_id: str, location_pk: int, amount: int = 12
    ) -> list[MediaSummary]:
        """
        Get top (most engaged) posts from a location.

        Args:
            account_id: The application account ID (for client lookup).
            location_pk: The Instagram location primary key.
            amount: Number of posts to retrieve (default 12).

        Returns:
            List of MediaSummary for location's top posts.

        Raises:
            Exception: If location not found or read fails.
        """
        ...

    def get_location_recent_posts(
        self, account_id: str, location_pk: int, amount: int = 12
    ) -> list[MediaSummary]:
        """
        Get recent posts from a location.

        Args:
            account_id: The application account ID (for client lookup).
            location_pk: The Instagram location primary key.
            amount: Number of posts to retrieve (default 12).

        Returns:
            List of MediaSummary for location's recent posts.

        Raises:
            Exception: If location not found or read fails.
        """
        ...

    def search_hashtags(self, account_id: str, query: str) -> list[HashtagSummary]:
        """
        Search hashtags by query string.

        Args:
            account_id: The application account ID (for client lookup).
            query: Search query (with or without # prefix).

        Returns:
            List of HashtagSummary results.

        Raises:
            Exception: If search fails.
        """
        ...

    def get_hashtag(self, account_id: str, name: str) -> HashtagSummary:
        """
        Get hashtag metadata by name.

        Args:
            account_id: The application account ID (for client lookup).
            name: Hashtag name (with or without # prefix).

        Returns:
            HashtagSummary with full metadata.

        Raises:
            Exception: If hashtag not found or read fails.
        """
        ...

    def get_hashtag_top_posts(
        self, account_id: str, name: str, amount: int = 12
    ) -> list[MediaSummary]:
        """
        Get top (most engaged) posts with a hashtag.

        Args:
            account_id: The application account ID (for client lookup).
            name: Hashtag name (with or without # prefix).
            amount: Number of posts to retrieve (default 12).

        Returns:
            List of MediaSummary for hashtag's top posts.

        Raises:
            Exception: If hashtag not found or read fails.
        """
        ...

    def get_hashtag_recent_posts(
        self, account_id: str, name: str, amount: int = 12
    ) -> list[MediaSummary]:
        """
        Get recent posts with a hashtag.

        Args:
            account_id: The application account ID (for client lookup).
            name: Hashtag name (with or without # prefix).
            amount: Number of posts to retrieve (default 12).

        Returns:
            List of MediaSummary for hashtag's recent posts.

        Raises:
            Exception: If hashtag not found or read fails.
        """
        ...
