"""Phase 10 normalization tests for smart engagement adapters."""

from __future__ import annotations

import asyncio
import sys
import types

if "langgraph.graph" not in sys.modules:
    langgraph_module = types.ModuleType("langgraph")
    graph_module = types.ModuleType("langgraph.graph")
    graph_module.add_messages = lambda x: x
    langgraph_module.graph = graph_module
    sys.modules["langgraph"] = langgraph_module
    sys.modules["langgraph.graph"] = graph_module

from ai_copilot.adapters.account_context_adapter import AccountContextAdapter
from ai_copilot.adapters.engagement_candidate_adapter import EngagementCandidateAdapter
from ai_copilot.adapters.engagement_executor_adapter import EngagementExecutorAdapter


class _StubAccountService:
    def __init__(self, status: str = "active"):
        self.status = status

    def get_accounts_summary(self) -> dict:
        return {
            "accounts": [
                {
                    "id": "acc-1",
                    "username": "operator",
                    "status": self.status,
                    "proxy": "none",
                }
            ]
        }


class _StubDataPort:
    async def get_followers(self, account_id: str, limit: int = 100, filters: dict | None = None):
        return [{"target_id": "alice", "target_type": "account", "metadata": {"follower_count": 100}}]

    async def get_following(self, account_id: str, limit: int = 100, filters: dict | None = None):
        return [{"target_id": "bob", "target_type": "account", "metadata": {"follower_count": 200}}]

    async def get_recent_posts(self, account_id: str, limit: int = 50, filters: dict | None = None):
        return [{"target_id": "123", "target_type": "post", "metadata": {"likes": 99}}]

    async def get_target_metadata(self, account_id: str, target_id: str):
        return {"target_id": target_id}


def test_account_context_adapter_reads_status_from_account_usecases():
    adapter = AccountContextAdapter(account_service=_StubAccountService(status="active"))

    health = asyncio.run(adapter.get_account_context("acc-1"))

    assert health["status"] == "active"
    assert health["login_state"] == "logged_in"


def test_candidate_adapter_not_placeholder_uses_data_port():
    adapter = EngagementCandidateAdapter(data_port=_StubDataPort())

    candidates = asyncio.run(
        adapter.discover_candidates(account_id="acc-1", goal="comment recent posts", filters={"max_results": 1})
    )

    assert len(candidates) == 1
    assert candidates[0]["target_type"] == "post"


def test_executor_follow_like_are_unsupported_actions():
    adapter = EngagementExecutorAdapter(
        account_id="acc-1",
        direct_use_cases=None,
        comment_use_cases=None,
    )

    follow_result = asyncio.run(adapter.execute_follow(target_id="target", account_id="acc-1"))
    like_result = asyncio.run(adapter.execute_like(post_id="123", account_id="acc-1"))

    assert follow_result["success"] is False
    assert follow_result["reason_code"] == "unsupported_action"
    assert like_result["success"] is False
    assert like_result["reason_code"] == "unsupported_action"
