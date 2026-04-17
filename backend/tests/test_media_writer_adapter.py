"""Adapter tests for InstagramMediaWriterAdapter.

Asserts each adapter method calls the exact instagrapi vendor method name +
signature verified in the plan's Evidence section, and that exceptions are
translated through the failure catalog (no raw vendor strings leak).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.adapters.instagram.media_writer import InstagramMediaWriterAdapter
from app.application.dto.instagram_media_dto import MediaActionReceipt


class _StubClientRepo:
    """Minimal client repository: returns a single mock client for any account_id."""

    def __init__(self, client):
        self._client = client

    def get(self, _account_id):
        return self._client


def _adapter_with_client(client):
    return InstagramMediaWriterAdapter(_StubClientRepo(client)), client


# ---------------------------------------------------------------------------
# Happy-path: vendor method name + signature
# ---------------------------------------------------------------------------

class TestVendorCallSignatures:
    """Each adapter method must invoke the exact instagrapi method name."""

    def test_like_calls_media_like(self):
        client = MagicMock()
        client.media_like.return_value = True
        adapter, _ = _adapter_with_client(client)

        result = adapter.like_media("acc-1", "10_20")

        assert result is True
        client.media_like.assert_called_once_with("10_20")

    def test_unlike_calls_media_unlike(self):
        client = MagicMock()
        client.media_unlike.return_value = True
        adapter, _ = _adapter_with_client(client)

        adapter.unlike_media("acc-1", "10_20")

        client.media_unlike.assert_called_once_with("10_20")

    def test_edit_caption_calls_media_edit(self):
        client = MagicMock()
        client.media_edit.return_value = {"status": "ok"}
        adapter, _ = _adapter_with_client(client)

        receipt = adapter.edit_caption("acc-1", "10_20", "new caption")

        client.media_edit.assert_called_once_with("10_20", "new caption")
        assert receipt == MediaActionReceipt(
            action_id="10_20", success=True, reason="Caption updated"
        )

    def test_delete_calls_media_delete(self):
        client = MagicMock()
        client.media_delete.return_value = True
        adapter, _ = _adapter_with_client(client)

        receipt = adapter.delete_media("acc-1", "10_20")

        client.media_delete.assert_called_once_with("10_20")
        assert receipt.success
        assert receipt.action_id == "10_20"
        assert receipt.reason == "Media deleted"

    def test_pin_converts_id_to_pk_then_calls_media_pin(self):
        client = MagicMock()
        client.media_pk.return_value = "10"  # pk segment of media_id "10_20"
        client.media_pin.return_value = True
        adapter, _ = _adapter_with_client(client)

        receipt = adapter.pin_media("acc-1", "10_20")

        client.media_pk.assert_called_once_with("10_20")
        client.media_pin.assert_called_once_with("10")
        assert receipt.success
        assert receipt.reason == "Media pinned"

    def test_unpin_converts_id_to_pk_then_calls_media_unpin(self):
        client = MagicMock()
        client.media_pk.return_value = "10"
        client.media_unpin.return_value = True
        adapter, _ = _adapter_with_client(client)

        adapter.unpin_media("acc-1", "10_20")

        client.media_pk.assert_called_once_with("10_20")
        client.media_unpin.assert_called_once_with("10")

    def test_archive_calls_media_archive(self):
        client = MagicMock()
        client.media_archive.return_value = True
        adapter, _ = _adapter_with_client(client)

        adapter.archive_media("acc-1", "10_20")

        client.media_archive.assert_called_once_with("10_20")

    def test_unarchive_calls_media_unarchive(self):
        client = MagicMock()
        client.media_unarchive.return_value = True
        adapter, _ = _adapter_with_client(client)

        adapter.unarchive_media("acc-1", "10_20")

        client.media_unarchive.assert_called_once_with("10_20")

    def test_save_default_collection_passes_none(self):
        client = MagicMock()
        client.media_save.return_value = True
        adapter, _ = _adapter_with_client(client)

        receipt = adapter.save_media("acc-1", "10_20")

        client.media_save.assert_called_once_with("10_20", None)
        assert receipt.success
        assert "default" in receipt.reason

    def test_save_to_specific_collection_passes_pk(self):
        client = MagicMock()
        client.media_save.return_value = True
        adapter, _ = _adapter_with_client(client)

        receipt = adapter.save_media("acc-1", "10_20", collection_pk=99)

        client.media_save.assert_called_once_with("10_20", 99)
        assert "99" in receipt.reason

    def test_unsave_default_passes_none(self):
        client = MagicMock()
        client.media_unsave.return_value = True
        adapter, _ = _adapter_with_client(client)

        adapter.unsave_media("acc-1", "10_20")

        client.media_unsave.assert_called_once_with("10_20", None)

    def test_unsave_to_specific_collection_passes_pk(self):
        client = MagicMock()
        client.media_unsave.return_value = True
        adapter, _ = _adapter_with_client(client)

        adapter.unsave_media("acc-1", "10_20", collection_pk=99)

        client.media_unsave.assert_called_once_with("10_20", 99)


# ---------------------------------------------------------------------------
# Error translation: vendor exceptions never leak raw
# ---------------------------------------------------------------------------

class _SyntheticVendorError(Exception):
    """Raised by mock client to simulate an instagrapi failure."""


class TestErrorTranslation:
    """Vendor exceptions must be translated through the failure catalog."""

    @pytest.mark.parametrize(
        "method, args",
        [
            ("edit_caption", ("acc-1", "10_20", "x")),
            ("delete_media", ("acc-1", "10_20")),
            ("pin_media", ("acc-1", "10_20")),
            ("unpin_media", ("acc-1", "10_20")),
            ("archive_media", ("acc-1", "10_20")),
            ("unarchive_media", ("acc-1", "10_20")),
            ("save_media", ("acc-1", "10_20")),
            ("unsave_media", ("acc-1", "10_20")),
        ],
    )
    def test_returns_failure_receipt_on_vendor_error(self, method, args):
        client = MagicMock()
        client.media_pk.return_value = "10"
        # Make every vendor call fail with the synthetic error.
        for vendor_method in (
            "media_edit",
            "media_delete",
            "media_pin",
            "media_unpin",
            "media_archive",
            "media_unarchive",
            "media_save",
            "media_unsave",
        ):
            getattr(client, vendor_method).side_effect = _SyntheticVendorError(
                "RAW_VENDOR_TEXT_SHOULD_NOT_LEAK"
            )
        adapter, _ = _adapter_with_client(client)

        receipt = getattr(adapter, method)(*args)

        assert isinstance(receipt, MediaActionReceipt)
        assert receipt.success is False
        assert receipt.action_id == "10_20"
        # Translated message should not include the raw vendor text.
        assert "RAW_VENDOR_TEXT_SHOULD_NOT_LEAK" not in receipt.reason

    def test_like_translates_vendor_error_to_value_error(self):
        client = MagicMock()
        client.media_like.side_effect = _SyntheticVendorError(
            "RAW_VENDOR_TEXT_SHOULD_NOT_LEAK"
        )
        adapter, _ = _adapter_with_client(client)

        with pytest.raises(ValueError) as exc_info:
            adapter.like_media("acc-1", "10_20")

        assert "RAW_VENDOR_TEXT_SHOULD_NOT_LEAK" not in str(exc_info.value)

    def test_unlike_translates_vendor_error_to_value_error(self):
        client = MagicMock()
        client.media_unlike.side_effect = _SyntheticVendorError(
            "RAW_VENDOR_TEXT_SHOULD_NOT_LEAK"
        )
        adapter, _ = _adapter_with_client(client)

        with pytest.raises(ValueError) as exc_info:
            adapter.unlike_media("acc-1", "10_20")

        assert "RAW_VENDOR_TEXT_SHOULD_NOT_LEAK" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# Boundary: missing client surfaces a guard error
# ---------------------------------------------------------------------------

class _EmptyRepo:
    def get(self, _account_id):
        return None


class TestClientGuard:
    @pytest.mark.parametrize(
        "method, args",
        [
            ("edit_caption", ("acc-1", "10_20", "x")),
            ("delete_media", ("acc-1", "10_20")),
            ("pin_media", ("acc-1", "10_20")),
            ("archive_media", ("acc-1", "10_20")),
            ("save_media", ("acc-1", "10_20")),
        ],
    )
    def test_raises_when_no_client_for_account(self, method, args):
        adapter = InstagramMediaWriterAdapter(_EmptyRepo())
        with pytest.raises(ValueError, match="not found or not authenticated"):
            getattr(adapter, method)(*args)
