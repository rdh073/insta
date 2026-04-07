"""Architecture boundary tests — Phase 0 of the Robust Threaded Job Engine migration.

These tests prove that app/application/ has no direct imports of legacy root
modules (instagram.py, state.py, services.py) or vendor SDKs (instagrapi,
sqlalchemy, fastapi).

Static AST analysis: no modules are imported at runtime.  Fast and stable.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
APPLICATION_DIR = BACKEND_DIR / "app" / "application"

# Legacy root-level modules that application code must never import.
_FORBIDDEN_ROOT_MODULES = frozenset({"instagram", "state", "services"})

# Vendor SDKs that application code must never import.
_FORBIDDEN_VENDOR_SDKS = frozenset({"instagrapi", "sqlalchemy", "fastapi", "uvicorn"})


def _absolute_top_level_imports(path: Path) -> list[str]:
    """Return every absolute top-level module name imported in *path* (AST parse only)."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        pytest.skip(f"Syntax error in {path}")
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # level == 0 means absolute import; relative imports (level > 0) are safe.
            if node.level == 0 and node.module:
                names.append(node.module.split(".")[0])
    return names


def _application_py_files() -> list[Path]:
    if not APPLICATION_DIR.exists():
        return []
    return [p for p in APPLICATION_DIR.rglob("*.py") if p.name != "__init__.py"]


_APPLICATION_FILES = _application_py_files()


class TestApplicationLayerBoundary:
    """app/application/ must not import legacy root modules or vendor SDKs."""

    @pytest.mark.parametrize(
        "py_file",
        _APPLICATION_FILES,
        ids=lambda p: str(p.relative_to(APPLICATION_DIR)),
    )
    def test_no_legacy_root_module_imports(self, py_file: Path) -> None:
        """Application code must not import instagram.py, state.py, or services.py."""
        imports = _absolute_top_level_imports(py_file)
        violations = [m for m in imports if m in _FORBIDDEN_ROOT_MODULES]
        assert not violations, (
            f"{py_file.relative_to(BACKEND_DIR)!s} imports legacy root module(s): {violations}\n"
            "Application layer must depend on ports only — never on instagram.py or state.py."
        )

    @pytest.mark.parametrize(
        "py_file",
        _APPLICATION_FILES,
        ids=lambda p: str(p.relative_to(APPLICATION_DIR)),
    )
    def test_no_vendor_sdk_imports(self, py_file: Path) -> None:
        """Application code must not import vendor SDKs (instagrapi, sqlalchemy, fastapi)."""
        imports = _absolute_top_level_imports(py_file)
        violations = [m for m in imports if m in _FORBIDDEN_VENDOR_SDKS]
        assert not violations, (
            f"{py_file.relative_to(BACKEND_DIR)!s} imports vendor SDK(s): {violations}\n"
            "Application layer must be vendor-free.  Add a port and adapter instead."
        )
