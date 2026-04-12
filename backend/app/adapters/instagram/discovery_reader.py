"""
Instagram discovery reader adapter.

Maps instagrapi Location and Hashtag objects to stable DTOs.
Routes all media results through the shared MediaSummary contract.
"""

from typing import Any, Optional

from app.application.dto.instagram_discovery_dto import (
    LocationSummary,
    HashtagSummary,
)
from app.application.dto.instagram_media_dto import MediaSummary
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.client_guard import get_guarded_client
from app.adapters.instagram.media_reader import InstagramMediaReaderAdapter
from app.adapters.instagram.error_utils import translate_instagram_error


class InstagramDiscoveryReaderAdapter:
    """
    Adapter for reading Instagram discovery data (Location and Hashtag) via instagrapi.

    Maps vendor Location, Hashtag objects to stable DTOs.
    Centralizes vendor-to-DTO translation for discovery reads.
    All media results are converted to MediaSummary to prevent vendor leakage.
    """

    def __init__(self, client_repo: ClientRepository):
        """
        Initialize discovery reader.

        Args:
            client_repo: Repository for retrieving authenticated clients.
        """
        self.client_repo = client_repo
        self.media_reader = InstagramMediaReaderAdapter(client_repo)

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
            List of LocationSummary.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Call vendor method to search for places
            locations = client.fbsearch_places(query, lat=lat, lng=lng)

            # Map each location to DTO
            return [self._map_location_to_summary(loc) for loc in locations]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="search_locations", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def get_location(self, account_id: str, location_pk: int) -> LocationSummary:
        """
        Get location metadata by primary key.

        Args:
            account_id: The application account ID (for client lookup).
            location_pk: The Instagram location primary key.

        Returns:
            LocationSummary.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Call vendor method to get location
            location = client.location_info(location_pk)

            # Map to DTO
            return self._map_location_to_summary(location)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_location", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def get_location_top_posts(
        self, account_id: str, location_pk: int, amount: int = 12
    ) -> list[MediaSummary]:
        """
        Get top posts from a location.

        Args:
            account_id: The application account ID (for client lookup).
            location_pk: The Instagram location primary key.
            amount: Number of posts to retrieve.

        Returns:
            List of MediaSummary.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Call vendor method to get top posts
            medias = client.location_medias_top(location_pk, amount=amount)

            # Map each media to DTO
            return [
                InstagramMediaReaderAdapter._map_media_to_summary(media)
                for media in medias
            ]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_location_top_posts", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def get_location_recent_posts(
        self, account_id: str, location_pk: int, amount: int = 12
    ) -> list[MediaSummary]:
        """
        Get recent posts from a location.

        Args:
            account_id: The application account ID (for client lookup).
            location_pk: The Instagram location primary key.
            amount: Number of posts to retrieve.

        Returns:
            List of MediaSummary.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Call vendor method to get recent posts
            medias = client.location_medias_recent(location_pk, amount=amount)

            # Map each media to DTO
            return [
                InstagramMediaReaderAdapter._map_media_to_summary(media)
                for media in medias
            ]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_location_recent_posts", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def search_hashtags(self, account_id: str, query: str) -> list[HashtagSummary]:
        """
        Search hashtags by query string.

        Args:
            account_id: The application account ID (for client lookup).
            query: Search query (with or without # prefix).

        Returns:
            List of HashtagSummary results.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            normalized = query.lstrip("#")
            hashtags = client.search_hashtags(normalized)
            return [self._map_hashtag_to_summary(ht) for ht in hashtags]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="search_hashtags", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def get_hashtag(self, account_id: str, name: str) -> HashtagSummary:
        """
        Get hashtag metadata by name.

        Args:
            account_id: The application account ID (for client lookup).
            name: Hashtag name (with or without # prefix).

        Returns:
            HashtagSummary.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Normalize hashtag name (remove # if present)
            normalized_name = name.lstrip("#")

            # Call vendor method to get hashtag
            hashtag = client.hashtag_info(normalized_name)

            # Map to DTO
            return self._map_hashtag_to_summary(hashtag)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_hashtag", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def get_hashtag_top_posts(
        self, account_id: str, name: str, amount: int = 12
    ) -> list[MediaSummary]:
        """
        Get top posts with a hashtag.

        Args:
            account_id: The application account ID (for client lookup).
            name: Hashtag name (with or without # prefix).
            amount: Number of posts to retrieve.

        Returns:
            List of MediaSummary.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Normalize hashtag name
            normalized_name = name.lstrip("#")

            # Call vendor method to get top posts
            medias = client.hashtag_medias_top(normalized_name, amount=amount)

            # Map each media to DTO
            return [
                InstagramMediaReaderAdapter._map_media_to_summary(media)
                for media in medias
            ]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_hashtag_top_posts", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def get_hashtag_recent_posts(
        self, account_id: str, name: str, amount: int = 12
    ) -> list[MediaSummary]:
        """
        Get recent posts with a hashtag.

        Args:
            account_id: The application account ID (for client lookup).
            name: Hashtag name (with or without # prefix).
            amount: Number of posts to retrieve.

        Returns:
            List of MediaSummary.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Normalize hashtag name
            normalized_name = name.lstrip("#")

            # Call vendor method to get recent posts
            medias = client.hashtag_medias_recent(normalized_name, amount=amount)

            # Map each media to DTO
            return [
                InstagramMediaReaderAdapter._map_media_to_summary(media)
                for media in medias
            ]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_hashtag_recent_posts", account_id=account_id
            )
            raise ValueError(failure.user_message)

    @staticmethod
    def _map_location_to_summary(location: Any) -> LocationSummary:
        """
        Map instagrapi Location object to LocationSummary DTO.

        Args:
            location: instagrapi Location object.

        Returns:
            LocationSummary DTO.
        """
        return LocationSummary(
            pk=location.pk,
            name=location.name,
            address=getattr(location, "address", None),
            city=getattr(location, "city", None),
            lat=getattr(location, "lat", None),
            lng=getattr(location, "lng", None),
            external_id=getattr(location, "external_id", None),
            external_id_source=getattr(location, "external_id_source", None),
        )

    @staticmethod
    def _map_hashtag_to_summary(hashtag: Any) -> HashtagSummary:
        """
        Map instagrapi Hashtag object to HashtagSummary DTO.

        Args:
            hashtag: instagrapi Hashtag object.

        Returns:
            HashtagSummary DTO.
        """
        # Convert profile_pic_url if it's an HttpUrl
        profile_pic_url = None
        if hasattr(hashtag, "profile_pic_url") and hashtag.profile_pic_url:
            profile_pic_url = str(hashtag.profile_pic_url)

        return HashtagSummary(
            id=hashtag.id,
            name=hashtag.name,
            media_count=getattr(hashtag, "media_count", None),
            profile_pic_url=profile_pic_url,
        )
