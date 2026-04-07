"""Tests for domain value objects (Phase 1 - Seed Value Objects).

Validates that:
  - Value objects enforce invariants at construction
  - Validation errors are app-owned (not framework-specific)
  - Normalization (strip, etc.) works as expected
  - Immutability is preserved (frozen dataclass)
"""

from __future__ import annotations

import pytest

from app.domain.instagram_interaction_values import (
    # Exceptions
    DomainValidationError,
    InvalidIdentifier,
    InvalidEnumValue,
    InvalidComposite,
    # Numeric IDs
    StoryPK,
    UserID,
    CommentID,
    # String IDs
    MediaID,
    DirectThreadID,
    DirectMessageID,
    # Enums
    MediaKind,
    StoryAudience,
    # Bounded integers
    QueryAmount,
    PageSize,
    ThreadMessageLimit,
    # Composite
    UserIDList,
    # String validation
    StoryURL,
    CommentText,
    SearchQuery,
    OptionalReplyTarget,
)


class TestNumericIdentifiers:
    """Test positive integer ID value objects."""

    def test_story_pk_valid(self):
        pk = StoryPK(12345)
        assert pk.value == 12345
        assert int(pk) == 12345

    def test_story_pk_zero_rejected(self):
        with pytest.raises(InvalidIdentifier, match="positive integer"):
            StoryPK(0)

    def test_story_pk_negative_rejected(self):
        with pytest.raises(InvalidIdentifier, match="positive integer"):
            StoryPK(-1)

    def test_story_pk_non_integer_rejected(self):
        with pytest.raises(InvalidIdentifier, match="positive integer"):
            StoryPK("12345")  # type: ignore

    def test_user_id_valid(self):
        uid = UserID(54321)
        assert uid.value == 54321
        assert int(uid) == 54321

    def test_user_id_zero_rejected(self):
        with pytest.raises(InvalidIdentifier):
            UserID(0)

    def test_comment_id_valid(self):
        cid = CommentID(999)
        assert cid.value == 999
        assert int(cid) == 999

    def test_comment_id_negative_rejected(self):
        with pytest.raises(InvalidIdentifier):
            CommentID(-1)


class TestStringIdentifiers:
    """Test non-empty string ID value objects with normalization."""

    def test_media_id_valid(self):
        mid = MediaID("some_media_id")
        assert mid.value == "some_media_id"

    def test_media_id_strips_whitespace(self):
        mid = MediaID("  some_media_id  ")
        assert mid.value == "some_media_id"

    def test_media_id_empty_rejected(self):
        with pytest.raises(InvalidIdentifier, match="must not be empty"):
            MediaID("")

    def test_media_id_whitespace_only_rejected(self):
        with pytest.raises(InvalidIdentifier, match="must not be empty"):
            MediaID("   ")

    def test_direct_thread_id_valid(self):
        tid = DirectThreadID("thread_123")
        assert tid.value == "thread_123"

    def test_direct_thread_id_strips(self):
        tid = DirectThreadID("  thread_123  ")
        assert tid.value == "thread_123"

    def test_direct_thread_id_empty_rejected(self):
        with pytest.raises(InvalidIdentifier):
            DirectThreadID("")

    def test_direct_message_id_valid(self):
        mid = DirectMessageID("msg_456")
        assert mid.value == "msg_456"

    def test_direct_message_id_empty_rejected(self):
        with pytest.raises(InvalidIdentifier):
            DirectMessageID("   ")


class TestEnumerations:
    """Test enumeration value objects."""

    def test_media_kind_photo_valid(self):
        mk = MediaKind.validate("photo")
        assert mk == MediaKind.PHOTO

    def test_media_kind_video_valid(self):
        mk = MediaKind.validate("video")
        assert mk == MediaKind.VIDEO

    def test_media_kind_invalid_rejected(self):
        with pytest.raises(InvalidEnumValue, match="must be one of"):
            MediaKind.validate("invalid")

    def test_story_audience_default_valid(self):
        aud = StoryAudience.validate("default")
        assert aud == StoryAudience.DEFAULT

    def test_story_audience_close_friends_valid(self):
        aud = StoryAudience.validate("close_friends")
        assert aud == StoryAudience.CLOSE_FRIENDS

    def test_story_audience_invalid_rejected(self):
        with pytest.raises(InvalidEnumValue):
            StoryAudience.validate("everyone")


class TestBoundedIntegers:
    """Test bounded integer value objects."""

    def test_query_amount_zero(self):
        qa = QueryAmount(0)
        assert qa.value == 0

    def test_query_amount_positive(self):
        qa = QueryAmount(100)
        assert qa.value == 100

    def test_query_amount_negative_rejected(self):
        with pytest.raises(InvalidIdentifier, match="non-negative"):
            QueryAmount(-1)

    def test_page_size_one(self):
        ps = PageSize(1)
        assert ps.value == 1

    def test_page_size_large(self):
        ps = PageSize(100)
        assert ps.value == 100

    def test_page_size_zero_rejected(self):
        with pytest.raises(InvalidIdentifier, match="positive integer"):
            PageSize(0)

    def test_page_size_negative_rejected(self):
        with pytest.raises(InvalidIdentifier):
            PageSize(-10)

    def test_thread_message_limit_valid(self):
        tml = ThreadMessageLimit(10)
        assert tml.value == 10

    def test_thread_message_limit_zero_rejected(self):
        with pytest.raises(InvalidIdentifier):
            ThreadMessageLimit(0)


class TestUserIDList:
    """Test composite UserIDList value object."""

    def test_user_id_list_valid(self):
        uidlist = UserIDList([1, 2, 3])
        assert len(uidlist) == 3
        assert uidlist[0] == 1
        assert uidlist[1] == 2
        assert list(uidlist) == [1, 2, 3]

    def test_user_id_list_from_tuple(self):
        uidlist = UserIDList((10, 20))
        assert len(uidlist) == 2
        assert uidlist[0] == 10

    def test_user_id_list_empty_rejected(self):
        with pytest.raises(InvalidComposite, match="must not be empty"):
            UserIDList([])

    def test_user_id_list_zero_rejected(self):
        with pytest.raises(InvalidComposite, match="positive integers"):
            UserIDList([1, 0, 3])

    def test_user_id_list_negative_rejected(self):
        with pytest.raises(InvalidComposite, match="positive integers"):
            UserIDList([1, -2, 3])

    def test_user_id_list_non_integer_rejected(self):
        with pytest.raises(InvalidComposite, match="positive integers"):
            UserIDList([1, "2", 3])  # type: ignore


class TestStringValidation:
    """Test string validation value objects."""

    def test_story_url_valid_http(self):
        url = StoryURL("https://instagram.com/stories/123")
        assert url.value == "https://instagram.com/stories/123"

    def test_story_url_valid_http_no_s(self):
        url = StoryURL("http://instagram.com/stories/123")
        assert url.value == "http://instagram.com/stories/123"

    def test_story_url_strips_whitespace(self):
        url = StoryURL("  https://instagram.com/stories/123  ")
        assert url.value == "https://instagram.com/stories/123"

    def test_story_url_non_http_rejected(self):
        with pytest.raises(InvalidComposite, match="must start with"):
            StoryURL("ftp://example.com")

    def test_story_url_empty_rejected(self):
        with pytest.raises(InvalidComposite, match="must not be empty"):
            StoryURL("")

    def test_comment_text_valid(self):
        text = CommentText("Great photo!")
        assert text.value == "Great photo!"

    def test_comment_text_strips(self):
        text = CommentText("  Great photo!  ")
        assert text.value == "Great photo!"

    def test_comment_text_empty_rejected(self):
        with pytest.raises(InvalidComposite, match="must not be empty"):
            CommentText("")

    def test_comment_text_whitespace_only_rejected(self):
        with pytest.raises(InvalidComposite):
            CommentText("    ")

    def test_search_query_valid(self):
        query = SearchQuery("love")
        assert query.value == "love"

    def test_search_query_empty_rejected(self):
        with pytest.raises(InvalidComposite):
            SearchQuery("")


class TestOptionalReplyTarget:
    """Test optional reply target value object."""

    def test_reply_target_none(self):
        ort = OptionalReplyTarget(None)
        assert ort.value is None
        assert not ort.is_reply()

    def test_reply_target_positive_integer(self):
        ort = OptionalReplyTarget(999)
        assert ort.value == 999
        assert ort.is_reply()

    def test_reply_target_zero_rejected(self):
        with pytest.raises(InvalidIdentifier, match="positive integer"):
            OptionalReplyTarget(0)

    def test_reply_target_negative_rejected(self):
        with pytest.raises(InvalidIdentifier):
            OptionalReplyTarget(-1)


class TestImmutability:
    """Test that value objects are immutable (frozen)."""

    def test_story_pk_frozen(self):
        pk = StoryPK(123)
        with pytest.raises(AttributeError):
            pk.value = 456  # type: ignore

    def test_media_id_frozen(self):
        mid = MediaID("test")
        with pytest.raises(AttributeError):
            mid.value = "other"  # type: ignore

    def test_query_amount_frozen(self):
        qa = QueryAmount(10)
        with pytest.raises(AttributeError):
            qa.value = 20  # type: ignore


class TestStringConversions:
    """Test __str__ methods for value objects."""

    def test_story_pk_str(self):
        assert str(StoryPK(123)) == "123"

    def test_media_id_str(self):
        assert str(MediaID("test_id")) == "test_id"

    def test_query_amount_str(self):
        assert str(QueryAmount(50)) == "50"

    def test_optional_reply_none_str(self):
        assert str(OptionalReplyTarget(None)) == "(none)"

    def test_optional_reply_str(self):
        assert str(OptionalReplyTarget(999)) == "999"
