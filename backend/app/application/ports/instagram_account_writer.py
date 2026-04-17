"""Instagram account writer port.

Defines the application-facing contract for mutating the authenticated
account's own settings: privacy, avatar, profile fields, presence, and
contact-confirmation (email / phone) requests.
"""

from typing import Optional, Protocol

from app.application.dto.instagram_account_dto import (
    AccountConfirmationRequest,
    AccountProfile,
)


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

    def request_email_confirm(
        self, account_id: str, email: str
    ) -> AccountConfirmationRequest:
        """Ask Instagram to send a confirmation code to ``email``.

        This is the first half of an email change: ``account_edit`` queues the
        new address, and this call delivers the verification code the operator
        must submit in a later step. Instagrapi method:
        ``Client.send_confirm_email(email)``.

        Returns:
            AccountConfirmationRequest describing what the vendor accepted.

        Raises:
            ValueError: If account not found, not authenticated, or the vendor
                rejected the request.
        """
        ...

    def request_phone_confirm(
        self, account_id: str, phone: str
    ) -> AccountConfirmationRequest:
        """Ask Instagram to send a confirmation code to ``phone``.

        This is the first half of a phone change: ``account_edit`` queues the
        new number, and this call delivers the verification code the operator
        must submit in a later step. Instagrapi method:
        ``Client.send_confirm_phone_number(phone_number)``.

        Returns:
            AccountConfirmationRequest describing what the vendor accepted.

        Raises:
            ValueError: If account not found, not authenticated, or the vendor
                rejected the request.
        """
        ...
