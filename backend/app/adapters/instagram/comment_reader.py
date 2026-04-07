"""
Instagram comment reader adapter.

Maps instagrapi Comment objects to stable comment DTOs.
Handles pagination via media_comments_chunk.
"""

from typing import Any, Optional

from app.application.dto.instagram_comment_dto import (
    CommentAuthorSummary,
    CommentSummary,
    CommentPage,
)
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.error_utils import translate_instagram_error


class InstagramCommentReaderAdapter:
    """
    Adapter for reading Instagram comments via instagrapi.

    Maps vendor Comment objects to stable CommentSummary DTOs.
    Centralizes vendor-to-DTO translation for comment reads.
    Handles pagination through CommentPage with cursor.
    """

    def __init__(self, client_repo: ClientRepository):
        """
        Initialize comment reader.

        Args:
            client_repo: Repository for retrieving authenticated clients.
        """
        self.client_repo = client_repo

    def list_comments(
        self,
        account_id: str,
        media_id: str,
        amount: int = 0,
    ) -> list[CommentSummary]:
        """
        List comments for a media item.

        Args:
            account_id: The application account ID (for client lookup).
            media_id: The Instagram media ID.
            amount: Maximum comments to retrieve (0 = all available).

        Returns:
            List of CommentSummary.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to get comments
            comments = client.media_comments(media_id, amount=amount)

            # Map each comment to DTO
            return [self._map_comment_to_summary(c) for c in comments]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="list_comments", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def list_comments_page(
        self,
        account_id: str,
        media_id: str,
        page_size: int,
        cursor: str | None = None,
    ) -> CommentPage:
        """
        Get paginated comments for a media item.

        Args:
            account_id: The application account ID (for client lookup).
            media_id: The Instagram media ID.
            page_size: Maximum comments per page.
            cursor: Optional cursor for pagination.

        Returns:
            CommentPage with comments and next_cursor.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to get paginated comments
            # min_id is the cursor in instagrapi; None/0 means start from beginning
            min_id = int(cursor) if cursor else None
            comments, next_min_id = client.media_comments_chunk(
                media_id,
                max_amount=page_size,
                min_id=min_id,
            )

            # Map comments to DTOs
            comment_summaries = [self._map_comment_to_summary(c) for c in comments]

            # Convert next_min_id to string cursor (or None if exhausted)
            next_cursor = str(next_min_id) if next_min_id else None

            return CommentPage(
                comments=comment_summaries,
                next_cursor=next_cursor,
            )

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="list_comments_page", account_id=account_id
            )
            raise ValueError(failure.user_message)

    @staticmethod
    def _map_comment_to_summary(comment: Any) -> CommentSummary:
        """
        Map instagrapi Comment object to CommentSummary DTO.

        Args:
            comment: instagrapi Comment object.

        Returns:
            CommentSummary DTO.
        """
        # Extract author information
        author = None
        if hasattr(comment, "user") and comment.user:
            user = comment.user
            author = CommentAuthorSummary(
                pk=user.pk,
                username=user.username,
                full_name=getattr(user, "full_name", None),
                profile_pic_url=InstagramCommentReaderAdapter._to_string(
                    getattr(user, "profile_pic_url", None)
                ),
            )
        else:
            # Fallback: create author from comment fields if user is missing
            author = CommentAuthorSummary(
                pk=getattr(comment, "user_id", 0),
                username=getattr(comment, "user_username", "unknown"),
            )

        return CommentSummary(
            pk=comment.pk,
            text=comment.text,
            author=author,
            created_at=getattr(comment, "created_at_utc", None),
            content_type=getattr(comment, "content_type", None),
            status=getattr(comment, "status", None),
            has_liked=getattr(comment, "has_liked", None),
            like_count=getattr(comment, "like_count", None),
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
