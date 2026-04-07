"""Tests for EngagementExecutorAdapter comment execution contract."""

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


class _StubComment:
    def __init__(self, pk: int):
        self.pk = pk


class _StubCommentWriter:
    def __init__(self):
        self.calls = []

    def create_comment(
        self,
        account_id: str,
        media_id: str,
        text: str,
        reply_to_comment_id: int | None = None,
    ):
        self.calls.append((account_id, media_id, text, reply_to_comment_id))
        return _StubComment(pk=4321)


class _StubCommentUseCases:
    def __init__(self):
        self.calls = []

    def create_comment(
        self,
        account_id: str,
        media_id: str,
        text: str,
        reply_to_comment_id: int | None = None,
    ):
        self.calls.append((account_id, media_id, text, reply_to_comment_id))
        return _StubComment(pk=8765)


def test_execute_comment_returns_action_id_from_comment_writer():
    """execute_comment must return ExecutionResult.action_id (not comment_id)."""
    comment_use_cases = _StubCommentUseCases()
    adapter = EngagementExecutorAdapter(
        account_id="acc-default",
        comment_use_cases=comment_use_cases,
    )

    result = asyncio.run(
        adapter.execute_comment(
            post_id="media-123",
            account_id="acc-1",
            comment_text="Great post!",
        )
    )

    assert result["success"] is True
    assert result["action_id"] == "8765"
    assert result["reason_code"] == "ok"
    assert "comment_id" not in result
    assert comment_use_cases.calls == [("acc-1", "media-123", "Great post!", None)]


def test_execute_comment_without_writer_fails_cleanly():
    """execute_comment should fail with stable reason when writer is missing."""
    adapter = EngagementExecutorAdapter(account_id="acc-default", comment_use_cases=None)

    result = asyncio.run(
        adapter.execute_comment(
            post_id="media-123",
            account_id="acc-1",
            comment_text="Great post!",
        )
    )

    assert result["success"] is False
    assert result["action_id"] is None
    assert result["reason_code"] == "adapter_not_configured"


def test_execute_comment_prefers_comment_use_case_seam():
    """execute_comment should prefer CommentUseCases when provided."""
    comment_use_cases = _StubCommentUseCases()
    adapter = EngagementExecutorAdapter(
        account_id="acc-default",
        comment_use_cases=comment_use_cases,
    )

    result = asyncio.run(
        adapter.execute_comment(
            post_id="media-777",
            account_id="acc-7",
            comment_text="Awesome!",
        )
    )

    assert result["success"] is True
    assert result["action_id"] == "8765"
    assert result["reason_code"] == "ok"
    assert comment_use_cases.calls == [("acc-7", "media-777", "Awesome!", None)]
