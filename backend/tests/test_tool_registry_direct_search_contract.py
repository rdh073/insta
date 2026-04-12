"""Tests for direct-search tool output contract in AI tool registry."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

from app.application.dto.instagram_direct_dto import DirectSearchUserSummary

_TOOL_REGISTRY_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "adapters" / "ai" / "tool_registry" / "__init__.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "tool_registry_under_test_direct_search",
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


class _StubDirectUseCases:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def search_threads(self, account_id: str, query: str):
        self.calls.append((account_id, query))
        return [
            DirectSearchUserSummary(
                user_id=77,
                username="alice",
                full_name="Alice",
                profile_pic_url="https://example.com/alice.jpg",
                is_private=False,
                is_verified=False,
            )
        ]


def test_search_threads_tool_returns_user_search_contract():
    """search_threads tool must return user-shaped results, not thread-shaped results."""
    direct_use_cases = _StubDirectUseCases()
    registry = create_tool_registry(
        _StubAccountUseCases(),
        _StubPostJobUseCases(),
        direct_use_cases=direct_use_cases,
    )

    result = asyncio.run(
        registry.execute(
            "search_threads",
            {"username": "@operator", "query": "alice"},
        )
    )

    assert result["count"] == 1
    assert list(result.keys()) == ["count", "users"]
    assert result["users"][0]["user_id"] == 77
    assert result["users"][0]["username"] == "alice"
    assert "thread_id" not in result["users"][0]
    assert direct_use_cases.calls == [("acc-1", "alice")]
