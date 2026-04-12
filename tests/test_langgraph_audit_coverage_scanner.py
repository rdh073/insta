"""Contract tests for the LangGraph coverage scanner."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from ai_copilot.audit.coverage_scanner import DEFAULT_EXCEPTION_PATH, run_scan


def test_langgraph_audit_scanner_ci_contract_has_no_unexplained_gaps():
    report = run_scan()
    assert report["is_ci_pass"], (
        "LangGraph coverage scanner found unexplained gaps.\n"
        + json.dumps(report, indent=2, sort_keys=True)
    )


def test_langgraph_audit_scanner_flags_potential_incompleteness_for_missing_probe():
    report = run_scan(dynamic_probe_modules=("module_does_not_exist_for_scan_probe",))
    assert report["potentially_incomplete"] is True
    assert any(
        "dynamic_probe_unavailable:module_does_not_exist_for_scan_probe" in reason
        for reason in report["incompleteness_reasons"]
    )


def test_langgraph_audit_scanner_requires_non_empty_exception_justification(tmp_path: Path):
    manifest = json.loads(DEFAULT_EXCEPTION_PATH.read_text(encoding="utf-8"))
    manifest["exceptions"].append(
        {
            "gap_key": "capability_gap:story_use_cases.publish_story",
            "justification": "   ",
        }
    )

    bad_manifest_path = tmp_path / "coverage_exceptions.invalid.json"
    bad_manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    report = run_scan(exceptions_path=bad_manifest_path)
    invalid_entries = report["exceptions"]["invalid_entries"]
    assert invalid_entries
    assert any("justification_missing_or_blank" in item for item in invalid_entries)
    assert report["is_ci_pass"] is False
