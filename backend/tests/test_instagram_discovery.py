"""
Tests for Instagram discovery reader and collection reader, and DTO mappings.

Verifies that instagrapi Location, Hashtag, and Collection objects map correctly
to stable application DTOs while reusing MediaSummary for all media-returning flows.
Ensures vendor types never leak into application code.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock

from app.application.dto.instagram_discovery_dto import (
    LocationSummary,
    HashtagSummary,
    CollectionSummary,
)
from app.application.dto.instagram_media_dto import MediaSummary
from app.adapters.instagram.discovery_reader import (
    InstagramDiscoveryReaderAdapter,
)
from app.adapters.instagram.collection_reader import (
    InstagramCollectionReaderAdapter,
)


class TestDiscoveryReaderAdapter:
    """Test the discovery reader adapter mappings."""

    def test_search_locations(self):
        """Verify fbsearch_places maps to LocationSummary list."""
        # Create mock client
        mock_client = Mock()
        mock_locations = [
            self._create_mock_location(pk=1, name="Restaurant A", city="NYC"),
            self._create_mock_location(pk=2, name="Restaurant B", city="NYC"),
        ]
        mock_client.fbsearch_places.return_value = mock_locations

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDiscoveryReaderAdapter(mock_repo)
        results = adapter.search_locations("acc-123", "restaurants")

        assert len(results) == 2
        assert all(isinstance(r, LocationSummary) for r in results)
        assert results[0].pk == 1
        assert results[0].name == "Restaurant A"
        assert results[1].city == "NYC"
        mock_client.fbsearch_places.assert_called_once()

    def test_search_locations_with_coordinates(self):
        """Verify location search with lat/lng parameters."""
        # Create mock client
        mock_client = Mock()
        mock_locations = [self._create_mock_location(pk=1, name="Nearby Place")]
        mock_client.fbsearch_places.return_value = mock_locations

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDiscoveryReaderAdapter(mock_repo)
        results = adapter.search_locations("acc-123", "places", lat=40.7128, lng=-74.0060)

        assert len(results) == 1
        assert results[0].name == "Nearby Place"
        # Verify parameters were passed
        call_args = mock_client.fbsearch_places.call_args
        assert call_args.kwargs.get("lat") == 40.7128
        assert call_args.kwargs.get("lng") == -74.0060

    def test_get_location(self):
        """Verify location_info maps to LocationSummary."""
        # Create mock client
        mock_client = Mock()
        mock_location = self._create_mock_location(pk=123, name="Test Location")
        mock_client.location_info.return_value = mock_location

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDiscoveryReaderAdapter(mock_repo)
        result = adapter.get_location("acc-123", 123)

        assert isinstance(result, LocationSummary)
        assert result.pk == 123
        assert result.name == "Test Location"
        mock_client.location_info.assert_called_once_with(123)

    def test_get_location_top_posts(self):
        """Verify location top posts return MediaSummary list."""
        # Create mock client
        mock_client = Mock()
        mock_media = [
            self._create_mock_media(pk=1, caption_text="Post 1"),
            self._create_mock_media(pk=2, caption_text="Post 2"),
        ]
        mock_client.location_medias_top.return_value = mock_media

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDiscoveryReaderAdapter(mock_repo)
        results = adapter.get_location_top_posts("acc-123", 123, amount=2)

        assert len(results) == 2
        assert all(isinstance(r, MediaSummary) for r in results)
        assert results[0].pk == 1
        assert results[0].caption_text == "Post 1"
        mock_client.location_medias_top.assert_called_once_with(123, amount=2)

    def test_get_location_recent_posts(self):
        """Verify location recent posts return MediaSummary list."""
        # Create mock client
        mock_client = Mock()
        mock_media = [self._create_mock_media(pk=1, caption_text="Recent 1")]
        mock_client.location_medias_recent.return_value = mock_media

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDiscoveryReaderAdapter(mock_repo)
        results = adapter.get_location_recent_posts("acc-123", 123, amount=5)

        assert len(results) == 1
        assert isinstance(results[0], MediaSummary)
        mock_client.location_medias_recent.assert_called_once_with(123, amount=5)

    def test_get_hashtag(self):
        """Verify hashtag_info maps to HashtagSummary."""
        # Create mock client
        mock_client = Mock()
        mock_hashtag = self._create_mock_hashtag(id=456, name="test", media_count=1000)
        mock_client.hashtag_info.return_value = mock_hashtag

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDiscoveryReaderAdapter(mock_repo)
        result = adapter.get_hashtag("acc-123", "test")

        assert isinstance(result, HashtagSummary)
        assert result.id == 456
        assert result.name == "test"
        assert result.media_count == 1000
        # Should normalize hashtag name (remove #)
        mock_client.hashtag_info.assert_called_once_with("test")

    def test_get_hashtag_with_hash_symbol(self):
        """Verify hashtag name normalization removes # prefix."""
        # Create mock client
        mock_client = Mock()
        mock_hashtag = self._create_mock_hashtag(id=456, name="test")
        mock_client.hashtag_info.return_value = mock_hashtag

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter with # prefix
        adapter = InstagramDiscoveryReaderAdapter(mock_repo)
        result = adapter.get_hashtag("acc-123", "#test")

        # Should call with normalized name (no #)
        mock_client.hashtag_info.assert_called_once_with("test")

    def test_get_hashtag_top_posts(self):
        """Verify hashtag top posts return MediaSummary list."""
        # Create mock client
        mock_client = Mock()
        mock_media = [self._create_mock_media(pk=5, caption_text="Popular")]
        mock_client.hashtag_medias_top.return_value = mock_media

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDiscoveryReaderAdapter(mock_repo)
        results = adapter.get_hashtag_top_posts("acc-123", "test", amount=10)

        assert len(results) == 1
        assert isinstance(results[0], MediaSummary)
        assert results[0].pk == 5
        mock_client.hashtag_medias_top.assert_called_once()

    def test_get_hashtag_recent_posts(self):
        """Verify hashtag recent posts return MediaSummary list."""
        # Create mock client
        mock_client = Mock()
        mock_media = [
            self._create_mock_media(pk=10, caption_text="New 1"),
            self._create_mock_media(pk=11, caption_text="New 2"),
        ]
        mock_client.hashtag_medias_recent.return_value = mock_media

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDiscoveryReaderAdapter(mock_repo)
        results = adapter.get_hashtag_recent_posts("acc-123", "test", amount=15)

        assert len(results) == 2
        assert all(isinstance(r, MediaSummary) for r in results)
        mock_client.hashtag_medias_recent.assert_called_once()

    def test_missing_client_error(self):
        """Verify proper error when client not found."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramDiscoveryReaderAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.search_locations("acc-123", "query")

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_location("acc-123", 123)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_hashtag("acc-123", "test")

    def test_location_mapping_with_full_metadata(self):
        """Verify location mapping extracts all available fields."""
        # Create mock client
        mock_client = Mock()
        mock_location = Mock()
        mock_location.pk = 999
        mock_location.name = "Test Venue"
        mock_location.address = "123 Main St"
        mock_location.city = "Springfield"
        mock_location.lat = 40.7128
        mock_location.lng = -74.0060
        mock_location.external_id = 12345
        mock_location.external_id_source = "fbsearch"

        mock_client.location_info.return_value = mock_location

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDiscoveryReaderAdapter(mock_repo)
        result = adapter.get_location("acc-123", 999)

        assert result.pk == 999
        assert result.name == "Test Venue"
        assert result.address == "123 Main St"
        assert result.city == "Springfield"
        assert result.lat == 40.7128
        assert result.lng == -74.0060
        assert result.external_id == 12345
        assert result.external_id_source == "fbsearch"

    def test_hashtag_mapping_with_profile_pic_url(self):
        """Verify hashtag profile_pic_url is converted to string."""

        class MockHttpUrl:
            def __str__(self):
                return "https://example.com/profile.jpg"

        # Create mock client
        mock_client = Mock()
        mock_hashtag = Mock()
        mock_hashtag.id = 789
        mock_hashtag.name = "test"
        mock_hashtag.media_count = 500
        mock_hashtag.profile_pic_url = MockHttpUrl()

        mock_client.hashtag_info.return_value = mock_hashtag

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDiscoveryReaderAdapter(mock_repo)
        result = adapter.get_hashtag("acc-123", "test")

        assert isinstance(result.profile_pic_url, str)
        assert result.profile_pic_url == "https://example.com/profile.jpg"

    @staticmethod
    def _create_mock_location(pk=1, name="Test", city=None):
        """Create a mock Location object."""
        mock = Mock()
        mock.pk = pk
        mock.name = name
        mock.address = None
        mock.city = city
        mock.lat = None
        mock.lng = None
        mock.external_id = None
        mock.external_id_source = None
        return mock

    @staticmethod
    def _create_mock_hashtag(id=1, name="test", media_count=0):
        """Create a mock Hashtag object."""
        mock = Mock()
        mock.id = id
        mock.name = name
        mock.media_count = media_count
        mock.profile_pic_url = None
        return mock

    @staticmethod
    def _create_mock_media(pk=1, caption_text=""):
        """Create a mock Media object."""
        mock = Mock()
        mock.pk = pk
        mock.id = f"{pk}_1"
        mock.code = f"CODE{pk}"
        mock.media_type = 1
        mock.product_type = "feed"
        mock.caption_text = caption_text
        mock.like_count = 0
        mock.comment_count = 0
        mock.taken_at = datetime(2023, 1, 1, tzinfo=timezone.utc)
        mock.resources = None
        mock.user = None
        return mock


class TestCollectionReaderAdapter:
    """Test the collection reader adapter mappings."""

    def test_list_collections(self):
        """Verify collections() maps to CollectionSummary list."""
        # Create mock client
        mock_client = Mock()
        mock_collections = [
            self._create_mock_collection(pk=1, name="Favorites", media_count=5),
            self._create_mock_collection(pk=2, name="Inspiration", media_count=12),
        ]
        mock_client.collections.return_value = mock_collections

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCollectionReaderAdapter(mock_repo)
        results = adapter.list_collections("acc-123")

        assert len(results) == 2
        assert all(isinstance(r, CollectionSummary) for r in results)
        assert results[0].pk == 1
        assert results[0].name == "Favorites"
        assert results[1].media_count == 12
        mock_client.collections.assert_called_once()

    def test_get_collection_pk_by_name(self):
        """Verify collection_pk_by_name lookup."""
        # Create mock client
        mock_client = Mock()
        mock_client.collection_pk_by_name.return_value = 999

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCollectionReaderAdapter(mock_repo)
        result = adapter.get_collection_pk_by_name("acc-123", "Favorites")

        assert result == 999
        mock_client.collection_pk_by_name.assert_called_once_with("Favorites")

    def test_get_collection_pk_by_name_not_found(self):
        """Verify error when collection not found."""
        # Create mock client
        mock_client = Mock()
        mock_client.collection_pk_by_name.return_value = None

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCollectionReaderAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found"):
            adapter.get_collection_pk_by_name("acc-123", "NonExistent")

    def test_get_collection_posts(self):
        """Verify collection_medias returns MediaSummary list."""
        # Create mock client
        mock_client = Mock()
        mock_media = [
            self._create_mock_media(pk=100, caption_text="Saved 1"),
            self._create_mock_media(pk=101, caption_text="Saved 2"),
        ]
        mock_client.collection_medias.return_value = mock_media

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCollectionReaderAdapter(mock_repo)
        results = adapter.get_collection_posts("acc-123", 999, amount=10)

        assert len(results) == 2
        assert all(isinstance(r, MediaSummary) for r in results)
        assert results[0].pk == 100
        mock_client.collection_medias.assert_called_once()

    def test_get_collection_posts_with_pagination(self):
        """Verify collection pagination via last_media_pk."""
        # Create mock client
        mock_client = Mock()
        mock_media = [self._create_mock_media(pk=200, caption_text="Next page")]
        mock_client.collection_medias.return_value = mock_media

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter with pagination
        adapter = InstagramCollectionReaderAdapter(mock_repo)
        results = adapter.get_collection_posts("acc-123", 999, amount=21, last_media_pk=100)

        assert len(results) == 1
        # Verify last_media_pk was passed
        call_args = mock_client.collection_medias.call_args
        assert call_args.kwargs.get("last_media_pk") == 100

    def test_get_collection_posts_pagination_zero_start(self):
        """Verify pagination with last_media_pk=0 starts from beginning."""
        # Create mock client
        mock_client = Mock()
        mock_media = [self._create_mock_media(pk=1)]
        mock_client.collection_medias.return_value = mock_media

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter with last_media_pk=0 (start)
        adapter = InstagramCollectionReaderAdapter(mock_repo)
        results = adapter.get_collection_posts("acc-123", 999, last_media_pk=0)

        # Should pass None to indicate no pagination
        call_args = mock_client.collection_medias.call_args
        assert call_args.kwargs.get("last_media_pk") is None

    def test_missing_client_error(self):
        """Verify proper error when client not found."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramCollectionReaderAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.list_collections("acc-123")

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_collection_pk_by_name("acc-123", "name")

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_collection_posts("acc-123", 999)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.list_liked_medias("acc-123")

    def test_list_liked_medias(self):
        """Verify liked_medias returns MediaSummary list with exact kwargs."""
        mock_client = Mock()
        mock_media = [
            self._create_mock_media(pk=300, caption_text="Liked 1"),
            self._create_mock_media(pk=301, caption_text="Liked 2"),
        ]
        mock_client.liked_medias.return_value = mock_media

        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        adapter = InstagramCollectionReaderAdapter(mock_repo)
        results = adapter.list_liked_medias("acc-123", amount=10)

        assert len(results) == 2
        assert all(isinstance(r, MediaSummary) for r in results)
        assert results[0].pk == 300
        # Verify exact vendor method name + kwargs per instagrapi docs
        mock_client.liked_medias.assert_called_once_with(amount=10, last_media_pk=0)

    def test_list_liked_medias_empty(self):
        """Verify empty-list path returns empty MediaSummary list."""
        mock_client = Mock()
        mock_client.liked_medias.return_value = []

        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        adapter = InstagramCollectionReaderAdapter(mock_repo)
        results = adapter.list_liked_medias("acc-123")

        assert results == []
        mock_client.liked_medias.assert_called_once_with(amount=21, last_media_pk=0)

    def test_list_liked_medias_with_pagination(self):
        """Verify liked_medias forwards last_media_pk cursor."""
        mock_client = Mock()
        mock_client.liked_medias.return_value = [self._create_mock_media(pk=400)]

        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        adapter = InstagramCollectionReaderAdapter(mock_repo)
        results = adapter.list_liked_medias("acc-123", amount=21, last_media_pk=250)

        assert len(results) == 1
        mock_client.liked_medias.assert_called_once_with(amount=21, last_media_pk=250)

    @staticmethod
    def _create_mock_collection(pk=1, name="Test", media_count=0):
        """Create a mock Collection object."""
        mock = Mock()
        mock.pk = pk
        mock.name = name
        mock.media_count = media_count
        return mock

    @staticmethod
    def _create_mock_media(pk=1, caption_text=""):
        """Create a mock Media object."""
        mock = Mock()
        mock.pk = pk
        mock.id = f"{pk}_1"
        mock.code = f"CODE{pk}"
        mock.media_type = 1
        mock.product_type = "feed"
        mock.caption_text = caption_text
        mock.like_count = 0
        mock.comment_count = 0
        mock.taken_at = datetime(2023, 1, 1, tzinfo=timezone.utc)
        mock.resources = None
        mock.user = None
        return mock


class TestDiscoveryDTOs:
    """Test the discovery DTO properties."""

    def test_location_summary_frozen(self):
        """Verify LocationSummary is immutable."""
        location = LocationSummary(pk=1, name="Test")
        with pytest.raises(AttributeError):
            location.name = "Different"

    def test_hashtag_summary_frozen(self):
        """Verify HashtagSummary is immutable."""
        hashtag = HashtagSummary(id=1, name="test")
        with pytest.raises(AttributeError):
            hashtag.name = "different"

    def test_collection_summary_frozen(self):
        """Verify CollectionSummary is immutable."""
        collection = CollectionSummary(pk=1, name="Test")
        with pytest.raises(AttributeError):
            collection.pk = 2

    def test_location_summary_defaults(self):
        """Verify LocationSummary has sensible defaults."""
        location = LocationSummary(pk=1, name="Test")
        assert location.address is None
        assert location.city is None
        assert location.lat is None
        assert location.lng is None
        assert location.external_id is None

    def test_hashtag_summary_defaults(self):
        """Verify HashtagSummary has sensible defaults."""
        hashtag = HashtagSummary(id=1, name="test")
        assert hashtag.media_count is None
        assert hashtag.profile_pic_url is None

    def test_collection_summary_defaults(self):
        """Verify CollectionSummary has sensible defaults."""
        collection = CollectionSummary(pk=1, name="Test")
        assert collection.media_count is None


class TestDiscoveryContractProofing:
    """Contract tests proving vendor types never leak into application code."""

    def test_discovery_returns_only_dtos_not_vendor_types(self):
        """Verify discovery reader never returns vendor Location/Hashtag objects."""
        # Create mock client
        mock_client = Mock()
        mock_location = TestDiscoveryReaderAdapter._create_mock_location(pk=1, name="Test")
        mock_client.location_info.return_value = mock_location

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDiscoveryReaderAdapter(mock_repo)
        result = adapter.get_location("acc-123", 1)

        # Verify result is only DTO, never raw vendor
        assert isinstance(result, LocationSummary)
        assert not hasattr(result, "search_surface")  # vendor field

    def test_media_results_use_shared_dto_not_vendor_types(self):
        """Verify location/hashtag media results use MediaSummary, not vendor Media."""
        # Create mock client
        mock_client = Mock()
        mock_media = TestDiscoveryReaderAdapter._create_mock_media(pk=1)
        mock_client.location_medias_top.return_value = [mock_media]

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDiscoveryReaderAdapter(mock_repo)
        results = adapter.get_location_top_posts("acc-123", 1)

        # Verify media is MediaSummary DTO, not raw vendor Media
        assert len(results) == 1
        assert isinstance(results[0], MediaSummary)
        assert not hasattr(results[0], "story_items")  # vendor field

    def test_collection_returns_only_dtos_not_vendor_types(self):
        """Verify collection reader never returns vendor Collection objects."""
        # Create mock client
        mock_client = Mock()
        mock_collection = TestCollectionReaderAdapter._create_mock_collection(
            pk=1, name="Test"
        )
        mock_client.collections.return_value = [mock_collection]

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCollectionReaderAdapter(mock_repo)
        results = adapter.list_collections("acc-123")

        # Verify result is only DTO, never raw vendor
        assert len(results) == 1
        assert isinstance(results[0], CollectionSummary)
        assert not hasattr(results[0], "cover_media_pk")  # vendor field
