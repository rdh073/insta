"""Use-case tests for CommentUseCases.

Tests the application orchestration layer using port doubles (stubs/fakes).
No instagrapi imports — all vendor types stay behind the port boundary.
Covers:
  - Preconditions: account not found, account not authenticated
  - media_id normalization: empty, whitespace, stripping
  - list_comments: amount validation
  - list_comments_page: page_size validation, cursor passthrough
  - create_comment: text validation, top-level vs reply flow
  - delete_comment: comment_id validation
  - Port not called when preconditions or validation fails
  - DTO boundary: only app-owned types returned
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.application.dto.instagram_comment_dto import (
    CommentActionReceipt,
    CommentAuthorSummary,
    CommentPage,
    CommentSummary,
)
from app.application.use_cases.comment import CommentUseCases


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_author() -> CommentAuthorSummary:
    return CommentAuthorSummary(pk=1, username="testuser")


def _make_comment(pk: int = 1) -> CommentSummary:
    return CommentSummary(pk=pk, text="Nice!", author=_make_author())


def _make_page(comments: list[CommentSummary] | None = None) -> CommentPage:
    return CommentPage(comments=comments or [], next_cursor=None)


def _make_receipt(action_id: str = "act-1") -> CommentActionReceipt:
    return CommentActionReceipt(action_id=action_id, success=True)


def _build_use_cases(
    *,
    account_exists: bool = True,
    client_exists: bool = True,
    reader: Mock | None = None,
    writer: Mock | None = None,
) -> tuple[CommentUseCases, Mock, Mock]:
    account_repo = Mock()
    account_repo.get.return_value = {"username": "testuser"} if account_exists else None

    client_repo = Mock()
    client_repo.exists.return_value = client_exists

    if reader is None:
        reader = Mock()
    if writer is None:
        writer = Mock()

    uc = CommentUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        comment_reader=reader,
        comment_writer=writer,
    )
    return uc, reader, writer


# ---------------------------------------------------------------------------
# Preconditions: account not found
# ---------------------------------------------------------------------------

class TestAccountPreconditions:
    def test_list_comments_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.list_comments("no-such", "media-1")

    def test_list_comments_page_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.list_comments_page("no-such", "media-1", 10)

    def test_create_comment_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.create_comment("no-such", "media-1", "Nice!")

    def test_delete_comment_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.delete_comment("no-such", "media-1", 999)


# ---------------------------------------------------------------------------
# Preconditions: account not authenticated
# ---------------------------------------------------------------------------

class TestAuthPreconditions:
    def test_list_comments_raises_if_not_authenticated(self):
        uc, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.list_comments("acc-1", "media-1")

    def test_list_comments_page_raises_if_not_authenticated(self):
        uc, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.list_comments_page("acc-1", "media-1", 10)

    def test_create_comment_raises_if_not_authenticated(self):
        uc, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.create_comment("acc-1", "media-1", "Hi!")

    def test_delete_comment_raises_if_not_authenticated(self):
        uc, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.delete_comment("acc-1", "media-1", 1)


# ---------------------------------------------------------------------------
# media_id normalization
# ---------------------------------------------------------------------------

class TestMediaIdNormalization:
    def test_rejects_empty_media_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="media_id"):
            uc.list_comments("acc-1", "")

    def test_rejects_whitespace_media_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="media_id"):
            uc.list_comments("acc-1", "   ")

    def test_strips_media_id_before_delegating(self):
        uc, reader, _ = _build_use_cases()
        reader.list_comments.return_value = []

        uc.list_comments("acc-1", "  12345  ")

        reader.list_comments.assert_called_once_with("acc-1", "12345", 0)

    def test_create_comment_strips_media_id(self):
        uc, _, writer = _build_use_cases()
        writer.create_comment.return_value = _make_comment()

        uc.create_comment("acc-1", "  12345  ", "Hi!")

        args = writer.create_comment.call_args[0]
        assert args[1] == "12345"

    def test_delete_comment_rejects_empty_media_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="media_id"):
            uc.delete_comment("acc-1", "", 1)


# ---------------------------------------------------------------------------
# list_comments: amount validation
# ---------------------------------------------------------------------------

class TestListCommentsValidation:
    def test_rejects_negative_amount(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="non-negative"):
            uc.list_comments("acc-1", "media-1", amount=-1)

    def test_accepts_zero_amount(self):
        uc, reader, _ = _build_use_cases()
        reader.list_comments.return_value = []

        uc.list_comments("acc-1", "media-1", amount=0)

        reader.list_comments.assert_called_once_with("acc-1", "media-1", 0)

    def test_accepts_positive_amount(self):
        uc, reader, _ = _build_use_cases()
        reader.list_comments.return_value = []

        uc.list_comments("acc-1", "media-1", amount=20)

        reader.list_comments.assert_called_once_with("acc-1", "media-1", 20)

    def test_default_amount_is_zero(self):
        uc, reader, _ = _build_use_cases()
        reader.list_comments.return_value = []

        uc.list_comments("acc-1", "media-1")

        reader.list_comments.assert_called_once_with("acc-1", "media-1", 0)


# ---------------------------------------------------------------------------
# list_comments_page: page_size and cursor
# ---------------------------------------------------------------------------

class TestListCommentsPageValidation:
    def test_rejects_zero_page_size(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.list_comments_page("acc-1", "media-1", 0)

    def test_rejects_negative_page_size(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.list_comments_page("acc-1", "media-1", -5)

    def test_accepts_valid_page_size(self):
        uc, reader, _ = _build_use_cases()
        reader.list_comments_page.return_value = _make_page()

        uc.list_comments_page("acc-1", "media-1", 10)

        reader.list_comments_page.assert_called_once_with("acc-1", "media-1", 10, None)

    def test_passes_cursor_to_port(self):
        uc, reader, _ = _build_use_cases()
        reader.list_comments_page.return_value = _make_page()

        uc.list_comments_page("acc-1", "media-1", 10, cursor="abc123")

        reader.list_comments_page.assert_called_once_with("acc-1", "media-1", 10, "abc123")

    def test_none_cursor_passes_through(self):
        uc, reader, _ = _build_use_cases()
        reader.list_comments_page.return_value = _make_page()

        uc.list_comments_page("acc-1", "media-1", 5, cursor=None)

        reader.list_comments_page.assert_called_once_with("acc-1", "media-1", 5, None)


# ---------------------------------------------------------------------------
# create_comment: text and reply flow
# ---------------------------------------------------------------------------

class TestCreateCommentValidation:
    def test_rejects_empty_text(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="text"):
            uc.create_comment("acc-1", "media-1", "")

    def test_rejects_whitespace_text(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="text"):
            uc.create_comment("acc-1", "media-1", "   ")

    def test_strips_text_before_delegating(self):
        uc, _, writer = _build_use_cases()
        writer.create_comment.return_value = _make_comment()

        uc.create_comment("acc-1", "media-1", "  Great post!  ")

        args = writer.create_comment.call_args[0]
        assert args[2] == "Great post!"

    def test_top_level_comment_passes_none_reply_id(self):
        uc, _, writer = _build_use_cases()
        writer.create_comment.return_value = _make_comment()

        uc.create_comment("acc-1", "media-1", "Nice!")

        writer.create_comment.assert_called_once_with("acc-1", "media-1", "Nice!", None)

    def test_reply_flow_passes_comment_id(self):
        uc, _, writer = _build_use_cases()
        writer.create_comment.return_value = _make_comment()

        uc.create_comment("acc-1", "media-1", "Thanks!", reply_to_comment_id=42)

        writer.create_comment.assert_called_once_with("acc-1", "media-1", "Thanks!", 42)

    def test_rejects_zero_reply_to_comment_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="reply_to_comment_id"):
            uc.create_comment("acc-1", "media-1", "Hi!", reply_to_comment_id=0)

    def test_rejects_negative_reply_to_comment_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="reply_to_comment_id"):
            uc.create_comment("acc-1", "media-1", "Hi!", reply_to_comment_id=-1)

    def test_rejects_non_int_reply_to_comment_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="reply_to_comment_id"):
            uc.create_comment("acc-1", "media-1", "Hi!", reply_to_comment_id="abc")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# delete_comment: comment_id validation
# ---------------------------------------------------------------------------

class TestDeleteCommentValidation:
    def test_rejects_zero_comment_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="comment_id"):
            uc.delete_comment("acc-1", "media-1", 0)

    def test_rejects_negative_comment_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="comment_id"):
            uc.delete_comment("acc-1", "media-1", -1)

    def test_rejects_non_int_comment_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="comment_id"):
            uc.delete_comment("acc-1", "media-1", "abc")  # type: ignore[arg-type]

    def test_delegates_valid_comment_id(self):
        uc, _, writer = _build_use_cases()
        writer.delete_comment.return_value = _make_receipt()

        uc.delete_comment("acc-1", "media-1", 999)

        writer.delete_comment.assert_called_once_with("acc-1", "media-1", 999)


# ---------------------------------------------------------------------------
# Port not called when preconditions or validation fails
# ---------------------------------------------------------------------------

class TestPortNotCalledOnFailure:
    def test_reader_not_called_when_account_missing(self):
        uc, reader, _ = _build_use_cases(account_exists=False)

        with pytest.raises(ValueError):
            uc.list_comments("acc-1", "media-1")

        reader.list_comments.assert_not_called()

    def test_writer_not_called_when_text_empty(self):
        uc, _, writer = _build_use_cases()

        with pytest.raises(ValueError):
            uc.create_comment("acc-1", "media-1", "")

        writer.create_comment.assert_not_called()

    def test_writer_not_called_when_comment_id_invalid(self):
        uc, _, writer = _build_use_cases()

        with pytest.raises(ValueError):
            uc.delete_comment("acc-1", "media-1", 0)

        writer.delete_comment.assert_not_called()

    def test_writer_not_called_when_media_id_empty(self):
        uc, _, writer = _build_use_cases()

        with pytest.raises(ValueError):
            uc.create_comment("acc-1", "", "Hi!")

        writer.create_comment.assert_not_called()


# ---------------------------------------------------------------------------
# DTO boundary: only app-owned types returned
# ---------------------------------------------------------------------------

class TestDTOBoundary:
    def test_list_comments_returns_comment_summaries(self):
        uc, reader, _ = _build_use_cases()
        reader.list_comments.return_value = [_make_comment(i) for i in range(1, 4)]

        results = uc.list_comments("acc-1", "media-1")

        assert all(isinstance(r, CommentSummary) for r in results)

    def test_list_comments_page_returns_comment_page(self):
        uc, reader, _ = _build_use_cases()
        reader.list_comments_page.return_value = _make_page([_make_comment(1)])

        result = uc.list_comments_page("acc-1", "media-1", 10)

        assert isinstance(result, CommentPage)

    def test_create_comment_returns_comment_summary(self):
        uc, _, writer = _build_use_cases()
        writer.create_comment.return_value = _make_comment()

        result = uc.create_comment("acc-1", "media-1", "Nice!")

        assert isinstance(result, CommentSummary)

    def test_delete_comment_returns_action_receipt(self):
        uc, _, writer = _build_use_cases()
        writer.delete_comment.return_value = _make_receipt()

        result = uc.delete_comment("acc-1", "media-1", 1)

        assert isinstance(result, CommentActionReceipt)
