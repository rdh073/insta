"""
Instagram story reader and publisher ports.

Separates story retrieval from publication/management.
Prevents instagrapi Story and sticker types from leaking into application code.
"""

from typing import Protocol

from app.application.dto.instagram_story_dto import (
    StorySummary,
    StoryDetail,
    StoryPublishRequest,
    StoryActionReceipt,
)


class InstagramStoryReader(Protocol):
    """Port for reading Instagram story metadata.

    Handles story lookups, user story lists, and story detail retrieval.
    Implementation depends on instagrapi; application layer depends on DTOs.
    """

    def get_story_pk_from_url(self, url: str) -> int:
        """
        Resolve story PK from a story URL.

        Args:
            url: Instagram story URL (e.g., 'https://www.instagram.com/stories/username/123456789/').

        Returns:
            Story primary key.

        Raises:
            Exception: If URL is invalid or resolution fails.
        """
        ...

    def get_story(
        self,
        account_id: str,
        story_pk: int,
        use_cache: bool = True,
    ) -> StoryDetail:
        """
        Get story with detailed metadata.

        Args:
            account_id: The application account ID (for client lookup).
            story_pk: The Instagram story primary key.
            use_cache: Whether to use cached story data (default True).

        Returns:
            StoryDetail with overlay counts.

        Raises:
            Exception: If story not found or read fails.
        """
        ...

    def list_user_stories(
        self,
        account_id: str,
        user_id: int,
        amount: int | None = None,
    ) -> list[StorySummary]:
        """
        List stories for a user.

        Args:
            account_id: The application account ID (for client lookup).
            user_id: The Instagram user ID.
            amount: Maximum stories to retrieve (None = all available).

        Returns:
            List of StorySummary in order returned by vendor.

        Raises:
            Exception: If user not found or list fails.
        """
        ...


class InstagramStoryPublisher(Protocol):
    """Port for publishing and managing Instagram stories.

    Handles story creation, deletion, and lifecycle operations.
    Implementation depends on instagrapi; application layer depends on DTOs.
    """

    def publish_story(
        self,
        account_id: str,
        request: StoryPublishRequest,
    ) -> StoryDetail:
        """
        Publish a story with optional overlays.

        Args:
            account_id: The application account ID (for client lookup).
            request: StoryPublishRequest with media and composition specs.

        Returns:
            StoryDetail of published story.

        Raises:
            Exception: If publication fails.
        """
        ...

    def delete_story(
        self,
        account_id: str,
        story_pk: int,
    ) -> StoryActionReceipt:
        """
        Delete a story by primary key.

        Args:
            account_id: The application account ID (for client lookup).
            story_pk: The Instagram story primary key.

        Returns:
            StoryActionReceipt with result.

        Raises:
            Exception: If deletion fails.
        """
        ...

    def mark_seen(
        self,
        account_id: str,
        story_pks: list[int],
        skipped_story_pks: list[int] | None = None,
    ) -> StoryActionReceipt:
        """
        Mark stories as seen.

        Args:
            account_id: The application account ID (for client lookup).
            story_pks: Story PKs to mark as seen.
            skipped_story_pks: Optional story PKs to mark as skipped.

        Returns:
            StoryActionReceipt with result.

        Raises:
            Exception: If operation fails.
        """
        ...
