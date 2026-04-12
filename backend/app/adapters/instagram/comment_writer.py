"""
Instagram comment writer adapter.

Handles comment creation and deletion via instagrapi.
Maps reply semantics and normalizes delete operations.
"""

from typing import Any, Optional

from app.application.dto.instagram_comment_dto import (
    CommentSummary,
    CommentActionReceipt,
)
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.comment_reader import InstagramCommentReaderAdapter
from app.adapters.instagram.error_utils import (
    attach_instagram_failure,
    translate_instagram_error,
)


class InstagramCommentWriterAdapter:
    """
    Adapter for creating and managing Instagram comments via instagrapi.

    Handles comment creation with optional reply semantics.
    Normalizes batch delete to single comment delete.
    Maps vendor Comment responses to CommentSummary DTOs.
    """

    def __init__(self, client_repo: ClientRepository):
        """
        Initialize comment writer.

        Args:
            client_repo: Repository for retrieving authenticated clients.
        """
        self.client_repo = client_repo

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
            reply_to_comment_id: Optional comment ID to reply to.

        Returns:
            CommentSummary of created comment.

        Raises:
            ValueError: If account not found or creation fails.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to create comment
            comment = client.media_comment(
                media_id,
                text,
                replied_to_comment_id=reply_to_comment_id,
            )

            # Map result to DTO
            return InstagramCommentReaderAdapter._map_comment_to_summary(comment)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="create_comment", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

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
            ValueError: If account not found or deletion fails.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to delete comment
            # Note: vendor uses comment_bulk_delete, but we normalize to single delete
            client.comment_bulk_delete(media_id, [comment_id])

            return CommentActionReceipt(
                action_id=str(comment_id),
                success=True,
                reason="Comment deleted successfully",
            )

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="delete_comment", account_id=account_id
            )
            return CommentActionReceipt(
                action_id=str(comment_id),
                success=False,
                reason=failure.user_message,
            )

    def like_comment(self, account_id: str, comment_id: int) -> CommentActionReceipt:
        """Like a comment."""
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")
        try:
            client.comment_like(comment_id)
            return CommentActionReceipt(action_id=str(comment_id), success=True, reason="Comment liked")
        except Exception as e:
            failure = translate_instagram_error(e, operation="like_comment", account_id=account_id)
            return CommentActionReceipt(action_id=str(comment_id), success=False, reason=failure.user_message)

    def unlike_comment(self, account_id: str, comment_id: int) -> CommentActionReceipt:
        """Unlike a comment."""
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")
        try:
            client.comment_unlike(comment_id)
            return CommentActionReceipt(action_id=str(comment_id), success=True, reason="Comment unliked")
        except Exception as e:
            failure = translate_instagram_error(e, operation="unlike_comment", account_id=account_id)
            return CommentActionReceipt(action_id=str(comment_id), success=False, reason=failure.user_message)

    def pin_comment(
        self, account_id: str, media_id: str, comment_id: int
    ) -> CommentActionReceipt:
        """Pin a comment (only for posts owned by the account)."""
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")
        try:
            client.comment_pin(media_id, comment_id)
            return CommentActionReceipt(action_id=str(comment_id), success=True, reason="Comment pinned")
        except Exception as e:
            failure = translate_instagram_error(e, operation="pin_comment", account_id=account_id)
            return CommentActionReceipt(action_id=str(comment_id), success=False, reason=failure.user_message)

    def unpin_comment(
        self, account_id: str, media_id: str, comment_id: int
    ) -> CommentActionReceipt:
        """Unpin a comment (only for posts owned by the account)."""
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")
        try:
            client.comment_unpin(media_id, comment_id)
            return CommentActionReceipt(action_id=str(comment_id), success=True, reason="Comment unpinned")
        except Exception as e:
            failure = translate_instagram_error(e, operation="unpin_comment", account_id=account_id)
            return CommentActionReceipt(action_id=str(comment_id), success=False, reason=failure.user_message)
