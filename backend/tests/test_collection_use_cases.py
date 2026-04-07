"""Use-case tests for CollectionUseCases.

Tests the application orchestration layer using port doubles (stubs/fakes).
No instagrapi imports — all vendor types stay behind the port boundary.
Covers:
  - Preconditions: account not found, account not authenticated
  - Collection name normalization: empty, whitespace-only
  - Not-found contract: port raises ValueError on missing collection
  - Amount clamping and default
  - last_media_pk validation (pagination cursor)
  - collection_pk validation (positive integer)
  - Happy-path delegation to port double
  - DTO boundary: only app-owned types returned
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.application.dto.instagram_discovery_dto import CollectionSummary
from app.application.dto.instagram_media_dto import MediaSummary
from app.application.use_cases.collection import CollectionUseCases


# ---------------------------------------------------------------------------
# Helpers / Stubs
# ---------------------------------------------------------------------------

def _make_collection(pk: int = 1, name: str = "Saved") -> CollectionSummary:
    return CollectionSummary(pk=pk, name=name, media_count=5)


def _make_media(pk: int = 1) -> MediaSummary:
    return MediaSummary(
        pk=pk,
        media_id=f"{pk}_0",
        code="XYZ",
        media_type=1,
        product_type="feed",
        taken_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _build_use_cases(
    *,
    account_exists: bool = True,
    client_exists: bool = True,
    reader: Mock | None = None,
) -> tuple[CollectionUseCases, Mock]:
    account_repo = Mock()
    account_repo.get.return_value = {"username": "testuser"} if account_exists else None

    client_repo = Mock()
    client_repo.exists.return_value = client_exists

    if reader is None:
        reader = Mock()

    uc = CollectionUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        collection_reader=reader,
    )
    return uc, reader


# ---------------------------------------------------------------------------
# Precondition: account not found
# ---------------------------------------------------------------------------

class TestAccountPreconditions:
    def test_list_collections_raises_if_account_missing(self):
        uc, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.list_collections("no-such")

    def test_get_collection_pk_by_name_raises_if_account_missing(self):
        uc, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.get_collection_pk_by_name("no-such", "Saved")

    def test_get_collection_posts_raises_if_account_missing(self):
        uc, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.get_collection_posts("no-such", 1)


# ---------------------------------------------------------------------------
# Precondition: account not authenticated
# ---------------------------------------------------------------------------

class TestAuthPreconditions:
    def test_list_collections_raises_if_not_authenticated(self):
        uc, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.list_collections("acc-1")

    def test_get_collection_pk_by_name_raises_if_not_authenticated(self):
        uc, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.get_collection_pk_by_name("acc-1", "Saved")

    def test_get_collection_posts_raises_if_not_authenticated(self):
        uc, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.get_collection_posts("acc-1", 1)


# ---------------------------------------------------------------------------
# Collection name normalization
# ---------------------------------------------------------------------------

class TestCollectionNameNormalization:
    def test_get_collection_pk_strips_whitespace(self):
        uc, reader = _build_use_cases()
        reader.get_collection_pk_by_name.return_value = 42

        uc.get_collection_pk_by_name("acc-1", "  Saved  ")

        reader.get_collection_pk_by_name.assert_called_once_with("acc-1", "Saved")

    def test_get_collection_pk_passes_clean_name_unchanged(self):
        uc, reader = _build_use_cases()
        reader.get_collection_pk_by_name.return_value = 42

        uc.get_collection_pk_by_name("acc-1", "My Collection")

        reader.get_collection_pk_by_name.assert_called_once_with("acc-1", "My Collection")

    def test_get_collection_pk_rejects_empty_name(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="empty"):
            uc.get_collection_pk_by_name("acc-1", "")

    def test_get_collection_pk_rejects_whitespace_only(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="empty"):
            uc.get_collection_pk_by_name("acc-1", "   ")

    def test_get_collection_pk_reader_not_called_on_empty(self):
        uc, reader = _build_use_cases()
        with pytest.raises(ValueError):
            uc.get_collection_pk_by_name("acc-1", "")
        reader.get_collection_pk_by_name.assert_not_called()


# ---------------------------------------------------------------------------
# Not-found contract
# ---------------------------------------------------------------------------

class TestNotFoundContract:
    def test_get_collection_pk_by_name_propagates_not_found(self):
        """Port raises ValueError on not-found; use case must propagate it."""
        uc, reader = _build_use_cases()
        reader.get_collection_pk_by_name.side_effect = ValueError(
            "Collection 'Missing' not found"
        )

        with pytest.raises(ValueError, match="not found"):
            uc.get_collection_pk_by_name("acc-1", "Missing")

    def test_get_collection_posts_propagates_not_found(self):
        uc, reader = _build_use_cases()
        reader.get_collection_posts.side_effect = ValueError("Collection not found")

        with pytest.raises(ValueError, match="not found"):
            uc.get_collection_posts("acc-1", 999)


# ---------------------------------------------------------------------------
# collection_pk validation
# ---------------------------------------------------------------------------

class TestCollectionPkValidation:
    def test_get_collection_posts_rejects_zero_pk(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_collection_posts("acc-1", 0)

    def test_get_collection_posts_rejects_negative_pk(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_collection_posts("acc-1", -1)

    def test_get_collection_posts_rejects_string_pk(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_collection_posts("acc-1", "abc")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Amount clamping
# ---------------------------------------------------------------------------

class TestAmountClamping:
    def test_clamps_amount_to_min(self):
        uc, reader = _build_use_cases()
        reader.get_collection_posts.return_value = []

        uc.get_collection_posts("acc-1", 1, amount=0)

        reader.get_collection_posts.assert_called_once_with("acc-1", 1, 1, 0)

    def test_clamps_amount_to_max(self):
        uc, reader = _build_use_cases()
        reader.get_collection_posts.return_value = []

        uc.get_collection_posts("acc-1", 1, amount=9999)

        reader.get_collection_posts.assert_called_once_with("acc-1", 1, 200, 0)

    def test_passes_valid_amount_unchanged(self):
        uc, reader = _build_use_cases()
        reader.get_collection_posts.return_value = []

        uc.get_collection_posts("acc-1", 1, amount=50)

        reader.get_collection_posts.assert_called_once_with("acc-1", 1, 50, 0)

    def test_default_amount_is_21(self):
        uc, reader = _build_use_cases()
        reader.get_collection_posts.return_value = []

        uc.get_collection_posts("acc-1", 1)

        reader.get_collection_posts.assert_called_once_with("acc-1", 1, 21, 0)


# ---------------------------------------------------------------------------
# Pagination cursor (last_media_pk)
# ---------------------------------------------------------------------------

class TestPaginationCursor:
    def test_default_last_media_pk_is_zero(self):
        uc, reader = _build_use_cases()
        reader.get_collection_posts.return_value = []

        uc.get_collection_posts("acc-1", 1)

        _, _, _, last = reader.get_collection_posts.call_args[0]
        assert last == 0

    def test_passes_last_media_pk_to_port(self):
        uc, reader = _build_use_cases()
        reader.get_collection_posts.return_value = []

        uc.get_collection_posts("acc-1", 1, last_media_pk=500)

        reader.get_collection_posts.assert_called_once_with("acc-1", 1, 21, 500)

    def test_rejects_negative_last_media_pk(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="non-negative"):
            uc.get_collection_posts("acc-1", 1, last_media_pk=-1)


# ---------------------------------------------------------------------------
# Happy-path delegation
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_list_collections_returns_list_from_port(self):
        uc, reader = _build_use_cases()
        expected = [_make_collection(1, "Saved"), _make_collection(2, "Travel")]
        reader.list_collections.return_value = expected

        result = uc.list_collections("acc-1")

        assert result is expected
        reader.list_collections.assert_called_once_with("acc-1")

    def test_list_collections_returns_empty_list(self):
        uc, reader = _build_use_cases()
        reader.list_collections.return_value = []

        result = uc.list_collections("acc-1")

        assert result == []

    def test_get_collection_pk_by_name_returns_pk(self):
        uc, reader = _build_use_cases()
        reader.get_collection_pk_by_name.return_value = 42

        result = uc.get_collection_pk_by_name("acc-1", "Saved")

        assert result == 42

    def test_get_collection_posts_returns_media_list(self):
        uc, reader = _build_use_cases()
        expected = [_make_media(1), _make_media(2)]
        reader.get_collection_posts.return_value = expected

        result = uc.get_collection_posts("acc-1", 99)

        assert result is expected

    def test_reader_not_called_when_precondition_fails(self):
        uc, reader = _build_use_cases(account_exists=False)

        with pytest.raises(ValueError):
            uc.list_collections("acc-1")

        reader.list_collections.assert_not_called()


# ---------------------------------------------------------------------------
# DTO boundary: only app-owned types returned
# ---------------------------------------------------------------------------

class TestDTOBoundary:
    def test_list_collections_items_are_collection_summary(self):
        uc, reader = _build_use_cases()
        reader.list_collections.return_value = [_make_collection()]

        results = uc.list_collections("acc-1")

        assert all(isinstance(c, CollectionSummary) for c in results)

    def test_get_collection_pk_by_name_returns_int(self):
        uc, reader = _build_use_cases()
        reader.get_collection_pk_by_name.return_value = 99

        result = uc.get_collection_pk_by_name("acc-1", "Saved")

        assert isinstance(result, int)

    def test_get_collection_posts_items_are_media_summary(self):
        uc, reader = _build_use_cases()
        reader.get_collection_posts.return_value = [_make_media(i) for i in range(3)]

        results = uc.get_collection_posts("acc-1", 1)

        assert all(isinstance(r, MediaSummary) for r in results)
