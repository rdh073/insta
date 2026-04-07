"""Adapter-level tests for catalog-driven Instagram error translation."""

from __future__ import annotations

import pytest

from app.adapters.instagram.collection_reader import InstagramCollectionReaderAdapter
from app.adapters.instagram.comment_reader import InstagramCommentReaderAdapter
from app.adapters.instagram.comment_writer import InstagramCommentWriterAdapter
from app.adapters.instagram.direct_reader import InstagramDirectReaderAdapter
from app.adapters.instagram.direct_writer import InstagramDirectWriterAdapter
from app.adapters.instagram.discovery_reader import InstagramDiscoveryReaderAdapter
from app.adapters.instagram.exception_catalog import EXCEPTION_REGISTRY, FailureSpec
from app.adapters.instagram.highlight_reader import InstagramHighlightReaderAdapter
from app.adapters.instagram.highlight_writer import InstagramHighlightWriterAdapter
from app.adapters.instagram.identity_reader import InstagramIdentityReaderAdapter
from app.adapters.instagram.insight_reader import InstagramInsightReaderAdapter
from app.adapters.instagram.media_reader import InstagramMediaReaderAdapter
from app.adapters.instagram.relationship_reader import InstagramRelationshipReaderAdapter
from app.adapters.instagram.story_publisher import InstagramStoryPublisherAdapter
from app.adapters.instagram.story_reader import InstagramStoryReaderAdapter
from app.adapters.instagram.track_catalog import InstagramTrackCatalogAdapter


class FakeVendorError(Exception):
    """Synthetic vendor error used to validate catalog-based translation."""


class StubClientRepo:
    """Minimal client repository stub for adapter tests."""

    def __init__(self, client):
        self._client = client

    def get(self, account_id: str):
        return self._client


class RaisingClient:
    """Client stub that raises the same exception on every method call."""

    def __init__(self, error: Exception):
        self._error = error

    def __getattr__(self, _name):
        def _raise(*_args, **_kwargs):
            raise self._error

        return _raise


@pytest.fixture
def catalog_failure_spec(monkeypatch) -> FailureSpec:
    """Register FakeVendorError in catalog registry for this test module."""
    spec = FailureSpec(
        code="catalog_error",
        family="test",
        retryable=False,
        requires_user_action=False,
        user_message="Catalog mapped message",
        http_hint=400,
    )
    monkeypatch.setitem(EXCEPTION_REGISTRY, FakeVendorError, spec)
    return spec


def test_read_adapters_raise_catalog_message(catalog_failure_spec: FailureSpec):
    """Read adapters must raise catalog message, not raw vendor string."""
    raw_msg = "RAW_VENDOR_STRING_SHOULD_NOT_LEAK"
    client = RaisingClient(FakeVendorError(raw_msg))
    repo = StubClientRepo(client)

    with pytest.raises(ValueError) as e1:
        InstagramDiscoveryReaderAdapter(repo).search_locations("acc-1", "jakarta")
    with pytest.raises(ValueError) as e2:
        InstagramCollectionReaderAdapter(repo).list_collections("acc-1")
    with pytest.raises(ValueError) as e3:
        InstagramCommentReaderAdapter(repo).list_comments("acc-1", "123")
    with pytest.raises(ValueError) as e4:
        InstagramDirectReaderAdapter(repo).list_inbox_threads("acc-1")
    with pytest.raises(ValueError) as e4b:
        InstagramDirectReaderAdapter(repo).list_pending_threads("acc-1")
    with pytest.raises(ValueError) as e4c:
        InstagramDirectReaderAdapter(repo).get_thread("acc-1", "thread-1")
    with pytest.raises(ValueError) as e4d:
        InstagramDirectReaderAdapter(repo).list_messages("acc-1", "thread-1")
    with pytest.raises(ValueError) as e4e:
        InstagramDirectReaderAdapter(repo).search_threads("acc-1", "query")
    with pytest.raises(ValueError) as e5:
        InstagramTrackCatalogAdapter(repo).search_tracks("acc-1", "lofi")
    with pytest.raises(ValueError) as e6:
        InstagramInsightReaderAdapter(repo).get_media_insight("acc-1", 123)
    with pytest.raises(ValueError) as e7:
        InstagramHighlightReaderAdapter(repo).get_highlight("acc-1", 123)
    with pytest.raises(ValueError) as e8:
        InstagramMediaReaderAdapter(repo).get_media_by_pk("acc-1", 123)
    with pytest.raises(ValueError) as e9:
        InstagramMediaReaderAdapter(repo).get_media_oembed("acc-1", "https://instagram.com/p/test/")
    with pytest.raises(ValueError) as e10:
        InstagramStoryReaderAdapter(repo).get_story("acc-1", 123)
    with pytest.raises(ValueError) as e11:
        InstagramStoryReaderAdapter(repo).list_user_stories("acc-1", 123)
    with pytest.raises(ValueError) as e12:
        InstagramIdentityReaderAdapter(repo).get_authenticated_account("acc-1")
    with pytest.raises(ValueError) as e13:
        InstagramIdentityReaderAdapter(repo).get_public_user_by_id("acc-1", 123)
    with pytest.raises(ValueError) as e14:
        InstagramIdentityReaderAdapter(repo).get_public_user_by_username("acc-1", "operator")
    with pytest.raises(ValueError) as e15:
        InstagramRelationshipReaderAdapter(repo).list_followers("acc-1", 123)
    with pytest.raises(ValueError) as e16:
        InstagramRelationshipReaderAdapter(repo).list_following("acc-1", 123)

    for err in (
        e1,
        e2,
        e3,
        e4,
        e4b,
        e4c,
        e4d,
        e4e,
        e5,
        e6,
        e7,
        e8,
        e9,
        e10,
        e11,
        e12,
        e13,
        e14,
        e15,
        e16,
    ):
        assert str(err.value) == catalog_failure_spec.user_message
        assert raw_msg not in str(err.value)


def test_write_adapters_raise_catalog_message(catalog_failure_spec: FailureSpec):
    """Write adapters that raise ValueError must use catalog message."""
    raw_msg = "RAW_VENDOR_STRING_SHOULD_NOT_LEAK"
    client = RaisingClient(FakeVendorError(raw_msg))
    repo = StubClientRepo(client)

    with pytest.raises(ValueError) as e1:
        InstagramCommentWriterAdapter(repo).create_comment("acc-1", "123", "hello")
    with pytest.raises(ValueError) as e2:
        InstagramDirectWriterAdapter(repo).send_to_users("acc-1", [1], "hello")
    with pytest.raises(ValueError) as e2b:
        InstagramDirectWriterAdapter(repo).find_or_create_thread("acc-1", [1, 2])
    with pytest.raises(ValueError) as e2c:
        InstagramDirectWriterAdapter(repo).send_to_thread("acc-1", "thread-1", "hello")
    with pytest.raises(ValueError) as e3:
        InstagramHighlightWriterAdapter(repo).change_title("acc-1", 1, "new")

    for err in (e1, e2, e2b, e2c, e3):
        assert str(err.value) == catalog_failure_spec.user_message
        assert raw_msg not in str(err.value)


def test_action_receipts_use_catalog_message(catalog_failure_spec: FailureSpec):
    """Adapters returning ActionReceipt on failure must use catalog message."""
    raw_msg = "RAW_VENDOR_STRING_SHOULD_NOT_LEAK"
    client = RaisingClient(FakeVendorError(raw_msg))
    repo = StubClientRepo(client)

    comment_receipt = InstagramCommentWriterAdapter(repo).delete_comment("acc-1", "123", 7)
    direct_receipt = InstagramDirectWriterAdapter(repo).delete_message("acc-1", "thread-1", "msg-1")
    story_receipt = InstagramStoryPublisherAdapter(repo).delete_story("acc-1", 99)
    highlight_receipt = InstagramHighlightWriterAdapter(repo).delete_highlight("acc-1", 101)

    for receipt in (comment_receipt, direct_receipt, story_receipt, highlight_receipt):
        assert receipt.success is False
        assert receipt.reason == catalog_failure_spec.user_message
        assert raw_msg not in receipt.reason
