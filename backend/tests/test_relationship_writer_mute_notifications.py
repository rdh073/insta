"""Unit tests for the mute + notification mutations on InstagramRelationshipWriterAdapter.

Covers:
- Each of the 12 new adapter methods proxies to the exact vendor method name.
- Each method translates a 429 failure into ``InstagramRateLimitError``.
- ``RelationshipUseCases`` resolves usernames and delegates to the writer.
- ``RelationshipUseCases.set_user_notifications`` rejects unknown kinds.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from app.adapters.instagram.error_utils import InstagramRateLimitError
from app.adapters.instagram.relationship_writer import (
    InstagramRelationshipWriterAdapter,
)
from app.application.use_cases.relationships import RelationshipUseCases
from app.domain.instagram_failures import InstagramFailure


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_failure(http_hint: int = 400, code: str = "unknown") -> InstagramFailure:
    return InstagramFailure(
        code=code,
        family="test",
        retryable=False,
        requires_user_action=False,
        user_message=f"Instagram error ({code})",
        http_hint=http_hint,
    )


def _build_adapter(mock_client):
    mock_repo = Mock()
    mock_repo.get.return_value = mock_client
    return InstagramRelationshipWriterAdapter(mock_repo)


# (adapter method name, vendor method name expected to be called).
_MUTE_METHODS: list[tuple[str, str]] = [
    ("mute_posts", "mute_posts_from_follow"),
    ("unmute_posts", "unmute_posts_from_follow"),
    ("mute_stories", "mute_stories_from_follow"),
    ("unmute_stories", "unmute_stories_from_follow"),
]


# (adapter method name, enabled flag, vendor method expected to be called).
_NOTIFICATION_METHODS: list[tuple[str, bool, str]] = [
    ("set_posts_notifications", True, "enable_posts_notifications"),
    ("set_posts_notifications", False, "disable_posts_notifications"),
    ("set_videos_notifications", True, "enable_videos_notifications"),
    ("set_videos_notifications", False, "disable_videos_notifications"),
    ("set_reels_notifications", True, "enable_reels_notifications"),
    ("set_reels_notifications", False, "disable_reels_notifications"),
    ("set_stories_notifications", True, "enable_stories_notifications"),
    ("set_stories_notifications", False, "disable_stories_notifications"),
]


# ---------------------------------------------------------------------------
# Mute methods
# ---------------------------------------------------------------------------


class TestMuteMethodsSuccess:
    @pytest.mark.parametrize("method_name,vendor_method", _MUTE_METHODS)
    def test_delegates_to_exact_vendor_method(self, method_name, vendor_method):
        mock_client = Mock()
        getattr(mock_client, vendor_method).return_value = True

        adapter = _build_adapter(mock_client)
        result = getattr(adapter, method_name)("acc-1", 12345)

        assert result is True
        getattr(mock_client, vendor_method).assert_called_once_with(12345)


class TestMuteMethodsRateLimit:
    @pytest.mark.parametrize("method_name,vendor_method", _MUTE_METHODS)
    def test_raises_rate_limit_on_429(self, method_name, vendor_method):
        mock_client = Mock()
        getattr(mock_client, vendor_method).side_effect = Exception("TooMany")

        adapter = _build_adapter(mock_client)

        with patch(
            "app.adapters.instagram.relationship_writer.translate_instagram_error",
            return_value=_make_failure(http_hint=429, code="rate_limit"),
        ):
            with pytest.raises(InstagramRateLimitError):
                getattr(adapter, method_name)("acc-1", 12345)


class TestMuteMethodsNon429Error:
    @pytest.mark.parametrize("method_name,vendor_method", _MUTE_METHODS)
    def test_non_rate_limit_error_becomes_value_error(self, method_name, vendor_method):
        mock_client = Mock()
        getattr(mock_client, vendor_method).side_effect = Exception("Generic")

        adapter = _build_adapter(mock_client)

        with patch(
            "app.adapters.instagram.relationship_writer.translate_instagram_error",
            return_value=_make_failure(http_hint=400, code="generic"),
        ):
            with pytest.raises(ValueError):
                getattr(adapter, method_name)("acc-1", 12345)


# ---------------------------------------------------------------------------
# Notification toggle methods
# ---------------------------------------------------------------------------


class TestNotificationTogglesSuccess:
    @pytest.mark.parametrize("method_name,enabled,vendor_method", _NOTIFICATION_METHODS)
    def test_routes_to_enable_or_disable_vendor_method(
        self, method_name, enabled, vendor_method
    ):
        mock_client = Mock()
        getattr(mock_client, vendor_method).return_value = True

        adapter = _build_adapter(mock_client)
        result = getattr(adapter, method_name)("acc-1", 99, enabled)

        assert result is True
        getattr(mock_client, vendor_method).assert_called_once_with(99)


class TestNotificationTogglesRateLimit:
    @pytest.mark.parametrize("method_name,enabled,vendor_method", _NOTIFICATION_METHODS)
    def test_raises_rate_limit_on_429(
        self, method_name, enabled, vendor_method
    ):
        mock_client = Mock()
        getattr(mock_client, vendor_method).side_effect = Exception("TooMany")

        adapter = _build_adapter(mock_client)

        with patch(
            "app.adapters.instagram.relationship_writer.translate_instagram_error",
            return_value=_make_failure(http_hint=429, code="rate_limit"),
        ):
            with pytest.raises(InstagramRateLimitError):
                getattr(adapter, method_name)("acc-1", 99, enabled)


# ---------------------------------------------------------------------------
# Use-case layer
# ---------------------------------------------------------------------------


def _build_use_cases(writer):
    account_repo = Mock()
    account_repo.get.return_value = {"username": "tester"}
    client_repo = Mock()
    client_repo.exists.return_value = True

    identity_reader = Mock()
    identity_reader.get_user_id_by_username.return_value = 4242

    return RelationshipUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        identity_reader=identity_reader,
        relationship_reader=Mock(),
        relationship_writer=writer,
    )


class TestMuteUseCases:
    @pytest.mark.parametrize(
        "method_name",
        ["mute_posts", "unmute_posts", "mute_stories", "unmute_stories"],
    )
    def test_resolves_username_and_delegates(self, method_name):
        writer = Mock()
        getattr(writer, method_name).return_value = True

        use_cases = _build_use_cases(writer)
        result = getattr(use_cases, method_name)("acc-1", "@someone")

        assert result is True
        getattr(writer, method_name).assert_called_once_with("acc-1", 4242)

    def test_rejects_when_writer_missing(self):
        use_cases = _build_use_cases(writer=None)
        with pytest.raises(ValueError, match="relationship writer not configured"):
            use_cases.mute_posts("acc-1", "someone")


class TestNotificationUseCases:
    @pytest.mark.parametrize(
        "kind,writer_method",
        [
            ("posts", "set_posts_notifications"),
            ("videos", "set_videos_notifications"),
            ("reels", "set_reels_notifications"),
            ("stories", "set_stories_notifications"),
        ],
    )
    def test_routes_to_correct_writer_method(self, kind, writer_method):
        writer = Mock()
        getattr(writer, writer_method).return_value = True

        use_cases = _build_use_cases(writer)
        result = use_cases.set_user_notifications("acc-1", "@someone", kind, True)

        assert result is True
        getattr(writer, writer_method).assert_called_once_with("acc-1", 4242, True)

    def test_disabled_flag_passed_through(self):
        writer = Mock()
        writer.set_posts_notifications.return_value = True

        use_cases = _build_use_cases(writer)
        use_cases.set_user_notifications("acc-1", "someone", "posts", False)

        writer.set_posts_notifications.assert_called_once_with("acc-1", 4242, False)

    def test_unknown_kind_raises(self):
        writer = Mock()
        use_cases = _build_use_cases(writer)

        with pytest.raises(ValueError, match="unknown notification kind"):
            use_cases.set_user_notifications("acc-1", "someone", "bogus", True)

    def test_rejects_when_writer_missing(self):
        use_cases = _build_use_cases(writer=None)
        with pytest.raises(ValueError, match="relationship writer not configured"):
            use_cases.set_user_notifications("acc-1", "someone", "posts", True)
