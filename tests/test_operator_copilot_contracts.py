"""Contract tests for operator copilot payload structures and adapter compliance.

Verifies:
1. validate_approval_payload(): 5-key contract enforced before interrupt()
2. AUDIT_EVENT_TYPES + AUDIT_EVENT_SCHEMA: canonical taxonomy and fields
3. validate_audit_event_payload(): rejects malformed payloads
4. Schema document in docs/ stays in sync with contract constants
5. ToolRegistryBridgeAdapter: BLOCKED tools filtered from get_schemas()
6. ToolRegistryBridgeAdapter: policy annotation suffixes appended to descriptions
7. ToolRegistryBridgeAdapter: BLOCKED tools raise ValueError in execute()
8. ToolRegistryBridgeAdapter: schema cache invalidation works
9. FakePortCompliance: all fake ports implement their abstract base classes
10. FakeAuditLogPort strict mode enforces event_type + payload schema
11. InMemoryOperatorApprovalAdapter: stores and retrieves pending approvals
12. FileOperatorAuditLogAdapter: logs events to JSONL file

These contract tests do NOT run the full graph pipeline.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest

from ai_copilot.application.ports import (
    AUDIT_EVENT_SCHEMA,
    AUDIT_EVENT_TYPES,
    APPROVAL_PAYLOAD_REQUIRED_KEYS,
    validate_approval_payload,
    validate_audit_event_payload,
    LLMGatewayPort,
    ToolExecutorPort,
    ApprovalPort,
    AuditLogPort,
    CheckpointFactoryPort,
)
from ai_copilot.adapters.fake_ports_operator_copilot import (
    FakeLLMGateway,
    FakeToolExecutor,
    FakeApprovalPort,
    FakeAuditLogPort,
    FakeCheckpointFactory,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _valid_approval_payload(**overrides):
    payload = {
        "operator_intent": "follow top 5 users",
        "proposed_tool_calls": [{"id": "c1", "name": "follow_user", "arguments": {"user_id": "u1"}}],
        "tool_reasons": {"c1": "grow audience"},
        "risk_assessment": {"level": "medium", "reasons": ["write action"], "blocking": False},
        "options": ["approve", "reject", "edit"],
    }
    payload.update(overrides)
    return payload


def _default_audit_field_value(field: str):
    defaults = {
        "thread_id": "thread-1",
        "operator_request": "show account summary",
        "step": 1,
        "stage": "classify_goal",
        "proposed_count": 1,
        "blocked_names": [],
        "executable_count": 1,
        "flags": {"c1": "read_only"},
        "risk_assessment": {"level": "low", "reasons": [], "blocking": False},
        "approval_request": _valid_approval_payload(),
        "approval_result": "approved",
        "call_id": "c1",
        "tool_name": "list_accounts",
        "args": {},
        "result_keys": ["accounts"],
        "error": "boom",
        "matched_intent": True,
        "warnings": [],
        "recommendation": "proceed_to_summary",
        "stop_reason": "done",
    }
    if field not in defaults:
        raise KeyError(f"No test default for audit field {field!r}")
    return defaults[field]


def _valid_audit_payload(event_type: str, **overrides) -> dict:
    schema = AUDIT_EVENT_SCHEMA[event_type]
    payload = {
        key: _default_audit_field_value(key)
        for key in schema["required"]
    }
    payload.update(overrides)
    return payload


# ===========================================================================
# validate_approval_payload contract
# ===========================================================================


def test_valid_payload_passes():
    validate_approval_payload(_valid_approval_payload())  # must not raise


def test_missing_operator_intent_raises():
    payload = _valid_approval_payload()
    del payload["operator_intent"]
    with pytest.raises(ValueError) as exc:
        validate_approval_payload(payload)
    assert "operator_intent" in str(exc.value)


def test_missing_proposed_tool_calls_raises():
    payload = _valid_approval_payload()
    del payload["proposed_tool_calls"]
    with pytest.raises(ValueError) as exc:
        validate_approval_payload(payload)
    assert "proposed_tool_calls" in str(exc.value)


def test_missing_tool_reasons_raises():
    payload = _valid_approval_payload()
    del payload["tool_reasons"]
    with pytest.raises(ValueError) as exc:
        validate_approval_payload(payload)
    assert "tool_reasons" in str(exc.value)


def test_missing_risk_assessment_raises():
    payload = _valid_approval_payload()
    del payload["risk_assessment"]
    with pytest.raises(ValueError) as exc:
        validate_approval_payload(payload)
    assert "risk_assessment" in str(exc.value)


def test_missing_options_raises():
    payload = _valid_approval_payload()
    del payload["options"]
    with pytest.raises(ValueError) as exc:
        validate_approval_payload(payload)
    assert "options" in str(exc.value)


def test_all_missing_keys_listed():
    with pytest.raises(ValueError) as exc:
        validate_approval_payload({})
    msg = str(exc.value)
    for key in APPROVAL_PAYLOAD_REQUIRED_KEYS:
        assert key in msg


# ===========================================================================
# AUDIT_EVENT_TYPES contract
# ===========================================================================


def test_audit_event_types_has_9_values():
    assert len(AUDIT_EVENT_TYPES) == 9


def test_audit_event_types_contains_all_required():
    required = {
        "operator_request",
        "planner_decision",
        "policy_gate",
        "approval_submitted",
        "approval_result",
        "tool_execution",
        "execution_failure",
        "review_finding",
        "stop_reason",
    }
    assert required <= AUDIT_EVENT_TYPES


def test_audit_event_types_match_schema_keys():
    assert AUDIT_EVENT_TYPES == frozenset(AUDIT_EVENT_SCHEMA.keys())


def test_audit_event_types_is_frozenset():
    assert isinstance(AUDIT_EVENT_TYPES, frozenset)


def test_audit_event_schema_required_optional_are_frozensets_and_disjoint():
    for event_type, schema in AUDIT_EVENT_SCHEMA.items():
        required = schema["required"]
        optional = schema["optional"]
        assert isinstance(required, frozenset), event_type
        assert isinstance(optional, frozenset), event_type
        assert required.isdisjoint(optional), event_type


def test_validate_audit_event_payload_accepts_optional_fields():
    payload = _valid_audit_payload("execution_failure", failure_kind="malformed_string_arguments")
    validate_audit_event_payload("execution_failure", payload)


def test_validate_audit_event_payload_rejects_missing_required_field():
    payload = _valid_audit_payload("stop_reason")
    del payload["thread_id"]
    with pytest.raises(ValueError) as exc:
        validate_audit_event_payload("stop_reason", payload)
    assert "missing required fields" in str(exc.value)


def test_validate_audit_event_payload_rejects_undocumented_field():
    payload = _valid_audit_payload("operator_request", unexpected="x")
    with pytest.raises(ValueError) as exc:
        validate_audit_event_payload("operator_request", payload)
    assert "undocumented fields" in str(exc.value)


def test_audit_schema_document_matches_contract():
    doc_path = Path(__file__).parent.parent / "docs" / "operator-audit-event-schema.md"
    text = doc_path.read_text(encoding="utf-8")

    m = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    assert m, "docs/operator-audit-event-schema.md must contain a fenced JSON schema block"
    doc_schema = json.loads(m.group(1))

    expected = {
        event_type: {
            "required": sorted(schema["required"]),
            "optional": sorted(schema["optional"]),
        }
        for event_type, schema in AUDIT_EVENT_SCHEMA.items()
    }
    assert doc_schema == expected


def test_operator_nodes_emit_only_canonical_audit_event_types():
    root = Path(__file__).parent.parent / "backend" / "ai_copilot" / "application" / "graphs" / "operator_copilot"
    files = [
        root / "nodes_plan_policy.py",
        root / "nodes_approval_execution.py",
    ]
    pattern = re.compile(r'audit_log\.log\("([a-z_]+)"')
    emitted = {
        event_type
        for path in files
        for event_type in pattern.findall(path.read_text(encoding="utf-8"))
    }
    assert emitted <= AUDIT_EVENT_TYPES


# ===========================================================================
# APPROVAL_PAYLOAD_REQUIRED_KEYS contract
# ===========================================================================


def test_approval_payload_keys_count():
    assert len(APPROVAL_PAYLOAD_REQUIRED_KEYS) == 5


def test_approval_payload_keys_contains_required():
    expected = {"operator_intent", "proposed_tool_calls", "tool_reasons", "risk_assessment", "options"}
    assert expected == APPROVAL_PAYLOAD_REQUIRED_KEYS


# ===========================================================================
# FakeAuditLogPort contract
# ===========================================================================


@pytest.mark.asyncio
async def test_fake_audit_log_captures_events():
    log = FakeAuditLogPort()
    await log.log("operator_request", _valid_audit_payload("operator_request"))
    await log.log("policy_gate", _valid_audit_payload("policy_gate"))

    assert log.call_count == 2
    assert log.event_types() == ["operator_request", "policy_gate"]


@pytest.mark.asyncio
async def test_fake_audit_log_has_event_true():
    log = FakeAuditLogPort()
    await log.log("stop_reason", _valid_audit_payload("stop_reason"))
    assert log.has_event("stop_reason") is True
    assert log.has_event("tool_execution") is False


@pytest.mark.asyncio
async def test_fake_audit_log_get_events_filters_by_type():
    log = FakeAuditLogPort()
    await log.log("operator_request", _valid_audit_payload("operator_request", operator_request="a"))
    await log.log("policy_gate", _valid_audit_payload("policy_gate"))
    await log.log("operator_request", _valid_audit_payload("operator_request", operator_request="b"))

    events = log.get_events("operator_request")
    assert len(events) == 2
    assert all(e["event_type"] == "operator_request" for e in events)


@pytest.mark.asyncio
async def test_fake_audit_log_strict_rejects_unknown():
    log = FakeAuditLogPort(strict=True)
    with pytest.raises(ValueError) as exc:
        await log.log("completely_unknown_event", {})
    assert "Unknown audit event_type" in str(exc.value)


@pytest.mark.asyncio
async def test_fake_audit_log_strict_rejects_missing_required_payload_field():
    log = FakeAuditLogPort(strict=True)
    with pytest.raises(ValueError) as exc:
        await log.log("stop_reason", {"stop_reason": "done"})
    assert "missing required fields" in str(exc.value)


@pytest.mark.asyncio
async def test_fake_audit_log_non_strict_accepts_unknown():
    log = FakeAuditLogPort(strict=False)
    await log.log("anything_goes", {"x": 1})  # must not raise
    assert log.call_count == 1


@pytest.mark.asyncio
async def test_fake_audit_log_reset():
    log = FakeAuditLogPort()
    await log.log("operator_request", _valid_audit_payload("operator_request"))
    log.reset()
    assert log.call_count == 0
    assert log.events == []


# ===========================================================================
# FakePortCompliance: all fakes implement their ABCs
# ===========================================================================


def test_fake_llm_gateway_implements_port():
    assert isinstance(FakeLLMGateway(), LLMGatewayPort)


def test_fake_tool_executor_implements_port():
    assert isinstance(FakeToolExecutor(), ToolExecutorPort)


def test_fake_approval_port_implements_port():
    assert isinstance(FakeApprovalPort(), ApprovalPort)


def test_fake_audit_log_port_implements_port():
    assert isinstance(FakeAuditLogPort(), AuditLogPort)


def test_fake_checkpoint_factory_implements_port():
    assert isinstance(FakeCheckpointFactory(), CheckpointFactoryPort)


# ===========================================================================
# FakeLLMGateway contract
# ===========================================================================


@pytest.mark.asyncio
async def test_fake_llm_returns_responses_in_sequence():
    llm = FakeLLMGateway(responses=["first", "second"])
    r1 = await llm.request_completion([])
    r2 = await llm.request_completion([])
    assert r1["content"] == "first"
    assert r2["content"] == "second"


@pytest.mark.asyncio
async def test_fake_llm_falls_back_to_default():
    llm = FakeLLMGateway(responses=[], default_response="{}")
    r = await llm.request_completion([])
    assert r["content"] == "{}"


@pytest.mark.asyncio
async def test_fake_llm_call_log_captures_messages():
    llm = FakeLLMGateway(responses=["ok"])
    messages = [{"role": "user", "content": "hello"}]
    await llm.request_completion(messages)
    assert llm.call_count == 1
    assert llm.last_messages() == messages


# ===========================================================================
# FakeToolExecutor contract
# ===========================================================================


@pytest.mark.asyncio
async def test_fake_executor_returns_configured_result():
    executor = FakeToolExecutor(results={"list_accounts": {"accounts": []}})
    result = await executor.execute("list_accounts", {})
    assert result == {"accounts": []}


@pytest.mark.asyncio
async def test_fake_executor_raises_for_missing_tool():
    executor = FakeToolExecutor(results={})
    with pytest.raises(ValueError):
        await executor.execute("unknown_tool", {})


def test_fake_executor_get_schemas_returns_configured():
    schemas = [{"function": {"name": "list_accounts", "description": "test"}}]
    executor = FakeToolExecutor(schemas=schemas)
    assert executor.get_schemas() == schemas


def test_fake_executor_was_called_with():
    executor = FakeToolExecutor(results={"list_accounts": {}})
    assert executor.was_called_with("list_accounts") is False


# ===========================================================================
# ToolRegistryBridgeAdapter contract
# ===========================================================================


def _make_bridge(
    tool_names: list[str],
    annotate: bool = True,
):
    """Build a ToolRegistryBridgeAdapter backed by a FakeToolExecutor."""
    from ai_copilot.adapters.tool_registry_bridge import ToolRegistryBridgeAdapter

    schemas = [
        {"function": {"name": name, "description": f"Does {name}"}}
        for name in tool_names
    ]
    executor = FakeToolExecutor(
        results={name: {} for name in tool_names},
        schemas=schemas,
    )
    return ToolRegistryBridgeAdapter(
        tool_registry=executor,
        annotate_schemas=annotate,
    )


_COMMENT_MODERATION_TOOLS = [
    "like_comment",
    "unlike_comment",
    "pin_comment",
    "unpin_comment",
]


def test_bridge_filters_blocked_tools_from_schemas():
    bridge = _make_bridge(["list_accounts", "delete_account", "follow_user"])
    schemas = bridge.get_schemas()
    names = [s["function"]["name"] for s in schemas]
    assert "delete_account" not in names
    assert "list_accounts" in names
    assert "follow_user" in names


def test_bridge_annotates_read_only_description():
    bridge = _make_bridge(["list_accounts"])
    schemas = bridge.get_schemas()
    desc = schemas[0]["function"]["description"]
    assert "read-only" in desc.lower()
    assert "no approval" in desc.lower()


def test_bridge_annotates_write_sensitive_description():
    bridge = _make_bridge(["follow_user"])
    schemas = bridge.get_schemas()
    desc = schemas[0]["function"]["description"]
    assert "write-sensitive" in desc.lower()
    assert "approval" in desc.lower()


def test_bridge_exposes_comment_moderation_tools_with_policy_hints():
    bridge = _make_bridge(_COMMENT_MODERATION_TOOLS)
    schemas = bridge.get_schemas()
    by_name = {schema["function"]["name"]: schema for schema in schemas}

    for tool_name in _COMMENT_MODERATION_TOOLS:
        assert tool_name in by_name
        desc = by_name[tool_name]["function"]["description"].lower()
        assert "write-sensitive" in desc
        assert "approval" in desc


def test_bridge_exposes_registered_comment_moderation_tools_with_policy_hints():
    from app.adapters.ai.tool_registry.builder import create_tool_registry
    from ai_copilot.adapters.tool_registry_bridge import ToolRegistryBridgeAdapter

    sentinel = object()
    tool_registry = create_tool_registry(
        account_usecases=sentinel,
        postjob_usecases=sentinel,
        hashtag_use_cases=sentinel,
        collection_use_cases=sentinel,
        media_use_cases=sentinel,
        story_use_cases=sentinel,
        highlight_use_cases=sentinel,
        comment_use_cases=sentinel,
        direct_use_cases=sentinel,
        insight_use_cases=sentinel,
        relationship_use_cases=sentinel,
        account_profile_usecases=sentinel,
        account_auth_usecases=sentinel,
        account_proxy_usecases=sentinel,
        proxy_pool_usecases=sentinel,
    )
    bridge = ToolRegistryBridgeAdapter(tool_registry=tool_registry)
    by_name = {schema["function"]["name"]: schema for schema in bridge.get_schemas()}

    for tool_name in _COMMENT_MODERATION_TOOLS:
        assert tool_name in by_name
        desc = by_name[tool_name]["function"]["description"].lower()
        assert "write-sensitive" in desc
        assert "approval" in desc


def test_bridge_no_annotation_when_disabled():
    bridge = _make_bridge(["list_accounts"], annotate=False)
    schemas = bridge.get_schemas()
    desc = schemas[0]["function"]["description"]
    # Original description unchanged
    assert desc == "Does list_accounts"


def test_bridge_caches_schemas():
    bridge = _make_bridge(["list_accounts"])
    s1 = bridge.get_schemas()
    s2 = bridge.get_schemas()
    assert s1 is s2  # same object (cached)


def test_bridge_invalidate_cache_forces_recompute():
    bridge = _make_bridge(["list_accounts"])
    s1 = bridge.get_schemas()
    bridge.invalidate_schema_cache()
    s2 = bridge.get_schemas()
    assert s1 is not s2  # recomputed


@pytest.mark.asyncio
async def test_bridge_execute_blocked_raises():
    bridge = _make_bridge(["delete_account"])
    with pytest.raises(ValueError) as exc:
        await bridge.execute("delete_account", {})
    assert "BLOCKED" in str(exc.value)


@pytest.mark.asyncio
async def test_bridge_execute_unknown_tool_raises():
    bridge = _make_bridge([])
    with pytest.raises(ValueError) as exc:
        await bridge.execute("nonexistent_xyz", {})
    assert "BLOCKED" in str(exc.value)


@pytest.mark.asyncio
async def test_bridge_execute_passes_through_for_readable():
    bridge = _make_bridge(["list_accounts"])
    result = await bridge.execute("list_accounts", {})
    assert result == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", _COMMENT_MODERATION_TOOLS)
async def test_bridge_execute_allows_comment_moderation_tools(tool_name):
    bridge = _make_bridge([tool_name])
    result = await bridge.execute(tool_name, {})
    assert result == {}


@pytest.mark.asyncio
async def test_bridge_planner_context_compacts_managed_accounts():
    from ai_copilot.adapters.tool_registry_bridge import ToolRegistryBridgeAdapter

    executor = FakeToolExecutor(
        results={
            "list_accounts": {
                "accounts": [
                    {"username": "operator", "status": "active", "proxy": "http://proxy:8080"},
                    {"username": "backup", "status": "inactive", "proxy": "none"},
                ],
                "total": 2,
                "active": 1,
            },
        },
        schemas=[{"function": {"name": "list_accounts", "description": "Does list_accounts"}}],
    )
    bridge = ToolRegistryBridgeAdapter(tool_registry=executor)

    context = await bridge.get_planner_context()

    assert context["managed_account_count"] == 2
    assert context["active_account_count"] == 1
    assert context["managed_accounts"] == [
        {"username": "@operator", "status": "active", "proxy": "configured"},
        {"username": "@backup", "status": "inactive", "proxy": "none"},
    ]


def test_bridge_get_policy_summary():
    bridge = _make_bridge(["list_accounts", "follow_user"])
    summary = bridge.get_policy_summary()
    assert summary.get("list_accounts") == "read_only"
    assert summary.get("follow_user") == "write_sensitive"


def test_bridge_get_policy_coverage_report_machine_readable():
    bridge = _make_bridge(["list_accounts", "follow_user"])
    report = bridge.get_policy_coverage_report()
    assert "registered_only" in report
    assert "policy_only" in report
    assert "intentional_exceptions" in report
    assert report["registered_only"] == []
    assert isinstance(report["policy_only"], list)
    assert isinstance(report["intentional_exceptions"], list)


# ===========================================================================
# InMemoryOperatorApprovalAdapter contract
# ===========================================================================


@pytest.mark.asyncio
async def test_approval_adapter_stores_pending():
    from ai_copilot.adapters.operator_copilot_approval_adapter import InMemoryOperatorApprovalAdapter

    adapter = InMemoryOperatorApprovalAdapter()
    payload = _valid_approval_payload()
    result = await adapter.submit_for_approval(payload)
    # Returns a string decision (or pending marker)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_file_audit_log_writes_jsonl():
    from ai_copilot.adapters.operator_copilot_audit_log_adapter import FileOperatorAuditLogAdapter

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name

    try:
        adapter = FileOperatorAuditLogAdapter(log_path=path)
        await adapter.log("operator_request", {
            "thread_id": "t1",
            "operator_request": "hello",
            "step": 1,
        })
        await adapter.log("stop_reason", {"thread_id": "t1", "stop_reason": "done"})

        with open(path) as f:
            lines = [json.loads(l) for l in f if l.strip()]

        assert len(lines) == 2
        assert lines[0]["event_type"] == "operator_request"
        assert lines[1]["event_type"] == "stop_reason"
    finally:
        os.unlink(path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
