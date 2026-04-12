"""Unit tests for SSE heartbeat and stream exception framing helper."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.adapters.http.streaming import sse_chunks


async def _collect_chunks(generator):
    return [chunk async for chunk in generator]


def _decode_data_events(chunks: list[str]) -> list[dict]:
    events: list[dict] = []
    for chunk in chunks:
        for line in chunk.splitlines():
            if not line.startswith("data: "):
                continue
            payload = line.removeprefix("data: ").strip()
            if not payload or payload == "[DONE]":
                continue
            events.append(json.loads(payload))
    return events


def test_sse_chunks_emits_heartbeat_while_waiting_for_events():
    async def delayed_events():
        await asyncio.sleep(0.03)
        yield {"type": "run_start", "run_id": "r1", "thread_id": "t1"}

    chunks = asyncio.run(
        _collect_chunks(sse_chunks(delayed_events(), heartbeat_seconds=0.005)),
    )

    assert any(chunk.startswith(": heartbeat") for chunk in chunks)
    events = _decode_data_events(chunks)
    assert events[0]["type"] == "run_start"


def test_sse_chunks_frames_stream_exception_as_run_error():
    async def failing_events():
        yield {"type": "run_start", "run_id": "run-x", "thread_id": "thread-x"}
        raise RuntimeError("exploded stream")
        yield  # pragma: no cover

    chunks = asyncio.run(
        _collect_chunks(sse_chunks(failing_events(), heartbeat_seconds=0.005)),
    )

    events = _decode_data_events(chunks)
    assert events[0]["type"] == "run_start"
    assert events[-1]["type"] == "run_error"
    assert events[-1]["code"] == "stream_error"
    assert events[-1]["run_id"] == "run-x"
    assert events[-1]["thread_id"] == "thread-x"
    assert events[-1]["message"] == "Stream interrupted by an internal transport error."
    assert "exploded stream" not in events[-1]["message"]


def test_sse_chunks_can_emit_named_run_error_event():
    async def failing_events():
        raise RuntimeError("exploded stream")
        yield  # pragma: no cover

    chunks = asyncio.run(
        _collect_chunks(
            sse_chunks(
                failing_events(),
                heartbeat_seconds=0.005,
                error_event_name="run_error",
            ),
        ),
    )

    assert any(chunk.startswith("event: run_error\n") for chunk in chunks)
    events = _decode_data_events(chunks)
    assert events[-1]["type"] == "run_error"
