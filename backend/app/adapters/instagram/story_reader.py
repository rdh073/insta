"""
Instagram story reader adapter.

Maps instagrapi Story objects to stable story DTOs.
Handles overlay counting and vendor field conversions.
"""

from typing import Any, Optional

from app.application.dto.instagram_story_dto import (
    StorySummary,
    StoryDetail,
)
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.error_utils import (
    attach_instagram_failure,
    translate_instagram_error,
)


class InstagramStoryReaderAdapter:
    """
    Adapter for reading Instagram story metadata via instagrapi.

    Maps vendor Story objects to stable StorySummary and StoryDetail DTOs.
    Centralizes vendor-to-DTO translation for story reads.
    """

    def __init__(self, client_repo: ClientRepository):
        """
        Initialize story reader.

        Args:
            client_repo: Repository for retrieving authenticated clients.
        """
        self.client_repo = client_repo

    def get_story_pk_from_url(self, url: str) -> int:
        """
        Resolve story PK from URL.

        Args:
            url: Instagram story URL.

        Returns:
            Story primary key.

        Raises:
            ValueError: If resolution fails.
        """
        try:
            # story_pk_from_url is a utility on instagrapi Client and does not require
            # repository account context. Keep vendor call isolated in this adapter.
            from instagrapi import Client

            return int(Client().story_pk_from_url(url))
        except Exception as e:
            failure = translate_instagram_error(e, operation="resolve_story_url")
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    def get_story(
        self,
        account_id: str,
        story_pk: int,
        use_cache: bool = True,
    ) -> StoryDetail:
        """
        Get story by primary key.

        Args:
            account_id: The application account ID (for client lookup).
            story_pk: The Instagram story primary key.
            use_cache: Whether to use cached data.

        Returns:
            StoryDetail with overlay counts.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to get Story object
            story = client.story_info(story_pk, use_cache=use_cache)

            # Map to DTO
            return self._map_story_to_detail(story)
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_story", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

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
            amount: Maximum stories to retrieve.

        Returns:
            List of StorySummary.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to get stories list
            stories = client.user_stories(user_id, amount=amount)

            # Map each story to DTO
            return [self._map_story_to_summary(story) for story in stories]
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="list_user_stories", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    @staticmethod
    def _map_story_to_summary(story: Any) -> StorySummary:
        """
        Map instagrapi Story object to StorySummary DTO.

        Args:
            story: instagrapi Story object.

        Returns:
            StorySummary DTO.
        """
        # Get owner username from nested user object
        owner_username = None
        if hasattr(story, "user") and story.user and hasattr(story.user, "username"):
            owner_username = story.user.username

        return StorySummary(
            pk=story.pk,
            story_id=story.id,
            media_type=getattr(story, "media_type", None),
            taken_at=getattr(story, "taken_at", None),
            thumbnail_url=InstagramStoryReaderAdapter._to_string(
                getattr(story, "thumbnail_url", None)
            ),
            video_url=InstagramStoryReaderAdapter._to_string(
                getattr(story, "video_url", None)
            ),
            viewer_count=getattr(story, "viewer_count", None),
            owner_username=owner_username,
        )

    @staticmethod
    def _map_story_to_detail(story: Any) -> StoryDetail:
        """
        Map instagrapi Story object to StoryDetail DTO with overlay counts.

        Args:
            story: instagrapi Story object.

        Returns:
            StoryDetail with summary and overlay counts.
        """
        summary = InstagramStoryReaderAdapter._map_story_to_summary(story)

        # Count overlays if available
        link_count = 0
        mention_count = 0
        hashtag_count = 0
        location_count = 0
        sticker_count = 0

        # Try to count story items/overlays
        story_items = getattr(story, "story_items", None)
        if isinstance(story_items, (list, tuple)):
            for item in story_items:
                if InstagramStoryReaderAdapter._has_explicit_attr(item, "story_link"):
                    link_count += 1
                if InstagramStoryReaderAdapter._has_explicit_attr(item, "story_mention"):
                    mention_count += 1
                if InstagramStoryReaderAdapter._has_explicit_attr(item, "story_hashtag"):
                    hashtag_count += 1
                if InstagramStoryReaderAdapter._has_explicit_attr(item, "story_location"):
                    location_count += 1
                if InstagramStoryReaderAdapter._has_explicit_attr(item, "story_sticker"):
                    sticker_count += 1

        return StoryDetail(
            summary=summary,
            link_count=link_count,
            mention_count=mention_count,
            hashtag_count=hashtag_count,
            location_count=location_count,
            sticker_count=sticker_count,
        )

    @staticmethod
    def _to_string(value: Any) -> Optional[str]:
        """
        Convert a value to string, handling HttpUrl and None.

        Instagrapi uses pydantic HttpUrl for some fields.
        """
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _has_explicit_attr(obj: Any, attr_name: str) -> bool:
        """Return True when an attribute was explicitly set and is not None.

        This avoids false positives with dynamic objects like unittest.mock.Mock
        where arbitrary attributes appear as auto-generated children.
        """
        obj_dict = getattr(obj, "__dict__", None)
        if isinstance(obj_dict, dict) and attr_name in obj_dict:
            return obj_dict[attr_name] is not None
        # unittest.mock.Mock synthesizes arbitrary attributes dynamically;
        # when not explicitly assigned, treat them as absent.
        if type(obj).__module__.startswith("unittest.mock"):
            return False
        return getattr(obj, attr_name, None) is not None
