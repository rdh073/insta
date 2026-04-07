"""
Instagram highlight reader and writer ports.

Separates highlight retrieval from authenticated highlight mutations.
Prevents instagrapi Highlight and nested Story types from leaking into application code.
Story data crosses the boundary through the shared story DTO seam (Phase 4).
"""

from typing import Protocol

from app.application.dto.instagram_highlight_dto import (
    HighlightSummary,
    HighlightDetail,
    HighlightActionReceipt,
)


class InstagramHighlightReader(Protocol):
    """Port for reading Instagram highlight metadata.

    Handles highlight lookups and story lists.
    Implementation depends on instagrapi; application layer depends on DTOs.
    """

    def get_highlight_pk_from_url(self, url: str) -> int:
        """
        Resolve highlight PK from a highlight URL.

        Args:
            url: Instagram highlight URL.

        Returns:
            Highlight primary key.

        Raises:
            Exception: If URL is invalid or resolution fails.
        """
        ...

    def get_highlight(
        self,
        account_id: str,
        highlight_pk: int,
    ) -> HighlightDetail:
        """
        Get highlight with full story details.

        Args:
            account_id: The application account ID (for client lookup).
            highlight_pk: The Instagram highlight primary key.

        Returns:
            HighlightDetail with story items mapped to StorySummary.

        Raises:
            Exception: If highlight not found or read fails.
        """
        ...

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
            List of HighlightSummary in order returned by vendor.

        Raises:
            Exception: If user not found or list fails.
        """
        ...


class InstagramHighlightWriter(Protocol):
    """Port for creating and managing Instagram highlights.

    Handles highlight creation, mutation, and deletion.
    Implementation depends on instagrapi; application layer depends on DTOs.
    """

    def create_highlight(
        self,
        account_id: str,
        title: str,
        story_ids: list[int],
        cover_story_id: int = 0,
        crop_rect: list[float] | None = None,
    ) -> HighlightDetail:
        """
        Create a new highlight with stories.

        Args:
            account_id: The application account ID (for client lookup).
            title: Highlight title.
            story_ids: List of story IDs to include.
            cover_story_id: Optional story ID for highlight cover (0 = use default).
            crop_rect: Optional crop rectangle as [x, y, width, height] (normalized [0, 1]).

        Returns:
            HighlightDetail of created highlight.

        Raises:
            Exception: If creation fails.
        """
        ...

    def change_title(
        self,
        account_id: str,
        highlight_pk: int,
        title: str,
    ) -> HighlightDetail:
        """
        Change highlight title.

        Args:
            account_id: The application account ID (for client lookup).
            highlight_pk: The Instagram highlight primary key.
            title: New title.

        Returns:
            HighlightDetail with updated information.

        Raises:
            Exception: If highlight not found or update fails.
        """
        ...

    def add_stories(
        self,
        account_id: str,
        highlight_pk: int,
        story_ids: list[int],
    ) -> HighlightDetail:
        """
        Add stories to an existing highlight.

        Args:
            account_id: The application account ID (for client lookup).
            highlight_pk: The Instagram highlight primary key.
            story_ids: List of story IDs to add.

        Returns:
            HighlightDetail with updated story list.

        Raises:
            Exception: If highlight not found or operation fails.
        """
        ...

    def remove_stories(
        self,
        account_id: str,
        highlight_pk: int,
        story_ids: list[int],
    ) -> HighlightDetail:
        """
        Remove stories from a highlight.

        Args:
            account_id: The application account ID (for client lookup).
            highlight_pk: The Instagram highlight primary key.
            story_ids: List of story IDs to remove.

        Returns:
            HighlightDetail with updated story list.

        Raises:
            Exception: If highlight not found or operation fails.
        """
        ...

    def delete_highlight(
        self,
        account_id: str,
        highlight_pk: int,
    ) -> HighlightActionReceipt:
        """
        Delete a highlight.

        Args:
            account_id: The application account ID (for client lookup).
            highlight_pk: The Instagram highlight primary key.

        Returns:
            HighlightActionReceipt with result.

        Raises:
            Exception: If deletion fails.
        """
        ...
