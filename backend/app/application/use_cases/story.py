"""Story use cases - application orchestration for Instagram story operations.

Owns precondition enforcement, input validation, and application-level policy
for story media kind, audience, and URL format before delegating to ports.

Policy owned here (not in router or adapter):
  - media_kind must be "photo" or "video" (validated via MediaKind domain enum)
  - audience must be "default" or "close_friends" (validated via StoryAudience domain enum)
  - story_pk and user_id must be positive integers (validated via StoryPK, UserID value objects)
  - media_path and url must be non-empty strings (validated via domain value objects)
  - mark_seen: story_pks list must not be empty
"""

from __future__ import annotations

from typing import Optional

from app.application.dto.instagram_story_dto import (
    StorySummary,
    StoryDetail,
    StoryPublishRequest,
    StoryActionReceipt,
)
from app.application.ports.instagram_stories import (
    InstagramStoryReader,
    InstagramStoryPublisher,
)
from app.application.ports.repositories import AccountRepository, ClientRepository
from app.domain.story import (
    InvalidEnumValue,
    InvalidIdentifier,
    InvalidComposite,
    MediaKind,
    StoryAudience,
    StoryPK,
    UserID,
    StoryURL,
    QueryAmount,
    StoryAggregate,
)


class StoryUseCases:
    """Application orchestration for Instagram story operations.

    Owns precondition enforcement (account exists, authenticated),
    input validation (media_kind, audience, story_pk, user_id),
    and URL sanity checks.
    The underlying ports handle vendor calls and DTO mapping.
    """

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        story_reader: InstagramStoryReader,
        story_publisher: InstagramStoryPublisher,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.story_reader = story_reader
        self.story_publisher = story_publisher

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

    def get_story_pk_from_url(self, url: str) -> int:
        """Resolve story PK from a story URL.

        Args:
            url: Instagram story URL (must start with 'http').

        Returns:
            Story primary key.

        Raises:
            ValueError: If url is empty or does not start with 'http'.
        """
        try:
            story_url = StoryURL(url)
            return self.story_reader.get_story_pk_from_url(str(story_url))
        except InvalidComposite as e:
            # Convert domain validation error to ValueError for backward compatibility
            raise ValueError(str(e)) from e

    def get_story(
        self,
        account_id: str,
        story_pk: int,
        use_cache: bool = True,
    ) -> StoryDetail:
        """Get story with detailed metadata.

        Args:
            account_id: Application account ID.
            story_pk: Instagram story primary key (positive integer).
            use_cache: Whether to use cached story data.

        Returns:
            StoryDetail with overlay counts.

        Raises:
            ValueError: If account not found, not authenticated, or story_pk invalid.
        """
        self._require_authenticated(account_id)
        try:
            pk = StoryPK(story_pk)
            return self.story_reader.get_story(account_id, int(pk), use_cache)
        except InvalidIdentifier as e:
            raise ValueError(str(e)) from e

    def list_user_stories(
        self,
        account_id: str,
        user_id: int,
        amount: Optional[int] = None,
    ) -> list[StorySummary]:
        """List stories for a user.

        Args:
            account_id: Application account ID.
            user_id: Instagram user ID (positive integer).
            amount: Maximum stories to retrieve (None = all available).

        Returns:
            List of StorySummary in order returned by vendor.

        Raises:
            ValueError: If account not found, not authenticated, user_id invalid,
                        or amount is negative.
        """
        self._require_authenticated(account_id)
        try:
            uid = UserID(user_id)
            if amount is not None:
                if not isinstance(amount, int) or amount < 1:
                    raise ValueError(
                        f"amount must be a positive integer, got {amount!r}"
                    )
                QueryAmount(amount)
            return self.story_reader.list_user_stories(account_id, int(uid), amount)
        except InvalidIdentifier as e:
            raise ValueError(str(e)) from e

    # -------------------------------------------------------------------------
    # Write operations
    # -------------------------------------------------------------------------

    def publish_story(
        self,
        account_id: str,
        request: StoryPublishRequest,
    ) -> StoryDetail:
        """Publish a story with optional overlays.

        Validates application-level policy:
        - media_path must not be empty
        - media_kind must be 'photo' or 'video' (via MediaKind domain enum)
        - audience must be 'default' or 'close_friends' (via StoryAudience domain enum)
        - video requires thumbnail_path

        Args:
            account_id: Application account ID.
            request: StoryPublishRequest with media and composition specs.

        Returns:
            StoryDetail of published story.

        Raises:
            ValueError: If account not found, not authenticated, or request invalid.
        """
        self._require_authenticated(account_id)
        if not request.media_path or not request.media_path.strip():
            raise ValueError("media_path must not be empty")

        try:
            media_kind = MediaKind.validate(request.media_kind)
            audience = StoryAudience.validate(request.audience)
        except InvalidEnumValue as e:
            lowered = str(e).lower()
            if "mediakind" in lowered:
                raise ValueError(
                    f"media_kind must be one of {{photo, video}}, got {request.media_kind!r}"
                ) from e
            raise ValueError(
                f"audience must be one of {{default, close_friends}}, got {request.audience!r}"
            ) from e

        try:
            StoryAggregate(
                story_pk=StoryPK(1),
                media_kind=media_kind,
                audience=audience,
                thumbnail_path=request.thumbnail_path,
            )
        except InvalidComposite as e:
            raise ValueError(str(e)) from e
        return self.story_publisher.publish_story(account_id, request)

    def delete_story(
        self,
        account_id: str,
        story_pk: int,
    ) -> StoryActionReceipt:
        """Delete a story by primary key.

        Args:
            account_id: Application account ID.
            story_pk: Instagram story primary key (positive integer).

        Returns:
            StoryActionReceipt with result.

        Raises:
            ValueError: If account not found, not authenticated, or story_pk invalid.
        """
        self._require_authenticated(account_id)
        try:
            pk = StoryPK(story_pk)
            return self.story_publisher.delete_story(account_id, int(pk))
        except InvalidIdentifier as e:
            raise ValueError(str(e)) from e

    def mark_seen(
        self,
        account_id: str,
        story_pks: list[int],
        skipped_story_pks: Optional[list[int]] = None,
    ) -> StoryActionReceipt:
        """Mark stories as seen.

        Args:
            account_id: Application account ID.
            story_pks: Story PKs to mark as seen (must not be empty).
            skipped_story_pks: Optional story PKs to mark as skipped.

        Returns:
            StoryActionReceipt with result.

        Raises:
            ValueError: If account not found, not authenticated, story_pks is empty,
                        or any PK is not a positive integer.
        """
        self._require_authenticated(account_id)
        if not story_pks:
            raise ValueError("story_pks must not be empty")
        try:
            validated_pks = [int(StoryPK(pk)) for pk in story_pks]
            validated_skipped = None
            if skipped_story_pks:
                validated_skipped = [int(StoryPK(pk)) for pk in skipped_story_pks]
            return self.story_publisher.mark_seen(account_id, validated_pks, validated_skipped)
        except InvalidIdentifier as e:
            raise ValueError(f"all story_pks must be positive integers ({e})") from e
