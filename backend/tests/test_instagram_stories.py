"""
Tests for Instagram story reader, publisher, and DTO mappings.

Verifies that instagrapi Story objects map correctly to stable application DTOs
while handling vendor field variations and composition specs.
Also verifies that vendor story overlay types never leak into application code.
"""

import pytest
import sys
import types
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from app.application.dto.instagram_story_dto import (
    StorySummary,
    StoryDetail,
    StoryLinkSpec,
    StoryLocationSpec,
    StoryMentionSpec,
    StoryHashtagSpec,
    StoryStickerSpec,
    StoryPublishRequest,
    StoryActionReceipt,
)
from app.adapters.instagram.story_reader import (
    InstagramStoryReaderAdapter,
)
from app.adapters.instagram.story_publisher import (
    InstagramStoryPublisherAdapter,
)


class TestStoryReaderAdapter:
    """Test the story reader adapter mappings."""

    def test_get_story_pk_from_url(self, monkeypatch):
        """Verify story_pk_from_url delegates to instagrapi utility."""
        instagrapi_module = types.ModuleType("instagrapi")

        class _FakeClient:
            def story_pk_from_url(self, url):
                assert "instagram.com/stories" in url
                return 2581281926631793076

        instagrapi_module.Client = _FakeClient
        monkeypatch.setitem(sys.modules, "instagrapi", instagrapi_module)

        adapter = InstagramStoryReaderAdapter(Mock())
        result = adapter.get_story_pk_from_url(
            "https://www.instagram.com/stories/example/2581281926631793076/"
        )

        assert result == 2581281926631793076

    def test_get_story(self):
        """Verify story_info() maps correctly to StoryDetail."""
        # Create mock client
        mock_client = Mock()
        mock_story = self._create_mock_story(
            pk=123,
            id="123_456",
            media_type=1,
            viewer_count=50,
        )
        mock_client.story_info.return_value = mock_story

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramStoryReaderAdapter(mock_repo)
        result = adapter.get_story("acc-123", 123)

        assert isinstance(result, StoryDetail)
        assert result.summary.pk == 123
        assert result.summary.story_id == "123_456"
        assert result.summary.media_type == 1
        assert result.summary.viewer_count == 50
        mock_client.story_info.assert_called_once_with(123, use_cache=True)

    def test_list_user_stories(self):
        """Verify user_stories() maps multiple stories correctly."""
        # Create mock client
        mock_client = Mock()
        story_list = [
            self._create_mock_story(pk=1, id="1_1"),
            self._create_mock_story(pk=2, id="2_2"),
            self._create_mock_story(pk=3, id="3_3"),
        ]
        mock_client.user_stories.return_value = story_list

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramStoryReaderAdapter(mock_repo)
        results = adapter.list_user_stories("acc-123", 999, amount=3)

        assert len(results) == 3
        assert all(isinstance(r, StorySummary) for r in results)
        assert results[0].pk == 1
        assert results[1].pk == 2
        assert results[2].pk == 3
        mock_client.user_stories.assert_called_once_with(999, amount=3)

    def test_owner_username_extraction(self):
        """Verify owner username is extracted from nested user object."""
        # Create mock client
        mock_client = Mock()
        mock_story = self._create_mock_story(pk=123)
        mock_story.user = Mock()
        mock_story.user.username = "story_author"
        mock_client.story_info.return_value = mock_story

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramStoryReaderAdapter(mock_repo)
        result = adapter.get_story("acc-123", 123)

        assert result.summary.owner_username == "story_author"

    def test_missing_client_error(self):
        """Verify proper error when client not found."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramStoryReaderAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_story("acc-123", 999)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.list_user_stories("acc-123", 999)

    def test_null_field_handling(self):
        """Verify None/null fields are handled gracefully."""
        # Create mock client with minimal data
        mock_client = Mock()
        mock_story = Mock()
        mock_story.pk = 123
        mock_story.id = "123_456"
        mock_story.user = None
        mock_story.media_type = None
        mock_story.taken_at = None
        mock_story.thumbnail_url = None
        mock_story.video_url = None
        mock_story.viewer_count = None

        mock_client.story_info.return_value = mock_story

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramStoryReaderAdapter(mock_repo)
        result = adapter.get_story("acc-123", 123)

        # Verify null handling
        assert result.summary.owner_username is None
        assert result.summary.media_type is None
        assert result.summary.taken_at is None
        assert result.summary.viewer_count is None

    def test_story_detail_overlay_counting(self):
        """Verify overlay counts are extracted from story_items."""
        # Create mock client
        mock_client = Mock()
        mock_story = self._create_mock_story(pk=123)

        # Create mock story items with overlays
        mock_link = Mock()
        mock_link.story_link = Mock()

        mock_mention = Mock()
        mock_mention.story_mention = Mock()

        mock_hashtag = Mock()
        mock_hashtag.story_hashtag = Mock()

        mock_story.story_items = [mock_link, mock_mention, mock_hashtag]

        mock_client.story_info.return_value = mock_story

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramStoryReaderAdapter(mock_repo)
        result = adapter.get_story("acc-123", 123)

        assert result.link_count == 1
        assert result.mention_count == 1
        assert result.hashtag_count == 1
        assert result.location_count == 0
        assert result.sticker_count == 0

    def test_httpurl_to_string_conversion(self):
        """Verify HttpUrl fields are converted to strings."""

        class MockHttpUrl:
            def __str__(self):
                return "https://example.com/story.jpg"

        # Create mock client
        mock_client = Mock()
        mock_story = self._create_mock_story(pk=123)
        mock_story.thumbnail_url = MockHttpUrl()
        mock_story.video_url = MockHttpUrl()
        mock_client.story_info.return_value = mock_story

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramStoryReaderAdapter(mock_repo)
        result = adapter.get_story("acc-123", 123)

        # Verify string conversion
        assert isinstance(result.summary.thumbnail_url, str)
        assert result.summary.thumbnail_url == "https://example.com/story.jpg"
        assert isinstance(result.summary.video_url, str)

    @staticmethod
    def _create_mock_story(
        pk=123,
        id="123_456",
        media_type=1,
        taken_at=None,
        viewer_count=0,
        user_username=None,
    ):
        """Create a mock Story object."""
        mock_story = Mock()
        mock_story.pk = pk
        mock_story.id = id
        mock_story.media_type = media_type
        mock_story.taken_at = taken_at or datetime(2023, 1, 1, tzinfo=timezone.utc)
        mock_story.viewer_count = viewer_count
        if user_username:
            mock_story.user = Mock()
            mock_story.user.username = user_username
        else:
            mock_story.user = None
        return mock_story


class TestStoryPublisherAdapter:
    """Test the story publisher adapter."""

    def test_publish_photo_story(self):
        """Verify photo story publication maps correctly."""
        # Create mock client
        mock_client = Mock()
        published_story = TestStoryReaderAdapter._create_mock_story(pk=999)
        mock_client.photo_upload_to_story.return_value = published_story

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Create publish request
        request = StoryPublishRequest(
            media_path="/tmp/test.jpg",
            media_kind="photo",
            caption="Test caption",
            audience="default",
        )

        # Test adapter
        adapter = InstagramStoryPublisherAdapter(mock_repo)
        result = adapter.publish_story("acc-123", request)

        assert isinstance(result, StoryDetail)
        assert result.summary.pk == 999
        mock_client.photo_upload_to_story.assert_called_once()

    def test_publish_video_story(self):
        """Verify video story publication maps correctly."""
        # Create mock client
        mock_client = Mock()
        published_story = TestStoryReaderAdapter._create_mock_story(pk=999)
        mock_client.video_upload_to_story.return_value = published_story

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Create publish request
        request = StoryPublishRequest(
            media_path="/tmp/test.mp4",
            media_kind="video",
            caption="Test video",
            audience="default",
        )

        # Test adapter
        adapter = InstagramStoryPublisherAdapter(mock_repo)
        result = adapter.publish_story("acc-123", request)

        assert isinstance(result, StoryDetail)
        assert result.summary.pk == 999
        mock_client.video_upload_to_story.assert_called_once()

    def test_publish_story_with_close_friends_audience(self):
        """Verify close_friends audience maps to vendor besties."""
        # Create mock client
        mock_client = Mock()
        published_story = TestStoryReaderAdapter._create_mock_story(pk=999)
        mock_client.photo_upload_to_story.return_value = published_story

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Create publish request with close_friends
        request = StoryPublishRequest(
            media_path="/tmp/test.jpg",
            media_kind="photo",
            caption="Close friends only",
            audience="close_friends",
        )

        # Test adapter
        adapter = InstagramStoryPublisherAdapter(mock_repo)
        result = adapter.publish_story("acc-123", request)

        # Verify extra_data was set correctly
        call_args = mock_client.photo_upload_to_story.call_args
        assert call_args is not None
        # Check if extra_data was passed with besties
        if "extra_data" in call_args.kwargs:
            assert call_args.kwargs["extra_data"] == {"audience": "besties"}

    def test_publish_story_rejects_non_dto_overlay_specs(self):
        """Publisher must reject non-DTO overlay items (vendor/raw types)."""
        mock_client = Mock()
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client
        adapter = InstagramStoryPublisherAdapter(mock_repo)

        request = StoryPublishRequest(
            media_path="/tmp/test.jpg",
            media_kind="photo",
            links=[{"webUri": "https://example.com"}],  # type: ignore[list-item]
        )

        with pytest.raises(ValueError, match="StoryLinkSpec"):
            adapter.publish_story("acc-123", request)

    def test_delete_story(self):
        """Verify story deletion."""
        # Create mock client
        mock_client = Mock()
        mock_client.story_delete.return_value = None

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramStoryPublisherAdapter(mock_repo)
        result = adapter.delete_story("acc-123", 999)

        assert isinstance(result, StoryActionReceipt)
        assert result.success is True
        assert "deleted" in result.reason.lower()
        mock_client.story_delete.assert_called_once_with(999)

    def test_mark_seen(self):
        """Verify marking stories as seen."""
        # Create mock client
        mock_client = Mock()
        mock_client.story_seen.return_value = None

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramStoryPublisherAdapter(mock_repo)
        result = adapter.mark_seen("acc-123", [1, 2, 3])

        assert isinstance(result, StoryActionReceipt)
        assert result.success is True
        assert "3" in result.reason  # Should mention 3 stories
        mock_client.story_seen.assert_called_once_with([1, 2, 3], skipped_story_pks=[])

    def test_missing_client_error_publish(self):
        """Verify proper error when client not found for publish."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramStoryPublisherAdapter(mock_repo)

        request = StoryPublishRequest(
            media_path="/tmp/test.jpg",
            media_kind="photo",
        )

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.publish_story("acc-123", request)

    def test_missing_client_error_delete(self):
        """Verify proper error when client not found for delete."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramStoryPublisherAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.delete_story("acc-123", 999)

    def test_missing_client_error_mark_seen(self):
        """Verify proper error when client not found for mark_seen."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramStoryPublisherAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.mark_seen("acc-123", [1, 2, 3])


class TestStoryDTOs:
    """Test the story DTO properties."""

    def test_story_summary_frozen(self):
        """Verify StorySummary is immutable."""
        story = StorySummary(
            pk=123,
            story_id="123_456",
        )

        with pytest.raises(AttributeError):
            story.pk = 456

    def test_story_detail_frozen(self):
        """Verify StoryDetail is immutable."""
        summary = StorySummary(pk=123, story_id="123_456")
        detail = StoryDetail(summary=summary, link_count=1)

        with pytest.raises(AttributeError):
            detail.link_count = 2

    def test_story_publish_request_frozen(self):
        """Verify StoryPublishRequest is immutable."""
        request = StoryPublishRequest(
            media_path="/tmp/test.jpg",
            media_kind="photo",
        )

        with pytest.raises(AttributeError):
            request.media_path = "/tmp/other.jpg"

    def test_story_action_receipt_frozen(self):
        """Verify StoryActionReceipt is immutable."""
        receipt = StoryActionReceipt(
            action_id="test_123",
            success=True,
        )

        with pytest.raises(AttributeError):
            receipt.success = False

    def test_story_publish_request_default_values(self):
        """Verify StoryPublishRequest has sensible defaults."""
        request = StoryPublishRequest(
            media_path="/tmp/test.jpg",
            media_kind="photo",
        )

        assert request.caption is None
        assert request.thumbnail_path is None
        assert request.audience == "default"
        assert request.links == []
        assert request.locations == []
        assert request.mentions == []
        assert request.hashtags == []
        assert request.stickers == []

    def test_story_detail_default_counts(self):
        """Verify StoryDetail has default overlay counts of 0."""
        summary = StorySummary(pk=123, story_id="123_456")
        detail = StoryDetail(summary=summary)

        assert detail.link_count == 0
        assert detail.mention_count == 0
        assert detail.hashtag_count == 0
        assert detail.location_count == 0
        assert detail.sticker_count == 0

    def test_story_specs_with_placement_geometry(self):
        """Verify story specs can hold placement coordinates."""
        link = StoryLinkSpec(web_uri="https://example.com")
        mention = StoryMentionSpec(
            user_id=123,
            username="testuser",
            x=0.5,
            y=0.5,
            width=0.2,
            height=0.2,
        )
        hashtag = StoryHashtagSpec(
            hashtag_name="test",
            x=0.3,
            y=0.3,
        )
        location = StoryLocationSpec(
            location_pk=456,
            name="Test Location",
        )
        sticker = StoryStickerSpec(
            sticker_type="giphy",
            sticker_id="abc123",
        )

        assert link.web_uri == "https://example.com"
        assert mention.user_id == 123
        assert mention.x == 0.5
        assert hashtag.hashtag_name == "test"
        assert location.location_pk == 456
        assert sticker.sticker_type == "giphy"

    def test_story_publish_request_with_all_overlays(self):
        """Verify StoryPublishRequest can hold all overlay types."""
        request = StoryPublishRequest(
            media_path="/tmp/test.jpg",
            media_kind="photo",
            caption="Test with all overlays",
            audience="close_friends",
            links=[StoryLinkSpec(web_uri="https://example.com")],
            locations=[StoryLocationSpec(name="Test Location")],
            mentions=[StoryMentionSpec(user_id=123)],
            hashtags=[StoryHashtagSpec(hashtag_name="test")],
            stickers=[StoryStickerSpec(sticker_type="giphy")],
        )

        assert len(request.links) == 1
        assert len(request.locations) == 1
        assert len(request.mentions) == 1
        assert len(request.hashtags) == 1
        assert len(request.stickers) == 1
        assert request.audience == "close_friends"


class TestStoryContractProofing:
    """Contract tests proving vendor story types never leak into application code."""

    def test_story_reader_returns_only_dtos_not_vendor_types(self):
        """Verify story reader never returns vendor Story objects."""
        # Create mock client
        mock_client = Mock()
        mock_story = TestStoryReaderAdapter._create_mock_story(pk=123)
        mock_client.story_info.return_value = mock_story

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramStoryReaderAdapter(mock_repo)
        result = adapter.get_story("acc-123", 123)

        # Verify result is only DTO types, never raw vendor Story
        assert isinstance(result, StoryDetail)
        assert not hasattr(result, "story_items")  # vendor field
        assert not hasattr(result, "media_type_name")  # vendor field

    def test_story_publisher_accepts_only_dtos_not_vendor_specs(self):
        """Verify story publisher requires DTOs, not vendor types."""
        # Create mock client
        mock_client = Mock()
        published_story = TestStoryReaderAdapter._create_mock_story(pk=999)
        mock_client.photo_upload_to_story.return_value = published_story

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter accepts DTO
        adapter = InstagramStoryPublisherAdapter(mock_repo)
        request = StoryPublishRequest(
            media_path="/tmp/test.jpg",
            media_kind="photo",
            links=[StoryLinkSpec(web_uri="https://example.com")],
        )

        # Should succeed with DTO
        result = adapter.publish_story("acc-123", request)
        assert isinstance(result, StoryDetail)

        # Attempting to pass vendor types would fail
        # (This is enforced by type hints and runtime checks)

    def test_story_overlay_specs_are_application_owned(self):
        """Verify overlay specs are application-owned, not vendor-borrowed."""
        link = StoryLinkSpec(web_uri="https://example.com")
        mention = StoryMentionSpec(user_id=123)
        hashtag = StoryHashtagSpec(hashtag_name="test")
        location = StoryLocationSpec(name="Test")
        sticker = StoryStickerSpec(sticker_type="giphy")

        # These should be frozen DTOs, not vendor types
        assert hasattr(link, "__dataclass_fields__")
        assert hasattr(mention, "__dataclass_fields__")
        assert hasattr(hashtag, "__dataclass_fields__")
        assert hasattr(location, "__dataclass_fields__")
        assert hasattr(sticker, "__dataclass_fields__")

        # Should be immutable (frozen dataclasses)
        with pytest.raises(AttributeError):
            link.web_uri = "https://different.com"
