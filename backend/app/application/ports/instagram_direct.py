"""
Instagram direct message reader and writer ports.

Separates direct message retrieval from direct message sending/deletion.
Prevents instagrapi DirectThread and DirectMessage objects from leaking into application code.

NAMING RULE: All parameters and return values use direct_thread_id and direct_message_id
to avoid collision with workflow thread_id used by AI graph execution.
"""

from typing import Protocol

from app.application.dto.instagram_direct_dto import (
    DirectThreadSummary,
    DirectThreadDetail,
    DirectMessageSummary,
    DirectSearchUserSummary,
    DirectActionReceipt,
)


class InstagramDirectReader(Protocol):
    """Port for reading Instagram direct messages and threads.

    Handles inbox retrieval, thread lookup, and message listing.
    Implementation depends on instagrapi; application layer depends on DTOs.
    """

    def list_inbox_threads(
        self,
        account_id: str,
        amount: int = 20,
        filter_name: str = "",
        thread_message_limit: int = 10,
    ) -> list[DirectThreadSummary]:
        """
        List threads in the inbox.

        Args:
            account_id: The application account ID (for client lookup).
            amount: Maximum threads to retrieve.
            filter_name: Optional filter (e.g., "unread").
            thread_message_limit: Messages to include in each thread summary.

        Returns:
            List of DirectThreadSummary.

        Raises:
            Exception: If read fails or account not authenticated.
        """
        ...

    def list_pending_threads(
        self,
        account_id: str,
        amount: int = 20,
    ) -> list[DirectThreadSummary]:
        """
        List pending direct message requests (from non-followers).

        Args:
            account_id: The application account ID (for client lookup).
            amount: Maximum threads to retrieve.

        Returns:
            List of DirectThreadSummary marked as pending.

        Raises:
            Exception: If read fails or account not authenticated.
        """
        ...

    def get_thread(
        self,
        account_id: str,
        direct_thread_id: str,
        amount: int = 20,
    ) -> DirectThreadDetail:
        """
        Get a specific thread with messages.

        Args:
            account_id: The application account ID (for client lookup).
            direct_thread_id: The Instagram direct thread ID.
            amount: Maximum messages to retrieve.

        Returns:
            DirectThreadDetail with summary and messages.

        Raises:
            Exception: If thread not found or read fails.
        """
        ...

    def list_messages(
        self,
        account_id: str,
        direct_thread_id: str,
        amount: int = 20,
    ) -> list[DirectMessageSummary]:
        """
        List messages for a thread.

        Args:
            account_id: The application account ID (for client lookup).
            direct_thread_id: The Instagram direct thread ID.
            amount: Maximum messages to retrieve.

        Returns:
            List of DirectMessageSummary.

        Raises:
            Exception: If thread not found or read fails.
        """
        ...

    def search_threads(
        self,
        account_id: str,
        query: str,
    ) -> list[DirectSearchUserSummary]:
        """
        Search for direct users by query.

        Args:
            account_id: The application account ID (for client lookup).
            query: Search query (username, full name, etc.).

        Returns:
            List of matching DirectSearchUserSummary.

        Raises:
            Exception: If search fails or account not authenticated.
        """
        ...


class InstagramDirectWriter(Protocol):
    """Port for creating and managing Instagram direct messages.

    Handles thread creation and message sending/deletion.
    Implementation depends on instagrapi; application layer depends on DTOs.
    """

    def find_or_create_thread(
        self,
        account_id: str,
        participant_user_ids: list[int],
    ) -> DirectThreadSummary:
        """
        Find existing thread or create new one with participants.

        Args:
            account_id: The application account ID (for client lookup).
            participant_user_ids: List of user IDs for thread participants.

        Returns:
            DirectThreadSummary of found or created thread.

        Raises:
            Exception: If operation fails.
        """
        ...

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
            Exception: If thread not found or send fails.
        """
        ...

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
            Exception: If send fails.
        """
        ...

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
            Exception: If deletion fails.
        """
        ...

    def approve_pending_thread(
        self,
        account_id: str,
        direct_thread_id: str,
    ) -> DirectActionReceipt:
        """
        Approve a pending DM request so it moves to the main inbox.

        Args:
            account_id: The application account ID (for client lookup).
            direct_thread_id: The pending thread ID to approve.

        Returns:
            DirectActionReceipt with result.

        Raises:
            Exception: If approval fails.
        """
        ...

    def mark_thread_seen(
        self,
        account_id: str,
        direct_thread_id: str,
    ) -> DirectActionReceipt:
        """
        Mark the most recent message in a thread as seen.

        Args:
            account_id: The application account ID (for client lookup).
            direct_thread_id: The thread ID to mark as seen.

        Returns:
            DirectActionReceipt with result.

        Raises:
            Exception: If the operation fails.
        """
        ...
