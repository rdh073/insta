"""
Instagram comment reader and writer ports.

Separates comment retrieval from comment creation/deletion.
Prevents instagrapi Comment objects from leaking into application code.
Reply and pagination semantics are explicit in the port signature.
"""

from typing import Protocol

from app.application.dto.instagram_comment_dto import (
    CommentSummary,
    CommentPage,
    CommentActionReceipt,
)


class InstagramCommentReader(Protocol):
    """Port for reading Instagram comments.

    Handles comment retrieval and pagination.
    Implementation depends on instagrapi; application layer depends on DTOs.
    """

    def list_comments(
        self,
        account_id: str,
        media_id: str,
        amount: int = 0,
    ) -> list[CommentSummary]:
        """
        List comments for a media item (post).

        Args:
            account_id: The application account ID (for client lookup).
            media_id: The Instagram media ID.
            amount: Maximum comments to retrieve (0 = all available).

        Returns:
            List of CommentSummary in order returned by vendor.

        Raises:
            Exception: If media not found or read fails.
        """
        ...

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
            cursor: Optional cursor for pagination (None = start from beginning).

        Returns:
            CommentPage with comments and next_cursor for iteration.

        Raises:
            Exception: If media not found or read fails.
        """
        ...


class InstagramCommentWriter(Protocol):
    """Port for creating and managing Instagram comments.

    Handles comment creation and deletion.
    Implementation depends on instagrapi; application layer depends on DTOs.

    Note: Like/unlike/pin/unpin are deferred to a separate port if needed.
    """

    def create_comment(
        self,
        account_id: str,
        media_id: str,
        text: str,
        reply_to_comment_id: int | None = None,
    ) -> CommentSummary:
        """
        Create a comment or reply on a media item.

        Args:
            account_id: The application account ID (for client lookup).
            media_id: The Instagram media ID to comment on.
            text: Comment text content.
            reply_to_comment_id: Optional comment ID to reply to (None = top-level comment).

        Returns:
            CommentSummary of created comment.

        Raises:
            Exception: If media not found or comment creation fails.
        """
        ...

    def delete_comment(
        self,
        account_id: str,
        media_id: str,
        comment_id: int,
    ) -> CommentActionReceipt:
        """
        Delete a comment.

        Args:
            account_id: The application account ID (for client lookup).
            media_id: The Instagram media ID (required by vendor API).
            comment_id: The Instagram comment ID to delete.

        Returns:
            CommentActionReceipt with result.

        Raises:
            Exception: If deletion fails.
        """
        ...

    def like_comment(self, account_id: str, comment_id: int) -> CommentActionReceipt:
        """Like a comment."""
        ...

    def unlike_comment(self, account_id: str, comment_id: int) -> CommentActionReceipt:
        """Unlike a comment."""
        ...

    def pin_comment(
        self, account_id: str, media_id: str, comment_id: int
    ) -> CommentActionReceipt:
        """Pin a comment on a media item owned by the account."""
        ...

    def unpin_comment(
        self, account_id: str, media_id: str, comment_id: int
    ) -> CommentActionReceipt:
        """Unpin a comment on a media item owned by the account."""
        ...
