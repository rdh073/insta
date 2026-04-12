"""Tests for collection tool wiring in AI tool registry."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

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


class _StubCollectionUseCases:
    def __init__(self):
        self.pk_calls: list[tuple[str, str]] = []
        self.posts_calls: list[tuple[str, int, int, int]] = []

    def get_collection_pk_by_name(self, account_id: str, name: str) -> int:
        self.pk_calls.append((account_id, name))
        return 99

    def get_collection_posts(
        self,
        account_id: str,
        collection_pk: int,
        amount: int = 21,
        last_media_pk: int = 0,
    ):
        self.posts_calls.append((account_id, collection_pk, amount, last_media_pk))
        return [
            MediaSummary(
                pk=321,
                media_id="321_1",
                code="CODE321",
                media_type=1,
                product_type="feed",
                owner_username="author_b",
                caption_text="saved post",
                like_count=101,
                comment_count=11,
                taken_at=datetime(2025, 1, 3, tzinfo=timezone.utc),
            )
        ]


def test_get_collection_posts_tool_uses_collection_usecases_dto_boundary():
    """Tool get_collection_posts must consume collection use-case DTOs only."""
    collection_use_cases = _StubCollectionUseCases()
    registry = create_tool_registry(
        _StubAccountUseCases(),
        _StubPostJobUseCases(),
        collection_use_cases=collection_use_cases,
    )

    result = asyncio.run(
        registry.execute(
            "get_collection_posts",
            {
                "username": "@operator",
                "collection_name": "  Saved  ",
                "amount": 1,
                "last_media_pk": 0,
            },
        )
    )

    assert result["collection"] == "Saved"
    assert result["collection_pk"] == 99
    assert result["count"] == 1
    assert result["posts"][0]["post_id"] == 321
    assert result["posts"][0]["caption_text"] == "saved post"
    assert "user" not in result["posts"][0]
    assert collection_use_cases.pk_calls == [("acc-1", "Saved")]
    assert collection_use_cases.posts_calls == [("acc-1", 99, 1, 0)]


def test_get_collection_posts_tool_validates_collection_name():
    """Tool should fail fast on missing collection_name."""
    registry = create_tool_registry(
        _StubAccountUseCases(),
        _StubPostJobUseCases(),
        collection_use_cases=_StubCollectionUseCases(),
    )

    result = asyncio.run(
        registry.execute(
            "get_collection_posts",
            {"username": "operator", "collection_name": "   "},
        )
    )

    assert "error" in result
    assert "collection_name is required" in result["error"]
