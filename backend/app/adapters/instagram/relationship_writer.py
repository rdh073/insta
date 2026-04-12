"""Instagram relationship writer adapter.

Maps follow/unfollow mutations through instagrapi into the
InstagramRelationshipWriter port.
"""

from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.error_utils import (
    attach_instagram_failure,
    translate_instagram_error,
    check_rate_limit,
    InstagramRateLimitError,
)


class InstagramRelationshipWriterAdapter:
    """Adapter for Instagram follow/unfollow mutations."""

    def __init__(self, client_repo: ClientRepository):
        self.client_repo = client_repo

    def follow_user(self, account_id: str, user_id: int) -> bool:
        """Follow a user via instagrapi."""
        check_rate_limit(account_id)
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            return client.user_follow(user_id)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="user_follow",
                account_id=account_id,
            )
            if failure.http_hint == 429:
                raise attach_instagram_failure(
                    InstagramRateLimitError(failure.user_message), failure
                ) from e
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    def unfollow_user(self, account_id: str, user_id: int) -> bool:
        """Unfollow a user via instagrapi."""
        check_rate_limit(account_id)
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            return client.user_unfollow(user_id)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="user_unfollow",
                account_id=account_id,
            )
            if failure.http_hint == 429:
                raise attach_instagram_failure(
                    InstagramRateLimitError(failure.user_message), failure
                ) from e
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    def remove_follower(self, account_id: str, user_id: int) -> bool:
        """Remove a follower via instagrapi."""
        check_rate_limit(account_id)
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            return client.user_remove_follower(user_id)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="user_remove_follower",
                account_id=account_id,
            )
            if failure.http_hint == 429:
                raise attach_instagram_failure(
                    InstagramRateLimitError(failure.user_message), failure
                ) from e
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    def close_friend_add(self, account_id: str, user_id: int) -> bool:
        """Add a user to Close Friends list via instagrapi."""
        check_rate_limit(account_id)
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            return client.close_friend_add(user_id)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="close_friend_add",
                account_id=account_id,
            )
            if failure.http_hint == 429:
                raise attach_instagram_failure(
                    InstagramRateLimitError(failure.user_message), failure
                ) from e
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    def close_friend_remove(self, account_id: str, user_id: int) -> bool:
        """Remove a user from Close Friends list via instagrapi."""
        check_rate_limit(account_id)
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            return client.close_friend_remove(user_id)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="close_friend_remove",
                account_id=account_id,
            )
            if failure.http_hint == 429:
                raise attach_instagram_failure(
                    InstagramRateLimitError(failure.user_message), failure
                ) from e
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e
