"""Use-case tests for MediaUseCases.

Tests the application orchestration layer (preconditions + parameter normalization)
using port doubles (stubs/fakes) instead of real adapters.
No instagrapi imports here — all vendor types stay behind the port boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.application.dto.instagram_media_dto import (
    MediaOembedSummary,
    MediaSummary,
    ResourceSummary,
)
from app.application.use_cases.media import MediaUseCases


# ---------------------------------------------------------------------------
# Helpers / Stubs
# ---------------------------------------------------------------------------

def _make_media(pk: int = 1, code: str = "ABC", caption: str = "") -> MediaSummary:
    return MediaSummary(
        pk=pk,
        media_id=f"{pk}_0",
        code=code,
        media_type=1,
        product_type="feed",
        caption_text=caption,
        taken_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _make_oembed(media_id: str = "oembed-1") -> MediaOembedSummary:
    return MediaOembedSummary(
        media_id=media_id,
        author_name="testuser",
    )


def _build_use_cases(
    *,
    account_exists: bool = True,
    client_exists: bool = True,
    reader: Mock | None = None,
) -> tuple[MediaUseCases, Mock]:
    """Build MediaUseCases with stubbed repos and an optional reader mock."""
    account_repo = Mock()
    account_repo.get.return_value = {"username": "testuser"} if account_exists else None

    client_repo = Mock()
    client_repo.exists.return_value = client_exists

    if reader is None:
        reader = Mock()

    uc = MediaUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        media_reader=reader,
    )
    return uc, reader


# ---------------------------------------------------------------------------
# Precondition: account not found
# ---------------------------------------------------------------------------

class TestAccountPreconditions:
    def test_get_media_by_pk_raises_if_account_missing(self):
        uc, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.get_media_by_pk("no-such", 123)

    def test_get_media_by_code_raises_if_account_missing(self):
        uc, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.get_media_by_code("no-such", "ABC")

    def test_get_user_medias_raises_if_account_missing(self):
        uc, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.get_user_medias("no-such", 999)

    def test_get_media_oembed_raises_if_account_missing(self):
        uc, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.get_media_oembed("no-such", "https://instagram.com/p/ABC/")


# ---------------------------------------------------------------------------
# Precondition: account not authenticated
# ---------------------------------------------------------------------------

class TestAuthPreconditions:
    def test_get_media_by_pk_raises_if_not_authenticated(self):
        uc, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.get_media_by_pk("acc-1", 123)

    def test_get_media_by_code_raises_if_not_authenticated(self):
        uc, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.get_media_by_code("acc-1", "ABC")

    def test_get_user_medias_raises_if_not_authenticated(self):
        uc, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.get_user_medias("acc-1", 999)

    def test_get_media_oembed_raises_if_not_authenticated(self):
        uc, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.get_media_oembed("acc-1", "https://instagram.com/p/ABC/")


# ---------------------------------------------------------------------------
# Parameter normalization
# ---------------------------------------------------------------------------

class TestParameterNormalization:
    def test_get_media_by_pk_rejects_zero(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_media_by_pk("acc-1", 0)

    def test_get_media_by_pk_rejects_negative(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_media_by_pk("acc-1", -5)

    def test_get_media_by_pk_rejects_string(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_media_by_pk("acc-1", "123")  # type: ignore[arg-type]

    def test_get_media_by_code_strips_whitespace(self):
        uc, reader = _build_use_cases()
        reader.get_media_by_code.return_value = _make_media(code="XYZ")

        uc.get_media_by_code("acc-1", "  XYZ  ")

        reader.get_media_by_code.assert_called_once_with("acc-1", "XYZ")

    def test_get_media_by_code_rejects_empty(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="empty"):
            uc.get_media_by_code("acc-1", "")

    def test_get_media_by_code_rejects_whitespace_only(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="empty"):
            uc.get_media_by_code("acc-1", "   ")

    def test_get_user_medias_rejects_zero_user_id(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_user_medias("acc-1", 0)

    def test_get_user_medias_rejects_negative_user_id(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_user_medias("acc-1", -1)

    def test_get_user_medias_clamps_amount_to_min(self):
        uc, reader = _build_use_cases()
        reader.get_user_medias.return_value = []

        uc.get_user_medias("acc-1", 999, amount=0)

        reader.get_user_medias.assert_called_once_with("acc-1", 999, 1)

    def test_get_user_medias_clamps_amount_to_max(self):
        uc, reader = _build_use_cases()
        reader.get_user_medias.return_value = []

        uc.get_user_medias("acc-1", 999, amount=9999)

        reader.get_user_medias.assert_called_once_with("acc-1", 999, 200)

    def test_get_user_medias_passes_valid_amount_unchanged(self):
        uc, reader = _build_use_cases()
        reader.get_user_medias.return_value = []

        uc.get_user_medias("acc-1", 999, amount=50)

        reader.get_user_medias.assert_called_once_with("acc-1", 999, 50)

    def test_get_user_medias_default_amount(self):
        uc, reader = _build_use_cases()
        reader.get_user_medias.return_value = []

        uc.get_user_medias("acc-1", 999)

        reader.get_user_medias.assert_called_once_with("acc-1", 999, 12)

    def test_get_media_oembed_rejects_empty_url(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="empty"):
            uc.get_media_oembed("acc-1", "")

    def test_get_media_oembed_rejects_non_http_url(self):
        uc, _ = _build_use_cases()
        with pytest.raises(ValueError, match="start with 'http'"):
            uc.get_media_oembed("acc-1", "ftp://example.com/p/ABC/")

    def test_get_media_oembed_strips_whitespace_from_url(self):
        uc, reader = _build_use_cases()
        reader.get_media_oembed.return_value = _make_oembed()

        uc.get_media_oembed("acc-1", "  https://instagram.com/p/ABC/  ")

        reader.get_media_oembed.assert_called_once_with(
            "acc-1", "https://instagram.com/p/ABC/"
        )

    def test_get_media_oembed_accepts_https(self):
        uc, reader = _build_use_cases()
        reader.get_media_oembed.return_value = _make_oembed()

        uc.get_media_oembed("acc-1", "https://www.instagram.com/p/ABC/")

        reader.get_media_oembed.assert_called_once()


# ---------------------------------------------------------------------------
# Happy-path delegation
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_get_media_by_pk_returns_dto_from_reader(self):
        uc, reader = _build_use_cases()
        expected = _make_media(pk=42)
        reader.get_media_by_pk.return_value = expected

        result = uc.get_media_by_pk("acc-1", 42)

        assert result is expected
        reader.get_media_by_pk.assert_called_once_with("acc-1", 42)

    def test_get_media_by_code_returns_dto_from_reader(self):
        uc, reader = _build_use_cases()
        expected = _make_media(code="XYZ")
        reader.get_media_by_code.return_value = expected

        result = uc.get_media_by_code("acc-1", "XYZ")

        assert result is expected
        reader.get_media_by_code.assert_called_once_with("acc-1", "XYZ")

    def test_get_user_medias_returns_list_from_reader(self):
        uc, reader = _build_use_cases()
        expected = [_make_media(pk=1), _make_media(pk=2)]
        reader.get_user_medias.return_value = expected

        result = uc.get_user_medias("acc-1", 777, amount=2)

        assert result is expected
        reader.get_user_medias.assert_called_once_with("acc-1", 777, 2)

    def test_get_media_oembed_returns_dto_from_reader(self):
        uc, reader = _build_use_cases()
        expected = _make_oembed()
        reader.get_media_oembed.return_value = expected

        result = uc.get_media_oembed("acc-1", "https://instagram.com/p/ABC/")

        assert result is expected
        reader.get_media_oembed.assert_called_once_with(
            "acc-1", "https://instagram.com/p/ABC/"
        )

    def test_get_user_medias_returns_empty_list(self):
        uc, reader = _build_use_cases()
        reader.get_user_medias.return_value = []

        result = uc.get_user_medias("acc-1", 777)

        assert result == []

    def test_reader_is_not_called_when_precondition_fails(self):
        uc, reader = _build_use_cases(account_exists=False)

        with pytest.raises(ValueError):
            uc.get_media_by_pk("acc-1", 42)

        reader.get_media_by_pk.assert_not_called()


# ---------------------------------------------------------------------------
# DTO boundary: no vendor types leak through the use case
# ---------------------------------------------------------------------------

class TestDTOBoundary:
    """Verify use case only returns app-owned DTOs, never raw vendor objects."""

    def test_get_media_by_pk_result_is_media_summary(self):
        uc, reader = _build_use_cases()
        reader.get_media_by_pk.return_value = _make_media()

        result = uc.get_media_by_pk("acc-1", 1)

        assert isinstance(result, MediaSummary)

    def test_get_media_by_code_result_is_media_summary(self):
        uc, reader = _build_use_cases()
        reader.get_media_by_code.return_value = _make_media()

        result = uc.get_media_by_code("acc-1", "ABC")

        assert isinstance(result, MediaSummary)

    def test_get_user_medias_result_items_are_media_summary(self):
        uc, reader = _build_use_cases()
        reader.get_user_medias.return_value = [_make_media(pk=i) for i in range(3)]

        results = uc.get_user_medias("acc-1", 999)

        assert all(isinstance(r, MediaSummary) for r in results)

    def test_get_media_oembed_result_is_oembed_summary(self):
        uc, reader = _build_use_cases()
        reader.get_media_oembed.return_value = _make_oembed()

        result = uc.get_media_oembed("acc-1", "https://instagram.com/p/X/")

        assert isinstance(result, MediaOembedSummary)
