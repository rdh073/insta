"""
Instagram identity reader adapter.

Maps instagrapi Account and User objects to stable application DTOs.
Handles reads of authenticated account and public user profiles.
"""

from app.application.dto.instagram_identity_dto import (
    AuthenticatedAccountProfile,
    PublicUserProfile,
)
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.error_utils import (
    translate_instagram_error,
    check_rate_limit,
    InstagramRateLimitError,
    InstagramAdapterError,
)


class InstagramIdentityReaderAdapter:
    """
    Adapter for reading Instagram identity data via instagrapi.

    Maps vendor Account and User objects to stable application DTOs.
    Handles vendor field conversions (e.g., HttpUrl -> str) and null safety.
    """

    def __init__(self, client_repo: ClientRepository):
        """
        Initialize identity reader.

        Args:
            client_repo: Repository for retrieving authenticated clients.
        """
        self.client_repo = client_repo

    def get_authenticated_account(self, account_id: str) -> AuthenticatedAccountProfile:
        """
        Get authenticated account profile for the logged-in user.

        Calls account_info() on the authenticated client and maps to DTO.

        Args:
            account_id: The application account ID.

        Returns:
            AuthenticatedAccountProfile with all available fields.

        Raises:
            ValueError: If account not found or client not authenticated.
            InstagramAdapterError: If the Instagram API call fails; carries the
                translated ``InstagramFailure`` with preserved metadata so callers
                can distinguish auth/challenge/2FA/transient failures.
        """
        check_rate_limit(account_id)
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            account = client.account_info()
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="account_info",
                account_id=account_id,
            )
            raise InstagramAdapterError(failure) from e

        # Map to DTO, converting HttpUrl fields to strings
        return AuthenticatedAccountProfile(
            pk=account.pk,
            username=account.username,
            full_name=account.full_name,
            biography=account.biography,
            profile_pic_url=self._to_string(account.profile_pic_url),
            follower_count=getattr(account, "follower_count", None),
            following_count=getattr(account, "following_count", None),
            external_url=account.external_url,
            is_private=account.is_private,
            is_verified=account.is_verified,
            is_business=account.is_business,
            email=account.email,
            phone_number=account.phone_number,
        )

    def get_profile_for_hydration(self, account_id: str) -> dict | None:
        """Single user_info() call for background profile hydration.

        user_info(pk) returns full_name, profile_pic_url, follower_count, and
        following_count in one API call — everything hydrate_account_profile
        needs. Avoids the separate account_info() call entirely.

        Returns a dict with the available fields, or None if the client is
        missing or the call fails.
        """
        client = self.client_repo.get(account_id)
        if not client:
            return None
        try:
            user = client.user_info(client.user_id)
            result: dict = {}
            if user.full_name:
                result["full_name"] = user.full_name
            if user.profile_pic_url:
                result["profile_pic_url"] = self._to_string(user.profile_pic_url)
            if user.follower_count is not None:
                result["follower_count"] = user.follower_count
            if user.following_count is not None:
                result["following_count"] = user.following_count
            return result or None
        except Exception:
            return None

    def get_public_user_by_id(self, account_id: str, user_id: int) -> PublicUserProfile:
        """
        Get public user profile by Instagram user ID.

        Calls user_info() on the authenticated client and maps to DTO.

        Args:
            account_id: The application account ID (for client lookup).
            user_id: The Instagram user ID.

        Returns:
            PublicUserProfile with public fields only.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to get User object
            user = client.user_info(user_id)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="user_info",
                account_id=account_id,
            )
            raise ValueError(failure.user_message)

        # Map to DTO, converting HttpUrl fields to strings
        return PublicUserProfile(
            pk=user.pk,
            username=user.username,
            full_name=user.full_name,
            biography=user.biography,
            profile_pic_url=self._to_string(user.profile_pic_url),
            follower_count=user.follower_count,
            following_count=user.following_count,
            media_count=user.media_count,
            is_private=user.is_private,
            is_verified=user.is_verified,
            is_business=user.is_business,
        )

    def get_public_user_by_username(
        self, account_id: str, username: str
    ) -> PublicUserProfile:
        """
        Get public user profile by username.

        Calls user_info_by_username() on the authenticated client and maps to DTO.

        Args:
            account_id: The application account ID (for client lookup).
            username: The Instagram username to look up.

        Returns:
            PublicUserProfile with public fields only.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to get User object
            user = client.user_info_by_username(username)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="user_info_by_username",
                account_id=account_id,
                username=username,
            )
            if failure.http_hint == 429:
                raise InstagramRateLimitError(failure.user_message)
            raise ValueError(failure.user_message)

        # Map to DTO, converting HttpUrl fields to strings
        return PublicUserProfile(
            pk=user.pk,
            username=user.username,
            full_name=user.full_name,
            biography=user.biography,
            profile_pic_url=self._to_string(user.profile_pic_url),
            follower_count=user.follower_count,
            following_count=user.following_count,
            media_count=user.media_count,
            is_private=user.is_private,
            is_verified=user.is_verified,
            is_business=user.is_business,
        )

    def get_user_id_by_username(self, account_id: str, username: str) -> int:
        """
        Resolve a username to its numeric Instagram user ID.

        Uses client.user_id_from_username() which is lighter than fetching
        the full profile. Intended for write flows (follow/unfollow/etc.)
        that only need the numeric ID.

        Args:
            account_id: The application account ID (for client lookup).
            username: The Instagram username to resolve.

        Returns:
            Numeric Instagram user ID as int.

        Raises:
            ValueError: If account not found, client not authenticated, or user
                not found on Instagram.
            InstagramRateLimitError: If Instagram responds with rate-limit signals.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            user_id = client.user_id_from_username(username)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="user_id_from_username",
                account_id=account_id,
                username=username,
            )
            if failure.http_hint == 429:
                raise InstagramRateLimitError(failure.user_message)
            raise ValueError(failure.user_message)

        return int(user_id)

    @staticmethod
    def _to_string(value) -> str | None:
        """
        Convert a value to string, handling HttpUrl and None.

        Instagrapi uses pydantic HttpUrl for some fields.
        """
        if value is None:
            return None
        return str(value)
