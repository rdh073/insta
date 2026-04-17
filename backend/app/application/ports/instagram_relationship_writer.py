"""Instagram relationship writer port.

Defines the application-facing contract for follow/unfollow mutations.
"""

from typing import Protocol


class InstagramRelationshipWriter(Protocol):
    """Port for mutating Instagram follow relationships."""

    def follow_user(self, account_id: str, user_id: int) -> bool:
        """Follow a user.

        Returns:
            True if the follow succeeded.

        Raises:
            ValueError: If account not found or operation failed.
        """
        ...

    def unfollow_user(self, account_id: str, user_id: int) -> bool:
        """Unfollow a user.

        Returns:
            True if the unfollow succeeded.

        Raises:
            ValueError: If account not found or operation failed.
        """
        ...

    def remove_follower(self, account_id: str, user_id: int) -> bool:
        """Remove a user from the authenticated account's followers.

        Returns:
            True if removal succeeded.

        Raises:
            ValueError: If account not found or operation failed.
        """
        ...

    def close_friend_add(self, account_id: str, user_id: int) -> bool:
        """Add a user to the Close Friends list.

        Returns:
            True if the user was added successfully.

        Raises:
            ValueError: If account not found or operation failed.
        """
        ...

    def close_friend_remove(self, account_id: str, user_id: int) -> bool:
        """Remove a user from the Close Friends list.

        Returns:
            True if the user was removed successfully.

        Raises:
            ValueError: If account not found or operation failed.
        """
        ...

    def mute_posts(self, account_id: str, user_id: int) -> bool:
        """Mute feed posts from a followed user."""
        ...

    def unmute_posts(self, account_id: str, user_id: int) -> bool:
        """Unmute feed posts from a followed user."""
        ...

    def mute_stories(self, account_id: str, user_id: int) -> bool:
        """Mute stories from a followed user."""
        ...

    def unmute_stories(self, account_id: str, user_id: int) -> bool:
        """Unmute stories from a followed user."""
        ...

    def set_posts_notifications(
        self, account_id: str, user_id: int, enabled: bool
    ) -> bool:
        """Toggle per-user push notifications for new feed posts."""
        ...

    def set_videos_notifications(
        self, account_id: str, user_id: int, enabled: bool
    ) -> bool:
        """Toggle per-user push notifications for new IGTV/videos."""
        ...

    def set_reels_notifications(
        self, account_id: str, user_id: int, enabled: bool
    ) -> bool:
        """Toggle per-user push notifications for new reels."""
        ...

    def set_stories_notifications(
        self, account_id: str, user_id: int, enabled: bool
    ) -> bool:
        """Toggle per-user push notifications for new stories."""
        ...
