"""Use-case tests for HighlightUseCases.

Tests the application orchestration layer using port doubles (stubs/fakes).
No instagrapi imports — all vendor types stay behind the port boundary.
Covers:
  - Preconditions: account not found, account not authenticated
  - URL validation: get_highlight_pk_from_url
  - highlight_pk validation (positive integer)
  - user_id and amount validation for list_user_highlights
  - create_highlight: title, story_ids, cover_story_id, crop_rect
  - change_title: highlight_pk, title
  - add_stories / remove_stories: highlight_pk, story_ids
  - delete_highlight: highlight_pk
  - Port not called when preconditions or validation fails
  - DTO boundary: only app-owned types returned
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.application.dto.instagram_highlight_dto import (
    HighlightActionReceipt,
    HighlightDetail,
    HighlightSummary,
)
from app.application.use_cases.highlight import HighlightUseCases


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_summary(pk: str = "1") -> HighlightSummary:
    return HighlightSummary(pk=pk, highlight_id=pk)


def _make_detail(pk: str = "1") -> HighlightDetail:
    return HighlightDetail(summary=_make_summary(pk))


def _make_receipt(action_id: str = "act-1") -> HighlightActionReceipt:
    return HighlightActionReceipt(action_id=action_id, success=True)


def _build_use_cases(
    *,
    account_exists: bool = True,
    client_exists: bool = True,
    reader: Mock | None = None,
    writer: Mock | None = None,
) -> tuple[HighlightUseCases, Mock, Mock]:
    account_repo = Mock()
    account_repo.get.return_value = {"username": "testuser"} if account_exists else None

    client_repo = Mock()
    client_repo.exists.return_value = client_exists

    if reader is None:
        reader = Mock()
    if writer is None:
        writer = Mock()

    uc = HighlightUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        highlight_reader=reader,
        highlight_writer=writer,
    )
    return uc, reader, writer


# ---------------------------------------------------------------------------
# Preconditions: account not found
# ---------------------------------------------------------------------------

class TestAccountPreconditions:
    def test_get_highlight_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.get_highlight("no-such", 1)

    def test_list_user_highlights_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.list_user_highlights("no-such", 123)

    def test_create_highlight_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.create_highlight("no-such", "Travel", [1, 2])

    def test_change_title_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.change_title("no-such", 1, "New Title")

    def test_add_stories_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.add_stories("no-such", 1, [10])

    def test_remove_stories_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.remove_stories("no-such", 1, [10])

    def test_delete_highlight_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.delete_highlight("no-such", 1)


# ---------------------------------------------------------------------------
# Preconditions: account not authenticated
# ---------------------------------------------------------------------------

class TestAuthPreconditions:
    def test_get_highlight_raises_if_not_authenticated(self):
        uc, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.get_highlight("acc-1", 1)

    def test_list_user_highlights_raises_if_not_authenticated(self):
        uc, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.list_user_highlights("acc-1", 123)

    def test_create_highlight_raises_if_not_authenticated(self):
        uc, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.create_highlight("acc-1", "Travel", [1])

    def test_delete_highlight_raises_if_not_authenticated(self):
        uc, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.delete_highlight("acc-1", 1)


# ---------------------------------------------------------------------------
# get_highlight_pk_from_url validation
# ---------------------------------------------------------------------------

class TestGetHighlightPkFromUrl:
    def test_rejects_empty_url(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="empty"):
            uc.get_highlight_pk_from_url("")

    def test_rejects_whitespace_only(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="empty"):
            uc.get_highlight_pk_from_url("   ")

    def test_rejects_non_http_url(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="http"):
            uc.get_highlight_pk_from_url("ftp://example.com/highlight/123")

    def test_strips_whitespace_and_delegates(self):
        uc, reader, _ = _build_use_cases()
        reader.get_highlight_pk_from_url.return_value = 55

        result = uc.get_highlight_pk_from_url(
            "  https://www.instagram.com/stories/highlights/55/  "
        )

        reader.get_highlight_pk_from_url.assert_called_once_with(
            "https://www.instagram.com/stories/highlights/55/"
        )
        assert result == 55

    def test_accepts_valid_url(self):
        uc, reader, _ = _build_use_cases()
        reader.get_highlight_pk_from_url.return_value = 77

        result = uc.get_highlight_pk_from_url(
            "https://www.instagram.com/stories/highlights/77/"
        )

        assert result == 77


# ---------------------------------------------------------------------------
# highlight_pk validation
# ---------------------------------------------------------------------------

class TestHighlightPkValidation:
    def test_rejects_zero(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_highlight("acc-1", 0)

    def test_rejects_negative(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_highlight("acc-1", -1)

    def test_rejects_non_int(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_highlight("acc-1", "abc")  # type: ignore[arg-type]

    def test_accepts_valid_pk(self):
        uc, reader, _ = _build_use_cases()
        reader.get_highlight.return_value = _make_detail("5")

        uc.get_highlight("acc-1", 5)

        reader.get_highlight.assert_called_once_with("acc-1", 5)


# ---------------------------------------------------------------------------
# list_user_highlights: user_id and amount
# ---------------------------------------------------------------------------

class TestListUserHighlightsValidation:
    def test_rejects_zero_user_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.list_user_highlights("acc-1", 0)

    def test_rejects_negative_user_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.list_user_highlights("acc-1", -1)

    def test_rejects_negative_amount(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="non-negative"):
            uc.list_user_highlights("acc-1", 100, amount=-1)

    def test_accepts_zero_amount(self):
        uc, reader, _ = _build_use_cases()
        reader.list_user_highlights.return_value = []

        uc.list_user_highlights("acc-1", 100, amount=0)

        reader.list_user_highlights.assert_called_once_with("acc-1", 100, 0)

    def test_default_amount_is_zero(self):
        uc, reader, _ = _build_use_cases()
        reader.list_user_highlights.return_value = []

        uc.list_user_highlights("acc-1", 100)

        reader.list_user_highlights.assert_called_once_with("acc-1", 100, 0)


# ---------------------------------------------------------------------------
# create_highlight validation
# ---------------------------------------------------------------------------

class TestCreateHighlightValidation:
    def test_rejects_empty_title(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="title"):
            uc.create_highlight("acc-1", "", [1])

    def test_rejects_whitespace_title(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="title"):
            uc.create_highlight("acc-1", "   ", [1])

    def test_strips_title_whitespace(self):
        uc, _, writer = _build_use_cases()
        writer.create_highlight.return_value = _make_detail()

        uc.create_highlight("acc-1", "  Travel  ", [1])

        args = writer.create_highlight.call_args[0]
        assert args[1] == "Travel"

    def test_rejects_empty_story_ids(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="must not be empty"):
            uc.create_highlight("acc-1", "Travel", [])

    def test_rejects_zero_story_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integers"):
            uc.create_highlight("acc-1", "Travel", [1, 0])

    def test_rejects_negative_cover_story_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="cover_story_id"):
            uc.create_highlight("acc-1", "Travel", [1], cover_story_id=-1)

    def test_accepts_zero_cover_story_id(self):
        uc, _, writer = _build_use_cases()
        writer.create_highlight.return_value = _make_detail()

        uc.create_highlight("acc-1", "Travel", [1], cover_story_id=0)

        writer.create_highlight.assert_called_once()

    def test_rejects_crop_rect_wrong_length(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="crop_rect"):
            uc.create_highlight("acc-1", "Travel", [1], crop_rect=[0.1, 0.2, 0.3])

    def test_rejects_crop_rect_out_of_range(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="crop_rect"):
            uc.create_highlight("acc-1", "Travel", [1], crop_rect=[0.1, 0.2, 1.5, 0.4])

    def test_accepts_valid_crop_rect(self):
        uc, _, writer = _build_use_cases()
        writer.create_highlight.return_value = _make_detail()

        uc.create_highlight("acc-1", "Travel", [1], crop_rect=[0.0, 0.0, 1.0, 1.0])

        writer.create_highlight.assert_called_once()

    def test_none_crop_rect_passes_through(self):
        uc, _, writer = _build_use_cases()
        writer.create_highlight.return_value = _make_detail()

        uc.create_highlight("acc-1", "Travel", [1])

        args = writer.create_highlight.call_args[0]
        assert args[4] is None  # crop_rect


# ---------------------------------------------------------------------------
# change_title validation
# ---------------------------------------------------------------------------

class TestChangeTitleValidation:
    def test_rejects_invalid_highlight_pk(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.change_title("acc-1", 0, "New Title")

    def test_rejects_empty_title(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="title"):
            uc.change_title("acc-1", 1, "")

    def test_strips_and_delegates_title(self):
        uc, _, writer = _build_use_cases()
        writer.change_title.return_value = _make_detail()

        uc.change_title("acc-1", 1, "  New Title  ")

        writer.change_title.assert_called_once_with("acc-1", 1, "New Title")


# ---------------------------------------------------------------------------
# add_stories / remove_stories validation
# ---------------------------------------------------------------------------

class TestStoryListValidation:
    def test_add_stories_rejects_empty_list(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="must not be empty"):
            uc.add_stories("acc-1", 1, [])

    def test_add_stories_rejects_invalid_pk(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.add_stories("acc-1", 0, [10])

    def test_remove_stories_rejects_empty_list(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="must not be empty"):
            uc.remove_stories("acc-1", 1, [])

    def test_remove_stories_rejects_zero_story_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integers"):
            uc.remove_stories("acc-1", 1, [5, 0])

    def test_add_stories_delegates_correctly(self):
        uc, _, writer = _build_use_cases()
        writer.add_stories.return_value = _make_detail()

        uc.add_stories("acc-1", 10, [100, 200])

        writer.add_stories.assert_called_once_with("acc-1", 10, [100, 200])

    def test_remove_stories_delegates_correctly(self):
        uc, _, writer = _build_use_cases()
        writer.remove_stories.return_value = _make_detail()

        uc.remove_stories("acc-1", 10, [100])

        writer.remove_stories.assert_called_once_with("acc-1", 10, [100])


# ---------------------------------------------------------------------------
# Port not called when preconditions or validation fails
# ---------------------------------------------------------------------------

class TestPortNotCalledOnFailure:
    def test_reader_not_called_when_account_missing(self):
        uc, reader, _ = _build_use_cases(account_exists=False)

        with pytest.raises(ValueError):
            uc.get_highlight("acc-1", 1)

        reader.get_highlight.assert_not_called()

    def test_writer_not_called_on_invalid_story_ids(self):
        uc, _, writer = _build_use_cases()

        with pytest.raises(ValueError):
            uc.add_stories("acc-1", 1, [])

        writer.add_stories.assert_not_called()

    def test_writer_not_called_on_invalid_crop_rect(self):
        uc, _, writer = _build_use_cases()

        with pytest.raises(ValueError):
            uc.create_highlight("acc-1", "Travel", [1], crop_rect=[0.1, 0.2])

        writer.create_highlight.assert_not_called()


# ---------------------------------------------------------------------------
# DTO boundary: only app-owned types returned
# ---------------------------------------------------------------------------

class TestDTOBoundary:
    def test_get_highlight_returns_highlight_detail(self):
        uc, reader, _ = _build_use_cases()
        reader.get_highlight.return_value = _make_detail()

        result = uc.get_highlight("acc-1", 1)

        assert isinstance(result, HighlightDetail)

    def test_list_user_highlights_returns_summaries(self):
        uc, reader, _ = _build_use_cases()
        reader.list_user_highlights.return_value = [_make_summary(str(i)) for i in range(3)]

        results = uc.list_user_highlights("acc-1", 100)

        assert all(isinstance(r, HighlightSummary) for r in results)

    def test_create_highlight_returns_highlight_detail(self):
        uc, _, writer = _build_use_cases()
        writer.create_highlight.return_value = _make_detail()

        result = uc.create_highlight("acc-1", "Travel", [1, 2])

        assert isinstance(result, HighlightDetail)

    def test_delete_highlight_returns_action_receipt(self):
        uc, _, writer = _build_use_cases()
        writer.delete_highlight.return_value = _make_receipt()

        result = uc.delete_highlight("acc-1", 1)

        assert isinstance(result, HighlightActionReceipt)

    def test_add_stories_returns_highlight_detail(self):
        uc, _, writer = _build_use_cases()
        writer.add_stories.return_value = _make_detail()

        result = uc.add_stories("acc-1", 1, [10])

        assert isinstance(result, HighlightDetail)

    def test_remove_stories_returns_highlight_detail(self):
        uc, _, writer = _build_use_cases()
        writer.remove_stories.return_value = _make_detail()

        result = uc.remove_stories("acc-1", 1, [10])

        assert isinstance(result, HighlightDetail)
