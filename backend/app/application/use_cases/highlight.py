"""Highlight use cases - application orchestration for Instagram highlight operations.

Owns precondition enforcement, input validation, and application-level policy
before delegating to ports.

Policy owned here (not in router or adapter):
  - highlight_pk and user_id must be positive integers
  - title must not be empty (stripped)
  - story_ids must not be empty for create/add_stories/remove_stories
  - all story_ids must be positive integers
  - cover_story_id must be >= 0 (0 = use default)
  - crop_rect if provided must have exactly 4 float elements, each in [0.0, 1.0]
  - amount must be >= 0 (0 = all available)
  - URL must be non-empty and start with 'http'
"""

from __future__ import annotations

from typing import Optional

from app.application.dto.instagram_highlight_dto import (
    HighlightSummary,
    HighlightDetail,
    HighlightActionReceipt,
)
from app.application.ports.instagram_highlights import (
    InstagramHighlightReader,
    InstagramHighlightWriter,
)
from app.application.ports.repositories import AccountRepository, ClientRepository
from app.domain.highlight import (
    HighlightPK,
    HighlightTitle,
    StoryPKList,
    CoverStoryID,
    HighlightCropRect,
    InvalidComposite,
    InvalidIdentifier,
)


class HighlightUseCases:
    """Application orchestration for Instagram highlight operations.

    Owns precondition enforcement (account exists, authenticated),
    input validation (highlight_pk, user_id, title, story_ids, crop_rect),
    and URL sanity checks.
    The underlying ports handle vendor calls and DTO mapping.
    """

    def __init__(
        self,
        account_repo: AccountRepository,
        client_repo: ClientRepository,
        highlight_reader: InstagramHighlightReader,
        highlight_writer: InstagramHighlightWriter,
    ):
        self.account_repo = account_repo
        self.client_repo = client_repo
        self.highlight_reader = highlight_reader
        self.highlight_writer = highlight_writer

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
    # Validation helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_highlight_pk(highlight_pk: int) -> None:
        try:
            HighlightPK(highlight_pk)
        except InvalidIdentifier as e:
            raise ValueError(str(e)) from e

    @staticmethod
    def _validate_story_ids(story_ids: list[int], *, label: str = "story_ids") -> None:
        try:
            StoryPKList(story_ids, label=label)
        except InvalidComposite as e:
            raise ValueError(str(e)) from e
        except InvalidIdentifier as e:
            raise ValueError(f"all {label} must be positive integers, got {story_ids!r}") from e

    @staticmethod
    def _validate_crop_rect(crop_rect: list[float]) -> None:
        try:
            HighlightCropRect.from_list(crop_rect)
        except InvalidComposite as e:
            raise ValueError(str(e)) from e

    # -------------------------------------------------------------------------
    # Read operations
    # -------------------------------------------------------------------------

    def get_highlight_pk_from_url(self, url: str) -> int:
        """Resolve highlight PK from a highlight URL.

        Args:
            url: Instagram highlight URL (must start with 'http').

        Returns:
            Highlight primary key.

        Raises:
            ValueError: If url is empty or does not start with 'http'.
        """
        clean_url = url.strip() if url else ""
        if not clean_url:
            raise ValueError("url must not be empty")
        if not clean_url.startswith("http"):
            raise ValueError(f"url must start with 'http', got {url!r}")
        return self.highlight_reader.get_highlight_pk_from_url(clean_url)

    def get_highlight(
        self,
        account_id: str,
        highlight_pk: int,
    ) -> HighlightDetail:
        """Get highlight with full story details.

        Args:
            account_id: Application account ID.
            highlight_pk: Instagram highlight primary key (positive integer).

        Returns:
            HighlightDetail with story items.

        Raises:
            ValueError: If account not found, not authenticated, or highlight_pk invalid.
        """
        self._require_authenticated(account_id)
        self._validate_highlight_pk(highlight_pk)
        return self.highlight_reader.get_highlight(account_id, highlight_pk)

    def list_user_highlights(
        self,
        account_id: str,
        user_id: int,
        amount: int = 0,
    ) -> list[HighlightSummary]:
        """List highlights for a user.

        Args:
            account_id: Application account ID.
            user_id: Instagram user ID (positive integer).
            amount: Maximum highlights to retrieve (0 = all available).

        Returns:
            List of HighlightSummary.

        Raises:
            ValueError: If account not found, not authenticated, user_id invalid,
                        or amount is negative.
        """
        self._require_authenticated(account_id)
        try:
            HighlightPK(user_id)
        except InvalidIdentifier as e:
            raise ValueError(f"user_id must be a positive integer, got {user_id!r}") from e
        if not isinstance(amount, int) or amount < 0:
            raise ValueError(f"amount must be a non-negative integer, got {amount!r}")
        return self.highlight_reader.list_user_highlights(account_id, user_id, amount)

    # -------------------------------------------------------------------------
    # Write operations
    # -------------------------------------------------------------------------

    def create_highlight(
        self,
        account_id: str,
        title: str,
        story_ids: list[int],
        cover_story_id: int = 0,
        crop_rect: Optional[list[float]] = None,
    ) -> HighlightDetail:
        """Create a new highlight with stories.

        Args:
            account_id: Application account ID.
            title: Highlight title (must not be empty).
            story_ids: Story IDs to include (must not be empty, all positive integers).
            cover_story_id: Optional story ID for cover (0 = use default).
            crop_rect: Optional [x, y, width, height] normalized to [0.0, 1.0].

        Returns:
            HighlightDetail of created highlight.

        Raises:
            ValueError: If account not found, not authenticated, title empty,
                        story_ids invalid, cover_story_id negative, or crop_rect invalid.
        """
        self._require_authenticated(account_id)
        try:
            normalized_title = HighlightTitle(title)
        except InvalidComposite as e:
            raise ValueError(str(e)) from e
        self._validate_story_ids(story_ids)
        try:
            normalized_cover_story_id = CoverStoryID(cover_story_id)
        except InvalidIdentifier as e:
            raise ValueError(str(e)) from e
        normalized_crop_rect = None
        if crop_rect is not None:
            self._validate_crop_rect(crop_rect)
            normalized_crop_rect = HighlightCropRect.from_list(crop_rect).to_list()
        return self.highlight_writer.create_highlight(
            account_id,
            str(normalized_title),
            story_ids,
            int(normalized_cover_story_id),
            normalized_crop_rect,
        )

    def change_title(
        self,
        account_id: str,
        highlight_pk: int,
        title: str,
    ) -> HighlightDetail:
        """Change highlight title.

        Args:
            account_id: Application account ID.
            highlight_pk: Instagram highlight primary key (positive integer).
            title: New title (must not be empty).

        Returns:
            HighlightDetail with updated title.

        Raises:
            ValueError: If account not found, not authenticated, highlight_pk invalid,
                        or title empty.
        """
        self._require_authenticated(account_id)
        self._validate_highlight_pk(highlight_pk)
        try:
            normalized_title = HighlightTitle(title)
        except InvalidComposite as e:
            raise ValueError(str(e)) from e
        return self.highlight_writer.change_title(account_id, highlight_pk, str(normalized_title))

    def add_stories(
        self,
        account_id: str,
        highlight_pk: int,
        story_ids: list[int],
    ) -> HighlightDetail:
        """Add stories to an existing highlight.

        Args:
            account_id: Application account ID.
            highlight_pk: Instagram highlight primary key (positive integer).
            story_ids: Story IDs to add (must not be empty, all positive integers).

        Returns:
            HighlightDetail with updated story list.

        Raises:
            ValueError: If account not found, not authenticated, highlight_pk invalid,
                        or story_ids invalid.
        """
        self._require_authenticated(account_id)
        self._validate_highlight_pk(highlight_pk)
        self._validate_story_ids(story_ids)
        return self.highlight_writer.add_stories(account_id, highlight_pk, story_ids)

    def remove_stories(
        self,
        account_id: str,
        highlight_pk: int,
        story_ids: list[int],
    ) -> HighlightDetail:
        """Remove stories from a highlight.

        Args:
            account_id: Application account ID.
            highlight_pk: Instagram highlight primary key (positive integer).
            story_ids: Story IDs to remove (must not be empty, all positive integers).

        Returns:
            HighlightDetail with updated story list.

        Raises:
            ValueError: If account not found, not authenticated, highlight_pk invalid,
                        or story_ids invalid.
        """
        self._require_authenticated(account_id)
        self._validate_highlight_pk(highlight_pk)
        self._validate_story_ids(story_ids)
        return self.highlight_writer.remove_stories(account_id, highlight_pk, story_ids)

    def delete_highlight(
        self,
        account_id: str,
        highlight_pk: int,
    ) -> HighlightActionReceipt:
        """Delete a highlight.

        Args:
            account_id: Application account ID.
            highlight_pk: Instagram highlight primary key (positive integer).

        Returns:
            HighlightActionReceipt with result.

        Raises:
            ValueError: If account not found, not authenticated, or highlight_pk invalid.
        """
        self._require_authenticated(account_id)
        self._validate_highlight_pk(highlight_pk)
        return self.highlight_writer.delete_highlight(account_id, highlight_pk)
