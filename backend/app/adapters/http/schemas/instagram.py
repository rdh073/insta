"""Instagram vertical transport schemas (Phase 0 foundation)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class InstagramWriteEnvelope(BaseModel):
    """Base envelope for write operations in Instagram vertical routes."""

    account_id: str = Field(..., description="Application account ID")
    dry_run: bool = Field(default=False, description="Execute validation only")
    request_id: Optional[str] = Field(
        default=None,
        description="Optional client-generated request id for idempotency/audit",
    )


class StoryPublishEnvelope(InstagramWriteEnvelope):
    """Write envelope contract for future story publish endpoint."""

    media_kind: str = Field(..., description="photo|video")
    media_path: str = Field(..., description="Absolute or resolved media path")
    caption: str = Field(default="", description="Story caption")
    thumbnail_path: Optional[str] = Field(
        default=None,
        description="Thumbnail path (required for video)",
    )
    audience: str = Field(
        default="default",
        description="default|close_friends",
    )


class StoryDeleteEnvelope(InstagramWriteEnvelope):
    """Write envelope contract for story delete endpoint."""

    story_pk: int = Field(..., description="Instagram story PK")


class StoryMarkSeenEnvelope(InstagramWriteEnvelope):
    """Write envelope contract for story mark_seen endpoint."""

    story_pks: list[int] = Field(..., description="Story PKs to mark as seen")
    skipped_story_pks: Optional[list[int]] = Field(
        default=None,
        description="Optional story PKs considered skipped",
    )


class HighlightCreateEnvelope(InstagramWriteEnvelope):
    """Write envelope contract for highlight create endpoint."""

    title: str = Field(..., description="Highlight title")
    story_ids: list[int] = Field(..., description="Story IDs to include")
    cover_story_id: int = Field(default=0, description="Cover story ID (0 = default)")
    crop_rect: Optional[list[float]] = Field(
        default=None,
        description="Optional crop rect [x,y,width,height] in [0,1]",
    )


class HighlightChangeTitleEnvelope(InstagramWriteEnvelope):
    """Write envelope contract for highlight change_title endpoint."""

    highlight_pk: int = Field(..., description="Instagram highlight PK")
    title: str = Field(..., description="New title")


class HighlightStoriesEnvelope(InstagramWriteEnvelope):
    """Write envelope contract for add/remove highlight stories endpoint."""

    highlight_pk: int = Field(..., description="Instagram highlight PK")
    story_ids: list[int] = Field(..., description="Story IDs to add/remove")


class HighlightDeleteEnvelope(InstagramWriteEnvelope):
    """Write envelope contract for highlight delete endpoint."""

    highlight_pk: int = Field(..., description="Instagram highlight PK")


class CommentCreateEnvelope(InstagramWriteEnvelope):
    """Write envelope contract for future comment create endpoint."""

    media_id: str = Field(..., description="Instagram media id")
    text: str = Field(..., description="Comment text")
    reply_to_comment_id: Optional[int] = Field(
        default=None,
        description="Optional reply target comment id",
    )


class CommentDeleteEnvelope(InstagramWriteEnvelope):
    """Write envelope contract for comment delete endpoint."""

    media_id: str = Field(..., description="Instagram media id")
    comment_id: int = Field(..., description="Instagram comment id")


class CommentLikeEnvelope(InstagramWriteEnvelope):
    """Write envelope for liking or unliking a comment."""

    comment_id: int = Field(..., description="Instagram comment id")


class CommentPinEnvelope(InstagramWriteEnvelope):
    """Write envelope for pinning or unpinning a comment."""

    media_id: str = Field(..., description="Instagram media id (must be owned by account)")
    comment_id: int = Field(..., description="Instagram comment id")


class DirectSendEnvelope(InstagramWriteEnvelope):
    """Write envelope contract for future direct message endpoint."""

    username: str = Field(..., description="Target username")
    text: str = Field(..., description="Message text")


class DirectFindOrCreateEnvelope(InstagramWriteEnvelope):
    """Write envelope contract for direct thread creation/find endpoint."""

    participant_user_ids: list[int] = Field(
        ...,
        description="Participant user IDs",
    )


class DirectSendThreadEnvelope(InstagramWriteEnvelope):
    """Write envelope contract for direct send-to-thread endpoint."""

    direct_thread_id: str = Field(..., description="Direct thread ID")
    text: str = Field(..., description="Message text")


class DirectSendUsersEnvelope(InstagramWriteEnvelope):
    """Write envelope contract for direct send-to-users endpoint."""

    user_ids: list[int] = Field(..., description="Recipient user IDs")
    text: str = Field(..., description="Message text")


class DirectDeleteMessageEnvelope(InstagramWriteEnvelope):
    """Write envelope contract for direct delete message endpoint."""

    direct_thread_id: str = Field(..., description="Direct thread ID")
    direct_message_id: str = Field(..., description="Direct message ID")
