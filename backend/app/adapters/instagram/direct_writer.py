"""
Instagram direct message writer adapter.

Handles direct message sending and deletion via instagrapi.
Normalizes send results and thread creation operations.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.application.dto.instagram_direct_dto import (
    DirectParticipantSummary,
    DirectThreadSummary,
    DirectMessageSummary,
    DirectMessageAck,
    DirectActionReceipt,
)
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.client_guard import get_guarded_client
from app.adapters.instagram.direct_reader import InstagramDirectReaderAdapter
from app.adapters.instagram.error_utils import (
    attach_instagram_failure,
    translate_instagram_error,
)


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
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Call vendor method to find or create thread
            thread = client.direct_thread_by_participants(participant_user_ids)

            # Map to DTO
            return self._map_find_or_create_thread_response(thread)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="find_or_create_thread", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

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
        client = get_guarded_client(self.client_repo, account_id)

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
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

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
        client = get_guarded_client(self.client_repo, account_id)

        try:
            # Call vendor method to send to users
            message = client.direct_send(text, user_ids=user_ids)

            # Map to DTO (may not have direct_thread_id yet)
            return InstagramDirectReaderAdapter._map_message_to_summary(message)

        except Exception as e:
            failure = translate_instagram_error(
                e, operation="send_to_users", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

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
        client = get_guarded_client(self.client_repo, account_id)

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
        client = get_guarded_client(self.client_repo, account_id)

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
        client = get_guarded_client(self.client_repo, account_id)

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

    # ------------------------------------------------------------------------
    # Attachment send/share
    # ------------------------------------------------------------------------

    _PHOTO_EXTS = frozenset({".jpg", ".jpeg", ".png"})
    _VIDEO_EXTS = frozenset({".mp4"})
    _VOICE_EXTS = frozenset({".m4a", ".mp3", ".ogg"})

    @staticmethod
    def _validate_extension(path: str, allowed: frozenset[str], kind: str) -> None:
        suffix = Path(path).suffix.lower()
        if suffix not in allowed:
            raise ValueError(
                f"Unsupported {kind} extension {suffix!r}; allowed: "
                f"{sorted(allowed)}"
            )

    @staticmethod
    def _coerce_thread_ids(thread_ids: list[str]) -> list[int]:
        return [int(tid) for tid in thread_ids]

    @staticmethod
    def _extract_message_id(response: Any) -> Optional[str]:
        if response is None:
            return None
        for attr in ("id", "item_id", "pk"):
            value = getattr(response, attr, None)
            if value:
                return str(value)
        if isinstance(response, dict):
            for key in ("id", "item_id", "pk", "message_id"):
                value = response.get(key)
                if value:
                    return str(value)
        return None

    def send_photo(
        self,
        account_id: str,
        thread_ids: list[str],
        image_path: str,
    ) -> DirectMessageAck:
        """Send a photo attachment into one or more DM threads."""
        self._validate_extension(image_path, self._PHOTO_EXTS, "photo")
        client = get_guarded_client(self.client_repo, account_id)
        try:
            response = client.direct_send_photo(
                path=image_path,
                thread_ids=self._coerce_thread_ids(thread_ids),
            )
            return DirectMessageAck(
                thread_ids=list(thread_ids),
                kind="photo",
                message_id=self._extract_message_id(response),
                sent_at=datetime.now(tz=timezone.utc),
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="direct_send_photo", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    def send_video(
        self,
        account_id: str,
        thread_ids: list[str],
        video_path: str,
    ) -> DirectMessageAck:
        """Send a video attachment into one or more DM threads."""
        self._validate_extension(video_path, self._VIDEO_EXTS, "video")
        client = get_guarded_client(self.client_repo, account_id)
        try:
            response = client.direct_send_video(
                path=video_path,
                thread_ids=self._coerce_thread_ids(thread_ids),
            )
            return DirectMessageAck(
                thread_ids=list(thread_ids),
                kind="video",
                message_id=self._extract_message_id(response),
                sent_at=datetime.now(tz=timezone.utc),
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="direct_send_video", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    def send_voice(
        self,
        account_id: str,
        thread_ids: list[str],
        audio_path: str,
    ) -> DirectMessageAck:
        """Send a voice-note attachment into one or more DM threads."""
        self._validate_extension(audio_path, self._VOICE_EXTS, "voice")
        client = get_guarded_client(self.client_repo, account_id)
        try:
            response = client.direct_send_voice(
                path=audio_path,
                thread_ids=self._coerce_thread_ids(thread_ids),
            )
            return DirectMessageAck(
                thread_ids=list(thread_ids),
                kind="voice",
                message_id=self._extract_message_id(response),
                sent_at=datetime.now(tz=timezone.utc),
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="direct_send_voice", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    def share_media(
        self,
        account_id: str,
        thread_ids: list[str],
        media_id: str,
    ) -> DirectMessageAck:
        """Share an existing Instagram post into one or more DM threads."""
        client = get_guarded_client(self.client_repo, account_id)
        try:
            response = client.direct_media_share(
                media_id=media_id,
                thread_ids=self._coerce_thread_ids(thread_ids),
            )
            return DirectMessageAck(
                thread_ids=list(thread_ids),
                kind="media_share",
                message_id=self._extract_message_id(response),
                sent_at=datetime.now(tz=timezone.utc),
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="direct_media_share", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    def share_story(
        self,
        account_id: str,
        thread_ids: list[str],
        story_pk: int,
    ) -> DirectMessageAck:
        """Share an existing Instagram story into one or more DM threads."""
        client = get_guarded_client(self.client_repo, account_id)
        try:
            response = client.direct_story_share(
                story_pk=int(story_pk),
                thread_ids=self._coerce_thread_ids(thread_ids),
            )
            return DirectMessageAck(
                thread_ids=list(thread_ids),
                kind="story_share",
                message_id=self._extract_message_id(response),
                sent_at=datetime.now(tz=timezone.utc),
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="direct_story_share", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    # ------------------------------------------------------------------------
    # Thread management (mute / unmute / hide / mark-unread / profile-share)
    # ------------------------------------------------------------------------

    def mute_thread(
        self,
        account_id: str,
        direct_thread_id: str,
    ) -> DirectActionReceipt:
        """Mute notifications for a thread via instagrapi ``direct_thread_mute``."""
        client = get_guarded_client(self.client_repo, account_id)
        try:
            client.direct_thread_mute(int(direct_thread_id))
            return DirectActionReceipt(
                action_id=direct_thread_id,
                success=True,
                reason="Thread muted",
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="mute_thread", account_id=account_id
            )
            return DirectActionReceipt(
                action_id=direct_thread_id,
                success=False,
                reason=failure.user_message,
            )

    def unmute_thread(
        self,
        account_id: str,
        direct_thread_id: str,
    ) -> DirectActionReceipt:
        """Unmute a thread via instagrapi ``direct_thread_unmute``."""
        client = get_guarded_client(self.client_repo, account_id)
        try:
            client.direct_thread_unmute(int(direct_thread_id))
            return DirectActionReceipt(
                action_id=direct_thread_id,
                success=True,
                reason="Thread unmuted",
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="unmute_thread", account_id=account_id
            )
            return DirectActionReceipt(
                action_id=direct_thread_id,
                success=False,
                reason=failure.user_message,
            )

    def hide_thread(
        self,
        account_id: str,
        direct_thread_id: str,
        move_to_spam: bool = False,
    ) -> DirectActionReceipt:
        """Hide a thread from the inbox via instagrapi ``direct_thread_hide``."""
        client = get_guarded_client(self.client_repo, account_id)
        try:
            client.direct_thread_hide(int(direct_thread_id), move_to_spam=bool(move_to_spam))
            return DirectActionReceipt(
                action_id=direct_thread_id,
                success=True,
                reason="Thread moved to spam" if move_to_spam else "Thread hidden",
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="hide_thread", account_id=account_id
            )
            return DirectActionReceipt(
                action_id=direct_thread_id,
                success=False,
                reason=failure.user_message,
            )

    def mark_thread_unread(
        self,
        account_id: str,
        direct_thread_id: str,
    ) -> DirectActionReceipt:
        """Mark a thread as unread via instagrapi ``direct_thread_mark_unread``."""
        client = get_guarded_client(self.client_repo, account_id)
        try:
            client.direct_thread_mark_unread(int(direct_thread_id))
            return DirectActionReceipt(
                action_id=direct_thread_id,
                success=True,
                reason="Thread marked as unread",
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="mark_thread_unread", account_id=account_id
            )
            return DirectActionReceipt(
                action_id=direct_thread_id,
                success=False,
                reason=failure.user_message,
            )

    def share_profile(
        self,
        account_id: str,
        thread_ids: list[str],
        user_id: int,
    ) -> DirectMessageAck:
        """Share a user profile to one or more DM threads via ``direct_profile_share``.

        instagrapi expects ``user_id`` as a string identifier for the profile
        being shared and ``thread_ids`` as a list of ints for the recipients.
        """
        client = get_guarded_client(self.client_repo, account_id)
        try:
            response = client.direct_profile_share(
                user_id=str(int(user_id)),
                thread_ids=self._coerce_thread_ids(thread_ids),
            )
            return DirectMessageAck(
                thread_ids=list(thread_ids),
                kind="profile_share",
                message_id=self._extract_message_id(response),
                sent_at=datetime.now(tz=timezone.utc),
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="direct_profile_share", account_id=account_id
            )
            raise attach_instagram_failure(ValueError(failure.user_message), failure) from e

    @staticmethod
    def _map_find_or_create_thread_response(thread: Any) -> DirectThreadSummary:
        """Map find/create response into a stable thread summary.

        ``direct_thread_by_participants`` can return either a vendor ``DirectThread``
        model or a raw dict payload depending on instagrapi/runtime version.
        """
        if isinstance(thread, dict):
            return InstagramDirectWriterAdapter._map_thread_payload_to_summary(thread)
        return InstagramDirectReaderAdapter._map_thread_to_summary(thread, is_pending=False)

    @staticmethod
    def _map_thread_payload_to_summary(payload: dict[str, Any]) -> DirectThreadSummary:
        """Map a raw thread payload dict into DirectThreadSummary."""
        thread = InstagramDirectWriterAdapter._extract_thread_payload(payload)

        direct_thread_id = (
            InstagramDirectWriterAdapter._first_non_empty_string(
                thread.get("thread_id"),
                thread.get("id"),
                thread.get("thread_v2_id"),
                payload.get("thread_id"),
                payload.get("id"),
                thread.get("pk"),
                payload.get("pk"),
            )
            or ""
        )
        pk = InstagramDirectWriterAdapter._to_int(
            thread.get("pk")
            if thread.get("pk") is not None
            else thread.get("thread_pk")
        )

        participants: list[DirectParticipantSummary] = []
        users = thread.get("users")
        if isinstance(users, list):
            for user in users:
                participant = InstagramDirectWriterAdapter._map_participant_payload(user)
                if participant is not None:
                    participants.append(participant)

        last_message = None
        last_message_payload = InstagramDirectWriterAdapter._extract_last_message_payload(thread)
        if last_message_payload is not None and direct_thread_id:
            last_message = InstagramDirectWriterAdapter._map_message_payload_to_summary(
                last_message_payload, direct_thread_id
            )

        return DirectThreadSummary(
            direct_thread_id=direct_thread_id,
            pk=pk,
            participants=participants,
            last_message=last_message,
            is_pending=False,
        )

    @staticmethod
    def _extract_thread_payload(payload: dict[str, Any]) -> dict[str, Any]:
        """Return the concrete thread dict from possible envelope shapes."""
        thread = payload.get("thread")
        if isinstance(thread, dict):
            return thread
        return payload

    @staticmethod
    def _map_participant_payload(user: Any) -> Optional[DirectParticipantSummary]:
        """Map a participant user dict into DirectParticipantSummary."""
        if not isinstance(user, dict):
            return None

        user_id = InstagramDirectWriterAdapter._to_int(
            user.get("pk")
            if user.get("pk") is not None
            else user.get("id")
            if user.get("id") is not None
            else user.get("user_id")
        )
        if user_id is None:
            return None

        username = (
            InstagramDirectWriterAdapter._first_non_empty_string(user.get("username")) or ""
        )

        return DirectParticipantSummary(
            user_id=user_id,
            username=username,
            full_name=InstagramDirectWriterAdapter._first_non_empty_string(user.get("full_name")),
            profile_pic_url=InstagramDirectReaderAdapter._to_string(
                user.get("profile_pic_url")
            ),
            is_private=(
                user.get("is_private") if isinstance(user.get("is_private"), bool) else None
            ),
        )

    @staticmethod
    def _extract_last_message_payload(thread: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Extract the most recent message payload from known dict shapes."""
        for key in ("items", "messages"):
            items = thread.get(key)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        return item

        for key in ("last_permanent_item", "last_message", "last_item"):
            value = thread.get(key)
            if isinstance(value, dict):
                return value

        return None

    @staticmethod
    def _map_message_payload_to_summary(
        message: dict[str, Any],
        direct_thread_id: str,
    ) -> Optional[DirectMessageSummary]:
        """Map a raw message payload dict into DirectMessageSummary."""
        direct_message_id = InstagramDirectWriterAdapter._first_non_empty_string(
            message.get("id"),
            message.get("item_id"),
            message.get("pk"),
            message.get("client_context"),
        )
        if direct_message_id is None:
            return None

        return DirectMessageSummary(
            direct_message_id=direct_message_id,
            direct_thread_id=direct_thread_id,
            sender_user_id=InstagramDirectWriterAdapter._to_int(
                message.get("user_id")
                if message.get("user_id") is not None
                else message.get("sender_id")
            ),
            sent_at=InstagramDirectWriterAdapter._to_datetime(
                message.get("timestamp")
                if message.get("timestamp") is not None
                else message.get("timestamp_ms")
            ),
            item_type=InstagramDirectWriterAdapter._first_non_empty_string(
                message.get("item_type")
            ),
            text=InstagramDirectWriterAdapter._first_non_empty_string(message.get("text")),
            is_shh_mode=(
                message.get("is_shh_mode")
                if isinstance(message.get("is_shh_mode"), bool)
                else None
            ),
        )

    @staticmethod
    def _first_non_empty_string(*values: Any) -> Optional[str]:
        """Return the first non-empty string representation of the given values."""
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        """Convert value to int when possible."""
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_datetime(value: Any) -> Optional[datetime]:
        """Convert timestamp-like payload values to UTC datetime."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value

        numeric: float
        try:
            numeric = float(str(value))
        except (TypeError, ValueError):
            return None

        # Instagram payloads often use microseconds; keep conversion deterministic.
        if numeric > 1e14:
            numeric /= 1_000_000.0
        elif numeric > 1e11:
            numeric /= 1_000.0

        try:
            return datetime.fromtimestamp(numeric, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
