"""Unit tests for operator copilot — policy classification, state, and node functions.

Tests cover:
- ToolPolicyRegistry: classify, classify_calls, has_blocked, has_write_sensitive,
  all_read_only, filter_executable
- make_initial_state: field initialisation, UUID generation
- validate_approval_payload: contract enforcement
- ingest_request_node: step_count increment, approval_attempted reset
- classify_goal_node: blocked intent, normal intent, JSON parse error fallback
- plan_actions_node: strips unknown tool names, returns empty plan
- review_tool_policy_node: flags classification, strips BLOCKED, risk assessment
- execute_tools_node: calls executor, captures results, logs failures
- finish_node: sets stop_reason

Uses FakeLLMGateway, FakeToolExecutor, FakeApprovalPort, FakeAuditLogPort.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import pytest

from app.adapters.ai.tool_registry.core import ToolRegistry
from ai_copilot.application.operator_copilot_policy import ToolPolicy, ToolPolicyRegistry
from ai_copilot.application.state import (
    VALID_APPROVAL_RESULTS,
    VALID_STOP_REASONS,
    make_initial_state,
)
from ai_copilot.application.ports import (
    AUDIT_EVENT_TYPES,
    APPROVAL_PAYLOAD_REQUIRED_KEYS,
    validate_approval_payload,
)
from ai_copilot.adapters.fake_ports_operator_copilot import (
    FakeLLMGateway,
    FakeToolExecutor,
    FakeApprovalPort,
    FakeAuditLogPort,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_nodes(
    llm=None,
    executor=None,
    approval=None,
    audit=None,
    policy=None,
):
    from ai_copilot.application.graphs.operator_copilot import OperatorCopilotNodes

    return OperatorCopilotNodes(
        llm_gateway=llm or FakeLLMGateway(),
        tool_executor=executor or FakeToolExecutor(),
        approval_port=approval or FakeApprovalPort(),
        audit_log=audit or FakeAuditLogPort(),
        policy_registry=policy or ToolPolicyRegistry(),
    )


def _base_state(**overrides):
    state = {
        "messages": [],
        "current_tool_calls": None,
        "tool_results": {},
        "stop_reason": None,
        "step_count": 0,
        "thread_id": "test-thread",
        "operator_request": "show my accounts",
        "normalized_goal": None,
        "execution_plan": None,
        "proposed_tool_calls": [],
        "approved_tool_calls": [],
        "tool_policy_flags": {},
        "risk_assessment": None,
        "approval_request": None,
        "approval_result": None,
        "review_findings": None,
        "final_response": None,
        "approval_attempted": False,
    }
    state.update(overrides)
    return state


class RegistryBackedToolExecutor:
    """Test executor that forwards to app ToolRegistry."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def execute(self, tool_name: str, args: dict) -> dict:
        return await self.registry.execute(tool_name, args)

    def get_schemas(self) -> list[dict]:
        return self.registry.get_schemas()


# ===========================================================================
# ToolPolicyRegistry unit tests
# ===========================================================================


def test_classify_read_only():
    reg = ToolPolicyRegistry()
    cls = reg.classify("list_accounts")
    assert cls.policy == ToolPolicy.READ_ONLY
    assert cls.requires_approval is False
    assert cls.reason  # non-empty


def test_classify_write_sensitive():
    reg = ToolPolicyRegistry()
    cls = reg.classify("follow_user")
    assert cls.policy == ToolPolicy.WRITE_SENSITIVE
    assert cls.requires_approval is True


@pytest.mark.parametrize(
    "tool_name",
    ["like_comment", "unlike_comment", "pin_comment", "unpin_comment"],
)
def test_comment_moderation_tools_classified_write_sensitive(tool_name):
    reg = ToolPolicyRegistry()
    cls = reg.classify(tool_name)
    assert cls.policy == ToolPolicy.WRITE_SENSITIVE
    assert cls.requires_approval is True
    assert "comment" in cls.reason.lower()


@pytest.mark.parametrize(
    ("tool_name", "expected_policy", "requires_approval"),
    [
        ("search_hashtags", ToolPolicy.READ_ONLY, False),
        ("get_hashtag", ToolPolicy.READ_ONLY, False),
        ("list_collections", ToolPolicy.READ_ONLY, False),
        ("get_media_oembed", ToolPolicy.READ_ONLY, False),
        ("get_story", ToolPolicy.READ_ONLY, False),
        ("get_highlight", ToolPolicy.READ_ONLY, False),
        ("delete_story", ToolPolicy.WRITE_SENSITIVE, True),
        ("mark_stories_seen", ToolPolicy.WRITE_SENSITIVE, True),
        ("change_highlight_title", ToolPolicy.WRITE_SENSITIVE, True),
        ("add_stories_to_highlight", ToolPolicy.WRITE_SENSITIVE, True),
        ("remove_stories_from_highlight", ToolPolicy.WRITE_SENSITIVE, True),
        ("approve_pending_direct_thread", ToolPolicy.WRITE_SENSITIVE, True),
        ("mark_direct_thread_seen", ToolPolicy.WRITE_SENSITIVE, True),
    ],
)
def test_new_langgraph_exposure_tools_classification(tool_name, expected_policy, requires_approval):
    reg = ToolPolicyRegistry()
    cls = reg.classify(tool_name)
    assert cls.policy == expected_policy
    assert cls.requires_approval is requires_approval


def test_classify_blocked():
    reg = ToolPolicyRegistry()
    cls = reg.classify("delete_account")
    assert cls.policy == ToolPolicy.BLOCKED
    assert cls.requires_approval is False


def test_classify_unknown_is_blocked():
    reg = ToolPolicyRegistry()
    cls = reg.classify("nonexistent_tool_xyz")
    assert cls.policy == ToolPolicy.BLOCKED
    assert "allowlist" in cls.reason.lower() or "unknown" in cls.reason.lower()


def test_classify_calls_returns_mapping():
    reg = ToolPolicyRegistry()
    calls = [
        {"id": "c1", "name": "list_accounts"},
        {"id": "c2", "name": "follow_user"},
    ]
    flags = reg.classify_calls(calls)
    assert flags["c1"] == "read_only"
    assert flags["c2"] == "write_sensitive"


def test_has_blocked_true():
    reg = ToolPolicyRegistry()
    calls = [
        {"id": "c1", "name": "list_accounts"},
        {"id": "c2", "name": "delete_account"},
    ]
    assert reg.has_blocked(calls) is True


def test_has_blocked_false():
    reg = ToolPolicyRegistry()
    calls = [{"id": "c1", "name": "list_accounts"}]
    assert reg.has_blocked(calls) is False


def test_has_write_sensitive_true():
    reg = ToolPolicyRegistry()
    calls = [{"id": "c1", "name": "follow_user"}]
    assert reg.has_write_sensitive(calls) is True


def test_has_write_sensitive_false():
    reg = ToolPolicyRegistry()
    calls = [{"id": "c1", "name": "list_accounts"}]
    assert reg.has_write_sensitive(calls) is False


def test_all_read_only_true():
    reg = ToolPolicyRegistry()
    calls = [
        {"id": "c1", "name": "list_accounts"},
        {"id": "c2", "name": "get_posts"},
    ]
    assert reg.all_read_only(calls) is True


def test_all_read_only_false_when_write():
    reg = ToolPolicyRegistry()
    calls = [
        {"id": "c1", "name": "list_accounts"},
        {"id": "c2", "name": "follow_user"},
    ]
    assert reg.all_read_only(calls) is False


def test_filter_executable_removes_blocked():
    reg = ToolPolicyRegistry()
    calls = [
        {"id": "c1", "name": "list_accounts"},
        {"id": "c2", "name": "delete_account"},   # BLOCKED
        {"id": "c3", "name": "follow_user"},
    ]
    result = reg.filter_executable(calls)
    names = [c["name"] for c in result]
    assert "delete_account" not in names
    assert "list_accounts" in names
    assert "follow_user" in names


def test_filter_executable_all_blocked_returns_empty():
    reg = ToolPolicyRegistry()
    calls = [
        {"id": "c1", "name": "delete_account"},
        {"id": "c2", "name": "bulk_dm"},
    ]
    assert reg.filter_executable(calls) == []


def test_classify_actual_registered_tool_names():
    reg = ToolPolicyRegistry()

    assert reg.classify("list_followers").policy == ToolPolicy.READ_ONLY
    assert reg.classify("list_following").policy == ToolPolicy.READ_ONLY
    assert reg.classify("list_proxy_pool").policy == ToolPolicy.READ_ONLY
    assert reg.classify("pick_proxy").policy == ToolPolicy.READ_ONLY
    assert reg.classify("get_direct_thread").policy == ToolPolicy.READ_ONLY
    assert reg.classify("list_direct_messages").policy == ToolPolicy.READ_ONLY
    assert reg.classify("search_hashtags").policy == ToolPolicy.READ_ONLY
    assert reg.classify("get_hashtag").policy == ToolPolicy.READ_ONLY
    assert reg.classify("list_collections").policy == ToolPolicy.READ_ONLY
    assert reg.classify("get_media_oembed").policy == ToolPolicy.READ_ONLY
    assert reg.classify("get_story").policy == ToolPolicy.READ_ONLY
    assert reg.classify("get_highlight").policy == ToolPolicy.READ_ONLY

    assert reg.classify("import_proxies").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("recheck_proxy_pool").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("delete_proxy").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("send_message_to_thread").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("find_or_create_direct_thread").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("delete_direct_message").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("delete_story").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("mark_stories_seen").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("change_highlight_title").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("add_stories_to_highlight").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("remove_stories_from_highlight").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("approve_pending_direct_thread").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("mark_direct_thread_seen").policy == ToolPolicy.WRITE_SENSITIVE


# ===========================================================================
# make_initial_state tests
# ===========================================================================


def test_make_initial_state_fields():
    state = make_initial_state("test request", thread_id="t-abc")
    assert state["operator_request"] == "test request"
    assert state["thread_id"] == "t-abc"
    assert state["step_count"] == 0
    assert state["proposed_tool_calls"] == []
    assert state["approved_tool_calls"] == []
    assert state["tool_policy_flags"] == {}
    assert state["approval_attempted"] is False
    assert state["stop_reason"] is None
    assert state["final_response"] is None


def test_make_initial_state_auto_generates_thread_id():
    state = make_initial_state("test request")
    assert state["thread_id"]
    assert len(state["thread_id"]) > 0


def test_make_initial_state_different_threads():
    a = make_initial_state("req")
    b = make_initial_state("req")
    assert a["thread_id"] != b["thread_id"]


# ===========================================================================
# validate_approval_payload tests
# ===========================================================================


def test_validate_approval_payload_passes():
    payload = {
        "operator_intent": "follow top users",
        "proposed_tool_calls": [{"id": "c1", "name": "follow_user", "arguments": {}}],
        "tool_reasons": {"c1": "grow audience"},
        "risk_assessment": {"level": "medium", "reasons": [], "blocking": False},
        "options": ["approve", "reject", "edit"],
    }
    validate_approval_payload(payload)  # must not raise


def test_validate_approval_payload_missing_key_raises():
    payload = {
        "operator_intent": "follow top users",
        "proposed_tool_calls": [],
        # missing: tool_reasons, risk_assessment, options
    }
    with pytest.raises(ValueError) as exc_info:
        validate_approval_payload(payload)
    assert "missing required keys" in str(exc_info.value).lower()


def test_validate_approval_payload_lists_all_missing():
    payload = {}
    with pytest.raises(ValueError) as exc_info:
        validate_approval_payload(payload)
    msg = str(exc_info.value)
    for key in APPROVAL_PAYLOAD_REQUIRED_KEYS:
        assert key in msg


# ===========================================================================
# VALID_APPROVAL_RESULTS and VALID_STOP_REASONS constants
# ===========================================================================


def test_valid_approval_results_contains_expected():
    assert "approved" in VALID_APPROVAL_RESULTS
    assert "rejected" in VALID_APPROVAL_RESULTS
    assert "edited" in VALID_APPROVAL_RESULTS
    assert "timeout" in VALID_APPROVAL_RESULTS


def test_valid_stop_reasons_contains_expected():
    assert "done" in VALID_STOP_REASONS
    assert "rejected" in VALID_STOP_REASONS
    assert "blocked" in VALID_STOP_REASONS
    assert "error" in VALID_STOP_REASONS


# ===========================================================================
# ingest_request_node tests
# ===========================================================================


@pytest.mark.asyncio
async def test_ingest_request_increments_step_count():
    nodes = _make_nodes()
    state = _base_state(step_count=3)
    result = await nodes.ingest_request_node(state)
    assert result["step_count"] == 4


@pytest.mark.asyncio
async def test_ingest_request_resets_approval_attempted():
    nodes = _make_nodes()
    state = _base_state(approval_attempted=True)
    result = await nodes.ingest_request_node(state)
    assert result["approval_attempted"] is False


@pytest.mark.asyncio
async def test_ingest_request_clears_proposed_calls():
    nodes = _make_nodes()
    state = _base_state(proposed_tool_calls=[{"id": "c1", "name": "old_tool"}])
    result = await nodes.ingest_request_node(state)
    assert result["proposed_tool_calls"] == []


@pytest.mark.asyncio
async def test_ingest_request_logs_operator_request_event():
    audit = FakeAuditLogPort()
    nodes = _make_nodes(audit=audit)
    await nodes.ingest_request_node(_base_state())
    assert audit.has_event("operator_request")


# ===========================================================================
# classify_goal_node tests
# ===========================================================================


@pytest.mark.asyncio
async def test_classify_goal_non_blocked():
    classification = json.dumps({
        "normalized_goal": "list all accounts",
        "blocked": False,
        "block_reason": None,
        "category": "account_info",
    })
    nodes = _make_nodes(llm=FakeLLMGateway(responses=[classification]))
    state = _base_state(operator_request="show me my accounts")

    result = await nodes.classify_goal_node(state)

    assert result["normalized_goal"] == "list all accounts"
    assert result.get("stop_reason") is None
    assert result.get("final_response") is None


@pytest.mark.asyncio
async def test_classify_goal_blocked_sets_stop_reason():
    classification = json.dumps({
        "normalized_goal": "spam users",
        "blocked": True,
        "block_reason": "mass spam action",
        "category": "spam",
    })
    nodes = _make_nodes(llm=FakeLLMGateway(responses=[classification]))
    state = _base_state(operator_request="spam everyone")

    result = await nodes.classify_goal_node(state)

    assert result["stop_reason"] == "blocked"
    assert result["final_response"]
    assert "mass spam action" in result["final_response"]


@pytest.mark.asyncio
async def test_classify_goal_logs_planner_decision():
    classification = json.dumps({
        "normalized_goal": "list accounts",
        "blocked": False,
        "block_reason": None,
    })
    audit = FakeAuditLogPort()
    nodes = _make_nodes(llm=FakeLLMGateway(responses=[classification]), audit=audit)
    await nodes.classify_goal_node(_base_state())
    assert audit.has_event("planner_decision")


@pytest.mark.asyncio
async def test_classify_goal_json_parse_error_fallback():
    # LLM returns non-JSON → fallback should not crash
    nodes = _make_nodes(llm=FakeLLMGateway(responses=["not json at all"]))
    state = _base_state(operator_request="show me accounts")
    result = await nodes.classify_goal_node(state)
    # fallback: normalized_goal = operator_request, not blocked
    assert result.get("stop_reason") is None


# ===========================================================================
# plan_actions_node tests
# ===========================================================================


@pytest.mark.asyncio
async def test_plan_actions_returns_proposed_calls():
    plan_resp = json.dumps({
        "execution_plan": [{"step": 1, "tool": "list_accounts", "reason": "show accounts", "risk_level": "low"}],
        "proposed_tool_calls": [{"id": "c1", "name": "list_accounts", "arguments": {}}],
    })
    executor = FakeToolExecutor(
        results={"list_accounts": {"accounts": []}},
        schemas=[{"function": {"name": "list_accounts", "description": "lists accounts"}}],
    )
    nodes = _make_nodes(
        llm=FakeLLMGateway(responses=[plan_resp]),
        executor=executor,
    )
    state = _base_state(normalized_goal="list all accounts")

    result = await nodes.plan_actions_node(state)

    assert len(result["proposed_tool_calls"]) == 1
    assert result["proposed_tool_calls"][0]["name"] == "list_accounts"
    assert len(result["execution_plan"]) == 1


@pytest.mark.asyncio
async def test_plan_actions_strips_unknown_tool_names():
    plan_resp = json.dumps({
        "execution_plan": [],
        "proposed_tool_calls": [
            {"id": "c1", "name": "list_accounts", "arguments": {}},
            {"id": "c2", "name": "nonexistent_tool", "arguments": {}},
        ],
    })
    executor = FakeToolExecutor(
        results={"list_accounts": {"accounts": []}},
        schemas=[{"function": {"name": "list_accounts", "description": "lists accounts"}}],
    )
    nodes = _make_nodes(llm=FakeLLMGateway(responses=[plan_resp]), executor=executor)
    result = await nodes.plan_actions_node(_base_state())

    names = [c["name"] for c in result["proposed_tool_calls"]]
    assert "nonexistent_tool" not in names
    assert "list_accounts" in names


@pytest.mark.asyncio
async def test_plan_actions_empty_plan_on_json_error():
    nodes = _make_nodes(llm=FakeLLMGateway(responses=["bad json"]))
    result = await nodes.plan_actions_node(_base_state())
    assert result["proposed_tool_calls"] == []
    assert result["execution_plan"] == []


class _PlannerContextExecutor(FakeToolExecutor):
    async def get_planner_context(self) -> dict:
        return {
            "managed_accounts": [
                {"username": "@operator", "status": "active", "proxy": "configured"},
                {"username": "@backup", "status": "inactive", "proxy": "none"},
            ],
            "managed_account_count": 2,
            "active_account_count": 1,
        }


@pytest.mark.asyncio
async def test_plan_actions_includes_runtime_context_and_parameter_guidance():
    llm = FakeLLMGateway(responses=[json.dumps({"execution_plan": [], "proposed_tool_calls": []})])
    executor = _PlannerContextExecutor(
        schemas=[{
            "function": {
                "name": "follow_user",
                "description": "Follow an Instagram user. [write-sensitive: requires operator approval]",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "username": {"type": "string", "description": "Authenticated account username"},
                        "target_username": {"type": "string", "description": "Target username"},
                    },
                    "required": ["username", "target_username"],
                },
            },
        }],
    )
    nodes = _make_nodes(llm=llm, executor=executor)

    await nodes.plan_actions_node(_base_state(normalized_goal="follow @alice using @operator"))

    planner_payload = json.loads(llm.call_log[-1]["messages"][-1]["content"])
    assert planner_payload["managed_accounts"][0]["username"] == "@operator"
    assert planner_payload["managed_account_count"] == 2
    assert planner_payload["available_tools"][0]["policy"] == "write_sensitive"
    assert "acting managed account" in planner_payload["available_tools"][0]["parameter_notes"]["username"].lower()
    assert "external instagram target" in planner_payload["available_tools"][0]["parameter_notes"]["target_username"].lower()


# ===========================================================================
# review_tool_policy_node tests
# ===========================================================================


@pytest.mark.asyncio
async def test_review_tool_policy_read_only_flags():
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[{"id": "c1", "name": "list_accounts", "arguments": {}}]
    )
    result = await nodes.review_tool_policy_node(state)

    assert result["tool_policy_flags"]["c1"] == "read_only"
    assert result["risk_assessment"]["level"] == "low"


@pytest.mark.asyncio
async def test_review_tool_policy_write_sensitive_flags():
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[{"id": "c1", "name": "follow_user", "arguments": {}}]
    )
    result = await nodes.review_tool_policy_node(state)

    assert result["tool_policy_flags"]["c1"] == "write_sensitive"
    assert result["risk_assessment"]["level"] == "medium"


@pytest.mark.asyncio
async def test_review_tool_policy_strips_blocked():
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[
            {"id": "c1", "name": "list_accounts"},
            {"id": "c2", "name": "delete_account"},   # BLOCKED
        ]
    )
    result = await nodes.review_tool_policy_node(state)

    # blocked tool stripped from proposed
    remaining_names = [c["name"] for c in result["proposed_tool_calls"]]
    assert "delete_account" not in remaining_names
    assert "list_accounts" in remaining_names


@pytest.mark.asyncio
async def test_review_tool_policy_all_blocked_empty_executable():
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[{"id": "c1", "name": "delete_account"}]
    )
    result = await nodes.review_tool_policy_node(state)
    assert result["proposed_tool_calls"] == []
    assert result["risk_assessment"]["level"] == "high"


@pytest.mark.asyncio
async def test_review_tool_policy_logs_policy_gate():
    audit = FakeAuditLogPort()
    nodes = _make_nodes(audit=audit)
    state = _base_state(
        proposed_tool_calls=[{"id": "c1", "name": "list_accounts"}]
    )
    await nodes.review_tool_policy_node(state)
    assert audit.has_event("policy_gate")


@pytest.mark.asyncio
async def test_review_tool_policy_prepopulates_approved_calls():
    nodes = _make_nodes()
    state = _base_state(
        proposed_tool_calls=[{"id": "c1", "name": "list_accounts"}]
    )
    result = await nodes.review_tool_policy_node(state)
    # approved_tool_calls pre-populated with executable calls
    assert len(result["approved_tool_calls"]) == 1
    assert result["approved_tool_calls"][0]["name"] == "list_accounts"


# ===========================================================================
# execute_tools_node tests
# ===========================================================================


@pytest.mark.asyncio
async def test_execute_tools_calls_executor():
    executor = FakeToolExecutor(results={"list_accounts": {"accounts": [{"id": "a1"}]}})
    nodes = _make_nodes(executor=executor)
    state = _base_state(
        approved_tool_calls=[{"id": "c1", "name": "list_accounts", "arguments": {}}]
    )
    result = await nodes.execute_tools_node(state)

    assert "c1" in result["tool_results"]
    assert result["tool_results"]["c1"]["accounts"] == [{"id": "a1"}]
    assert executor.was_called_with("list_accounts")


@pytest.mark.asyncio
async def test_execute_tools_captures_handler_exceptions():
    executor = FakeToolExecutor(results={})  # empty → will raise ValueError
    audit = FakeAuditLogPort()
    nodes = _make_nodes(executor=executor, audit=audit)
    state = _base_state(
        approved_tool_calls=[{"id": "c1", "name": "list_accounts", "arguments": {}}]
    )
    result = await nodes.execute_tools_node(state)

    assert "c1" in result["tool_results"]
    assert "error" in result["tool_results"]["c1"]
    assert audit.has_event("execution_failure")
    failure = audit.get_events("execution_failure")[0]["data"]
    assert failure["call_id"] == "c1"
    assert failure["tool_name"] == "list_accounts"
    assert failure["status"] == "failure"
    assert "not in results map" in failure["error"]
    assert audit.has_event("tool_execution") is False


@pytest.mark.asyncio
async def test_execute_tools_logs_tool_execution():
    executor = FakeToolExecutor(results={"list_accounts": {"accounts": []}})
    audit = FakeAuditLogPort()
    nodes = _make_nodes(executor=executor, audit=audit)
    state = _base_state(
        approved_tool_calls=[{"id": "c1", "name": "list_accounts", "arguments": {}}]
    )
    await nodes.execute_tools_node(state)
    assert audit.has_event("tool_execution")
    event = audit.get_events("tool_execution")[0]["data"]
    assert event["call_id"] == "c1"
    assert event["tool_name"] == "list_accounts"
    assert event["status"] == "success"
    assert event["error"] is None


@pytest.mark.asyncio
async def test_execute_tools_treats_error_payload_as_failure():
    executor = FakeToolExecutor(results={"list_accounts": {"error": "upstream timeout"}})
    audit = FakeAuditLogPort()
    nodes = _make_nodes(executor=executor, audit=audit)
    state = _base_state(
        approved_tool_calls=[{"id": "c1", "name": "list_accounts", "arguments": {}}]
    )

    result = await nodes.execute_tools_node(state)

    assert result["tool_results"]["c1"]["error"] == "upstream timeout"
    assert audit.has_event("tool_execution") is False
    assert audit.has_event("execution_failure")
    failure = audit.get_events("execution_failure")[0]["data"]
    assert failure["call_id"] == "c1"
    assert failure["tool_name"] == "list_accounts"
    assert failure["status"] == "failure"
    assert failure["error"] == "upstream timeout"
    assert failure["failure_kind"] == "error_return_payload"


@pytest.mark.asyncio
async def test_execute_tools_treats_unknown_tool_payload_as_failure():
    registry = ToolRegistry()
    executor = RegistryBackedToolExecutor(registry)
    audit = FakeAuditLogPort()
    nodes = _make_nodes(executor=executor, audit=audit)
    state = _base_state(
        approved_tool_calls=[{"id": "c1", "name": "totally_missing_tool", "arguments": {}}]
    )

    result = await nodes.execute_tools_node(state)

    assert "Unknown tool" in result["tool_results"]["c1"]["error"]
    assert audit.has_event("tool_execution") is False
    assert audit.has_event("execution_failure")
    failure = audit.get_events("execution_failure")[0]["data"]
    assert failure["call_id"] == "c1"
    assert failure["tool_name"] == "totally_missing_tool"
    assert failure["status"] == "failure"
    assert "Unknown tool" in failure["error"]
    assert failure["failure_kind"] == "error_return_payload"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name",
    [
        "search_hashtags",
        "get_story",
        "delete_story",
        "mark_stories_seen",
        "change_highlight_title",
        "approve_pending_direct_thread",
        "mark_direct_thread_seen",
    ],
)
async def test_execute_tools_audits_new_exposed_tool_names(tool_name):
    executor = FakeToolExecutor(results={tool_name: {"ok": True}})
    audit = FakeAuditLogPort()
    nodes = _make_nodes(executor=executor, audit=audit)
    state = _base_state(
        approved_tool_calls=[{"id": "c1", "name": tool_name, "arguments": {}}]
    )

    await nodes.execute_tools_node(state)

    events = audit.get_events("tool_execution")
    assert len(events) == 1
    assert events[0]["data"]["tool_name"] == tool_name


@pytest.mark.asyncio
async def test_execute_tools_with_json_string_args():
    executor = FakeToolExecutor(results={"get_posts": {"posts": []}})
    nodes = _make_nodes(executor=executor)
    state = _base_state(
        approved_tool_calls=[{
            "id": "c1",
            "name": "get_posts",
            "arguments": json.dumps({"limit": 5}),  # string args
        }]
    )
    result = await nodes.execute_tools_node(state)
    assert "c1" in result["tool_results"]
    _, args = executor.calls[0]
    assert args == {"limit": 5}


@pytest.mark.asyncio
async def test_execute_tools_logs_failure_for_malformed_json_args():
    executor = FakeToolExecutor(results={"get_posts": {"posts": []}})
    audit = FakeAuditLogPort()
    nodes = _make_nodes(executor=executor, audit=audit)
    state = _base_state(
        approved_tool_calls=[{
            "id": "c1",
            "name": "get_posts",
            "arguments": "{not valid json",
        }]
    )

    result = await nodes.execute_tools_node(state)

    assert "malformed_arguments" in result["tool_results"]["c1"]["error"]
    assert executor.calls == []
    assert audit.has_event("tool_execution") is False
    assert audit.has_event("execution_failure")
    failure = audit.get_events("execution_failure")[0]["data"]
    assert failure["call_id"] == "c1"
    assert failure["tool_name"] == "get_posts"
    assert failure["status"] == "failure"
    assert failure["error"] == "malformed_arguments"
    assert failure["failure_kind"] == "malformed_string_arguments"


# ===========================================================================
# review_results_node tests
# ===========================================================================


@pytest.mark.asyncio
async def test_review_results_non_json_reviewer_output_does_not_crash_audit():
    """Reviewer LLM returning non-JSON (e.g. Ollama gpt-oss:20b free-form text)
    must not poison the audit stream — the parse_error field is documented and
    the run proceeds with a synthetic pass-through finding."""
    audit = FakeAuditLogPort()  # strict mode: validates payload
    nodes = _make_nodes(
        llm=FakeLLMGateway(responses=["I think everything looks fine, no issues."]),
        audit=audit,
    )
    state = _base_state(
        normalized_goal="list accounts",
        tool_results={"c1": {"accounts": []}},
        execution_plan=[{"step": 1, "tool": "list_accounts"}],
    )

    result = await nodes.review_results_node(state)

    # Reviewer failure falls through to a pass-through finding.
    assert result["review_findings"]["matched_intent"] is True
    assert result["review_findings"]["recommendation"] == "proceed_to_summary"

    # Audit event was accepted by the strict validator (no ValueError raised above).
    events = audit.get_events("review_finding")
    assert len(events) == 1
    assert events[0]["data"]["parse_error"] == "reviewer_returned_non_json"


@pytest.mark.asyncio
async def test_review_results_valid_json_reviewer_output_no_parse_error():
    """When the reviewer returns valid JSON, parse_error is None but still
    allowed by the schema."""
    audit = FakeAuditLogPort()
    reviewer_resp = json.dumps({
        "matched_intent": True,
        "warnings": [],
        "recommendation": "proceed_to_summary",
    })
    nodes = _make_nodes(llm=FakeLLMGateway(responses=[reviewer_resp]), audit=audit)
    state = _base_state(
        normalized_goal="list accounts",
        tool_results={"c1": {"accounts": []}},
    )

    await nodes.review_results_node(state)

    events = audit.get_events("review_finding")
    assert len(events) == 1
    assert events[0]["data"]["parse_error"] is None


# ===========================================================================
# summarize_result_node provider routing tests
# ===========================================================================


@pytest.mark.asyncio
async def test_summarize_routes_to_state_provider_ollama():
    """A thread configured with Ollama must route its summarize LLM call to
    Ollama, not a silent OpenAI default. Regression guard for the pre-
    2026-04-17 bug where summarize ignored the thread's selected provider."""
    llm = FakeLLMGateway(responses=["Summary text"])
    nodes = _make_nodes(llm=llm)
    state = _base_state(
        provider="ollama",
        model="llama3.2:3b",
        api_key=None,
        provider_base_url="http://localhost:11434/v1",
        tool_results={"c1": {"accounts": []}},
        execution_plan=[{"step": 1, "tool": "list_accounts"}],
        review_findings={"matched_intent": True, "warnings": [], "recommendation": "proceed_to_summary"},
    )

    await nodes.summarize_result_node(state)

    assert llm.call_count == 1
    kwargs = llm.call_log[-1]["kwargs"]
    assert kwargs["provider"] == "ollama"
    assert kwargs["model"] == "llama3.2:3b"
    assert kwargs["provider_base_url"] == "http://localhost:11434/v1"


@pytest.mark.asyncio
async def test_summarize_routes_to_state_provider_openai():
    """A thread configured with OpenAI must route its summarize call to OpenAI."""
    llm = FakeLLMGateway(responses=["Summary text"])
    nodes = _make_nodes(llm=llm)
    state = _base_state(
        provider="openai",
        model="gpt-4o-mini",
        api_key="sk-test",
        tool_results={"c1": {"accounts": []}},
    )

    await nodes.summarize_result_node(state)

    kwargs = llm.call_log[-1]["kwargs"]
    assert kwargs["provider"] == "openai"
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["api_key"] == "sk-test"


@pytest.mark.asyncio
async def test_summarize_does_not_fall_back_when_state_provider_is_set():
    """Even when api_key/base_url are unset, a set state.provider must be
    honored — summarize must not silently default to 'openai'."""
    llm = FakeLLMGateway(responses=["ok"])
    nodes = _make_nodes(llm=llm)
    state = _base_state(provider="gemini", tool_results={"c1": {}})

    await nodes.summarize_result_node(state)

    assert llm.call_log[-1]["kwargs"]["provider"] == "gemini"


@pytest.mark.asyncio
async def test_summarize_skips_llm_call_when_final_response_already_set():
    """If an earlier gate (block/reject/responded) set final_response, summarize
    must short-circuit and NOT call the LLM at all — so provider routing is
    moot on those paths."""
    llm = FakeLLMGateway(responses=["should not be called"])
    nodes = _make_nodes(llm=llm)
    state = _base_state(
        provider="ollama",
        final_response="Action cancelled by operator.",
        stop_reason="rejected",
    )

    result = await nodes.summarize_result_node(state)

    assert llm.call_count == 0
    assert result["final_response"] == "Action cancelled by operator."


@pytest.mark.asyncio
async def test_summarize_redacts_raw_exception_text_from_final_response():
    """Regression guard: when the summary LLM call raises (e.g. missing
    provider credentials), the operator-facing ``final_response`` must NOT
    contain raw provider internals like env-var names, API key hints, or
    stack traces. The leak channel at nodes_approval_execution.py:354 used
    to embed ``str(exc)`` directly into the chat stream — CLAUDE.md's error
    translation rule forbids that."""

    class _RaisingLLMGateway(FakeLLMGateway):
        def __init__(self, exc: Exception):
            super().__init__()
            self._exc = exc

        async def request_completion(self, messages, **kwargs):
            raise self._exc

    leaky_message = (
        "OpenAIError: The api_key client option must be set either by "
        "passing apiKey or by setting the OPENAI_API_KEY environment variable"
    )
    llm = _RaisingLLMGateway(RuntimeError(leaky_message))
    nodes = _make_nodes(llm=llm)
    state = _base_state(
        provider="openai",
        tool_results={"c1": {"accounts": []}},
        execution_plan=[{"step": 1, "tool": "list_accounts"}],
    )

    result = await nodes.summarize_result_node(state)

    final = result["final_response"]
    assert isinstance(final, str) and final.strip(), "must return a generic message"
    for forbidden in ("OPENAI_API_KEY", "apiKey", "api_key", "OpenAIError", "Traceback", leaky_message):
        assert forbidden not in final, (
            f"final_response leaked sensitive substring {forbidden!r}: {final!r}"
        )


# ===========================================================================
# finish_node tests
# ===========================================================================


@pytest.mark.asyncio
async def test_finish_node_done_when_no_stop_reason():
    nodes = _make_nodes()
    state = _base_state(stop_reason=None)
    result = await nodes.finish_node(state)
    assert result["stop_reason"] == "done"


@pytest.mark.asyncio
async def test_finish_node_preserves_explicit_stop_reason():
    nodes = _make_nodes()
    state = _base_state(stop_reason="blocked")
    result = await nodes.finish_node(state)
    assert result["stop_reason"] == "blocked"


@pytest.mark.asyncio
async def test_finish_node_logs_stop_reason():
    audit = FakeAuditLogPort()
    nodes = _make_nodes(audit=audit)
    await nodes.finish_node(_base_state(stop_reason="done"))
    assert audit.has_event("stop_reason")


@pytest.mark.asyncio
async def test_finish_node_converts_responded_to_done():
    nodes = _make_nodes()
    state = _base_state(stop_reason="responded")
    result = await nodes.finish_node(state)
    assert result["stop_reason"] == "done"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
