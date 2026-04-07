"""Use-case tests for HashtagUseCases.

Tests the application orchestration layer using port doubles (stubs/fakes).
No instagrapi imports — all vendor types stay behind the port boundary.
Covers:
  - Preconditions: account not found, account not authenticated
  - Hashtag name normalization: '#tag' vs 'tag', whitespace, empty
  - Amount clamping: below min, above max, default
  - Happy-path delegation to port double
  - DTO boundary: only app-owned types returned
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.application.dto.instagram_discovery_dto import HashtagSummary
from app.application.dto.instagram_media_dto import MediaSummary
from app.application.use_cases.hashtag import HashtagUseCases


# ---------------------------------------------------------------------------
# Helpers / Stubs
# ---------------------------------------------------------------------------

def _make_hashtag(name: str = "python", media_count: int = 1000) -> HashtagSummary:
    return HashtagSummary(id=1, name=name, media_count=media_count)


def _make_media(pk: int = 1) -> MediaSummary:
    return MediaSummary(
        pk=pk,
        media_id=f"{pk}_0",
        code="ABC",
        media_type=1,
        product_type="feed",
        taken_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _build_use_cases(
    *,
    account_exists: bool = True,
    client_exists: bool = True,
    reader: Mock | None = None,
) -> tuple[HashtagUseCases, Mock]:
    account_repo = Mock()
    account_repo.get.return_value = {"username": "testuser"} if account_exists else None

    client_repo = Mock()
    client_repo.exists.return_value = client_exists

    if reader is None:
        reader = Mock()

    uc = HashtagUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        discovery_reader=reader,
    )
    return uc, reader


# ---------------------------------------------------------------------------
# Precondition: account not found
# ---------------------------------------------------------------------------

class TestAccountPreconditions:
    def test_get_hashtag_raises_if_account_missing(self):
        uc, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.get_hashtag("no-such", "python")

    def test_get_hashtag_top_posts_raises_if_account_missing(self):
        uc, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.get_hashtag_top_posts("no-such", "python")

    def test_get_hashtag_recent_posts_raises_if_account_missing(self):
        uc, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.get_hashtag_recent_posts("no-such", "python")


# ---------------------------------------------------------------------------
# Precondition: account not authenticated
# ---------------------------------------------------------------------------

class TestAuthPreconditions:
    def test_get_hashtag_raises_if_not_authenticated(self):
        uc, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.get_hashtag("acc-1", "python")

    def test_get_hashtag_top_posts_raises_if_not_authenticated(self):
        uc, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.get_hashtag_top_posts("acc-1", "python")

    def test_get_hashtag_recent_posts_raises_if_not_authenticated(self):
        uc, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.get_hashtag_recent_posts("acc-1", "python")


# ---------------------------------------------------------------------------
# Hashtag name normalization
# ---------------------------------------------------------------------------

class TestHashtagNormalization:
    """Verify the use case strips # and whitespace before calling the port."""

    def test_get_hashtag_strips_hash_prefix(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag.return_value = _make_hashtag()

        uc.get_hashtag("acc-1", "#python")

        reader.get_hashtag.assert_called_once_with("acc-1", "python")

    def test_get_hashtag_strips_whitespace(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag.return_value = _make_hashtag()

        uc.get_hashtag("acc-1", "  python  ")

        reader.get_hashtag.assert_called_once_with("acc-1", "python")

    def test_get_hashtag_strips_hash_and_whitespace(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag.return_value = _make_hashtag()

        uc.get_hashtag("acc-1", "  #python  ")

        reader.get_hashtag.assert_called_once_with("acc-1", "python")

    def test_get_hashtag_passes_clean_name_unchanged(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag.return_value = _make_hashtag()

        uc.get_hashtag("acc-1", "python")

        reader.get_hashtag.assert_called_once_with("acc-1", "python")

    def test_get_hashtag_rejects_empty_name(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="empty"):
            uc.get_hashtag("acc-1", "")

    def test_get_hashtag_rejects_hash_only(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="empty"):
            uc.get_hashtag("acc-1", "#")

    def test_get_hashtag_rejects_whitespace_only(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="empty"):
            uc.get_hashtag("acc-1", "   ")

    def test_get_hashtag_top_posts_normalizes_name(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag_top_posts.return_value = []

        uc.get_hashtag_top_posts("acc-1", "#trending")

        reader.get_hashtag_top_posts.assert_called_once_with("acc-1", "trending", 12)

    def test_get_hashtag_recent_posts_normalizes_name(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag_recent_posts.return_value = []

        uc.get_hashtag_recent_posts("acc-1", "#trending")

        reader.get_hashtag_recent_posts.assert_called_once_with("acc-1", "trending", 12)


# ---------------------------------------------------------------------------
# Amount clamping
# ---------------------------------------------------------------------------

class TestAmountClamping:
    def test_top_posts_clamps_amount_to_min(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag_top_posts.return_value = []

        uc.get_hashtag_top_posts("acc-1", "python", amount=0)

        reader.get_hashtag_top_posts.assert_called_once_with("acc-1", "python", 1)

    def test_top_posts_clamps_amount_to_max(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag_top_posts.return_value = []

        uc.get_hashtag_top_posts("acc-1", "python", amount=9999)

        reader.get_hashtag_top_posts.assert_called_once_with("acc-1", "python", 200)

    def test_top_posts_passes_valid_amount_unchanged(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag_top_posts.return_value = []

        uc.get_hashtag_top_posts("acc-1", "python", amount=50)

        reader.get_hashtag_top_posts.assert_called_once_with("acc-1", "python", 50)

    def test_top_posts_default_amount_is_12(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag_top_posts.return_value = []

        uc.get_hashtag_top_posts("acc-1", "python")

        reader.get_hashtag_top_posts.assert_called_once_with("acc-1", "python", 12)

    def test_recent_posts_clamps_amount_to_min(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag_recent_posts.return_value = []

        uc.get_hashtag_recent_posts("acc-1", "python", amount=-5)

        reader.get_hashtag_recent_posts.assert_called_once_with("acc-1", "python", 1)

    def test_recent_posts_clamps_amount_to_max(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag_recent_posts.return_value = []

        uc.get_hashtag_recent_posts("acc-1", "python", amount=500)

        reader.get_hashtag_recent_posts.assert_called_once_with("acc-1", "python", 200)

    def test_recent_posts_default_amount_is_12(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag_recent_posts.return_value = []

        uc.get_hashtag_recent_posts("acc-1", "python")

        reader.get_hashtag_recent_posts.assert_called_once_with("acc-1", "python", 12)


# ---------------------------------------------------------------------------
# Happy-path delegation
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_get_hashtag_returns_dto_from_reader(self):
        uc, reader = _build_use_cases()
        expected = _make_hashtag("python", 50000)
        reader.get_hashtag.return_value = expected

        result = uc.get_hashtag("acc-1", "python")

        assert result is expected
        reader.get_hashtag.assert_called_once_with("acc-1", "python")

    def test_get_hashtag_top_posts_returns_list(self):
        uc, reader = _build_use_cases()
        expected = [_make_media(1), _make_media(2)]
        reader.get_hashtag_top_posts.return_value = expected

        result = uc.get_hashtag_top_posts("acc-1", "python", amount=2)

        assert result is expected

    def test_get_hashtag_recent_posts_returns_list(self):
        uc, reader = _build_use_cases()
        expected = [_make_media(10)]
        reader.get_hashtag_recent_posts.return_value = expected

        result = uc.get_hashtag_recent_posts("acc-1", "python")

        assert result is expected

    def test_reader_not_called_when_precondition_fails(self):
        uc, reader = _build_use_cases(account_exists=False)

        with pytest.raises(ValueError):
            uc.get_hashtag("acc-1", "python")

        reader.get_hashtag.assert_not_called()

    def test_reader_not_called_when_name_empty(self):
        uc, reader = _build_use_cases()

        with pytest.raises(ValueError):
            uc.get_hashtag("acc-1", "#")

        reader.get_hashtag.assert_not_called()


# ---------------------------------------------------------------------------
# DTO boundary: no vendor types leak through the use case
# ---------------------------------------------------------------------------

class TestDTOBoundary:
    def test_get_hashtag_result_is_hashtag_summary(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag.return_value = _make_hashtag()

        result = uc.get_hashtag("acc-1", "python")

        assert isinstance(result, HashtagSummary)

    def test_get_hashtag_top_posts_items_are_media_summary(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag_top_posts.return_value = [_make_media(i) for i in range(3)]

        results = uc.get_hashtag_top_posts("acc-1", "python")

        assert all(isinstance(r, MediaSummary) for r in results)

    def test_get_hashtag_recent_posts_items_are_media_summary(self):
        uc, reader = _build_use_cases()
        reader.get_hashtag_recent_posts.return_value = [_make_media(i) for i in range(2)]

        results = uc.get_hashtag_recent_posts("acc-1", "python")

        assert all(isinstance(r, MediaSummary) for r in results)

    def test_location_methods_not_exposed(self):
        """Verify HashtagUseCases does not expose location methods."""
        uc, _ = _build_use_cases()
        assert not hasattr(uc, "get_location")
        assert not hasattr(uc, "search_locations")
        assert not hasattr(uc, "get_location_top_posts")
        assert not hasattr(uc, "get_location_recent_posts")
