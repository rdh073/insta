"""
Instagram direct message reader adapter.

Maps instagrapi DirectThread, DirectMessage, and UserShort objects to stable DTOs.
Handles thread listing, search, and message retrieval.
"""

from typing import Any, Optional

from app.application.dto.instagram_direct_dto import (
    DirectParticipantSummary,
    DirectMessageSummary,
    DirectThreadSummary,
    DirectThreadDetail,
    DirectSearchUserSummary,
)
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.error_utils import (
    attach_instagram_failure,
    translate_instagram_error,
)


class InstagramDirectReaderAdapter:
    """
    Adapter for reading Instagram direct messages via instagrapi.

    Maps vendor DirectThread/DirectMessage/UserShort objects to stable DTOs.
    Centralizes vendor-to-DTO translation for direct message reads.
    """

    def __init__(self, client_repo: ClientRepository):
        """
        Initialize direct reader.

        Args:
            client_repo: Repository for retrieving authenticated clients.
        """
        self.client_repo = client_repo

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
            filter_name: Optional filter.
            thread_message_limit: Messages to include per thread.

        Returns:
            List of DirectThreadSummary.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to list threads
            threads = client.direct_threads(
                amount=amount,
                selected_filter=filter_name,
                thread_message_limit=thread_message_limit,
            )

            # Map each thread to DTO
            return [self._map_thread_to_summary(t, is_pending=False) for t in threads]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="list_inbox_threads", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    def list_pending_threads(
        self,
        account_id: str,
        amount: int = 20,
    ) -> list[DirectThreadSummary]:
        """
        List pending direct message requests.

        Args:
            account_id: The application account ID (for client lookup).
            amount: Maximum threads to retrieve.

        Returns:
            List of DirectThreadSummary marked as pending.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to list pending
            threads = client.direct_pending_inbox(amount=amount)

            # Map each thread to DTO with pending flag
            return [self._map_thread_to_summary(t, is_pending=True) for t in threads]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="list_pending_threads", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

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
            DirectThreadDetail with messages.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # instagrapi expects int thread ID
            thread = client.direct_thread(int(direct_thread_id), amount=amount)

            # Map thread summary
            summary = self._map_thread_to_summary(thread, is_pending=False)

            # Map thread messages
            messages = []
            if hasattr(thread, "messages") and thread.messages:
                messages = [self._map_message_to_summary(m) for m in thread.messages]

            return DirectThreadDetail(summary=summary, messages=messages)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="get_direct_thread", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

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
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # instagrapi expects int thread ID
            messages = client.direct_messages(int(direct_thread_id), amount=amount)

            # Map each message to DTO
            return [self._map_message_to_summary(m, direct_thread_id) for m in messages]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="list_direct_messages", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    def search_threads(
        self,
        account_id: str,
        query: str,
    ) -> list[DirectSearchUserSummary]:
        """
        Search for direct users.

        Args:
            account_id: The application account ID (for client lookup).
            query: Search query.

        Returns:
            List of DirectSearchUserSummary matching query.

        Raises:
            ValueError: If account not found or client not authenticated.
        """
        client = self.client_repo.get(account_id)
        if not client:
            raise ValueError(f"Account {account_id} not found or not authenticated")

        try:
            # Call vendor method to search
            users = client.direct_search(query)

            # direct_search returns UserShort-like results, not thread objects.
            return [self._map_search_user_to_summary(user) for user in users]

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="search_direct_threads", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    @staticmethod
    def _map_thread_to_summary(thread: Any, is_pending: bool = False) -> DirectThreadSummary:
        """
        Map instagrapi DirectThread object to DirectThreadSummary DTO.

        Args:
            thread: instagrapi DirectThread object.
            is_pending: Whether this is a pending thread.

        Returns:
            DirectThreadSummary DTO.
        """
        # Extract participants
        participants = []
        if hasattr(thread, "users") and thread.users:
            for user in thread.users:
                participant = DirectParticipantSummary(
                    user_id=user.pk,
                    username=user.username,
                    full_name=getattr(user, "full_name", None),
                    profile_pic_url=InstagramDirectReaderAdapter._to_string(
                        getattr(user, "profile_pic_url", None)
                    ),
                    is_private=getattr(user, "is_private", None),
                )
                participants.append(participant)

        # Extract last message if present
        last_message = None
        if hasattr(thread, "messages") and thread.messages and len(thread.messages) > 0:
            last_msg = thread.messages[0]  # Usually first is most recent
            last_message = InstagramDirectReaderAdapter._map_message_to_summary(
                last_msg, thread.id
            )

        return DirectThreadSummary(
            direct_thread_id=thread.id,
            pk=getattr(thread, "pk", None),
            participants=participants,
            last_message=last_message,
            is_pending=is_pending,
        )

    @staticmethod
    def _map_message_to_summary(
        message: Any, direct_thread_id: Optional[str] = None
    ) -> DirectMessageSummary:
        """
        Map instagrapi DirectMessage object to DirectMessageSummary DTO.

        Args:
            message: instagrapi DirectMessage object.
            direct_thread_id: Optional thread ID for context.

        Returns:
            DirectMessageSummary DTO.
        """
        return DirectMessageSummary(
            direct_message_id=message.id,
            direct_thread_id=direct_thread_id or getattr(message, "thread_id", None),
            sender_user_id=getattr(message, "user_id", None),
            sent_at=getattr(message, "timestamp", None),
            item_type=getattr(message, "item_type", None),
            text=getattr(message, "text", None),
            is_shh_mode=getattr(message, "is_shh_mode", None),
        )

    @staticmethod
    def _map_search_user_to_summary(user: Any) -> DirectSearchUserSummary:
        """
        Map instagrapi UserShort-like direct_search result to DTO.

        Args:
            user: instagrapi UserShort-like object.

        Returns:
            DirectSearchUserSummary DTO.
        """
        return DirectSearchUserSummary(
            user_id=getattr(user, "pk"),
            username=getattr(user, "username", ""),
            full_name=getattr(user, "full_name", None),
            profile_pic_url=InstagramDirectReaderAdapter._to_string(
                getattr(user, "profile_pic_url", None)
            ),
            is_private=getattr(user, "is_private", None),
            is_verified=getattr(user, "is_verified", None),
        )

    @staticmethod
    def _to_string(value: Any) -> Optional[str]:
        """
        Convert a value to string, handling HttpUrl and None.

        Instagrapi uses pydantic HttpUrl for some fields.
        """
        if value is None:
            return None
        return str(value)
