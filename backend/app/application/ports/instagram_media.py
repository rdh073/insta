"""
Instagram media reader port.

Defines the application-facing contract for reading Instagram media metadata.
Separates media queries from authentication/session management.
"""

from typing import Protocol

from app.application.dto.instagram_identity_dto import PublicUserProfile
from app.application.dto.instagram_media_dto import (
    MediaSummary,
    MediaOembedSummary,
)


class InstagramMediaReader(Protocol):
    """
    Port for reading Instagram media metadata.

    Handles queries for individual media, user media feeds, and oembed data.
    Implementation depends on instagrapi; application layer depends on DTOs.
    """

    def get_media_by_pk(self, account_id: str, media_pk: int) -> MediaSummary:
        """
        Get media by primary key.

        Args:
            account_id: The application account ID (for client lookup).
            media_pk: The Instagram media primary key.

        Returns:
            MediaSummary with full metadata.

        Raises:
            Exception: If media not found or read fails.
        """
        ...

    def get_media_by_code(self, account_id: str, code: str) -> MediaSummary:
        """
        Get media by Instagram code (short URL identifier).

        Args:
            account_id: The application account ID (for client lookup).
            code: The Instagram media code (e.g., 'CpbDdszj7ei').

        Returns:
            MediaSummary with full metadata.

        Raises:
            Exception: If media not found or read fails.
        """
        ...

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
            Exception: If user not found or read fails.
        """
        ...

    def get_media_oembed(self, account_id: str, url: str) -> MediaOembedSummary:
        """
        Get media oEmbed data from a media URL.

        oEmbed provides limited metadata suitable for embedding/sharing.

        Args:
            account_id: The application account ID (for client lookup).
            url: The Instagram media URL (e.g., 'https://www.instagram.com/p/CODE/').

        Returns:
            MediaOembedSummary with embeddable metadata.

        Raises:
            Exception: If URL invalid or read fails.
        """
        ...

    def list_media_likers(
        self, account_id: str, media_id: str
    ) -> list[PublicUserProfile]:
        """
        List users who liked a media post.

        Backed by instagrapi ``media_likers(media_id)`` which returns
        ``List[UserShort]``.

        Args:
            account_id: The application account ID (for client lookup).
            media_id: Instagram media ID string (e.g., '123_456').

        Returns:
            List of PublicUserProfile in the order returned by Instagram.

        Raises:
            Exception: If media not found or read fails.
        """
        ...

    def list_user_clips(
        self, account_id: str, user_id: int, amount: int = 12
    ) -> list[MediaSummary]:
        """
        List a user's clip (reels) catalog.

        Backed by instagrapi ``user_clips(user_id, amount)`` which returns
        ``List[Media]`` of product_type='clips'.

        Args:
            account_id: The application account ID (for client lookup).
            user_id: The Instagram user ID.
            amount: Maximum number of clips to retrieve.

        Returns:
            List of MediaSummary representing reels.

        Raises:
            Exception: If user not found or read fails.
        """
        ...

    def list_usertag_medias(
        self, account_id: str, user_id: int, amount: int = 12
    ) -> list[MediaSummary]:
        """
        List media posts in which a user is tagged.

        Backed by instagrapi ``usertag_medias(user_id, amount)`` which returns
        ``List[Media]``.

        Args:
            account_id: The application account ID (for client lookup).
            user_id: The Instagram user ID.
            amount: Maximum number of media to retrieve.

        Returns:
            List of MediaSummary in which the user appears as a tag.

        Raises:
            Exception: If user not found or read fails.
        """
        ...
