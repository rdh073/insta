"""Instagram relationship writer adapter.

Maps follow/unfollow/mute/notification mutations through instagrapi into the
InstagramRelationshipWriter port.
"""

from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.client_guard import get_guarded_client
from app.adapters.instagram.error_utils import (
    attach_instagram_failure,
    translate_instagram_error,
    InstagramRateLimitError,
)


class InstagramRelationshipWriterAdapter:
    """Adapter for Instagram follow/unfollow + mute + notification mutations."""

    def __init__(self, client_repo: ClientRepository):
        self.client_repo = client_repo

    def _call(self, account_id: str, operation: str, fn):
        """Run an instagrapi call with rate-limit-aware error translation."""
        client = get_guarded_client(self.client_repo, account_id)
        try:
            return fn(client)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation=operation,
                account_id=account_id,
            )
            if failure.http_hint == 429:
                raise attach_instagram_failure(
                    InstagramRateLimitError(failure.user_message), failure
                ) from e
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    def follow_user(self, account_id: str, user_id: int) -> bool:
        return self._call(account_id, "user_follow", lambda c: c.user_follow(user_id))

    def unfollow_user(self, account_id: str, user_id: int) -> bool:
        return self._call(account_id, "user_unfollow", lambda c: c.user_unfollow(user_id))

    def remove_follower(self, account_id: str, user_id: int) -> bool:
        return self._call(
            account_id, "user_remove_follower", lambda c: c.user_remove_follower(user_id)
        )

    def close_friend_add(self, account_id: str, user_id: int) -> bool:
        return self._call(
            account_id, "close_friend_add", lambda c: c.close_friend_add(user_id)
        )

    def close_friend_remove(self, account_id: str, user_id: int) -> bool:
        return self._call(
            account_id, "close_friend_remove", lambda c: c.close_friend_remove(user_id)
        )

    def mute_posts(self, account_id: str, user_id: int) -> bool:
        return self._call(
            account_id,
            "mute_posts_from_follow",
            lambda c: c.mute_posts_from_follow(user_id),
        )

    def unmute_posts(self, account_id: str, user_id: int) -> bool:
        return self._call(
            account_id,
            "unmute_posts_from_follow",
            lambda c: c.unmute_posts_from_follow(user_id),
        )

    def mute_stories(self, account_id: str, user_id: int) -> bool:
        return self._call(
            account_id,
            "mute_stories_from_follow",
            lambda c: c.mute_stories_from_follow(user_id),
        )

    def unmute_stories(self, account_id: str, user_id: int) -> bool:
        return self._call(
            account_id,
            "unmute_stories_from_follow",
            lambda c: c.unmute_stories_from_follow(user_id),
        )

    def set_posts_notifications(
        self, account_id: str, user_id: int, enabled: bool
    ) -> bool:
        if enabled:
            return self._call(
                account_id,
                "enable_posts_notifications",
                lambda c: c.enable_posts_notifications(user_id),
            )
        return self._call(
            account_id,
            "disable_posts_notifications",
            lambda c: c.disable_posts_notifications(user_id),
        )

    def set_videos_notifications(
        self, account_id: str, user_id: int, enabled: bool
    ) -> bool:
        if enabled:
            return self._call(
                account_id,
                "enable_videos_notifications",
                lambda c: c.enable_videos_notifications(user_id),
            )
        return self._call(
            account_id,
            "disable_videos_notifications",
            lambda c: c.disable_videos_notifications(user_id),
        )

    def set_reels_notifications(
        self, account_id: str, user_id: int, enabled: bool
    ) -> bool:
        if enabled:
            return self._call(
                account_id,
                "enable_reels_notifications",
                lambda c: c.enable_reels_notifications(user_id),
            )
        return self._call(
            account_id,
            "disable_reels_notifications",
            lambda c: c.disable_reels_notifications(user_id),
        )

    def set_stories_notifications(
        self, account_id: str, user_id: int, enabled: bool
    ) -> bool:
        if enabled:
            return self._call(
                account_id,
                "enable_stories_notifications",
                lambda c: c.enable_stories_notifications(user_id),
            )
        return self._call(
            account_id,
            "disable_stories_notifications",
            lambda c: c.disable_stories_notifications(user_id),
        )
