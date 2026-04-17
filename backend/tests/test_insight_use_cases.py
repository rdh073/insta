"""Use-case tests for InsightUseCases.

Tests the application orchestration layer using port doubles (stubs/fakes).
No instagrapi imports — all vendor types stay behind the port boundary.
Covers:
  - Preconditions: account not found, account not authenticated
  - media_pk validation (positive integer)
  - Filter normalization: post_type, time_frame, ordering
    - Case insensitivity (lowercase accepted)
    - Whitespace stripping
    - Invalid values rejected with helpful message
  - count validation (non-negative integer)
  - Default filter values
  - Happy-path delegation to port double
  - DTO boundary: only app-owned MediaInsightSummary returned
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.application.dto.instagram_analytics_dto import (
    AccountInsightSummary,
    MediaInsightSummary,
)
from app.application.use_cases.insight import InsightUseCases


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_insight(media_pk: int = 1) -> MediaInsightSummary:
    return MediaInsightSummary(
        media_pk=media_pk,
        reach_count=100,
        impression_count=200,
    )


def _build_use_cases(
    *,
    account_exists: bool = True,
    client_exists: bool = True,
    reader: Mock | None = None,
) -> tuple[InsightUseCases, Mock]:
    account_repo = Mock()
    account_repo.get.return_value = {"username": "testuser"} if account_exists else None

    client_repo = Mock()
    client_repo.exists.return_value = client_exists

    if reader is None:
        reader = Mock()

    uc = InsightUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        insight_reader=reader,
    )
    return uc, reader


# ---------------------------------------------------------------------------
# Preconditions: account not found
# ---------------------------------------------------------------------------

class TestAccountPreconditions:
    def test_get_media_insight_raises_if_account_missing(self):
        uc, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.get_media_insight("no-such", 1)

    def test_list_media_insights_raises_if_account_missing(self):
        uc, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.list_media_insights("no-such")

    def test_get_account_insight_raises_if_account_missing(self):
        uc, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.get_account_insight("no-such")

    def test_get_account_insight_raises_if_not_authenticated(self):
        uc, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.get_account_insight("acc-1")

    def test_get_account_insight_delegates_to_port(self):
        uc, reader = _build_use_cases()
        expected = AccountInsightSummary(followers_count=2500, reach_last_7_days=9000)
        reader.get_account_insight.return_value = expected

        result = uc.get_account_insight("acc-1")

        assert result is expected
        reader.get_account_insight.assert_called_once_with("acc-1")

    def test_get_account_insight_does_not_call_port_when_missing_account(self):
        uc, reader = _build_use_cases(account_exists=False)

        with pytest.raises(ValueError):
            uc.get_account_insight("acc-1")

        reader.get_account_insight.assert_not_called()


# ---------------------------------------------------------------------------
# Preconditions: account not authenticated
# ---------------------------------------------------------------------------

class TestAuthPreconditions:
    def test_get_media_insight_raises_if_not_authenticated(self):
        uc, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.get_media_insight("acc-1", 1)

    def test_list_media_insights_raises_if_not_authenticated(self):
        uc, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.list_media_insights("acc-1")


# ---------------------------------------------------------------------------
# media_pk validation
# ---------------------------------------------------------------------------

class TestMediaPkValidation:
    def test_rejects_zero(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_media_insight("acc-1", 0)

    def test_rejects_negative(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_media_insight("acc-1", -1)

    def test_rejects_non_int(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_media_insight("acc-1", "abc")  # type: ignore[arg-type]

    def test_accepts_valid_pk(self):
        uc, reader = _build_use_cases()
        reader.get_media_insight.return_value = _make_insight(42)

        uc.get_media_insight("acc-1", 42)

        reader.get_media_insight.assert_called_once_with("acc-1", 42)


# ---------------------------------------------------------------------------
# Filter normalization: post_type
# ---------------------------------------------------------------------------

class TestPostTypeNormalization:
    def test_accepts_uppercase(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", post_type="ALL")

        reader.list_media_insights.assert_called_once()
        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["post_type"] == "ALL"

    def test_accepts_vendor_post_type(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", post_type="SHOPPING")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["post_type"] == "SHOPPING"

    def test_accepts_lowercase_and_normalizes(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", post_type="photo")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["post_type"] == "IMAGE"

    def test_accepts_mixed_case(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", post_type="Video")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["post_type"] == "VIDEO"

    def test_strips_whitespace(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", post_type="  carousel  ")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["post_type"] == "CAROUSEL_V2"

    def test_rejects_invalid_post_type(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="post_type"):
            uc.list_media_insights("acc-1", post_type="REEL")

    def test_default_post_type_is_all(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["post_type"] == "ALL"


# ---------------------------------------------------------------------------
# Filter normalization: time_frame
# ---------------------------------------------------------------------------

class TestTimeFrameNormalization:
    def test_accepts_valid_time_frame(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", time_frame="ONE_YEAR")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["time_frame"] == "ONE_YEAR"

    def test_normalizes_lowercase(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", time_frame="month")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["time_frame"] == "ONE_MONTH"

    def test_maps_week_alias(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", time_frame="week")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["time_frame"] == "ONE_WEEK"

    def test_rejects_invalid_time_frame(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="time_frame"):
            uc.list_media_insights("acc-1", time_frame="DAILY")

    def test_default_time_frame_is_two_years(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["time_frame"] == "TWO_YEARS"


# ---------------------------------------------------------------------------
# Filter normalization: ordering
# ---------------------------------------------------------------------------

class TestOrderingNormalization:
    def test_accepts_valid_ordering(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", ordering="IMPRESSION_COUNT")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["ordering"] == "IMPRESSION_COUNT"

    def test_normalizes_lowercase(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", ordering="like_count")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["ordering"] == "LIKE_COUNT"

    def test_maps_impressions_alias(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", ordering="impressions")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["ordering"] == "IMPRESSION_COUNT"

    def test_maps_engagement_alias_by_policy(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", ordering="ENGAGEMENT")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["ordering"] == "LIKE_COUNT"

    def test_accepts_new_vendor_ordering(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", ordering="FOLLOW")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["ordering"] == "FOLLOW"

    def test_rejects_invalid_ordering(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="ordering"):
            uc.list_media_insights("acc-1", ordering="VIEWS")

    def test_default_ordering_is_reach_count(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["ordering"] == "REACH_COUNT"


# ---------------------------------------------------------------------------
# count validation
# ---------------------------------------------------------------------------

class TestCountValidation:
    def test_accepts_zero(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", count=0)

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["count"] == 0

    def test_accepts_positive(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1", count=10)

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["count"] == 10

    def test_rejects_negative(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="non-negative"):
            uc.list_media_insights("acc-1", count=-1)

    def test_rejects_non_int(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="non-negative"):
            uc.list_media_insights("acc-1", count="all")  # type: ignore[arg-type]

    def test_default_count_is_zero(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = []

        uc.list_media_insights("acc-1")

        kwargs = reader.list_media_insights.call_args[1]
        assert kwargs["count"] == 0


# ---------------------------------------------------------------------------
# Happy-path delegation
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_get_media_insight_delegates_to_port(self):
        uc, reader = _build_use_cases()
        expected = _make_insight(99)
        reader.get_media_insight.return_value = expected

        result = uc.get_media_insight("acc-1", 99)

        assert result is expected

    def test_list_media_insights_delegates_to_port(self):
        uc, reader = _build_use_cases()
        expected = [_make_insight(1), _make_insight(2)]
        reader.list_media_insights.return_value = expected

        result = uc.list_media_insights("acc-1", post_type="photo", count=5)

        assert result is expected

    def test_port_not_called_when_precondition_fails(self):
        uc, reader = _build_use_cases(account_exists=False)

        with pytest.raises(ValueError):
            uc.get_media_insight("acc-1", 1)

        reader.get_media_insight.assert_not_called()

    def test_port_not_called_when_filter_invalid(self):
        uc, reader = _build_use_cases()

        with pytest.raises(ValueError):
            uc.list_media_insights("acc-1", post_type="INVALID")

        reader.list_media_insights.assert_not_called()

    def test_port_not_called_when_ordering_invalid(self):
        uc, reader = _build_use_cases()

        with pytest.raises(ValueError):
            uc.list_media_insights("acc-1", ordering="UNSUPPORTED")

        reader.list_media_insights.assert_not_called()


# ---------------------------------------------------------------------------
# DTO boundary: only app-owned types returned
# ---------------------------------------------------------------------------

class TestDTOBoundary:
    def test_get_media_insight_result_is_media_insight_summary(self):
        uc, reader = _build_use_cases()
        reader.get_media_insight.return_value = _make_insight()

        result = uc.get_media_insight("acc-1", 1)

        assert isinstance(result, MediaInsightSummary)

    def test_list_media_insights_items_are_media_insight_summary(self):
        uc, reader = _build_use_cases()
        reader.list_media_insights.return_value = [_make_insight(i) for i in range(3)]

        results = uc.list_media_insights("acc-1")

        assert all(isinstance(r, MediaInsightSummary) for r in results)

    def test_insight_summary_has_no_raw_dict_leak(self):
        """extra_metrics must be a dict, not a raw vendor payload."""
        uc, reader = _build_use_cases()
        insight = MediaInsightSummary(
            media_pk=1,
            reach_count=500,
            extra_metrics={"engagement_rate": 0.05},
        )
        reader.get_media_insight.return_value = insight

        result = uc.get_media_insight("acc-1", 1)

        assert isinstance(result.extra_metrics, dict)
        # Must not contain raw vendor objects
        for v in result.extra_metrics.values():
            assert not hasattr(v, "__dict__") or isinstance(v, (int, float, str, bool, type(None)))
