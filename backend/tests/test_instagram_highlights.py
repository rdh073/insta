"""
Tests for Instagram highlight reader, writer, and DTO mappings.

Verifies that instagrapi Highlight objects map correctly to stable application DTOs
while reusing StorySummary from Phase 4. Ensures nested Story types never leak into
application code, and all results use shared story mapping.
"""

import pytest
import sys
import types
from datetime import datetime, timezone
from unittest.mock import Mock

from app.application.dto.instagram_highlight_dto import (
    HighlightCoverSummary,
    HighlightSummary,
    HighlightDetail,
    HighlightActionReceipt,
)
from app.application.dto.instagram_story_dto import StorySummary
from app.adapters.instagram.highlight_reader import (
    InstagramHighlightReaderAdapter,
)
from app.adapters.instagram.highlight_writer import (
    InstagramHighlightWriterAdapter,
)


class TestHighlightReaderAdapter:
    """Test the highlight reader adapter mappings."""

    def test_get_highlight_pk_from_url(self, monkeypatch):
        """Verify highlight_pk_from_url delegates to instagrapi utility."""
        instagrapi_module = types.ModuleType("instagrapi")

        class _FakeClient:
            def highlight_pk_from_url(self, url):
                assert "instagram.com/stories/highlights" in url
                return 17907771728171896

        instagrapi_module.Client = _FakeClient
        monkeypatch.setitem(sys.modules, "instagrapi", instagrapi_module)

        adapter = InstagramHighlightReaderAdapter(Mock())
        result = adapter.get_highlight_pk_from_url(
            "https://www.instagram.com/stories/highlights/17907771728171896/"
        )

        assert result == 17907771728171896

    def test_get_highlight(self):
        """Verify highlight_info() maps to HighlightDetail."""
        # Create mock client
        mock_client = Mock()
        mock_highlight = self._create_mock_highlight(
            pk=123,
            id="123_456",
            title="Test Highlight",
            media_count=5,
        )
        mock_client.highlight_info.return_value = mock_highlight

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramHighlightReaderAdapter(mock_repo)
        result = adapter.get_highlight("acc-123", 123)

        assert isinstance(result, HighlightDetail)
        assert result.summary.pk == "123"
        assert result.summary.highlight_id == "123_456"
        assert result.summary.title == "Test Highlight"
        assert result.summary.media_count == 5
        mock_client.highlight_info.assert_called_once_with(123)

    def test_list_user_highlights(self):
        """Verify user_highlights() maps multiple highlights correctly."""
        # Create mock client
        mock_client = Mock()
        highlight_list = [
            self._create_mock_highlight(pk=1, id="1_1", title="First"),
            self._create_mock_highlight(pk=2, id="2_2", title="Second"),
            self._create_mock_highlight(pk=3, id="3_3", title="Third"),
        ]
        mock_client.user_highlights.return_value = highlight_list

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramHighlightReaderAdapter(mock_repo)
        results = adapter.list_user_highlights("acc-123", 999, amount=3)

        assert len(results) == 3
        assert all(isinstance(r, HighlightSummary) for r in results)
        assert results[0].pk == "1"
        assert results[1].title == "Second"
        assert results[2].pk == "3"
        mock_client.user_highlights.assert_called_once_with(999, amount=3)

    def test_highlight_with_stories(self):
        """Verify highlight story items map to StorySummary list."""
        # Create mock client
        mock_client = Mock()
        mock_story1 = self._create_mock_story(pk=10, id="10_1")
        mock_story2 = self._create_mock_story(pk=11, id="11_1")
        mock_highlight = self._create_mock_highlight(
            pk=123,
            id="123_456",
            title="Story Highlight",
            story_ids=[10, 11],
            items=[mock_story1, mock_story2],
        )
        mock_client.highlight_info.return_value = mock_highlight

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramHighlightReaderAdapter(mock_repo)
        result = adapter.get_highlight("acc-123", 123)

        # Verify stories are mapped to StorySummary
        assert len(result.items) == 2
        assert all(isinstance(s, StorySummary) for s in result.items)
        assert result.items[0].pk == 10
        assert result.items[1].pk == 11
        assert result.story_ids == ["10", "11"]

    def test_owner_username_extraction(self):
        """Verify owner username is extracted from nested user object."""
        # Create mock client
        mock_client = Mock()
        mock_highlight = self._create_mock_highlight(pk=123)
        mock_highlight.user = Mock()
        mock_highlight.user.username = "highlight_owner"
        mock_client.highlight_info.return_value = mock_highlight

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramHighlightReaderAdapter(mock_repo)
        result = adapter.get_highlight("acc-123", 123)

        assert result.summary.owner_username == "highlight_owner"

    def test_highlight_cover_extraction(self):
        """Verify highlight cover metadata is extracted."""
        # Create mock client
        mock_client = Mock()
        mock_highlight = self._create_mock_highlight(pk=123)

        # Create mock cover media
        mock_cover = Mock()
        mock_cover.id = "cover_123"
        mock_cover.crop_rect = [0.1, 0.2, 0.8, 0.9]
        # Simulate image_versions2 structure
        mock_cover.image_versions2 = {
            "candidates": [{"url": "https://example.com/cover.jpg"}]
        }
        mock_highlight.cover_media = mock_cover

        mock_client.highlight_info.return_value = mock_highlight

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramHighlightReaderAdapter(mock_repo)
        result = adapter.get_highlight("acc-123", 123)

        assert result.summary.cover is not None
        assert isinstance(result.summary.cover, HighlightCoverSummary)
        assert result.summary.cover.media_id == "cover_123"
        assert result.summary.cover.crop_rect == [0.1, 0.2, 0.8, 0.9]

    def test_missing_client_error(self):
        """Verify proper error when client not found."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramHighlightReaderAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_highlight("acc-123", 999)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.list_user_highlights("acc-123", 999)

    def test_null_field_handling(self):
        """Verify None/null fields are handled gracefully."""
        # Create mock client with minimal data
        mock_client = Mock()
        mock_highlight = Mock()
        mock_highlight.pk = 123
        mock_highlight.id = "123_456"
        mock_highlight.title = None
        mock_highlight.created_at = None
        mock_highlight.is_pinned_highlight = None
        mock_highlight.media_count = None
        mock_highlight.latest_reel_media = None
        mock_highlight.user = None
        mock_highlight.cover_media = None
        mock_highlight.media_ids = None
        mock_highlight.items = None

        mock_client.highlight_info.return_value = mock_highlight

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramHighlightReaderAdapter(mock_repo)
        result = adapter.get_highlight("acc-123", 123)

        # Verify null handling
        assert result.summary.title is None
        assert result.summary.created_at is None
        assert result.summary.owner_username is None
        assert result.summary.cover is None
        assert result.story_ids == []
        assert result.items == []

    @staticmethod
    def _create_mock_highlight(
        pk=1,
        id="1_1",
        title="Test",
        media_count=0,
        created_at=None,
        story_ids=None,
        items=None,
    ):
        """Create a mock Highlight object."""
        mock = Mock()
        mock.pk = pk
        mock.id = id
        mock.title = title
        mock.media_count = media_count
        mock.created_at = created_at or datetime(2023, 1, 1, tzinfo=timezone.utc)
        mock.is_pinned_highlight = False
        mock.latest_reel_media = None
        mock.user = None
        mock.cover_media = None
        mock.media_ids = story_ids or []
        mock.items = items or []
        return mock

    @staticmethod
    def _create_mock_story(pk=1, id="1_1"):
        """Create a mock Story object."""
        mock = Mock()
        mock.pk = pk
        mock.id = id
        mock.media_type = 1
        mock.taken_at = datetime(2023, 1, 1, tzinfo=timezone.utc)
        mock.viewer_count = 0
        mock.user = None
        return mock


class TestHighlightWriterAdapter:
    """Test the highlight writer adapter."""

    def test_create_highlight(self):
        """Verify highlight_create() maps to HighlightDetail."""
        # Create mock client
        mock_client = Mock()
        created_highlight = TestHighlightReaderAdapter._create_mock_highlight(
            pk=999, title="New Highlight"
        )
        mock_client.highlight_create.return_value = created_highlight

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Create writer
        adapter = InstagramHighlightWriterAdapter(mock_repo)
        result = adapter.create_highlight(
            "acc-123",
            "New Highlight",
            [1, 2, 3],
        )

        assert isinstance(result, HighlightDetail)
        assert result.summary.pk == "999"
        assert result.summary.title == "New Highlight"
        mock_client.highlight_create.assert_called_once()

    def test_create_highlight_with_cover_and_crop(self):
        """Verify create_highlight passes cover and crop parameters."""
        # Create mock client
        mock_client = Mock()
        created_highlight = TestHighlightReaderAdapter._create_mock_highlight(pk=999)
        mock_client.highlight_create.return_value = created_highlight

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Create writer
        adapter = InstagramHighlightWriterAdapter(mock_repo)
        crop = [0.1, 0.2, 0.8, 0.9]
        result = adapter.create_highlight(
            "acc-123",
            "Test",
            [1, 2],
            cover_story_id=1,
            crop_rect=crop,
        )

        # Verify parameters were passed
        call_args = mock_client.highlight_create.call_args
        assert call_args.kwargs.get("cover_story_id") == 1
        assert call_args.kwargs.get("crop_rect") == crop

    def test_change_title(self):
        """Verify highlight_change_title() updates highlight."""
        # Create mock client
        mock_client = Mock()
        updated_highlight = TestHighlightReaderAdapter._create_mock_highlight(
            pk=123, title="Updated Title"
        )
        mock_client.highlight_change_title.return_value = updated_highlight

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Create writer
        adapter = InstagramHighlightWriterAdapter(mock_repo)
        result = adapter.change_title("acc-123", 123, "Updated Title")

        assert isinstance(result, HighlightDetail)
        assert result.summary.title == "Updated Title"
        mock_client.highlight_change_title.assert_called_once_with(123, "Updated Title")

    def test_add_stories(self):
        """Verify highlight_add_stories() adds stories."""
        # Create mock client
        mock_client = Mock()
        story1 = TestHighlightReaderAdapter._create_mock_story(pk=10)
        story2 = TestHighlightReaderAdapter._create_mock_story(pk=11)
        story3 = TestHighlightReaderAdapter._create_mock_story(pk=12)
        updated_highlight = TestHighlightReaderAdapter._create_mock_highlight(
            pk=123,
            story_ids=[10, 11, 12],
            items=[story1, story2, story3],
        )
        mock_client.highlight_add_stories.return_value = updated_highlight

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Create writer
        adapter = InstagramHighlightWriterAdapter(mock_repo)
        result = adapter.add_stories("acc-123", 123, [12])

        assert len(result.items) == 3
        assert result.story_ids == ["10", "11", "12"]
        mock_client.highlight_add_stories.assert_called_once_with(123, [12])

    def test_remove_stories(self):
        """Verify highlight_remove_stories() removes stories."""
        # Create mock client
        mock_client = Mock()
        story1 = TestHighlightReaderAdapter._create_mock_story(pk=10)
        updated_highlight = TestHighlightReaderAdapter._create_mock_highlight(
            pk=123,
            story_ids=[10],
            items=[story1],
        )
        mock_client.highlight_remove_stories.return_value = updated_highlight

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Create writer
        adapter = InstagramHighlightWriterAdapter(mock_repo)
        result = adapter.remove_stories("acc-123", 123, [11, 12])

        assert len(result.items) == 1
        assert result.story_ids == ["10"]
        mock_client.highlight_remove_stories.assert_called_once_with(123, [11, 12])

    def test_delete_highlight(self):
        """Verify highlight_delete() returns success receipt."""
        # Create mock client
        mock_client = Mock()
        mock_client.highlight_delete.return_value = None

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Create writer
        adapter = InstagramHighlightWriterAdapter(mock_repo)
        result = adapter.delete_highlight("acc-123", 123)

        assert isinstance(result, HighlightActionReceipt)
        assert result.success is True
        assert "deleted" in result.reason.lower()
        mock_client.highlight_delete.assert_called_once_with(123)

    def test_missing_client_error_create(self):
        """Verify proper error when client not found for create."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramHighlightWriterAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.create_highlight("acc-123", "Title", [1, 2])

    def test_missing_client_error_delete(self):
        """Verify proper error when client not found for delete."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramHighlightWriterAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.delete_highlight("acc-123", 123)


class TestHighlightDTOs:
    """Test the highlight DTO properties."""

    def test_highlight_summary_frozen(self):
        """Verify HighlightSummary is immutable."""
        summary = HighlightSummary(pk="1", highlight_id="1_1")
        with pytest.raises(AttributeError):
            summary.title = "Different"

    def test_highlight_detail_frozen(self):
        """Verify HighlightDetail is immutable."""
        summary = HighlightSummary(pk="1", highlight_id="1_1")
        detail = HighlightDetail(summary=summary)
        with pytest.raises(AttributeError):
            detail.summary = None

    def test_highlight_cover_summary_frozen(self):
        """Verify HighlightCoverSummary is immutable."""
        cover = HighlightCoverSummary(media_id="1", image_url="url")
        with pytest.raises(AttributeError):
            cover.media_id = "2"

    def test_highlight_action_receipt_frozen(self):
        """Verify HighlightActionReceipt is immutable."""
        receipt = HighlightActionReceipt(action_id="test", success=True)
        with pytest.raises(AttributeError):
            receipt.success = False

    def test_highlight_summary_defaults(self):
        """Verify HighlightSummary has sensible defaults."""
        summary = HighlightSummary(pk="1", highlight_id="1_1")
        assert summary.title is None
        assert summary.created_at is None
        assert summary.is_pinned is None
        assert summary.media_count is None
        assert summary.owner_username is None
        assert summary.cover is None

    def test_highlight_detail_defaults(self):
        """Verify HighlightDetail has sensible defaults."""
        summary = HighlightSummary(pk="1", highlight_id="1_1")
        detail = HighlightDetail(summary=summary)
        assert detail.story_ids == []
        assert detail.items == []

    def test_highlight_detail_with_stories(self):
        """Verify HighlightDetail can hold StorySummary items."""
        summary = HighlightSummary(pk="1", highlight_id="1_1")
        stories = [
            StorySummary(pk=10, story_id="10_1"),
            StorySummary(pk=11, story_id="11_1"),
        ]
        detail = HighlightDetail(
            summary=summary,
            story_ids=["10", "11"],
            items=stories,
        )

        assert len(detail.items) == 2
        assert detail.items[0].pk == 10
        assert detail.items[1].story_id == "11_1"

    def test_highlight_cover_summary_with_crop(self):
        """Verify HighlightCoverSummary can hold crop rectangle."""
        cover = HighlightCoverSummary(
            media_id="1",
            image_url="url",
            crop_rect=[0.1, 0.2, 0.8, 0.9],
        )

        assert cover.crop_rect == [0.1, 0.2, 0.8, 0.9]


class TestHighlightContractProofing:
    """Contract tests proving vendor types never leak into application code."""

    def test_highlight_reader_returns_only_dtos_not_vendor_types(self):
        """Verify highlight reader never returns vendor Highlight objects."""
        # Create mock client
        mock_client = Mock()
        mock_highlight = TestHighlightReaderAdapter._create_mock_highlight(pk=1)
        mock_client.highlight_info.return_value = mock_highlight

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramHighlightReaderAdapter(mock_repo)
        result = adapter.get_highlight("acc-123", 1)

        # Verify result is only DTO, never raw vendor
        assert isinstance(result, HighlightDetail)
        assert not hasattr(result, "user")  # vendor field
        assert not hasattr(result, "cover_media")  # vendor field

    def test_stories_use_shared_story_dto_not_vendor_types(self):
        """Verify highlight story items use StorySummary, not vendor Story."""
        # Create mock client
        mock_client = Mock()
        mock_story = TestHighlightReaderAdapter._create_mock_story(pk=10)
        mock_highlight = TestHighlightReaderAdapter._create_mock_highlight(
            pk=1,
            items=[mock_story],
        )
        mock_client.highlight_info.return_value = mock_highlight

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramHighlightReaderAdapter(mock_repo)
        result = adapter.get_highlight("acc-123", 1)

        # Verify stories are StorySummary DTO, not raw vendor Story
        assert len(result.items) == 1
        assert isinstance(result.items[0], StorySummary)
        # Vendor Story fields should not be present
        assert not hasattr(result.items[0], "media_versions2")  # vendor field

    def test_cover_uses_dto_not_vendor_media(self):
        """Verify highlight cover uses HighlightCoverSummary DTO."""
        # Create mock client
        mock_client = Mock()
        mock_highlight = TestHighlightReaderAdapter._create_mock_highlight(pk=1)
        mock_cover = Mock()
        mock_cover.id = "1"
        mock_cover.image_versions2 = {"candidates": [{"url": "url"}]}
        mock_cover.crop_rect = [0.1, 0.2, 0.8, 0.9]
        mock_highlight.cover_media = mock_cover
        mock_client.highlight_info.return_value = mock_highlight

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramHighlightReaderAdapter(mock_repo)
        result = adapter.get_highlight("acc-123", 1)

        # Verify cover is DTO
        assert isinstance(result.summary.cover, HighlightCoverSummary)
        assert not hasattr(result.summary.cover, "image_versions2")  # vendor field
