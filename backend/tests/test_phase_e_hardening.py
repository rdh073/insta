"""Phase E hardening guardrails for LangGraph-only architecture.

These tests are intended to block regression in CI.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.routing import APIRoute

from app.main import app


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


class TestPhaseEArchitectureGuards:
    """Block legacy dependency reintroduction in app layer."""

    def test_no_ai_tools_imports_in_backend_app(self):
        pattern = re.compile(r"(from\s+ai_tools\s+import|import\s+ai_tools)")
        violations: list[str] = []

        for path in BACKEND_APP.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for line_no, line in enumerate(path.read_text().splitlines(), 1):
                if pattern.search(line):
                    violations.append(f"{path}:{line_no}:{line.strip()}")

        assert violations == [], "\n".join([
            "Found forbidden ai_tools imports in backend/app:",
            *violations,
        ])

    def test_no_legacy_usecase_injection_functions(self):
        dep_file = REPO_ROOT / "backend" / "app" / "adapters" / "http" / "dependencies.py"
        content = dep_file.read_text()

        assert "def get_ai_chat_usecases():" not in content
        assert "def get_ai_graph_chat_usecases():" not in content

    def test_no_legacy_orchestrator_in_container(self):
        container = REPO_ROOT / "backend" / "app" / "bootstrap" / "container.py"
        content = container.read_text()

        forbidden = [
            "from app.application.use_cases.ai_chat import",
            "from app.application.use_cases.ai_graph_chat import",
            "AIChartUseCases(",
            "AIGraphChatUseCases(",
        ]
        for token in forbidden:
            assert token not in content, f"Forbidden token in container: {token}"


class TestPhaseERouteOwnership:
    """Ensure graph endpoints are owned by ai_copilot and not duplicated."""

    def _post_routes(self, path: str) -> list[APIRoute]:
        return [
            route
            for route in app.routes
            if isinstance(route, APIRoute)
            and route.path == path
            and "POST" in route.methods
        ]

    def test_graph_primary_route_single_owner(self):
        routes = self._post_routes("/api/ai/chat/graph")

        assert len(routes) == 1
        assert routes[0].endpoint.__module__.endswith("ai_copilot.api")

    def test_graph_resume_route_single_owner(self):
        routes = self._post_routes("/api/ai/chat/graph/resume")

        assert len(routes) == 1
        assert routes[0].endpoint.__module__.endswith("ai_copilot.api")

    def test_graph_alias_routes_single_owner(self):
        alias_paths = ["/api/ai/graph-chat", "/api/ai/graph-chat/resume"]

        for path in alias_paths:
            routes = self._post_routes(path)
            assert len(routes) == 1
            assert routes[0].endpoint.__module__.endswith("ai_copilot.api")

    def test_legacy_chat_route_absent(self):
        routes = self._post_routes("/api/ai/chat")
        assert routes == []

    def test_no_duplicate_post_route_registration(self):
        seen: set[tuple[str, str]] = set()
        dupes: list[tuple[str, str]] = []

        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            for method in route.methods or set():
                key = (route.path, method)
                if key in seen:
                    dupes.append(key)
                else:
                    seen.add(key)

        assert dupes == [], f"Duplicate route registrations detected: {dupes}"


class TestPhaseEToolRegistryGuards:
    """Ensure only tool registry path is used by app runtime."""

    def test_container_provides_tool_registry(self):
        from app.bootstrap.container import create_services

        services = create_services()
        assert services.get("tool_registry") is not None

    def test_deprecated_tools_bridge_removed(self):
        # Phase 5: tombstone file deleted — import must fail
        import importlib
        import pytest

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("app.adapters.ai.tools")


class TestPhaseEDocumentationGuards:
    """Ensure anti-legacy rules are documented where contributors will see them."""

    # Canonical token for wording guards: use one exact phrase to avoid drift
    # between hyphen/case variants while keeping docs and tests machine-checkable.
    LANGGRAPH_ONLY_PHRASE = "LangGraph-Only"

    def test_agents_docs_contain_langgraph_only_rule(self):
        docs = [
            REPO_ROOT / "backend" / "AGENTS.md",
            REPO_ROOT / "backend" / "app" / "AGENTS.md",
            REPO_ROOT / "backend" / "ai_copilot" / "AGENTS.md",
        ]

        for doc in docs:
            assert doc.exists(), f"Missing required AGENTS file: {doc}"
            text = doc.read_text()
            assert self.LANGGRAPH_ONLY_PHRASE in text, (
                f"Missing {self.LANGGRAPH_ONLY_PHRASE} rule in {doc}"
            )
            assert "/api/ai/chat" in text, f"Missing legacy endpoint prohibition in {doc}"


class TestPhaseEProgramExitCriteria:
    """Program-level checks to mirror plan exit criteria."""

    def test_runtime_has_no_legacy_orchestrator_services(self):
        from app.bootstrap.container import create_services

        services = create_services()
        assert "ai_chat" not in services
        assert "ai_graph_chat" not in services

    def test_legacy_usecase_modules_removed(self):
        legacy_files = [
            REPO_ROOT / "backend" / "app" / "application" / "use_cases" / "ai_chat.py",
            REPO_ROOT / "backend" / "app" / "application" / "use_cases" / "ai_graph_chat.py",
        ]

        for path in legacy_files:
            assert not path.exists(), f"Legacy file should be removed: {path}"


class TestBackendRefactorCleanupGuards:
    """Phase 0 guardrails: block inward dependency leaks from new core to root legacy layer.

    Allowed transitional exceptions (must stay outside the policy core):
    - app/adapters/* may delegate to legacy instagram.py / services.py at the adapter layer
    """

    APPLICATION_DIRS = [
        BACKEND_APP / "application",
        REPO_ROOT / "backend" / "ai_copilot" / "application",
    ]

    def _scan(self, pattern: re.Pattern) -> list[str]:
        violations: list[str] = []
        for base in self.APPLICATION_DIRS:
            for path in base.rglob("*.py"):
                if "__pycache__" in path.parts:
                    continue
                for line_no, line in enumerate(path.read_text().splitlines(), 1):
                    if pattern.search(line):
                        violations.append(f"{path}:{line_no}:{line.strip()}")
        return violations

    def test_no_root_usecases_imports_in_application_layer(self):
        pattern = re.compile(r"from\s+usecases\.")
        violations = self._scan(pattern)
        assert violations == [], (
            "New application layer must not import from root usecases.*:\n"
            + "\n".join(violations)
        )

    def test_no_root_adapters_imports_in_application_layer(self):
        pattern = re.compile(r"from\s+adapters\.")
        violations = self._scan(pattern)
        assert violations == [], (
            "New application layer must not import from root adapters.*:\n"
            + "\n".join(violations)
        )

    def test_no_root_instagram_imports_in_application_layer(self):
        pattern = re.compile(r"(from\s+instagram\s+import|import\s+instagram\b)")
        violations = self._scan(pattern)
        assert violations == [], (
            "New application layer must not import root instagram.py:\n"
            + "\n".join(violations)
        )

    def test_dead_schema_files_removed(self):
        dead_files = [
            BACKEND_APP / "adapters" / "http" / "schemas.py",
            BACKEND_APP / "adapters" / "http" / "schemas" / "posts.py",
            BACKEND_APP / "adapters" / "ai" / "fake_ports.py",
        ]
        for path in dead_files:
            assert not path.exists(), f"Dead file should be removed: {path}"

    def test_bootstrap_does_not_use_sys_path_insert(self):
        container = REPO_ROOT / "backend" / "app" / "bootstrap" / "container.py"
        content = container.read_text()
        assert "sys.path.insert" not in content, (
            "bootstrap/container.py must not manipulate sys.path — "
            "use app-owned adapters instead"
        )

    def test_totp_adapter_is_app_owned(self):
        app_totp = BACKEND_APP / "adapters" / "totp_adapter.py"
        assert app_totp.exists(), "app/adapters/totp_adapter.py must exist"
        content = app_totp.read_text()
        assert "import pyotp" in content, "app TOTP adapter must use pyotp directly"
        assert "totp_utils" not in content, (
            "app TOTP adapter must not import root totp_utils"
        )


class TestPhase6CleanArchitectureCheckpoint:
    """Phase 6 final checkpoint — lock the clean-architecture spine permanently.

    Exit criteria (rollout plan Phase 6):
    - Single canonical entrypoint: backend/app/main.py
    - Single composition point: backend/app/bootstrap/container.py
    - Domain and application layers have no root-legacy imports
    - Root legacy files exist only at the adapter edge, never in core

    Remaining allowed root-legacy files (at adapter edge only):
    - backend/state.py       — accessed via app/adapters/persistence/state_gateway.py
    - backend/instagram.py   — accessed via app/adapters/instagram/client.py + scheduler
    - backend/services.py    — test infrastructure only, no production path
    """

    BACKEND_ROOT = REPO_ROOT / "backend"
    CORE_DIRS = [
        BACKEND_APP / "domain",
        BACKEND_APP / "application",
        REPO_ROOT / "backend" / "ai_copilot" / "application",
    ]
    ROOT_LEGACY_PATTERN = re.compile(
        r"(from\s+(state|services|instagram)\s+import"
        r"|import\s+(state|services|instagram)\b"
        r"|from\s+usecases\."
        r"|from\s+adapters\.)"
    )

    def _scan_core(self, pattern: re.Pattern) -> list[str]:
        violations: list[str] = []
        for base in self.CORE_DIRS:
            for path in base.rglob("*.py"):
                if "__pycache__" in path.parts:
                    continue
                for line_no, line in enumerate(path.read_text().splitlines(), 1):
                    if pattern.search(line):
                        violations.append(f"{path}:{line_no}: {line.strip()}")
        return violations

    def test_single_entrypoint(self):
        """Only app/main.py may define a FastAPI app instance at the root."""
        main = BACKEND_APP / "main.py"
        assert main.exists(), "backend/app/main.py must exist"
        # No other main.py under backend/app should create a FastAPI app
        for path in BACKEND_APP.rglob("*.py"):
            if path == main or "__pycache__" in path.parts:
                continue
            content = path.read_text()
            assert "FastAPI()" not in content and 'FastAPI(' not in content or path == main, (
                f"Unexpected FastAPI() instantiation outside main.py: {path}"
            )

    def test_single_composition_point(self):
        """Service wiring must happen only in bootstrap/container.py."""
        container = BACKEND_APP / "bootstrap" / "container.py"
        assert container.exists(), "backend/app/bootstrap/container.py must exist"
        # No other file under app/ should call create_services()
        for path in BACKEND_APP.rglob("*.py"):
            if path == container or "__pycache__" in path.parts:
                continue
            content = path.read_text()
            assert "create_services()" not in content, (
                f"create_services() called outside container.py: {path}"
            )

    def test_domain_layer_has_no_root_legacy_imports(self):
        domain_dir = BACKEND_APP / "domain"
        violations: list[str] = []
        for path in domain_dir.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for line_no, line in enumerate(path.read_text().splitlines(), 1):
                if self.ROOT_LEGACY_PATTERN.search(line):
                    violations.append(f"{path}:{line_no}: {line.strip()}")
        assert violations == [], (
            "Domain layer must not import root legacy modules:\n" + "\n".join(violations)
        )

    def test_application_layer_has_no_root_legacy_imports(self):
        violations = self._scan_core(self.ROOT_LEGACY_PATTERN)
        assert violations == [], (
            "Application/domain layer must not import root legacy modules:\n"
            + "\n".join(violations)
        )

    def test_root_legacy_chain_deleted(self):
        """Phase 5 chain must be gone — no re-introduction allowed."""
        deleted = [
            self.BACKEND_ROOT / "ai_tools.py",
            self.BACKEND_ROOT / "container.py",
            self.BACKEND_ROOT / "adapters" / "__init__.py",
            self.BACKEND_ROOT / "adapters" / "state_repository.py",
            self.BACKEND_ROOT / "adapters" / "instagram_adapter.py",
            self.BACKEND_ROOT / "adapters" / "activity_logger.py",
            self.BACKEND_ROOT / "adapters" / "totp_adapter.py",
            self.BACKEND_ROOT / "usecases" / "__init__.py",
            self.BACKEND_ROOT / "usecases" / "post_job.py",
            self.BACKEND_ROOT / "usecases" / "account.py",
            self.BACKEND_ROOT / "totp_utils.py",
            BACKEND_APP / "adapters" / "ai" / "tools.py",
        ]
        for path in deleted:
            assert not path.exists(), (
                f"Phase 5 deleted file must not be re-introduced: {path}"
            )

    def test_state_gateway_is_sole_state_bridge(self):
        """state.py must only be accessed through state_gateway.py inside app/."""
        gateway = BACKEND_APP / "adapters" / "persistence" / "state_gateway.py"
        assert gateway.exists(), "state_gateway.py must exist as the sole state bridge"

        direct_state_pattern = re.compile(r"(from\s+state\s+import|import\s+state\b)")
        for path in BACKEND_APP.rglob("*.py"):
            if path == gateway or "__pycache__" in path.parts:
                continue
            for line_no, line in enumerate(path.read_text().splitlines(), 1):
                if direct_state_pattern.search(line):
                    assert False, (
                        f"Direct state.py import found outside state_gateway.py: "
                        f"{path}:{line_no}: {line.strip()}"
                    )
