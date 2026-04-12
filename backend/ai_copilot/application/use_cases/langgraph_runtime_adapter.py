"""LangGraph runtime compatibility adapter.

This module centralizes runtime contract handling across LangGraph versions.

Goals:
- Prefer explicit v2 invocation/stream contracts at graph boundaries.
- Fall back to legacy invocation when the runtime does not support `version=...`.
- Normalize legacy and v2 interrupt/stream payload shapes for callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal

LEGACY_INTERRUPT_KEY = "__interrupt__"


@dataclass(frozen=True)
class LangGraphVersionStrategy:
    """Invocation version strategy at graph boundaries."""

    preferred_version: str | None = "v2"
    allow_legacy_fallback: bool = True


DEFAULT_LANGGRAPH_VERSION_STRATEGY = LangGraphVersionStrategy()


@dataclass(frozen=True)
class NormalizedStreamEntry:
    """One normalized stream item from a chunk."""

    kind: Literal["update", "interrupt"]
    payload: Any
    node_name: str | None = None


@dataclass(frozen=True)
class NormalizedStreamChunk:
    """Normalized stream chunk across legacy and v2 output formats."""

    entries: tuple[NormalizedStreamEntry, ...]


@dataclass(frozen=True)
class NormalizedInvokeResult:
    """Normalized invoke result across legacy dict and v2 GraphOutput shapes."""

    value: Any
    interrupt_payloads: tuple[Any, ...]


def _is_version_argument_error(exc: TypeError) -> bool:
    message = str(exc)
    return "version" in message and "unexpected keyword argument" in message


def _iter_invoke_kwargs(
    config: dict,
    strategy: LangGraphVersionStrategy,
) -> tuple[dict[str, Any], ...]:
    legacy = {"config": config}
    if strategy.preferred_version:
        preferred = {"config": config, "version": strategy.preferred_version}
        if strategy.allow_legacy_fallback:
            return (preferred, legacy)
        return (preferred,)
    return (legacy,)


async def ainvoke_with_contract(
    graph: Any,
    graph_input: Any,
    *,
    config: dict,
    strategy: LangGraphVersionStrategy = DEFAULT_LANGGRAPH_VERSION_STRATEGY,
) -> Any:
    """Call graph.ainvoke() with explicit version strategy."""

    last_error: TypeError | None = None
    for kwargs in _iter_invoke_kwargs(config, strategy):
        try:
            return await graph.ainvoke(graph_input, **kwargs)
        except TypeError as exc:
            if (
                "version" in kwargs
                and strategy.allow_legacy_fallback
                and _is_version_argument_error(exc)
            ):
                last_error = exc
                continue
            raise

    if last_error is not None:
        raise last_error
    raise RuntimeError("No invocation strategy available for LangGraph ainvoke().")


async def astream_with_contract(
    graph: Any,
    graph_input: Any,
    *,
    config: dict,
    stream_mode: str = "updates",
    strategy: LangGraphVersionStrategy = DEFAULT_LANGGRAPH_VERSION_STRATEGY,
) -> AsyncIterator[NormalizedStreamChunk]:
    """Call graph.astream() with explicit version strategy and normalized chunks."""

    last_error: TypeError | None = None
    for kwargs in _iter_invoke_kwargs(config, strategy):
        try:
            async for chunk in graph.astream(
                graph_input,
                stream_mode=stream_mode,
                **kwargs,
            ):
                yield normalize_stream_chunk(chunk)
            return
        except TypeError as exc:
            if (
                "version" in kwargs
                and strategy.allow_legacy_fallback
                and _is_version_argument_error(exc)
            ):
                last_error = exc
                continue
            raise

    if last_error is not None:
        raise last_error
    raise RuntimeError("No invocation strategy available for LangGraph astream().")


def normalize_stream_chunk(chunk: Any) -> NormalizedStreamChunk:
    """Normalize stream chunks from legacy and v2 LangGraph outputs."""

    payload = _extract_updates_payload(chunk)
    if not isinstance(payload, dict):
        return NormalizedStreamChunk(entries=())

    entries: list[NormalizedStreamEntry] = []
    for node_name, node_output in payload.items():
        if node_name == LEGACY_INTERRUPT_KEY:
            for interrupt_payload in _coerce_interrupt_payloads(node_output):
                entries.append(
                    NormalizedStreamEntry(
                        kind="interrupt",
                        payload=interrupt_payload,
                    ),
                )
            continue
        entries.append(
            NormalizedStreamEntry(
                kind="update",
                node_name=str(node_name),
                payload=node_output,
            ),
        )
    return NormalizedStreamChunk(entries=tuple(entries))


def normalize_invoke_result(result: Any) -> NormalizedInvokeResult:
    """Normalize invoke result from legacy dict and v2 GraphOutput."""

    if hasattr(result, "value") and hasattr(result, "interrupts"):
        return NormalizedInvokeResult(
            value=getattr(result, "value"),
            interrupt_payloads=_coerce_interrupt_payloads(getattr(result, "interrupts")),
        )

    if isinstance(result, dict) and LEGACY_INTERRUPT_KEY in result:
        return NormalizedInvokeResult(
            value=result,
            interrupt_payloads=_coerce_interrupt_payloads(result.get(LEGACY_INTERRUPT_KEY)),
        )

    return NormalizedInvokeResult(value=result, interrupt_payloads=())


def interrupt_payloads_from_exception(exc: BaseException) -> tuple[Any, ...]:
    """Extract interrupt payload(s) from GraphInterrupt-like exceptions."""

    if not _looks_like_interrupt_exception(exc):
        return ()

    if hasattr(exc, "interrupts"):
        payloads = _coerce_interrupt_payloads(getattr(exc, "interrupts"))
        if payloads:
            return payloads

    if hasattr(exc, "value"):
        payloads = _coerce_interrupt_payloads(getattr(exc, "value"))
        if payloads:
            return payloads

    args = getattr(exc, "args", ())
    if args:
        payloads = _coerce_interrupt_payloads(args[0])
        if payloads:
            return payloads
        payloads = _coerce_interrupt_payloads(args)
        if payloads:
            return payloads

    return ()


def first_interrupt_payload(payloads: tuple[Any, ...]) -> Any | None:
    """Return the first interrupt payload, if any."""

    return payloads[0] if payloads else None


def _extract_updates_payload(chunk: Any) -> Any:
    # Legacy "updates" mode: chunk is already {node_name: update}.
    if not isinstance(chunk, dict):
        return chunk

    # v2 StreamPart shape:
    # {"type": "updates", "ns": (...), "data": {node_name: update}}
    if "type" in chunk and "data" in chunk:
        if chunk.get("type") != "updates":
            return {}
        return chunk.get("data")

    return chunk


def _looks_like_interrupt_exception(exc: BaseException) -> bool:
    if hasattr(exc, "interrupts"):
        return True
    name = type(exc).__name__
    return "Interrupt" in name


def _coerce_interrupt_payloads(raw: Any) -> tuple[Any, ...]:
    if raw is None:
        return ()

    if isinstance(raw, dict) and LEGACY_INTERRUPT_KEY in raw:
        return _coerce_interrupt_payloads(raw[LEGACY_INTERRUPT_KEY])

    payloads = [
        getattr(item, "value", item)
        for item in _flatten_interrupt_items(raw)
    ]
    return tuple(payloads)


def _flatten_interrupt_items(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        flattened: list[Any] = []
        for item in raw:
            flattened.extend(_flatten_interrupt_items(item))
        return flattened
    return [raw]
