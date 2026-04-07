"""
Tests for Instagram media reader and DTO mappings.

Verifies that instagrapi Media, Resource, and MediaOembed objects map correctly
to stable application DTOs while handling vendor field variations and null safety.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock

from app.application.dto.instagram_media_dto import (
    MediaSummary,
    ResourceSummary,
    MediaOembedSummary,
)
from app.adapters.instagram.media_reader import (
    InstagramMediaReaderAdapter,
)


class TestMediaReaderAdapter:
    """Test the media reader adapter mappings."""

    def test_get_media_by_pk(self):
        """Verify media_info() maps correctly to MediaSummary."""
        # Create mock client
        mock_client = Mock()
        mock_media = self._create_mock_media(
            pk=123,
            id="123_456",
            code="ABC123",
            caption_text="Test post caption",
            like_count=100,
            comment_count=5,
        )
        mock_client.media_info.return_value = mock_media

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramMediaReaderAdapter(mock_repo)
        result = adapter.get_media_by_pk("acc-123", 123)

        assert isinstance(result, MediaSummary)
        assert result.pk == 123
        assert result.media_id == "123_456"
        assert result.code == "ABC123"
        assert result.caption_text == "Test post caption"
        assert result.like_count == 100
        assert result.comment_count == 5
        mock_client.media_info.assert_called_once_with(123)

    def test_media_mapping_with_album_resources(self):
        """Verify album media maps resources correctly."""
        # Create mock client
        mock_client = Mock()

        # Create resources for carousel
        resource1 = Mock()
        resource1.pk = 1001
        resource1.media_type = 1  # photo
        resource1.thumbnail_url = "https://example.com/thumb1.jpg"
        resource1.video_url = None

        resource2 = Mock()
        resource2.pk = 1002
        resource2.media_type = 2  # video
        resource2.thumbnail_url = "https://example.com/thumb2.jpg"
        resource2.video_url = "https://example.com/vid2.mp4"

        mock_media = self._create_mock_media(
            pk=200,
            media_type=8,  # album
            resources=[resource1, resource2],
        )
        mock_client.media_info.return_value = mock_media

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramMediaReaderAdapter(mock_repo)
        result = adapter.get_media_by_pk("acc-123", 200)

        # Verify resources are mapped
        assert len(result.resources) == 2
        assert result.resources[0].pk == 1001
        assert result.resources[0].media_type == 1
        assert result.resources[0].thumbnail_url == "https://example.com/thumb1.jpg"
        assert result.resources[1].pk == 1002
        assert result.resources[1].media_type == 2
        assert result.resources[1].video_url == "https://example.com/vid2.mp4"

    def test_media_mapping_missing_resources(self):
        """Verify missing resources are treated as empty list."""
        # Create mock client
        mock_client = Mock()
        mock_media = self._create_mock_media(
            pk=300,
            media_type=1,  # single photo
            resources=None,
        )
        mock_client.media_info.return_value = mock_media

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramMediaReaderAdapter(mock_repo)
        result = adapter.get_media_by_pk("acc-123", 300)

        # Verify empty resources list
        assert result.resources == []

    def test_caption_field_standardization(self):
        """Verify caption_text is preferred over caption field."""
        # Create mock client
        mock_client = Mock()

        # Test with caption_text field
        mock_media1 = self._create_mock_media()
        mock_media1.caption_text = "Modern caption"
        if hasattr(mock_media1, "caption"):
            mock_media1.caption = "Legacy caption"
        mock_client.media_info.return_value = mock_media1

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        adapter = InstagramMediaReaderAdapter(mock_repo)
        result = adapter.get_media_by_pk("acc-123", 123)

        # Should use caption_text
        assert result.caption_text == "Modern caption"

    def test_get_user_medias(self):
        """Verify get_user_medias maps multiple media correctly."""
        # Create mock client
        mock_client = Mock()
        media_list = [
            self._create_mock_media(pk=1, caption_text="Post 1"),
            self._create_mock_media(pk=2, caption_text="Post 2"),
            self._create_mock_media(pk=3, caption_text="Post 3"),
        ]
        mock_client.user_medias.return_value = media_list

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramMediaReaderAdapter(mock_repo)
        results = adapter.get_user_medias("acc-123", 999, amount=3)

        assert len(results) == 3
        assert all(isinstance(r, MediaSummary) for r in results)
        assert results[0].pk == 1
        assert results[1].pk == 2
        assert results[2].pk == 3
        mock_client.user_medias.assert_called_once_with(999, amount=3)

    def test_get_media_oembed(self):
        """Verify media_oembed() maps to MediaOembedSummary."""
        # Create mock client
        mock_client = Mock()
        mock_oembed = Mock()
        mock_oembed.media_id = "oembed-123"
        mock_oembed.author_name = "TestUser"
        mock_oembed.author_url = "https://instagram.com/testuser"
        mock_oembed.author_id = 999
        mock_oembed.title = "Post title"
        mock_oembed.provider_name = "Instagram"
        mock_oembed.html = "<iframe>...</iframe>"
        mock_oembed.thumbnail_url = "https://example.com/thumb.jpg"
        mock_oembed.width = 600
        mock_oembed.height = 400
        mock_oembed.can_view = True

        mock_client.media_oembed.return_value = mock_oembed

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramMediaReaderAdapter(mock_repo)
        result = adapter.get_media_oembed(
            "acc-123", "https://www.instagram.com/p/CODE/"
        )

        assert isinstance(result, MediaOembedSummary)
        assert result.media_id == "oembed-123"
        assert result.author_name == "TestUser"
        assert result.author_id == 999
        assert result.html == "<iframe>...</iframe>"
        assert result.width == 600
        assert result.height == 400

    def test_owner_username_extraction(self):
        """Verify owner username is extracted from nested user object."""
        # Create mock client
        mock_client = Mock()
        mock_media = self._create_mock_media(pk=123)
        mock_media.user = Mock()
        mock_media.user.username = "post_author"
        mock_client.media_info.return_value = mock_media

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramMediaReaderAdapter(mock_repo)
        result = adapter.get_media_by_pk("acc-123", 123)

        assert result.owner_username == "post_author"

    def test_missing_client_error(self):
        """Verify proper error when client not found."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramMediaReaderAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_media_by_pk("acc-123", 999)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_user_medias("acc-123", 999)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_media_oembed("acc-123", "https://instagram.com/p/test/")

    @staticmethod
    def _create_mock_media(
        pk=123,
        id="123_456",
        code="ABC123",
        media_type=1,
        product_type="feed",
        caption_text="Test caption",
        like_count=0,
        comment_count=0,
        taken_at=None,
        resources=None,
        user_username=None,
    ):
        """Create a mock Media object."""
        mock_media = Mock()
        mock_media.pk = pk
        mock_media.id = id
        mock_media.code = code
        mock_media.media_type = media_type
        mock_media.product_type = product_type
        mock_media.caption_text = caption_text
        mock_media.like_count = like_count
        mock_media.comment_count = comment_count
        mock_media.taken_at = taken_at or datetime(
            2023, 1, 1, tzinfo=timezone.utc
        )
        mock_media.resources = resources
        if user_username:
            mock_media.user = Mock()
            mock_media.user.username = user_username
        else:
            mock_media.user = None
        return mock_media

    def test_null_field_handling(self):
        """Verify None/null fields are handled gracefully."""
        # Create mock client with minimal data
        mock_client = Mock()
        mock_media = Mock()
        mock_media.pk = 123
        mock_media.id = "123_456"
        mock_media.code = "ABC"
        mock_media.media_type = 1
        mock_media.product_type = ""
        mock_media.user = None
        mock_media.caption_text = None
        mock_media.like_count = None
        mock_media.comment_count = None
        mock_media.taken_at = None
        mock_media.resources = None

        mock_client.media_info.return_value = mock_media

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramMediaReaderAdapter(mock_repo)
        result = adapter.get_media_by_pk("acc-123", 123)

        # Verify null handling
        assert result.owner_username is None
        assert result.caption_text == ""
        assert result.like_count == 0
        assert result.comment_count == 0
        assert result.taken_at is None
        assert result.resources == []

    def test_httpurl_to_string_conversion(self):
        """Verify HttpUrl fields are converted to strings."""

        class MockHttpUrl:
            def __str__(self):
                return "https://example.com/image.jpg"

        # Create mock client
        mock_client = Mock()
        mock_oembed = Mock()
        mock_oembed.media_id = "test"
        mock_oembed.author_url = MockHttpUrl()
        mock_oembed.thumbnail_url = MockHttpUrl()
        mock_oembed.author_name = None
        mock_oembed.author_id = None
        mock_oembed.title = None
        mock_oembed.provider_name = None
        mock_oembed.html = None
        mock_oembed.width = None
        mock_oembed.height = None
        mock_oembed.can_view = None

        mock_client.media_oembed.return_value = mock_oembed

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramMediaReaderAdapter(mock_repo)
        result = adapter.get_media_oembed("acc-123", "https://instagram.com/p/test/")

        # Verify string conversion
        assert isinstance(result.author_url, str)
        assert result.author_url == "https://example.com/image.jpg"
        assert isinstance(result.thumbnail_url, str)
        assert result.thumbnail_url == "https://example.com/image.jpg"


class TestMediaDTOs:
    """Test the media DTO properties."""

    def test_media_summary_frozen(self):
        """Verify MediaSummary is immutable."""
        media = MediaSummary(
            pk=123,
            media_id="123_456",
            code="ABC",
            media_type=1,
            product_type="feed",
            caption_text="Test",
        )

        with pytest.raises(AttributeError):
            media.caption_text = "Modified"

    def test_resource_summary_frozen(self):
        """Verify ResourceSummary is immutable."""
        resource = ResourceSummary(
            pk=999,
            media_type=1,
            thumbnail_url="https://example.com/thumb.jpg",
        )

        with pytest.raises(AttributeError):
            resource.pk = 888

    def test_oembed_summary_frozen(self):
        """Verify MediaOembedSummary is immutable."""
        oembed = MediaOembedSummary(
            media_id="test-123",
            author_name="TestUser",
        )

        with pytest.raises(AttributeError):
            oembed.author_name = "Different"

    def test_media_summary_default_values(self):
        """Verify MediaSummary has sensible defaults."""
        media = MediaSummary(
            pk=123,
            media_id="123_456",
            code="ABC",
            media_type=1,
            product_type="feed",
        )

        assert media.caption_text == ""
        assert media.like_count == 0
        assert media.comment_count == 0
        assert media.resources == []
        assert media.owner_username is None
        assert media.taken_at is None

    def test_media_summary_with_resources(self):
        """Verify MediaSummary can contain ResourceSummary items."""
        resources = [
            ResourceSummary(pk=1, media_type=1),
            ResourceSummary(pk=2, media_type=2),
        ]
        media = MediaSummary(
            pk=123,
            media_id="123_456",
            code="ABC",
            media_type=8,  # album
            product_type="feed",
            resources=resources,
        )

        assert len(media.resources) == 2
        assert media.resources[0].pk == 1
        assert media.resources[1].pk == 2
