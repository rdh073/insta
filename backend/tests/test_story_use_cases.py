"""Use-case tests for StoryUseCases.

Tests the application orchestration layer using port doubles (stubs/fakes).
No instagrapi imports — all vendor types stay behind the port boundary.
Covers:
  - Preconditions: account not found, account not authenticated
  - Read ops: get_story_pk_from_url (url validation), get_story (story_pk),
              list_user_stories (user_id, amount)
  - Write ops: publish_story (media_kind, audience, thumbnail_path),
               delete_story (story_pk), mark_seen (story_pks)
  - Happy-path delegation to port doubles
  - DTO boundary: only app-owned story DTOs returned
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.application.dto.instagram_story_dto import (
    StoryActionReceipt,
    StoryDetail,
    StorySummary,
    StoryPublishRequest,
)
from app.application.use_cases.story import StoryUseCases


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_summary(pk: int = 1) -> StorySummary:
    return StorySummary(pk=pk, story_id=str(pk))


def _make_detail(pk: int = 1) -> StoryDetail:
    return StoryDetail(summary=_make_summary(pk))


def _make_receipt(action_id: str = "act-1") -> StoryActionReceipt:
    return StoryActionReceipt(action_id=action_id, success=True)


def _make_photo_request() -> StoryPublishRequest:
    return StoryPublishRequest(
        media_path="/tmp/photo.jpg",
        media_kind="photo",
    )


def _make_video_request(with_thumbnail: bool = True) -> StoryPublishRequest:
    return StoryPublishRequest(
        media_path="/tmp/video.mp4",
        media_kind="video",
        thumbnail_path="/tmp/thumb.jpg" if with_thumbnail else None,
    )


def _build_use_cases(
    *,
    account_exists: bool = True,
    client_exists: bool = True,
    reader: Mock | None = None,
    publisher: Mock | None = None,
) -> tuple[StoryUseCases, Mock, Mock]:
    account_repo = Mock()
    account_repo.get.return_value = {"username": "testuser"} if account_exists else None

    client_repo = Mock()
    client_repo.exists.return_value = client_exists

    if reader is None:
        reader = Mock()
    if publisher is None:
        publisher = Mock()

    uc = StoryUseCases(
        account_repo=account_repo,
        client_repo=client_repo,
        story_reader=reader,
        story_publisher=publisher,
    )
    return uc, reader, publisher


# ---------------------------------------------------------------------------
# Preconditions: account not found
# ---------------------------------------------------------------------------

class TestAccountPreconditions:
    def test_get_story_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.get_story("no-such", 1)

    def test_list_user_stories_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.list_user_stories("no-such", 123)

    def test_publish_story_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.publish_story("no-such", _make_photo_request())

    def test_delete_story_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.delete_story("no-such", 1)

    def test_mark_seen_raises_if_account_missing(self):
        uc, _, _ = _build_use_cases(account_exists=False)
        with pytest.raises(ValueError, match="not found"):
            uc.mark_seen("no-such", [1, 2])


# ---------------------------------------------------------------------------
# Preconditions: account not authenticated
# ---------------------------------------------------------------------------

class TestAuthPreconditions:
    def test_get_story_raises_if_not_authenticated(self):
        uc, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.get_story("acc-1", 1)

    def test_list_user_stories_raises_if_not_authenticated(self):
        uc, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.list_user_stories("acc-1", 123)

    def test_publish_story_raises_if_not_authenticated(self):
        uc, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.publish_story("acc-1", _make_photo_request())

    def test_delete_story_raises_if_not_authenticated(self):
        uc, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.delete_story("acc-1", 1)

    def test_mark_seen_raises_if_not_authenticated(self):
        uc, _, _ = _build_use_cases(client_exists=False)
        with pytest.raises(ValueError, match="not authenticated"):
            uc.mark_seen("acc-1", [1])


# ---------------------------------------------------------------------------
# get_story_pk_from_url validation (no account needed)
# ---------------------------------------------------------------------------

class TestGetStoryPkFromUrl:
    def test_rejects_empty_url(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="empty"):
            uc.get_story_pk_from_url("")

    def test_rejects_whitespace_only_url(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="empty"):
            uc.get_story_pk_from_url("   ")

    def test_rejects_non_http_url(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="http"):
            uc.get_story_pk_from_url("ftp://example.com/story/123")

    def test_strips_whitespace_and_delegates(self):
        uc, reader, _ = _build_use_cases()
        reader.get_story_pk_from_url.return_value = 99

        result = uc.get_story_pk_from_url("  https://www.instagram.com/stories/user/99/  ")

        reader.get_story_pk_from_url.assert_called_once_with(
            "https://www.instagram.com/stories/user/99/"
        )
        assert result == 99

    def test_accepts_valid_http_url(self):
        uc, reader, _ = _build_use_cases()
        reader.get_story_pk_from_url.return_value = 42

        result = uc.get_story_pk_from_url("https://www.instagram.com/stories/user/42/")

        assert result == 42


# ---------------------------------------------------------------------------
# get_story: story_pk validation
# ---------------------------------------------------------------------------

class TestGetStoryValidation:
    def test_rejects_zero_story_pk(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_story("acc-1", 0)

    def test_rejects_negative_story_pk(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_story("acc-1", -5)

    def test_rejects_non_int_story_pk(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.get_story("acc-1", "abc")  # type: ignore[arg-type]

    def test_passes_use_cache_to_port(self):
        uc, reader, _ = _build_use_cases()
        reader.get_story.return_value = _make_detail(7)

        uc.get_story("acc-1", 7, use_cache=False)

        reader.get_story.assert_called_once_with("acc-1", 7, False)

    def test_default_use_cache_is_true(self):
        uc, reader, _ = _build_use_cases()
        reader.get_story.return_value = _make_detail(7)

        uc.get_story("acc-1", 7)

        reader.get_story.assert_called_once_with("acc-1", 7, True)


# ---------------------------------------------------------------------------
# list_user_stories: user_id and amount validation
# ---------------------------------------------------------------------------

class TestListUserStoriesValidation:
    def test_rejects_zero_user_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.list_user_stories("acc-1", 0)

    def test_rejects_negative_user_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.list_user_stories("acc-1", -1)

    def test_rejects_non_int_user_id(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.list_user_stories("acc-1", "me")  # type: ignore[arg-type]

    def test_rejects_zero_amount(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.list_user_stories("acc-1", 100, amount=0)

    def test_rejects_negative_amount(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.list_user_stories("acc-1", 100, amount=-3)

    def test_none_amount_passes_through(self):
        uc, reader, _ = _build_use_cases()
        reader.list_user_stories.return_value = []

        uc.list_user_stories("acc-1", 100)

        reader.list_user_stories.assert_called_once_with("acc-1", 100, None)

    def test_positive_amount_passes_through(self):
        uc, reader, _ = _build_use_cases()
        reader.list_user_stories.return_value = []

        uc.list_user_stories("acc-1", 100, amount=5)

        reader.list_user_stories.assert_called_once_with("acc-1", 100, 5)


# ---------------------------------------------------------------------------
# publish_story: media_kind, audience, thumbnail_path validation
# ---------------------------------------------------------------------------

class TestPublishStoryValidation:
    def test_rejects_empty_media_path(self):
        uc, _, _ = _build_use_cases()
        req = StoryPublishRequest(media_path="", media_kind="photo")
        with pytest.raises(ValueError, match="media_path"):
            uc.publish_story("acc-1", req)

    def test_rejects_whitespace_media_path(self):
        uc, _, _ = _build_use_cases()
        req = StoryPublishRequest(media_path="  ", media_kind="photo")
        with pytest.raises(ValueError, match="media_path"):
            uc.publish_story("acc-1", req)

    def test_rejects_invalid_media_kind(self):
        uc, _, _ = _build_use_cases()
        req = StoryPublishRequest(media_path="/tmp/file.gif", media_kind="gif")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="media_kind"):
            uc.publish_story("acc-1", req)

    def test_rejects_invalid_audience(self):
        uc, _, _ = _build_use_cases()
        req = StoryPublishRequest(
            media_path="/tmp/photo.jpg",
            media_kind="photo",
            audience="vip",  # type: ignore[arg-type]
        )
        with pytest.raises(ValueError, match="audience"):
            uc.publish_story("acc-1", req)

    def test_rejects_video_without_thumbnail(self):
        uc, _, _ = _build_use_cases()
        req = _make_video_request(with_thumbnail=False)
        with pytest.raises(ValueError, match="thumbnail_path"):
            uc.publish_story("acc-1", req)

    def test_accepts_photo_without_thumbnail(self):
        uc, _, publisher = _build_use_cases()
        publisher.publish_story.return_value = _make_detail()
        req = _make_photo_request()

        uc.publish_story("acc-1", req)

        publisher.publish_story.assert_called_once_with("acc-1", req)

    def test_accepts_video_with_thumbnail(self):
        uc, _, publisher = _build_use_cases()
        publisher.publish_story.return_value = _make_detail()
        req = _make_video_request(with_thumbnail=True)

        uc.publish_story("acc-1", req)

        publisher.publish_story.assert_called_once_with("acc-1", req)

    def test_accepts_close_friends_audience(self):
        uc, _, publisher = _build_use_cases()
        publisher.publish_story.return_value = _make_detail()
        req = StoryPublishRequest(
            media_path="/tmp/photo.jpg",
            media_kind="photo",
            audience="close_friends",
        )

        uc.publish_story("acc-1", req)

        publisher.publish_story.assert_called_once_with("acc-1", req)


# ---------------------------------------------------------------------------
# delete_story: story_pk validation
# ---------------------------------------------------------------------------

class TestDeleteStoryValidation:
    def test_rejects_zero_story_pk(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.delete_story("acc-1", 0)

    def test_rejects_negative_story_pk(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integer"):
            uc.delete_story("acc-1", -1)

    def test_delegates_valid_pk(self):
        uc, _, publisher = _build_use_cases()
        publisher.delete_story.return_value = _make_receipt()

        uc.delete_story("acc-1", 77)

        publisher.delete_story.assert_called_once_with("acc-1", 77)


# ---------------------------------------------------------------------------
# mark_seen: story_pks validation
# ---------------------------------------------------------------------------

class TestMarkSeenValidation:
    def test_rejects_empty_list(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="must not be empty"):
            uc.mark_seen("acc-1", [])

    def test_rejects_zero_pk_in_list(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integers"):
            uc.mark_seen("acc-1", [1, 0, 3])

    def test_rejects_negative_pk_in_list(self):
        uc, _, _ = _build_use_cases()
        with pytest.raises(ValueError, match="positive integers"):
            uc.mark_seen("acc-1", [1, -2])

    def test_delegates_valid_pks(self):
        uc, _, publisher = _build_use_cases()
        publisher.mark_seen.return_value = _make_receipt()

        uc.mark_seen("acc-1", [10, 20, 30])

        publisher.mark_seen.assert_called_once_with("acc-1", [10, 20, 30], None)

    def test_passes_skipped_pks(self):
        uc, _, publisher = _build_use_cases()
        publisher.mark_seen.return_value = _make_receipt()

        uc.mark_seen("acc-1", [10], skipped_story_pks=[99])

        publisher.mark_seen.assert_called_once_with("acc-1", [10], [99])


# ---------------------------------------------------------------------------
# Port not called when preconditions fail
# ---------------------------------------------------------------------------

class TestPortNotCalledOnFailure:
    def test_reader_not_called_when_account_missing(self):
        uc, reader, publisher = _build_use_cases(account_exists=False)

        with pytest.raises(ValueError):
            uc.get_story("acc-1", 1)

        reader.get_story.assert_not_called()

    def test_publisher_not_called_when_invalid_media_kind(self):
        uc, _, publisher = _build_use_cases()
        req = StoryPublishRequest(media_path="/tmp/f.gif", media_kind="gif")  # type: ignore[arg-type]

        with pytest.raises(ValueError):
            uc.publish_story("acc-1", req)

        publisher.publish_story.assert_not_called()

    def test_publisher_not_called_for_empty_mark_seen(self):
        uc, _, publisher = _build_use_cases()

        with pytest.raises(ValueError):
            uc.mark_seen("acc-1", [])

        publisher.mark_seen.assert_not_called()


# ---------------------------------------------------------------------------
# DTO boundary: only app-owned types returned
# ---------------------------------------------------------------------------

class TestDTOBoundary:
    def test_get_story_returns_story_detail(self):
        uc, reader, _ = _build_use_cases()
        reader.get_story.return_value = _make_detail(5)

        result = uc.get_story("acc-1", 5)

        assert isinstance(result, StoryDetail)

    def test_list_user_stories_returns_story_summaries(self):
        uc, reader, _ = _build_use_cases()
        reader.list_user_stories.return_value = [_make_summary(i) for i in range(1, 4)]

        results = uc.list_user_stories("acc-1", 100)

        assert all(isinstance(r, StorySummary) for r in results)

    def test_publish_story_returns_story_detail(self):
        uc, _, publisher = _build_use_cases()
        publisher.publish_story.return_value = _make_detail()

        result = uc.publish_story("acc-1", _make_photo_request())

        assert isinstance(result, StoryDetail)

    def test_delete_story_returns_action_receipt(self):
        uc, _, publisher = _build_use_cases()
        publisher.delete_story.return_value = _make_receipt()

        result = uc.delete_story("acc-1", 1)

        assert isinstance(result, StoryActionReceipt)

    def test_mark_seen_returns_action_receipt(self):
        uc, _, publisher = _build_use_cases()
        publisher.mark_seen.return_value = _make_receipt()

        result = uc.mark_seen("acc-1", [1, 2])

        assert isinstance(result, StoryActionReceipt)
