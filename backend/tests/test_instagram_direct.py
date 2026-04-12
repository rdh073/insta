"""
Tests for Instagram direct message reader, writer, and DTO mappings.

Verifies that instagrapi DirectThread and DirectMessage objects map correctly
to stable application DTOs while ensuring direct_thread_id naming avoids
collision with workflow thread_id.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock

from app.application.dto.instagram_direct_dto import (
    DirectParticipantSummary,
    DirectMessageSummary,
    DirectThreadSummary,
    DirectThreadDetail,
    DirectActionReceipt,
)
from app.adapters.instagram.direct_reader import (
    InstagramDirectReaderAdapter,
)
from app.adapters.instagram.direct_writer import (
    InstagramDirectWriterAdapter,
)


class TestDirectReaderAdapter:
    """Test the direct message reader adapter mappings."""

    def test_list_inbox_threads(self):
        """Verify direct_threads() maps to DirectThreadSummary list."""
        # Create mock client
        mock_client = Mock()
        mock_threads = [
            self._create_mock_thread(id="thread-1", pk=1),
            self._create_mock_thread(id="thread-2", pk=2),
        ]
        mock_client.direct_threads.return_value = mock_threads

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDirectReaderAdapter(mock_repo)
        results = adapter.list_inbox_threads("acc-123", amount=20)

        assert len(results) == 2
        assert all(isinstance(r, DirectThreadSummary) for r in results)
        assert results[0].direct_thread_id == "thread-1"
        assert results[1].direct_thread_id == "thread-2"
        assert results[0].is_pending is False
        mock_client.direct_threads.assert_called_once()

    def test_list_pending_threads(self):
        """Verify direct_pending_inbox() maps pending threads."""
        # Create mock client
        mock_client = Mock()
        mock_threads = [self._create_mock_thread(id="pending-1", pk=100)]
        mock_client.direct_pending_inbox.return_value = mock_threads

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDirectReaderAdapter(mock_repo)
        results = adapter.list_pending_threads("acc-123")

        assert len(results) == 1
        assert results[0].direct_thread_id == "pending-1"
        assert results[0].is_pending is True
        mock_client.direct_pending_inbox.assert_called_once()

    def test_get_thread(self):
        """Verify direct_thread() maps to DirectThreadDetail."""
        # Create mock client
        mock_client = Mock()
        mock_message1 = self._create_mock_message(id="msg-1", text="First")
        mock_message2 = self._create_mock_message(id="msg-2", text="Second")
        mock_thread = self._create_mock_thread(
            id="thread-1", pk=1, messages=[mock_message1, mock_message2]
        )
        mock_client.direct_thread.return_value = mock_thread

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDirectReaderAdapter(mock_repo)
        result = adapter.get_thread("acc-123", "thread-1")

        assert isinstance(result, DirectThreadDetail)
        assert result.summary.direct_thread_id == "thread-1"
        assert len(result.messages) == 2
        assert result.messages[0].text == "First"
        assert result.messages[1].text == "Second"

    def test_list_messages(self):
        """Verify direct_messages() maps message list."""
        # Create mock client
        mock_client = Mock()
        mock_messages = [
            self._create_mock_message(id="msg-1", text="Message 1"),
            self._create_mock_message(id="msg-2", text="Message 2"),
        ]
        mock_client.direct_messages.return_value = mock_messages

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDirectReaderAdapter(mock_repo)
        results = adapter.list_messages("acc-123", "thread-1")

        assert len(results) == 2
        assert all(isinstance(r, DirectMessageSummary) for r in results)
        assert results[0].direct_message_id == "msg-1"
        assert results[1].direct_message_id == "msg-2"

    def test_search_threads(self):
        """Verify direct_search() maps search results."""
        # Create mock client
        mock_client = Mock()
        mock_threads = [self._create_mock_thread(id="search-result-1")]
        mock_client.direct_search.return_value = mock_threads

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDirectReaderAdapter(mock_repo)
        results = adapter.search_threads("acc-123", "username")

        assert len(results) == 1
        assert results[0].direct_thread_id == "search-result-1"

    def test_participants_extraction(self):
        """Verify thread participants are extracted."""
        # Create mock client
        mock_client = Mock()
        mock_user1 = Mock()
        mock_user1.pk = 100
        mock_user1.username = "user1"
        mock_user1.full_name = "User One"
        mock_user1.profile_pic_url = "https://example.com/user1.jpg"
        mock_user1.is_private = False

        mock_user2 = Mock()
        mock_user2.pk = 101
        mock_user2.username = "user2"
        mock_user2.full_name = "User Two"
        mock_user2.is_private = True

        mock_thread = self._create_mock_thread(id="thread-1", users=[mock_user1, mock_user2])
        mock_client.direct_threads.return_value = [mock_thread]

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDirectReaderAdapter(mock_repo)
        results = adapter.list_inbox_threads("acc-123")

        assert len(results[0].participants) == 2
        assert all(isinstance(p, DirectParticipantSummary) for p in results[0].participants)
        assert results[0].participants[0].username == "user1"
        assert results[0].participants[1].is_private is True

    def test_missing_client_error(self):
        """Verify proper error when client not found."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramDirectReaderAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.list_inbox_threads("acc-123")

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.get_thread("acc-123", "thread-1")

    def test_null_field_handling(self):
        """Verify None/null fields are handled gracefully."""
        # Create mock client with minimal data
        mock_client = Mock()
        mock_message = Mock()
        mock_message.id = "msg-1"
        mock_message.text = None
        mock_message.user_id = None
        mock_message.timestamp = None
        mock_message.item_type = None
        mock_message.is_shh_mode = None

        mock_client.direct_messages.return_value = [mock_message]

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDirectReaderAdapter(mock_repo)
        results = adapter.list_messages("acc-123", "thread-1")

        assert results[0].text is None
        assert results[0].sender_user_id is None
        assert results[0].sent_at is None

    @staticmethod
    def _create_mock_thread(id="1", pk=None, users=None, messages=None):
        """Create a mock DirectThread object."""
        mock = Mock()
        mock.id = id
        mock.pk = pk or 1
        mock.users = users or []
        mock.messages = messages or []
        return mock

    @staticmethod
    def _create_mock_message(id="1", text="Test message"):
        """Create a mock DirectMessage object."""
        mock = Mock()
        mock.id = id
        mock.text = text
        mock.user_id = 100
        mock.thread_id = "thread-1"
        mock.timestamp = datetime(2023, 1, 1, tzinfo=timezone.utc)
        mock.item_type = "text"
        mock.is_shh_mode = False
        return mock


class TestDirectWriterAdapter:
    """Test the direct message writer adapter."""

    def test_find_or_create_thread(self):
        """Verify direct_thread_by_participants() creates thread."""
        # Create mock client
        mock_client = Mock()
        created_thread = TestDirectReaderAdapter._create_mock_thread(id="new-thread")
        mock_client.direct_thread_by_participants.return_value = created_thread

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDirectWriterAdapter(mock_repo)
        result = adapter.find_or_create_thread("acc-123", [100, 101])

        assert isinstance(result, DirectThreadSummary)
        assert result.direct_thread_id == "new-thread"
        mock_client.direct_thread_by_participants.assert_called_once_with([100, 101])

    def test_find_or_create_thread_maps_existing_dict_payload(self):
        """Verify dict payload with thread envelope maps deterministically."""
        mock_client = Mock()
        mock_client.direct_thread_by_participants.return_value = {
            "status": "ok",
            "thread": {
                "thread_id": "340282366841710300949128171234567890123",
                "pk": "178612312342",
                "users": [
                    {
                        "pk": "100",
                        "username": "alice",
                        "full_name": "Alice A",
                        "profile_pic_url": "https://example.com/alice.jpg",
                        "is_private": False,
                    },
                    {
                        "pk": 101,
                        "username": "bob",
                        "full_name": "Bob B",
                        "is_private": True,
                    },
                ],
                "items": [
                    {
                        "item_id": "30076214123123123123123864",
                        "user_id": "100",
                        "timestamp": "1700000000000000",
                        "item_type": "text",
                        "text": "hello from existing thread",
                        "is_shh_mode": False,
                    }
                ],
            },
        }

        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        adapter = InstagramDirectWriterAdapter(mock_repo)
        result = adapter.find_or_create_thread("acc-123", [100, 101])

        assert result.direct_thread_id == "340282366841710300949128171234567890123"
        assert result.pk == 178612312342
        assert len(result.participants) == 2
        assert result.participants[0].user_id == 100
        assert result.participants[0].username == "alice"
        assert result.participants[1].username == "bob"
        assert result.last_message is not None
        assert result.last_message.direct_message_id == "30076214123123123123123864"
        assert result.last_message.direct_thread_id == result.direct_thread_id
        assert result.last_message.sender_user_id == 100
        assert result.last_message.text == "hello from existing thread"
        assert result.last_message.item_type == "text"
        assert isinstance(result.last_message.sent_at, datetime)
        assert result.last_message.sent_at.tzinfo == timezone.utc

    def test_find_or_create_thread_maps_new_thread_dict_payload(self):
        """Verify direct dict payload (without thread envelope) maps correctly."""
        mock_client = Mock()
        mock_client.direct_thread_by_participants.return_value = {
            "id": "340282366841710300949128171234567890999",
            "pk": 178612300099,
            "users": [{"id": 777, "username": "newfriend"}],
            "last_permanent_item": {
                "id": "msg-new-1",
                "sender_id": 777,
                "timestamp": 1700000100,
                "item_type": "text",
                "text": "first message",
            },
        }

        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        adapter = InstagramDirectWriterAdapter(mock_repo)
        result = adapter.find_or_create_thread("acc-123", [777])

        assert result.direct_thread_id == "340282366841710300949128171234567890999"
        assert result.pk == 178612300099
        assert len(result.participants) == 1
        assert result.participants[0].user_id == 777
        assert result.participants[0].username == "newfriend"
        assert result.last_message is not None
        assert result.last_message.direct_message_id == "msg-new-1"
        assert result.last_message.sender_user_id == 777
        assert result.last_message.text == "first message"
        assert result.last_message.item_type == "text"

    def test_find_or_create_thread_maps_partial_dict_payload(self):
        """Verify partial dict payload maps without attribute errors."""
        mock_client = Mock()
        mock_client.direct_thread_by_participants.return_value = {
            "thread": {
                "thread_id": "partial-thread-1",
                "users": [{"pk": "321"}],  # no username/full_name/profile fields
            }
        }

        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        adapter = InstagramDirectWriterAdapter(mock_repo)
        result = adapter.find_or_create_thread("acc-123", [321])

        assert result.direct_thread_id == "partial-thread-1"
        assert result.pk is None
        assert len(result.participants) == 1
        assert result.participants[0].user_id == 321
        assert result.participants[0].username == ""
        assert result.last_message is None

    def test_send_to_thread(self):
        """Verify direct_answer() sends message to thread."""
        # Create mock client
        mock_client = Mock()
        sent_message = TestDirectReaderAdapter._create_mock_message(id="sent-1")
        mock_client.direct_answer.return_value = sent_message

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDirectWriterAdapter(mock_repo)
        result = adapter.send_to_thread("acc-123", "thread-1", "Hello")

        assert isinstance(result, DirectMessageSummary)
        assert result.direct_message_id == "sent-1"
        mock_client.direct_answer.assert_called_once_with("thread-1", "Hello")

    def test_send_to_users(self):
        """Verify direct_send() sends message to users."""
        # Create mock client
        mock_client = Mock()
        sent_message = TestDirectReaderAdapter._create_mock_message(id="sent-2")
        mock_client.direct_send.return_value = sent_message

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDirectWriterAdapter(mock_repo)
        result = adapter.send_to_users("acc-123", [100, 101], "Hi there")

        assert isinstance(result, DirectMessageSummary)
        assert result.direct_message_id == "sent-2"
        mock_client.direct_send.assert_called_once_with("Hi there", user_ids=[100, 101])

    def test_delete_message(self):
        """Verify direct_message_delete() deletes message."""
        # Create mock client
        mock_client = Mock()
        mock_client.direct_message_delete.return_value = None

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDirectWriterAdapter(mock_repo)
        result = adapter.delete_message("acc-123", "thread-1", "msg-1")

        assert isinstance(result, DirectActionReceipt)
        assert result.success is True
        assert result.action_id == "msg-1"
        mock_client.direct_message_delete.assert_called_once_with("thread-1", "msg-1")

    def test_delete_message_failure(self):
        """Verify delete failure is captured."""
        # Create mock client
        mock_client = Mock()
        mock_client.direct_message_delete.side_effect = Exception("Delete failed")

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDirectWriterAdapter(mock_repo)
        result = adapter.delete_message("acc-123", "thread-1", "msg-1")

        assert isinstance(result, DirectActionReceipt)
        assert result.success is False
        assert result.action_id == "msg-1"

    def test_missing_client_error(self):
        """Verify proper error when client not found."""
        # Create mock repo that returns None
        mock_repo = Mock()
        mock_repo.get.return_value = None

        adapter = InstagramDirectWriterAdapter(mock_repo)

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.find_or_create_thread("acc-123", [100])

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.send_to_thread("acc-123", "thread-1", "text")

        with pytest.raises(ValueError, match="not found or not authenticated"):
            adapter.send_to_users("acc-123", [100], "text")


class TestDirectDTOs:
    """Test the direct message DTO properties."""

    def test_thread_summary_frozen(self):
        """Verify DirectThreadSummary is immutable."""
        thread = DirectThreadSummary(direct_thread_id="1")
        with pytest.raises(AttributeError):
            thread.direct_thread_id = "2"

    def test_message_summary_frozen(self):
        """Verify DirectMessageSummary is immutable."""
        message = DirectMessageSummary(direct_message_id="1")
        with pytest.raises(AttributeError):
            message.direct_message_id = "2"

    def test_thread_detail_frozen(self):
        """Verify DirectThreadDetail is immutable."""
        summary = DirectThreadSummary(direct_thread_id="1")
        detail = DirectThreadDetail(summary=summary)
        with pytest.raises(AttributeError):
            detail.summary = None

    def test_action_receipt_frozen(self):
        """Verify DirectActionReceipt is immutable."""
        receipt = DirectActionReceipt(action_id="1", success=True)
        with pytest.raises(AttributeError):
            receipt.success = False

    def test_naming_uses_direct_thread_id(self):
        """Verify DTO uses direct_thread_id, not plain thread_id."""
        thread = DirectThreadSummary(direct_thread_id="thread-123")
        message = DirectMessageSummary(
            direct_message_id="msg-1", direct_thread_id="thread-123"
        )

        # Key assertion: names are unambiguous
        assert thread.direct_thread_id == "thread-123"
        assert message.direct_thread_id == "thread-123"
        # Plain thread_id should NOT exist
        assert not hasattr(thread, "thread_id")
        assert not hasattr(message, "thread_id")

    def test_thread_summary_defaults(self):
        """Verify DirectThreadSummary has sensible defaults."""
        thread = DirectThreadSummary(direct_thread_id="1")
        assert thread.pk is None
        assert thread.participants == []
        assert thread.last_message is None
        assert thread.is_pending is False


class TestDirectContractProofing:
    """Contract tests proving vendor types never leak into application code."""

    def test_thread_reader_returns_only_dtos(self):
        """Verify thread reader never returns vendor DirectThread objects."""
        # Create mock client
        mock_client = Mock()
        mock_thread = TestDirectReaderAdapter._create_mock_thread(id="1")
        mock_client.direct_threads.return_value = [mock_thread]

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDirectReaderAdapter(mock_repo)
        results = adapter.list_inbox_threads("acc-123")

        # Verify result is only DTO, never raw vendor
        assert isinstance(results[0], DirectThreadSummary)
        assert not hasattr(results[0], "users")  # vendor field

    def test_message_reader_returns_only_dtos(self):
        """Verify message reader never returns vendor DirectMessage objects."""
        # Create mock client
        mock_client = Mock()
        mock_message = TestDirectReaderAdapter._create_mock_message(id="1")
        mock_client.direct_messages.return_value = [mock_message]

        # Create mock repo
        mock_repo = Mock()
        mock_repo.get.return_value = mock_client

        # Test adapter
        adapter = InstagramDirectReaderAdapter(mock_repo)
        results = adapter.list_messages("acc-123", "thread-1")

        # Verify result is only DTO
        assert isinstance(results[0], DirectMessageSummary)
        # Vendor DirectMessage fields should not be accessible
        assert not hasattr(results[0], "item_type_enum")  # vendor field

    def test_naming_convention_respected(self):
        """Verify direct_thread_id and direct_message_id used throughout."""
        # Create thread and message DTOs
        thread = DirectThreadSummary(direct_thread_id="thread-xyz")
        message = DirectMessageSummary(
            direct_message_id="msg-abc", direct_thread_id="thread-xyz"
        )
        detail = DirectThreadDetail(summary=thread, messages=[message])

        # Verify naming is unambiguous everywhere
        assert thread.direct_thread_id == "thread-xyz"
        assert message.direct_message_id == "msg-abc"
        assert message.direct_thread_id == "thread-xyz"
        assert detail.summary.direct_thread_id == "thread-xyz"
