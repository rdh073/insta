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
