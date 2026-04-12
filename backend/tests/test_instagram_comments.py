"""
Tests for Instagram comment reader, writer, and DTO mappings.

Verifies that instagrapi Comment objects map correctly to stable application DTOs.
Tests pagination, reply semantics, and delete normalization.
Ensures vendor types never leak into application code.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock

from app.application.dto.instagram_comment_dto import (
    CommentAuthorSummary,
    CommentSummary,
    CommentPage,
    CommentActionReceipt,
)
from app.adapters.instagram.comment_reader import (
    InstagramCommentReaderAdapter,
)
from app.adapters.instagram.comment_writer import (
    InstagramCommentWriterAdapter,
)


class TestCommentReaderAdapter:
    """Test the comment reader adapter mappings."""

    def test_list_comments(self):
        """Verify media_comments() maps to CommentSummary list."""
        # Create mock client
        mock_client = Mock()
        mock_comments = [
            self._create_mock_comment(pk=1, text="First comment", username="user1"),
            self._create_mock_comment(pk=2, text="Second comment", username="user2"),
            self._create_mock_comment(pk=3, text="Third comment", username="user3"),
        ]
        mock_client.media_comments.return_value = mock_comments

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCommentReaderAdapter(mock_repo)
        results = adapter.list_comments("acc-123", "media-456", amount=3)

        assert len(results) == 3
        assert all(isinstance(r, CommentSummary) for r in results)
        assert results[0].pk == 1
        assert results[0].text == "First comment"
        assert results[1].author.username == "user2"
        mock_client.media_comments.assert_called_once_with("media-456", amount=3)

    def test_list_comments_page(self):
        """Verify media_comments_chunk() maps to CommentPage."""
        # Create mock client
        mock_client = Mock()
        mock_comments = [
            self._create_mock_comment(pk=100, text="Page 1, Item 1"),
            self._create_mock_comment(pk=101, text="Page 1, Item 2"),
        ]
        next_min_id = "Q1VSU09SX1RPS0VOPQ=="  # Opaque cursor for next page
        mock_client.media_comments_chunk.return_value = (mock_comments, next_min_id)

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCommentReaderAdapter(mock_repo)
        result = adapter.list_comments_page("acc-123", "media-456", page_size=2)

        assert isinstance(result, CommentPage)
        assert len(result.comments) == 2
        assert result.comments[0].pk == 100
        assert result.next_cursor == "Q1VSU09SX1RPS0VOPQ=="
        mock_client.media_comments_chunk.assert_called_once()

    def test_list_comments_page_with_cursor(self):
        """Verify pagination cursor is passed correctly."""
        # Create mock client
        mock_client = Mock()
        mock_comments = [self._create_mock_comment(pk=200, text="Page 2, Item 1")]
        mock_client.media_comments_chunk.return_value = (mock_comments, None)

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter with cursor
        adapter = InstagramCommentReaderAdapter(mock_repo)
        opaque_cursor = "eyJjdXJzb3IiOiJwYWdlLTIifQ=="
        result = adapter.list_comments_page(
            "acc-123",
            "media-456",
            page_size=10,
            cursor=opaque_cursor,
        )

        assert len(result.comments) == 1
        assert result.next_cursor is None  # No more pages
        # Verify opaque cursor is passed through unchanged as min_id
        call_args = mock_client.media_comments_chunk.call_args
        assert call_args.kwargs.get("min_id") == opaque_cursor

    def test_comment_author_extraction(self):
        """Verify comment author is extracted from nested user object."""
        # Create mock client
        mock_client = Mock()
        mock_comment = self._create_mock_comment(pk=1, text="Test")
        mock_comment.user = Mock()
        mock_comment.user.pk = 999
        mock_comment.user.username = "testuser"
        mock_comment.user.full_name = "Test User"
        mock_comment.user.profile_pic_url = "https://example.com/profile.jpg"
        mock_client.media_comments.return_value = [mock_comment]

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCommentReaderAdapter(mock_repo)
        results = adapter.list_comments("acc-123", "media-456")

        assert len(results) == 1
        assert isinstance(results[0].author, CommentAuthorSummary)
        assert results[0].author.username == "testuser"
        assert results[0].author.full_name == "Test User"
        assert results[0].author.profile_pic_url == "https://example.com/profile.jpg"

    def test_missing_client_error(self):
        """Verify proper error when client not found."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramCommentReaderAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.list_comments("acc-123", "media-456")

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.list_comments_page("acc-123", "media-456", page_size=10)

    def test_null_field_handling(self):
        """Verify None/null fields are handled gracefully."""
        # Create mock client with minimal data
        mock_client = Mock()
        mock_comment = Mock()
        mock_comment.pk = 1
        mock_comment.text = "Comment"
        mock_comment.user = None
        mock_comment.created_at_utc = None
        mock_comment.content_type = None
        mock_comment.status = None
        mock_comment.has_liked = None
        mock_comment.like_count = None

        mock_client.media_comments.return_value = [mock_comment]

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCommentReaderAdapter(mock_repo)
        results = adapter.list_comments("acc-123", "media-456")

        # Verify null handling
        assert results[0].created_at is None
        assert results[0].content_type is None
        assert results[0].has_liked is None
        assert results[0].like_count is None

    @staticmethod
    def _create_mock_comment(pk=1, text="Test comment", username="user"):
        """Create a mock Comment object."""
        mock = Mock()
        mock.pk = pk
        mock.text = text
        mock.user = Mock()
        mock.user.pk = 100 + pk
        mock.user.username = username
        mock.user.full_name = f"{username} Name"
        mock.user.profile_pic_url = f"https://example.com/{username}.jpg"
        mock.created_at_utc = datetime(2023, 1, 1, tzinfo=timezone.utc)
        mock.content_type = "comment"
        mock.status = "Active"
        mock.has_liked = False
        mock.like_count = 0
        return mock


class TestCommentWriterAdapter:
    """Test the comment writer adapter."""

    def test_create_comment(self):
        """Verify media_comment() maps to CommentSummary."""
        # Create mock client
        mock_client = Mock()
        created_comment = TestCommentReaderAdapter._create_mock_comment(
            pk=999, text="New comment"
        )
        mock_client.media_comment.return_value = created_comment

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCommentWriterAdapter(mock_repo)
        result = adapter.create_comment("acc-123", "media-456", "New comment")

        assert isinstance(result, CommentSummary)
        assert result.pk == 999
        assert result.text == "New comment"
        mock_client.media_comment.assert_called_once_with(
            "media-456", "New comment", replied_to_comment_id=None
        )

    def test_create_reply(self):
        """Verify create_comment with reply_to_comment_id."""
        # Create mock client
        mock_client = Mock()
        created_comment = TestCommentReaderAdapter._create_mock_comment(
            pk=1000, text="Reply"
        )
        mock_client.media_comment.return_value = created_comment

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCommentWriterAdapter(mock_repo)
        result = adapter.create_comment(
            "acc-123", "media-456", "Reply text", reply_to_comment_id=999
        )

        assert isinstance(result, CommentSummary)
        # Verify reply_to_comment_id was passed
        call_args = mock_client.media_comment.call_args
        assert call_args.kwargs.get("replied_to_comment_id") == 999

    def test_delete_comment(self):
        """Verify comment_bulk_delete() normalizes to single delete."""
        # Create mock client
        mock_client = Mock()
        mock_client.comment_bulk_delete.return_value = None

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCommentWriterAdapter(mock_repo)
        result = adapter.delete_comment("acc-123", "media-456", 999)

        assert isinstance(result, CommentActionReceipt)
        assert result.success is True
        assert result.action_id == "999"
        assert "deleted" in result.reason.lower()
        # Verify comment_bulk_delete was called with array
        mock_client.comment_bulk_delete.assert_called_once_with("media-456", [999])

    def test_delete_comment_failure(self):
        """Verify delete failure is captured in receipt."""
        # Create mock client
        mock_client = Mock()
        mock_client.comment_bulk_delete.side_effect = Exception("Delete failed")

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCommentWriterAdapter(mock_repo)
        result = adapter.delete_comment("acc-123", "media-456", 999)

        assert isinstance(result, CommentActionReceipt)
        assert result.success is False
        assert result.action_id == "999"
        assert result.reason
        assert "Delete failed" not in result.reason

    def test_missing_client_error_create(self):
        """Verify proper error when client not found for create."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramCommentWriterAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.create_comment("acc-123", "media-456", "text")

    def test_missing_client_error_delete(self):
        """Verify proper error when client not found for delete."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramCommentWriterAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.delete_comment("acc-123", "media-456", 999)


class TestCommentDTOs:
    """Test the comment DTO properties."""

    def test_comment_author_summary_frozen(self):
        """Verify CommentAuthorSummary is immutable."""
        author = CommentAuthorSummary(pk=1, username="test")
        with pytest.raises(AttributeError):
            author.username = "different"

    def test_comment_summary_frozen(self):
        """Verify CommentSummary is immutable."""
        author = CommentAuthorSummary(pk=1, username="test")
        comment = CommentSummary(pk=1, text="test", author=author)
        with pytest.raises(AttributeError):
            comment.text = "different"

    def test_comment_page_frozen(self):
        """Verify CommentPage is immutable."""
        page = CommentPage(comments=[], next_cursor=None)
        with pytest.raises(AttributeError):
            page.next_cursor = "new"

    def test_comment_action_receipt_frozen(self):
        """Verify CommentActionReceipt is immutable."""
        receipt = CommentActionReceipt(action_id="1", success=True)
        with pytest.raises(AttributeError):
            receipt.success = False

    def test_comment_summary_defaults(self):
        """Verify CommentSummary has sensible defaults."""
        author = CommentAuthorSummary(pk=1, username="test")
        comment = CommentSummary(pk=1, text="test", author=author)
        assert comment.created_at is None
        assert comment.content_type is None
        assert comment.status is None
        assert comment.has_liked is None
        assert comment.like_count is None

    def test_comment_author_summary_defaults(self):
        """Verify CommentAuthorSummary has sensible defaults."""
        author = CommentAuthorSummary(pk=1, username="test")
        assert author.full_name is None
        assert author.profile_pic_url is None

    def test_comment_page_defaults(self):
        """Verify CommentPage has sensible defaults."""
        page = CommentPage()
        assert page.comments == []
        assert page.next_cursor is None

    def test_comment_page_with_data(self):
        """Verify CommentPage can hold comments and cursor."""
        author = CommentAuthorSummary(pk=1, username="test")
        comments = [CommentSummary(pk=i, text=f"comment {i}", author=author) for i in range(3)]
        page = CommentPage(comments=comments, next_cursor="100")

        assert len(page.comments) == 3
        assert page.next_cursor == "100"


class TestCommentContractProofing:
    """Contract tests proving vendor types never leak into application code."""

    def test_comment_reader_returns_only_dtos_not_vendor_types(self):
        """Verify comment reader never returns vendor Comment objects."""
        # Create mock client
        mock_client = Mock()
        mock_comment = TestCommentReaderAdapter._create_mock_comment(pk=1)
        mock_client.media_comments.return_value = [mock_comment]

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCommentReaderAdapter(mock_repo)
        results = adapter.list_comments("acc-123", "media-456")

        # Verify result is only DTO, never raw vendor
        assert len(results) == 1
        assert isinstance(results[0], CommentSummary)
        # Vendor Comment fields should not be present
        assert not hasattr(results[0], "content_type_enum")  # vendor field

    def test_comment_page_contains_only_dtos(self):
        """Verify CommentPage contains DTOs, not vendor objects."""
        # Create mock client
        mock_client = Mock()
        mock_comment = TestCommentReaderAdapter._create_mock_comment(pk=1)
        mock_client.media_comments_chunk.return_value = ([mock_comment], 0)

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCommentReaderAdapter(mock_repo)
        result = adapter.list_comments_page("acc-123", "media-456", page_size=10)

        # Verify page contains only DTOs
        assert isinstance(result, CommentPage)
        assert len(result.comments) == 1
        assert isinstance(result.comments[0], CommentSummary)

    def test_author_uses_dto_not_vendor_user(self):
        """Verify comment author uses CommentAuthorSummary DTO."""
        # Create mock client
        mock_client = Mock()
        mock_comment = TestCommentReaderAdapter._create_mock_comment(pk=1)
        mock_client.media_comments.return_value = [mock_comment]

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramCommentReaderAdapter(mock_repo)
        results = adapter.list_comments("acc-123", "media-456")

        # Verify author is DTO
        assert isinstance(results[0].author, CommentAuthorSummary)
        # Vendor User fields should not be accessible
        assert not hasattr(results[0].author, "is_private")  # vendor field
