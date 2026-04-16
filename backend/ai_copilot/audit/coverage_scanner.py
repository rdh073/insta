"""LangGraph tool/audit completeness scanner.

This scanner compares four surfaces:
1) Use-case capabilities (public methods on selected use-case classes)
2) Registered tool exposure (tool_registry handlers)
3) Tool policy coverage (ToolPolicyRegistry parity)
4) Audit coverage expectations (operator + smart-engagement audit events)

Output is deterministic and machine-readable so CI and local runs can share
the same contract.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class UseCaseSurface:
    """Static definition of one use-case capability surface."""

    alias: str
    module_path: str
    class_name: str


_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[3]

DEFAULT_EXCEPTION_PATH = (
    _REPO_ROOT / "backend" / "ai_copilot" / "audit" / "coverage_exceptions.json"
)

_USE_CASE_SURFACES: tuple[UseCaseSurface, ...] = (
    UseCaseSurface(
        alias="profile_usecases",
        module_path="backend/app/application/use_cases/account_profile.py",
        class_name="AccountProfileUseCases",
    ),
    UseCaseSurface(
        alias="auth_usecases",
        module_path="backend/app/application/use_cases/account_auth.py",
        class_name="AccountAuthUseCases",
    ),
    UseCaseSurface(
        alias="proxy_usecases",
        module_path="backend/app/application/use_cases/account_proxy.py",
        class_name="AccountProxyUseCases",
    ),
    UseCaseSurface(
        alias="edit_usecases",
        module_path="backend/app/application/use_cases/account/edit.py",
        class_name="AccountEditUseCases",
    ),
    UseCaseSurface(
        alias="postjob_usecases",
        module_path="backend/app/application/use_cases/post_job.py",
        class_name="PostJobUseCases",
    ),
    UseCaseSurface(
        alias="hashtag_use_cases",
        module_path="backend/app/application/use_cases/hashtag.py",
        class_name="HashtagUseCases",
    ),
    UseCaseSurface(
        alias="collection_use_cases",
        module_path="backend/app/application/use_cases/collection.py",
        class_name="CollectionUseCases",
    ),
    UseCaseSurface(
        alias="media_use_cases",
        module_path="backend/app/application/use_cases/media.py",
        class_name="MediaUseCases",
    ),
    UseCaseSurface(
        alias="story_use_cases",
        module_path="backend/app/application/use_cases/story.py",
        class_name="StoryUseCases",
    ),
    UseCaseSurface(
        alias="highlight_use_cases",
        module_path="backend/app/application/use_cases/highlight.py",
        class_name="HighlightUseCases",
    ),
    UseCaseSurface(
        alias="comment_use_cases",
        module_path="backend/app/application/use_cases/comment.py",
        class_name="CommentUseCases",
    ),
    UseCaseSurface(
        alias="direct_use_cases",
        module_path="backend/app/application/use_cases/direct.py",
        class_name="DirectUseCases",
    ),
    UseCaseSurface(
        alias="insight_use_cases",
        module_path="backend/app/application/use_cases/insight.py",
        class_name="InsightUseCases",
    ),
    UseCaseSurface(
        alias="relationship_use_cases",
        module_path="backend/app/application/use_cases/relationships.py",
        class_name="RelationshipUseCases",
    ),
    UseCaseSurface(
        alias="proxy_pool_usecases",
        module_path="backend/app/application/use_cases/proxy_pool.py",
        class_name="ProxyPoolUseCases",
    ),
)

_USE_CASE_SURFACES_BY_ALIAS = {surface.alias: surface for surface in _USE_CASE_SURFACES}

_TOOL_REGISTRY_SOURCES: tuple[Path, ...] = (
    _REPO_ROOT / "backend" / "app" / "adapters" / "ai" / "tool_registry" / "account_tools.py",
    _REPO_ROOT / "backend" / "app" / "adapters" / "ai" / "tool_registry" / "content_read_tools.py",
    _REPO_ROOT / "backend" / "app" / "adapters" / "ai" / "tool_registry" / "engagement_write_tools.py",
    _REPO_ROOT / "backend" / "app" / "adapters" / "ai" / "tool_registry" / "proxy_pool_tools.py",
)

_OPERATOR_AUDIT_SOURCES: tuple[Path, ...] = (
    _REPO_ROOT
    / "backend"
    / "ai_copilot"
    / "application"
    / "graphs"
    / "operator_copilot"
    / "nodes_plan_policy.py",
    _REPO_ROOT
    / "backend"
    / "ai_copilot"
    / "application"
    / "graphs"
    / "operator_copilot"
    / "nodes_approval_execution.py",
)

_SMART_ENGAGEMENT_NODE_SOURCES: tuple[Path, ...] = tuple(
    sorted(
        path
        for path in (
            _REPO_ROOT
            / "backend"
            / "ai_copilot"
            / "application"
            / "smart_engagement"
            / "nodes"
        ).glob("*.py")
        if path.name != "__init__.py"
    )
)

_DEFAULT_DYNAMIC_PROBE_MODULES: tuple[str, ...] = (
    "langgraph.graph",
    "langgraph.store.memory",
    "app.bootstrap.container",
)


def _relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(_REPO_ROOT))
    except Exception:
        return str(path)


def _load_ast(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=_relpath(path))


def _public_methods_for_surface(surface: UseCaseSurface) -> set[str]:
    source_path = _REPO_ROOT / surface.module_path
    tree = _load_ast(source_path)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == surface.class_name:
            return {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not child.name.startswith("_")
            }
    raise ValueError(
        f"Class {surface.class_name!r} not found in {_relpath(source_path)}"
    )


def _is_registry_register_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    return (
        isinstance(fn, ast.Attribute)
        and fn.attr == "register"
        and isinstance(fn.value, ast.Name)
        and fn.value.id == "registry"
    )


def _extract_string_literal(call: ast.Call, arg_index: int) -> tuple[str | None, bool]:
    if len(call.args) <= arg_index:
        return None, False
    arg = call.args[arg_index]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value, True
    return None, False


def _extract_name_arg(call: ast.Call, arg_index: int) -> str | None:
    if len(call.args) <= arg_index:
        return None
    arg = call.args[arg_index]
    if isinstance(arg, ast.Name):
        return arg.id
    return None


def _extract_context_capabilities(node: ast.AST) -> set[str]:
    """Extract context.<alias>.<method>(...) call signatures."""
    capabilities: set[str] = set()
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Attribute):
            continue

        method = call.func.attr
        owner = call.func.value
        if not (
            isinstance(owner, ast.Attribute)
            and isinstance(owner.value, ast.Name)
            and owner.value.id == "context"
        ):
            continue

        alias = owner.attr
        if alias not in _USE_CASE_SURFACES_BY_ALIAS:
            continue
        capabilities.add(f"{alias}.{method}")
    return capabilities


def _collect_tool_registry_index() -> dict[str, Any]:
    """Collect static tool names and capability mappings from tool_registry source."""
    registered_tools: set[str] = set()
    tool_to_capabilities: dict[str, set[str]] = {}
    capability_to_tools: dict[str, set[str]] = {}
    non_literal_tool_name_calls: list[str] = []

    for source_path in _TOOL_REGISTRY_SOURCES:
        tree = _load_ast(source_path)
        register_functions = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("register_")
        ]

        for register_fn in register_functions:
            handler_capabilities: dict[str, set[str]] = {}
            for child in register_fn.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    handler_capabilities[child.name] = _extract_context_capabilities(child)

            for call in ast.walk(register_fn):
                if not _is_registry_register_call(call):
                    continue
                assert isinstance(call, ast.Call)

                tool_name, is_literal = _extract_string_literal(call, 0)
                handler_name = _extract_name_arg(call, 1)
                if tool_name:
                    registered_tools.add(tool_name)
                elif not is_literal:
                    non_literal_tool_name_calls.append(
                        f"{_relpath(source_path)}:{call.lineno}"
                    )

                if not tool_name or not handler_name:
                    continue
                capabilities = handler_capabilities.get(handler_name, set())
                if not capabilities:
                    continue
                tool_to_capabilities.setdefault(tool_name, set()).update(capabilities)
                for capability in capabilities:
                    capability_to_tools.setdefault(capability, set()).add(tool_name)

    return {
        "registered_tools": sorted(registered_tools),
        "tool_to_capabilities": {
            tool: sorted(capabilities)
            for tool, capabilities in sorted(tool_to_capabilities.items())
        },
        "capability_to_tools": {
            capability: sorted(tools)
            for capability, tools in sorted(capability_to_tools.items())
        },
        "non_literal_tool_name_calls": sorted(non_literal_tool_name_calls),
    }


def _collect_operator_emitted_audit_events() -> tuple[set[str], list[str]]:
    events: set[str] = set()
    dynamic_sites: list[str] = []

    for source_path in _OPERATOR_AUDIT_SOURCES:
        tree = _load_ast(source_path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not (
                isinstance(fn, ast.Attribute)
                and fn.attr == "log"
                and isinstance(fn.value, ast.Attribute)
                and fn.value.attr == "audit_log"
                and isinstance(fn.value.value, ast.Name)
                and fn.value.value.id == "self"
            ):
                continue
            event_name, is_literal = _extract_string_literal(node, 0)
            if event_name:
                events.add(event_name)
            elif not is_literal:
                dynamic_sites.append(f"{_relpath(source_path)}:{node.lineno}")
    return events, sorted(dynamic_sites)


def _collect_smart_engagement_emitted_audit_events() -> tuple[set[str], list[str]]:
    events: set[str] = set()
    dynamic_sites: list[str] = []

    for source_path in _SMART_ENGAGEMENT_NODE_SOURCES:
        tree = _load_ast(source_path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Name) and node.func.id == "AuditEvent"):
                continue
            event_kw = next((kw for kw in node.keywords if kw.arg == "event_type"), None)
            if event_kw is None:
                dynamic_sites.append(f"{_relpath(source_path)}:{node.lineno}")
                continue
            if (
                isinstance(event_kw.value, ast.Constant)
                and isinstance(event_kw.value.value, str)
            ):
                events.add(event_kw.value.value)
            else:
                dynamic_sites.append(f"{_relpath(source_path)}:{node.lineno}")
    return events, sorted(dynamic_sites)


def _run_dynamic_probes(modules: Sequence[str]) -> list[dict[str, Any]]:
    probe_results: list[dict[str, Any]] = []
    for module_name in modules:
        try:
            importlib.import_module(module_name)
            probe_results.append(
                {
                    "probe": module_name,
                    "available": True,
                    "error": None,
                }
            )
        except Exception as exc:  # pragma: no cover - environment-dependent
            probe_results.append(
                {
                    "probe": module_name,
                    "available": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return probe_results


def _load_exception_manifest(path: Path) -> dict[str, Any]:
    invalid_entries: list[str] = []
    exception_map: dict[str, str] = {}
    version: int | None = None

    if not path.exists():
        invalid_entries.append(f"manifest_missing:{_relpath(path)}")
        return {
            "path": _relpath(path),
            "version": version,
            "exception_map": exception_map,
            "invalid_entries": invalid_entries,
        }

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        invalid_entries.append(f"invalid_json:{type(exc).__name__}: {exc}")
        return {
            "path": _relpath(path),
            "version": version,
            "exception_map": exception_map,
            "invalid_entries": invalid_entries,
        }

    if not isinstance(data, dict):
        invalid_entries.append("manifest_not_object")
        return {
            "path": _relpath(path),
            "version": version,
            "exception_map": exception_map,
            "invalid_entries": invalid_entries,
        }

    raw_version = data.get("version")
    if isinstance(raw_version, int):
        version = raw_version
    else:
        invalid_entries.append("version_missing_or_not_int")

    raw_exceptions = data.get("exceptions")
    if not isinstance(raw_exceptions, list):
        invalid_entries.append("exceptions_missing_or_not_list")
        return {
            "path": _relpath(path),
            "version": version,
            "exception_map": exception_map,
            "invalid_entries": invalid_entries,
        }

    for idx, entry in enumerate(raw_exceptions):
        prefix = f"exceptions[{idx}]"
        if not isinstance(entry, dict):
            invalid_entries.append(f"{prefix}:not_object")
            continue
        gap_key = entry.get("gap_key")
        justification = entry.get("justification")
        if not isinstance(gap_key, str) or not gap_key.strip():
            invalid_entries.append(f"{prefix}:gap_key_missing_or_blank")
            continue
        if not isinstance(justification, str) or not justification.strip():
            invalid_entries.append(f"{prefix}:justification_missing_or_blank")
            continue
        normalized_key = gap_key.strip()
        if normalized_key in exception_map:
            invalid_entries.append(f"{prefix}:duplicate_gap_key:{normalized_key}")
            continue
        exception_map[normalized_key] = justification.strip()

    return {
        "path": _relpath(path),
        "version": version,
        "exception_map": exception_map,
        "invalid_entries": sorted(invalid_entries),
    }


def _gap_record(gap_key: str, section: str, description: str, *, data: Any = None) -> dict[str, Any]:
    return {
        "gap_key": gap_key,
        "section": section,
        "description": description,
        "data": data,
    }


def run_scan(
    *,
    exceptions_path: Path | None = None,
    dynamic_probe_modules: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Run full coverage scan and return machine-readable report."""
    exception_path = Path(exceptions_path) if exceptions_path else DEFAULT_EXCEPTION_PATH
    probe_modules = tuple(dynamic_probe_modules or _DEFAULT_DYNAMIC_PROBE_MODULES)

    gaps: dict[str, dict[str, Any]] = {}
    incompleteness_reasons: list[str] = []

    # Dynamic probe block (non-fatal; drives potentially_incomplete indicator).
    dynamic_probes = _run_dynamic_probes(probe_modules)
    for probe in dynamic_probes:
        if not probe["available"]:
            incompleteness_reasons.append(
                f"dynamic_probe_unavailable:{probe['probe']}:{probe['error']}"
            )

    # 1) Use-case capabilities and tool exposure mapping (static AST).
    use_case_capabilities: dict[str, list[str]] = {}
    for surface in _USE_CASE_SURFACES:
        methods = sorted(_public_methods_for_surface(surface))
        use_case_capabilities[surface.alias] = methods

    all_capabilities = sorted(
        f"{alias}.{method}"
        for alias, methods in use_case_capabilities.items()
        for method in methods
    )

    tool_registry_index = _collect_tool_registry_index()
    capability_to_tools = tool_registry_index["capability_to_tools"]
    capability_gaps = sorted(set(all_capabilities) - set(capability_to_tools.keys()))

    for capability in capability_gaps:
        gap_key = f"capability_gap:{capability}"
        gaps[gap_key] = _gap_record(
            gap_key,
            "use_case_vs_tools",
            "Use-case capability is not reachable from any registered tool handler",
            data={"capability": capability},
        )

    if tool_registry_index["non_literal_tool_name_calls"]:
        incompleteness_reasons.extend(
            [
                f"non_literal_tool_name_registration:{site}"
                for site in tool_registry_index["non_literal_tool_name_calls"]
            ]
        )

    # 2) Runtime-registered tools and policy parity.
    runtime_registered_tools: list[str]
    runtime_registry_available = True
    runtime_registry_error = None
    try:
        from app.adapters.ai.tool_registry.builder import (
            list_registered_tool_names_for_policy_audit,
        )

        runtime_registered_tools = sorted(
            {name for name in list_registered_tool_names_for_policy_audit() if name}
        )
    except Exception as exc:  # pragma: no cover - environment-dependent
        runtime_registered_tools = []
        runtime_registry_available = False
        runtime_registry_error = f"{type(exc).__name__}: {exc}"
        incompleteness_reasons.append(
            f"runtime_registered_tools_unavailable:{runtime_registry_error}"
        )

    static_registered_tools = tool_registry_index["registered_tools"]
    if runtime_registry_available:
        static_set = set(static_registered_tools)
        runtime_set = set(runtime_registered_tools)
        for tool_name in sorted(runtime_set - static_set):
            gap_key = f"registry_runtime_only:{tool_name}"
            gaps[gap_key] = _gap_record(
                gap_key,
                "use_case_vs_tools",
                "Tool appears in runtime registry but not static tool_registry source scan",
                data={"tool_name": tool_name},
            )
        for tool_name in sorted(static_set - runtime_set):
            gap_key = f"registry_static_only:{tool_name}"
            gaps[gap_key] = _gap_record(
                gap_key,
                "use_case_vs_tools",
                "Tool appears in static tool_registry source scan but not runtime registry",
                data={"tool_name": tool_name},
            )

    tools_for_policy = runtime_registered_tools or static_registered_tools

    from ai_copilot.application.operator_copilot_policy import ToolPolicyRegistry

    policy_report = ToolPolicyRegistry.build_parity_report(tools_for_policy)
    for tool_name in policy_report.get("registered_only", []):
        gap_key = f"policy_registered_only:{tool_name}"
        gaps[gap_key] = _gap_record(
            gap_key,
            "policy_coverage",
            "Registered tool is missing policy classification",
            data={"tool_name": tool_name},
        )
    for tool_name in policy_report.get("policy_only_unexpected", []):
        gap_key = f"policy_unexpected_policy_only:{tool_name}"
        gaps[gap_key] = _gap_record(
            gap_key,
            "policy_coverage",
            "Policy entry is missing from runtime registry and is not explicitly excepted",
            data={"tool_name": tool_name},
        )
    for tool_name in policy_report.get("stale_intentional_exceptions", []):
        gap_key = f"policy_stale_intentional_exception:{tool_name}"
        gaps[gap_key] = _gap_record(
            gap_key,
            "policy_coverage",
            "Policy intentional-exception entry is stale and should be removed",
            data={"tool_name": tool_name},
        )

    # 3) Audit coverage expectations.
    from ai_copilot.application.ports import AUDIT_EVENT_TYPES
    from ai_copilot.application.smart_engagement.ports import (
        SMART_ENGAGEMENT_AUDIT_EVENT_TYPES,
    )

    operator_expected = sorted(set(AUDIT_EVENT_TYPES))
    operator_emitted, operator_dynamic_sites = _collect_operator_emitted_audit_events()

    smart_expected = sorted(set(SMART_ENGAGEMENT_AUDIT_EVENT_TYPES))
    smart_emitted, smart_dynamic_sites = _collect_smart_engagement_emitted_audit_events()

    if operator_dynamic_sites:
        incompleteness_reasons.extend(
            [f"operator_audit_event_non_literal:{site}" for site in operator_dynamic_sites]
        )
    if smart_dynamic_sites:
        incompleteness_reasons.extend(
            [f"smart_engagement_audit_event_non_literal:{site}" for site in smart_dynamic_sites]
        )

    operator_missing = sorted(set(operator_expected) - set(operator_emitted))
    operator_unexpected = sorted(set(operator_emitted) - set(operator_expected))
    smart_missing = sorted(set(smart_expected) - set(smart_emitted))
    smart_unexpected = sorted(set(smart_emitted) - set(smart_expected))

    for event_name in operator_missing:
        gap_key = f"operator_audit_missing:{event_name}"
        gaps[gap_key] = _gap_record(
            gap_key,
            "audit_coverage.operator",
            "Expected operator audit event is not emitted by graph nodes",
            data={"event_type": event_name},
        )
    for event_name in operator_unexpected:
        gap_key = f"operator_audit_unexpected:{event_name}"
        gaps[gap_key] = _gap_record(
            gap_key,
            "audit_coverage.operator",
            "Operator graph emits audit event not present in canonical schema",
            data={"event_type": event_name},
        )
    for event_name in smart_missing:
        gap_key = f"smart_audit_missing:{event_name}"
        gaps[gap_key] = _gap_record(
            gap_key,
            "audit_coverage.smart_engagement",
            "Expected smart-engagement audit event is not emitted by nodes",
            data={"event_type": event_name},
        )
    for event_name in smart_unexpected:
        gap_key = f"smart_audit_unexpected:{event_name}"
        gaps[gap_key] = _gap_record(
            gap_key,
            "audit_coverage.smart_engagement",
            "Smart-engagement node emits audit event not in expected contract",
            data={"event_type": event_name},
        )

    # 4) Apply explicit exception manifest with mandatory justifications.
    manifest = _load_exception_manifest(exception_path)
    exception_map = manifest["exception_map"]
    invalid_exception_entries = manifest["invalid_entries"]
    all_gap_keys = sorted(gaps.keys())
    excepted_gap_keys = sorted(set(all_gap_keys) & set(exception_map.keys()))
    unexplained_gap_keys = sorted(set(all_gap_keys) - set(exception_map.keys()))
    stale_exception_keys = sorted(set(exception_map.keys()) - set(all_gap_keys))

    is_ci_pass = (
        not unexplained_gap_keys
        and not stale_exception_keys
        and not invalid_exception_entries
    )

    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scanner_version": 1,
        "potentially_incomplete": bool(incompleteness_reasons),
        "incompleteness_reasons": sorted(incompleteness_reasons),
        "dynamic_probes": dynamic_probes,
        "sections": {
            "use_case_vs_tools": {
                "use_case_capabilities": use_case_capabilities,
                "all_capabilities": all_capabilities,
                "covered_capabilities": sorted(capability_to_tools.keys()),
                "capability_to_tools": capability_to_tools,
                "capability_gaps": capability_gaps,
                "registered_tools_static": static_registered_tools,
                "registered_tools_runtime": runtime_registered_tools,
                "runtime_registry_available": runtime_registry_available,
                "runtime_registry_error": runtime_registry_error,
                "tool_to_capabilities": tool_registry_index["tool_to_capabilities"],
            },
            "policy_coverage": {
                **policy_report,
                "tool_names_input": tools_for_policy,
            },
            "audit_coverage": {
                "operator": {
                    "expected": operator_expected,
                    "emitted": sorted(operator_emitted),
                    "missing_expected": operator_missing,
                    "unexpected_emitted": operator_unexpected,
                },
                "smart_engagement": {
                    "expected": smart_expected,
                    "emitted": sorted(smart_emitted),
                    "missing_expected": smart_missing,
                    "unexpected_emitted": smart_unexpected,
                },
            },
        },
        "exceptions": {
            "manifest_path": manifest["path"],
            "manifest_version": manifest["version"],
            "declared_gap_keys": sorted(exception_map.keys()),
            "matched_gap_keys": excepted_gap_keys,
            "stale_gap_keys": stale_exception_keys,
            "invalid_entries": invalid_exception_entries,
        },
        "gaps": {
            "all": [gaps[key] for key in all_gap_keys],
            "unexplained_gap_keys": unexplained_gap_keys,
            "excepted_gap_keys": excepted_gap_keys,
            "stale_exception_gap_keys": stale_exception_keys,
        },
        "backlog_status": {
            "tracked_open_gaps": excepted_gap_keys,
            "tracked_open_count": len(excepted_gap_keys),
            "closure_confirmed": len(excepted_gap_keys) == 0,
        },
        "is_ci_pass": is_ci_pass,
    }
    return report


def _render_text_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("LangGraph Audit Coverage Report")
    lines.append(f"generated_at_utc: {report['generated_at_utc']}")
    lines.append(
        "potentially_incomplete: "
        + ("yes" if report["potentially_incomplete"] else "no")
    )
    if report["incompleteness_reasons"]:
        lines.append("incompleteness_reasons:")
        for reason in report["incompleteness_reasons"]:
            lines.append(f"  - {reason}")

    use_case_section = report["sections"]["use_case_vs_tools"]
    policy_section = report["sections"]["policy_coverage"]
    audit_section = report["sections"]["audit_coverage"]

    lines.append(
        "use_case_vs_tools: "
        f"{len(use_case_section['all_capabilities'])} capabilities, "
        f"{len(use_case_section['covered_capabilities'])} covered, "
        f"{len(use_case_section['capability_gaps'])} gaps"
    )
    lines.append(
        "policy_coverage: "
        f"registered_only={len(policy_section['registered_only'])}, "
        f"policy_only_unexpected={len(policy_section['policy_only_unexpected'])}, "
        "stale_intentional_exceptions="
        f"{len(policy_section['stale_intentional_exceptions'])}"
    )
    lines.append(
        "audit_coverage.operator: "
        f"missing_expected={len(audit_section['operator']['missing_expected'])}, "
        f"unexpected_emitted={len(audit_section['operator']['unexpected_emitted'])}"
    )
    lines.append(
        "audit_coverage.smart_engagement: "
        f"missing_expected={len(audit_section['smart_engagement']['missing_expected'])}, "
        "unexpected_emitted="
        f"{len(audit_section['smart_engagement']['unexpected_emitted'])}"
    )

    lines.append(
        "exceptions: "
        f"matched={len(report['exceptions']['matched_gap_keys'])}, "
        f"stale={len(report['exceptions']['stale_gap_keys'])}, "
        f"invalid={len(report['exceptions']['invalid_entries'])}"
    )

    lines.append(
        f"unexplained_gaps: {len(report['gaps']['unexplained_gap_keys'])}"
    )
    if report["gaps"]["unexplained_gap_keys"]:
        lines.append("unexplained_gap_keys:")
        for key in report["gaps"]["unexplained_gap_keys"]:
            lines.append(f"  - {key}")

    lines.append(f"is_ci_pass: {str(report['is_ci_pass']).lower()}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan LangGraph tool/policy/audit coverage and report gaps."
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the full JSON report",
    )
    parser.add_argument(
        "--exceptions",
        type=Path,
        default=DEFAULT_EXCEPTION_PATH,
        help="Path to exception manifest JSON",
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Exit with code 1 when unexplained/stale/invalid gaps exist",
    )
    args = parser.parse_args(argv)

    report = run_scan(exceptions_path=args.exceptions)
    report_json = json.dumps(report, indent=2, sort_keys=True)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report_json + "\n", encoding="utf-8")

    if args.format == "json":
        sys.stdout.write(report_json + "\n")
    else:
        sys.stdout.write(_render_text_report(report) + "\n")

    if args.enforce and not report["is_ci_pass"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
