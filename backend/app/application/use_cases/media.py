"""Media use cases - application orchestration for Instagram media reads.

Enforces account preconditions and parameter normalization before delegating
to the InstagramMediaReader port. Consumers (router, tool_registry, ai_copilot)
must use this class instead of calling the adapter directly.
"""

from __future__ import annotations

from typing import Optional

from app.application.dto.instagram_identity_dto import PublicUserProfile
from app.application.dto.instagram_media_dto import (
    MediaActionReceipt,
    MediaSummary,
    MediaOembedSummary,
)
from app.application.ports.instagram_media import InstagramMediaReader
from app.application.ports.repositories import AccountRepository, ClientRepository

_AMOUNT_MIN = 1
_AMOUNT_MAX = 200
_AMOUNT_DEFAULT = 12
_CAPTION_MAX_LEN = 2200


class MediaUseCases:
    """Application orchestration for Instagram media reads.

    Owns precondition enforcement (account exists, account authenticated)
    and parameter normalization for all media operations.
    The underlying InstagramMediaReader port is responsible only for
    vendor calls and DTO mapping.
    """

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        media_reader: InstagramMediaReader,
        media_writer=None,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.media_reader = media_reader
        self.media_writer = media_writer

    # -------------------------------------------------------------------------
    # Precondition helpers
    # -------------------------------------------------------------------------

    def _require_authenticated(self, account_id: str) -> None:
        """Raise ValueError if account does not exist or is not authenticated."""
        if not self.account_repo.get(account_id):
            raise ValueError(f"Account {account_id!r} not found")
        if not self.client_repo.exists(account_id):
            raise ValueError(f"Account {account_id!r} is not authenticated")

    # -------------------------------------------------------------------------
    # Read operations
    # -------------------------------------------------------------------------

    def get_media_by_pk(self, account_id: str, media_pk: int) -> MediaSummary:
        """Get media by Instagram primary key.

        Args:
            account_id: Application account ID.
            media_pk: Instagram media primary key (positive integer).

        Returns:
            MediaSummary with full metadata.

        Raises:
            ValueError: If account not found, not authenticated, or media_pk invalid.
        """
        self._require_authenticated(account_id)
        if not isinstance(media_pk, int) or media_pk <= 0:
            raise ValueError(f"media_pk must be a positive integer, got {media_pk!r}")
        return self.media_reader.get_media_by_pk(account_id, media_pk)

    def get_media_by_code(self, account_id: str, code: str) -> MediaSummary:
        """Get media by Instagram code (short URL identifier).

        Normalizes the code by stripping whitespace. The code is the
        alphanumeric segment in Instagram post URLs (e.g. 'CpbDdszj7ei').

        Args:
            account_id: Application account ID.
            code: Instagram media code, optionally with surrounding whitespace.

        Returns:
            MediaSummary with full metadata.

        Raises:
            ValueError: If account not found, not authenticated, or code empty.
        """
        self._require_authenticated(account_id)
        clean_code = code.strip() if code else ""
        if not clean_code:
            raise ValueError("code must not be empty")
        return self.media_reader.get_media_by_code(account_id, clean_code)

    def get_user_medias(
        self,
        account_id: str,
        user_id: int,
        amount: int = _AMOUNT_DEFAULT,
    ) -> list[MediaSummary]:
        """Get media feed for a user.

        Clamps amount to [1, 200] so callers cannot request unbounded pages.

        Args:
            account_id: Application account ID.
            user_id: Instagram user ID (positive integer).
            amount: Number of posts to retrieve. Clamped to [1, 200].

        Returns:
            List of MediaSummary in reverse chronological order.

        Raises:
            ValueError: If account not found, not authenticated, or user_id invalid.
        """
        self._require_authenticated(account_id)
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id must be a positive integer, got {user_id!r}")
        clamped_amount = max(_AMOUNT_MIN, min(amount, _AMOUNT_MAX))
        return self.media_reader.get_user_medias(account_id, user_id, clamped_amount)

    def get_media_oembed(self, account_id: str, url: str) -> MediaOembedSummary:
        """Get oEmbed metadata for an Instagram media URL.

        Args:
            account_id: Application account ID.
            url: Instagram media URL starting with 'http'.

        Returns:
            MediaOembedSummary with embeddable metadata.

        Raises:
            ValueError: If account not found, not authenticated, or URL invalid.
        """
        self._require_authenticated(account_id)
        clean_url = url.strip() if url else ""
        if not clean_url:
            raise ValueError("url must not be empty")
        if not clean_url.startswith("http"):
            raise ValueError(f"url must start with 'http', got {clean_url!r}")
        return self.media_reader.get_media_oembed(account_id, clean_url)

    def list_media_likers(
        self, account_id: str, media_id: str
    ) -> list[PublicUserProfile]:
        """List users who liked a media post.

        Args:
            account_id: Application account ID.
            media_id: Instagram media ID string (e.g. '123_456'). Stripped of
                surrounding whitespace.

        Returns:
            List of PublicUserProfile in Instagram's returned order.

        Raises:
            ValueError: If account not found, not authenticated, or media_id empty.
        """
        self._require_authenticated(account_id)
        clean_id = (media_id or "").strip()
        if not clean_id:
            raise ValueError("media_id must not be empty")
        return self.media_reader.list_media_likers(account_id, clean_id)

    def list_user_clips(
        self,
        account_id: str,
        user_id: int,
        amount: int = _AMOUNT_DEFAULT,
    ) -> list[MediaSummary]:
        """List a user's clip (reels) catalog.

        Clamps amount to [1, 200] so callers cannot request unbounded pages.

        Args:
            account_id: Application account ID.
            user_id: Instagram user ID (positive integer).
            amount: Number of clips to retrieve. Clamped to [1, 200].

        Returns:
            List of MediaSummary representing reels.

        Raises:
            ValueError: If account not found, not authenticated, or user_id invalid.
        """
        self._require_authenticated(account_id)
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id must be a positive integer, got {user_id!r}")
        clamped_amount = max(_AMOUNT_MIN, min(amount, _AMOUNT_MAX))
        return self.media_reader.list_user_clips(account_id, user_id, clamped_amount)

    def list_usertag_medias(
        self,
        account_id: str,
        user_id: int,
        amount: int = _AMOUNT_DEFAULT,
    ) -> list[MediaSummary]:
        """List media in which a user is tagged.

        Clamps amount to [1, 200] so callers cannot request unbounded pages.

        Args:
            account_id: Application account ID.
            user_id: Instagram user ID (positive integer).
            amount: Number of tagged-in media to retrieve. Clamped to [1, 200].

        Returns:
            List of MediaSummary in which the user is tagged.

        Raises:
            ValueError: If account not found, not authenticated, or user_id invalid.
        """
        self._require_authenticated(account_id)
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"user_id must be a positive integer, got {user_id!r}")
        clamped_amount = max(_AMOUNT_MIN, min(amount, _AMOUNT_MAX))
        return self.media_reader.list_usertag_medias(
            account_id, user_id, clamped_amount
        )

    # -------------------------------------------------------------------------
    # Write operations
    # -------------------------------------------------------------------------

    def like_media(self, account_id: str, media_id: str) -> bool:
        """Like a post.

        Args:
            account_id: Authenticated account performing the like.
            media_id: Instagram media ID string.

        Raises:
            ValueError: If account not found, not authenticated, writer not configured, or media_id empty.
        """
        self._require_authenticated(account_id)
        if self.media_writer is None:
            raise ValueError("media writer not configured")
        clean_id = (media_id or "").strip()
        if not clean_id:
            raise ValueError("media_id must not be empty")
        return self.media_writer.like_media(account_id, clean_id)

    def unlike_media(self, account_id: str, media_id: str) -> bool:
        """Remove a like from a post.

        Args:
            account_id: Authenticated account removing the like.
            media_id: Instagram media ID string.

        Raises:
            ValueError: If account not found, not authenticated, writer not configured, or media_id empty.
        """
        self._require_authenticated(account_id)
        if self.media_writer is None:
            raise ValueError("media writer not configured")
        clean_id = (media_id or "").strip()
        if not clean_id:
            raise ValueError("media_id must not be empty")
        return self.media_writer.unlike_media(account_id, clean_id)

    def _prepare_write(self, account_id: str, media_id: str) -> str:
        """Shared precondition for media-write methods.

        Returns the normalized media_id and raises ValueError on any failure.
        """
        self._require_authenticated(account_id)
        if self.media_writer is None:
            raise ValueError("media writer not configured")
        clean_id = (media_id or "").strip()
        if not clean_id:
            raise ValueError("media_id must not be empty")
        return clean_id

    def edit_caption(
        self, account_id: str, media_id: str, caption: str
    ) -> MediaActionReceipt:
        """Edit a published post's caption.

        Raises:
            ValueError: If preconditions fail or caption exceeds Instagram's
                2200-character limit.
        """
        clean_id = self._prepare_write(account_id, media_id)
        if caption is None:
            raise ValueError("caption must not be None")
        if len(caption) > _CAPTION_MAX_LEN:
            raise ValueError(
                f"caption must be <= {_CAPTION_MAX_LEN} characters, got {len(caption)}"
            )
        return self.media_writer.edit_caption(account_id, clean_id, caption)

    def delete_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Permanently delete a post owned by the account."""
        clean_id = self._prepare_write(account_id, media_id)
        return self.media_writer.delete_media(account_id, clean_id)

    def pin_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Pin a post to the profile grid (max 3 pinned)."""
        clean_id = self._prepare_write(account_id, media_id)
        return self.media_writer.pin_media(account_id, clean_id)

    def unpin_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Unpin a previously pinned post."""
        clean_id = self._prepare_write(account_id, media_id)
        return self.media_writer.unpin_media(account_id, clean_id)

    def archive_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Archive a post (hides from public profile)."""
        clean_id = self._prepare_write(account_id, media_id)
        return self.media_writer.archive_media(account_id, clean_id)

    def unarchive_media(self, account_id: str, media_id: str) -> MediaActionReceipt:
        """Restore an archived post to the public profile."""
        clean_id = self._prepare_write(account_id, media_id)
        return self.media_writer.unarchive_media(account_id, clean_id)

    def save_media(
        self,
        account_id: str,
        media_id: str,
        collection_pk: Optional[int] = None,
    ) -> MediaActionReceipt:
        """Bookmark a post into a saved collection.

        Args:
            collection_pk: Optional Instagram collection PK. None saves to the
                default "All Posts" collection.
        """
        clean_id = self._prepare_write(account_id, media_id)
        if collection_pk is not None and (
            not isinstance(collection_pk, int) or collection_pk <= 0
        ):
            raise ValueError(
                f"collection_pk must be a positive integer, got {collection_pk!r}"
            )
        return self.media_writer.save_media(account_id, clean_id, collection_pk)

    def unsave_media(
        self,
        account_id: str,
        media_id: str,
        collection_pk: Optional[int] = None,
    ) -> MediaActionReceipt:
        """Remove a post from a saved collection."""
        clean_id = self._prepare_write(account_id, media_id)
        if collection_pk is not None and (
            not isinstance(collection_pk, int) or collection_pk <= 0
        ):
            raise ValueError(
                f"collection_pk must be a positive integer, got {collection_pk!r}"
            )
        return self.media_writer.unsave_media(account_id, clean_id, collection_pk)
