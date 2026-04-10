"""
Instagram media reader adapter.

Maps instagrapi Media, Resource, and MediaOembed objects to stable DTOs.
Handles vendor field conversions and album resource normalization.
"""

from datetime import datetime
from typing import Optional

from app.application.dto.instagram_media_dto import (
    MediaSummary,
    ResourceSummary,
    MediaOembedSummary,
)
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.error_utils import translate_instagram_error


class InstagramMediaReaderAdapter:
    """
    Adapter for reading Instagram media metadata via instagrapi.

    Maps vendor Media, Resource, and MediaOembed objects to stable DTOs.
    Centralizes vendor-to-DTO translation in one seam.
    """

    def __init__(self, client_repo: ClientRepository):
        """
        Initialize media reader.

        Args:
            client_repo: Repository for retrieving authenticated clients.
        """
        self.client_repo = client_repo

    def get_media_by_pk(self, account_id: str, media_pk: int) -> MediaSummary:
        """
        Get media by primary key.

        Args:
            account_id: The application account ID (for client lookup).
            media_pk: The Instagram media primary key.

        Returns:
            MediaSummary with full metadata.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to get Media object
            media = client.media_info(media_pk)

            # Map to DTO
            return self._map_media_to_summary(media)
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_media_by_pk", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def get_media_by_code(self, account_id: str, code: str) -> MediaSummary:
        """
        Get media by Instagram code.

        Args:
            account_id: The application account ID (for client lookup).
            code: The Instagram media code.

        Returns:
            MediaSummary with full metadata.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to get Media object
            media = client.media_info(client.media_pk_from_code(code))

            # Map to DTO
            return self._map_media_to_summary(media)
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_media_by_code", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def get_user_medias(
        self, account_id: str, user_id: int, amount: int = 12
    ) -> list[MediaSummary]:
        """
        Get media feed for a user.

        Args:
            account_id: The application account ID (for client lookup).
            user_id: The Instagram user ID.
            amount: Number of media to retrieve (default 12).

        Returns:
            List of MediaSummary in reverse chronological order.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to get media list
            medias = client.user_medias(user_id, amount=amount)

            # Map each media to DTO
            return [self._map_media_to_summary(media) for media in medias]
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_user_medias", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def get_media_oembed(self, account_id: str, url: str) -> MediaOembedSummary:
        """
        Get media oEmbed data from a media URL.

        Args:
            account_id: The application account ID (for client lookup).
            url: The Instagram media URL.

        Returns:
            MediaOembedSummary with embeddable metadata.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to get MediaOembed object
            oembed = client.media_oembed(url)

            # Map to DTO
            return self._map_oembed_to_summary(oembed)
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_media_oembed", account_id=account_id
            )
            raise ValueError(failure.user_message)

    @staticmethod
    def _map_media_to_summary(media) -> MediaSummary:
        """
        Map instagrapi Media object to MediaSummary DTO.

        Args:
            media: instagrapi Media object.

        Returns:
            MediaSummary DTO.
        """
        # Get owner username from nested user object
        owner_username = None
        if hasattr(media, "user") and media.user and hasattr(media.user, "username"):
            owner_username = media.user.username

        # Normalize caption field (use caption_text if available, else caption)
        # and only accept real strings, not mock/proxy objects.
        caption_text = (
            InstagramMediaReaderAdapter._normalize_string(
                getattr(media, "caption_text", None)
            )
            or InstagramMediaReaderAdapter._normalize_string(
                getattr(media, "caption", None)
            )
            or ""
        )

        # Normalize resources - treat missing as empty list
        resources = []
        if hasattr(media, "resources") and media.resources:
            resources = [
                InstagramMediaReaderAdapter._map_resource_to_summary(res)
                for res in media.resources
            ]

        return MediaSummary(
            pk=media.pk,
            media_id=media.id,
            code=media.code,
            media_type=media.media_type,
            product_type=media.product_type or "",
            owner_username=owner_username,
            caption_text=caption_text,
            like_count=getattr(media, "like_count", 0) or 0,
            comment_count=getattr(media, "comment_count", 0) or 0,
            taken_at=media.taken_at,
            resources=resources,
        )

    @staticmethod
    def _map_resource_to_summary(resource) -> ResourceSummary:
        """
        Map instagrapi Resource object to ResourceSummary DTO.

        Args:
            resource: instagrapi Resource object.

        Returns:
            ResourceSummary DTO.
        """
        return ResourceSummary(
            pk=resource.pk,
            media_type=resource.media_type,
            thumbnail_url=InstagramMediaReaderAdapter._to_string(
                resource.thumbnail_url
            ),
            video_url=InstagramMediaReaderAdapter._to_string(resource.video_url),
        )

    @staticmethod
    def _map_oembed_to_summary(oembed) -> MediaOembedSummary:
        """
        Map instagrapi MediaOembed object to MediaOembedSummary DTO.

        Args:
            oembed: instagrapi MediaOembed object.

        Returns:
            MediaOembedSummary DTO.
        """
        return MediaOembedSummary(
            media_id=oembed.media_id or "",
            author_name=getattr(oembed, "author_name", None),
            author_url=InstagramMediaReaderAdapter._to_string(
                getattr(oembed, "author_url", None)
            ),
            author_id=getattr(oembed, "author_id", None),
            title=getattr(oembed, "title", None),
            provider_name=getattr(oembed, "provider_name", None),
            html=getattr(oembed, "html", None),
            thumbnail_url=InstagramMediaReaderAdapter._to_string(
                getattr(oembed, "thumbnail_url", None)
            ),
            width=getattr(oembed, "width", None),
            height=getattr(oembed, "height", None),
            can_view=getattr(oembed, "can_view", None),
        )

    @staticmethod
    def _to_string(value) -> Optional[str]:
        """
        Convert a value to string, handling HttpUrl and None.

        Instagrapi uses pydantic HttpUrl for some fields.
        """
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _normalize_string(value) -> Optional[str]:
        """Return value only when it is a concrete string."""
        if isinstance(value, str):
            return value
        return None
