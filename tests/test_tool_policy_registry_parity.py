"""Parity tests for operator tool-policy classification vs runtime registry."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from ai_copilot.application.operator_copilot_policy import ToolPolicyRegistry
from app.adapters.ai.tool_registry.builder import list_registered_tool_names_for_policy_audit


def test_policy_registry_parity_against_registered_tools():
    registered_tool_names = list_registered_tool_names_for_policy_audit()
    report = ToolPolicyRegistry.build_parity_report(registered_tool_names)

    assert report["registered_only"] == [], (
        "Registered tools missing policy classifications: "
        f"{report['registered_only']}. Full report: {report}"
    )
    assert report["policy_only_unexpected"] == [], (
        "Policy entries missing from registry and not explicitly excepted: "
        f"{report['policy_only_unexpected']}. Full report: {report}"
    )
    assert report["stale_intentional_exceptions"] == [], (
        "Intentional exception list contains stale entries: "
        f"{report['stale_intentional_exceptions']}. Full report: {report}"
    )


def test_policy_registry_parity_report_is_machine_readable():
    report = ToolPolicyRegistry.build_parity_report(
        list_registered_tool_names_for_policy_audit()
    )

    assert "registered_only" in report
    assert "policy_only" in report
    assert "intentional_exceptions" in report
    assert isinstance(report["registered_only"], list)
    assert isinstance(report["policy_only"], list)
    assert isinstance(report["intentional_exceptions"], list)

    blocked_legacy_names = {"delete_account", "mass_unfollow", "bulk_dm", "scrape_users"}
    assert blocked_legacy_names <= set(report["intentional_exceptions"])
