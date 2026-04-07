"""Tests for EngagementExecutorAdapter DM execution contract."""

from __future__ import annotations

import asyncio
import sys
import types

# Minimal shim so importing smart_engagement ports/state does not require langgraph package.
if "langgraph.graph" not in sys.modules:
    langgraph_module = types.ModuleType("langgraph")
    graph_module = types.ModuleType("langgraph.graph")
    graph_module.add_messages = lambda x: x
    langgraph_module.graph = graph_module
    sys.modules["langgraph"] = langgraph_module
    sys.modules["langgraph.graph"] = graph_module

from ai_copilot.adapters.engagement_executor_adapter import EngagementExecutorAdapter


class _StubSentMessage:
    def __init__(self, direct_message_id: str):
        self.direct_message_id = direct_message_id


class _StubIdentityUseCases:
    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def get_public_user_by_id(self, account_id: str, user_id: int):
        self.calls.append((account_id, user_id))
        return {"pk": user_id}


class _StubDirectUseCases:
    def __init__(self):
        self.calls = []

    def send_to_username(self, account_id: str, username: str, text: str):
        self.calls.append(("send_to_username", account_id, username, text))
        return _StubSentMessage(direct_message_id="dm-654")

    def send_to_users(self, account_id: str, user_ids: list[int], text: str):
        self.calls.append(("send_to_users", account_id, user_ids, text))
        return _StubSentMessage(direct_message_id="dm-321")


def test_execute_dm_without_direct_usecases_fails_cleanly():
    adapter = EngagementExecutorAdapter(
        account_id="acc-default",
        direct_use_cases=None,
        comment_use_cases=None,
    )

    result = asyncio.run(
        adapter.execute_dm(
            target_id="target_user",
            account_id="acc-1",
            message="Hello from test",
        )
    )

    assert result["success"] is False
    assert result["action_id"] is None
    assert result["reason_code"] == "adapter_not_configured"


def test_execute_dm_prefers_direct_use_case_seam_for_username():
    direct_use_cases = _StubDirectUseCases()
    adapter = EngagementExecutorAdapter(
        account_id="acc-default",
        direct_use_cases=direct_use_cases,
        comment_use_cases=None,
    )

    result = asyncio.run(
        adapter.execute_dm(
            target_id="target_user",
            account_id="acc-2",
            message="Hi seam",
        )
    )

    assert result["success"] is True
    assert result["action_id"] == "dm-654"
    assert result["reason_code"] == "ok"
    assert direct_use_cases.calls == [("send_to_username", "acc-2", "target_user", "Hi seam")]


def test_execute_dm_numeric_target_validates_with_identity_usecases_when_available():
    direct_use_cases = _StubDirectUseCases()
    identity_use_cases = _StubIdentityUseCases()
    adapter = EngagementExecutorAdapter(
        account_id="acc-default",
        direct_use_cases=direct_use_cases,
        comment_use_cases=None,
        identity_use_cases=identity_use_cases,
    )

    result = asyncio.run(
        adapter.execute_dm(
            target_id="789",
            account_id="acc-9",
            message="Ping seam",
        )
    )

    assert result["success"] is True
    assert result["action_id"] == "dm-321"
    assert result["reason_code"] == "ok"
    assert identity_use_cases.calls == [("acc-9", 789)]
    assert direct_use_cases.calls == [("send_to_users", "acc-9", [789], "Ping seam")]
