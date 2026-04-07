"""
Instagram highlight reader adapter.

Maps instagrapi Highlight objects to stable highlight DTOs.
Reuses StorySummary from Phase 4 for nested story items.
Handles cover metadata extraction and vendor field conversions.
"""

from typing import Any, Optional

from app.application.dto.instagram_highlight_dto import (
    HighlightCoverSummary,
    HighlightSummary,
    HighlightDetail,
)
from app.application.dto.instagram_story_dto import StorySummary
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.story_reader import InstagramStoryReaderAdapter
from app.adapters.instagram.error_utils import translate_instagram_error


class InstagramHighlightReaderAdapter:
    """
    Adapter for reading Instagram highlight metadata via instagrapi.

    Maps vendor Highlight objects to stable HighlightSummary and HighlightDetail DTOs.
    Reuses StorySummary from Phase 4 for nested story items.
    Centralizes vendor-to-DTO translation for highlight reads.
    """

    def __init__(self, client_repo: ClientRepository):
        """
        Initialize highlight reader.

        Args:
            client_repo: Repository for retrieving authenticated clients.
        """
        self.client_repo = client_repo

    def get_highlight_pk_from_url(self, url: str) -> int:
        """
        Resolve highlight PK from URL.

        Args:
            url: Instagram highlight URL.

        Returns:
            Highlight primary key.

        Raises:
            ValueError: If resolution fails.
        """
        try:
            # highlight_pk_from_url is a utility on instagrapi Client and does not
            # require repository account context. Keep vendor call isolated here.
            from instagrapi import Client

            return int(Client().highlight_pk_from_url(url))
        except Exception as e:
            failure = translate_instagram_error(e, operation="resolve_highlight_url")
            raise ValueError(failure.user_message)

    def get_highlight(
        self,
        account_id: str,
        highlight_pk: int,
    ) -> HighlightDetail:
        """
        Get highlight by primary key.

        Args:
            account_id: The application account ID (for client lookup).
            highlight_pk: The Instagram highlight primary key.

        Returns:
            HighlightDetail with story items.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to get Highlight object
            highlight = client.highlight_info(highlight_pk)

            # Map to DTO
            return self._map_highlight_to_detail(highlight)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_highlight", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def list_user_highlights(
        self,
        account_id: str,
        user_id: int,
        amount: int = 0,
    ) -> list[HighlightSummary]:
        """
        List highlights for a user.

        Args:
            account_id: The application account ID (for client lookup).
            user_id: The Instagram user ID.
            amount: Maximum highlights to retrieve (0 = all available).

        Returns:
            List of HighlightSummary.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to get highlights list
            highlights = client.user_highlights(user_id, amount=amount)

            # Map each highlight to DTO
            return [self._map_highlight_to_summary(h) for h in highlights]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="list_user_highlights", account_id=account_id
            )
            raise ValueError(failure.user_message)

    @staticmethod
    def _map_highlight_to_summary(highlight: Any) -> HighlightSummary:
        """
        Map instagrapi Highlight object to HighlightSummary DTO.

        Args:
            highlight: instagrapi Highlight object.

        Returns:
            HighlightSummary DTO.
        """
        # Get owner username from nested user object
        owner_username = None
        if hasattr(highlight, "user") and highlight.user and hasattr(highlight.user, "username"):
            owner_username = highlight.user.username

        # Extract cover information
        cover = None
        if hasattr(highlight, "cover_media") and highlight.cover_media:
            cover_media = highlight.cover_media
            cover = HighlightCoverSummary(
                media_id=getattr(cover_media, "id", None),
                image_url=InstagramHighlightReaderAdapter._to_string(
                    getattr(cover_media, "image_versions2", {}).get("candidates", [{}])[0].get("url")
                    if hasattr(cover_media, "image_versions2")
                    else getattr(cover_media, "image_url", None)
                ),
                crop_rect=getattr(cover_media, "crop_rect", []),
            )

        return HighlightSummary(
            pk=str(highlight.pk),
            highlight_id=highlight.id,
            title=getattr(highlight, "title", None),
            created_at=getattr(highlight, "created_at", None),
            is_pinned=getattr(highlight, "is_pinned_highlight", None),
            media_count=getattr(highlight, "media_count", None),
            latest_reel_media=getattr(highlight, "latest_reel_media", None),
            owner_username=owner_username,
            cover=cover,
        )

    @staticmethod
    def _map_highlight_to_detail(highlight: Any) -> HighlightDetail:
        """
        Map instagrapi Highlight object to HighlightDetail DTO with stories.

        Args:
            highlight: instagrapi Highlight object.

        Returns:
            HighlightDetail with summary and story items.
        """
        summary = InstagramHighlightReaderAdapter._map_highlight_to_summary(highlight)

        # Extract story IDs
        story_ids = []
        if hasattr(highlight, "media_ids") and highlight.media_ids:
            story_ids = [str(sid) for sid in highlight.media_ids]

        # Map story items using Phase 4 story mapping
        items = []
        if hasattr(highlight, "items") and highlight.items:
            for item in highlight.items:
                story_summary = InstagramStoryReaderAdapter._map_story_to_summary(item)
                items.append(story_summary)

        return HighlightDetail(
            summary=summary,
            story_ids=story_ids,
            items=items,
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
