"""Phase D boundaries for ai_copilot normalization lock."""

from __future__ import annotations

import asyncio
import re
import sys
import types
from pathlib import Path

# Minimal shim so importing smart_engagement nodes does not require langgraph package.
if "langgraph.graph" not in sys.modules:
    langgraph_module = types.ModuleType("langgraph")
    graph_module = types.ModuleType("langgraph.graph")
    graph_module.add_messages = lambda x: x
    types_module = types.ModuleType("langgraph.types")
    types_module.interrupt = lambda payload: {"decision": "approved", "notes": "ok"}
    langgraph_module.graph = graph_module
    langgraph_module.types = types_module
    sys.modules["langgraph"] = langgraph_module
    sys.modules["langgraph.graph"] = graph_module
    sys.modules["langgraph.types"] = types_module

from ai_copilot.application.smart_engagement.nodes import SmartEngagementNodes


REPO_ROOT = Path("/home/xtrzy/Workspace/insta")
AI_COPILOT_ROOT = REPO_ROOT / "backend" / "ai_copilot"


def _iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


class _NoOpPort:
    async def __call__(self, *args, **kwargs):
        return None


class _FakeAccountContext:
    async def get_account_context(self, account_id: str):
        return {
            "status": "active",
            "cooldown_until": None,
            "proxy": None,
            "login_state": "logged_in",
            "recent_actions": 0,
        }

    async def validate_account_ready(self, account_id: str) -> bool:
        return True


class _FakeCandidateDiscovery:
    async def discover_candidates(self, account_id: str, goal: str, filters: dict | None = None):
        return []

    async def get_target_metadata(self, target_id: str):
        return {"target_id": target_id}


class _FakeRiskScoring:
    async def assess_risk(self, action, target, account_health):
        return {
            "risk_level": "low",
            "rule_hits": [],
            "reasoning": "ok",
            "requires_approval": False,
        }


class _FakeApproval:
    async def submit_for_approval(self, *args, **kwargs):
        return "apr-1"

    async def get_approval_status(self, approval_id: str):
        return {"approval_id": approval_id, "decision": "approved"}


class _FakeAuditLog:
    async def log_event(self, event):
        return None

    async def get_audit_trail(self, thread_id: str):
        return []


class _LeakyExecutor:
    async def execute_follow(self, target_id: str, account_id: str):
        return {"success": True, "action_id": "f-1", "reason": "ok", "reason_code": "ok", "timestamp": 1.0}

    async def execute_dm(self, target_id: str, account_id: str, message: str):
        # Includes vendor-specific and raw fields that must be dropped by node.
        return {
            "success": True,
            "action_id": "dm-1",
            "reason": "sent",
            "reason_code": "ok",
            "timestamp": 123.0,
            "dm_id": "vendor-dm-id",
            "raw_vendor_payload": {"thread_id": "x"},
        }

    async def execute_comment(self, post_id: str, account_id: str, comment_text: str):
        return {"success": True, "action_id": "c-1", "reason": "ok", "reason_code": "ok", "timestamp": 1.0}

    async def execute_like(self, post_id: str, account_id: str):
        return {"success": True, "action_id": "l-1", "reason": "ok", "reason_code": "ok", "timestamp": 1.0}

    def is_write_action(self, action_type: str) -> bool:
        return action_type in {"follow", "dm", "comment", "like"}


def _build_nodes(executor=None) -> SmartEngagementNodes:
    return SmartEngagementNodes(
        account_context=_FakeAccountContext(),
        candidate_discovery=_FakeCandidateDiscovery(),
        risk_scoring=_FakeRiskScoring(),
        approval=_FakeApproval(),
        executor=executor or _LeakyExecutor(),
        audit_log=_FakeAuditLog(),
    )


def test_ai_copilot_must_not_import_instagram_concrete_adapter_or_vendor_sdk():
    concrete_adapter_pattern = re.compile(
        r"from\s+app\.adapters\.instagram\b|import\s+app\.adapters\.instagram\b"
    )
    vendor_pattern = re.compile(r"(^|\s)(from\s+instagrapi\b|import\s+instagrapi\b)")
    violations: list[str] = []

    for path in _iter_python_files(AI_COPILOT_ROOT):
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            if concrete_adapter_pattern.search(line) or vendor_pattern.search(line):
                violations.append(f"{path}:{line_no}:{line.strip()}")

    assert violations == [], "\n".join(
        [
            "Found forbidden ai_copilot imports (instagram adapter concrete or instagrapi vendor sdk):",
            *violations,
        ]
    )


def test_execute_action_node_normalizes_execution_result_shape():
    nodes = _build_nodes(executor=_LeakyExecutor())
    state = {
        "mode": "execute",
        "account_id": "acc-1",
        "approval_result": {"decision": "approved"},
        "proposed_action": {"action_type": "dm", "target_id": "alice", "content": "hello"},
    }

    update = asyncio.run(nodes.execute_action_node(state))
    result = update["execution_result"]

    assert set(result.keys()) == {"success", "action_id", "reason", "reason_code", "timestamp"}
    assert result["success"] is True
    assert result["action_id"] == "dm-1"
    assert result["reason_code"] == "ok"


def test_execute_action_node_keeps_app_owned_failure_contract_on_executor_error():
    class _BoomExecutor(_LeakyExecutor):
        async def execute_dm(self, target_id: str, account_id: str, message: str):
            raise RuntimeError("vendor exploded")

    nodes = _build_nodes(executor=_BoomExecutor())
    state = {
        "mode": "execute",
        "account_id": "acc-1",
        "approval_result": {"decision": "approved"},
        "proposed_action": {"action_type": "dm", "target_id": "alice", "content": "hello"},
    }

    update = asyncio.run(nodes.execute_action_node(state))
    result = update["execution_result"]

    assert set(result.keys()) == {"success", "action_id", "reason", "reason_code", "timestamp"}
    assert result["success"] is False
    assert result["reason_code"] == "execution_failed"
