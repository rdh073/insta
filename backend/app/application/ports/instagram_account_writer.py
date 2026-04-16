"""Instagram account writer port.

Defines the application-facing contract for mutating the authenticated
account's own settings: privacy, avatar, profile fields, and presence.
"""

from typing import Optional, Protocol

from app.application.dto.instagram_account_dto import AccountProfile


class InstagramAccountWriter(Protocol):
    """Port for self-account mutations (privacy, avatar, profile, presence)."""

    def set_private(self, account_id: str) -> AccountProfile:
        """Switch the authenticated account to private.

        Returns:
            AccountProfile snapshot after the mutation.

        Raises:
            ValueError: If account not found or operation failed.
        """
        ...

    def set_public(self, account_id: str) -> AccountProfile:
        """Switch the authenticated account to public.

        Returns:
            AccountProfile snapshot after the mutation.

        Raises:
            ValueError: If account not found or operation failed.
        """
        ...

    def change_avatar(self, account_id: str, image_path: str) -> AccountProfile:
        """Replace the profile picture from a local image file.

        Args:
            image_path: Local filesystem path to the new avatar image.

        Returns:
            AccountProfile snapshot after the mutation.

        Raises:
            ValueError: If account not found or operation failed.
        """
        ...

    def edit_profile(
        self,
        account_id: str,
        *,
        first_name: Optional[str] = None,
        biography: Optional[str] = None,
        external_url: Optional[str] = None,
    ) -> AccountProfile:
        """Edit profile fields. Only provided kwargs are sent to the vendor.

        Returns:
            AccountProfile snapshot after the mutation.

        Raises:
            ValueError: If account not found or operation failed.
        """
        ...

    def set_presence_disabled(
        self, account_id: str, disabled: bool
    ) -> AccountProfile:
        """Toggle the 'show activity status' presence flag.

        Args:
            disabled: True hides last-active timestamps from other users.

        Returns:
            AccountProfile snapshot after the mutation.

        Raises:
            ValueError: If account not found or operation failed.
        """
        ...
