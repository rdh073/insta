"""Phase B Test: Verify tool runtime consolidation - no legacy ai_tools in app layer."""

from __future__ import annotations

import os
import re
import subprocess

import pytest


class TestPhaseBAiToolsCleanup:
    """Verify ai_tools is not imported in app layer."""

    def test_no_ai_tools_imports_in_app_layer(self):
        result = subprocess.run(
            ["grep", "-r", "from ai_tools\\|import ai_tools", "backend/app", "--include=*.py"],
            capture_output=True,
            text=True,
            cwd="/home/xtrzy/Workspace/insta",
        )

        assert result.returncode != 0 or "No such file" in result.stderr, (
            f"CRITICAL: Found ai_tools imports in app layer:\n{result.stdout}\n"
            "Phase B requires ALL ai_tools imports to be removed from backend/app/*"
        )

    def test_tool_registry_is_single_source_of_truth(self):
        from app.adapters.ai.tool_registry import ToolRegistry

        assert ToolRegistry is not None
        assert hasattr(ToolRegistry, "execute")
        assert hasattr(ToolRegistry, "get_schemas")

    def test_utils_py_no_ai_tools_import(self):
        with open("/home/xtrzy/Workspace/insta/backend/app/adapters/http/utils.py") as f:
            content = f.read()

        assert "from ai_tools import" not in content
        assert "import ai_tools" not in content

    def test_legacy_tools_py_marked_deprecated(self):
        with open("/home/xtrzy/Workspace/insta/backend/app/adapters/ai/tools.py") as f:
            content = f.read()

        assert "DEPRECATED" in content
        assert "PHASE B" in content


class TestPhaseBToolRegistryIntegration:
    def test_tool_registry_in_container(self):
        from app.bootstrap.container import create_services

        services = create_services()
        assert "tool_registry" in services
        assert services["tool_registry"] is not None

    def test_legacy_ai_chat_module_removed_in_langgraph_only_mode(self):
        with pytest.raises(ModuleNotFoundError):
            __import__("app.application.use_cases.ai_chat")


class TestPhaseBUtilsCleanup:
    def test_utils_no_dead_code(self):
        with open("/home/xtrzy/Workspace/insta/backend/app/adapters/http/utils.py") as f:
            content = f.read()

        assert "async def stream_tool_calls" not in content
        assert "def resolve_ai_provider" not in content
        assert "def build_ai_messages" not in content
        assert "def build_ai_client" not in content

    def test_utils_has_required_functions(self):
        with open("/home/xtrzy/Workspace/insta/backend/app/adapters/http/utils.py") as f:
            content = f.read()

        assert "def format_error" in content
        assert "def format_instagram_failure" in content


class TestPhaseBExitCriteria:
    def test_criterion_no_ai_tools_in_app(self):
        ai_tools_pattern = re.compile(r"(from\\s+ai_tools\\s+import|import\\s+ai_tools)")

        found_imports = []
        for root, dirs, files in os.walk("/home/xtrzy/Workspace/insta/backend/app"):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    with open(filepath) as f:
                        for line_num, line in enumerate(f, 1):
                            if ai_tools_pattern.search(line):
                                found_imports.append(f"{filepath}:{line_num}: {line.strip()}")

        assert len(found_imports) == 0, (
            f"Found {len(found_imports)} ai_tools imports in app layer:\n"
            + "\n".join(found_imports)
        )

    def test_criterion_single_tool_registry(self):
        from app.adapters.ai.tool_registry import ToolRegistry
        from app.bootstrap.container import create_services

        assert ToolRegistry is not None
        services = create_services()
        assert services["tool_registry"] is not None

    def test_criterion_deprecated_functions_fail_safely(self):
        from app.adapters.ai.tools import get_ai_tool_registry, get_ai_tools_list, execute_tool

        with pytest.raises(NotImplementedError):
            get_ai_tool_registry()
        with pytest.raises(NotImplementedError):
            get_ai_tools_list()
        with pytest.raises(NotImplementedError):
            execute_tool("test", {})


class TestPhaseBNoRegression:
    def test_no_new_ai_tools_imports(self):
        ai_tools_pattern = re.compile(r"(from\\s+ai_tools\\s+import|import\\s+ai_tools)")

        violations = []
        for root, dirs, files in os.walk("/home/xtrzy/Workspace/insta/backend/app"):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath) as f:
                            content = f.read()
                            if ai_tools_pattern.search(content):
                                violations.append(filepath)
                    except (IOError, UnicodeDecodeError):
                        pass

        assert len(violations) == 0, (
            "Regression: Found ai_tools imports in:\n" + "\n".join(violations)
        )
