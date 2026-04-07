"""Tests for domain aggregates and services (Phase 3).

Validates:
  - Aggregate invariants are enforced
  - Domain services correctly apply cross-aggregate rules
  - No framework dependencies
  - Immutability where expected
"""

from __future__ import annotations

import pytest

from app.domain.instagram_aggregates import (
    StoryAggregate,
    CommentAggregate,
    DirectThreadAggregate,
    DirectMessageAggregate,
    HighlightAggregate,
)
from app.domain.instagram_services import (
    StoryAudienceService,
    CommentThreadService,
    DirectThreadService,
)
from app.domain.instagram_interaction_values import (
    StoryPK,
    UserID,
    MediaID,
    CommentID,
    DirectThreadID,
    DirectMessageID,
    UserIDList,
    MediaKind,
    StoryAudience,
    OptionalReplyTarget,
    InvalidIdentifier,
    InvalidComposite,
)


class TestStoryAggregate:
    """Test Story aggregate root and invariants."""

    def test_story_aggregate_valid_photo(self):
        """Create valid photo story."""
        story = StoryAggregate(
            story_pk=StoryPK(12345),
            media_kind=MediaKind.PHOTO,
            audience=StoryAudience.DEFAULT,
            owner_user_id=UserID(999),
        )
        assert story.story_pk.value == 12345
        assert story.media_kind == MediaKind.PHOTO
        assert story.audience == StoryAudience.DEFAULT

    def test_story_aggregate_valid_video_with_thumbnail(self):
        """Create valid video story with required thumbnail."""
        story = StoryAggregate(
            story_pk=StoryPK(67890),
            media_kind=MediaKind.VIDEO,
            audience=StoryAudience.CLOSE_FRIENDS,
            owner_user_id=UserID(555),
            thumbnail_path="/path/to/thumb.jpg",
        )
        assert story.media_kind == MediaKind.VIDEO
        assert story.thumbnail_path == "/path/to/thumb.jpg"

    def test_story_aggregate_video_without_thumbnail_rejected(self):
        """Video story without thumbnail must be rejected."""
        with pytest.raises(InvalidComposite, match="thumbnail_path"):
            StoryAggregate(
                story_pk=StoryPK(67890),
                media_kind=MediaKind.VIDEO,
                audience=StoryAudience.DEFAULT,
                owner_user_id=UserID(555),
                thumbnail_path=None,
            )

    def test_story_is_one_to_one(self):
        """Check 1:1 property."""
        story = StoryAggregate(
            story_pk=StoryPK(1),
            media_kind=MediaKind.PHOTO,
            audience=StoryAudience.DEFAULT,
        )
        assert str(story) == "Story(pk=1, kind=photo, audience=default)"

    def test_story_can_be_seen_by_default_audience(self):
        """Default audience stories visible to all."""
        story = StoryAggregate(
            story_pk=StoryPK(1),
            media_kind=MediaKind.PHOTO,
            audience=StoryAudience.DEFAULT,
            owner_user_id=UserID(100),
        )
        assert story.can_be_seen_by(200) is True  # Viewer is not owner

    def test_story_can_be_seen_by_close_friends_audience(self):
        """Close friends audience requires explicit approval."""
        story = StoryAggregate(
            story_pk=StoryPK(1),
            media_kind=MediaKind.PHOTO,
            audience=StoryAudience.CLOSE_FRIENDS,
            owner_user_id=UserID(100),
        )
        # Conservative: story returns False, service checks adapter context
        assert story.can_be_seen_by(200) is False


class TestCommentAggregate:
    """Test Comment aggregate root and invariants."""

    def test_comment_aggregate_top_level(self):
        """Create valid top-level comment."""
        comment = CommentAggregate(
            comment_id=CommentID(111),
            media_id=MediaID("media_123"),
            text="Great post!",
        )
        assert comment.comment_id.value == 111
        assert comment.is_top_level() is True
        assert comment.is_reply() is False

    def test_comment_aggregate_reply(self):
        """Create valid reply comment."""
        comment = CommentAggregate(
            comment_id=CommentID(222),
            media_id=MediaID("media_123"),
            text="Thanks!",
            reply_to_comment_id=OptionalReplyTarget(111),
        )
        assert comment.comment_id.value == 222
        assert comment.is_reply() is True
        assert comment.is_top_level() is False

    def test_comment_empty_text_rejected(self):
        """Empty comment text must be rejected."""
        with pytest.raises(InvalidComposite, match="text must not be empty"):
            CommentAggregate(
                comment_id=CommentID(333),
                media_id=MediaID("media_456"),
                text="",
            )

    def test_comment_whitespace_only_text_rejected(self):
        """Whitespace-only text must be rejected."""
        with pytest.raises(InvalidComposite):
            CommentAggregate(
                comment_id=CommentID(333),
                media_id=MediaID("media_456"),
                text="   ",
            )


class TestDirectThreadAggregate:
    """Test DirectThread aggregate root and invariants."""

    def test_thread_aggregate_one_to_one(self):
        """Create valid 1:1 thread."""
        thread = DirectThreadAggregate(
            direct_thread_id=DirectThreadID("thread_abc123"),
            participant_user_ids=UserIDList([100, 200]),
        )
        assert thread.is_one_to_one() is True
        assert thread.is_group() is False
        assert thread.participant_count() == 2

    def test_thread_aggregate_group(self):
        """Create valid group thread."""
        thread = DirectThreadAggregate(
            direct_thread_id=DirectThreadID("thread_xyz789"),
            participant_user_ids=UserIDList([100, 200, 300]),
        )
        assert thread.is_group() is True
        assert thread.is_one_to_one() is False
        assert thread.participant_count() == 3

    def test_thread_empty_id_rejected(self):
        """Empty thread ID must be rejected."""
        with pytest.raises(InvalidIdentifier, match="DirectThreadID"):
            DirectThreadID("")  # Raises InvalidIdentifier at value object construction

    def test_thread_string_representation(self):
        """Thread string representation shows type and participant count."""
        thread = DirectThreadAggregate(
            direct_thread_id=DirectThreadID("thread_1"),
            participant_user_ids=UserIDList([100, 200]),
        )
        assert "1:1" in str(thread)
        assert "participants=2" in str(thread)


class TestDirectMessageAggregate:
    """Test DirectMessage aggregate root and invariants."""

    def test_message_aggregate_valid(self):
        """Create valid direct message."""
        msg = DirectMessageAggregate(
            direct_message_id=DirectMessageID("msg_001"),
            direct_thread_id=DirectThreadID("thread_abc"),
            text="Hello!",
        )
        assert msg.direct_message_id.value == "msg_001"
        assert msg.direct_thread_id.value == "thread_abc"
        assert msg.text == "Hello!"

    def test_message_empty_text_rejected(self):
        """Empty message text must be rejected."""
        with pytest.raises(InvalidComposite, match="text must not be empty"):
            DirectMessageAggregate(
                direct_message_id=DirectMessageID("msg_002"),
                direct_thread_id=DirectThreadID("thread_def"),
                text="",
            )


class TestHighlightAggregate:
    """Test Highlight aggregate root and invariants."""

    def test_highlight_aggregate_valid(self):
        """Create valid highlight with stories."""
        highlight = HighlightAggregate(
            highlight_id="hl_001",
            story_ids=[StoryPK(1), StoryPK(2), StoryPK(3)],
            title="Vacation 2024",
        )
        assert highlight.highlight_id == "hl_001"
        assert highlight.story_count() == 3
        assert "Vacation 2024" in str(highlight)

    def test_highlight_empty_stories_rejected(self):
        """Highlight without stories must be rejected."""
        with pytest.raises(InvalidComposite, match="story_ids"):
            HighlightAggregate(
                highlight_id="hl_002",
                story_ids=[],
                title="Empty",
            )

    def test_highlight_empty_title_rejected(self):
        """Highlight without title must be rejected."""
        with pytest.raises(InvalidComposite, match="title"):
            HighlightAggregate(
                highlight_id="hl_003",
                story_ids=[StoryPK(1)],
                title="",
            )


class TestStoryAudienceService:
    """Test Story audience service rules."""

    def test_audience_consistency_default(self):
        """Default audience does not require owner_user_id."""
        story = StoryAggregate(
            story_pk=StoryPK(1),
            media_kind=MediaKind.PHOTO,
            audience=StoryAudience.DEFAULT,
            owner_user_id=None,
        )
        # Should not raise
        StoryAudienceService.validate_audience_consistency(story)

    def test_audience_consistency_close_friends_requires_owner(self):
        """Close friends audience requires owner_user_id."""
        story = StoryAggregate(
            story_pk=StoryPK(1),
            media_kind=MediaKind.PHOTO,
            audience=StoryAudience.CLOSE_FRIENDS,
            owner_user_id=None,
        )
        with pytest.raises(InvalidComposite, match="owner_user_id"):
            StoryAudienceService.validate_audience_consistency(story)

    def test_can_view_story_default_audience(self):
        """Any user can view default audience story."""
        story = StoryAggregate(
            story_pk=StoryPK(1),
            media_kind=MediaKind.PHOTO,
            audience=StoryAudience.DEFAULT,
            owner_user_id=UserID(100),
        )
        assert StoryAudienceService.can_view_story(story, 200) is True

    def test_can_view_story_owner_always_can(self):
        """Story owner can always view their own story."""
        story = StoryAggregate(
            story_pk=StoryPK(1),
            media_kind=MediaKind.PHOTO,
            audience=StoryAudience.CLOSE_FRIENDS,
            owner_user_id=UserID(100),
        )
        assert StoryAudienceService.can_view_story(story, 100) is True

    def test_can_view_story_close_friends(self):
        """Only close friends can view close_friends audience."""
        story = StoryAggregate(
            story_pk=StoryPK(1),
            media_kind=MediaKind.PHOTO,
            audience=StoryAudience.CLOSE_FRIENDS,
            owner_user_id=UserID(100),
        )
        # Non-close-friend
        assert StoryAudienceService.can_view_story(story, 200, is_close_friend=False) is False
        # Close friend
        assert StoryAudienceService.can_view_story(story, 200, is_close_friend=True) is True


class TestCommentThreadService:
    """Test Comment thread service rules."""

    def test_reply_chain_valid(self):
        """Valid reply chain should not raise."""
        parent = CommentAggregate(
            comment_id=CommentID(111),
            media_id=MediaID("media_123"),
            text="Original comment",
        )
        reply = CommentAggregate(
            comment_id=CommentID(222),
            media_id=MediaID("media_123"),
            text="Reply to original",
            reply_to_comment_id=OptionalReplyTarget(111),
        )
        # Should not raise
        CommentThreadService.validate_reply_chain(reply, parent)

    def test_reply_chain_missing_parent_rejected(self):
        """Reply without parent must be rejected."""
        reply = CommentAggregate(
            comment_id=CommentID(222),
            media_id=MediaID("media_123"),
            text="Reply",
            reply_to_comment_id=OptionalReplyTarget(111),
        )
        with pytest.raises(InvalidComposite, match="parent comment not found"):
            CommentThreadService.validate_reply_chain(reply, parent=None)

    def test_reply_chain_different_media_rejected(self):
        """Reply to comment in different media must be rejected."""
        parent = CommentAggregate(
            comment_id=CommentID(111),
            media_id=MediaID("media_123"),
            text="Original",
        )
        reply = CommentAggregate(
            comment_id=CommentID(222),
            media_id=MediaID("media_456"),  # Different media!
            text="Reply",
            reply_to_comment_id=OptionalReplyTarget(111),
        )
        with pytest.raises(InvalidComposite, match="same media"):
            CommentThreadService.validate_reply_chain(reply, parent)

    def test_can_delete_comment_owner_only(self):
        """Only comment owner can delete."""
        comment = CommentAggregate(
            comment_id=CommentID(111),
            media_id=MediaID("media_123"),
            text="My comment",
        )
        # Owner can delete
        assert CommentThreadService.can_delete_comment(comment, 100, 100) is True
        # Non-owner cannot delete
        assert CommentThreadService.can_delete_comment(comment, 200, 100) is False


class TestDirectThreadService:
    """Test DirectThread service rules."""

    def test_message_in_thread_valid(self):
        """Message in correct thread should not raise."""
        thread = DirectThreadAggregate(
            direct_thread_id=DirectThreadID("thread_abc"),
            participant_user_ids=UserIDList([100, 200]),
        )
        message = DirectMessageAggregate(
            direct_message_id=DirectMessageID("msg_001"),
            direct_thread_id=DirectThreadID("thread_abc"),
            text="Hello",
        )
        # Should not raise
        DirectThreadService.validate_message_in_thread(message, thread)

    def test_message_in_wrong_thread_rejected(self):
        """Message in wrong thread must be rejected."""
        thread = DirectThreadAggregate(
            direct_thread_id=DirectThreadID("thread_abc"),
            participant_user_ids=UserIDList([100, 200]),
        )
        message = DirectMessageAggregate(
            direct_message_id=DirectMessageID("msg_001"),
            direct_thread_id=DirectThreadID("thread_xyz"),  # Different thread!
            text="Hello",
        )
        with pytest.raises(InvalidComposite, match="does not match"):
            DirectThreadService.validate_message_in_thread(message, thread)

    def test_can_send_message_participant_only(self):
        """Only participants can send messages."""
        thread = DirectThreadAggregate(
            direct_thread_id=DirectThreadID("thread_1"),
            participant_user_ids=UserIDList([100, 200]),
        )
        # Participant can send
        assert DirectThreadService.can_send_message(thread, 100) is True
        # Non-participant cannot send
        assert DirectThreadService.can_send_message(thread, 999) is False

    def test_can_read_thread_participant_only(self):
        """Only participants can read thread."""
        thread = DirectThreadAggregate(
            direct_thread_id=DirectThreadID("thread_1"),
            participant_user_ids=UserIDList([100, 200]),
        )
        # Participant can read
        assert DirectThreadService.can_read_thread(thread, 100) is True
        # Non-participant cannot read
        assert DirectThreadService.can_read_thread(thread, 999) is False

    def test_can_delete_message_sender_only(self):
        """Only sender can delete message."""
        message = DirectMessageAggregate(
            direct_message_id=DirectMessageID("msg_1"),
            direct_thread_id=DirectThreadID("thread_1"),
            text="Hello",
        )
        # Sender can delete
        assert DirectThreadService.can_delete_message(message, 100, 100) is True
        # Non-sender cannot delete
        assert DirectThreadService.can_delete_message(message, 200, 100) is False
