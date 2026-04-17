"""Instagram media writer adapter.

Maps media-mutating operations through instagrapi into the
InstagramMediaWriter port: like/unlike, caption edit, delete,
pin/unpin, archive/unarchive, and collection bookmarking.
"""

from typing import Optional

from app.application.dto.instagram_media_dto import MediaActionReceipt
from app.application.ports.repositories import ClientRepository
from app.adapters.instagram.client_guard import get_guarded_client
from app.adapters.instagram.error_utils import translate_instagram_error


class InstagramMediaWriterAdapter:
    """Adapter for Instagram media mutations (engagement + lifecycle + collections)."""

    def __init__(self, client_repo: ClientRepository):
        self.client_repo = client_repo

    def like_media(self, account_id: str, media_id: str) -> bool:
        """Like a post via instagrapi."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            return client.media_like(media_id)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="media_like",
                account_id=account_id,
            )
            raise ValueError(failure.user_message)

    def unlike_media(self, account_id: str, media_id: str) -> bool:
        """Remove a like from a post via instagrapi."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            return client.media_unlike(media_id)
        except Exception as e:
            failure = translate_instagram_error(
                e,
                operation="media_unlike",
                account_id=account_id,
            )
            raise ValueError(failure.user_message)

    def edit_caption(
        self, account_id: str, media_id: str, caption: str
    ) -> MediaActionReceipt:
        """Edit a published post's caption via instagrapi.media_edit."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            client.media_edit(media_id, caption)
            return MediaActionReceipt(
                action_id=media_id, success=True, reason="Caption updated"
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="media_edit", account_id=account_id
            )
            return MediaActionReceipt(
                action_id=media_id, success=False, reason=failure.user_message
            )

    def delete_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Permanently delete a post via instagrapi.media_delete."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            client.media_delete(media_id)
            return MediaActionReceipt(
                action_id=media_id, success=True, reason="Media deleted"
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="media_delete", account_id=account_id
            )
            return MediaActionReceipt(
                action_id=media_id, success=False, reason=failure.user_message
            )

    def pin_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Pin a post to the profile grid via instagrapi.media_pin.

        instagrapi's ``media_pin`` accepts ``media_pk`` (digits-only) — convert
        from the canonical ``"{pk}_{user_id}"`` ``media_id`` first.
        """
        client = get_guarded_client(self.client_repo, account_id)

        try:
            media_pk = client.media_pk(media_id)
            client.media_pin(media_pk)
            return MediaActionReceipt(
                action_id=media_id, success=True, reason="Media pinned"
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="media_pin", account_id=account_id
            )
            return MediaActionReceipt(
                action_id=media_id, success=False, reason=failure.user_message
            )

    def unpin_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Unpin a previously pinned post via instagrapi.media_unpin (takes media_pk)."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            media_pk = client.media_pk(media_id)
            client.media_unpin(media_pk)
            return MediaActionReceipt(
                action_id=media_id, success=True, reason="Media unpinned"
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="media_unpin", account_id=account_id
            )
            return MediaActionReceipt(
                action_id=media_id, success=False, reason=failure.user_message
            )

    def archive_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Archive a post via instagrapi.media_archive (hidden from profile)."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            client.media_archive(media_id)
            return MediaActionReceipt(
                action_id=media_id, success=True, reason="Media archived"
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="media_archive", account_id=account_id
            )
            return MediaActionReceipt(
                action_id=media_id, success=False, reason=failure.user_message
            )

    def unarchive_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Restore an archived post via instagrapi.media_unarchive."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            client.media_unarchive(media_id)
            return MediaActionReceipt(
                action_id=media_id, success=True, reason="Media unarchived"
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="media_unarchive", account_id=account_id
            )
            return MediaActionReceipt(
                action_id=media_id, success=False, reason=failure.user_message
            )

    def save_media(
        self,
        account_id: str,
        media_id: str,
        collection_pk: Optional[int] = None,
    ) -> MediaActionReceipt:
        """Bookmark a post into a saved collection via instagrapi.media_save."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            client.media_save(media_id, collection_pk)
            target = (
                f"collection {collection_pk}"
                if collection_pk is not None
                else "default collection"
            )
            return MediaActionReceipt(
                action_id=media_id,
                success=True,
                reason=f"Media saved to {target}",
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="media_save", account_id=account_id
            )
            return MediaActionReceipt(
                action_id=media_id, success=False, reason=failure.user_message
            )

    def unsave_media(
        self,
        account_id: str,
        media_id: str,
        collection_pk: Optional[int] = None,
    ) -> MediaActionReceipt:
        """Remove a post from a saved collection via instagrapi.media_unsave."""
        client = get_guarded_client(self.client_repo, account_id)

        try:
            client.media_unsave(media_id, collection_pk)
            return MediaActionReceipt(
                action_id=media_id, success=True, reason="Media unsaved"
            )
        except Exception as e:
            failure = translate_instagram_error(
                e, operation="media_unsave", account_id=account_id
            )
            return MediaActionReceipt(
                action_id=media_id, success=False, reason=failure.user_message
            )
