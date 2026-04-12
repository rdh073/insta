"""Tests for newly exposed LangGraph-facing Instagram tool wrappers."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.application.dto.instagram_direct_dto import DirectActionReceipt
from app.application.dto.instagram_highlight_dto import (
    HighlightActionReceipt,
    HighlightDetail,
    HighlightSummary,
)
from app.application.dto.instagram_media_dto import MediaOembedSummary
from app.application.dto.instagram_story_dto import (
    StoryActionReceipt,
    StoryDetail,
    StorySummary,
)

_TOOL_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "adapters" / "ai" / "tool_registry" / "__init__.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "tool_registry_under_test_langgraph_exposure",
    _TOOL_REGISTRY_PATH,
    submodule_search_locations=[str(_TOOL_REGISTRY_PATH.parent)],
)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
create_tool_registry = _MODULE.create_tool_registry


class _StubAccountUseCases:
    def find_by_username(self, username: str):
        if username == "operator":
            return "acc-1"
        return None

    def get_accounts_summary(self):
        return {"accounts": []}

    def get_account_info(self, _account_id: str):
        return type("AccountInfo", (), {"error": "not-implemented"})()

    def relogin_account_by_username(self, _username: str):
        return {"ok": True}

    def logout_account(self, _account_id: str, detail: str):
        return None

    def set_account_proxy(self, _account_id: str, _proxy_url: str):
        return None


class _StubPostJobUseCases:
    def list_recent_posts(self, limit: int = 10, status_filter=None):
        return {"jobs": [], "limit": limit, "status_filter": status_filter}

    def create_scheduled_post_for_usernames(self, usernames, caption, scheduled_at):
        return {
            "usernames": usernames,
            "caption": caption,
            "scheduled_at": scheduled_at,
        }


class _StubMediaUseCases:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def get_media_oembed(self, account_id: str, url: str) -> MediaOembedSummary:
        self.calls.append((account_id, url))
        return MediaOembedSummary(
            media_id="123_1",
            author_name="creator",
            provider_name="Instagram",
            can_view=True,
        )


class _StubStoryUseCases:
    def __init__(self) -> None:
        self.get_calls: list[tuple[str, int, bool]] = []
        self.delete_calls: list[tuple[str, int]] = []
        self.mark_seen_calls: list[tuple[str, list[int], list[int] | None]] = []

    def get_story(self, account_id: str, story_pk: int, use_cache: bool = True) -> StoryDetail:
        self.get_calls.append((account_id, story_pk, use_cache))
        return StoryDetail(
            summary=StorySummary(
                pk=story_pk,
                story_id=f"{story_pk}_1",
                media_type=1,
                taken_at=datetime(2025, 1, 5, tzinfo=timezone.utc),
                owner_username="creator",
            ),
            link_count=1,
            mention_count=2,
            hashtag_count=3,
            location_count=0,
            sticker_count=1,
        )

    def delete_story(self, account_id: str, story_pk: int) -> StoryActionReceipt:
        self.delete_calls.append((account_id, story_pk))
        return StoryActionReceipt(action_id="story-delete-1", success=True, reason="")

    def mark_seen(
        self,
        account_id: str,
        story_pks: list[int],
        skipped_story_pks: list[int] | None = None,
    ) -> StoryActionReceipt:
        self.mark_seen_calls.append((account_id, story_pks, skipped_story_pks))
        return StoryActionReceipt(action_id="story-seen-1", success=True, reason="")


class _StubHighlightUseCases:
    def __init__(self) -> None:
        self.get_calls: list[tuple[str, int]] = []
        self.change_calls: list[tuple[str, int, str]] = []
        self.add_calls: list[tuple[str, int, list[int]]] = []
        self.remove_calls: list[tuple[str, int, list[int]]] = []

    @staticmethod
    def _detail(title: str, story_ids: list[str]) -> HighlightDetail:
        return HighlightDetail(
            summary=HighlightSummary(
                pk="77",
                highlight_id="77_1",
                title=title,
                media_count=len(story_ids),
                owner_username="creator",
            ),
            story_ids=story_ids,
            items=[
                StorySummary(
                    pk=101,
                    story_id="101_1",
                    media_type=1,
                    taken_at=datetime(2025, 1, 5, tzinfo=timezone.utc),
                    owner_username="creator",
                )
            ],
        )

    def get_highlight(self, account_id: str, highlight_pk: int) -> HighlightDetail:
        self.get_calls.append((account_id, highlight_pk))
        return self._detail("Launch", ["101_1"])

    def change_title(self, account_id: str, highlight_pk: int, title: str) -> HighlightDetail:
        self.change_calls.append((account_id, highlight_pk, title))
        return self._detail(title, ["101_1"])

    def add_stories(self, account_id: str, highlight_pk: int, story_ids: list[int]) -> HighlightDetail:
        self.add_calls.append((account_id, highlight_pk, story_ids))
        return self._detail("Launch", [str(story_id) for story_id in story_ids])

    def remove_stories(self, account_id: str, highlight_pk: int, story_ids: list[int]) -> HighlightDetail:
        self.remove_calls.append((account_id, highlight_pk, story_ids))
        return self._detail("Launch", [])

    def delete_highlight(self, _account_id: str, _highlight_pk: int) -> HighlightActionReceipt:
        return HighlightActionReceipt(action_id="delete-highlight-1", success=True, reason="")


class _StubDirectUseCases:
    def __init__(self) -> None:
        self.approve_calls: list[tuple[str, str]] = []
        self.seen_calls: list[tuple[str, str]] = []

    def approve_pending_thread(self, account_id: str, thread_id: str) -> DirectActionReceipt:
        self.approve_calls.append((account_id, thread_id))
        return DirectActionReceipt(action_id="approve-1", success=True, reason="")

    def mark_thread_seen(self, account_id: str, thread_id: str) -> DirectActionReceipt:
        self.seen_calls.append((account_id, thread_id))
        return DirectActionReceipt(action_id="seen-1", success=True, reason="")


def _make_registry():
    return create_tool_registry(
        _StubAccountUseCases(),
        _StubPostJobUseCases(),
        media_use_cases=_StubMediaUseCases(),
        story_use_cases=_StubStoryUseCases(),
        highlight_use_cases=_StubHighlightUseCases(),
        direct_use_cases=_StubDirectUseCases(),
    )


def test_get_media_oembed_tool_maps_use_case_dto():
    registry = _make_registry()
    result = asyncio.run(
        registry.execute(
            "get_media_oembed",
            {"username": "@operator", "url": "https://instagram.com/p/abc123/"},
        )
    )

    assert result["media_id"] == "123_1"
    assert result["author_name"] == "creator"
    assert result["provider_name"] == "Instagram"
    assert result["can_view"] is True


def test_story_read_and_write_tools_call_story_use_cases():
    registry = _make_registry()

    story = asyncio.run(
        registry.execute(
            "get_story",
            {"username": "operator", "story_pk": 101, "use_cache": False},
        )
    )
    deleted = asyncio.run(
        registry.execute(
            "delete_story",
            {"username": "operator", "story_pk": 101},
        )
    )
    seen = asyncio.run(
        registry.execute(
            "mark_stories_seen",
            {"username": "operator", "story_pks": [101, 102], "skipped_story_pks": [103]},
        )
    )

    assert story["summary"]["pk"] == 101
    assert story["link_count"] == 1
    assert story["mention_count"] == 2
    assert deleted["action_id"] == "story-delete-1"
    assert deleted["success"] is True
    assert seen["action_id"] == "story-seen-1"
    assert seen["success"] is True


def test_highlight_read_and_write_tools_call_highlight_use_cases():
    registry = _make_registry()

    detail = asyncio.run(
        registry.execute(
            "get_highlight",
            {"username": "@operator", "highlight_pk": 77},
        )
    )
    renamed = asyncio.run(
        registry.execute(
            "change_highlight_title",
            {"username": "@operator", "highlight_pk": 77, "title": "Spring"},
        )
    )
    added = asyncio.run(
        registry.execute(
            "add_stories_to_highlight",
            {"username": "@operator", "highlight_pk": 77, "story_ids": [201, 202]},
        )
    )
    removed = asyncio.run(
        registry.execute(
            "remove_stories_from_highlight",
            {"username": "@operator", "highlight_pk": 77, "story_ids": [201]},
        )
    )

    assert detail["summary"]["highlight_id"] == "77_1"
    assert detail["items"][0]["story_id"] == "101_1"
    assert renamed["success"] is True
    assert renamed["highlight"]["title"] == "Spring"
    assert added["success"] is True
    assert added["highlight"]["media_count"] == 2
    assert removed["success"] is True


def test_direct_pending_and_seen_tools_map_action_receipts():
    registry = _make_registry()

    approved = asyncio.run(
        registry.execute(
            "approve_pending_direct_thread",
            {"username": "@operator", "thread_id": "thread-1"},
        )
    )
    seen = asyncio.run(
        registry.execute(
            "mark_direct_thread_seen",
            {"username": "@operator", "thread_id": "thread-1"},
        )
    )

    assert approved["action_id"] == "approve-1"
    assert approved["success"] is True
    assert seen["action_id"] == "seen-1"
    assert seen["success"] is True
