"""Source-level regression checks for frontend stream transport guards."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_graph_runner_has_content_type_and_empty_stream_guards():
    source = _read("frontend/src/api/graph-runner.ts")
    assert "text/event-stream" in source
    assert "Stream ended without any SSE data events." in source


def test_operator_stream_has_content_type_and_empty_stream_guards():
    source = _read("frontend/src/api/operator-copilot.ts")
    assert "text/event-stream" in source
    assert "Stream ended without any SSE data events." in source


def test_engage_slash_command_uses_stream_endpoints_and_resume_mapping():
    source = _read("frontend/src/lib/slash-commands.ts")
    assert "/ai/smart-engagement/recommend/stream" in source
    assert "/ai/smart-engagement/resume/stream" in source
    assert "editedCaption" in source
    assert "overridePolicy" in source
    assert "twoFaCode" in source


def test_frontend_stream_consumers_handle_named_run_error_events():
    files = [
        "frontend/src/pages/LogStreamPage.tsx",
        "frontend/src/features/accounts/hooks/useAccountEvents.ts",
        "frontend/src/api/posts.ts",
    ]
    for path in files:
        source = _read(path)
        assert "addEventListener('run_error'" in source or 'addEventListener("run_error"' in source

    # Ensure shared formatting/parsing helpers are used so diagnostics stay consistent.
    assert "formatStreamRunError" in _read("frontend/src/pages/LogStreamPage.tsx")
    assert "formatStreamRunError" in _read("frontend/src/features/accounts/hooks/useAccountEvents.ts")
    assert "parseStreamRunError" in _read("frontend/src/api/posts.ts")
