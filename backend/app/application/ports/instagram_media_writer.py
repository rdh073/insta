"""Instagram media writer port.

Defines the application-facing contract for media write mutations:
likes, caption edit, delete, pin/unpin, archive/unarchive, and
collection bookmarking (save/unsave).
"""

from typing import Optional, Protocol

from app.application.dto.instagram_media_dto import MediaActionReceipt


class InstagramMediaWriter(Protocol):
    """Port for mutating Instagram media (engagement + lifecycle + collections)."""

    def like_media(self, account_id: str, media_id: str) -> bool:
        """Like a post.

        Args:
            account_id: Authenticated account performing the like.
            media_id: Instagram media ID string (e.g. "3488123456_25025320").

        Returns:
            True if the like succeeded.

        Raises:
            ValueError: If account not found or operation failed.
        """
        ...

    def unlike_media(self, account_id: str, media_id: str) -> bool:
        """Remove a like from a post.

        Args:
            account_id: Authenticated account removing the like.
            media_id: Instagram media ID string.

        Returns:
            True if the unlike succeeded.

        Raises:
            ValueError: If account not found or operation failed.
        """
        ...

    def edit_caption(
        self, account_id: str, media_id: str, caption: str
    ) -> MediaActionReceipt:
        """Edit a published post's caption.

        Wraps instagrapi's ``media_edit`` (caption-only). usertags / location /
        IGTV title editing is intentionally not exposed here — defer to a
        follow-up task if operator demand surfaces.
        """
        ...

    def delete_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Permanently delete a post owned by the account."""
        ...

    def pin_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Pin a post to the profile grid (max 3 pinned per profile)."""
        ...

    def unpin_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Unpin a previously pinned post."""
        ...

    def archive_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Archive a post (hides from public profile, owner can still view)."""
        ...

    def unarchive_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Restore an archived post back to the public profile."""
        ...

    def save_media(
        self,
        account_id: str,
        media_id: str,
        collection_pk: Optional[int] = None,
    ) -> MediaActionReceipt:
        """Bookmark a post into a saved collection.

        Args:
            collection_pk: Optional Instagram collection PK. None saves to the
                default "All Posts" collection.
        """
        ...

    def unsave_media(
        self,
        account_id: str,
        media_id: str,
        collection_pk: Optional[int] = None,
    ) -> MediaActionReceipt:
        """Remove a post from a saved collection (or all if collection_pk is None)."""
        ...
