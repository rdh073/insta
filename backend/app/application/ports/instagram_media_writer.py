"""Instagram media writer port.

Defines the application-facing contract for like/unlike mutations.
"""

from typing import Protocol


class InstagramMediaWriter(Protocol):
    """Port for mutating Instagram media engagement (likes)."""

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
