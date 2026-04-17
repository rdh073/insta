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
    MediaActionReceipt,
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


def _build_use_cases_with_writer(
    *,
    account_exists: bool = True,
    client_exists: bool = True,
    writer: Mock | None = None,
) -> tuple[MediaUseCases, Mock]:
    """Build MediaUseCases with a writer mock for write-method tests."""
    account_repo = Mock()
    account_repo.get.return_value = {"username": "testuser"} if account_exists else None

    client_repo = Mock()
    client_repo.exists.return_value = client_exists

    if writer is None:
        writer = Mock()

    uc = MediaUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        media_reader=Mock(),
        media_writer=writer,
    )
    return uc, writer


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


# ---------------------------------------------------------------------------
# Write methods (edit/delete/pin/archive/save)
# ---------------------------------------------------------------------------

def _ok(action_id: str, reason: str = "ok") -> MediaActionReceipt:
    return MediaActionReceipt(action_id=action_id, success=True, reason=reason)


WRITE_METHODS = [
    "edit_caption",
    "delete_media",
    "pin_media",
    "unpin_media",
    "archive_media",
    "unarchive_media",
    "save_media",
    "unsave_media",
]


class TestMediaWritePreconditions:
    @pytest.mark.parametrize("method", WRITE_METHODS)
    def test_raises_if_account_missing(self, method):
        uc, _ = _build_use_cases_with_writer(account_exists=False)
        kwargs = {"caption": ""} if method == "edit_caption" else {}
        with pytest.raises(ValueError, match="not found"):
            getattr(uc, method)("no-such", "1_1", **kwargs)

    @pytest.mark.parametrize("method", WRITE_METHODS)
    def test_raises_if_not_authenticated(self, method):
        uc, _ = _build_use_cases_with_writer(client_exists=False)
        kwargs = {"caption": ""} if method == "edit_caption" else {}
        with pytest.raises(ValueError, match="not authenticated"):
            getattr(uc, method)("acc-1", "1_1", **kwargs)

    @pytest.mark.parametrize("method", WRITE_METHODS)
    def test_raises_if_writer_not_configured(self, method):
        # Build with the read-only helper so writer is None.
        uc, _ = _build_use_cases()
        kwargs = {"caption": ""} if method == "edit_caption" else {}
        with pytest.raises(ValueError, match="writer not configured"):
            getattr(uc, method)("acc-1", "1_1", **kwargs)

    @pytest.mark.parametrize("method", WRITE_METHODS)
    def test_rejects_empty_media_id(self, method):
        uc, _ = _build_use_cases_with_writer()
        kwargs = {"caption": ""} if method == "edit_caption" else {}
        with pytest.raises(ValueError, match="media_id"):
            getattr(uc, method)("acc-1", "", **kwargs)

    @pytest.mark.parametrize("method", WRITE_METHODS)
    def test_rejects_whitespace_only_media_id(self, method):
        uc, _ = _build_use_cases_with_writer()
        kwargs = {"caption": ""} if method == "edit_caption" else {}
        with pytest.raises(ValueError, match="media_id"):
            getattr(uc, method)("acc-1", "   ", **kwargs)

    @pytest.mark.parametrize("method", WRITE_METHODS)
    def test_strips_media_id_whitespace(self, method):
        uc, writer = _build_use_cases_with_writer()
        getattr(writer, method).return_value = _ok("3_4")
        kwargs = {"caption": "ok"} if method == "edit_caption" else {}

        getattr(uc, method)("acc-1", "  3_4  ", **kwargs)

        # Adapter is called with stripped id; collection_pk is added by the use
        # case for save/unsave (positional or default None — accept either).
        call = getattr(writer, method).call_args
        assert call.args[1] == "3_4"


class TestMediaWriteCaptionValidation:
    def test_edit_caption_rejects_none(self):
        uc, _ = _build_use_cases_with_writer()
        with pytest.raises(ValueError, match="caption"):
            uc.edit_caption("acc-1", "1_1", None)  # type: ignore[arg-type]

    def test_edit_caption_rejects_oversize(self):
        uc, _ = _build_use_cases_with_writer()
        with pytest.raises(ValueError, match="2200"):
            uc.edit_caption("acc-1", "1_1", "x" * 2201)

    def test_edit_caption_accepts_max_length(self):
        uc, writer = _build_use_cases_with_writer()
        writer.edit_caption.return_value = _ok("1_1")

        result = uc.edit_caption("acc-1", "1_1", "x" * 2200)

        assert result.success
        writer.edit_caption.assert_called_once_with("acc-1", "1_1", "x" * 2200)


class TestMediaWriteCollectionPkValidation:
    @pytest.mark.parametrize("method", ["save_media", "unsave_media"])
    def test_accepts_none_collection_pk(self, method):
        uc, writer = _build_use_cases_with_writer()
        getattr(writer, method).return_value = _ok("1_1")

        getattr(uc, method)("acc-1", "1_1")

        getattr(writer, method).assert_called_once_with("acc-1", "1_1", None)

    @pytest.mark.parametrize("method", ["save_media", "unsave_media"])
    def test_accepts_positive_collection_pk(self, method):
        uc, writer = _build_use_cases_with_writer()
        getattr(writer, method).return_value = _ok("1_1")

        getattr(uc, method)("acc-1", "1_1", collection_pk=42)

        getattr(writer, method).assert_called_once_with("acc-1", "1_1", 42)

    @pytest.mark.parametrize("method", ["save_media", "unsave_media"])
    @pytest.mark.parametrize("bad_pk", [0, -1, "42"])
    def test_rejects_invalid_collection_pk(self, method, bad_pk):
        uc, _ = _build_use_cases_with_writer()
        with pytest.raises(ValueError, match="collection_pk"):
            getattr(uc, method)("acc-1", "1_1", collection_pk=bad_pk)


class TestMediaWriteHappyPath:
    @pytest.mark.parametrize(
        "method, vendor_args",
        [
            ("delete_media", ("acc-1", "1_1")),
            ("pin_media", ("acc-1", "1_1")),
            ("unpin_media", ("acc-1", "1_1")),
            ("archive_media", ("acc-1", "1_1")),
            ("unarchive_media", ("acc-1", "1_1")),
        ],
    )
    def test_delegates_to_writer(self, method, vendor_args):
        uc, writer = _build_use_cases_with_writer()
        receipt = _ok("1_1", reason=f"{method} ok")
        getattr(writer, method).return_value = receipt

        result = getattr(uc, method)("acc-1", "1_1")

        assert result is receipt
        getattr(writer, method).assert_called_once_with(*vendor_args)

    def test_writer_not_called_when_precondition_fails(self):
        uc, writer = _build_use_cases_with_writer(account_exists=False)
        with pytest.raises(ValueError):
            uc.delete_media("acc-1", "1_1")
        writer.delete_media.assert_not_called()
