"""Comment use cases - application orchestration for Instagram comment operations.

Owns precondition enforcement, input validation, and application-level policy
for comment operations before delegating to ports.

Policy owned here (not in router or adapter):
  - media_id must be non-empty string (stripped) - validated via MediaID domain value object
  - amount must be >= 0 (0 = all available) - validated via QueryAmount domain value object
  - page_size must be >= 1 - validated via PageSize domain value object
  - comment text must not be empty (stripped) - validated via CommentText domain value object
  - comment_id must be a positive integer - validated via CommentID domain value object
  - reply_to_comment_id if provided must be a positive integer (top-level vs reply flow)
"""

from __future__ import annotations

from typing import Optional

from app.application.dto.instagram_comment_dto import (
    CommentSummary,
    CommentPage,
    CommentActionReceipt,
)
from app.application.ports.instagram_comments import (
    InstagramCommentReader,
    InstagramCommentWriter,
)
from app.application.ports.repositories import AccountRepository, ClientRepository
from app.domain.comment import (
    InvalidIdentifier,
    InvalidComposite,
    MediaID,
    CommentID,
    CommentText,
    QueryAmount,
    PageSize,
    OptionalReplyTarget,
    CommentAggregate,
)


class CommentUseCases:
    """Application orchestration for Instagram comment operations.

    Owns precondition enforcement (account exists, authenticated),
    media_id normalization, text validation, and top-level vs reply flow policy.
    The underlying ports handle vendor calls and DTO mapping.
    """

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        comment_reader: InstagramCommentReader,
        comment_writer: InstagramCommentWriter,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.comment_reader = comment_reader
        self.comment_writer = comment_writer

    # -------------------------------------------------------------------------
    # Precondition helpers
    # -------------------------------------------------------------------------

    def _require_authenticated(self, account_id: str) -> None:
        """Raise ValueError if account does not exist or is not authenticated."""
        if not self.account_repo.get(account_id):
            raise ValueError(f"Account {account_id!r} not found")
        if not self.client_repo.exists(account_id):
            raise ValueError(f"Account {account_id!r} is not authenticated")

    # -------------------------------------------------------------------------
    # Read operations
    # -------------------------------------------------------------------------

    def list_comments(
        self,
        account_id: str,
        media_id: str,
        amount: int = 0,
    ) -> list[CommentSummary]:
        """List comments for a media item.

        Args:
            account_id: Application account ID.
            media_id: Instagram media ID (must not be empty).
            amount: Maximum comments to retrieve (0 = all available).

        Returns:
            List of CommentSummary in order returned by vendor.

        Raises:
            ValueError: If account not found, not authenticated, media_id empty,
                        or amount is negative.
        """
        self._require_authenticated(account_id)
        if not isinstance(amount, int) or amount < 0:
            raise ValueError(f"amount must be a non-negative integer, got {amount!r}")
        try:
            mid = MediaID(media_id)
            amt = QueryAmount(amount)
            return self.comment_reader.list_comments(account_id, str(mid), int(amt))
        except (InvalidIdentifier, InvalidComposite) as e:
            raise ValueError(f"media_id must not be empty ({e})") from e

    def list_comments_page(
        self,
        account_id: str,
        media_id: str,
        page_size: int,
        cursor: Optional[str] = None,
    ) -> CommentPage:
        """Get paginated comments for a media item.

        Args:
            account_id: Application account ID.
            media_id: Instagram media ID (must not be empty).
            page_size: Comments per page (must be >= 1).
            cursor: Optional cursor for pagination (None = first page).

        Returns:
            CommentPage with comments and next_cursor.

        Raises:
            ValueError: If account not found, not authenticated, media_id empty,
                        or page_size < 1.
        """
        self._require_authenticated(account_id)
        try:
            mid = MediaID(media_id)
            ps = PageSize(page_size)
            return self.comment_reader.list_comments_page(
                account_id, str(mid), int(ps), cursor
            )
        except InvalidIdentifier as e:
            message = str(e).lower()
            if "pagesize" in message:
                raise ValueError(
                    f"page_size must be a positive integer, got {page_size!r}"
                ) from e
            raise ValueError(f"media_id must not be empty ({e})") from e

    # -------------------------------------------------------------------------
    # Write operations
    # -------------------------------------------------------------------------

    def create_comment(
        self,
        account_id: str,
        media_id: str,
        text: str,
        reply_to_comment_id: Optional[int] = None,
    ) -> CommentSummary:
        """Create a top-level comment or reply on a media item.

        Top-level flow: reply_to_comment_id=None (default).
        Reply flow: reply_to_comment_id must be a positive integer.

        Args:
            account_id: Application account ID.
            media_id: Instagram media ID (must not be empty).
            text: Comment text (must not be empty after stripping).
            reply_to_comment_id: Comment ID to reply to (None = top-level).

        Returns:
            CommentSummary of created comment.

        Raises:
            ValueError: If account not found, not authenticated, media_id empty,
                        text empty, or reply_to_comment_id is not a positive integer.
        """
        self._require_authenticated(account_id)
        try:
            mid = MediaID(media_id)
            ct = CommentText(text)
            reply_target = OptionalReplyTarget(reply_to_comment_id)
            CommentAggregate(
                comment_id=CommentID(1),
                media_id=mid,
                text=str(ct),
                reply_to_comment_id=reply_target,
            )
            return self.comment_writer.create_comment(
                account_id, str(mid), str(ct), reply_to_comment_id
            )
        except (InvalidIdentifier, InvalidComposite) as e:
            message = str(e).lower()
            if "reply_to_comment_id" in message or "replytarget" in message:
                raise ValueError(
                    f"reply_to_comment_id must be a positive integer, got {reply_to_comment_id!r}"
                ) from e
            if "commenttext" in message:
                raise ValueError(f"text must not be empty, got {text!r}") from e
            raise ValueError(f"media_id must not be empty ({e})") from e

    def delete_comment(
        self,
        account_id: str,
        media_id: str,
        comment_id: int,
    ) -> CommentActionReceipt:
        """Delete a comment.

        Args:
            account_id: Application account ID.
            media_id: Instagram media ID (required by vendor API, must not be empty).
            comment_id: Instagram comment ID (positive integer).

        Returns:
            CommentActionReceipt with result.

        Raises:
            ValueError: If account not found, not authenticated, media_id empty,
                        or comment_id is not a positive integer.
        """
        self._require_authenticated(account_id)
        try:
            mid = MediaID(media_id)
            cid = CommentID(comment_id)
            return self.comment_writer.delete_comment(account_id, str(mid), int(cid))
        except InvalidIdentifier as e:
            message = str(e).lower()
            if "commentid" in message:
                raise ValueError(
                    f"comment_id must be a positive integer, got {comment_id!r}"
                ) from e
            raise ValueError(f"media_id must not be empty ({e})") from e

    def like_comment(self, account_id: str, comment_id: int) -> CommentActionReceipt:
        """Like a comment."""
        self._require_authenticated(account_id)
        try:
            cid = CommentID(comment_id)
            return self.comment_writer.like_comment(account_id, int(cid))
        except InvalidIdentifier as e:
            raise ValueError(f"comment_id must be a positive integer, got {comment_id!r}") from e

    def unlike_comment(self, account_id: str, comment_id: int) -> CommentActionReceipt:
        """Unlike a comment."""
        self._require_authenticated(account_id)
        try:
            cid = CommentID(comment_id)
            return self.comment_writer.unlike_comment(account_id, int(cid))
        except InvalidIdentifier as e:
            raise ValueError(f"comment_id must be a positive integer, got {comment_id!r}") from e

    def pin_comment(
        self, account_id: str, media_id: str, comment_id: int
    ) -> CommentActionReceipt:
        """Pin a comment on a media item owned by the account."""
        self._require_authenticated(account_id)
        try:
            mid = MediaID(media_id)
            cid = CommentID(comment_id)
            return self.comment_writer.pin_comment(account_id, str(mid), int(cid))
        except InvalidIdentifier as e:
            message = str(e).lower()
            if "commentid" in message:
                raise ValueError(f"comment_id must be a positive integer, got {comment_id!r}") from e
            raise ValueError(f"media_id must not be empty ({e})") from e

    def unpin_comment(
        self, account_id: str, media_id: str, comment_id: int
    ) -> CommentActionReceipt:
        """Unpin a comment on a media item owned by the account."""
        self._require_authenticated(account_id)
        try:
            mid = MediaID(media_id)
            cid = CommentID(comment_id)
            return self.comment_writer.unpin_comment(account_id, str(mid), int(cid))
        except InvalidIdentifier as e:
            message = str(e).lower()
            if "commentid" in message:
                raise ValueError(f"comment_id must be a positive integer, got {comment_id!r}") from e
            raise ValueError(f"media_id must not be empty ({e})") from e
