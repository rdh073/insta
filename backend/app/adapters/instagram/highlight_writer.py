"""
Instagram highlight writer adapter.

Handles highlight creation, mutation, and deletion.
Maps story composition requests to vendor API calls.
Returns HighlightDetail (or HighlightActionReceipt for delete).
"""

from typing import Any, Optional

from app.application.dto.instagram_highlight_dto import (
    HighlightActionReceipt,
    HighlightDetail,
)
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.client_guard import get_guarded_client
from app.adapters.instagram.highlight_reader import InstagramHighlightReaderAdapter
from app.adapters.instagram.error_utils import (
    attach_instagram_failure,
    translate_instagram_error,
)


class InstagramHighlightWriterAdapter:
    """
    Adapter for creating and managing Instagram highlights via instagrapi.

    Handles highlight creation, mutation, and deletion.
    Centralizes vendor-specific concerns:
    - Calling appropriate vendor methods
    - Mapping story IDs to vendor format
    - Handling crop rectangle parameters
    - Normalizing delete results to HighlightActionReceipt
    """

    def __init__(self, client_repo: ClientRepository):
        """
        Initialize highlight writer.

        Args:
            client_repo: Repository for retrieving authenticated clients.
        """
        self.client_repo = client_repo
        self.highlight_reader = InstagramHighlightReaderAdapter(client_repo)

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
            cover_story_id: Optional story ID for cover (0 = use default).
            crop_rect: Optional crop rectangle.

        Returns:
            HighlightDetail of created highlight.

        Raises:
            ValueError: If account not found or creation fails.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Call vendor method to create highlight
            highlight = client.highlight_create(
                title=title,
                story_ids=story_ids,
                cover_story_id=cover_story_id if cover_story_id > 0 else "",
                crop_rect=crop_rect,
            )

            # Map result to DTO
            return self.highlight_reader._map_highlight_to_detail(highlight)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="create_highlight", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

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
            ValueError: If account not found or update fails.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Call vendor method to change title
            highlight = client.highlight_change_title(highlight_pk, title)

            # Map result to DTO
            return self.highlight_reader._map_highlight_to_detail(highlight)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="change_highlight_title", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

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
            ValueError: If account not found or operation fails.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Call vendor method to add stories
            highlight = client.highlight_add_stories(highlight_pk, story_ids)

            # Map result to DTO
            return self.highlight_reader._map_highlight_to_detail(highlight)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="add_highlight_stories", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

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
            ValueError: If account not found or operation fails.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Call vendor method to remove stories
            highlight = client.highlight_remove_stories(highlight_pk, story_ids)

            # Map result to DTO
            return self.highlight_reader._map_highlight_to_detail(highlight)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="remove_highlight_stories", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

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
            ValueError: If account not found or deletion fails.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Call vendor method to delete
            client.highlight_delete(highlight_pk)

            return HighlightActionReceipt(
                action_id=f"delete_{highlight_pk}",
                success=True,
                reason="Highlight deleted successfully",
            )

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="delete_highlight", account_id=account_id
            )
            return HighlightActionReceipt(
                action_id=f"delete_{highlight_pk}",
                success=False,
                reason=failure.user_message,
            )
