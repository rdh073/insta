"""Anthropic SSE streaming event normalization helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class SSEParserState:
    buffer: str = ""
    current_event: str | None = None
    current_data_lines: list[str] | None = None

    def __post_init__(self) -> None:
        if self.current_data_lines is None:
            self.current_data_lines = []


def parse_sse_chunk(chunk: str, state: SSEParserState) -> tuple[list[dict[str, Any]], SSEParserState]:
    """Parse SSE chunk into event list while preserving parser state."""
    events: list[dict[str, Any]] = []
    lines = (state.buffer + chunk).split("\n")
    buffer_tail = ""

    for i, line in enumerate(lines):
        # keep incomplete last line for next chunk
        if i == len(lines) - 1 and chunk and not chunk.endswith("\n"):
            buffer_tail = line
            continue

        if line.startswith("event:"):
            state.current_event = line[len("event:") :].strip()
            continue
        if line.startswith("data:"):
            state.current_data_lines.append(line[len("data:") :].strip())
            continue
        if line.strip() == "":
            if state.current_event and state.current_data_lines:
                data_raw = "\n".join(state.current_data_lines).strip()
                parsed_data: Any
                try:
                    parsed_data = json.loads(data_raw)
                except Exception:
                    parsed_data = {"raw": data_raw}
                events.append({"event": state.current_event, "data": parsed_data})
            state.current_event = None
            state.current_data_lines = []

    state.buffer = buffer_tail
    return events, state


def normalize_anthropic_sse_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Normalize Anthropic SSE events to gateway completion shape."""
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    finish_reason = "stop"

    for event in events:
        event_type = str(event.get("event") or "")
        data = event.get("data")

        if event_type == "content_block_delta" and isinstance(data, dict):
            delta = data.get("delta")
            if isinstance(delta, dict) and isinstance(delta.get("text"), str):
                text_parts.append(delta["text"])

        if event_type == "content_block_start" and isinstance(data, dict):
            block = data.get("content_block")
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_calls.append(
                    {
                        "id": block.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                        },
                    }
                )

        if event_type == "message_delta" and isinstance(data, dict):
            delta = data.get("delta")
            if isinstance(delta, dict) and isinstance(delta.get("stop_reason"), str):
                finish_reason = delta["stop_reason"]

    return {
        "content": "".join(text_parts).strip(),
        "finish_reason": finish_reason or "stop",
        "tool_calls": tool_calls,
    }
