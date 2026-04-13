"""Shared SSE event contract helpers for ai_copilot use cases.

Canonical node update event shape:

    {
        "type": "node_update",
        "node": "<graph_node_name>",
        "data": <json_safe_payload>,
    }

Notes:
- ``data`` is the single canonical payload field for ``node_update``.
- Payloads are normalized to JSON-safe primitives for SSE transport.
"""

from __future__ import annotations

from typing import Any, Literal, TypeAlias, TypedDict

JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


class NodeUpdateEvent(TypedDict):
    """SSE event emitted for each LangGraph node update."""

    type: Literal["node_update"]
    node: str
    data: JSONValue


def to_json_safe(value: Any) -> JSONValue:
    """Convert arbitrary values to JSON-safe transport values."""
    if isinstance(value, dict):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [to_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    return str(value)


def emit_node_update(node_name: str, payload: Any) -> NodeUpdateEvent:
    """Build a canonical ``node_update`` SSE event."""
    return {
        "type": "node_update",
        "node": node_name,
        "data": to_json_safe(payload),
    }

