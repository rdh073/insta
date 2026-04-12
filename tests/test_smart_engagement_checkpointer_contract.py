"""Checkpointer contract tests for SmartEngagementUseCase and wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.checkpoint.memory import MemorySaver

from ai_copilot.application.graphs.smart_engagement import build_smart_engagement_graph
from ai_copilot.application.smart_engagement.nodes import SmartEngagementNodes
from ai_copilot.application.smart_engagement.ports import (
    AccountContextPort,
    ApprovalPort,
    AuditLogPort,
    EngagementCandidatePort,
    EngagementExecutorPort,
    RiskScoringPort,
)
from ai_copilot.application.use_cases.run_smart_engagement import SmartEngagementUseCase
from app.bootstrap.container import _build_smart_engagement


def _make_ports() -> dict:
    account_context = AsyncMock(spec=AccountContextPort)
    candidate_discovery = AsyncMock(spec=EngagementCandidatePort)
    risk_scoring = AsyncMock(spec=RiskScoringPort)
    approval = AsyncMock(spec=ApprovalPort)
    executor = AsyncMock(spec=EngagementExecutorPort)
    executor.is_write_action = MagicMock(return_value=True)
    audit_log = AsyncMock(spec=AuditLogPort)
    audit_log.get_audit_trail = AsyncMock(return_value=[])
    return {
        "account_context": account_context,
        "candidate_discovery": candidate_discovery,
        "risk_scoring": risk_scoring,
        "approval": approval,
        "executor": executor,
        "audit_log": audit_log,
    }


def _make_use_case(**kwargs) -> SmartEngagementUseCase:
    return SmartEngagementUseCase(**_make_ports(), **kwargs)


def _make_nodes() -> SmartEngagementNodes:
    return SmartEngagementNodes(**_make_ports())


class _AsyncFactory:
    def __init__(self, checkpointer):
        self._checkpointer = checkpointer
        self.async_calls = 0

    async def create_async(self):
        self.async_calls += 1
        return self._checkpointer


class _AsyncAndSyncFactory(_AsyncFactory):
    def create_checkpointer(self):
        raise AssertionError("create_checkpointer() should not be used when create_async() exists")


class _SyncFactory:
    def __init__(self, checkpointer):
        self._checkpointer = checkpointer
        self.sync_calls = 0

    def create_checkpointer(self):
        self.sync_calls += 1
        return self._checkpointer


def test_use_case_accepts_direct_checkpointer():
    checkpointer = MemorySaver()
    use_case = _make_use_case(checkpointer=checkpointer)

    assert use_case.graph is not None
    assert use_case._checkpointer is checkpointer


@pytest.mark.asyncio
async def test_use_case_prefers_async_factory_path_when_available():
    checkpointer = MemorySaver()
    factory = _AsyncAndSyncFactory(checkpointer)
    use_case = _make_use_case(checkpoint_factory=factory)

    assert use_case.graph is None
    assert use_case._checkpointer is None

    await use_case._ensure_graph()

    assert factory.async_calls == 1
    assert use_case.graph is not None
    assert use_case._checkpointer is checkpointer


def test_use_case_supports_sync_factory_without_create_async():
    checkpointer = MemorySaver()
    factory = _SyncFactory(checkpointer)
    use_case = _make_use_case(checkpoint_factory=factory)

    assert factory.sync_calls == 1
    assert use_case.graph is not None
    assert use_case._checkpointer is checkpointer


def test_use_case_uses_memorysaver_fallback_when_no_config_is_supplied():
    use_case = _make_use_case()

    assert use_case.graph is not None
    assert isinstance(use_case._checkpointer, MemorySaver)


def test_use_case_rejects_both_checkpointer_and_factory():
    with pytest.raises(ValueError, match="either 'checkpointer' or 'checkpoint_factory'"):
        _make_use_case(checkpointer=MemorySaver(), checkpoint_factory=_AsyncFactory(MemorySaver()))


def test_use_case_rejects_invalid_factory_shape():
    with pytest.raises(ValueError, match="checkpoint_factory"):
        _make_use_case(checkpoint_factory=object())


def test_use_case_rejects_invalid_checkpointer_shape():
    with pytest.raises(ValueError, match="Invalid smart engagement checkpointer"):
        _make_use_case(checkpointer=object())


def test_graph_builder_requires_checkpointer():
    with pytest.raises(ValueError, match="requires a checkpointer"):
        build_smart_engagement_graph(_make_nodes(), checkpointer=None)


def test_container_wiring_builds_rec_and_exec_with_compliant_factory(monkeypatch):
    monkeypatch.setenv("SMART_ENGAGEMENT_EXECUTION_ENABLED", "true")
    factory = _AsyncFactory(MemorySaver())

    services = _build_smart_engagement(
        account_usecases=MagicMock(),
        ig_usecases={
            "identity": MagicMock(),
            "relationships": MagicMock(),
            "media": MagicMock(),
            "comment": MagicMock(),
            "direct": MagicMock(),
        },
        ai_services={"checkpoint_factory": factory},
    )

    assert services["rec"] is not None
    assert services["exec"] is not None
    assert services["rec"].graph is None
    assert services["exec"].graph is None


def test_container_wiring_rejects_missing_checkpoint_factory():
    with pytest.raises(RuntimeError, match="checkpoint_factory"):
        _build_smart_engagement(
            account_usecases=MagicMock(),
            ig_usecases={
                "identity": MagicMock(),
                "relationships": MagicMock(),
                "media": MagicMock(),
                "comment": MagicMock(),
                "direct": MagicMock(),
            },
            ai_services={"checkpoint_factory": None},
        )
