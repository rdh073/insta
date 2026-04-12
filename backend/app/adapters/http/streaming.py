"""SSE streaming helpers with heartbeat and exception framing."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import suppress
import logging
from typing import Any, Callable

from fastapi.responses import StreamingResponse

_DEFAULT_HEARTBEAT_SECONDS = 15.0
_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

ErrorEventBuilder = Callable[[Exception, Mapping[str, Any] | None], Mapping[str, Any]]


def _default_error_event(
    exc: Exception,
    last_event: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    event: dict[str, Any] = {
        "type": "run_error",
        "message": str(exc)[:500] or "SSE stream failed.",
    }
    if last_event:
        run_id = last_event.get("run_id")
        thread_id = last_event.get("thread_id")
        if run_id is not None:
            event["run_id"] = run_id
        if thread_id is not None:
            event["thread_id"] = thread_id
    return event


def _encode_data(payload: Any) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


async def sse_chunks(
    events: AsyncIterator[Mapping[str, Any]],
    *,
    heartbeat_seconds: float = _DEFAULT_HEARTBEAT_SECONDS,
    logger: logging.Logger | None = None,
    error_event_builder: ErrorEventBuilder | None = None,
) -> AsyncIterator[str]:
    """Encode event dicts to SSE chunks, with heartbeat + exception framing."""
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
    finished = asyncio.Event()
    last_event: Mapping[str, Any] | None = None
    builder = error_event_builder or _default_error_event

    async def _pump() -> None:
        try:
            async for event in events:
                await queue.put(("event", event))
        except Exception as exc:  # pragma: no cover - exercised via streaming tests
            await queue.put(("error", exc))
        finally:
            finished.set()

    pump_task = asyncio.create_task(_pump())
    try:
        while True:
            if finished.is_set() and queue.empty():
                break

            try:
                item_type, payload = await asyncio.wait_for(
                    queue.get(),
                    timeout=heartbeat_seconds,
                )
            except asyncio.TimeoutError:
                if finished.is_set() and queue.empty():
                    break
                yield ": heartbeat\n\n"
                continue

            if item_type == "event":
                if isinstance(payload, Mapping):
                    last_event = payload
                yield _encode_data(payload)
                continue

            exc = payload
            if logger is not None:
                logger.error("SSE stream producer failed: %s", exc)
            yield _encode_data(builder(exc, last_event))
            break
    finally:
        if not pump_task.done():
            pump_task.cancel()
            with suppress(asyncio.CancelledError):
                await pump_task


def sse_response(
    events: AsyncIterator[Mapping[str, Any]],
    *,
    heartbeat_seconds: float = _DEFAULT_HEARTBEAT_SECONDS,
    logger: logging.Logger | None = None,
    error_event_builder: ErrorEventBuilder | None = None,
    include_done_sentinel: bool = False,
) -> StreamingResponse:
    """Create a StreamingResponse with standardized SSE behavior."""

    async def _stream() -> AsyncIterator[str]:
        async for chunk in sse_chunks(
            events,
            heartbeat_seconds=heartbeat_seconds,
            logger=logger,
            error_event_builder=error_event_builder,
        ):
            yield chunk
        if include_done_sentinel:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers=dict(_SSE_HEADERS),
    )

