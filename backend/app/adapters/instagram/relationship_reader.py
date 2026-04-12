"""
Instagram relationship reader adapter.

Maps instagrapi relationship queries (followers/following) into
application-owned PublicUserProfile DTOs.
"""

from app.application.dto.instagram_identity_dto import PublicUserProfile
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.client_guard import get_guarded_client
from app.adapters.instagram.error_utils import (
    attach_instagram_failure,
    translate_instagram_error,
)


class InstagramRelationshipReaderAdapter:
    """Adapter for reading Instagram follower/following lists."""

    def __init__(self, client_repo: ClientRepository):
        self.client_repo = client_repo

    def list_followers(
        self,
        account_id: str,
        user_id: int,
        amount: int = 50,
    ) -> list[PublicUserProfile]:
        """List followers and map vendor users to PublicUserProfile."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            users = client.user_followers(user_id, amount=amount)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="user_followers",
                account_id=account_id,
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e
        return [self._map_user_to_profile(user) for user in users.values()]

    def list_following(
        self,
        account_id: str,
        user_id: int,
        amount: int = 50,
    ) -> list[PublicUserProfile]:
        """List following and map vendor users to PublicUserProfile."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            users = client.user_following(user_id, amount=amount)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="user_following",
                account_id=account_id,
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e
        return [self._map_user_to_profile(user) for user in users.values()]

    def search_followers(
        self,
        account_id: str,
        user_id: int,
        query: str,
    ) -> list[PublicUserProfile]:
        """Search within a user's follower list (server-side)."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            users = client.search_followers(user_id, query)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="search_followers",
                account_id=account_id,
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e
        return [self._map_user_to_profile(user) for user in users]

    def search_following(
        self,
        account_id: str,
        user_id: int,
        query: str,
    ) -> list[PublicUserProfile]:
        """Search within a user's following list (server-side)."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            users = client.search_following(user_id, query)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="search_following",
                account_id=account_id,
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e
        return [self._map_user_to_profile(user) for user in users]

    @staticmethod
    def _map_user_to_profile(user) -> PublicUserProfile:
        """Map instagrapi User object into stable identity DTO."""
        return PublicUserProfile(
            pk=user.pk,
            username=user.username,
            full_name=getattr(user, "full_name", None),
            biography=getattr(user, "biography", None),
            profile_pic_url=str(getattr(user, "profile_pic_url", "")) or None,
            follower_count=getattr(user, "follower_count", None),
            following_count=getattr(user, "following_count", None),
            media_count=getattr(user, "media_count", None),
            is_private=getattr(user, "is_private", None),
            is_verified=getattr(user, "is_verified", None),
            is_business=getattr(user, "is_business", None),
        )
