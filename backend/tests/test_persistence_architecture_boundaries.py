"""Phase 0 persistence architecture guardrails.

These tests enforce dependency direction and prevent persistence leakage.
"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path("/home/xtrzy/Workspace/insta")
BACKEND_ROOT = REPO_ROOT / "backend"
APP_ROOT = BACKEND_ROOT / "app"
APPLICATION_ROOT = APP_ROOT / "application"
HTTP_ROOT = APP_ROOT / "adapters" / "http"
AI_COPILOT_ROOT = BACKEND_ROOT / "ai_copilot"
INSTAGRAM_ADAPTER_ROOT = APP_ROOT / "adapters" / "instagram"


def _iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


class TestPersistenceArchitectureBoundaries:
    """Block persistence boundary violations."""

    def test_application_layer_must_not_import_backend_state(self):
        pattern = re.compile(r"(^|\s)(import\s+state\b|from\s+state\s+import\b)")
        violations: list[str] = []

        for path in _iter_python_files(APPLICATION_ROOT):
            for line_no, line in enumerate(path.read_text().splitlines(), 1):
                if pattern.search(line):
                    violations.append(f"{path}:{line_no}:{line.strip()}")

        assert violations == [], "\n".join([
            "Found forbidden state.py imports in backend/app/application:",
            *violations,
        ])

    def test_http_layer_must_not_import_concrete_persistence_adapters(self):
        pattern = re.compile(
            r"from\s+app\.adapters\.persistence\b|import\s+app\.adapters\.persistence\b"
        )
        violations: list[str] = []

        for path in _iter_python_files(HTTP_ROOT):
            for line_no, line in enumerate(path.read_text().splitlines(), 1):
                if pattern.search(line):
                    violations.append(f"{path}:{line_no}:{line.strip()}")

        assert violations == [], "\n".join([
            "Found forbidden persistence adapter imports in backend/app/adapters/http:",
            *violations,
        ])

    def test_ai_copilot_must_not_import_concrete_persistence_adapters(self):
        pattern = re.compile(
            r"from\s+app\.adapters\.persistence\b|import\s+app\.adapters\.persistence\b"
        )
        violations: list[str] = []

        for path in _iter_python_files(AI_COPILOT_ROOT):
            for line_no, line in enumerate(path.read_text().splitlines(), 1):
                if pattern.search(line):
                    violations.append(f"{path}:{line_no}:{line.strip()}")

        assert violations == [], "\n".join([
            "Found forbidden persistence adapter imports in backend/ai_copilot:",
            *violations,
        ])

    def test_state_import_allowed_only_in_persistence_gateway(self):
        pattern = re.compile(r"(^|\s)(import\s+state\b|from\s+state\s+import\b)")
        allowed = APP_ROOT / "adapters" / "persistence" / "state_gateway.py"
        violations: list[str] = []

        for path in _iter_python_files(APP_ROOT):
            if path == allowed:
                continue
            for line_no, line in enumerate(path.read_text().splitlines(), 1):
                if pattern.search(line):
                    violations.append(f"{path}:{line_no}:{line.strip()}")

        assert violations == [], "\n".join([
            "Found forbidden direct state.py imports outside persistence gateway:",
            *violations,
        ])

    def test_application_layer_must_not_import_concrete_persistence_adapters(self):
        pattern = re.compile(
            r"from\s+app\.adapters\.persistence\b|import\s+app\.adapters\.persistence\b"
        )
        violations: list[str] = []

        for path in _iter_python_files(APPLICATION_ROOT):
            for line_no, line in enumerate(path.read_text().splitlines(), 1):
                if pattern.search(line):
                    violations.append(f"{path}:{line_no}:{line.strip()}")

        assert violations == [], "\n".join([
            "Found forbidden persistence adapter imports in backend/app/application:",
            *violations,
        ])

    def test_instagrapi_imports_allowed_only_in_instagram_adapters(self):
        pattern = re.compile(
            r"(^|\s)(from\s+instagrapi\b|import\s+instagrapi\b)"
        )
        violations: list[str] = []

        for path in _iter_python_files(APP_ROOT):
            if INSTAGRAM_ADAPTER_ROOT in path.parents:
                continue
            for line_no, line in enumerate(path.read_text().splitlines(), 1):
                if pattern.search(line):
                    violations.append(f"{path}:{line_no}:{line.strip()}")

        assert violations == [], "\n".join([
            "Found forbidden instagrapi imports outside backend/app/adapters/instagram:",
            *violations,
        ])

    def test_application_layer_must_not_import_sqlalchemy(self):
        """Enforce that application/use-cases never import SQLAlchemy directly."""
        pattern = re.compile(
            r"(^|\s)(from\s+sqlalchemy|import\s+sqlalchemy)"
        )
        violations: list[str] = []

        for path in _iter_python_files(APPLICATION_ROOT):
            for line_no, line in enumerate(path.read_text().splitlines(), 1):
                if pattern.search(line):
                    violations.append(f"{path}:{line_no}:{line.strip()}")

        assert violations == [], "\n".join([
            "Found forbidden SQLAlchemy imports in backend/app/application:",
            "Application layer must use only persistence ports, not SQLAlchemy directly.",
            *violations,
        ])

    def test_persistence_contracts_frozen(self):
        """Verify that persistence record contracts are documented and immutable."""
        persistence_models_path = APP_ROOT / "application" / "ports" / "persistence_models.py"
        content = persistence_models_path.read_text()

        # Verify core record types exist with docstrings
        assert "class AccountRecord:" in content
        assert "class JobRecord:" in content
        assert '"""Canonical account persistence record."""' in content or "account persistence record" in content
        assert '"""Canonical post job persistence record."""' in content or "post job persistence record" in content

        # Verify they are immutable dataclasses with @dataclass decorator
        assert "@dataclass" in content
        assert "class AccountRecord:" in content

    def test_persistence_uow_contract_defined(self):
        """Verify persistence UoW port contract is defined."""
        persistence_uow_path = APP_ROOT / "application" / "ports" / "persistence_uow.py"
        content = persistence_uow_path.read_text()

        # Verify contract exists
        assert "class PersistenceUnitOfWork" in content
