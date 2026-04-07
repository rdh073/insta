"""Tests for discovery-first consumer wiring in AI tool registry."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from datetime import datetime, timezone

from app.application.dto.instagram_media_dto import MediaSummary

_TOOL_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "adapters" / "ai" / "tool_registry.py"
)
_SPEC = importlib.util.spec_from_file_location("tool_registry_under_test", _TOOL_REGISTRY_PATH)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
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
