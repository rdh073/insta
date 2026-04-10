"""
Instagram direct message writer adapter.

Handles direct message sending and deletion via instagrapi.
Normalizes send results and thread creation operations.
"""

from typing import Optional

from app.application.dto.instagram_direct_dto import (
    DirectThreadSummary,
    DirectMessageSummary,
    DirectActionReceipt,
)
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.direct_reader import InstagramDirectReaderAdapter
from app.adapters.instagram.error_utils import translate_instagram_error


class InstagramDirectWriterAdapter:
    """
    Adapter for sending and managing Instagram direct messages via instagrapi.

    Handles thread creation, message sending, and message deletion.
    Maps vendor DirectThread and DirectMessage responses to DTOs.
    """

    def __init__(self, client_repo: ClientRepository):
        """
        Initialize direct writer.

        Args:
            client_repo: Repository for retrieving authenticated clients.
        """
        self.client_repo = client_repo

    def find_or_create_thread(
        self,
        account_id: str,
        participant_user_ids: list[int],
    ) -> DirectThreadSummary:
        """
        Find existing thread or create new one with participants.

        Args:
            account_id: The application account ID (for client lookup).
            participant_user_ids: List of user IDs for thread.

        Returns:
            DirectThreadSummary of found or created thread.

        Raises:
            ValueError: If account not found or operation fails.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to find or create thread
            thread = client.direct_thread_by_participants(participant_user_ids)

            # Map to DTO
            return InstagramDirectReaderAdapter._map_thread_to_summary(thread, is_pending=False)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="find_or_create_thread", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def send_to_thread(
        self,
        account_id: str,
        direct_thread_id: str,
        text: str,
    ) -> DirectMessageSummary:
        """
        Send a message to an existing thread.

        Args:
            account_id: The application account ID (for client lookup).
            direct_thread_id: The Instagram direct thread ID.
            text: Message text content.

        Returns:
            DirectMessageSummary of sent message.

        Raises:
            ValueError: If account not found or send fails.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # instagrapi expects int thread ID
            message = client.direct_answer(int(direct_thread_id), text)

            # Map to DTO
            return InstagramDirectReaderAdapter._map_message_to_summary(
                message, direct_thread_id
            )

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="send_to_thread", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def send_to_users(
        self,
        account_id: str,
        user_ids: list[int],
        text: str,
    ) -> DirectMessageSummary:
        """
        Send a message to one or more users (creates thread if needed).

        Args:
            account_id: The application account ID (for client lookup).
            user_ids: List of user IDs to message.
            text: Message text content.

        Returns:
            DirectMessageSummary of sent message.

        Raises:
            ValueError: If account not found or send fails.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to send to users
            message = client.direct_send(text, user_ids=user_ids)

            # Map to DTO (may not have direct_thread_id yet)
            return InstagramDirectReaderAdapter._map_message_to_summary(message)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="send_to_users", account_id=account_id
            )
            raise ValueError(failure.user_message)

    def delete_message(
        self,
        account_id: str,
        direct_thread_id: str,
        direct_message_id: str,
    ) -> DirectActionReceipt:
        """
        Delete a message from a thread.

        Args:
            account_id: The application account ID (for client lookup).
            direct_thread_id: The Instagram direct thread ID.
            direct_message_id: The message ID to delete.

        Returns:
            DirectActionReceipt with result.

        Raises:
            ValueError: If account not found or deletion fails.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # instagrapi expects int IDs for both thread and message
            client.direct_message_delete(int(direct_thread_id), int(direct_message_id))

            return DirectActionReceipt(
                action_id=direct_message_id,
                success=True,
                reason="Message deleted successfully",
            )

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="delete_direct_message", account_id=account_id
            )
            return DirectActionReceipt(
                action_id=direct_message_id,
                success=False,
                reason=failure.user_message,
            )

    def approve_pending_thread(
        self,
        account_id: str,
        direct_thread_id: str,
    ) -> DirectActionReceipt:
        """Approve a pending DM request, moving it to the main inbox."""
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            client.direct_pending_approve(int(direct_thread_id))
            return DirectActionReceipt(
                action_id=direct_thread_id,
                success=True,
                reason="Pending thread approved",
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="approve_pending_thread", account_id=account_id
            )
            return DirectActionReceipt(
                action_id=direct_thread_id,
                success=False,
                reason=failure.user_message,
            )

    def mark_thread_seen(
        self,
        account_id: str,
        direct_thread_id: str,
    ) -> DirectActionReceipt:
        """Mark the most recent message in a thread as seen."""
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            client.direct_send_seen(int(direct_thread_id))
            return DirectActionReceipt(
                action_id=direct_thread_id,
                success=True,
                reason="Thread marked as seen",
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="mark_thread_seen", account_id=account_id
            )
            return DirectActionReceipt(
                action_id=direct_thread_id,
                success=False,
                reason=failure.user_message,
            )
