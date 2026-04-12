"""Tests for discovery-first consumer wiring in AI tool registry."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.application.dto.instagram_discovery_dto import HashtagSummary, CollectionSummary
from app.application.dto.instagram_media_dto import MediaSummary

_TOOL_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "adapters" / "ai" / "tool_registry" / "__init__.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "tool_registry_under_test",
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


class _StubHashtagUseCases:
    def __init__(self):
        self.calls: list[tuple[str, str, int]] = []
        self.search_calls: list[tuple[str, str]] = []
        self.get_calls: list[tuple[str, str]] = []

    def search_hashtags(self, account_id: str, query: str):
        self.search_calls.append((account_id, query))
        return [
            HashtagSummary(
                id=17,
                name="test",
                media_count=1234,
                profile_pic_url="https://example.com/hashtag-test.jpg",
            )
        ]

    def get_hashtag(self, account_id: str, name: str):
        self.get_calls.append((account_id, name))
        return HashtagSummary(
            id=42,
            name=name,
            media_count=9876,
            profile_pic_url="https://example.com/hashtag-detail.jpg",
        )

    def get_hashtag_recent_posts(self, account_id: str, name: str, amount: int = 12):
        self.calls.append((account_id, name, amount))
        return [
            MediaSummary(
                pk=123,
                media_id="123_1",
                code="CODE123",
                media_type=1,
                product_type="feed",
                owner_username="author_a",
                caption_text="hello #test",
                like_count=77,
                comment_count=9,
                taken_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            )
        ]

    def get_hashtag_top_posts(self, account_id: str, name: str, amount: int = 12):
        self.calls.append((account_id, f"top:{name}", amount))
        return []


class _StubCollectionUseCases:
    def __init__(self):
        self.calls: list[str] = []

    def list_collections(self, account_id: str):
        self.calls.append(account_id)
        return [
            CollectionSummary(pk=71, name="Saved Reads", media_count=11),
            CollectionSummary(pk=72, name="Campaign Ideas", media_count=5),
        ]


def test_get_hashtag_posts_tool_uses_hashtag_usecases_dto_boundary():
    """Tool get_hashtag_posts must consume hashtag use-case DTOs, not vendor media objects."""
    hashtag_use_cases = _StubHashtagUseCases()
    registry = create_tool_registry(
        _StubAccountUseCases(),
        _StubPostJobUseCases(),
        hashtag_use_cases=hashtag_use_cases,
    )

    result = asyncio.run(
        registry.execute(
            "get_hashtag_posts",
            {
                "username": "@operator",
                "hashtag": "#test",
                "amount": 1,
            },
        )
    )

    assert result["hashtag"] == "test"
    assert result["feed"] == "recent"
    assert result["count"] == 1
    assert result["posts"][0]["post_id"] == 123
    assert result["posts"][0]["caption_text"] == "hello #test"
    assert "user" not in result["posts"][0]
    assert hashtag_use_cases.calls == [("acc-1", "test", 1)]


def test_get_hashtag_posts_tool_validates_username():
    """Tool should fail fast when username cannot be resolved to an account."""
    registry = create_tool_registry(
        _StubAccountUseCases(),
        _StubPostJobUseCases(),
        hashtag_use_cases=_StubHashtagUseCases(),
    )

    result = asyncio.run(
        registry.execute(
            "get_hashtag_posts",
            {"username": "unknown", "hashtag": "test"},
        )
    )

    assert "error" in result
    assert "not found" in result["error"].lower()


def test_search_hashtags_tool_returns_hashtag_contract():
    hashtag_use_cases = _StubHashtagUseCases()
    registry = create_tool_registry(
        _StubAccountUseCases(),
        _StubPostJobUseCases(),
        hashtag_use_cases=hashtag_use_cases,
    )

    result = asyncio.run(
        registry.execute(
            "search_hashtags",
            {"username": "@operator", "query": "#test"},
        )
    )

    assert result["count"] == 1
    assert result["hashtags"][0]["id"] == 17
    assert result["hashtags"][0]["name"] == "test"
    assert result["hashtags"][0]["media_count"] == 1234
    assert hashtag_use_cases.search_calls == [("acc-1", "#test")]


def test_get_hashtag_tool_returns_single_hashtag_contract():
    hashtag_use_cases = _StubHashtagUseCases()
    registry = create_tool_registry(
        _StubAccountUseCases(),
        _StubPostJobUseCases(),
        hashtag_use_cases=hashtag_use_cases,
    )

    result = asyncio.run(
        registry.execute(
            "get_hashtag",
            {"username": "operator", "name": "test"},
        )
    )

    assert result["id"] == 42
    assert result["name"] == "test"
    assert result["media_count"] == 9876
    assert hashtag_use_cases.get_calls == [("acc-1", "test")]


def test_list_collections_tool_returns_collection_contract():
    collection_use_cases = _StubCollectionUseCases()
    registry = create_tool_registry(
        _StubAccountUseCases(),
        _StubPostJobUseCases(),
        collection_use_cases=collection_use_cases,
    )

    result = asyncio.run(
        registry.execute(
            "list_collections",
            {"username": "@operator"},
        )
    )

    assert result["count"] == 2
    assert result["collections"][0]["pk"] == 71
    assert result["collections"][0]["name"] == "Saved Reads"
    assert collection_use_cases.calls == ["acc-1"]
