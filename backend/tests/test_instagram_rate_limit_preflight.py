"""Rate-limit preflight contract tests for Instagram adapters."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.adapters.instagram.comment_writer import InstagramCommentWriterAdapter
from app.adapters.instagram.direct_reader import InstagramDirectReaderAdapter
from app.adapters.instagram.error_utils import InstagramRateLimitError
from app.adapters.instagram.media_reader import InstagramMediaReaderAdapter
from app.adapters.instagram.rate_limit_guard import rate_limit_guard

ADAPTER_ROOT = Path(__file__).resolve().parents[1] / "app" / "adapters" / "instagram"

# translate_instagram_error paths without account_id cannot run account cooldown preflight.
ALLOWED_UNSCOPED_TRANSLATE_PATHS = {
    ("story_reader.py", "get_story_pk_from_url"),
    ("highlight_reader.py", "get_highlight_pk_from_url"),
}

GUARD_CALL_NAMES = {"check_rate_limit", "get_guarded_client"}
SKIP_MODULES = {
    "__init__.py",
    "client.py",
    "client_guard.py",
    "device_pool.py",
    "error_utils.py",
    "exception_handler.py",
    "rate_limit_guard.py",
}


def _called_function_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name):
            names.add(child.func.id)
        elif isinstance(child.func, ast.Attribute):
            names.add(child.func.attr)
    return names


def _iter_adapter_paths() -> list[Path]:
    return sorted(
        path
        for path in ADAPTER_ROOT.glob("*.py")
        if path.name not in SKIP_MODULES
    )


def test_translate_paths_with_account_context_are_preflight_guarded() -> None:
    """Every account-scoped translate path must execute a cooldown preflight."""
    missing_guard: list[str] = []
    unscoped_translate_paths: set[tuple[str, str]] = set()

    for path in _iter_adapter_paths():
        tree = ast.parse(path.read_text(), filename=str(path))

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            called = _called_function_names(node)
            if "translate_instagram_error" not in called:
                continue

            has_account_id_arg = any(arg.arg == "account_id" for arg in node.args.args)
            if not has_account_id_arg:
                unscoped_translate_paths.add((path.name, node.name))
                continue

            if called.isdisjoint(GUARD_CALL_NAMES):
                missing_guard.append(f"{path.name}:{node.lineno}::{node.name}")

    assert unscoped_translate_paths == ALLOWED_UNSCOPED_TRANSLATE_PATHS
    assert missing_guard == []


@pytest.mark.parametrize(
    ("adapter_factory", "invoke"),
    [
        (
            InstagramMediaReaderAdapter,
            lambda adapter, account_id: adapter.get_media_by_pk(account_id, 123),
        ),
        (
            InstagramCommentWriterAdapter,
            lambda adapter, account_id: adapter.create_comment(account_id, "123", "hi"),
        ),
        (
            InstagramDirectReaderAdapter,
            lambda adapter, account_id: adapter.list_inbox_threads(account_id, amount=1),
        ),
    ],
    ids=["media_reader", "comment_writer", "direct_reader"],
)
def test_cooldown_preflight_blocks_before_client_lookup(adapter_factory, invoke) -> None:
    """When an account is cooling down, adapters must short-circuit before repo/client usage."""
    account_id = "acc-cooldown"
    repo = Mock()
    repo.get.side_effect = AssertionError("client lookup should not run while cooling down")
    adapter = adapter_factory(repo)

    rate_limit_guard.mark_limited(account_id, cooldown_sec=60)
    try:
        with pytest.raises(InstagramRateLimitError):
            invoke(adapter, account_id)
    finally:
        rate_limit_guard.clear(account_id)

    assert repo.get.call_count == 0
