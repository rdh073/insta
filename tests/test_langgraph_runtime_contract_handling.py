from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_copilot.adapters.fake_ports_operator_copilot import (
    FakeApprovalPort,
    FakeAuditLogPort,
    FakeCheckpointFactory,
    FakeLLMGateway,
    FakeToolExecutor,
)
from ai_copilot.application.smart_engagement.ports import (
    AccountContextPort,
    ApprovalPort,
    AuditLogPort,
    EngagementCandidatePort,
    EngagementExecutorPort,
    RiskScoringPort,
)
from ai_copilot.application.use_cases.langgraph_runtime_adapter import (
    DEFAULT_LANGGRAPH_VERSION_STRATEGY,
    ainvoke_with_contract,
    astream_with_contract,
    interrupt_payloads_from_exception,
    normalize_stream_chunk,
)
from ai_copilot.application.use_cases.run_operator_copilot import (
    RunOperatorCopilotUseCase,
)
from ai_copilot.application.use_cases.run_smart_engagement import (
    SmartEngagementUseCase,
)
from langgraph.checkpoint.memory import MemorySaver


class _FakeGraphOutput:
    def __init__(self, value, interrupts=()):
        self.value = value
        self.interrupts = interrupts


class _FakeOperatorGraph:
    def __init__(self, chunk_sequences: list[list[dict]]):
        self._chunk_sequences = list(chunk_sequences)
        self.calls: list[dict] = []

    async def astream(
        self,
        graph_input,
        *,
        config=None,
        stream_mode=None,
        version=None,
    ):
        self.calls.append({
            "graph_input": graph_input,
            "config": config,
            "stream_mode": stream_mode,
            "version": version,
        })
        chunks = self._chunk_sequences.pop(0)
        for chunk in chunks:
            yield chunk


class _FakeSmartGraph:
    def __init__(self, results: list):
        self._results = list(results)
        self.calls: list[dict] = []

    async def ainvoke(self, graph_input, *, config=None, version=None):
        self.calls.append({
            "graph_input": graph_input,
            "config": config,
            "version": version,
        })
        item = self._results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _LegacyInvokeOnlyGraph:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    async def ainvoke(self, graph_input, config=None):
        self.calls += 1
        return self.result


class _LegacyStreamOnlyGraph:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.calls = 0

    async def astream(self, graph_input, config=None, stream_mode=None):
        self.calls += 1
        for chunk in self.chunks:
            yield chunk


def _make_operator_use_case() -> RunOperatorCopilotUseCase:
    return RunOperatorCopilotUseCase(
        llm_gateway=FakeLLMGateway(),
        tool_executor=FakeToolExecutor(),
        approval_port=FakeApprovalPort(),
        audit_log=FakeAuditLogPort(),
        checkpoint_factory=FakeCheckpointFactory(),
    )


def _make_smart_use_case() -> SmartEngagementUseCase:
    account_context = AsyncMock(spec=AccountContextPort)
    candidate_discovery = AsyncMock(spec=EngagementCandidatePort)
    risk_scoring = AsyncMock(spec=RiskScoringPort)
    approval = AsyncMock(spec=ApprovalPort)
    executor = AsyncMock(spec=EngagementExecutorPort)
    executor.is_write_action = MagicMock(return_value=True)
    audit_log = AsyncMock(spec=AuditLogPort)
    audit_log.get_audit_trail = AsyncMock(return_value=[])

    return SmartEngagementUseCase(
        account_context=account_context,
        candidate_discovery=candidate_discovery,
        risk_scoring=risk_scoring,
        approval=approval,
        executor=executor,
        audit_log=audit_log,
        checkpointer=MemorySaver(),
    )


async def _collect(async_iter):
    return [item async for item in async_iter]


def test_normalize_stream_chunk_supports_legacy_and_v2_shapes():
    payload = {"approval_id": "apr_1", "options": ["approved", "rejected"]}
    legacy = {
        "__interrupt__": [SimpleNamespace(value=payload)],
        "plan_actions": {"execution_plan": [{"step": 1}]},
    }
    v2 = {
        "type": "updates",
        "ns": (),
        "data": {
            "__interrupt__": [SimpleNamespace(value=payload)],
            "review_tool_policy": {"tool_policy_flags": {"c1": "write_sensitive"}},
        },
    }

    legacy_norm = normalize_stream_chunk(legacy)
    v2_norm = normalize_stream_chunk(v2)

    assert any(e.kind == "interrupt" and e.payload == payload for e in legacy_norm.entries)
    assert any(e.kind == "update" and e.node_name == "plan_actions" for e in legacy_norm.entries)
    assert any(e.kind == "interrupt" and e.payload == payload for e in v2_norm.entries)
    assert any(e.kind == "update" and e.node_name == "review_tool_policy" for e in v2_norm.entries)


@pytest.mark.asyncio
async def test_invoke_and_stream_contract_fallback_to_legacy_when_version_unsupported():
    invoke_graph = _LegacyInvokeOnlyGraph(result={"ok": True})
    stream_graph = _LegacyStreamOnlyGraph(chunks=[{"node_a": {"x": 1}}])

    invoke_result = await ainvoke_with_contract(
        invoke_graph,
        {"input": "x"},
        config={"configurable": {"thread_id": "t-1"}},
        strategy=DEFAULT_LANGGRAPH_VERSION_STRATEGY,
    )
    stream_chunks = [
        chunk
        async for chunk in astream_with_contract(
            stream_graph,
            {"input": "x"},
            config={"configurable": {"thread_id": "t-2"}},
            strategy=DEFAULT_LANGGRAPH_VERSION_STRATEGY,
        )
    ]

    assert invoke_result == {"ok": True}
    assert invoke_graph.calls == 1
    assert stream_graph.calls == 1
    assert len(stream_chunks) == 1
    assert stream_chunks[0].entries[0].node_name == "node_a"


def test_interrupt_payloads_from_graph_interrupt_exception_shape():
    GraphInterrupt = type("GraphInterrupt", (Exception,), {})
    payload = {"approval_id": "apr_2"}
    exc = GraphInterrupt([SimpleNamespace(value=payload)])

    extracted = interrupt_payloads_from_exception(exc)
    assert extracted == (payload,)


@pytest.mark.asyncio
async def test_operator_run_detects_v2_stream_interrupt():
    payload = {
        "operator_intent": "follow top users",
        "proposed_tool_calls": [{"id": "c1", "name": "follow_user", "arguments": {"user_id": "u1"}}],
        "tool_reasons": {"c1": "growth"},
        "risk_assessment": {"level": "medium", "reasons": [], "blocking": False},
        "options": ["approved", "rejected", "edited"],
    }
    graph = _FakeOperatorGraph(chunk_sequences=[[
        {
            "type": "updates",
            "ns": (),
            "data": {"__interrupt__": [SimpleNamespace(value=payload)]},
        },
    ]])
    use_case = _make_operator_use_case()
    use_case._graph = graph

    events = await _collect(use_case.run("follow top users", thread_id="t-op-run-v2"))
    assert [e["type"] for e in events] == ["run_start", "approval_required"]
    assert events[1]["payload"] == payload
    assert graph.calls[0]["version"] == "v2"


@pytest.mark.asyncio
async def test_operator_resume_detects_legacy_stream_interrupt():
    payload = {
        "operator_intent": "follow top users",
        "proposed_tool_calls": [{"id": "c1", "name": "follow_user", "arguments": {"user_id": "u2"}}],
        "tool_reasons": {"c1": "growth"},
        "risk_assessment": {"level": "medium", "reasons": [], "blocking": False},
        "options": ["approved", "rejected", "edited"],
    }
    graph = _FakeOperatorGraph(chunk_sequences=[[
        {"__interrupt__": [SimpleNamespace(value=payload)]},
    ]])
    use_case = _make_operator_use_case()
    use_case._graph = graph

    events = await _collect(
        use_case.resume(
            thread_id="t-op-resume-legacy",
            approval_result="approved",
        ),
    )
    assert [e["type"] for e in events] == ["run_start", "approval_required"]
    assert events[1]["payload"] == payload


@pytest.mark.asyncio
async def test_smart_engagement_run_detects_v2_invoke_interrupt():
    payload = {"approval_id": "apr_3", "decision_options": ["approved", "rejected"]}
    graph = _FakeSmartGraph(
        results=[
            _FakeGraphOutput(
                value={"audit_trail": [{"event_type": "approval_requested"}]},
                interrupts=(SimpleNamespace(value=payload),),
            ),
        ],
    )
    use_case = _make_smart_use_case()
    use_case.graph = graph

    result = await use_case.run(
        execution_mode="execute",
        goal="follow relevant users",
        metadata={"thread_id": "t-se-run-v2"},
    )

    assert result["status"] == "interrupted"
    assert result["interrupted"] is True
    assert result["interrupt_payload"] == payload
    assert result["thread_id"] == "t-se-run-v2"
    assert graph.calls[0]["version"] == "v2"


@pytest.mark.asyncio
async def test_smart_engagement_resume_detects_legacy_invoke_interrupt():
    payload = {"approval_id": "apr_4", "decision_options": ["approved", "rejected"]}
    graph = _FakeSmartGraph(
        results=[
            {
                "__interrupt__": [SimpleNamespace(value=payload)],
                "audit_trail": [{"event_type": "approval_requested"}],
            },
        ],
    )
    use_case = _make_smart_use_case()
    use_case.graph = graph

    result = await use_case.resume(
        thread_id="t-se-resume-legacy",
        decision={"decision": "approved"},
    )

    assert result["status"] == "interrupted"
    assert result["interrupted"] is True
    assert result["interrupt_payload"] == payload
    assert result["thread_id"] == "t-se-resume-legacy"
