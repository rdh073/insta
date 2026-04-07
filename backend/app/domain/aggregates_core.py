"""Domain aggregates for Instagram interaction entities (Phase 3).

Aggregates encapsulate domain entities and value objects, enforcing invariants
and defining clear boundaries. Each aggregate has a root entity responsible
for maintaining consistency.

Characteristics:
  - Root entity (e.g., Story, Comment, DirectThread)
  - Immutable where possible (frozen dataclass for value aggregates)
  - Explicit invariant checks at construction
  - No dependencies on framework, HTTP, or vendor details
  - Clear ownership of business rules
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.domain.interaction_values_core import (
    StoryPK,
    MediaKind,
    StoryAudience,
    UserID,
    MediaID,
    CommentID,
    OptionalReplyTarget,
    DirectThreadID,
    DirectMessageID,
    UserIDList,
    InvalidComposite,
    InvalidIdentifier,
)


# ============================================================================
# Story Aggregate
# ============================================================================

@dataclass
class StoryAggregate:
    """Story aggregate root with invariants.

    Owns:
      - Story identity (story_pk)
      - Media metadata (media_kind, audience)
      - Composition constraints

    Invariants:
      - story_pk must be positive
      - media_kind must be in {photo, video}
      - audience must be in {default, close_friends}
      - If media_kind is video, thumbnail_path is required
    """
    story_pk: StoryPK
    media_kind: MediaKind
    audience: StoryAudience
    owner_user_id: Optional[UserID] = None  # Read model: who owns this story
    thumbnail_path: Optional[str] = None  # Required for video

    def __post_init__(self):
        """Validate aggregate invariants."""
        if self.media_kind == MediaKind.VIDEO and not self.thumbnail_path:
            raise InvalidComposite(
                "StoryAggregate: video stories require thumbnail_path"
            )

    def can_be_seen_by(self, viewer_user_id: int) -> bool:
        """Check if viewer can see this story based on audience.

        Rules:
          - 'default': visible to all followers
          - 'close_friends': visible to close friends only (requires relationship check)

        Note: This method requires adapter-layer relationship data (not implemented in pure domain).
        In practice, this check happens in adapter layer with relationship context.
        """
        if self.audience == StoryAudience.DEFAULT:
            return True
        # 'close_friends' requires relationship check (handled by adapter)
        return False  # Conservative: require explicit approval in adapter

    def __str__(self) -> str:
        return f"Story(pk={self.story_pk}, kind={self.media_kind.value}, audience={self.audience.value})"


# ============================================================================
# Comment Aggregate
# ============================================================================

@dataclass
class CommentAggregate:
    """Comment aggregate root with invariants.

    Owns:
      - Comment identity (comment_id)
      - Comment text and metadata
      - Reply flow (reply_to_comment_id determines top-level vs reply)

    Invariants:
      - comment_id must be positive
      - text must not be empty
      - media_id must not be empty
      - reply_to_comment_id: if present, must be positive (reply flow)
    """
    comment_id: CommentID
    media_id: MediaID
    text: str  # Already validated at use case layer
    reply_to_comment_id: OptionalReplyTarget = field(default_factory=lambda: OptionalReplyTarget(None))

    def __post_init__(self):
        """Validate aggregate invariants."""
        if not self.text or not self.text.strip():
            raise InvalidComposite("CommentAggregate: text must not be empty")

    def is_reply(self) -> bool:
        """Check if this comment is a reply (not top-level)."""
        return self.reply_to_comment_id.is_reply()

    def is_top_level(self) -> bool:
        """Check if this comment is top-level (not a reply)."""
        return not self.is_reply()

    def __str__(self) -> str:
        level = "reply" if self.is_reply() else "top-level"
        return f"Comment(id={self.comment_id}, level={level}, media={self.media_id})"


# ============================================================================
# DirectThread Aggregate
# ============================================================================

@dataclass
class DirectThreadAggregate:
    """Direct message thread aggregate root with invariants.

    Owns:
      - Thread identity (direct_thread_id)
      - Participant list (user_ids)
      - Message flow state

    Invariants:
      - direct_thread_id must not be empty
      - participant_user_ids must not be empty and all positive
      - thread represents 1:1 or group conversation
    """
    direct_thread_id: DirectThreadID
    participant_user_ids: UserIDList  # Non-empty list of positive integers

    def __post_init__(self):
        """Validate aggregate invariants."""
        if not self.direct_thread_id.value:
            raise InvalidComposite(
                "DirectThreadAggregate: direct_thread_id must not be empty"
            )
        # UserIDList already validates non-empty and positive in __init__

    def is_one_to_one(self) -> bool:
        """Check if this is a 1:1 conversation."""
        return len(self.participant_user_ids) == 2

    def is_group(self) -> bool:
        """Check if this is a group conversation."""
        return len(self.participant_user_ids) > 2

    def participant_count(self) -> int:
        """Return number of participants in thread."""
        return len(self.participant_user_ids)

    def __str__(self) -> str:
        conv_type = "1:1" if self.is_one_to_one() else "group"
        return f"DirectThread(id={self.direct_thread_id}, type={conv_type}, participants={self.participant_count()})"


# ============================================================================
# DirectMessage Aggregate
# ============================================================================

@dataclass
class DirectMessageAggregate:
    """Direct message aggregate root.

    Owns:
      - Message identity (direct_message_id)
      - Thread location (direct_thread_id)
      - Message text

    Invariants:
      - direct_message_id must not be empty
      - direct_thread_id must not be empty
      - text must not be empty
    """
    direct_message_id: DirectMessageID
    direct_thread_id: DirectThreadID
    text: str  # Already validated at use case layer

    def __post_init__(self):
        """Validate aggregate invariants."""
        if not self.text or not self.text.strip():
            raise InvalidComposite("DirectMessageAggregate: text must not be empty")

    def __str__(self) -> str:
        return f"DirectMessage(id={self.direct_message_id}, thread={self.direct_thread_id})"


# ============================================================================
# Highlight Aggregate (Skeleton - Deferred Full Implementation)
# ============================================================================

@dataclass
class HighlightAggregate:
    """Highlight aggregate root (skeleton).

    Owns:
      - Highlight identity
      - Story membership
      - Metadata (title, etc.)

    Invariants:
      - highlight_id must not be empty
      - story_ids list must not be empty
      - title must not be empty

    Note: Full implementation deferred pending code review of highlight use case.
    """
    highlight_id: str  # Would become HighlightID value object in full implementation
    story_ids: list[StoryPK]  # Collection of story references
    title: str

    def __post_init__(self):
        """Validate aggregate invariants."""
        if not self.highlight_id or not self.highlight_id.strip():
            raise InvalidComposite("HighlightAggregate: highlight_id must not be empty")
        if not self.story_ids:
            raise InvalidComposite("HighlightAggregate: story_ids must not be empty")
        if not self.title or not self.title.strip():
            raise InvalidComposite("HighlightAggregate: title must not be empty")

    def story_count(self) -> int:
        """Return number of stories in highlight."""
        return len(self.story_ids)

    def __str__(self) -> str:
        return f"Highlight(id={self.highlight_id}, stories={self.story_count()}, title={self.title!r})"
