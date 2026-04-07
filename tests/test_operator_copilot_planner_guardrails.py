from __future__ import annotations

import asyncio
import json
import sys
from types import SimpleNamespace
import types

if "langgraph" not in sys.modules:
    langgraph = types.ModuleType("langgraph")
    graph_module = types.ModuleType("langgraph.graph")
    types_module = types.ModuleType("langgraph.types")

    class _StateGraph:
        def __init__(self, *_args, **_kwargs):
            pass

    graph_module.END = "END"
    graph_module.START = "START"
    graph_module.StateGraph = _StateGraph
    graph_module.add_messages = lambda existing, new: (existing or []) + (new or [])
    types_module.interrupt = lambda payload: payload

    sys.modules["langgraph"] = langgraph
    sys.modules["langgraph.graph"] = graph_module
    sys.modules["langgraph.types"] = types_module

from ai_copilot.adapters.fake_ports_operator_copilot import (
    FakeApprovalPort,
    FakeAuditLogPort,
    FakeLLMGateway,
    FakeToolExecutor,
)
from ai_copilot.adapters.tool_registry_bridge import ToolRegistryBridgeAdapter
from ai_copilot.application.graphs.operator_copilot import OperatorCopilotNodes
from ai_copilot.application.operator_copilot_policy import ToolPolicy, ToolPolicyRegistry
from ai_copilot.application.state import make_initial_state
from app.adapters.ai.tool_registry import create_tool_registry


def _tool_schema(
    name: str,
    description: str,
    properties: dict | None = None,
    required: list[str] | None = None,
) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


def test_plan_actions_filters_placeholder_and_unknown_account_calls():
    llm = FakeLLMGateway(responses=[{
        "content": json.dumps({
            "execution_plan": [
                {"step": "List accounts", "tool": "list_accounts", "reason": "Need accounts", "risk_level": "low"},
                {"step": "Get account info", "tool": "get_account_info", "reason": "Need details", "risk_level": "low"},
                {"step": "List media insights", "tool": "list_media_insights", "reason": "Need engagement", "risk_level": "medium"},
            ],
            "proposed_tool_calls": [
                {"id": "c1", "name": "list_accounts", "arguments": {}},
                {"id": "c2", "name": "get_account_info", "arguments": {"account_id": "account_id_from_list"}},
                {"id": "c3", "name": "list_media_insights", "arguments": {"account_id": "account_id_from_list", "days": 7}},
            ],
        }),
        "finish_reason": "stop",
        "tool_calls": [],
    }])
    tool_executor = FakeToolExecutor(
        schemas=[
            _tool_schema("list_accounts", "List all accounts"),
            _tool_schema(
                "get_account_info",
                "Get detailed information for one account",
                properties={"username": {"type": "string", "description": "Instagram username"}},
                required=["username"],
            ),
            _tool_schema(
                "list_media_insights",
                "List media insights for one account",
                properties={
                    "username": {"type": "string", "description": "Instagram username"},
                    "days": {"type": "integer", "description": "Number of days to inspect"},
                },
                required=["username"],
            ),
        ],
    )
    audit_log = FakeAuditLogPort()
    nodes = OperatorCopilotNodes(
        llm_gateway=llm,
        tool_executor=tool_executor,
        approval_port=FakeApprovalPort(),
        audit_log=audit_log,
    )

    state = make_initial_state("Show engagement activity for the last 7 days.")
    state["normalized_goal"] = "Show engagement activity for the last 7 days."

    result = asyncio.run(nodes.plan_actions_node(state))

    assert result["proposed_tool_calls"] == [
        {"id": "c1", "name": "list_accounts", "arguments": {}},
    ]

    planner_event = audit_log.get_events("planner_decision")[-1]
    assert planner_event["data"]["dropped_tool_calls"] == [
        {
            "id": "c2",
            "name": "get_account_info",
            "reason": "missing_required_arguments",
            "missing": ["username"],
        },
        {
            "id": "c3",
            "name": "list_media_insights",
            "reason": "missing_required_arguments",
            "missing": ["username"],
        },
    ]


def test_plan_actions_passes_parameter_schema_to_planner_prompt():
    llm = FakeLLMGateway(responses=[
        json.dumps({"execution_plan": [], "proposed_tool_calls": []}),
    ])
    tool_executor = FakeToolExecutor(
        schemas=[
            _tool_schema(
                "get_account_info",
                "Get detailed information for one account",
                properties={"username": {"type": "string", "description": "Instagram username"}},
                required=["username"],
            ),
        ],
    )
    nodes = OperatorCopilotNodes(
        llm_gateway=llm,
        tool_executor=tool_executor,
        approval_port=FakeApprovalPort(),
        audit_log=FakeAuditLogPort(),
    )

    state = make_initial_state("Show profile details for maryannbunn762")
    state["normalized_goal"] = "Show profile details for maryannbunn762"

    asyncio.run(nodes.plan_actions_node(state))

    planner_payload = json.loads(llm.call_log[-1]["messages"][-1]["content"])
    assert planner_payload["available_tools"][0] == {
        "name": "get_account_info",
        "description": "Get detailed information for one account",
        "policy": None,
        "required": ["username"],
        "parameters": {
            "username": {
                "type": "string",
                "description": "Instagram username",
                "enum": None,
                "items_type": None,
            },
        },
        "parameter_notes": {
            "username": "Acting managed account username. Must come from managed_accounts.",
        },
        "planning_hints": [],
    }


class _StubAccountRepo:
    def __init__(self) -> None:
        self._accounts: dict[str, dict] = {}

    def get(self, account_id: str) -> dict | None:
        return self._accounts.get(account_id)


class _StubAccountUseCases:
    def __init__(self) -> None:
        self.account_repo = _StubAccountRepo()

    def get_accounts_summary(self) -> dict:
        return {"accounts": [], "total": 0, "active": 0}

    def find_by_username(self, username: str) -> str | None:
        return None

    def get_account_info(self, account_id: str):
        raise AssertionError("get_account_info should not run when account resolution fails")


def test_get_account_info_requires_username_instead_of_returning_at_placeholder():
    registry = create_tool_registry(
        account_usecases=_StubAccountUseCases(),
        postjob_usecases=object(),
    )

    result = asyncio.run(registry.execute("get_account_info", {}))

    assert result == {"error": "username is required"}


def test_list_media_insights_reports_invalid_account_id_clearly():
    registry = create_tool_registry(
        account_usecases=_StubAccountUseCases(),
        postjob_usecases=object(),
        insight_use_cases=SimpleNamespace(),
    )

    result = asyncio.run(registry.execute("list_media_insights", {"account_id": "account_id_from_list"}))

    assert result == {"error": "Account id account_id_from_list not found"}


def test_policy_registry_covers_actual_registered_tool_names():
    reg = ToolPolicyRegistry()

    assert reg.classify("list_followers").policy == ToolPolicy.READ_ONLY
    assert reg.classify("list_following").policy == ToolPolicy.READ_ONLY
    assert reg.classify("list_proxy_pool").policy == ToolPolicy.READ_ONLY
    assert reg.classify("pick_proxy").policy == ToolPolicy.READ_ONLY
    assert reg.classify("get_direct_thread").policy == ToolPolicy.READ_ONLY
    assert reg.classify("list_direct_messages").policy == ToolPolicy.READ_ONLY

    assert reg.classify("import_proxies").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("recheck_proxy_pool").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("delete_proxy").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("send_message_to_thread").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("find_or_create_direct_thread").policy == ToolPolicy.WRITE_SENSITIVE
    assert reg.classify("delete_direct_message").policy == ToolPolicy.WRITE_SENSITIVE


def test_bridge_planner_context_compacts_managed_accounts():
    bridge = ToolRegistryBridgeAdapter(
        tool_registry=FakeToolExecutor(
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
            schemas=[_tool_schema("list_accounts", "List all accounts")],
        )
    )

    context = asyncio.run(bridge.get_planner_context())

    assert context == {
        "managed_accounts": [
            {"username": "@operator", "status": "active", "proxy": "configured"},
            {"username": "@backup", "status": "inactive", "proxy": "none"},
        ],
        "managed_account_count": 2,
        "active_account_count": 1,
    }
