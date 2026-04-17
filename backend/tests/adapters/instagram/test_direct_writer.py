"""
Vendor contract tests for InstagramDirectWriterAdapter against instagrapi 2.3.0.

Pins two drift-prone call sites:

1. ``client.direct_thread_by_participants(user_ids)`` — the installed instagrapi
   2.3.0 source returns a raw dict (``mixins/direct.py:818``), while the public
   usage guide advertises a ``DirectThread`` model. A future release that flips
   the default shape would silently regress ``find_or_create_thread`` unless
   both branches are covered.

2. ``client.direct_answer(thread_id: int, text: str)`` — the canonical
   signature at ``mixins/direct.py:366`` takes ``thread_id`` as ``int``. The
   adapter coerces at the boundary; this test file locks in the coercion so a
   future relaxation to ``str | int`` does not change our call shape silently.
"""

from __future__ import annotations

from unittest.mock import Mock

from app.adapters.instagram.direct_writer import InstagramDirectWriterAdapter
from app.application.dto.instagram_direct_dto import DirectThreadSummary


# ---------------------------------------------------------------------------
# Fixtures — deterministic payloads shared by model and dict branch tests.
# ---------------------------------------------------------------------------

_THREAD_ID = "340282366841710300949128171234567890123"
_THREAD_PK = 178612312342
_USER_ID = 100
_USERNAME = "alice"
_MESSAGE_ID = "30076214123123123123123864"
_MESSAGE_TEXT = "hello"


def _build_model_thread() -> Mock:
    """DirectThread-shaped object with the same fields the vendor model exposes."""
    user = Mock()
    user.pk = _USER_ID
    user.username = _USERNAME
    user.full_name = "Alice A"
    user.profile_pic_url = "https://example.com/alice.jpg"
    user.is_private = False

    message = Mock()
    message.id = _MESSAGE_ID
    message.user_id = _USER_ID
    message.thread_id = _THREAD_ID
    message.timestamp = None
    message.item_type = "text"
    message.text = _MESSAGE_TEXT
    message.is_shh_mode = False

    thread = Mock()
    thread.id = _THREAD_ID
    thread.pk = _THREAD_PK
    thread.users = [user]
    thread.messages = [message]
    return thread


def _build_dict_payload() -> dict:
    """Raw dict payload matching instagrapi 2.3.0 ``direct_thread_by_participants``."""
    return {
        "thread_id": _THREAD_ID,
        "pk": _THREAD_PK,
        "users": [
            {
                "pk": _USER_ID,
                "username": _USERNAME,
                "full_name": "Alice A",
                "profile_pic_url": "https://example.com/alice.jpg",
                "is_private": False,
            }
        ],
        "items": [
            {
                "item_id": _MESSAGE_ID,
                "user_id": _USER_ID,
                "timestamp": 1700000000,
                "item_type": "text",
                "text": _MESSAGE_TEXT,
            }
        ],
    }


def _build_dict_payload_with_last_permanent_item() -> dict:
    """Dict payload using the ``last_permanent_item`` envelope instead of ``items``."""
    return {
        "thread_id": _THREAD_ID,
        "pk": _THREAD_PK,
        "users": [
            {
                "pk": _USER_ID,
                "username": _USERNAME,
            }
        ],
        "last_permanent_item": {
            "id": _MESSAGE_ID,
            "user_id": _USER_ID,
            "timestamp": 1700000000,
            "item_type": "text",
            "text": _MESSAGE_TEXT,
        },
    }


def _build_adapter_with_client(client: Mock) -> InstagramDirectWriterAdapter:
    repo = Mock()
    repo.get.return_value = client
    return InstagramDirectWriterAdapter(repo)


def _build_sent_message_mock() -> Mock:
    msg = Mock()
    msg.id = "sent-message-id"
    msg.user_id = 999
    msg.thread_id = None
    msg.timestamp = None
    msg.item_type = "text"
    msg.text = _MESSAGE_TEXT
    msg.is_shh_mode = False
    return msg


# ---------------------------------------------------------------------------
# find_or_create_thread — dual-shape contract
# ---------------------------------------------------------------------------


class TestFindOrCreateThreadVendorShapeContract:
    """``direct_thread_by_participants`` may return a model *or* a dict.

    Both branches must produce a ``DirectThreadSummary`` with the same
    structural contract so downstream DTO consumers are insulated from the
    vendor version in use.
    """

    def test_maps_direct_thread_model_response(self) -> None:
        client = Mock()
        client.direct_thread_by_participants.return_value = _build_model_thread()

        result = _build_adapter_with_client(client).find_or_create_thread("acc-1", [100])

        assert isinstance(result, DirectThreadSummary)
        assert result.direct_thread_id == _THREAD_ID
        assert result.pk == _THREAD_PK
        assert result.is_pending is False
        assert len(result.participants) == 1
        assert result.participants[0].user_id == _USER_ID
        assert result.participants[0].username == _USERNAME
        assert result.last_message is not None
        assert result.last_message.direct_message_id == _MESSAGE_ID
        assert result.last_message.text == _MESSAGE_TEXT
        client.direct_thread_by_participants.assert_called_once_with([100])

    def test_maps_dict_response_with_items_key(self) -> None:
        client = Mock()
        client.direct_thread_by_participants.return_value = _build_dict_payload()

        result = _build_adapter_with_client(client).find_or_create_thread("acc-1", [100])

        assert isinstance(result, DirectThreadSummary)
        assert result.direct_thread_id == _THREAD_ID
        assert result.pk == _THREAD_PK
        assert result.is_pending is False
        assert len(result.participants) == 1
        assert result.participants[0].user_id == _USER_ID
        assert result.participants[0].username == _USERNAME
        assert result.last_message is not None
        assert result.last_message.direct_message_id == _MESSAGE_ID
        assert result.last_message.text == _MESSAGE_TEXT
        client.direct_thread_by_participants.assert_called_once_with([100])

    def test_maps_dict_response_with_last_permanent_item_key(self) -> None:
        client = Mock()
        client.direct_thread_by_participants.return_value = (
            _build_dict_payload_with_last_permanent_item()
        )

        result = _build_adapter_with_client(client).find_or_create_thread("acc-1", [100])

        assert isinstance(result, DirectThreadSummary)
        assert result.direct_thread_id == _THREAD_ID
        assert result.pk == _THREAD_PK
        assert result.last_message is not None
        assert result.last_message.direct_message_id == _MESSAGE_ID
        assert result.last_message.text == _MESSAGE_TEXT

    def test_dict_and_model_share_same_structural_contract(self) -> None:
        """Guard invariant: switching between the two vendor shapes changes
        nothing a downstream consumer of ``DirectThreadSummary`` can observe.
        """
        model_client = Mock()
        model_client.direct_thread_by_participants.return_value = _build_model_thread()

        dict_client = Mock()
        dict_client.direct_thread_by_participants.return_value = _build_dict_payload()

        model_result = _build_adapter_with_client(model_client).find_or_create_thread(
            "acc-1", [100]
        )
        dict_result = _build_adapter_with_client(dict_client).find_or_create_thread(
            "acc-1", [100]
        )

        assert model_result.direct_thread_id == dict_result.direct_thread_id
        assert model_result.pk == dict_result.pk
        assert model_result.is_pending == dict_result.is_pending
        assert len(model_result.participants) == len(dict_result.participants)
        assert model_result.participants[0].user_id == dict_result.participants[0].user_id
        assert (
            model_result.participants[0].username == dict_result.participants[0].username
        )
        assert model_result.last_message is not None
        assert dict_result.last_message is not None
        assert (
            model_result.last_message.direct_message_id
            == dict_result.last_message.direct_message_id
        )
        assert model_result.last_message.text == dict_result.last_message.text


# ---------------------------------------------------------------------------
# send_to_thread — direct_answer canonical int signature
# ---------------------------------------------------------------------------


class TestSendToThreadCanonicalSignature:
    """Canonical ``direct_answer(thread_id: int, text: str)`` call shape.

    Pinning the int coercion guards against two drift modes:
    - a vendor bump that relaxes ``thread_id`` to ``str | int`` (we keep int);
    - a local refactor that drops the coercion and lets string ids leak through.
    """

    def test_calls_direct_answer_with_int_thread_id_from_integer_string(self) -> None:
        client = Mock()
        client.direct_answer.return_value = _build_sent_message_mock()

        _build_adapter_with_client(client).send_to_thread("acc-1", "12345", "hi")

        client.direct_answer.assert_called_once_with(12345, "hi")
        (thread_arg, text_arg), _ = client.direct_answer.call_args
        assert type(thread_arg) is int
        assert text_arg == "hi"

    def test_coerces_large_numeric_string_thread_id_to_int(self) -> None:
        """Instagram thread ids are 39-digit snowflake-like numbers; coercion
        must preserve their exact value rather than overflow or round-trip
        through float.
        """
        client = Mock()
        client.direct_answer.return_value = _build_sent_message_mock()
        large_thread_id = "340282366841710300949128171234567890123"

        _build_adapter_with_client(client).send_to_thread(
            "acc-1", large_thread_id, _MESSAGE_TEXT
        )

        expected_int = int(large_thread_id)
        client.direct_answer.assert_called_once_with(expected_int, _MESSAGE_TEXT)
        (thread_arg, _text_arg), _ = client.direct_answer.call_args
        assert type(thread_arg) is int
        assert thread_arg == expected_int
