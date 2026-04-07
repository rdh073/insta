"""Phase C policy-centralization tests.

These tests prove business validation/orchestration stays in use cases even when
the underlying adapter implementation is swapped.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.application.dto.instagram_comment_dto import (
    CommentAuthorSummary,
    CommentSummary,
)
from app.application.dto.instagram_direct_dto import DirectMessageSummary
from app.application.dto.instagram_highlight_dto import (
    HighlightDetail,
    HighlightSummary,
)
from app.application.dto.instagram_story_dto import (
    StoryDetail,
    StoryPublishRequest,
    StorySummary,
)
from app.application.use_cases.comment import CommentUseCases
from app.application.use_cases.direct import DirectUseCases
from app.application.use_cases.highlight import HighlightUseCases
from app.application.use_cases.story import StoryUseCases


@dataclass
class _AccountRepo:
    exists: bool = True

    def get(self, _account_id: str):
        return {"username": "operator"} if self.exists else None


@dataclass
class _ClientRepo:
    authenticated: bool = True

    def exists(self, _account_id: str) -> bool:
        return self.authenticated


class _SwappedStoryPublisher:
    def __init__(self):
        self.calls = 0

    def publish_story(self, _account_id: str, _request: StoryPublishRequest) -> StoryDetail:
        self.calls += 1
        return StoryDetail(summary=StorySummary(pk=1, story_id="1"))


class _SwappedCommentWriter:
    def __init__(self):
        self.calls = 0
        self.last = None

    def create_comment(
        self,
        account_id: str,
        media_id: str,
        text: str,
        reply_to_comment_id: int | None = None,
    ) -> CommentSummary:
        self.calls += 1
        self.last = (account_id, media_id, text, reply_to_comment_id)
        return CommentSummary(
            pk=1,
            text=text,
            author=CommentAuthorSummary(pk=1, username="operator"),
        )


class _SwappedDirectWriter:
    def __init__(self):
        self.calls = 0
        self.last = None

    def send_to_thread(
        self,
        account_id: str,
        direct_thread_id: str,
        text: str,
    ) -> DirectMessageSummary:
        self.calls += 1
        self.last = (account_id, direct_thread_id, text)
        return DirectMessageSummary(direct_message_id="dm-1", text=text)


class _SwappedHighlightWriter:
    def __init__(self):
        self.calls = 0

    def create_highlight(
        self,
        _account_id: str,
        title: str,
        _story_ids: list[int],
        *,
        cover_story_id: int = 0,
        crop_rect: list[float] | None = None,
    ) -> HighlightDetail:
        self.calls += 1
        return HighlightDetail(
            summary=HighlightSummary(pk="1", highlight_id="1", title=title),
        )


class _NoOpReader:
    def __getattr__(self, _name):
        def _noop(*_args, **_kwargs):
            return []

        return _noop


class _IdentityUseCasesStub:
    def get_public_user_by_username(self, _account_id: str, _username: str):
        class _User:
            pk = 1

        return _User()


def test_story_use_case_policy_blocks_swapped_adapter_on_invalid_input():
    publisher = _SwappedStoryPublisher()
    uc = StoryUseCases(
        account_repo=_AccountRepo(),
        client_repo=_ClientRepo(),
        story_reader=_NoOpReader(),
        story_publisher=publisher,
    )

    bad_request = StoryPublishRequest(media_path="/tmp/a.jpg", media_kind="gif")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="media_kind"):
        uc.publish_story("acc-1", bad_request)
    assert publisher.calls == 0


def test_comment_use_case_policy_normalizes_before_swapped_adapter_call():
    writer = _SwappedCommentWriter()
    uc = CommentUseCases(
        account_repo=_AccountRepo(),
        client_repo=_ClientRepo(),
        comment_reader=_NoOpReader(),
        comment_writer=writer,
    )

    result = uc.create_comment("acc-1", "  media-1  ", "  hello  ")

    assert result.text == "hello"
    assert writer.calls == 1
    assert writer.last == ("acc-1", "media-1", "hello", None)


def test_direct_use_case_policy_blocks_swapped_adapter_on_empty_text():
    writer = _SwappedDirectWriter()
    uc = DirectUseCases(
        account_repo=_AccountRepo(),
        client_repo=_ClientRepo(),
        direct_reader=_NoOpReader(),
        direct_writer=writer,
        identity_use_cases=_IdentityUseCasesStub(),
    )

    with pytest.raises(ValueError, match="text"):
        uc.send_to_thread("acc-1", "thread-1", "   ")
    assert writer.calls == 0


def test_highlight_use_case_policy_blocks_swapped_adapter_on_invalid_crop_rect():
    writer = _SwappedHighlightWriter()
    uc = HighlightUseCases(
        account_repo=_AccountRepo(),
        client_repo=_ClientRepo(),
        highlight_reader=_NoOpReader(),
        highlight_writer=writer,
    )

    with pytest.raises(ValueError, match="crop_rect"):
        uc.create_highlight(
            "acc-1",
            "Travel",
            [1],
            crop_rect=[0.1, 0.2],  # must have exactly 4 elements
        )
    assert writer.calls == 0
