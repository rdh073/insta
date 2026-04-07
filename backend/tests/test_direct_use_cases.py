"""Use-case tests for DirectUseCases.

Tests the application orchestration layer using port doubles (stubs/fakes).
No instagrapi imports — all vendor types stay behind the port boundary.
Covers:
  - Preconditions: account not found, account not authenticated
  - direct_thread_id and direct_message_id validation (non-empty string)
  - amount and thread_message_limit validation (>= 1)
  - query normalization for search_threads
  - participant_user_ids / user_ids validation (non-empty, all positive integers)
  - text validation for send operations
  - Identity seam: send_to_username and find_or_create_thread_with_usernames
    delegate username resolution to IdentityUseCases
  - Port not called when preconditions or validation fails
  - DTO boundary: only app-owned types returned
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.application.dto.instagram_direct_dto import (
    DirectActionReceipt,
    DirectMessageSummary,
    DirectThreadDetail,
    DirectThreadSummary,
)
from app.application.dto.instagram_identity_dto import PublicUserProfile
from app.application.use_cases.direct import DirectUseCases


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_thread(direct_thread_id: str = "thread-1") -> DirectThreadSummary:
    return DirectThreadSummary(direct_thread_id=direct_thread_id)


def _make_thread_detail(direct_thread_id: str = "thread-1") -> DirectThreadDetail:
    return DirectThreadDetail(summary=_make_thread(direct_thread_id))


def _make_message(direct_message_id: str = "msg-1") -> DirectMessageSummary:
    return DirectMessageSummary(direct_message_id=direct_message_id)


def _make_receipt(action_id: str = "act-1") -> DirectActionReceipt:
    return DirectActionReceipt(action_id=action_id, success=True)


def _make_profile(pk: int = 42, username: str = "testuser") -> PublicUserProfile:
    return PublicUserProfile(pk=pk, username=username)


def _build_use_cases(
    *,
    account_exists: bool = True,
    client_exists: bool = True,
    reader: Mock | None = None,
    writer: Mock | None = None,
    identity: Mock | None = None,
) -> tuple[DirectUseCases, Mock, Mock, Mock]:
    account_repo = Mock()
    account_repo.get.return_value = {"username": "testuser"} if account_exists else None

    client_repo = Mock()
    client_repo.exists.return_value = client_exists

    if reader is None:
        reader = Mock()
    if writer is None:
        writer = Mock()
    if identity is None:
        identity = Mock()

    uc = DirectUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        direct_reader=reader,
        direct_writer=writer,
        identity_use_cases=identity,
    )
    return uc, reader, writer, identity


# ---------------------------------------------------------------------------
# Preconditions: account not found
# ---------------------------------------------------------------------------

class TestAccountPreconditions:
    def test_list_inbox_raises_if_account_missing(self):
        uc, _, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.list_inbox_threads("no-such")

    def test_get_thread_raises_if_account_missing(self):
        uc, _, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.get_thread("no-such", "thread-1")

    def test_send_to_thread_raises_if_account_missing(self):
        uc, _, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.send_to_thread("no-such", "thread-1", "Hi!")

    def test_delete_message_raises_if_account_missing(self):
        uc, _, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.delete_message("no-such", "thread-1", "msg-1")


# ---------------------------------------------------------------------------
# Preconditions: account not authenticated
# ---------------------------------------------------------------------------

class TestAuthPreconditions:
    def test_list_inbox_raises_if_not_authenticated(self):
        uc, _, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.list_inbox_threads("acc-1")

    def test_send_to_users_raises_if_not_authenticated(self):
        uc, _, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.send_to_users("acc-1", [123], "Hi!")

    def test_search_threads_raises_if_not_authenticated(self):
        uc, _, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.search_threads("acc-1", "john")


# ---------------------------------------------------------------------------
# direct_thread_id validation
# ---------------------------------------------------------------------------

class TestThreadIdValidation:
    def test_rejects_empty_thread_id(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="direct_thread_id"):
            uc.get_thread("acc-1", "")

    def test_rejects_whitespace_thread_id(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="direct_thread_id"):
            uc.get_thread("acc-1", "   ")

    def test_strips_thread_id_before_delegating(self):
        uc, reader, _, _ = _build_use_cases()
        reader.get_thread.return_value = _make_thread_detail()

        uc.get_thread("acc-1", "  thread-99  ")

        reader.get_thread.assert_called_once_with("acc-1", "thread-99", 20)

    def test_send_to_thread_rejects_empty_thread_id(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="direct_thread_id"):
            uc.send_to_thread("acc-1", "", "Hi!")

    def test_delete_rejects_empty_thread_id(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="direct_thread_id"):
            uc.delete_message("acc-1", "", "msg-1")


# ---------------------------------------------------------------------------
# direct_message_id validation
# ---------------------------------------------------------------------------

class TestMessageIdValidation:
    def test_rejects_empty_message_id(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="direct_message_id"):
            uc.delete_message("acc-1", "thread-1", "")

    def test_rejects_whitespace_message_id(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="direct_message_id"):
            uc.delete_message("acc-1", "thread-1", "   ")

    def test_strips_message_id_before_delegating(self):
        uc, _, writer, _ = _build_use_cases()
        writer.delete_message.return_value = _make_receipt()

        uc.delete_message("acc-1", "thread-1", "  msg-99  ")

        writer.delete_message.assert_called_once_with("acc-1", "thread-1", "msg-99")


# ---------------------------------------------------------------------------
# amount / thread_message_limit validation
# ---------------------------------------------------------------------------

class TestAmountValidation:
    def test_rejects_zero_amount(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="amount"):
            uc.list_inbox_threads("acc-1", amount=0)

    def test_rejects_negative_amount(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="amount"):
            uc.list_pending_threads("acc-1", amount=-1)

    def test_rejects_zero_thread_message_limit(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="thread_message_limit"):
            uc.list_inbox_threads("acc-1", thread_message_limit=0)

    def test_defaults_passed_to_port(self):
        uc, reader, _, _ = _build_use_cases()
        reader.list_inbox_threads.return_value = []

        uc.list_inbox_threads("acc-1")

        reader.list_inbox_threads.assert_called_once_with("acc-1", 20, "", 10)

    def test_custom_amount_passed_to_port(self):
        uc, reader, _, _ = _build_use_cases()
        reader.list_pending_threads.return_value = []

        uc.list_pending_threads("acc-1", amount=5)

        reader.list_pending_threads.assert_called_once_with("acc-1", 5)


# ---------------------------------------------------------------------------
# search_threads: query normalization
# ---------------------------------------------------------------------------

class TestSearchThreadsValidation:
    def test_rejects_empty_query(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="query"):
            uc.search_threads("acc-1", "")

    def test_rejects_whitespace_query(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="query"):
            uc.search_threads("acc-1", "   ")

    def test_strips_query_before_delegating(self):
        uc, reader, _, _ = _build_use_cases()
        reader.search_threads.return_value = []

        uc.search_threads("acc-1", "  john  ")

        reader.search_threads.assert_called_once_with("acc-1", "john")


# ---------------------------------------------------------------------------
# find_or_create_thread / send_to_users: user_ids validation
# ---------------------------------------------------------------------------

class TestUserIdsValidation:
    def test_find_or_create_rejects_empty_user_ids(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="participant_user_ids"):
            uc.find_or_create_thread("acc-1", [])

    def test_find_or_create_rejects_zero_user_id(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integers"):
            uc.find_or_create_thread("acc-1", [0])

    def test_find_or_create_rejects_negative_user_id(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integers"):
            uc.find_or_create_thread("acc-1", [1, -2])

    def test_send_to_users_rejects_empty_user_ids(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="user_ids"):
            uc.send_to_users("acc-1", [], "Hi!")

    def test_find_or_create_delegates_valid_ids(self):
        uc, _, writer, _ = _build_use_cases()
        writer.find_or_create_thread.return_value = _make_thread()

        uc.find_or_create_thread("acc-1", [100, 200])

        writer.find_or_create_thread.assert_called_once_with("acc-1", [100, 200])


# ---------------------------------------------------------------------------
# Text validation for send operations
# ---------------------------------------------------------------------------

class TestTextValidation:
    def test_send_to_thread_rejects_empty_text(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="text"):
            uc.send_to_thread("acc-1", "thread-1", "")

    def test_send_to_thread_rejects_whitespace_text(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="text"):
            uc.send_to_thread("acc-1", "thread-1", "   ")

    def test_send_to_thread_strips_text(self):
        uc, _, writer, _ = _build_use_cases()
        writer.send_to_thread.return_value = _make_message()

        uc.send_to_thread("acc-1", "thread-1", "  Hello!  ")

        args = writer.send_to_thread.call_args[0]
        assert args[2] == "Hello!"

    def test_send_to_users_rejects_empty_text(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="text"):
            uc.send_to_users("acc-1", [100], "")

    def test_send_to_username_rejects_empty_text(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="text"):
            uc.send_to_username("acc-1", "john", "")


# ---------------------------------------------------------------------------
# Identity resolution seam
# ---------------------------------------------------------------------------

class TestIdentityResolution:
    def test_send_to_username_resolves_via_identity(self):
        uc, _, writer, identity = _build_use_cases()
        identity.get_public_user_by_username.return_value = _make_profile(pk=999)
        writer.send_to_users.return_value = _make_message()

        uc.send_to_username("acc-1", "john", "Hi!")

        identity.get_public_user_by_username.assert_called_once_with("acc-1", "john")
        writer.send_to_users.assert_called_once_with("acc-1", [999], "Hi!")

    def test_find_or_create_with_usernames_resolves_each(self):
        uc, _, writer, identity = _build_use_cases()
        identity.get_public_user_by_username.side_effect = [
            _make_profile(pk=10, username="alice"),
            _make_profile(pk=20, username="bob"),
        ]
        writer.find_or_create_thread.return_value = _make_thread()

        uc.find_or_create_thread_with_usernames("acc-1", ["alice", "bob"])

        assert identity.get_public_user_by_username.call_count == 2
        writer.find_or_create_thread.assert_called_once_with("acc-1", [10, 20])

    def test_find_or_create_with_usernames_rejects_empty_list(self):
        uc, _, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="usernames"):
            uc.find_or_create_thread_with_usernames("acc-1", [])

    def test_send_to_username_propagates_identity_error(self):
        uc, _, _, identity = _build_use_cases()
        identity.get_public_user_by_username.side_effect = ValueError("User not found")

        with pytest.raises(ValueError, match="User not found"):
            uc.send_to_username("acc-1", "ghost", "Hi!")


# ---------------------------------------------------------------------------
# Port not called when preconditions or validation fails
# ---------------------------------------------------------------------------

class TestPortNotCalledOnFailure:
    def test_reader_not_called_when_account_missing(self):
        uc, reader, _, _ = _build_use_cases(account_exists=False)

        with pytest.raises(ValueError):
            uc.list_inbox_threads("acc-1")

        reader.list_inbox_threads.assert_not_called()

    def test_writer_not_called_on_empty_text(self):
        uc, _, writer, _ = _build_use_cases()

        with pytest.raises(ValueError):
            uc.send_to_thread("acc-1", "thread-1", "")

        writer.send_to_thread.assert_not_called()

    def test_identity_not_called_on_empty_text(self):
        uc, _, _, identity = _build_use_cases()

        with pytest.raises(ValueError):
            uc.send_to_username("acc-1", "john", "")

        identity.get_public_user_by_username.assert_not_called()

    def test_writer_not_called_on_invalid_user_ids(self):
        uc, _, writer, _ = _build_use_cases()

        with pytest.raises(ValueError):
            uc.find_or_create_thread("acc-1", [])

        writer.find_or_create_thread.assert_not_called()


# ---------------------------------------------------------------------------
# DTO boundary: only app-owned types returned
# ---------------------------------------------------------------------------

class TestDTOBoundary:
    def test_list_inbox_returns_thread_summaries(self):
        uc, reader, _, _ = _build_use_cases()
        reader.list_inbox_threads.return_value = [_make_thread(f"t{i}") for i in range(3)]

        results = uc.list_inbox_threads("acc-1")

        assert all(isinstance(r, DirectThreadSummary) for r in results)

    def test_get_thread_returns_thread_detail(self):
        uc, reader, _, _ = _build_use_cases()
        reader.get_thread.return_value = _make_thread_detail()

        result = uc.get_thread("acc-1", "thread-1")

        assert isinstance(result, DirectThreadDetail)

    def test_list_messages_returns_message_summaries(self):
        uc, reader, _, _ = _build_use_cases()
        reader.list_messages.return_value = [_make_message(f"m{i}") for i in range(3)]

        results = uc.list_messages("acc-1", "thread-1")

        assert all(isinstance(r, DirectMessageSummary) for r in results)

    def test_send_to_thread_returns_message_summary(self):
        uc, _, writer, _ = _build_use_cases()
        writer.send_to_thread.return_value = _make_message()

        result = uc.send_to_thread("acc-1", "thread-1", "Hi!")

        assert isinstance(result, DirectMessageSummary)

    def test_delete_message_returns_action_receipt(self):
        uc, _, writer, _ = _build_use_cases()
        writer.delete_message.return_value = _make_receipt()

        result = uc.delete_message("acc-1", "thread-1", "msg-1")

        assert isinstance(result, DirectActionReceipt)

    def test_send_to_username_returns_message_summary(self):
        uc, _, writer, identity = _build_use_cases()
        identity.get_public_user_by_username.return_value = _make_profile()
        writer.send_to_users.return_value = _make_message()

        result = uc.send_to_username("acc-1", "john", "Hi!")

        assert isinstance(result, DirectMessageSummary)
