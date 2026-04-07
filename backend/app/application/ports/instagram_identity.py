"""
Instagram identity reader port.

Defines the application-facing contract for reading authenticated account
and public user profile data.
"""

from typing import Protocol

from app.application.dto.instagram_identity_dto import (
    AuthenticatedAccountProfile,
    PublicUserProfile,
)


class InstagramIdentityReader(Protocol):
    """
    Port for reading Instagram account and user profile data.

    Separates authenticated account reads (with private fields) from
    public user profile reads. Implementation handles mapping from
    instagrapi Account and User objects to stable application DTOs.
    """

    def get_authenticated_account(self, account_id: str) -> AuthenticatedAccountProfile:
        """
        Get authenticated account profile for the logged-in user.

        Includes private/self-only fields like email and phone_number.

        Args:
            account_id: The application account ID.

        Returns:
            AuthenticatedAccountProfile with all available fields.

        Raises:
            Exception: If account not found or authentication fails.
        """
        ...

    def get_public_user_by_id(self, account_id: str, user_id: int) -> PublicUserProfile:
        """
        Get public user profile by Instagram user ID.

        Args:
            account_id: The application account ID (for client lookup).
            user_id: The Instagram user ID.

        Returns:
            PublicUserProfile with public fields only.

        Raises:
            Exception: If user not found or read fails.
        """
        ...

    def get_public_user_by_username(
        self, account_id: str, username: str
    ) -> PublicUserProfile:
        """
        Get public user profile by username.

        Args:
            account_id: The application account ID (for client lookup).
            username: The Instagram username to look up.

        Returns:
            PublicUserProfile with public fields only.

        Raises:
            Exception: If user not found or read fails.
        """
        ...

    def get_profile_for_hydration(self, account_id: str) -> dict | None:
        """
        Single user_info() call returning all fields needed for background hydration.

        Returns a dict with any of: full_name, profile_pic_url, follower_count,
        following_count. Returns None if the client is missing or the call fails.

        Do not call in request-path code — intended for background tasks only.
        """
        ...

    def get_user_id_by_username(self, account_id: str, username: str) -> int:
        """
        Resolve a username to its numeric Instagram user ID.

        Lighter than get_public_user_by_username because it only fetches
        the numeric ID, not the full profile. Intended for write flows
        (follow, unfollow, remove_follower, close_friends) that only need
        the ID to pass to the relationship writer.

        Args:
            account_id: The application account ID (for client lookup).
            username: The Instagram username to resolve.

        Returns:
            Numeric Instagram user ID as int.

        Raises:
            ValueError: If the username is not found or the client is missing.
            InstagramRateLimitError: If Instagram responds with rate-limit signals.
        """
        ...
