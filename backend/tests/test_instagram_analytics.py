"""Tests for Instagram analytics (insights and tracks) readers.

Verifies that instagrapi insight dicts and Track objects map correctly
to stable application DTOs while ensuring vendor types never leak.
"""

import pytest
from unittest.mock import Mock

from app.application.dto.instagram_analytics_dto import (
    MediaInsightSummary,
    TrackSummary,
    TrackDetail,
    TrackReference,
)
from app.adapters.instagram.insight_reader import (
    InstagramInsightReaderAdapter,
)
from app.adapters.instagram.track_catalog import (
    InstagramTrackCatalogAdapter,
)
from app.adapters.instagram.exception_catalog import SPEC_CLIENT_UNKNOWN_ERROR


def _create_mock_track(id=None, title=None, artist=None, uri=None, display_artist=None):
    """Create a mock Track object."""
    mock = Mock()
    mock.id = id or 1
    mock.canonical_id = id or 1
    mock.title = title or "Test Track"
    mock.name = title or "Test Track"
    mock.artist_name = artist or "Test Artist"
    mock.duration_in_ms = 180000
    mock.uri = uri
    mock.display_artist = display_artist or artist
    return mock


class TestInsightReaderAdapter:
    """Test the insight reader adapter mappings."""

    def test_get_media_insight_success(self):
        """Verify insights_media() maps to MediaInsightSummary."""
        # Create mock client
        mock_client = Mock()
        mock_insight_dict = {
            "reach": 1500,
            "impressions": 2500,
            "likes": 150,
            "comments": 25,
            "shares": 10,
            "saves": 5,
            "video_views": None,
            "profile_views": 80,
        }
        mock_client.insights_media.return_value = mock_insight_dict

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramInsightReaderAdapter(mock_repo)
        result = adapter.get_media_insight("acc-123", 999)

        assert isinstance(result, MediaInsightSummary)
        assert result.media_pk == 999
        assert result.reach_count == 1500
        assert result.impression_count == 2500
        assert result.like_count == 150
        assert result.comment_count == 25
        assert result.share_count == 10
        assert result.save_count == 5
        assert result.video_view_count is None
        assert result.profile_view_count == 80
        mock_client.insights_media.assert_called_once_with(999)

    def test_get_media_insight_with_extra_metrics(self):
        """Verify unknown metrics are captured in extra_metrics."""
        # Create mock client with additional vendor metrics
        mock_client = Mock()
        mock_insight_dict = {
            "reach": 1000,
            "impressions": 2000,
            "likes": 100,
            "custom_vendor_metric_1": 42,
            "custom_vendor_metric_2": "some_value",
            "engagement_rate": 5.5,
        }
        mock_client.insights_media.return_value = mock_insight_dict

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramInsightReaderAdapter(mock_repo)
        result = adapter.get_media_insight("acc-123", 555)

        assert result.reach_count == 1000
        assert result.impression_count == 2000
        assert result.like_count == 100
        # Unknown metrics in extra_metrics
        assert result.extra_metrics["custom_vendor_metric_1"] == 42
        assert result.extra_metrics["custom_vendor_metric_2"] == "some_value"
        assert result.extra_metrics["engagement_rate"] == 5.5

    def test_list_media_insights_from_top_posts_edges_payload(self):
        """Verify edge/node GraphQL payload maps to MediaInsightSummary."""
        # Create mock client
        mock_client = Mock()
        mock_insights = {
            "top_posts": {
                "edges": [
                    {
                        "node": {
                            "id": "111_42",
                            "reach_count": 1000,
                            "impression_count": 1500,
                            "like_count": 100,
                            "comment_count": 10,
                            "save_count": 5,
                            "engagement_rate": 0.125,
                        }
                    },
                    {
                        "node": {
                            "media_pk": 222,
                            "reach": 2000,
                            "impressions": 3000,
                            "likes": 200,
                            "shares": 15,
                            "profile_views": 80,
                        }
                    },
                    {
                        "node": {
                            "media": {"pk": "333"},
                            "metrics": {
                                "reach": 3000,
                                "impressions": 4500,
                                "likes": 300,
                                "video_view_count": 999,
                                "vendor_metric": "alpha",
                            },
                        }
                    },
                ]
            }
        }
        mock_client.insights_media_feed_all.return_value = mock_insights

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramInsightReaderAdapter(mock_repo)
        results = adapter.list_media_insights("acc-123")

        assert len(results) == 3
        assert all(isinstance(r, MediaInsightSummary) for r in results)
        assert results[0].media_pk == 111
        assert results[0].reach_count == 1000
        assert results[0].comment_count == 10
        assert results[0].save_count == 5
        assert results[0].extra_metrics["engagement_rate"] == 0.125
        assert results[1].media_pk == 222
        assert results[1].reach_count == 2000
        assert results[1].share_count == 15
        assert results[1].profile_view_count == 80
        assert results[2].media_pk == 333
        assert results[2].reach_count == 3000
        assert results[2].video_view_count == 999
        assert results[2].extra_metrics["vendor_metric"] == "alpha"
        mock_client.insights_media_feed_all.assert_called_once_with(
            post_type="ALL",
            time_frame="TWO_YEARS",
            data_ordering="REACH_COUNT",
            count=0,
        )

    def test_list_media_insights_edge_list_skips_invalid_nodes(self):
        """Verify malformed edge entries are ignored without failing the call."""
        mock_client = Mock()
        mock_client.insights_media_feed_all.return_value = [
            {"node": {"id": "444_99", "reach": 4000, "likes": 400}},
            {"node": {"pk": 555, "impressions": 6000, "likes": 500}},
            {"node": {"id": "not-a-media-id", "reach": 999}},
            {"node": {}},
            {"unexpected": "shape"},
            None,
        ]

        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        adapter = InstagramInsightReaderAdapter(mock_repo)
        results = adapter.list_media_insights("acc-123")

        assert [r.media_pk for r in results] == [444, 555]
        assert results[0].reach_count == 4000
        assert results[1].impression_count == 6000

    def test_list_media_insights_empty_top_posts_edges(self):
        """Verify empty edge lists return an empty result set."""
        mock_client = Mock()
        mock_client.insights_media_feed_all.return_value = {
            "top_posts": {"edges": []}
        }

        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        adapter = InstagramInsightReaderAdapter(mock_repo)
        results = adapter.list_media_insights("acc-123")

        assert results == []

    def test_list_media_insights_with_filters(self):
        """Verify filter parameters are passed to vendor method."""
        # Create mock client
        mock_client = Mock()
        mock_client.insights_media_feed_all.return_value = []

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter with custom filters
        adapter = InstagramInsightReaderAdapter(mock_repo)
        results = adapter.list_media_insights(
            "acc-123",
            post_type="VIDEO",
            time_frame="ONE_MONTH",
            ordering="IMPRESSION_COUNT",
            count=50,
        )

        # Verify parameters passed to vendor
        mock_client.insights_media_feed_all.assert_called_once_with(
            post_type="VIDEO",
            time_frame="ONE_MONTH",
            data_ordering="IMPRESSION_COUNT",
            count=50,
        )
        assert results == []

    def test_get_media_insight_missing_client(self):
        """Verify proper error when client not found."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramInsightReaderAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_media_insight("acc-123", 999)

    def test_list_media_insights_missing_client(self):
        """Verify proper error for list when client not found."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramInsightReaderAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.list_media_insights("acc-123")

    def test_get_media_insight_api_error(self):
        """Verify error handling when vendor API fails."""
        raw_msg = "API rate limited"
        # Create mock client that raises exception
        mock_client = Mock()
        mock_client.insights_media.side_effect = Exception(raw_msg)

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramInsightReaderAdapter(mock_repo)

        with pytest.raises(ValueError) as err:
            adapter.get_media_insight("acc-123", 999)
        assert str(err.value) == SPEC_CLIENT_UNKNOWN_ERROR.user_message
        assert raw_msg not in str(err.value)

    def test_list_media_insights_business_account_error_surface(self):
        """Verify list surfaces business-account failures via translated ValueError."""
        raw_msg = "Account is not business account"
        mock_client = Mock()
        mock_client.insights_media_feed_all.side_effect = Exception(raw_msg)

        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        adapter = InstagramInsightReaderAdapter(mock_repo)

        with pytest.raises(ValueError) as err:
            adapter.list_media_insights("acc-123")
        assert str(err.value) == SPEC_CLIENT_UNKNOWN_ERROR.user_message
        assert raw_msg not in str(err.value)

    def test_insight_summary_frozen(self):
        """Verify MediaInsightSummary is immutable."""
        insight = MediaInsightSummary(media_pk=1)
        with pytest.raises(AttributeError):
            insight.media_pk = 2

    def test_insight_summary_defaults(self):
        """Verify MediaInsightSummary has sensible defaults."""
        insight = MediaInsightSummary(media_pk=123)
        assert insight.reach_count is None
        assert insight.impression_count is None
        assert insight.like_count is None
        assert insight.extra_metrics == {}


class TestTrackCatalogAdapter:
    """Test the track catalog adapter."""

    def test_search_tracks_success(self):
        """Verify search_music() maps to TrackSummary list."""
        # Create mock client
        mock_client = Mock()
        mock_track1 = _create_mock_track(id=100, title="Song 1", artist="Artist A")
        mock_track2 = _create_mock_track(id=101, title="Song 2", artist="Artist B")
        mock_client.search_music.return_value = [mock_track1, mock_track2]

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramTrackCatalogAdapter(mock_repo)
        results = adapter.search_tracks("acc-123", "test query")

        assert len(results) == 2
        assert all(isinstance(r, TrackSummary) for r in results)
        assert results[0].title == "Song 1"
        assert results[0].artist_name == "Artist A"
        assert results[1].title == "Song 2"
        assert results[1].artist_name == "Artist B"
        mock_client.search_music.assert_called_once_with("test query")

    def test_search_tracks_with_limit(self):
        """Verify limit parameter is enforced in adapter."""
        # Create mock client
        mock_client = Mock()
        mock_client.search_music.return_value = [
            _create_mock_track(id=100, title="Song 1"),
            _create_mock_track(id=101, title="Song 2"),
            _create_mock_track(id=102, title="Song 3"),
        ]

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter with custom limit
        adapter = InstagramTrackCatalogAdapter(mock_repo)
        results = adapter.search_tracks("acc-123", "query", limit=2)

        mock_client.search_music.assert_called_once_with("query")
        assert len(results) == 2
        assert results[0].canonical_id == "100"
        assert results[1].canonical_id == "101"

    def test_search_tracks_vendor_query_only_signature_regression(self):
        """Regression: do not pass limit kwarg to query-only vendor method."""

        def search_music_query_only(query):
            # Would raise TypeError if adapter forwarded limit=...
            return [
                _create_mock_track(id=200, title="Strict Song 1"),
                _create_mock_track(id=201, title="Strict Song 2"),
            ]

        mock_client = Mock()
        mock_client.search_music.side_effect = search_music_query_only

        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        adapter = InstagramTrackCatalogAdapter(mock_repo)
        results = adapter.search_tracks("acc-123", "strict query", limit=1)

        mock_client.search_music.assert_called_once_with("strict query")
        assert mock_client.search_music.call_args.kwargs == {}
        assert len(results) == 1
        assert results[0].canonical_id == "200"

    def test_get_track_success(self):
        """Verify track_info_by_canonical_id() maps to TrackDetail."""
        # Create mock client
        mock_client = Mock()
        mock_track = _create_mock_track(
            id=100,
            title="Featured Song",
            artist="Pop Artist",
            uri="spotify:track:xyz",
            display_artist="Pop Artist (Official)",
        )
        mock_client.track_info_by_canonical_id.return_value = mock_track

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramTrackCatalogAdapter(mock_repo)
        result = adapter.get_track("acc-123", 100)

        assert isinstance(result, TrackDetail)
        assert result.summary.title == "Featured Song"
        assert result.summary.artist_name == "Pop Artist"
        assert result.uri == "spotify:track:xyz"
        assert result.display_artist == "Pop Artist (Official)"
        mock_client.track_info_by_canonical_id.assert_called_once_with(100)

    def test_get_track_with_string_canonical_id(self):
        """Verify canonical_id can be string or int."""
        # Create mock client
        mock_client = Mock()
        mock_track = _create_mock_track(id="canonical-string-id")
        mock_client.track_info_by_canonical_id.return_value = mock_track

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter with string canonical_id
        adapter = InstagramTrackCatalogAdapter(mock_repo)
        result = adapter.get_track("acc-123", "canonical-string-id")

        mock_client.track_info_by_canonical_id.assert_called_once_with(
            "canonical-string-id"
        )

    def test_get_track_missing_client(self):
        """Verify proper error when client not found."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramTrackCatalogAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_track("acc-123", 100)

    def test_search_tracks_missing_client(self):
        """Verify proper error for search when client not found."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramTrackCatalogAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.search_tracks("acc-123", "query")

    def test_search_tracks_api_error(self):
        """Verify error handling when vendor API fails."""
        raw_msg = "Network error"
        # Create mock client that raises exception
        mock_client = Mock()
        mock_client.search_music.side_effect = Exception(raw_msg)

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramTrackCatalogAdapter(mock_repo)

        with pytest.raises(ValueError) as err:
            adapter.search_tracks("acc-123", "query")
        assert str(err.value) == SPEC_CLIENT_UNKNOWN_ERROR.user_message
        assert raw_msg not in str(err.value)

    def test_get_track_not_found(self):
        """Verify error handling when track not found."""
        raw_msg = "Track not found"
        # Create mock client that raises exception
        mock_client = Mock()
        mock_client.track_info_by_canonical_id.side_effect = Exception(raw_msg)

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramTrackCatalogAdapter(mock_repo)

        with pytest.raises(ValueError) as err:
            adapter.get_track("acc-123", 999)
        assert str(err.value) == SPEC_CLIENT_UNKNOWN_ERROR.user_message
        assert raw_msg not in str(err.value)

    def test_track_summary_frozen(self):
        """Verify TrackSummary is immutable."""
        track = TrackSummary(canonical_id="100")
        with pytest.raises(AttributeError):
            track.canonical_id = "200"

    def test_track_detail_frozen(self):
        """Verify TrackDetail is immutable."""
        summary = TrackSummary(canonical_id="100")
        detail = TrackDetail(summary=summary)
        with pytest.raises(AttributeError):
            detail.summary = None

    def test_track_reference_frozen(self):
        """Verify TrackReference is immutable."""
        ref = TrackReference(canonical_id="100")
        with pytest.raises(AttributeError):
            ref.canonical_id = "200"

    def test_track_summary_defaults(self):
        """Verify TrackSummary has sensible defaults."""
        track = TrackSummary(canonical_id="100")
        assert track.title is None
        assert track.artist_name is None
        assert track.duration_in_ms is None

    def test_track_detail_defaults(self):
        """Verify TrackDetail has sensible defaults."""
        summary = TrackSummary(canonical_id="100")
        detail = TrackDetail(summary=summary)
        assert detail.uri is None
        assert detail.display_artist is None


class TestAnalyticsContractProofing:
    """Contract tests proving vendor types never leak into application code."""

    def test_insight_reader_returns_only_dtos(self):
        """Verify insight reader never returns raw vendor dicts."""
        # Create mock client
        mock_client = Mock()
        mock_insight_dict = {
            "reach": 1000,
            "impressions": 1500,
            "likes": 100,
        }
        mock_client.insights_media.return_value = mock_insight_dict

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramInsightReaderAdapter(mock_repo)
        result = adapter.get_media_insight("acc-123", 999)

        # Verify result is only DTO, never raw vendor dict
        assert isinstance(result, MediaInsightSummary)
        assert not isinstance(result, dict)
        assert type(result).__name__ == "MediaInsightSummary"

    def test_track_search_returns_only_dtos(self):
        """Verify track search never returns vendor Track objects."""
        # Create mock client
        mock_client = Mock()
        mock_track = _create_mock_track(id=100)
        mock_client.search_music.return_value = [mock_track]

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramTrackCatalogAdapter(mock_repo)
        results = adapter.search_tracks("acc-123", "query")

        # Verify result is only DTO, not vendor Track
        assert isinstance(results[0], TrackSummary)
        # Should not expose vendor Track fields
        assert not hasattr(results[0], "search_surface_id")

    def test_track_get_returns_only_dtos(self):
        """Verify track lookup never returns vendor Track objects."""
        # Create mock client
        mock_client = Mock()
        mock_track = _create_mock_track(id=100)
        mock_client.track_info_by_canonical_id.return_value = mock_track

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramTrackCatalogAdapter(mock_repo)
        result = adapter.get_track("acc-123", 100)

        # Verify result is only DTO, not vendor Track
        assert isinstance(result, TrackDetail)
        # Should not expose vendor Track fields
        assert not hasattr(result, "search_surface_id")

    def test_extra_metrics_preserves_variant_without_leaking(self):
        """Verify extra_metrics captures unknown metrics without leaking raw dicts."""
        # Create mock client with vendor-specific metrics
        mock_client = Mock()
        mock_insight_dict = {
            "reach": 1000,
            "impressions": 1500,
            "likes": 100,
            "vendor_specific_field_1": 42,
            "vendor_specific_field_2": "data",
        }
        mock_client.insights_media.return_value = mock_insight_dict

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramInsightReaderAdapter(mock_repo)
        result = adapter.get_media_insight("acc-123", 999)

        # Unknown metrics are captured in extra_metrics (dict)
        assert isinstance(result.extra_metrics, dict)
        assert result.extra_metrics["vendor_specific_field_1"] == 42
        # But the result itself is still a DTO, not a raw dict
        assert isinstance(result, MediaInsightSummary)

class TestTrackReferenceDTOUsage:
    """Tests verifying TrackReference is the right type for publishing workflows."""

    def test_track_reference_from_summary(self):
        """Verify TrackReference can be constructed from TrackSummary."""
        summary = TrackSummary(
            canonical_id="track-100",
            title="My Song",
            artist_name="My Artist",
        )

        # Convert to reference for publishing
        ref = TrackReference(
            canonical_id=summary.canonical_id,
            title=summary.title,
            artist_name=summary.artist_name,
        )

        assert ref.canonical_id == "track-100"
        assert ref.title == "My Song"
        assert ref.artist_name == "My Artist"

    def test_track_reference_immutable(self):
        """Verify TrackReference is frozen."""
        ref = TrackReference(canonical_id="track-100")
        with pytest.raises(AttributeError):
            ref.canonical_id = "track-200"
